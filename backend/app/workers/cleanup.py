"""Retention cleanup: limit raw webhook payloads and expired artifacts."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.db.models.artifact import RequestArtifact
from app.db.models.webhook_event import WebhookEvent

WEBHOOK_RETENTION = timedelta(days=30)


def cleanup(db: Session, now=None) -> dict:
    now = now or utcnow()

    old_webhooks = db.execute(
        delete(WebhookEvent).where(WebhookEvent.received_at < now - WEBHOOK_RETENTION)
    )

    expired_artifacts = db.execute(
        select(RequestArtifact).where(
            RequestArtifact.retention_delete_after.is_not(None),
            RequestArtifact.retention_delete_after < now,
        )
    ).scalars().all()
    for art in expired_artifacts:
        db.delete(art)

    db.commit()
    return {
        "webhooks_deleted": old_webhooks.rowcount or 0,
        "artifacts_deleted": len(expired_artifacts),
    }
