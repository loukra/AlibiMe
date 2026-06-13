from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_fk, uuid_pk


class RequestArtifact(Base):
    """Minimal output. No transcripts/recordings stored by default."""

    __tablename__ = "request_artifacts"

    id: Mapped[uuid.UUID] = uuid_pk()
    request_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivered_message_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript_pointer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recording_pointer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retention_delete_after: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
