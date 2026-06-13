from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.domain.templates.service import list_catalog
from app.schemas.templates import TemplateListResponse, TemplateOut

router = APIRouter(prefix="/v1/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
def get_templates(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> TemplateListResponse:
    catalog = list_catalog(db, ctx.user.locale)
    return TemplateListResponse(templates=[TemplateOut(**t) for t in catalog])
