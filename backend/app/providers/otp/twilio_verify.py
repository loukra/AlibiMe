from __future__ import annotations

from app.providers.otp.base import OtpProvider
from app.providers.types import OtpConfirmResult, OtpStartResult

# Placeholder for the later manual Twilio Verify integration. Requires account
# creation, a Verify Service SID, and dashboard setup — out of scope for the
# first coding pass. Implemented against the same OtpProvider interface.


class TwilioVerifyProvider(OtpProvider):
    name = "twilio_verify"

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "TwilioVerifyProvider is a later manual integration. Use OTP_PROVIDER=mock."
        )

    def start_verification(self, phone_e164: str, locale: str) -> OtpStartResult:  # pragma: no cover
        raise NotImplementedError

    def confirm_verification(self, provider_verification_id: str, code: str) -> OtpConfirmResult:  # pragma: no cover
        raise NotImplementedError
