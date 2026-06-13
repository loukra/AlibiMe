from __future__ import annotations

from abc import ABC, abstractmethod

from app.providers.types import NumberLookup, OtpConfirmResult, OtpStartResult


class OtpProvider(ABC):
    name: str = "base"

    @abstractmethod
    def start_verification(self, phone_e164: str, locale: str) -> OtpStartResult: ...

    @abstractmethod
    def confirm_verification(self, provider_verification_id: str, code: str) -> OtpConfirmResult: ...

    def lookup_number(self, phone_e164: str) -> NumberLookup:  # optional
        return NumberLookup(valid=True, line_type="unknown")
