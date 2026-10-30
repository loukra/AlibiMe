"""Request creation, retrieval, cancellation — where the load-bearing
invariants are enforced.

Invariants enforced here:
  - Client never supplies a destination number (schema-level + no field exists).
  - Destination resolved from the user's verified primary phone.
  - At most one active live request per user.
  - Idempotent per (user, client_request_id).
  - Schedule window <= 24h; allowed delays 0/30/300.
  - Template must support the chosen channel.
  - Credits checked before persisting (reserved later at dispatch).
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.clock import utcnow
from app.core.config import settings
from app.core.errors import (
    ActiveRequestExists,
    NotFound,
    RequestNotCancelable,
    ValidationFailed,
)
from app.db.models.enums import (
    Channel,
    LIVE_REQUEST_STATUSES,
    RequestStatus,
    ScheduledKind,
)
from app.db.models.request import Request
from app.db.models.template import Template
from app.domain.billing import credits
from app.domain.requests import state
from app.domain.sender_identity import service as sender_identity
from app.domain.templates import service as templates
from app.domain.users.service import require_primary_phone

ALLOWED_DELAYS = {0, 30, 300}
MAX_SCHEDULE_HORIZON = timedelta(hours=24)
# How many jobs a user may have queued/in-flight at once. Multiple pending jobs
# are allowed (a queue); this caps it so it can't grow unbounded.
MAX_PENDING_REQUESTS = 3

_LIVE_VALUES = {s.value for s in LIVE_REQUEST_STATUSES}


def get_active_request(db: Session, user_id: uuid.UUID) -> Request | None:
    """The soonest upcoming live request (used for the Home 'next job' chip)."""
    return db.execute(
        select(Request)
        .where(Request.user_id == user_id, Request.status.in_(_LIVE_VALUES))
        .order_by(Request.execute_at.asc())
    ).scalars().first()


def count_active_requests(db: Session, user_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(Request)
        .where(Request.user_id == user_id, Request.status.in_(_LIVE_VALUES))
    ).scalar_one()


def get_request(db: Session, user_id: uuid.UUID, request_id: uuid.UUID) -> Request:
    req = db.get(Request, request_id)
    if req is None or req.user_id != user_id:
        raise NotFound("Request not found.")
    return req


def _resolve_execute_at(delay_seconds: int | None, scheduled_at, now) -> tuple:
    if scheduled_at is not None:
        if scheduled_at.tzinfo is None:
            raise ValidationFailed("scheduled_at must include a timezone offset.")
        if scheduled_at <= now:
            from app.core.errors import InvalidScheduleWindow

            raise InvalidScheduleWindow("scheduled_at must be in the future.")
        if scheduled_at > now + MAX_SCHEDULE_HORIZON:
            from app.core.errors import InvalidScheduleWindow

            raise InvalidScheduleWindow("scheduled_at must be within the next 24 hours.")
        return scheduled_at, ScheduledKind.exact_time

    delay = delay_seconds or 0
    if delay not in ALLOWED_DELAYS:
        raise ValidationFailed(f"delay_seconds must be one of {sorted(ALLOWED_DELAYS)}.")
    kind = ScheduledKind.immediate if delay == 0 else ScheduledKind.delayed
    return now + timedelta(seconds=delay), kind


def create_request(
    db: Session,
    user_id: uuid.UUID,
    *,
    client_request_id: str,
    template_id: uuid.UUID,
    channel: str,
    delay_seconds: int | None,
    scheduled_at,
    user_locale: str,
) -> Request:
    if channel not in (Channel.call.value, Channel.sms.value):
        raise ValidationFailed("channel must be 'call' or 'sms'.")
    if (delay_seconds is None) == (scheduled_at is None):
        raise ValidationFailed("Exactly one of delay_seconds or scheduled_at must be set.")

    # Idempotency: return the existing request for this (user, client_request_id).
    existing = db.execute(
        select(Request).where(
            Request.user_id == user_id,
            Request.client_request_id == client_request_id,
        )
    ).scalars().first()
    if existing:
        return existing

    rate_limit.check_and_increment(db, rate_limit.REQUEST_CREATE, str(user_id))

    # Destination is always the user's verified primary phone (never client-supplied).
    primary_phone = require_primary_phone(db, user_id)

    # Multiple pending jobs are allowed (a queue), capped so it can't grow
    # unbounded. The idempotency check above already returned any existing job
    # for this client_request_id, so retries don't count against the cap.
    if count_active_requests(db, user_id) >= MAX_PENDING_REQUESTS:
        raise ActiveRequestExists(
            f"You can have at most {MAX_PENDING_REQUESTS} jobs queued at once. "
            "Cancel one to schedule another."
        )

    template = db.get(Template, template_id)
    if template is None or not template.active:
        raise NotFound("Template not found.")
    version = templates.resolve_version(db, template.id, user_locale)
    templates.assert_channel_supported(version, channel)

    now = utcnow()
    execute_at, scheduled_kind = _resolve_execute_at(delay_seconds, scheduled_at, now)

    cost = credit_cost(channel)
    if not credits.has_credits(db, user_id, cost):
        from app.core.errors import InsufficientCredits

        raise InsufficientCredits()

    # Resolve (or allocate) a stable sender binding so the same persona keeps the
    # same number across sends and channels, and snapshot it onto the request.
    sender_binding_id = None
    sender_persona_key = None
    sender_display_name_snapshot = None
    sender_phone_e164_snapshot = None
    resolved = sender_identity.resolve_or_allocate_binding(
        db,
        user_id,
        sender_persona_key=template.sender_persona_key,
        channel=channel,
        template_id=template.id,
    )
    if resolved is not None:
        binding, line = resolved
        sender_binding_id = binding.id
        sender_persona_key = template.sender_persona_key
        sender_display_name_snapshot = template.sender_display_name
        sender_phone_e164_snapshot = line.identity_value

    request = Request(
        user_id=user_id,
        template_id=template.id,
        template_version_id=version.id,
        channel=channel,
        primary_phone_number_id=primary_phone.id,
        client_request_id=client_request_id,
        requested_at=now,
        execute_at=execute_at,
        status=RequestStatus.scheduled.value,
        scheduled_kind=scheduled_kind.value,
        credit_cost_units=cost,
        credits_reserved=False,
        sender_binding_id=sender_binding_id,
        sender_persona_key=sender_persona_key,
        sender_display_name_snapshot=sender_display_name_snapshot,
        sender_phone_e164_snapshot=sender_phone_e164_snapshot,
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        # Concurrent duplicate with same client_request_id — return the winner.
        db.rollback()
        winner = db.execute(
            select(Request).where(
                Request.user_id == user_id,
                Request.client_request_id == client_request_id,
            )
        ).scalars().first()
        if winner:
            return winner
        raise
    db.commit()
    return request


def credit_cost(channel: str) -> int:
    return settings.call_credit_cost if channel == Channel.call.value else settings.sms_credit_cost


def sender_identity_payload(db: Session, request: Request) -> dict | None:
    """Sender metadata for API responses; ``None`` when no binding was resolved
    (an empty sender pool)."""
    if request.sender_binding_id is None:
        return None
    template = db.get(Template, request.template_id)
    supports_contact_save = bool(template.supports_contact_save) if template else False
    return {
        "sender_binding_id": str(request.sender_binding_id),
        "sender_persona_key": request.sender_persona_key,
        "sender_display_name": request.sender_display_name_snapshot,
        "sender_phone_e164": request.sender_phone_e164_snapshot,
        "contact_prompt_recommended": supports_contact_save,
    }


def latest_call_attempt(db: Session, request_id: uuid.UUID):
    from app.db.models.attempts import CallAttempt

    return db.execute(
        select(CallAttempt)
        .where(CallAttempt.request_id == request_id)
        .order_by(CallAttempt.attempt_no.desc())
    ).scalars().first()


def latest_message_attempt(db: Session, request_id: uuid.UUID):
    from app.db.models.attempts import MessageAttempt

    return db.execute(
        select(MessageAttempt)
        .where(MessageAttempt.request_id == request_id)
        .order_by(MessageAttempt.attempt_no.desc())
    ).scalars().first()


def latest_attempt_summary(db: Session, request: Request) -> dict | None:
    if request.channel == Channel.call.value:
        attempt = latest_call_attempt(db, request.id)
        if not attempt:
            return None
        return {
            "status": attempt.status,
            "provider_status": attempt.provider_status,
            "duration_seconds": attempt.duration_seconds,
            "failure_reason": attempt.ended_reason,
        }
    attempt = latest_message_attempt(db, request.id)
    if not attempt:
        return None
    return {
        "status": attempt.status,
        "provider_status": attempt.provider_status,
        "duration_seconds": None,
        "failure_reason": attempt.failure_reason,
    }


def cancel_request(db: Session, user_id: uuid.UUID, request_id: uuid.UUID) -> Request:
    req = get_request(db, user_id, request_id)
    if not state.is_cancelable(req.status):
        raise RequestNotCancelable()
    state.assert_transition(req.status, RequestStatus.canceled.value)
    req.status = RequestStatus.canceled.value
    req.cancel_reason = "canceled_by_user"
    if req.credits_reserved:
        credits.release(db, user_id, req.credit_cost_units, req.id)
        req.credits_reserved = False
    db.commit()
    return req
