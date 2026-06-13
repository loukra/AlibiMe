"""Declarative base + portable column helpers.

Models are written to work on both PostgreSQL (production target) and SQLite
(used for the local test suite). We therefore use SQLAlchemy's dialect-neutral
``Uuid`` and ``JSON`` types instead of Postgres-only ones.

All ``datetime`` columns are timezone-aware UTC, enforced by ``UTCDateTime``
(SQLite does not persist tzinfo, so we re-attach UTC on read). This is wired up
globally via ``type_annotation_map`` so every ``Mapped[datetime]`` uses it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.clock import utcnow


class UTCDateTime(TypeDecorator):
    """Always store/return timezone-aware UTC datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime}


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def uuid_fk(*args, **kwargs) -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, *args, **kwargs)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)
