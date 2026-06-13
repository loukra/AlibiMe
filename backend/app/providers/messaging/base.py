from __future__ import annotations

from abc import ABC, abstractmethod

from app.providers.types import ProviderMessageResult, RequestPlan, WebhookParseResult


class MessageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send_sms(self, plan: RequestPlan) -> ProviderMessageResult: ...

    def cancel_sms(self, provider_message_id: str) -> bool:  # best effort / optional
        return False

    @abstractmethod
    def parse_webhook(self, payload: dict) -> WebhookParseResult: ...

    def get_message_state(self, provider_message_id: str) -> str | None:  # optional
        return None
