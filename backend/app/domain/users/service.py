"""User + primary-phone helpers."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, PhoneNotVerified
from app.core.security import decrypt_phone, mask_phone
from app.db.models.enums import PhoneStatus
from app.db.models.phone import PhoneNumber
from app.db.models.user import User


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    return user


def get_primary_phone(db: Session, user_id: uuid.UUID) -> PhoneNumber | None:
    return db.execute(
        select(PhoneNumber).where(
            PhoneNumber.user_id == user_id,
            PhoneNumber.is_primary.is_(True),
            PhoneNumber.status == PhoneStatus.verified.value,
        )
    ).scalars().first()


def require_primary_phone(db: Session, user_id: uuid.UUID) -> PhoneNumber:
    phone = get_primary_phone(db, user_id)
    if phone is None:
        raise PhoneNotVerified()
    return phone


def masked_primary_number(db: Session, user_id: uuid.UUID) -> str | None:
    phone = get_primary_phone(db, user_id)
    if phone is None:
        return None
    return mask_phone(decrypt_phone(phone.phone_e164_encrypted))
