"""Dispatch due requests through provider adapters.

Claim model (durable scheduler):
  1. Poll due `requests` (status=scheduled, execute_at<=now).
  2. Claim with FOR UPDATE SKIP LOCKED and flip to `dispatching` (committed),
     so no other worker double-dispatches.
  3. Dispatch each claimed request via the channel adapter in its own txn.

Credit policy:
  - reserve at dispatch
  - capture on provider acceptance
  - release on pre-dispatch failure (so internal failures don't burn credits)

Retry policy:
  - only pre-dispatch transient failures, at most 1 retry per request.
  - never re-dispatch once a human-facing outcome happened.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import phonenumbers
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.prompt import PROMPT_VERSION, build_system_prompt
from app.core.clock import utcnow
from app.core.config import settings
from app.core.errors import InsufficientCredits
from app.core.logging import get_logger
from app.db.models.attempts import CallAttempt, MessageAttempt
from app.db.models.enums import (
    CallAttemptStatus,
    Channel,
    MessageAttemptStatus,
    RequestStatus,
    ServiceIdentityStatus,
)
from app.db.models.phone import PhoneNumber
from app.db.models.request import Request
from app.db.models.service_identity import ServiceIdentity
from app.db.models.template import Template, TemplateVersion
from app.db.models.user import User
from app.domain.billing import credits
from app.domain.profile import context as profile_context
from app.domain.templates.service import build_call_variables, build_request_plan_snapshot
from app.providers.factory import get_message_provider, get_voice_provider
from app.providers.messaging.base import MessageProvider
from app.providers.types import (
    ProviderError,
    RequestPlan,
    TransientProviderError,
)
from app.providers.voice.base import VoiceProvider
from app.core.security import decrypt_phone

logger = get_logger("worker.dispatch")

MAX_PREDISPATCH_RETRIES = 1

# An alibi that arrives much later than asked for is useless: one this overdue
# (the worker was down) expires instead of going out. Credits are only taken
# at dispatch, so nothing is charged.
MISSED_AFTER = timedelta(minutes=10)


def _supports_skip_locked(db: Session) -> bool:
    return db.bind.dialect.name == "postgresql"


def claim_due_requests(db: Session, now=None, batch_size: int = 20) -> list[uuid.UUID]:
    now = now or utcnow()
    stmt = (
        select(Request)
        .where(
            Request.status == RequestStatus.scheduled.value,
            Request.execute_at <= now,
        )
        .order_by(Request.execute_at)
        .limit(batch_size)
    )
    if _supports_skip_locked(db):
        stmt = stmt.with_for_update(skip_locked=True)
    rows = db.execute(stmt).scalars().all()
    ids = []
    for req in rows:
        req.updated_at = now
        if req.execute_at < now - MISSED_AFTER:
            req.status = RequestStatus.expired.value
            req.last_error_code = "missed_window"
            req.last_error_message = "Not sent: too late to be useful."
            continue
        req.status = RequestStatus.dispatching.value
        ids.append(req.id)
    db.commit()
    return ids


def _select_service_identity(db: Session, channel: str) -> ServiceIdentity | None:
    stmt = select(ServiceIdentity).where(
        ServiceIdentity.status == ServiceIdentityStatus.active.value
    )
    if channel == Channel.call.value:
        stmt = stmt.where(ServiceIdentity.capability_outbound_voice.is_(True))
    else:
        stmt = stmt.where(ServiceIdentity.capability_outbound_sms.is_(True))
    return db.execute(stmt.order_by(ServiceIdentity.created_at)).scalars().first()


def _resolve_dispatch_identity(db: Session, request: Request) -> ServiceIdentity | None:
    """Prefer the line the request was bound to at create time so the sender
    number stays consistent with what the user was shown; fall back to a pool
    pick if the binding's line is gone or no binding exists."""
    from app.db.models.user_sender_binding import UserSenderBinding

    if request.sender_binding_id is not None:
        binding = db.get(UserSenderBinding, request.sender_binding_id)
        if binding is not None:
            line = db.get(ServiceIdentity, binding.sender_line_id)
            if line is not None and line.status == ServiceIdentityStatus.active.value:
                return line
    return _select_service_identity(db, request.channel)


def _country_code(e164: str | None) -> int | None:
    try:
        return phonenumbers.parse(e164 or "").country_code
    except phonenumbers.NumberParseException:
        return None


