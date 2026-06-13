import uuid

import pytest

from app.core.errors import InsufficientCredits
from app.db.models.user import User
from app.domain.billing import credits


def _user(db) -> User:
    u = User(locale="en")
    db.add(u)
    db.commit()
    return u


def test_balance_starts_at_zero(db):
    u = _user(db)
    assert credits.current_balance(db, u.id) == 0


def test_grant_increases_balance(db):
    u = _user(db)
    credits.grant(db, u.id, 5)
    db.commit()
    assert credits.current_balance(db, u.id) == 5


def test_reserve_then_capture_holds_credit(db):
    u = _user(db)
    credits.grant(db, u.id, 5)
    rid = uuid.uuid4()
    credits.reserve(db, u.id, 2, rid)
    assert credits.current_balance(db, u.id) == 3
    credits.capture(db, u.id, rid)
    # capture is a 0-amount finalization; balance unchanged.
    assert credits.current_balance(db, u.id) == 3


def test_reserve_then_release_restores_credit(db):
    u = _user(db)
    credits.grant(db, u.id, 5)
    rid = uuid.uuid4()
    credits.reserve(db, u.id, 2, rid)
    credits.release(db, u.id, 2, rid)
    assert credits.current_balance(db, u.id) == 5


def test_reserve_without_balance_raises(db):
    u = _user(db)
    with pytest.raises(InsufficientCredits):
        credits.reserve(db, u.id, 1, uuid.uuid4())


def test_has_credits(db):
    u = _user(db)
    credits.grant(db, u.id, 2)
    db.commit()
    assert credits.has_credits(db, u.id, 2)
    assert not credits.has_credits(db, u.id, 3)
