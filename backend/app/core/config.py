"""Application configuration loaded from environment / .env.

Keep this provider-agnostic: the app code must not depend on Supabase-specific
auth or Edge Functions — only plain Postgres + FastAPI.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEV_ENVS = ("local", "test")
_DEV_SECRET = "dev-secret-change-me-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application. Unset counts as production, so a server that forgot its
    # .env refuses to start (see assert_deployable) instead of running mocks.
    # Local runs and tests set "local" / "test".
    app_env: str = "production"
    app_secret_key: str = _DEV_SECRET
    session_token_ttl_days: int = 30

    # Database
    database_url: str = "sqlite+pysqlite:///./believablecall.db"

    # Phone encryption (Fernet urlsafe base64 key). Derived from secret if blank.
    phone_encryption_key: str = ""

    # Providers
    otp_provider: str = "mock"
    voice_provider: str = "mock"
    message_provider: str = "mock"

    # Feature flags
    feature_free_test_request: bool = True
    # One text and one call: the text offers to save the number as a contact,
    # the call then shows that name. Once per phone number.
    free_test_credits: int = 3
    # What a request costs; a call costs more than a text (see docs/pricing.md).
    call_credit_cost: int = 2
    sms_credit_cost: int = 1
    # Extra credits on a phone number's first App Store purchase.
    first_purchase_bonus_credits: int = 3
    # Calls into another country bill at the destination's mobile rate per
    # started minute (US line to a German mobile: $0.376/min), so keep them
    # inside the first minute. 0 turns the cap off.
    cross_border_call_max_seconds: int = 55
    # Max request-create calls per user per hour. 5 is the production default;
    # raise it in dev (env REQUEST_CREATE_MAX_PER_HOUR) for rapid testing.
    request_create_max_per_hour: int = 5
    # Free credits once per iPhone through Apple's DeviceCheck, on top of once
    # per phone number: "apple", "mock" (local) or "off" (see
    # app/providers/device_check.py).
    device_check: str = "off"
    device_check_team_id: str | None = None
    device_check_key_id: str | None = None
    device_check_private_key_path: str | None = None  # the .p8 key file
    device_check_environment: str = "development"  # or "production"
    supported_countries: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["DE", "US", "GB", "AT", "CH"]
    )

    # Optional / later
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_verify_service_sid: str | None = None
    twilio_messaging_service_sid: str | None = None
    twilio_sms_from_number: str | None = None
    twilio_status_callback_url: str | None = None
    vapi_api_key: str | None = None
    # Fallback caller line when a sender line has neither its own Vapi number
    # nor Twilio credentials to place the call from.
    vapi_phone_number_id: str | None = None
    vapi_webhook_secret: str | None = None
    # Public https base of this API; Vapi posts call events to <base>/v1/webhooks/voice.
    public_base_url: str | None = None

    # Voice agent (sent to Vapi with every call; see app/agent)
    agent_llm_provider: str = "openai"
    agent_llm_model: str = "gpt-4o"
    agent_llm_temperature: float = 0.8
    agent_llm_max_tokens: int = 120
    agent_voice_provider: str = "11labs"
    agent_voice_model: str = "eleven_multilingual_v2"
    # ElevenLabs voice ids per style. Placeholders until real voices are picked.
    agent_voice_id_warm: str = "EXAVITQu4vr4xnSDxMaL"
    agent_voice_id_neutral: str = "21m00Tcm4TlvDq8ikWAM"
    agent_transcriber_provider: str = "deepgram"
    agent_transcriber_model: str = "nova-3"

    # Eval harness (backend/evals); "mock" runs offline with scripted replies.
    eval_llm_provider: str = "mock"
    eval_llm_model: str = "gpt-4o"
    eval_judge_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # In-app purchases. "mock" accepts mock:<product>:<id> tokens (never in
    # production); "app_store" verifies Apple's signed transactions.
    store_verifier: str = "mock"
    app_store_bundle_id: str = "com.believablecall.app"
    app_store_app_apple_id: int | None = None  # required for Production
    app_store_environment: str = "Sandbox"  # "Production", or "Xcode" for local StoreKit testing
    app_store_root_certs_dir: str | None = None
    revenuecat_webhook_secret: str | None = None
    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator("supported_countries", mode="before")
    @classmethod
    def _split_countries(cls, v):
        if isinstance(v, str):
            return [c.strip().upper() for c in v.split(",") if c.strip()]
        return v

    @property
    def is_dev(self) -> bool:
        return self.app_env in DEV_ENVS

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def fernet_key(self) -> bytes:
        """Return a valid Fernet key.

        If PHONE_ENCRYPTION_KEY is set, use it. Otherwise derive a deterministic
        key from APP_SECRET_KEY — acceptable for local/dev only.
        """
        if self.phone_encryption_key:
            return self.phone_encryption_key.encode()
        digest = hashlib.sha256(("phone-enc::" + self.app_secret_key).encode()).digest()
        return base64.urlsafe_b64encode(digest)


def production_problems(s: Settings) -> list[str]:
    """Settings that are fine on a laptop and dangerous on a server."""
    problems = []
    if s.otp_provider == "mock":
        problems.append("OTP_PROVIDER=mock accepts code 123456 for any number")
    if s.voice_provider == "mock" or s.message_provider == "mock":
        problems.append("VOICE_PROVIDER / MESSAGE_PROVIDER=mock deliver nothing")
    if s.store_verifier == "mock":
        problems.append("STORE_VERIFIER=mock grants credits for made-up purchases")
    if s.device_check == "mock":
        problems.append("DEVICE_CHECK=mock forgets every device on restart")
    if s.app_store_environment == "Xcode":
        problems.append("APP_STORE_ENVIRONMENT=Xcode skips Apple's signature")
    if s.app_secret_key == _DEV_SECRET or len(s.app_secret_key) < 32:
        problems.append("APP_SECRET_KEY is the dev default or shorter than 32 characters")
    if not s.phone_encryption_key:
        problems.append("PHONE_ENCRYPTION_KEY is empty")
    return problems


def assert_deployable(s: Settings | None = None) -> None:
    """Called when the API and the worker start. Outside local/test, refuse
    to run with any setting from production_problems."""
    s = s or settings
    if s.is_dev:
        return
    problems = production_problems(s)
    if problems:
        raise RuntimeError(
            f"Refusing to start with APP_ENV={s.app_env}:\n- " + "\n- ".join(problems)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
