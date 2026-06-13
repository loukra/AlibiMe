"""Route-level enforcement of Twilio signature verification on /v1/webhooks/sms.

Verification is enforced only in real Twilio mode; mock/local stays open so the
`simulate` flow and the rest of the suite keep working.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.twilio_webhook import compute_twilio_signature

CALLBACK_URL = "https://example.test/v1/webhooks/sms"
AUTH_TOKEN = "test_auth_token"


def _enable_twilio(monkeypatch):
    monkeypatch.setattr(settings, "message_provider", "twilio_messaging")
    monkeypatch.setattr(settings, "twilio_auth_token", AUTH_TOKEN)
    monkeypatch.setattr(settings, "twilio_status_callback_url", CALLBACK_URL)
    # Needed only when a request passes verification and builds the provider.
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_test")
    monkeypatch.setattr(settings, "twilio_messaging_service_sid", "MG_test")


def test_mock_mode_skips_verification(client):
    # Default mode is mock: an unsigned callback must NOT be rejected, so the
    # local `simulate` flow keeps working.
    resp = client.post(
        "/v1/webhooks/sms",
        data={"type": "message.delivered", "provider_message_id": "mock-1"},
    )
    assert resp.status_code == 200, resp.text


def test_twilio_mode_rejects_missing_signature(client, monkeypatch):
    _enable_twilio(monkeypatch)
    resp = client.post(
        "/v1/webhooks/sms",
        data={"MessageSid": "SM1", "MessageStatus": "delivered"},
    )
    assert resp.status_code == 403, resp.text


def test_twilio_mode_rejects_invalid_signature(client, monkeypatch):
    _enable_twilio(monkeypatch)
    resp = client.post(
        "/v1/webhooks/sms",
        data={"MessageSid": "SM1", "MessageStatus": "delivered"},
        headers={"X-Twilio-Signature": "totally-wrong=="},
    )
    assert resp.status_code == 403, resp.text


def test_twilio_mode_accepts_valid_signature(client, monkeypatch):
    _enable_twilio(monkeypatch)
    params = {"MessageSid": "SM1", "MessageStatus": "delivered"}
    signature = compute_twilio_signature(CALLBACK_URL, params, AUTH_TOKEN)
    resp = client.post(
        "/v1/webhooks/sms",
        data=params,
        headers={"X-Twilio-Signature": signature},
    )
    assert resp.status_code == 200, resp.text
    # No matching attempt exists, but the request was accepted and processed.
    assert resp.json()["status"] in {"processed", "duplicate"}
