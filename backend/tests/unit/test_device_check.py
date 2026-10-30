"""AppleDeviceCheck: the signed request and Apple's two answer shapes."""
from __future__ import annotations

import base64
import json

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app.core.config import settings
from app.providers import device_check as dc


def _unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


@pytest.fixture
def apple(monkeypatch, tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    p8 = tmp_path / "AuthKey_TEST.p8"
    p8.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    monkeypatch.setattr(settings, "device_check_team_id", "TEAM123")
    monkeypatch.setattr(settings, "device_check_key_id", "KEY456")
    monkeypatch.setattr(settings, "device_check_private_key_path", str(p8))
    monkeypatch.setattr(settings, "device_check_environment", "development")
    sent = []

    def respond(text: str, status: int = 200):
        def post(url, json=None, headers=None, timeout=None):
            sent.append((url, json, headers))
            return httpx.Response(status, text=text)
        monkeypatch.setattr(dc.httpx, "post", post)

    return dc.AppleDeviceCheck(), key, sent, respond


def test_jwt_is_es256_signed_by_the_key(apple):
    checker, key, _, _ = apple
    header, payload, sig = checker._jwt().split(".")
    assert json.loads(_unb64(header)) == {"alg": "ES256", "kid": "KEY456"}
    assert json.loads(_unb64(payload))["iss"] == "TEAM123"
    raw = _unb64(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    key.public_key().verify(der, f"{header}.{payload}".encode(), ec.ECDSA(hashes.SHA256()))


def test_unknown_device_is_not_claimed(apple):
    checker, _, sent, respond = apple
    respond("Failed to find bit state")
    assert checker.already_claimed("tok") is False
    url, body, headers = sent[0]
    assert url == "https://api.development.devicecheck.apple.com/v1/query_two_bits"
    assert body["device_token"] == "tok" and body["transaction_id"] and body["timestamp"]
    assert headers["Authorization"].startswith("Bearer ")


def test_set_bit_means_claimed(apple):
    checker, _, sent, respond = apple
    respond('{"bit0": true, "bit1": false, "last_update_time": "2026-10"}')
    assert checker.already_claimed("tok") is True
    checker.mark_claimed("tok")
    assert sent[-1][0].endswith("/update_two_bits") and sent[-1][1]["bit0"] is True


def test_apple_error_is_unavailable(apple):
    checker, _, _, respond = apple
    respond("Bad device token", status=400)
    with pytest.raises(dc.DeviceCheckUnavailable):
        checker.already_claimed("tok")


def test_apple_needs_its_key(monkeypatch):
    monkeypatch.setattr(settings, "device_check_key_id", None)
    with pytest.raises(RuntimeError, match="DEVICE_CHECK_KEY_ID"):
        dc.AppleDeviceCheck()
