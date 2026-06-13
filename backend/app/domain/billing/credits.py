"""Ledger-based credit accounting.

Balance is the running sum of signed ``amount_units`` — never a mutable field.

Entry semantics:
  grant            +N    increases available balance
  reserve          -cost holds credits at dispatch time (reduces available)
  release          +cost returns a reservation (pre-acceptance failure)
  capture           0    finalizes a reservation on provider acceptance
  refund           +cost post-hoc refund
  admin_adjustment  ±N   manual correction
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import InsufficientCredits
from app.db.models.credit_ledger import CreditLedger
from app.db.models.enums import CreditEntryType, CreditReferenceType


def current_balance(db: Session, user_id: uuid.UUID) -> int:
    total = db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount_units), 0)).where(
            CreditLedger.user_id == user_id
        )
    ).scalar_one()
    return int(total or 0)


def _append(
    db: Session,
    user_id: uuid.UUID,
    entry_type: CreditEntryType,
    amount: int,
    *,
    reference_type: CreditReferenceType | None = None,
    reference_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> CreditLedger:
    balance_after = current_balance(db, user_id) + amount
    entry = CreditLedger(
        user_id=user_id,
        entry_type=entry_type.value,
        amount_units=amount,
        balance_after_units=balance_after,
        reference_type=reference_type.value if reference_type else None,
        reference_id=reference_id,
        notes=notes,
    )
    db.add(entry)
    db.flush()
    return entry


def grant(
    db: Session,
    user_id: uuid.UUID,
    amount: int,
    *,
    reference_type: CreditReferenceType = CreditReferenceType.manual,
    reference_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> CreditLedger:
    if amount <= 0:
        raise ValueError("grant amount must be positive")
    return _append(
        db, user_id, CreditEntryType.grant, amount,
        reference_type=reference_type, reference_id=reference_id, notes=notes,
    )


def reserve(db: Session, user_id: uuid.UUID, amount: int, request_id: uuid.UUID) -> CreditLedger:
    if amount <= 0:
        raise ValueError("reserve amount must be positive")
    if current_balance(db, user_id) < amount:
        raise InsufficientCredits()
    return _append(
        db, user_id, CreditEntryType.reserve, -amount,
        reference_type=CreditReferenceType.request, reference_id=request_id,
        notes="reserve at dispatch",
    )


def capture(db: Session, user_id: uuid.UUID, request_id: uuid.UUID) -> CreditLedger:
    return _append(
        db, user_id, CreditEntryType.capture, 0,
        reference_type=CreditReferenceType.request, reference_id=request_id,
        notes="capture on provider acceptance",
    )


def release(db: Session, user_id: uuid.UUID, amount: int, request_id: uuid.UUID) -> CreditLedger:
    if amount <= 0:
        raise ValueError("release amount must be positive")
    return _append(
        db, user_id, CreditEntryType.release, amount,
        reference_type=CreditReferenceType.request, reference_id=request_id,
        notes="release on pre-acceptance failure",
    )


def has_credits(db: Session, user_id: uuid.UUID, amount: int) -> bool:
    return current_balance(db, user_id) >= amount
