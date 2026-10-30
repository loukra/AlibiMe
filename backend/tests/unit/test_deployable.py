"""The startup guard: mocks and dev secrets never run on a server."""
from __future__ import annotations

import pytest

from app.core.config import _DEV_SECRET, Settings, assert_deployable, production_problems

_REAL = dict(
    otp_provider="twilio_verify",
    voice_provider="vapi",
    message_provider="twilio",
    store_verifier="app_store",
    app_store_environment="Production",
    app_secret_key="x" * 40,
    phone_encryption_key="k" * 44,
)


def test_unset_app_env_counts_as_production(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert Settings(_env_file=None).app_env == "production"


def test_server_with_mocks_refuses_to_start():
    s = Settings(_env_file=None, app_env="production", app_secret_key=_DEV_SECRET)
    problems = production_problems(s)
    assert any("OTP_PROVIDER" in p for p in problems)
    assert any("STORE_VERIFIER" in p for p in problems)
    assert any("APP_SECRET_KEY" in p for p in problems)
    with pytest.raises(RuntimeError, match="STORE_VERIFIER=mock"):
        assert_deployable(s)


def test_xcode_purchases_refused_on_a_server():
    s = Settings(_env_file=None, app_env="staging", **{**_REAL, "app_store_environment": "Xcode"})
    assert production_problems(s) == ["APP_STORE_ENVIRONMENT=Xcode skips Apple's signature"]


def test_configured_server_starts():
    assert_deployable(Settings(_env_file=None, app_env="production", **_REAL))


def test_local_runs_with_mocks():
    assert_deployable(Settings(_env_file=None, app_env="local"))
