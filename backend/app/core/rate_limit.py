"""Postgres-backed (and SQLite-compatible) fixed-window rate limiting.

First coding pass uses a simple counter table with a window key. Redis can be
introduced later if concurrency pressure appears. Limits are enforced with a
SELECT ... FOR UPDATE on the counter row (a no-op lock hint on SQLite, which
serializes writes anyway).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import RateLimited
from app.db.models.rate_limit import RateLimitCounter


@dataclass(frozen=True)
class Limit:
    name: str
    max_count: int
    window: timedelta


# MVP limits (see spec "Rate limits").
OTP_START = Limit("otp_start", 5, timedelta(hours=1))            # per phone hash
OTP_CONFIRM = Limit("otp_confirm", 10, timedelta(hours=1))       # per verification id
REQUEST_CREATE = Limit("request_create", 5, timedelta(hours=1))  # per user
SESSION_CREATE = Limit("session_create", 10, timedelta(hours=1)) # per device/phone


def _window_start(window: timedelta, now=None):
    now = now or utcnow()
    seconds = int(window.total_seconds())
    epoch = int(now.timestamp())
    bucket = epoch - (epoch % seconds)
    return bucket


def check_and_increment(db: Session, limit: Limit, subject: str) -> None:
    """Increment the counter for (limit, subject) in the current window.

    Raises RateLimited if the limit is exceeded.
    """
    window_start = _window_start(limit.window)
    key = f"{limit.name}:{subject}"

    row = db.execute(
        select(RateLimitCounter)
        .where(
            RateLimitCounter.key == key,
            RateLimitCounter.window_start == window_start,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if row is None:
        row = RateLimitCounter(key=key, window_start=window_start, count=0)
        db.add(row)
        db.flush()

    if row.count >= limit.max_count:
        raise RateLimited(
            f"Rate limit exceeded for {limit.name}. Try again later."
        )

    row.count += 1
    db.flush()
