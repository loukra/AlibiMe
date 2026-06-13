"""Real OTP delivery via Twilio Verify.

https://www.twilio.com/docs/verify/api

Requires three settings (env vars), all from the Twilio console:

- ``TWILIO_ACCOUNT_SID``        — account SID (starts with "AC...")
- ``TWILIO_AUTH_TOKEN``         — account auth token
- ``TWILIO_VERIFY_SERVICE_SID`` — a Verify Service SID (starts with "VA...")

Implements the same ``OtpProvider`` interface as ``MockOtpProvider`` — see
that module for the expected behavior of each method.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.providers.otp.base import OtpProvider
from app.providers.types import (
    NumberLookup,
    OtpConfirmResult,
    OtpStartResult,
    ProviderRejected,
    TransientProviderError,
)

_VERIFY_BASE = "https://verify.twilio.com/v2"
_LOOKUP_BASE = "https://lookups.twilio.com/v2"

# Twilio Verify verifications expire 10 minutes after creation (fixed).
_VERIFICATION_TTL_SECONDS = 600

_LINE_TYPE_MAP = {
    "mobile": "mobile",
    "personal": "mobile",
    "landline": "landline",
    "tollFree": "landline",
    "premium": "landline",
    "sharedCost": "landline",
    "voip": "non_fixed_voip",
    "fixedVoip": "non_fixed_voip",
    "nonFixedVoip": "non_fixed_voip",
}


class TwilioVerifyProvider(OtpProvider):
    """OTP delivery via Twilio Verify (SMS)."""

    name = "twilio_verify"

    def __init__(self) -> None:
        if not (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_verify_service_sid
        ):
            raise RuntimeError(
                "TwilioVerifyProvider requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "and TWILIO_VERIFY_SERVICE_SID to be set."
            )
        self._auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        self._service_sid = settings.twilio_verify_service_sid

    def start_verification(self, phone_e164: str, locale: str) -> OtpStartResult:
        url = f"{_VERIFY_BASE}/Services/{self._service_sid}/Verifications"
        resp = self._post(url, {"To": phone_e164, "Channel": "sms", "Locale": locale})
        self._raise_for_status(resp)
        body = resp.json()
        return OtpStartResult(
            provider_verification_id=body["sid"],
            channel=body.get("channel", "sms"),
            expires_in_seconds=_VERIFICATION_TTL_SECONDS,
        )

    def confirm_verification(self, provider_verification_id: str, code: str) -> OtpConfirmResult:
        url = f"{_VERIFY_BASE}/Services/{self._service_sid}/VerificationCheck"
        resp = self._post(url, {"VerificationSid": provider_verification_id, "Code": code})
        if resp.status_code == 404:
            # Expired verification or max check-attempts exceeded on Twilio's
            # side — treat as an incorrect code, our own attempt/expiry checks
            # already happened before this call.
            return OtpConfirmResult(success=False)
        self._raise_for_status(resp)
        return OtpConfirmResult(success=(resp.json().get("status") == "approved"))

    def lookup_number(self, phone_e164: str) -> NumberLookup:
        url = f"{_LOOKUP_BASE}/PhoneNumbers/{phone_e164}"
        try:
            resp = httpx.get(
                url,
                auth=self._auth,
                params={"Fields": "line_type_intelligence"},
                timeout=10.0,
            )
        except httpx.TransportError:
            return NumberLookup(valid=True, line_type="unknown")

        if resp.status_code != 200:
            return NumberLookup(valid=False)

        body = resp.json()
        intel = body.get("line_type_intelligence") or {}
        line_type = _LINE_TYPE_MAP.get(intel.get("type"), "unknown")
        return NumberLookup(valid=True, line_type=line_type, country_code=body.get("country_code"))

    def _post(self, url: str, data: dict) -> httpx.Response:
        try:
            return httpx.post(url, auth=self._auth, data=data, timeout=10.0)
        except httpx.TransportError as exc:
            raise TransientProviderError(f"Twilio request failed: {exc}") from exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 500 or resp.status_code == 429:
            raise TransientProviderError(f"Twilio returned {resp.status_code}: {resp.text}")
        if resp.status_code >= 400:
            raise ProviderRejected(f"Twilio returned {resp.status_code}: {resp.text}")
