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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: str = "local"
    app_secret_key: str = "dev-secret-change-me-0123456789abcdef"
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
    free_test_credits: int = 3
    supported_countries: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["DE", "US", "GB", "AT", "CH"]
    )

    # Optional / later
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_verify_service_sid: str | None = None
    twilio_messaging_service_sid: str | None = None
    vapi_api_key: str | None = None
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
