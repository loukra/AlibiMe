from __future__ import annotations

from app.providers.types import ProviderCallResult, RequestPlan, WebhookParseResult
from app.providers.voice.base import VoiceProvider

# Placeholder for the later manual Vapi integration (API key + assistant +
# webhook URL configured by a human). Implemented against VoiceProvider.


class VapiVoiceProvider(VoiceProvider):
    name = "vapi"

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "VapiVoiceProvider is a later manual integration. Use VOICE_PROVIDER=mock."
        )

    def create_outbound_call(self, plan: RequestPlan) -> ProviderCallResult:  # pragma: no cover
        raise NotImplementedError

    def cancel_call(self, provider_call_id: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def parse_webhook(self, payload: dict) -> WebhookParseResult:  # pragma: no cover
        raise NotImplementedError
