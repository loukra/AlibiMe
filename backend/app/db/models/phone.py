from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_fk, uuid_pk
from app.core.clock import utcnow
from app.db.models.enums import LineType, PhoneStatus


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_e164_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    line_type: Mapped[str] = mapped_column(String(20), default=LineType.unknown.value, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=PhoneStatus.pending.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="phone_numbers")  # noqa: F821


# At most one primary number per user (enforced for the rows that are primary).
Index(
    "uq_one_primary_per_user",
    PhoneNumber.user_id,
    unique=True,
    sqlite_where=PhoneNumber.is_primary.is_(True),
    postgresql_where=PhoneNumber.is_primary.is_(True),
)
