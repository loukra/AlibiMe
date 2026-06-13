from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.requests.webhook_ingest import ingest_sms_webhook
from app.providers.factory import get_message_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    # Twilio posts status callbacks as application/x-www-form-urlencoded; the
    # mock provider posts JSON. Accept both and hand a plain dict to the provider.
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = dict(await request.form())
    return ingest_sms_webhook(db, get_message_provider(), payload)
