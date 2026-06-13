from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.core.twilio_webhook import verify_twilio_signature
from app.domain.requests.webhook_ingest import ingest_sms_webhook
from app.providers.factory import get_message_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
logger = get_logger("webhooks.sms")


def _should_verify_signature() -> bool:
    """Enforce Twilio signatures only when actually running on Twilio. In mock/
    local/test modes verification is skipped so those flows keep working."""
    return bool(
        settings.message_provider == "twilio_messaging"
        and settings.twilio_auth_token
        and settings.twilio_status_callback_url
    )


@router.post("/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    # Observability: record whether Twilio's authenticity signature was present.
    # Never log its value.
    signature = request.headers.get("x-twilio-signature")
    content_type = request.headers.get("content-type", "")
    logger.info(
        "sms_webhook_received x_twilio_signature=%s content_type=%s",
        "present" if signature else "absent",
        content_type or "(none)",
        extra={"provider": "twilio_messaging"},
    )

    # Twilio posts status callbacks as application/x-www-form-urlencoded; the
    # mock provider posts JSON. Accept both and hand a plain dict to the provider.
    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = dict(await request.form())

    # Reject forged/unsigned callbacks before doing any work. We verify against
    # the configured public callback URL (the exact string Twilio signed).
    if _should_verify_signature():
        ok = verify_twilio_signature(
            settings.twilio_status_callback_url, payload, signature, settings.twilio_auth_token
        )
        if not ok:
            logger.warning(
                "sms_webhook_rejected reason=%s",
                "missing_signature" if not signature else "invalid_signature",
                extra={"provider": "twilio_messaging"},
            )
            raise HTTPException(status_code=403, detail="invalid Twilio signature")

    return ingest_sms_webhook(db, get_message_provider(), payload)
