"""Webhook ingestion: persist raw, dedupe by external event id, then apply."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.db.models.attempts import CallAttempt, MessageAttempt
from app.db.models.enums import WebhookProcessingStatus
from app.db.models.webhook_event import WebhookEvent
from app.domain.requests import lifecycle
from app.providers.messaging.base import MessageProvider
from app.providers.voice.base import VoiceProvider


def _persist_raw(db: Session, provider: str, external_event_id: str | None, event_type: str | None, payload: dict) -> tuple[WebhookEvent, bool]:
    """Persist the raw event. Returns (event, is_duplicate)."""
    event = WebhookEvent(
        provider=provider,
        external_event_id=external_event_id,
        event_type=event_type,
        payload_json=payload,
        processing_status=WebhookProcessingStatus.received.value,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None, True  # duplicate (provider, external_event_id)
    return event, False


def ingest_voice_webhook(db: Session, provider: VoiceProvider, payload: dict) -> dict:
    parsed = provider.parse_webhook(payload)
    event, is_dup = _persist_raw(
        db, provider.name, parsed.external_event_id, parsed.event_type, payload
    )
    if is_dup:
        return {"status": "duplicate"}

    if parsed.provider_ref_id:
        attempt = db.execute(
            select(CallAttempt).where(CallAttempt.provider_call_id == parsed.provider_ref_id)
        ).scalars().first()
        if attempt:
            attempt.provider_status = parsed.event_type
            lifecycle.apply_call_event(db, attempt, parsed.mapped_status, parsed.fields)

    event.processing_status = WebhookProcessingStatus.processed.value
    event.processed_at = utcnow()
    db.commit()
    return {"status": "processed"}


def ingest_sms_webhook(db: Session, provider: MessageProvider, payload: dict) -> dict:
    parsed = provider.parse_webhook(payload)
    event, is_dup = _persist_raw(
        db, provider.name, parsed.external_event_id, parsed.event_type, payload
    )
    if is_dup:
        return {"status": "duplicate"}

    if parsed.provider_ref_id:
        attempt = db.execute(
            select(MessageAttempt).where(
                MessageAttempt.provider_message_id == parsed.provider_ref_id
            )
        ).scalars().first()
        if attempt:
            attempt.provider_status = parsed.event_type
            lifecycle.apply_message_event(db, attempt, parsed.mapped_status, parsed.fields)

    event.processing_status = WebhookProcessingStatus.processed.value
    event.processed_at = utcnow()
    db.commit()
    return {"status": "processed"}
