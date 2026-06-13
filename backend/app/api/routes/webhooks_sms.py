from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.requests.webhook_ingest import ingest_sms_webhook
from app.providers.factory import get_message_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.json()
    return ingest_sms_webhook(db, get_message_provider(), payload)
