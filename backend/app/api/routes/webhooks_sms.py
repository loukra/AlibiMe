from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import get_logger
from app.domain.requests.webhook_ingest import ingest_sms_webhook
from app.providers.factory import get_message_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
logger = get_logger("webhooks.sms")


@router.post("/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    # Observability: record whether Twilio's authenticity signature was present.
    # This is the prerequisite for signature verification — never log its value.
    signature_present = request.headers.get("x-twilio-signature") is not None
    content_type = request.headers.get("content-type", "")
    logger.info(
        "sms_webhook_received x_twilio_signature=%s content_type=%s",
        "present" if signature_present else "absent",
        content_type or "(none)",
        extra={"provider": "twilio_messaging"},
    )

    # Twilio posts status callbacks as application/x-www-form-urlencoded; the
    # mock provider posts JSON. Accept both and hand a plain dict to the provider.
    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = dict(await request.form())
    return ingest_sms_webhook(db, get_message_provider(), payload)
