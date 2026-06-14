from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_fk, uuid_pk
from app.db.models.enums import SenderBindingStatus


class UserSenderBinding(Base):
    """Stable mapping of (user, sender persona, channel) -> a sender line.

    This is the core object that makes future messages from the same persona
    come from the same number. It is provider-agnostic: the bound sender line
    (``service_identities``) carries the Twilio/Vapi specifics, so a ``call``
    binding can later point at a voice-capable line under the same persona.
    """

    __tablename__ = "user_sender_bindings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "sender_persona_key", "channel", name="uq_user_persona_channel"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_persona_key: Mapped[str] = mapped_column(String(48), nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)
    sender_line_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("service_identities.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=SenderBindingStatus.active.value, nullable=False
    )
    first_bound_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    created_from_template_id: Mapped[uuid.UUID | None] = uuid_fk(
        ForeignKey("templates.id"), nullable=True
    )
