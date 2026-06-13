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
        target_phone_e164=to,
        user_first_name="Alex",
    )


@pytest.fixture
def vapi_creds(monkeypatch):
    monkeypatch.setattr(settings, "vapi_api_key", "vapi_key")
    monkeypatch.setattr(settings, "vapi_assistant_id", "asst_1")
    monkeypatch.setattr(settings, "vapi_phone_number_id", "pn_1")


def test_init_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "vapi_api_key", None)
    with pytest.raises(RuntimeError):
        VapiVoiceProvider()


def test_init_requires_assistant_and_number(monkeypatch):
    monkeypatch.setattr(settings, "vapi_api_key", "k")
    monkeypatch.setattr(settings, "vapi_assistant_id", None)
    monkeypatch.setattr(settings, "vapi_phone_number_id", None)
    with pytest.raises(RuntimeError):
        VapiVoiceProvider()


def test_create_call_success(vapi_creds, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse(201, {"id": "call_1", "status": "queued", "cost": None})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = VapiVoiceProvider().create_outbound_call(_plan())

    assert result.provider_call_id == "call_1"
    assert result.status == CallAttemptStatus.queued.value
    assert result.accepted is True
    body = captured["json"]
    assert body["phoneNumberId"] == "pn_1"
    assert body["assistantId"] == "asst_1"
    assert body["customer"]["number"] == "+14155550123"
    assert body["assistantOverrides"]["firstMessage"].startswith("Hey, it's your sibling")
    assert body["assistantOverrides"]["maxDurationSeconds"] == 60
    assert body["assistantOverrides"]["variableValues"]["caller"] == "sibling"
    assert captured["headers"]["Authorization"] == "Bearer vapi_key"


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