def _is_cross_border(sender_e164: str | None, target_e164: str | None) -> bool:
    sender, target = _country_code(sender_e164), _country_code(target_e164)
    return sender is not None and target is not None and sender != target


def _build_plan(db: Session, request: Request, identity: ServiceIdentity | None) -> RequestPlan:
    template = db.get(Template, request.template_id)
    version = db.get(TemplateVersion, request.template_version_id)
    user = db.get(User, request.user_id)
    phone = db.get(PhoneNumber, request.primary_phone_number_id)
    target_e164 = decrypt_phone(phone.phone_e164_encrypted)

    snapshot = build_request_plan_snapshot(
        template=template,
        version=version,
        channel=request.channel,
        locale=user.locale,
        service_identity_value=identity.identity_value if identity else None,
        service_identity_type=identity.identity_type if identity else None,
        target_phone_number_id=str(phone.id),
    )
    # Live call variables (template params + the user's optional context) so the
    # Vapi assistant can adapt the whole call. Built only for calls.
    call_variables: dict = {}
    if request.channel == Channel.call.value:
        context = profile_context.context_dict(db, user.id)
        call_variables = build_call_variables(
            template=template,
            version=version,
            locale=user.locale,
            timezone=getattr(user, "timezone", None),
            first_name=user.first_name,
            rendered_opening_line=snapshot.get("rendered_opening_line"),
            context=context,
        )
        snapshot["call_variables"] = call_variables
        # The agent prompt (app/agent) supersedes the template's short prompt;
        # snapshot it with its version so history shows what the agent was told.
        snapshot["call_system_prompt"] = build_system_prompt(call_variables)
        snapshot["agent_prompt_version"] = PROMPT_VERSION
        cap = settings.cross_border_call_max_seconds
        if cap and _is_cross_border(snapshot.get("service_identity_value"), target_e164):
            snapshot["max_duration_seconds"] = min(snapshot.get("max_duration_seconds") or cap, cap)
    request.request_plan_snapshot_json = snapshot

    return RequestPlan(
        request_id=str(request.id),
        channel=request.channel,
        template_code=snapshot["template_code"],
        template_version=snapshot["template_version"],
        locale=snapshot["locale"],
        caller_persona=snapshot["caller_persona"],
        reason_code=snapshot["reason_code"],
        rendered_opening_line=snapshot.get("rendered_opening_line"),
        rendered_sms_body=snapshot.get("rendered_sms_body"),
        allowed_followup_facts=snapshot.get("allowed_followup_facts", []),
        call_system_prompt=snapshot.get("call_system_prompt"),
        voice_profile_code=snapshot.get("voice_profile_code"),
        max_duration_seconds=snapshot.get("max_duration_seconds"),
        supports_interruptions=snapshot.get("supports_interruptions", False),
        call_variables=call_variables,
        service_identity_value=snapshot.get("service_identity_value"),
        service_identity_type=snapshot.get("service_identity_type"),
        sender_vapi_phone_number_id=identity.vapi_phone_number_id if identity else None,
        target_phone_e164=target_e164,
        target_phone_number_id=snapshot["target_phone_number_id"],
    )


def _fail_request(db: Session, request: Request, code: str, message: str) -> None:
    if request.credits_reserved:
        credits.release(db, request.user_id, request.credit_cost_units, request.id)
        request.credits_reserved = False
    request.status = RequestStatus.failed.value
    request.last_error_code = code
    request.last_error_message = message[:500]
    request.updated_at = utcnow()


def dispatch_one(
    db: Session,
    request_id: uuid.UUID,
    voice_provider: VoiceProvider | None = None,
    message_provider: MessageProvider | None = None,
) -> str:
    request = db.get(Request, request_id)
    if request is None or request.status != RequestStatus.dispatching.value:
        return "skipped"

    # Reserve credits at dispatch time.
    if not request.credits_reserved:
        try:
            credits.reserve(db, request.user_id, request.credit_cost_units, request.id)
            request.credits_reserved = True
        except InsufficientCredits:
            _fail_request(db, request, "insufficient_credits", "No credits at dispatch.")
            db.commit()
            return "failed"

    identity = _resolve_dispatch_identity(db, request)
    if identity is None:
        _fail_request(db, request, "provider_unavailable", "No active service identity.")
        db.commit()
        return "failed"
    request.service_identity_id = identity.id

    plan = _build_plan(db, request, identity)

    if request.channel == Channel.call.value:
        provider = voice_provider or get_voice_provider()
        outcome = _dispatch_call(db, request, plan, provider)
    else:
        provider = message_provider or get_message_provider()
        outcome = _dispatch_sms(db, request, plan, provider)

    db.commit()
    return outcome


