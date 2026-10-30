from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PhoneStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str = Field(min_length=3, max_length=32)
    device_id: str | None = Field(default=None, max_length=128)
    locale: Literal["en", "de"] = "en"


class PhoneStartResponse(BaseModel):
    verification_id: str
    channel: str
    expires_in_seconds: int


class PhoneConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verification_id: str
    code: str = Field(min_length=3, max_length=10)
    device_id: str | None = Field(default=None, max_length=128)
    # DCDevice token, base64; lets the backend grant free credits once per iPhone.
    device_check_token: str | None = Field(default=None, max_length=8192)


class UserPublic(BaseModel):
    id: str
    locale: str
    phone_number_masked: str | None = None


class PhoneConfirmResponse(BaseModel):
    session_token: str
    user: UserPublic


class LogoutResponse(BaseModel):
    status: str = "logged_out"
