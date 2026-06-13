from __future__ import annotations

import uuid

import phonenumbers

from app.providers.otp.base import OtpProvider
from app.providers.types import NumberLookup, OtpConfirmResult, OtpStartResult

# Deterministic mock code so local/dev/tests don't need to scrape logs.
MOCK_OTP_CODE = "123456"
# A code that always fails, to exercise the wrong-code path.
MOCK_OTP_BAD_CODE = "000000"


class MockOtpProvider(OtpProvider):
    """Simulates OTP verification without any external account.

    - The correct code is always ``123456``.
    - ``000000`` (and any other value) is rejected.
    - ``lookup_number`` derives a plausible line type from the number.
    """

    name = "mock"

    def start_verification(self, phone_e164: str, locale: str) -> OtpStartResult:
        return OtpStartResult(
            provider_verification_id=f"mock-otp-{uuid.uuid4()}",
            channel="sms",
            expires_in_seconds=600,
            debug_code=MOCK_OTP_CODE,
        )

    def confirm_verification(self, provider_verification_id: str, code: str) -> OtpConfirmResult:
        return OtpConfirmResult(success=(code == MOCK_OTP_CODE))

    def lookup_number(self, phone_e164: str) -> NumberLookup:
        try:
            parsed = phonenumbers.parse(phone_e164, None)
        except phonenumbers.NumberParseException:
            return NumberLookup(valid=False)
        if not phonenumbers.is_valid_number(parsed):
            return NumberLookup(valid=False)
        region = phonenumbers.region_code_for_number(parsed)
        ntype = phonenumbers.number_type(parsed)
        line_type = "mobile"
        if ntype == phonenumbers.PhoneNumberType.FIXED_LINE:
            line_type = "landline"
        elif ntype == phonenumbers.PhoneNumberType.VOIP:
            line_type = "non_fixed_voip"
        return NumberLookup(valid=True, line_type=line_type, country_code=region)
