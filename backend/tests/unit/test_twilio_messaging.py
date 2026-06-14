"""Unit tests for the Twilio SMS provider — fully network-stubbed.

These never call Twilio: httpx.post is monkeypatched and the credentials are
injected onto the settings object.
"""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.db.models.enums import MessageAttemptStatus
from app.providers.messaging.twilio_sms import TwilioMessagingProvider
from app.providers.types import ProviderRejected, RequestPlan, TransientProviderError


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text

    def json(self) -> dict:
        return self._json


def _plan(body: str = "Your sibling: can you call home?", to: str = "+14155550123") -> RequestPlan:
    return RequestPlan(
        request_id="req-1",
        channel="sms",
        template_code="sibling_family_checkin",
        template_version=1,
        locale="en",
        caller_persona="sibling",
        reason_code="family_checkin",
        rendered_sms_body=body,
        target_phone_e164=to,
    )


@pytest.fixture
def twilio_creds(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_test")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok_test")
    monkeypatch.setattr(settings, "twilio_messaging_service_sid", "MG_test")
    monkeypatch.setattr(settings, "twilio_sms_from_number", None)
    monkeypatch.setattr(settings, "twilio_status_callback_url", "https://example.test/v1/webhooks/sms")


def test_init_requires_credentials(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", None)
    with pytest.raises(RuntimeError):
        TwilioMessagingProvider()


def test_init_requires_sender(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_test")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok_test")
    monkeypatch.setattr(settings, "twilio_messaging_service_sid", None)
    monkeypatch.setattr(settings, "twilio_sms_from_number", None)
    with pytest.raises(RuntimeError):
        TwilioMessagingProvider()


def test_send_success_maps_result(twilio_creds, monkeypatch):
    captured = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        captured["url"] = url
        captured["auth"] = auth
        captured["data"] = data
        return FakeResponse(201, {"sid": "SM123", "status": "queued", "price": None})

    monkeypatch.setattr(httpx, "post", fake_post)

    result = TwilioMessagingProvider().send_sms(_plan())

    assert result.provider_message_id == "SM123"
    assert result.status == MessageAttemptStatus.queued.value
    assert result.accepted is True
    # Sends via the Messaging Service, to the resolved number, with our callback.
    assert captured["data"]["MessagingServiceSid"] == "MG_test"
    assert captured["data"]["To"] == "+14155550123"
    assert captured["data"]["StatusCallback"] == "https://example.test/v1/webhooks/sms"
    assert captured["auth"] == ("AC_test", "tok_test")


def test_send_uses_bound_line_as_explicit_from(twilio_creds, monkeypatch):
    """When the dispatcher resolved a sender line, send with it as an explicit
    From — even though a Messaging Service is configured — so the recipient sees
    the bound number (continuity with the saved contact)."""
    captured = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        captured["data"] = data
        return FakeResponse(201, {"sid": "SM77", "status": "queued"})

    monkeypatch.setattr(httpx, "post", fake_post)
    plan = _plan()
    plan.service_identity_value = "+19998887777"  # the bound sender line
    TwilioMessagingProvider().send_sms(plan)
    assert captured["data"]["From"] == "+19998887777"
    assert "MessagingServiceSid" not in captured["data"]


def test_send_uses_from_number_when_no_messaging_service(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_test")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok_test")
    monkeypatch.setattr(settings, "twilio_messaging_service_sid", None)
    monkeypatch.setattr(settings, "twilio_sms_from_number", "+18885550000")
    monkeypatch.setattr(settings, "twilio_status_callback_url", None)
    captured = {}

    def fake_post(url, auth=None, data=None, timeout=None):
        captured["data"] = data
        return FakeResponse(201, {"sid": "SM9", "status": "accepted"})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = TwilioMessagingProvider().send_sms(_plan())
    assert result.status == MessageAttemptStatus.queued.value  # "accepted" -> queued
    assert captured["data"]["From"] == "+18885550000"
    assert "MessagingServiceSid" not in captured["data"]
    assert "StatusCallback" not in captured["data"]


def test_send_transient_on_5xx(twilio_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(503, text="busy"))
    with pytest.raises(TransientProviderError):
        TwilioMessagingProvider().send_sms(_plan())


def test_send_transient_on_429(twilio_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(429, text="slow down"))
    with pytest.raises(TransientProviderError):
        TwilioMessagingProvider().send_sms(_plan())


def test_send_rejected_on_4xx(twilio_creds, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(400, text="bad number"))
    with pytest.raises(ProviderRejected):
        TwilioMessagingProvider().send_sms(_plan())


def test_send_transient_on_network_error(twilio_creds, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("dns")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(TransientProviderError):
        TwilioMessagingProvider().send_sms(_plan())


def test_send_rejected_without_body(twilio_creds):
    with pytest.raises(ProviderRejected):
        TwilioMessagingProvider().send_sms(_plan(body=""))


@pytest.mark.parametrize(
    "twilio_status,expected",
    [
        ("queued", MessageAttemptStatus.queued.value),
        ("sent", MessageAttemptStatus.sent.value),
        ("delivered", MessageAttemptStatus.delivered.value),
        ("undelivered", MessageAttemptStatus.failed_post_send.value),
        ("failed", MessageAttemptStatus.failed_post_send.value),
    ],
)
def test_parse_webhook_status_mapping(twilio_creds, twilio_status, expected):
    provider = TwilioMessagingProvider()
    parsed = provider.parse_webhook(
        {"MessageSid": "SM123", "MessageStatus": twilio_status, "ErrorCode": "30008"}
    )
    assert parsed.provider_ref_id == "SM123"
    assert parsed.mapped_status == expected
    assert parsed.event_type == twilio_status
    # Dedupe key is per (message, status) since Twilio sends no event id.
    assert parsed.external_event_id == f"SM123:{twilio_status}"
    assert parsed.fields["failure_reason"] == "30008"


def test_parse_webhook_accepts_sms_aliases(twilio_creds):
    provider = TwilioMessagingProvider()
    parsed = provider.parse_webhook({"SmsSid": "SMabc", "SmsStatus": "delivered"})
    assert parsed.provider_ref_id == "SMabc"
    assert parsed.mapped_status == MessageAttemptStatus.delivered.value
