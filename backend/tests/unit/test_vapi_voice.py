"""Unit tests for the Vapi voice provider — fully network-stubbed."""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.db.models.enums import CallAttemptStatus
from app.providers.types import ProviderRejected, RequestPlan, TransientProviderError
from app.providers.voice.vapi import VapiVoiceProvider


class FakeResponse:
    def __init__(self, status_code: int, json_body=None, text: str = ""):
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}
        self.text = text

    def json(self):
        return self._json


def _plan(to: str = "+14155550123") -> RequestPlan:
    return RequestPlan(
        request_id="req-1",
        channel="call",
        template_code="sibling_family_checkin",
        template_version=1,
        locale="en",
        caller_persona="sibling",
        reason_code="family_checkin",
        rendered_opening_line="Hey, it's your sibling — can you talk?",
        max_duration_seconds=60,
        call_variables={
            "caller_label": "your sibling",
            "reason_summary": "a family check-in",
            "tone": "warm",
            "outcome": "step out briefly",
        },
        target_phone_e164=to,
    )


@pytest.fixture
def vapi_creds(monkeypatch):
    monkeypatch.setattr(settings, "vapi_api_key", "vapi_key")
    monkeypatch.setattr(settings, "vapi_phone_number_id", "pn_1")
    monkeypatch.setattr(settings, "twilio_account_sid", None)
    monkeypatch.setattr(settings, "twilio_auth_token", None)
    monkeypatch.setattr(settings, "public_base_url", None)


def test_init_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "vapi_api_key", None)
    with pytest.raises(RuntimeError):
        VapiVoiceProvider()


def _capture_post(monkeypatch) -> dict:
    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse(201, {"id": "call_1", "status": "queued", "cost": None})

    monkeypatch.setattr(httpx, "post", fake_post)
    return captured


def test_create_call_sends_agent_from_repo(vapi_creds, monkeypatch):
    captured = _capture_post(monkeypatch)
    result = VapiVoiceProvider().create_outbound_call(_plan())

    assert result.provider_call_id == "call_1"
    assert result.status == CallAttemptStatus.queued.value
    assert result.accepted is True
    body = captured["json"]
    assert "assistantId" not in body
    assert body["phoneNumberId"] == "pn_1"
    assert body["customer"]["number"] == "+14155550123"
    assistant = body["assistant"]
    assert assistant["firstMessage"].startswith("Hey, it's your sibling")
    assert assistant["maxDurationSeconds"] == 60
    assert assistant["backgroundSound"] == "off"
    system = assistant["model"]["messages"][0]
    assert system["role"] == "system"
    assert "your sibling" in system["content"]
    assert "not customer service" in system["content"]
    assert {"type": "endCall"} in assistant["model"]["tools"]
    assert assistant["transcriber"]["language"] == "en"
    assert assistant["metadata"]["request_id"] == "req-1"
    assert "server" not in assistant
    assert captured["headers"]["Authorization"] == "Bearer vapi_key"


def test_call_uses_sender_lines_own_vapi_number(vapi_creds, monkeypatch):
    captured = _capture_post(monkeypatch)
    plan = _plan()
    plan.sender_vapi_phone_number_id = "pn_mom"
    VapiVoiceProvider().create_outbound_call(plan)
    assert captured["json"]["phoneNumberId"] == "pn_mom"


def test_call_uses_sender_lines_twilio_number_inline(vapi_creds, monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC1")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok")
    captured = _capture_post(monkeypatch)
    plan = _plan()
    plan.service_identity_value = "+15550100123"
    VapiVoiceProvider().create_outbound_call(plan)
    body = captured["json"]
    assert "phoneNumberId" not in body
    assert body["phoneNumber"]["twilioPhoneNumber"] == "+15550100123"
    assert body["phoneNumber"]["twilioAccountSid"] == "AC1"


def test_call_without_any_caller_number_is_rejected(vapi_creds, monkeypatch):
    monkeypatch.setattr(settings, "vapi_phone_number_id", None)
    _capture_post(monkeypatch)
    with pytest.raises(ProviderRejected):
        VapiVoiceProvider().create_outbound_call(_plan())


