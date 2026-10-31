from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.core.errors import ValidationFailed
from app.domain.billing import credits
from app.domain.requests import service as requests_service
from app.domain.requests import state
from app.schemas.requests import (
    AttemptSummary,
    CancelResponse,
    CreateRequestBody,
    CreateRequestResponse,
    RequestDetail,
    SenderIdentityOut,
)

router = APIRouter(prefix="/v1/requests", tags=["requests"])


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        raise ValidationFailed(f"Invalid {field}.")


@router.post("", response_model=CreateRequestResponse, status_code=201)
def create_request(
    body: CreateRequestBody,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> CreateRequestResponse:
    template_id = _parse_uuid(body.template_id, "template_id")
    req = requests_service.create_request(
        db,
        ctx.user.id,
        client_request_id=body.client_request_id,
        template_id=template_id,
        channel=body.channel,
        delay_seconds=body.delay_seconds,
        scheduled_at=body.scheduled_at,
        user_locale=ctx.user.locale,
    )
    sender = requests_service.sender_identity_payload(db, req, ctx.user.locale)
    return CreateRequestResponse(
        request_id=str(req.id),
        channel=req.channel,
        status=req.status,
        execute_at=req.execute_at,
        credits_available=credits.current_balance(db, ctx.user.id),
        cancelable=state.is_cancelable(req.status),
        sender_identity=SenderIdentityOut(**sender) if sender else None,
    )


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(
    request_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> RequestDetail:
    rid = _parse_uuid(request_id, "request_id")
    req = requests_service.get_request(db, ctx.user.id, rid)
    summary = requests_service.latest_attempt_summary(db, req)
    sender = requests_service.sender_identity_payload(db, req, ctx.user.locale)
    return RequestDetail(
        request_id=str(req.id),
        channel=req.channel,
        status=req.status,
        scheduled_kind=req.scheduled_kind,
        execute_at=req.execute_at,
        requested_at=req.requested_at,
        cancelable=state.is_cancelable(req.status),
        last_error_code=req.last_error_code,
        latest_attempt=AttemptSummary(**summary) if summary else None,
        sender_identity=SenderIdentityOut(**sender) if sender else None,
    )


@router.post("/{request_id}/cancel", response_model=CancelResponse)
def cancel_request(
    request_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> CancelResponse:
    rid = _parse_uuid(request_id, "request_id")
    req = requests_service.cancel_request(db, ctx.user.id, rid)
    return CancelResponse(request_id=str(req.id), status=req.status)
