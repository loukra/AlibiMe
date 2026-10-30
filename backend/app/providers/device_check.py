"""Apple DeviceCheck: free credits once per iPhone.

Apple keeps two bits per device and developer team. They survive deleting the
app and resetting its data, so bit0 marks "this iPhone already had its free
credits", whichever phone number signs up on it next. The app sends a token
from ``DCDevice.generateToken()``; only Apple can map it to a device.

``DEVICE_CHECK=apple`` needs a DeviceCheck key from the developer account
(team id, key id, the ``.p8`` file). ``mock`` keeps the bits in memory for local
runs; ``off`` skips the check.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import settings

_APPLE_HOSTS = {
    "development": "https://api.development.devicecheck.apple.com/v1",
    "production": "https://api.devicecheck.apple.com/v1",
}


class DeviceCheckUnavailable(Exception):
    """Apple couldn't be asked; the caller falls back to the phone-number check."""


class DeviceCheck(Protocol):
    def already_claimed(self, token: str) -> bool: ...

    def mark_claimed(self, token: str) -> None: ...


_mock_claimed: set[str] = set()


class MockDeviceCheck:
    def already_claimed(self, token: str) -> bool:
        return token in _mock_claimed

    def mark_claimed(self, token: str) -> None:
        _mock_claimed.add(token)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class AppleDeviceCheck:
    def __init__(self) -> None:
        missing = [
            name
            for name, value in (
                ("DEVICE_CHECK_TEAM_ID", settings.device_check_team_id),
                ("DEVICE_CHECK_KEY_ID", settings.device_check_key_id),
                ("DEVICE_CHECK_PRIVATE_KEY_PATH", settings.device_check_private_key_path),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"DEVICE_CHECK=apple needs {', '.join(missing)}.")
        self._base = _APPLE_HOSTS[settings.device_check_environment]
        self._key = Path(settings.device_check_private_key_path).read_bytes()

    def _jwt(self) -> str:
        """ES256 token Apple expects, signed with the DeviceCheck key."""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        header = {"alg": "ES256", "kid": settings.device_check_key_id}
        payload = {"iss": settings.device_check_team_id, "iat": int(time.time())}
        signing_input = (
            _b64url(json.dumps(header).encode()) + "." + _b64url(json.dumps(payload).encode())
        )
        key = serialization.load_pem_private_key(self._key, password=None)
        r, s = decode_dss_signature(key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256())))
        return signing_input + "." + _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))

    def _post(self, path: str, body: dict) -> httpx.Response:
        body = {
            **body,
            "transaction_id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
        }
        try:
            resp = httpx.post(
                f"{self._base}/{path}",
                json=body,
                headers={"Authorization": f"Bearer {self._jwt()}"},
                timeout=10.0,
            )
        except httpx.TransportError as exc:
            raise DeviceCheckUnavailable(str(exc)) from exc
        if resp.status_code != 200:
            raise DeviceCheckUnavailable(f"DeviceCheck {path}: HTTP {resp.status_code}")
        return resp

    def already_claimed(self, token: str) -> bool:
        resp = self._post("query_two_bits", {"device_token": token})
        # A device whose bits were never set answers 200 with plain text.
        try:
            return bool(resp.json().get("bit0"))
        except ValueError:
            return False

    def mark_claimed(self, token: str) -> None:
        self._post("update_two_bits", {"device_token": token, "bit0": True})


def get_device_check() -> DeviceCheck | None:
    if settings.device_check == "apple":
        return AppleDeviceCheck()
    if settings.device_check == "mock":
        return MockDeviceCheck()
    return None
