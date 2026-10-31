from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.db.models.enums import UserStatus


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    status: Mapped[str] = mapped_column(String(16), default=UserStatus.active.value, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    # Only ever an entry of app/domain/users/first_names.txt, never typed text.
    first_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
