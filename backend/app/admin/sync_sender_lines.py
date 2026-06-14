"""Sync the local sender-line pool with Twilio's number inventory.

Source-of-truth split: Twilio owns *which numbers exist* (and which belong to a
Messaging Service); this backend owns *how they're assigned* to users/personas.
``service_identities`` is our local mirror of Twilio's inventory — sender
bindings, request snapshots, and the iOS "Save Contact" number all read from it,
so the mirror must reflect the real numbers.

This is a manual/admin reconciliation (run it after changing Twilio numbers); it
is intentionally *not* on the request path:

    python -m app.admin.sync_sender_lines      # or: make sync-senders

Behavior:
  - upsert each Twilio number into ``service_identities`` (provider ``twilio``),
    keyed by the phone-number SID, with SMS/voice capabilities;
  - mark Twilio rows that vanished from inventory ``disabled`` (their bindings
    then orphan + reallocate to a live line on the next send);
  - once real SMS senders exist, stop allocating SMS from non-Twilio lines (the
    mock seed) by clearing their SMS capability — existing mock bindings then
    reallocate to a real number. Voice capability is left intact so local mock
    voice still works.

The Twilio fetch (I/O) and the DB upsert (pure) are separated so the upsert is
unit-testable without network access.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.models.enums import ServiceIdentityStatus
from app.db.models.service_identity import ServiceIdentity
from app.db.session import SessionLocal

logger = get_logger("admin.sync_sender_lines")

_API_BASE = "https://api.twilio.com/2010-04-01"
_MESSAGING_API = "https://messaging.twilio.com/v1"

TWILIO_PROVIDER = "twilio"


@dataclass
class TwilioNumber:
    sid: str
    e164: str
    sms: bool
    voice: bool


def fetch_twilio_numbers() -> list[TwilioNumber]:
    """Pull the sendable numbers from Twilio.

    Uses the Messaging Service's sender pool when one is configured (the precise
    set we send through); otherwise all account numbers.
    """
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise RuntimeError(
            "Twilio credentials required: set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )
    auth = (settings.twilio_account_sid, settings.twilio_auth_token)

    if settings.twilio_messaging_service_sid:
        url = f"{_MESSAGING_API}/Services/{settings.twilio_messaging_service_sid}/PhoneNumbers"
        resp = httpx.get(url, auth=auth, timeout=15.0)
        resp.raise_for_status()
        items = resp.json().get("phone_numbers", [])
    else:
        url = f"{_API_BASE}/Accounts/{settings.twilio_account_sid}/IncomingPhoneNumbers.json"
        resp = httpx.get(url, auth=auth, params={"PageSize": 1000}, timeout=15.0)
        resp.raise_for_status()
        items = resp.json().get("incoming_phone_numbers", [])

    numbers: list[TwilioNumber] = []
    for item in items:
        sid = item.get("sid")
        e164 = item.get("phone_number")
        if not sid or not e164:
            continue
        sms, voice = _capabilities(item.get("capabilities"))
        numbers.append(TwilioNumber(sid=sid, e164=e164, sms=sms, voice=voice))
    return numbers


def _capabilities(caps) -> tuple[bool, bool]:
    """Normalize Twilio's two capability shapes to (sms, voice).

    IncomingPhoneNumbers returns a dict (``{"sms": true, "voice": true}``); the
    Messaging Service PhoneNumbers endpoint returns a list (``["SMS","Voice"]``).
    """
    if isinstance(caps, dict):
        return bool(caps.get("sms", True)), bool(caps.get("voice", False))
    if isinstance(caps, list):
        lowered = {str(c).lower() for c in caps}
        return "sms" in lowered, "voice" in lowered
    return True, False


def sync_sender_lines(
    db: Session,
    numbers: list[TwilioNumber],
    *,
    messaging_service_sid: str | None = None,
) -> dict:
    """Reconcile ``service_identities`` against the given Twilio numbers.

    Pure DB logic (no network) so it can be unit-tested with fabricated numbers.
    """
    seen_sids: set[str] = set()
    created = updated = 0

    for n in numbers:
        seen_sids.add(n.sid)
        row = db.execute(
            select(ServiceIdentity).where(ServiceIdentity.external_identity_id == n.sid)
        ).scalars().first()
        if row is None:
            # Adopt a pre-existing row with the same number (e.g. a manual seed).
            row = db.execute(
                select(ServiceIdentity).where(ServiceIdentity.identity_value == n.e164)
            ).scalars().first()
        if row is None:
            row = ServiceIdentity(provider=TWILIO_PROVIDER, identity_value=n.e164)
            db.add(row)
            created += 1
        else:
            updated += 1
        row.provider = TWILIO_PROVIDER
        row.external_identity_id = n.sid
        row.identity_value = n.e164
        row.capability_outbound_sms = n.sms
        row.capability_outbound_voice = n.voice
        row.twilio_messaging_service_sid = messaging_service_sid
        row.status = ServiceIdentityStatus.active.value
        if not row.display_label:
            row.display_label = "twilio"
    db.flush()

    # Disable Twilio rows no longer present upstream; their bindings reallocate.
    disabled = 0
    twilio_rows = db.execute(
        select(ServiceIdentity).where(ServiceIdentity.provider == TWILIO_PROVIDER)
    ).scalars().all()
    for row in twilio_rows:
        if (
            row.external_identity_id not in seen_sids
            and row.status == ServiceIdentityStatus.active.value
        ):
            row.status = ServiceIdentityStatus.disabled.value
            disabled += 1

    # Once a real SMS sender exists, stop using non-Twilio lines (the mock seed)
    # for SMS so allocation and the explicit-From use the real number. Existing
    # mock bindings orphan + reallocate on next send. Voice is left untouched.
    has_real_sms = any(
        row.capability_outbound_sms and row.status == ServiceIdentityStatus.active.value
        for row in twilio_rows
    )
    sms_demoted = 0
    if has_real_sms:
        others = db.execute(
            select(ServiceIdentity).where(
                ServiceIdentity.provider != TWILIO_PROVIDER,
                ServiceIdentity.capability_outbound_sms.is_(True),
            )
        ).scalars().all()
        for row in others:
            row.capability_outbound_sms = False
            sms_demoted += 1

    db.commit()
    return {
        "twilio_numbers": len(numbers),
        "created": created,
        "updated": updated,
        "disabled": disabled,
        "sms_demoted": sms_demoted,
    }


def main() -> None:  # pragma: no cover - thin I/O wrapper
    configure_logging()
    numbers = fetch_twilio_numbers()
    db = SessionLocal()
    try:
        result = sync_sender_lines(
            db, numbers, messaging_service_sid=settings.twilio_messaging_service_sid
        )
    finally:
        db.close()
    logger.info("sender_lines_synced", extra={"provider": "admin"})
    print("Synced sender lines:", result)


if __name__ == "__main__":  # pragma: no cover
    main()
