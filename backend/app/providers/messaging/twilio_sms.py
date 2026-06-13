from __future__ import annotations

from app.providers.messaging.base import MessageProvider
from app.providers.types import ProviderMessageResult, RequestPlan, WebhookParseResult

# Placeholder for the later manual Twilio Messaging integration.


class TwilioMessagingProvider(MessageProvider):
    name = "twilio_messaging"

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "TwilioMessagingProvider is a later manual integration. Use MESSAGE_PROVIDER=mock."
        )

    def send_sms(self, plan: RequestPlan) -> ProviderMessageResult:  # pragma: no cover
        raise NotImplementedError

    def parse_webhook(self, payload: dict) -> WebhookParseResult:  # pragma: no cover
        raise NotImplementedError
