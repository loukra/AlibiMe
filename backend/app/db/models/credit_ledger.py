from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_fk, uuid_pk


class CreditLedger(Base):
    """Immutable credit movements. Balance is derived, never mutated in place."""

    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    amount_units: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
