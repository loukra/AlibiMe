"""Sign-in for Apple's App Review, which can't receive our SMS codes.

Wraps the real OTP provider. For the configured review number no code is
sent and no carrier lookup is paid for; the fixed code confirms it. Every
other number goes to the real provider unchanged.
"""
from __future__ import annotations

import hmac
import uuid

from app.providers.otp.base import OtpProvider
from app.providers.types import NumberLookup, OtpConfirmResult, OtpStartResult

_ID_PREFIX = "review-"


class ReviewOtpProvider(OtpProvider):
    def __init__(self, inner: OtpProvider, phone_e164: str, code: str):
        self.inner = inner
        self.name = inner.name
        self.phone_e164 = phone_e164
        self.code = code

    def start_verification(self, phone_e164: str, locale: str) -> OtpStartResult:
        if phone_e164 != self.phone_e164:
            return self.inner.start_verification(phone_e164, locale)
        return OtpStartResult(
            provider_verification_id=f"{_ID_PREFIX}{uuid.uuid4()}",
            channel="sms",
            expires_in_seconds=600,
        )

    def confirm_verification(self, provider_verification_id: str, code: str) -> OtpConfirmResult:
        if not provider_verification_id.startswith(_ID_PREFIX):
            return self.inner.confirm_verification(provider_verification_id, code)
        return OtpConfirmResult(success=hmac.compare_digest(code.encode(), self.code.encode()))

    def lookup_number(self, phone_e164: str) -> NumberLookup:
        if phone_e164 == self.phone_e164:
            return NumberLookup(valid=True, line_type="unknown")
        return self.inner.lookup_number(phone_e164)
