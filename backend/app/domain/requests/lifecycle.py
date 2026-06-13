"""Apply provider events to attempts and recompute request status.

Shared by the dispatch worker and the webhook ingestion path so status logic
lives in exactly one place.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.db.models.artifact import RequestArtifact
from app.db.models.attempts import CallAttempt, MessageAttempt
from app.db.models.enums import (
    CallAttemptStatus,
    MessageAttemptStatus,
    RequestStatus,
)
from app.db.models.request import Request
from app.domain.requests import state

# Map a call attempt status to the request status it implies.
_CALL_TO_REQUEST = {
    CallAttemptStatus.queued.value: RequestStatus.provider_accepted.value,
    CallAttemptStatus.ringing.value: RequestStatus.active.value,
    CallAttemptStatus.in_progress.value: RequestStatus.active.value,
    CallAttemptStatus.ended.value: RequestStatus.completed.value,
    CallAttemptStatus.failed_pre_dial.value: RequestStatus.failed.value,
    CallAttemptStatus.failed_post_dial.value: RequestStatus.failed.value,
    CallAttemptStatus.canceled.value: RequestStatus.canceled.value,
}

_MESSAGE_TO_REQUEST = {
    MessageAttemptStatus.queued.value: RequestStatus.provider_accepted.value,
    MessageAttemptStatus.sent.value: RequestStatus.provider_accepted.value,
    MessageAttemptStatus.delivered.value: RequestStatus.completed.value,
    MessageAttemptStatus.failed_pre_send.value: RequestStatus.failed.value,
    MessageAttemptStatus.failed_post_send.value: RequestStatus.failed.value,
    MessageAttemptStatus.canceled.value: RequestStatus.canceled.value,
}


def _advance_request(db: Session, request: Request, target_status: str) -> None:
    if request.status == target_status:
        return
    if not state.can_transition(request.status, target_status):
        # Ignore out-of-order / stale events rather than crashing.
        return
    request.status = target_status
    request.updated_at = utcnow()


def apply_call_event(db: Session, attempt: CallAttempt, mapped_status: str | None, fields: dict) -> None:
    if mapped_status is None:
        return
    request = db.get(Request, attempt.request_id)
    now = utcnow()

    if mapped_status == CallAttemptStatus.ringing.value and attempt.ringing_at is None:
        attempt.ringing_at = now
    elif mapped_status == CallAttemptStatus.in_progress.value and attempt.answered_at is None:
        attempt.answered_at = now
    elif mapped_status == CallAttemptStatus.ended.value:
        attempt.ended_at = now
        attempt.ended_reason = fields.get("ended_reason")
        if fields.get("duration_seconds") is not None:
            attempt.duration_seconds = int(fields["duration_seconds"])
        if fields.get("estimated_cost_minor") is not None:
            attempt.estimated_cost_minor = int(fields["estimated_cost_minor"])

    attempt.status = mapped_status
    attempt.updated_at = now

    target = _CALL_TO_REQUEST.get(mapped_status)
    if target:
        _advance_request(db, request, target)
        if target == RequestStatus.completed.value:
            _ensure_artifact(db, request, summary=_call_summary(request, attempt))


def apply_message_event(
    db: Session, attempt: MessageAttempt, mapped_status: str | None, fields: dict
) -> None:
    if mapped_status is None:
        return
    request = db.get(Request, attempt.request_id)
    now = utcnow()

    if mapped_status == MessageAttemptStatus.sent.value and attempt.sent_at is None:
        attempt.sent_at = now
    elif mapped_status == MessageAttemptStatus.delivered.value:
        attempt.delivered_at = now
        if fields.get("estimated_cost_minor") is not None:
            attempt.estimated_cost_minor = int(fields["estimated_cost_minor"])
    elif mapped_status in (
        MessageAttemptStatus.failed_pre_send.value,
        MessageAttemptStatus.failed_post_send.value,
    ):
        attempt.failed_at = now
        attempt.failure_reason = fields.get("failure_reason")

    attempt.status = mapped_status
    attempt.updated_at = now

    target = _MESSAGE_TO_REQUEST.get(mapped_status)
    if target:
        _advance_request(db, request, target)
        if target == RequestStatus.completed.value:
            preview = (request.request_plan_snapshot_json or {}).get("rendered_sms_body")
            _ensure_artifact(db, request, delivered_preview=preview)


def _call_summary(request: Request, attempt: CallAttempt) -> str:
    snap = request.request_plan_snapshot_json or {}
    persona = snap.get("caller_persona", "caller")
    dur = attempt.duration_seconds or 0
    return f"Call from {persona} completed ({dur}s)."


def _ensure_artifact(
    db: Session,
    request: Request,
    *,
    summary: str | None = None,
    delivered_preview: str | None = None,
) -> None:
    existing = (
        db.query(RequestArtifact).filter(RequestArtifact.request_id == request.id).first()
    )
    if existing:
        return
    db.add(
        RequestArtifact(
            request_id=request.id,
            summary_text=summary,
            delivered_message_preview=delivered_preview,
        )
    )