def test_call_keeps_no_recording_transcript_or_summary_at_vapi(vapi_creds, monkeypatch):
    captured = _capture_post(monkeypatch)
    VapiVoiceProvider().create_outbound_call(_plan())
    assistant = captured["json"]["assistant"]
    assert assistant["artifactPlan"] == {
        "recordingEnabled": False,
        "pcapEnabled": False,
        "loggingEnabled": False,
        "transcriptPlan": {"enabled": False},
    }
    assert assistant["analysisPlan"] == {"summaryPrompt": "", "successEvaluationPrompt": ""}
    assert assistant["serverMessages"] == ["status-update", "end-of-call-report"]
    # The live transcriber stays: the agent has to hear the user.
    assert assistant["transcriber"]["provider"]


def test_webhook_server_and_secret_sent_when_configured(vapi_creds, monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "https://api.example.com/")
    monkeypatch.setattr(settings, "vapi_webhook_secret", "s3cret")
    captured = _capture_post(monkeypatch)
    VapiVoiceProvider().create_outbound_call(_plan())
    server = captured["json"]["assistant"]["server"]
    assert server["url"] == "https://api.example.com/v1/webhooks/voice"
    assert server["headers"]["X-Vapi-Secret"] == "s3cret"


def test_create_call_handles_list_response(vapi_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(201, [{"id": "c9", "status": "ringing"}]))
    result = VapiVoiceProvider().create_outbound_call(_plan())
    assert result.provider_call_id == "c9"
    assert result.status == CallAttemptStatus.ringing.value


def test_create_call_transient_on_5xx(vapi_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(502, text="bad gateway"))
    with pytest.raises(TransientProviderError):
        VapiVoiceProvider().create_outbound_call(_plan())


def test_create_call_transient_on_429(vapi_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(429, text="rate limited"))
    with pytest.raises(TransientProviderError):
        VapiVoiceProvider().create_outbound_call(_plan())


def test_create_call_rejected_on_4xx(vapi_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(400, text="bad assistant"))
    with pytest.raises(ProviderRejected):
        VapiVoiceProvider().create_outbound_call(_plan())


def test_create_call_transient_on_network_error(vapi_creds, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(TransientProviderError):
        VapiVoiceProvider().create_outbound_call(_plan())


def test_parse_webhook_status_update(vapi_creds):
    provider = VapiVoiceProvider()
    parsed = provider.parse_webhook(
        {"message": {"type": "status-update", "status": "ringing", "call": {"id": "call_1"}}}
    )
    assert parsed.provider_ref_id == "call_1"
    assert parsed.mapped_status == CallAttemptStatus.ringing.value
    assert parsed.external_event_id == "call_1:status-update"


def test_parse_webhook_in_progress(vapi_creds):
    provider = VapiVoiceProvider()
    parsed = provider.parse_webhook(
        {"message": {"type": "status-update", "status": "in-progress", "call": {"id": "c2"}}}
    )
    assert parsed.mapped_status == CallAttemptStatus.in_progress.value


def test_parse_webhook_end_of_call_report(vapi_creds):
    provider = VapiVoiceProvider()
    parsed = provider.parse_webhook(
        {
            "message": {
                "type": "end-of-call-report",
                "call": {"id": "call_1"},
                "endedReason": "customer-ended-call",
                "durationSeconds": 42.6,
                "cost": 0.07,
            }
        }
    )
    assert parsed.mapped_status == CallAttemptStatus.ended.value
    assert parsed.fields["ended_reason"] == "customer-ended-call"
    assert parsed.fields["duration_seconds"] == 43
    assert parsed.fields["estimated_cost_minor"] == 7


def test_parse_webhook_handles_flat_payload(vapi_creds):
    # Defensive: some events may arrive without the {"message": ...} wrapper.
    provider = VapiVoiceProvider()
    parsed = provider.parse_webhook({"type": "status-update", "status": "ended", "callId": "c3"})
    assert parsed.provider_ref_id == "c3"
    assert parsed.mapped_status == CallAttemptStatus.ended.value
