from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.requests.webhook_ingest import ingest_voice_webhook
from app.providers.factory import get_voice_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/voice")
async def voice_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    # Signature verification happens here once a real provider is configured.
    payload = await request.json()
    return ingest_voice_webhook(db, get_voice_provider(), payload)
