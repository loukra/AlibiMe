from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.domain.auth import service as auth_service
from app.providers.factory import get_otp_provider
from app.schemas.auth import (
    LogoutResponse,
    PhoneConfirmRequest,
    PhoneConfirmResponse,
    PhoneStartRequest,
    PhoneStartResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/phone/start", response_model=PhoneStartResponse)
def phone_start(body: PhoneStartRequest, db: Session = Depends(get_db)) -> PhoneStartResponse:
    result = auth_service.start_phone_verification(
        db,
        get_otp_provider(),
        raw_phone=body.phone_number,
        device_id=body.device_id,
        locale=body.locale,
    )
    return PhoneStartResponse(**result)


@router.post("/phone/confirm", response_model=PhoneConfirmResponse)
def phone_confirm(body: PhoneConfirmRequest, db: Session = Depends(get_db)) -> PhoneConfirmResponse:
    result = auth_service.confirm_phone_verification(
        db,
        get_otp_provider(),
        verification_id=body.verification_id,
        code=body.code,
        device_id=body.device_id,
        device_check_token=body.device_check_token,
    )
    return PhoneConfirmResponse(**result)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    auth_service.logout(db, ctx.session)
    return LogoutResponse()
