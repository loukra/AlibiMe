from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth,
    credit_packages,
    devices,
    entitlements,
    health,
    history,
    me,
    requests,
    templates,
    webhooks_revenuecat,
    webhooks_sms,
    webhooks_voice,
)
from app.core.errors import AppError, error_envelope
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("app")

app = FastAPI(title="BelievableCall API", version="0.1.0")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4()}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.http_status,
        content=error_envelope(exc.code, exc.message, exc.retryable, request_id),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    # Surface a stable, client-friendly message. Any unexpected/forbidden field
    # (e.g. a smuggled destination number) lands here as a 422.
    return JSONResponse(
        status_code=422,
        content=error_envelope(
            "validation_failed",
            "The request failed validation.",
            False,
            request_id,
        )
        | {"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception("unhandled_error", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content=error_envelope("internal_error", "An internal error occurred.", False, request_id),
    )


for module in (
    health,
    auth,
    me,
    devices,
    templates,
    requests,
    history,
    entitlements,
    credit_packages,
    webhooks_voice,
    webhooks_sms,
    webhooks_revenuecat,
):
    app.include_router(module.router)


@app.get("/")
def root() -> dict:
    return {"service": "believablecall", "status": "ok"}
