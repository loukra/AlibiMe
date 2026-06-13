"""Single source of 'now' so tests can reason about time consistently."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
