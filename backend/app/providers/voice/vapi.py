"""Real outbound voice calls via Vapi.

https://docs.vapi.ai/api-reference/calls/create

Requires (env vars, from the Vapi dashboard):

- ``VAPI_API_KEY``          — private API key (Authorization: Bearer)
- ``VAPI_ASSISTANT_ID``     — the Assistant to run (voice + system prompt live there)
- ``VAPI_PHONE_NUMBER_ID``  — the Vapi-managed number to call *from*

Optional:
- ``VAPI_WEBHOOK_SECRET``   — the Server URL secret; Vapi echoes it on webhooks
  as the ``X-Vapi-Secret`` header so we can authenticate them.

Template content is passed as assistant overrides (opening line + variables);
the bounded behavior still lives in the configured Assistant. Implements the
same ``VoiceProvider`` interface as ``MockVoiceCallProvider``.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.db.models.enums import CallAttemptStatus
from app.providers.types import (
    ProviderCallResult,
    ProviderRejected,
    RequestPlan,
    TransientProviderError,
    WebhookParseResult,
)
from app.providers.voice.base import VoiceProvider

_API_BASE = "https://api.vapi.ai"

# Vapi call status -> our neutral CallAttemptStatus.
_STATUS_MAP = {
    "queued": CallAttemptStatus.queued.value,
    "scheduled": CallAttemptStatus.queued.value,
    "ringing": CallAttemptStatus.ringing.value,
    "in-progress": CallAttemptStatus.in_progress.value,
    "forwarding": CallAttemptStatus.in_progress.value,
    "ended": CallAttemptStatus.ended.value,
}


class VapiVoiceProvider(VoiceProvider):
    """Outbound voice via Vapi."""

    name = "vapi"

    def __init__(self) -> None:
        if not settings.vapi_api_key:
            raise RuntimeError("VapiVoiceProvider requires VAPI_API_KEY.")
        if not (settings.vapi_assistant_id and settings.vapi_phone_number_id):
            raise RuntimeError(
                "VapiVoiceProvider requires VAPI_ASSISTANT_ID and VAPI_PHONE_NUMBER_ID."
            )
        self._headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}
        self._assistant_id = settings.vapi_assistant_id
        self._phone_number_id = settings.vapi_phone_number_id

    def create_outbound_call(self, plan: RequestPlan) -> ProviderCallResult:
        if not plan.target_phone_e164:
            raise ProviderRejected("No destination number resolved for call dispatch.")

        body: dict = {
            "phoneNumberId": self._phone_number_id,
            "assistantId": self._assistant_id,
            "customer": {"number": plan.target_phone_e164},
        }
        overrides: dict = {}
        if plan.rendered_opening_line:
            overrides["firstMessage"] = plan.rendered_opening_line
        if plan.max_duration_seconds:
            overrides["maxDurationSeconds"] = plan.max_duration_seconds
        # The template-parameter + context variable set is the single source of
        # truth for the call; the assistant's dashboard prompt references these
        # via {{...}}. (Built in build_call_variables / threaded via RequestPlan.)
        if plan.call_variables:
            overrides["variableValues"] = dict(plan.call_variables)
        if overrides:
            body["assistantOverrides"] = overrides

        resp = self._post(f"{_API_BASE}/call", body)
        self._raise_for_status(resp)
        data = resp.json()
        # Vapi may return a single call object or a list (batched); take the first.
        if isinstance(data, list):
            data = data[0] if data else {}
        status = _STATUS_MAP.get(data.get("status", ""), CallAttemptStatus.queued.value)
        return ProviderCallResult(
            provider_call_id=data["id"],
            status=status,
            accepted=True,
            estimated_cost_minor=_cost_to_minor(data.get("cost")),
            raw=data,
        )

    def cancel_call(self, provider_call_id: str) -> bool:
        # Best effort: end/delete the call. Only effective while not yet ended.
        try:
            resp = httpx.delete(
                f"{_API_BASE}/call/{provider_call_id}", headers=self._headers, timeout=10.0
            )
        except httpx.TransportError:
            return False
        return resp.status_code < 400

    def parse_webhook(self, payload: dict) -> WebhookParseResult:
        # Vapi wraps events as {"message": {...}}.
        msg = payload.get("message", payload) or {}
        event_type = msg.get("type")
        call = msg.get("call") or {}
        call_id = call.get("id") or msg.get("callId") or payload.get("callId")

        # end-of-call-report implies ended; status-update carries an explicit status.
        if event_type == "end-of-call-report":
            vapi_status = "ended"
        else:
            vapi_status = msg.get("status") or call.get("status")

        external_event_id = (
            f"{call_id}:{event_type or vapi_status}" if call_id else None
        )
        return WebhookParseResult(
            external_event_id=external_event_id,
            event_type=vapi_status or event_type,
            provider_ref_id=call_id,
            mapped_status=_STATUS_MAP.get(vapi_status or ""),
            fields={
                "ended_reason": msg.get("endedReason"),
                "duration_seconds": _duration_seconds(msg),
                "estimated_cost_minor": _cost_to_minor(msg.get("cost")),
            },
        )

    def _post(self, url: str, json_body: dict) -> httpx.Response:
        try:
            return httpx.post(url, headers=self._headers, json=json_body, timeout=15.0)
        except httpx.TransportError as exc:
            raise TransientProviderError(f"Vapi request failed: {exc}") from exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 500 or resp.status_code == 429:
            raise TransientProviderError(f"Vapi returned {resp.status_code}: {resp.text}")
        if resp.status_code >= 400:
            raise ProviderRejected(f"Vapi returned {resp.status_code}: {resp.text}")


def _cost_to_minor(cost) -> int | None:
    """Vapi reports cost as a number in USD (e.g. 0.043) or null."""
    if cost is None:
        return None
    try:
        return int(round(abs(float(cost)) * 100))
    except (TypeError, ValueError):
        return None


def _duration_seconds(msg: dict) -> int | None:
    if msg.get("durationSeconds") is not None:
        try:
            return int(round(float(msg["durationSeconds"])))
        except (TypeError, ValueError):
            return None
    if msg.get("durationMs") is not None:
        try:
            return int(round(float(msg["durationMs"]) / 1000.0))
        except (TypeError, ValueError):
            return None
    return None
