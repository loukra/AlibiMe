"""Security primitives: phone encryption, deterministic hashing, session tokens.

Invariants:
- Phone numbers are encrypted at rest (Fernet).
- A deterministic HMAC hash enables uniqueness / rate-limit lookups without
  decryption.
- Session tokens are opaque random secrets; only their SHA-256 hash is stored.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


# --- Phone encryption ---

_fernet = Fernet(settings.fernet_key)


def encrypt_phone(phone_e164: str) -> str:
    return _fernet.encrypt(phone_e164.encode()).decode()


def decrypt_phone(token: str) -> str:
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("Could not decrypt phone number") from exc


def hash_phone(phone_e164: str) -> str:
    """Deterministic keyed hash for uniqueness and rate limiting."""
    return hmac.new(
        settings.app_secret_key.encode(), phone_e164.encode(), hashlib.sha256
    ).hexdigest()


def mask_phone(phone_e164: str) -> str:
    """Mask a normalized phone number, keeping country prefix + last 3 digits."""
    if not phone_e164:
        return ""
    keep_prefix = 3 if phone_e164.startswith("+") else 0
    head = phone_e164[:keep_prefix]
    tail = phone_e164[-3:] if len(phone_e164) > keep_prefix + 3 else ""
    masked_len = max(0, len(phone_e164) - keep_prefix - len(tail))
    return f"{head}{'*' * masked_len}{tail}"


# --- Session tokens ---

def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- Generic OTP code (used by mock provider) ---

def generate_numeric_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))
