import pytest

from app.core import rate_limit
from app.core.errors import RateLimited


def test_rate_limit_blocks_after_max(db):
    limit = rate_limit.Limit("test_limit", max_count=3, window=rate_limit.timedelta(hours=1))
    for _ in range(3):
        rate_limit.check_and_increment(db, limit, "subject-a")
    with pytest.raises(RateLimited):
        rate_limit.check_and_increment(db, limit, "subject-a")


def test_rate_limit_is_per_subject(db):
    limit = rate_limit.Limit("test_limit2", max_count=1, window=rate_limit.timedelta(hours=1))
    rate_limit.check_and_increment(db, limit, "subject-x")
    # Different subject has its own window/counter.
    rate_limit.check_and_increment(db, limit, "subject-y")
    with pytest.raises(RateLimited):
        rate_limit.check_and_increment(db, limit, "subject-x")
