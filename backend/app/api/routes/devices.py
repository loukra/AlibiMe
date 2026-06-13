from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.core.clock import utcnow
from app.db.models.device import Device
from app.schemas.devices import DeviceResponse, DeviceUpsert

router = APIRouter(prefix="/v1/devices", tags=["devices"])


@router.put("/current", response_model=DeviceResponse)
def upsert_current_device(
    body: DeviceUpsert,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    device = db.execute(
        select(Device).where(
            Device.user_id == ctx.user.id, Device.device_id == body.device_id
        )
    ).scalars().first()
    if device is None:
        device = Device(user_id=ctx.user.id, device_id=body.device_id)
        db.add(device)
    device.platform = body.platform
    device.push_token = body.push_token
    device.app_version = body.app_version
    device.os_version = body.os_version
    device.last_seen_at = utcnow()
    db.commit()
    return DeviceResponse(id=str(device.id), device_id=device.device_id, platform=device.platform)
