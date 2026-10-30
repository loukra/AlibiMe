"""User + primary-phone helpers."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
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


def delete_account(db: Session, user_id: uuid.UUID) -> None:
    """Delete the user and everything tied to them: phone numbers, sessions,
    requests with their call and message records, custom templates, sender
    bindings, credits, context profile.

    Pending requests go with it; a worker that later picks one up finds nothing
    and skips it. Only the free-allowance claim (a phone hash) stays, see
    ``FreeAllowanceClaim``.
    """
    from app.db.models.otp_verification import OtpVerification
    from app.db.models.request import Request
    from app.db.models.user_sender_binding import UserSenderBinding

    db.flush()  # write pending changes (e.g. session last-seen) before the rows go
    hashes = db.execute(
        select(PhoneNumber.phone_hash).where(PhoneNumber.user_id == user_id)
    ).scalars().all()
    # Requests and bindings first: they point at the user's phone numbers and
    # templates without a cascade of their own.
    db.execute(delete(Request).where(Request.user_id == user_id))
    db.execute(delete(UserSenderBinding).where(UserSenderBinding.user_id == user_id))
    if hashes:
        db.execute(delete(OtpVerification).where(OtpVerification.phone_hash.in_(hashes)))
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    db.expunge_all()
