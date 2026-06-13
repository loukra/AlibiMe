from __future__ import annotations

from abc import ABC, abstractmethod

from app.providers.types import ProviderCallResult, RequestPlan, WebhookParseResult


class VoiceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_outbound_call(self, plan: RequestPlan) -> ProviderCallResult: ...

    @abstractmethod
    def cancel_call(self, provider_call_id: str) -> bool: ...

    @abstractmethod
    def parse_webhook(self, payload: dict) -> WebhookParseResult: ...

    def get_call_state(self, provider_call_id: str) -> str | None:  # optional
        return None
