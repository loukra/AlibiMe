"""Route-level enforcement of the Vapi shared-secret on /v1/webhooks/voice.

Enforced only in real Vapi mode; mock/local stays open so the `simulate` flow
and the rest of the suite keep working.
"""
from __future__ import annotations

from app.core.config import settings

SECRET = "vapi_server_secret"


def _enable_vapi(monkeypatch):
    monkeypatch.setattr(settings, "voice_provider", "vapi")
    monkeypatch.setattr(settings, "vapi_webhook_secret", SECRET)
    # Needed only when a request passes verification and builds the provider.
    monkeypatch.setattr(settings, "vapi_api_key", "vapi_key")
    monkeypatch.setattr(settings, "vapi_assistant_id", "asst_1")
    monkeypatch.setattr(settings, "vapi_phone_number_id", "pn_1")


def test_mock_mode_skips_secret(client):
    resp = client.post(
        "/v1/webhooks/voice",
        json={"type": "call.completed", "provider_call_id": "mock-1"},
    )
    assert resp.status_code == 200, resp.text


def test_vapi_mode_rejects_missing_secret(client, monkeypatch):
    _enable_vapi(monkeypatch)
    resp = client.post(
        "/v1/webhooks/voice",
        json={"message": {"type": "status-update", "status": "ringing", "call": {"id": "c1"}}},
    )
    assert resp.status_code == 403, resp.text


def test_vapi_mode_rejects_invalid_secret(client, monkeypatch):
    _enable_vapi(monkeypatch)
    resp = client.post(
        "/v1/webhooks/voice",
        json={"message": {"type": "status-update", "status": "ringing", "call": {"id": "c1"}}},
        headers={"X-Vapi-Secret": "wrong"},
    )
    assert resp.status_code == 403, resp.text


def test_vapi_mode_accepts_valid_secret(client, monkeypatch):
    _enable_vapi(monkeypatch)
    resp = client.post(
        "/v1/webhooks/voice",
        json={"message": {"type": "status-update", "status": "ringing", "call": {"id": "c1"}}},
        headers={"X-Vapi-Secret": SECRET},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] in {"processed", "duplicate"}
