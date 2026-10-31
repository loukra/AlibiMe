from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.db.models.artifact import RequestArtifact
from app.db.models.enums import Channel
from app.db.models.request import Request
from app.db.models.template import Template
from app.domain.requests import service as requests_service
from app.domain.requests import state
from app.domain.templates import service as templates_service
from app.schemas.history import HistoryItem, HistoryResponse

router = APIRouter(prefix="/v1/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
def get_history(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> HistoryResponse:
    rows = db.execute(
        select(Request, Template)
        .join(Template, Template.id == Request.template_id)
        .where(Request.user_id == ctx.user.id)
        .order_by(Request.created_at.desc())
        .limit(limit + 1)
        .offset(offset)
    ).all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items: list[HistoryItem] = []
    for req, template in rows:
        template_label = templates_service.display_name(db, template, ctx.user.locale)
        duration = None
        if req.channel == Channel.call.value:
            attempt = requests_service.latest_call_attempt(db, req.id)
            duration = attempt.duration_seconds if attempt else None
        artifact = (
            db.query(RequestArtifact).filter(RequestArtifact.request_id == req.id).first()
        )
        preview = None
        if artifact:
            preview = artifact.delivered_message_preview or artifact.summary_text
        items.append(
            HistoryItem(
                request_id=str(req.id),
                channel=req.channel,
                template_label=template_label,
                requested_at=req.requested_at,
                execute_at=req.execute_at,
                final_status=req.status,
                cancelable=state.is_cancelable(req.status),
                duration_seconds=duration,
                delivered_preview=preview,
                sender_binding_id=str(req.sender_binding_id) if req.sender_binding_id else None,
                sender_persona_key=req.sender_persona_key,
                sender_display_name=req.sender_display_name_snapshot,
                sender_phone_e164=req.sender_phone_e164_snapshot,
            )
        )

    return HistoryResponse(items=items, limit=limit, offset=offset, has_more=has_more)
