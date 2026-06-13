from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=1, max_length=128)
    platform: Literal["ios", "android"] = "ios"
    push_token: str | None = Field(default=None, max_length=512)
    app_version: str | None = Field(default=None, max_length=32)
    os_version: str | None = Field(default=None, max_length=32)


class DeviceResponse(BaseModel):
    id: str
    device_id: str
    platform: str
