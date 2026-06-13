"""Passwordless OTP auth: start, confirm, session lifecycle, number change."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.clock import utcnow
from app.core.config import settings
from app.core.errors import (
    InvalidPhoneNumber,
    ProviderUnavailable,
    SessionExpired,
    Unauthorized,
    ValidationFailed,
)
from app.core.security import (
    decrypt_phone,
    encrypt_phone,
    generate_session_token,
    hash_phone,
    hash_session_token,
    mask_phone,
)
from app.db.models.enums import PhoneStatus
from app.db.models.otp_verification import OtpVerification
from app.db.models.phone import PhoneNumber
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.domain.billing.entitlements import grant_free_test_allowance
from app.domain.phone import assert_supported_line_type, normalize_phone
from app.providers.otp.base import OtpProvider
from app.providers.types import ProviderRejected, TransientProviderError

_MAX_CONFIRM_ATTEMPTS = 6


def start_phone_verification(
    db: Session,
    provider: OtpProvider,
    *,
    raw_phone: str,
    device_id: str | None,
    locale: str,
) -> dict:
    normalized = normalize_phone(raw_phone)
    assert_supported_line_type(normalized.line_type)

    phone_hash = hash_phone(normalized.e164)
    rate_limit.check_and_increment(db, rate_limit.OTP_START, phone_hash)

    try:
        start = provider.start_verification(normalized.e164, locale)
    except TransientProviderError as exc:
        raise ProviderUnavailable(str(exc)) from exc
    except ProviderRejected as exc:
        raise InvalidPhoneNumber(str(exc)) from exc

    verification = OtpVerification(
        provider=provider.name,
        provider_verification_id=start.provider_verification_id,
        phone_hash=phone_hash,
        phone_e164_encrypted=encrypt_phone(normalized.e164),
        country_code=normalized.country_code,
        line_type=normalized.line_type,
        locale=locale,
        channel=start.channel,
        status="pending",
        expires_at=utcnow() + timedelta(seconds=start.expires_in_seconds),
    )
    db.add(verification)
    db.flush()
    db.commit()

    return {
        "verification_id": str(verification.id),
        "channel": start.channel,
        "expires_in_seconds": start.expires_in_seconds,
    }


def _issue_session(db: Session, user_id: uuid.UUID, device_id: str | None) -> str:
    # Rotate: revoke existing active sessions for the same device.
    if device_id:
        existing = db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.device_id == device_id,
                UserSession.revoked_at.is_(None),
            )
        ).scalars().all()
        for s in existing:
            s.revoked_at = utcnow()

    token = generate_session_token()
    session = UserSession(
        user_id=user_id,
        token_hash=hash_session_token(token),
        device_id=device_id,
        expires_at=utcnow() + timedelta(days=settings.session_token_ttl_days),
        last_used_at=utcnow(),
    )
    db.add(session)
    db.flush()
    return token


def _set_primary_phone(
    db: Session, user_id: uuid.UUID, *, e164: str, country_code: str | None, line_type: str
) -> PhoneNumber:
    phone_hash = hash_phone(e164)
    # Reuse an existing verified phone row for this user+hash if present.
    existing = db.execute(
        select(PhoneNumber).where(
            PhoneNumber.user_id == user_id,
            PhoneNumber.phone_hash == phone_hash,
        )
    ).scalars().first()
    if existing:
        existing.status = PhoneStatus.verified.value
        existing.is_primary = True
        existing.verified_at = utcnow()
        db.flush()
        return existing

    # Demote any other primary numbers for this user (number-change flow).
    others = db.execute(
        select(PhoneNumber).where(
            PhoneNumber.user_id == user_id,
            PhoneNumber.is_primary.is_(True),
        )
    ).scalars().all()
    for o in others:
        o.is_primary = False
        o.status = PhoneStatus.replaced.value

    phone = PhoneNumber(
        user_id=user_id,
        phone_e164_encrypted=encrypt_phone(e164),
        phone_hash=phone_hash,
        country_code=country_code,
        line_type=line_type,
        verified_at=utcnow(),
        is_primary=True,
        status=PhoneStatus.verified.value,
    )
    db.add(phone)
    db.flush()
    return phone


def confirm_phone_verification(
    db: Session,
    provider: OtpProvider,
    *,
    verification_id: str,
    code: str,
    device_id: str | None,
) -> dict:
    try:
        vid = uuid.UUID(str(verification_id))
    except (ValueError, TypeError):
        raise ValidationFailed("Invalid verification id.")

    rate_limit.check_and_increment(db, rate_limit.OTP_CONFIRM, str(vid))

    verification = db.get(OtpVerification, vid)
    if verification is None:
        raise ValidationFailed("Verification not found.")
    if verification.status == "confirmed":
        raise ValidationFailed("This verification was already used.")
    if verification.expires_at < utcnow():
        verification.status = "expired"
        db.commit()
        raise ValidationFailed("This verification has expired.")
    if verification.attempts >= _MAX_CONFIRM_ATTEMPTS:
        raise ValidationFailed("Too many attempts for this verification.")

    try:
        result = provider.confirm_verification(verification.provider_verification_id, code)
    except TransientProviderError as exc:
        raise ProviderUnavailable(str(exc)) from exc
    except ProviderRejected as exc:
        verification.attempts += 1
        db.commit()
        raise ValidationFailed("The verification code is incorrect.") from exc

    verification.attempts += 1
    if not result.success:
        db.commit()
        raise ValidationFailed("The verification code is incorrect.")

    e164 = decrypt_phone(verification.phone_e164_encrypted)

    # Find an existing user by a phone with the same hash.
    existing_phone = db.execute(
        select(PhoneNumber).where(PhoneNumber.phone_hash == verification.phone_hash)
    ).scalars().first()

    is_new_user = existing_phone is None
    if existing_phone:
        user = db.get(User, existing_phone.user_id)
    else:
        user = User(locale=verification.locale)
        db.add(user)
        db.flush()

    user.last_login_at = utcnow()
    _set_primary_phone(
        db, user.id, e164=e164, country_code=verification.country_code,
        line_type=verification.line_type,
    )

    if is_new_user:
        grant_free_test_allowance(db, user.id)

    verification.status = "confirmed"
    verification.confirmed_at = utcnow()

    token = _issue_session(db, user.id, device_id)
    db.commit()

    return {
        "session_token": token,
        "user": {
            "id": str(user.id),
            "locale": user.locale,
            "phone_number_masked": mask_phone(e164),
        },
    }


def resolve_session(db: Session, token: str) -> tuple[User, UserSession]:
    if not token:
        raise Unauthorized()
    token_hash = hash_session_token(token)
    session = db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    ).scalars().first()
    if session is None or session.revoked_at is not None:
        raise Unauthorized()
    if session.expires_at < utcnow():
        raise SessionExpired()
    user = db.get(User, session.user_id)
    if user is None or user.status != "active":
        raise Unauthorized()
    session.last_used_at = utcnow()
    return user, session


def logout(db: Session, session: UserSession) -> None:
    session.revoked_at = utcnow()
    db.commit()
