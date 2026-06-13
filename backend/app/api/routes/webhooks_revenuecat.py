from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.clock import utcnow
from app.db.models.enums import WebhookProcessingStatus
from app.db.models.webhook_event import WebhookEvent
from app.providers.revenuecat import parse_revenuecat_webhook

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/revenuecat")
async def revenuecat_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.json()
    parsed = parse_revenuecat_webhook(payload)
    event = WebhookEvent(
        provider="revenuecat",
        external_event_id=parsed.event_id,
        event_type=parsed.event_type,
        payload_json=payload,
        processing_status=WebhookProcessingStatus.received.value,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    # MVP: persist only. Entitlement mapping is a later manual integration.
    event.processing_status = WebhookProcessingStatus.processed.value
    event.processed_at = utcnow()
    db.commit()
    return {"status": "processed"}
