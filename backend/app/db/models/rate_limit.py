from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        UniqueConstraint("key", "window_start", name="uq_ratelimit_key_window"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    window_start: Mapped[int] = mapped_column(BigInteger, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
