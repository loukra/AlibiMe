"""App Store Server Notifications V2.

Apple posts a signed payload for purchase events; we act on refunds (credits
taken back) and store every notification for the audit trail.
Set the URL in App Store Connect to <PUBLIC_BASE_URL>/v1/webhooks/app-store.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.clock import utcnow
from app.db.models.enums import WebhookProcessingStatus
from app.db.models.webhook_event import WebhookEvent
from app.domain.billing.credit_packages import refund_store_transaction
from app.domain.billing.store import get_store_verifier

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

_REFUND_TYPES = {"REFUND"}


class AppStoreNotificationBody(BaseModel):
    signedPayload: str


@router.post("/app-store")
def app_store_webhook(body: AppStoreNotificationBody, db: Session = Depends(get_db)) -> dict:
    note = get_store_verifier().verify_notification(body.signedPayload)
    tx = note.transaction
    event = WebhookEvent(
        provider="app_store",
        external_event_id=None,
        event_type=note.type,
        payload_json={"type": note.type, "transaction_id": tx.transaction_id if tx else None},
        processing_status=WebhookProcessingStatus.received.value,
    )
    db.add(event)
    db.flush()
    refunded = False
    if note.type in _REFUND_TYPES and tx is not None:
        refunded = refund_store_transaction(db, tx.transaction_id)
    event.processing_status = WebhookProcessingStatus.processed.value
    event.processed_at = utcnow()
    db.commit()
    return {"status": "processed", "refunded": refunded}