def _next_attempt_no(db: Session, model, request_id: uuid.UUID) -> int:
    existing = db.execute(
        select(model).where(model.request_id == request_id)
    ).scalars().all()
    return len(existing) + 1


def _dispatch_call(db: Session, request: Request, plan: RequestPlan, provider: VoiceProvider) -> str:
    attempts_made = 0
    while attempts_made <= MAX_PREDISPATCH_RETRIES:
        attempt = CallAttempt(
            request_id=request.id,
            attempt_no=_next_attempt_no(db, CallAttempt, request.id),
            provider=provider.name,
            status=CallAttemptStatus.provider_requested.value,
            started_at=utcnow(),
        )
        db.add(attempt)
        db.flush()
        try:
            result = provider.create_outbound_call(plan)
        except TransientProviderError as exc:
            attempt.status = CallAttemptStatus.failed_pre_dial.value
            attempt.ended_reason = "transient_error"
            attempts_made += 1
            if attempts_made > MAX_PREDISPATCH_RETRIES:
                _fail_request(db, request, "provider_unavailable", str(exc))
                return "failed"
            continue  # retry pre-dispatch
        except ProviderError as exc:
            attempt.status = CallAttemptStatus.failed_pre_dial.value
            attempt.ended_reason = "rejected"
            _fail_request(db, request, "provider_unavailable", str(exc))
            return "failed"

        # Accepted by provider.
        attempt.provider_call_id = result.provider_call_id
        attempt.provider_status = result.status
        attempt.status = result.status  # e.g. "queued"
        attempt.estimated_cost_minor = result.estimated_cost_minor
        credits.capture(db, request.user_id, request.id)
        request.status = RequestStatus.provider_accepted.value
        request.updated_at = utcnow()
        return "dispatched"
    return "failed"


def _dispatch_sms(db: Session, request: Request, plan: RequestPlan, provider: MessageProvider) -> str:
    attempts_made = 0
    while attempts_made <= MAX_PREDISPATCH_RETRIES:
        attempt = MessageAttempt(
            request_id=request.id,
            attempt_no=_next_attempt_no(db, MessageAttempt, request.id),
            provider=provider.name,
            status=MessageAttemptStatus.provider_requested.value,
            queued_at=utcnow(),
        )
        db.add(attempt)
        db.flush()
        try:
            result = provider.send_sms(plan)
        except TransientProviderError as exc:
            attempt.status = MessageAttemptStatus.failed_pre_send.value
            attempt.failure_reason = "transient_error"
            attempts_made += 1
            if attempts_made > MAX_PREDISPATCH_RETRIES:
                _fail_request(db, request, "provider_unavailable", str(exc))
                return "failed"
            continue
        except ProviderError as exc:
            attempt.status = MessageAttemptStatus.failed_pre_send.value
            attempt.failure_reason = "rejected"
            _fail_request(db, request, "provider_unavailable", str(exc))
            return "failed"

        attempt.provider_message_id = result.provider_message_id
        attempt.provider_status = result.status
        attempt.status = result.status
        attempt.estimated_cost_minor = result.estimated_cost_minor
        credits.capture(db, request.user_id, request.id)
        request.status = RequestStatus.provider_accepted.value
        request.updated_at = utcnow()
        return "dispatched"
    return "failed"


def run_once(
    db: Session,
    *,
    voice_provider: VoiceProvider | None = None,
    message_provider: MessageProvider | None = None,
    now=None,
    batch_size: int = 20,
) -> list[str]:
    """Claim and dispatch one batch. Returns per-request outcomes."""
    ids = claim_due_requests(db, now=now, batch_size=batch_size)
    outcomes = []
    for rid in ids:
        outcomes.append(
            dispatch_one(db, rid, voice_provider=voice_provider, message_provider=message_provider)
        )
    return outcomes
