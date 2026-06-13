from __future__ import annotations

import uuid

from app.db.models.enums import CallAttemptStatus
from app.providers.types import (
    ProviderCallResult,
    ProviderRejected,
    RequestPlan,
    TransientProviderError,
    WebhookParseResult,
)
from app.providers.voice.base import VoiceProvider

# Maps mock webhook event types to neutral CallAttempt statuses.
_EVENT_STATUS = {
    "call.queued": CallAttemptStatus.queued.value,
    "call.ringing": CallAttemptStatus.ringing.value,
    "call.answered": CallAttemptStatus.in_progress.value,
    "call.in_progress": CallAttemptStatus.in_progress.value,
    "call.completed": CallAttemptStatus.ended.value,
    "call.failed": CallAttemptStatus.failed_post_dial.value,
}


class MockVoiceCallProvider(VoiceProvider):
    """Simulates outbound calls and their lifecycle events.

    Behavior can be controlled per-instance (``fail_pre_dial_times`` / ``reject``)
    or per-request via ``plan.mock_behavior``:
      - ``{"fail_pre_dial": true}``  -> transient pre-dial failure (retryable)
      - ``{"reject": true}``         -> hard rejection (not retryable)
    """

    name = "mock_voice"

    def __init__(self, fail_pre_dial_times: int = 0, reject: bool = False):
        self._fail_pre_dial_times = fail_pre_dial_times
        self._reject = reject

    def create_outbound_call(self, plan: RequestPlan) -> ProviderCallResult:
        behavior = plan.mock_behavior or {}
        if self._reject or behavior.get("reject"):
            raise ProviderRejected("Mock voice provider rejected the call.")
        if self._fail_pre_dial_times > 0:
            self._fail_pre_dial_times -= 1
            raise TransientProviderError("Mock transient pre-dial failure.")
        if behavior.get("fail_pre_dial"):
            raise TransientProviderError("Mock transient pre-dial failure.")
        return ProviderCallResult(
            provider_call_id=f"mock-call-{uuid.uuid4()}",
            status=CallAttemptStatus.queued.value,
            accepted=True,
            estimated_cost_minor=2,
        )

    def cancel_call(self, provider_call_id: str) -> bool:
        return True

    def parse_webhook(self, payload: dict) -> WebhookParseResult:
        event_type = payload.get("type")
        return WebhookParseResult(
            external_event_id=payload.get("event_id"),
            event_type=event_type,
            provider_ref_id=payload.get("provider_call_id"),
            mapped_status=_EVENT_STATUS.get(event_type or ""),
            fields={
                "duration_seconds": payload.get("duration_seconds"),
                "ended_reason": payload.get("ended_reason"),
                "estimated_cost_minor": payload.get("estimated_cost_minor"),
            },
        )

    # --- Helpers for local/dev/test lifecycle simulation ---

    @staticmethod
    def simulate_lifecycle(
        provider_call_id: str,
        *,
        outcome: str = "completed",
        duration_seconds: int = 25,
    ) -> list[dict]:
        """Return an ordered list of webhook payloads driving a call to terminal."""
        base = f"mock-evt-{provider_call_id}"
        events = [
            {"event_id": f"{base}-1", "type": "call.queued", "provider_call_id": provider_call_id},
            {"event_id": f"{base}-2", "type": "call.ringing", "provider_call_id": provider_call_id},
        ]
        if outcome == "completed":
            events += [
                {"event_id": f"{base}-3", "type": "call.answered", "provider_call_id": provider_call_id},
                {
                    "event_id": f"{base}-4",
                    "type": "call.completed",
                    "provider_call_id": provider_call_id,
                    "duration_seconds": duration_seconds,
                    "ended_reason": "completed",
                    "estimated_cost_minor": 4,
                },
            ]
        elif outcome == "no_answer":
            events += [
                {
                    "event_id": f"{base}-3",
                    "type": "call.failed",
                    "provider_call_id": provider_call_id,
                    "ended_reason": "no_answer",
                }
            ]
        return events
