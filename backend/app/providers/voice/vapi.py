"""Real outbound voice calls via Vapi.

https://docs.vapi.ai/api-reference/calls/create

Vapi only carries the call. The agent itself — system prompt, model, voice,
transcriber and call behaviour — is defined in ``app.agent`` and sent as a
transient assistant with every call, so nothing about how a call sounds lives
in the Vapi dashboard. ``build_assistant`` and ``caller_line`` are the only
places that know Vapi's field names.

Requires:
- ``VAPI_API_KEY``          — private API key (Authorization: Bearer)

The call is placed from the persona's sender line, so a saved contact
("Mom") shows for calls as well as texts. In order of preference:
- the line's own ``vapi_phone_number_id`` (number imported into Vapi), or
- the line's Twilio number, passed inline with ``TWILIO_ACCOUNT_SID`` /
  ``TWILIO_AUTH_TOKEN``, or
- ``VAPI_PHONE_NUMBER_ID`` as a shared fallback.

Optional:
- ``PUBLIC_BASE_URL``       — Vapi posts call events to <base>/v1/webhooks/voice
- ``VAPI_WEBHOOK_SECRET``   — sent back by Vapi as ``X-Vapi-Secret`` on webhooks

Implements the same ``VoiceProvider`` interface as ``MockVoiceCallProvider``.
"""
from __future__ import annotations

import httpx

from app.agent.config import AgentConfig, agent_config
from app.agent.prompt import build_system_prompt
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

# The webhook events ``parse_webhook`` acts on.
SERVER_MESSAGES = ("status-update", "end-of-call-report")

# Vapi call status -> our neutral CallAttemptStatus.
_STATUS_MAP = {
    "queued": CallAttemptStatus.queued.value,
    "scheduled": CallAttemptStatus.queued.value,
    "ringing": CallAttemptStatus.ringing.value,
    "in-progress": CallAttemptStatus.in_progress.value,
    "forwarding": CallAttemptStatus.in_progress.value,
    "ended": CallAttemptStatus.ended.value,
}


def build_assistant(plan: RequestPlan, config: AgentConfig) -> dict:
    """The transient assistant for one call, in Vapi's schema."""
    system_prompt = plan.call_system_prompt or build_system_prompt(plan.call_variables)
    model: dict = {
        "provider": config.model.provider,
        "model": config.model.model,
        "temperature": config.model.temperature,
        "maxTokens": config.model.max_tokens,
        "messages": [{"role": "system", "content": system_prompt}],
        # Lets the agent hang up once it has what it wanted.
        "tools": [{"type": "endCall"}],
    }
    voice: dict = {"provider": config.voice.provider, "voiceId": config.voice.voice_id}
    if config.voice.model:
        voice["model"] = config.voice.model
    assistant: dict = {
        "firstMessage": plan.rendered_opening_line or "",
        "firstMessageMode": "assistant-speaks-first",
        "model": model,
        "voice": voice,
        "transcriber": {
            "provider": config.transcriber.provider,
            "model": config.transcriber.model,
            "language": config.transcriber.language,
        },
        "backgroundSound": config.background_sound,
        "silenceTimeoutSeconds": config.silence_timeout_seconds,
        "metadata": {"request_id": plan.request_id, "template": plan.template_code},
        # Nothing about the call stays at Vapi: no recording, packet capture,
        # call log, stored transcript or summary. The live transcriber above
        # still lets the agent hear the user. Recording, logging and packet
        # capture are on unless switched off.
        "artifactPlan": {
            "recordingEnabled": False,
            "pcapEnabled": False,
            "loggingEnabled": False,
            "transcriptPlan": {"enabled": False},
        },
        "analysisPlan": {"summaryPrompt": "", "successEvaluationPrompt": ""},
        # Only the events the backend reads, not the running conversation.
        "serverMessages": list(SERVER_MESSAGES),
    }
    if plan.max_duration_seconds:
        assistant["maxDurationSeconds"] = plan.max_duration_seconds
    if settings.public_base_url:
        server: dict = {"url": settings.public_base_url.rstrip("/") + "/v1/webhooks/voice"}
        if settings.vapi_webhook_secret:
            server["headers"] = {"X-Vapi-Secret": settings.vapi_webhook_secret}
        assistant["server"] = server
    return assistant


def caller_line(plan: RequestPlan) -> dict:
    """Which number the call comes from, as Vapi call-body fields."""
    if plan.sender_vapi_phone_number_id:
        return {"phoneNumberId": plan.sender_vapi_phone_number_id}
    if plan.service_identity_value and settings.twilio_account_sid and settings.twilio_auth_token:
        return {
            "phoneNumber": {
                "twilioPhoneNumber": plan.service_identity_value,
                "twilioAccountSid": settings.twilio_account_sid,
                "twilioAuthToken": settings.twilio_auth_token,
            }
        }
    if settings.vapi_phone_number_id:
        return {"phoneNumberId": settings.vapi_phone_number_id}
    raise ProviderRejected("No caller number: sender line has no Vapi/Twilio number configured.")


class VapiVoiceProvider(VoiceProvider):
    """Outbound voice via Vapi."""

    name = "vapi"

    def __init__(self) -> None:
        if not settings.vapi_api_key:
            raise RuntimeError("VapiVoiceProvider requires VAPI_API_KEY.")
        self._headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}

    def create_outbound_call(self, plan: RequestPlan) -> ProviderCallResult:
        if not plan.target_phone_e164:
            raise ProviderRejected("No destination number resolved for call dispatch.")

        body: dict = {
            **caller_line(plan),
            "customer": {"number": plan.target_phone_e164},
            "assistant": build_assistant(plan, agent_config(plan.locale, plan.voice_profile_code)),
        }

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
