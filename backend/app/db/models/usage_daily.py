from __future__ import annotations

import uuid

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_fk, uuid_pk


class UsageDaily(Base):
    __tablename__ = "usage_daily"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_usage_user_date"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    requests_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sms_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_call_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
