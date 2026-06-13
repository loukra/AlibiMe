"""Consistent error model used across the API.

The error envelope is:
{
  "error": {
    "code": "...",
    "message": "...",
    "retryable": false,
    "request_id": "server-request-id"
  }
}
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for domain/application errors mapped to the JSON envelope."""

    code: str = "internal_error"
    http_status: int = 400
    retryable: bool = False

    def __init__(self, message: str | None = None, *, retryable: bool | None = None):
        self.message = message or self.default_message
        if retryable is not None:
            self.retryable = retryable
        super().__init__(self.message)

    default_message: str = "An error occurred."


class Unauthorized(AppError):
    code = "unauthorized"
    http_status = 401
    default_message = "Authentication is required."


class SessionExpired(AppError):
    code = "session_expired"
    http_status = 401
    default_message = "Your session has expired. Please sign in again."


class PhoneNotVerified(AppError):
    code = "phone_not_verified"
    http_status = 409
    default_message = "You must verify a primary phone number first."


class InvalidPhoneNumber(AppError):
    code = "invalid_phone_number"
    http_status = 422
    default_message = "The phone number is invalid."


class UnsupportedLineType(AppError):
    code = "unsupported_line_type"
    http_status = 422
    default_message = "This type of phone line is not supported."


class RateLimited(AppError):
    code = "rate_limited"
    http_status = 429
    retryable = True
    default_message = "Too many requests. Please slow down."


class ActiveRequestExists(AppError):
    code = "active_request_exists"
    http_status = 409
    default_message = "You already have an active request in progress."


class TemplateChannelNotSupported(AppError):
    code = "template_channel_not_supported"
    http_status = 422
    default_message = "This template does not support the requested channel."


class InsufficientCredits(AppError):
    code = "insufficient_credits"
    http_status = 402
    default_message = "You do not have enough credits to send this request."


class InvalidScheduleWindow(AppError):
    code = "invalid_schedule_window"
    http_status = 422
    default_message = "The requested time is outside the allowed scheduling window."


class RequestNotCancelable(AppError):
    code = "request_not_cancelable"
    http_status = 409
    default_message = "This request can no longer be canceled."


class ProviderUnavailable(AppError):
    code = "provider_unavailable"
    http_status = 503
    retryable = True
    default_message = "The provider is temporarily unavailable."


class NotFound(AppError):
    code = "not_found"
    http_status = 404
    default_message = "Resource not found."


class ValidationFailed(AppError):
    code = "validation_failed"
    http_status = 422
    default_message = "The request failed validation."


def error_envelope(code: str, message: str, retryable: bool, request_id: str | None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": request_id,
        }
    }
