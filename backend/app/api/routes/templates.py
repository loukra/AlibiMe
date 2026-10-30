from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.core.errors import ValidationFailed
from app.domain.templates import compose
from app.domain.templates import service as templates_service
from app.schemas.templates import (
    CreateCustomTemplateBody,
    TemplateListResponse,
    TemplateOut,
)

router = APIRouter(prefix="/v1/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
def get_templates(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> TemplateListResponse:
    catalog = templates_service.list_catalog(db, ctx.user.locale, ctx.user.id)
    return TemplateListResponse(templates=[TemplateOut(**t) for t in catalog])


@router.get("/options")
def get_template_options(
    ctx: CurrentContext = Depends(get_current_context),
) -> dict:
    # The full coded catalog (scenario dimensions + user-context profile options)
    # the editor and Profile tab build from. Returned as-is.
    return compose.options(ctx.user.locale)


def _parse_id(template_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(template_id)
    except (ValueError, TypeError):
        raise ValidationFailed("Invalid template id.")


@router.post("", response_model=TemplateOut, status_code=201)
def create_custom_template(
    body: CreateCustomTemplateBody,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> TemplateOut:
    item = templates_service.create_custom_template(
        db, ctx.user.id, locale=ctx.user.locale, **body.model_dump()
    )
    return TemplateOut(**item)


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: str,
    body: CreateCustomTemplateBody,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> TemplateOut:
    """Edit an own template, or a built-in one (stored as the user's edited copy)."""
    item = templates_service.update_template(
        db, ctx.user.id, _parse_id(template_id), locale=ctx.user.locale, **body.model_dump()
    )
    return TemplateOut(**item)


@router.delete("/{template_id}", status_code=204)
def delete_custom_template(
    template_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> None:
    """Delete an own template, or reset an edited built-in to its original."""
    templates_service.delete_custom_template(db, ctx.user.id, _parse_id(template_id))
