from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.requests.webhook_ingest import ingest_voice_webhook
from app.providers.factory import get_voice_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
logger = get_logger("webhooks.voice")


def _should_verify_secret() -> bool:
    """Enforce the Vapi shared secret only when actually running on Vapi. In
    mock/local/test modes verification is skipped so those flows keep working."""
    return bool(settings.voice_provider == "vapi" and settings.vapi_webhook_secret)


@router.post("/voice")
async def voice_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    # Vapi echoes the configured Server URL secret as the X-Vapi-Secret header.
    secret = request.headers.get("x-vapi-secret")
    logger.info(
        "voice_webhook_received x_vapi_secret=%s",
        "present" if secret else "absent",
        extra={"provider": "vapi"},
    )

    if _should_verify_secret():
        if not secret or not hmac.compare_digest(secret, settings.vapi_webhook_secret):
            logger.warning(
                "voice_webhook_rejected reason=%s",
                "missing_secret" if not secret else "invalid_secret",
                extra={"provider": "vapi"},
            )
            raise HTTPException(status_code=403, detail="invalid Vapi secret")

    payload = await request.json()
    return ingest_voice_webhook(db, get_voice_provider(), payload)
