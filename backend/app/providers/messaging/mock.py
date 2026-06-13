from __future__ import annotations

import uuid

from app.db.models.enums import MessageAttemptStatus
from app.providers.messaging.base import MessageProvider
from app.providers.types import (
    ProviderMessageResult,
    ProviderRejected,
    RequestPlan,
    TransientProviderError,
    WebhookParseResult,
)

_EVENT_STATUS = {
    "message.queued": MessageAttemptStatus.queued.value,
    "message.sent": MessageAttemptStatus.sent.value,
    "message.delivered": MessageAttemptStatus.delivered.value,
    "message.failed": MessageAttemptStatus.failed_post_send.value,
}


class MockMessageProvider(MessageProvider):
    """Simulates one-way outbound SMS without any external account."""

    name = "mock_sms"

    def __init__(self, fail_pre_send_times: int = 0, reject: bool = False):
        self._fail_pre_send_times = fail_pre_send_times
        self._reject = reject

    def send_sms(self, plan: RequestPlan) -> ProviderMessageResult:
        behavior = plan.mock_behavior or {}
        if self._reject or behavior.get("reject"):
            raise ProviderRejected("Mock message provider rejected the message.")
        if self._fail_pre_send_times > 0:
            self._fail_pre_send_times -= 1
            raise TransientProviderError("Mock transient pre-send failure.")
        if behavior.get("fail_pre_send"):
            raise TransientProviderError("Mock transient pre-send failure.")
        return ProviderMessageResult(
            provider_message_id=f"mock-msg-{uuid.uuid4()}",
            status=MessageAttemptStatus.queued.value,
            accepted=True,
            estimated_cost_minor=1,
        )

    def cancel_sms(self, provider_message_id: str) -> bool:
        # SMS cannot be unsent once accepted; best-effort no-op.
        return False

    def parse_webhook(self, payload: dict) -> WebhookParseResult:
        event_type = payload.get("type")
        return WebhookParseResult(
            external_event_id=payload.get("event_id"),
            event_type=event_type,
            provider_ref_id=payload.get("provider_message_id"),
            mapped_status=_EVENT_STATUS.get(event_type or ""),
            fields={
                "failure_reason": payload.get("failure_reason"),
                "estimated_cost_minor": payload.get("estimated_cost_minor"),
            },
        )

    @staticmethod
    def simulate_lifecycle(provider_message_id: str, *, outcome: str = "delivered") -> list[dict]:
        base = f"mock-evt-{provider_message_id}"
        events = [
            {"event_id": f"{base}-1", "type": "message.queued", "provider_message_id": provider_message_id},
            {"event_id": f"{base}-2", "type": "message.sent", "provider_message_id": provider_message_id},
        ]
        if outcome == "delivered":
            events.append(
                {
                    "event_id": f"{base}-3",
                    "type": "message.delivered",
                    "provider_message_id": provider_message_id,
                    "estimated_cost_minor": 1,
                }
            )
        elif outcome == "failed":
            events.append(
                {
                    "event_id": f"{base}-3",
                    "type": "message.failed",
                    "provider_message_id": provider_message_id,
                    "failure_reason": "undelivered",
                }
            )
        return events
