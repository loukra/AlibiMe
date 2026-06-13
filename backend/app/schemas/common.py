from __future__ import annotations

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
