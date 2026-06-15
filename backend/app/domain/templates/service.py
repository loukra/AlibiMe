"""Template catalog, version resolution, content rendering, and snapshotting."""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, TemplateChannelNotSupported, ValidationFailed
from app.db.models.enums import Channel
from app.db.models.template import Template, TemplateVersion
from app.domain.templates import compose, rendering

_DEFAULT_LOCALE = "en"


def resolve_version(db: Session, template_id: uuid.UUID, locale: str) -> TemplateVersion:
    """Return the active version for (template, locale), falling back to en."""
    for loc in (locale, _DEFAULT_LOCALE):
        version = db.execute(
            select(TemplateVersion)
            .where(
                TemplateVersion.template_id == template_id,
                TemplateVersion.locale == loc,
                TemplateVersion.active.is_(True),
            )
            .order_by(TemplateVersion.version.desc())
        ).scalars().first()
        if version:
            return version
    raise NotFound("No active template version found for this template.")


def supported_channels(version: TemplateVersion) -> list[str]:
    channels = []
    if version.supports_call:
        channels.append(Channel.call.value)
    if version.supports_sms:
        channels.append(Channel.sms.value)
    return channels


def assert_channel_supported(version: TemplateVersion, channel: str) -> None:
    if channel not in supported_channels(version):
        raise TemplateChannelNotSupported(
            f"Template version does not support channel '{channel}'."
        )


def _catalog_item(db: Session, tmpl: Template, locale: str) -> dict | None:
    try:
        version = resolve_version(db, tmpl.id, locale)
    except NotFound:
        return None
    ctx = rendering.build_context(
        locale=locale, caller_persona=tmpl.caller_persona, reason_code=tmpl.reason_code
    )
    return {
        "id": str(tmpl.id),
        "code": tmpl.code,
        "display_name": tmpl.display_name,
        "description": tmpl.description,
        "category": tmpl.category,
        "caller_persona": tmpl.caller_persona,
        "reason_code": tmpl.reason_code,
        "sender_persona_key": tmpl.sender_persona_key,
        "sender_display_name": tmpl.sender_display_name,
        "supports_contact_save": tmpl.supports_contact_save,
        "is_custom": tmpl.owner_user_id is not None,
        "supported_channels": supported_channels(version),
        "call_max_duration_seconds": version.call_max_duration_seconds
        if version.supports_call
        else None,
        "preview_opening_line": rendering.render(version.call_opening_line_template, ctx)
        if version.supports_call
        else None,
        "preview_sms_body": rendering.render(version.sms_body_template, ctx)
        if version.supports_sms
        else None,
    }


def list_catalog(db: Session, locale: str, user_id: uuid.UUID) -> list[dict]:
    """System templates plus the requesting user's own custom templates.

    Custom (user-owned) templates sort after system ones.
    """
    templates = db.execute(
        select(Template)
        .where(
            Template.active.is_(True),
            or_(Template.owner_user_id.is_(None), Template.owner_user_id == user_id),
        )
        .order_by(Template.owner_user_id.isnot(None), Template.code)
    ).scalars().all()
    catalog = []
    for tmpl in templates:
        item = _catalog_item(db, tmpl, locale)
        if item is not None:
            catalog.append(item)
    return catalog


def create_custom_template(
    db: Session,
    user_id: uuid.UUID,
    *,
    display_name: str,
    description: str | None,
    category: str,
    persona: str,
    reason: str,
    urgency: str,
    channels: list[str],
    voice_style: str,
    call_max_seconds: int | None,
    locale: str = _DEFAULT_LOCALE,
) -> dict:
    """Validate structured choices and compose a user-owned template (+ versions)
    from approved skeletons. No free-form user text reaches the content."""
    name = (display_name or "").strip()
    if not (1 <= len(name) <= 120):
        raise ValidationFailed("Template name must be 1–120 characters.")
    if description and len(description) > 255:
        raise ValidationFailed("Description is too long.")
    if category not in compose.CATEGORIES:
        raise ValidationFailed("Unknown category.")
    if not compose.is_valid_persona(persona):
        raise ValidationFailed("Unknown persona.")
    if not compose.is_valid_reason(reason):
        raise ValidationFailed("Unknown reason.")
    if urgency not in compose.URGENCIES:
        raise ValidationFailed("Unknown urgency.")
    if voice_style not in compose.VOICE_STYLES:
        raise ValidationFailed("Unknown voice style.")
    selected = [c for c in channels if c in (Channel.call.value, Channel.sms.value)]
    if not selected:
        raise ValidationFailed("Select at least one channel.")
    seconds = compose.clamp_call_seconds(call_max_seconds)

    existing = db.execute(
        select(func.count()).select_from(Template).where(Template.owner_user_id == user_id)
    ).scalar_one()
    if existing >= compose.MAX_CUSTOM_TEMPLATES_PER_USER:
        raise ValidationFailed("You've reached the maximum number of custom templates.")

    tmpl = Template(
        code=f"custom_{uuid.uuid4().hex[:12]}",
        category=category,
        caller_persona=persona,
        reason_code=reason,
        display_name=name,
        description=(description.strip() if description else None),
        owner_user_id=user_id,
        sender_persona_key=persona,
        sender_display_name=rendering.PERSONA_LABELS["en"].get(persona, persona),
        supports_contact_save=True,
        active=True,
    )
    db.add(tmpl)
    db.flush()

    for loc in ("en", "de"):
        content = compose.compose_version_content(
            persona=persona,
            reason=reason,
            urgency=urgency,
            locale=loc,
            channels=selected,
            voice_style=voice_style,
            call_max_seconds=seconds,
            category=category,
        )
        db.add(TemplateVersion(template_id=tmpl.id, version=1, active=True, **content))

    db.commit()
    item = _catalog_item(db, tmpl, locale)
    if item is None:
        raise NotFound("Template not found after creation.")
    return item


def delete_custom_template(db: Session, user_id: uuid.UUID, template_id: uuid.UUID) -> None:
    tmpl = db.get(Template, template_id)
    if tmpl is None or tmpl.owner_user_id != user_id:
        # Don't reveal whether a system/other-user template exists.
        raise NotFound("Custom template not found.")
    db.delete(tmpl)
    db.commit()


def build_request_plan_snapshot(
    *,
    template: Template,
    version: TemplateVersion,
    channel: str,
    locale: str,
    first_name: str | None,
    service_identity_value: str | None,
    service_identity_type: str | None,
    target_phone_number_id: str,
) -> dict:
    """Resolved snapshot stored on the request; makes history reproducible."""
    ctx = rendering.build_context(
        locale=locale, caller_persona=template.caller_persona, reason_code=template.reason_code,
        first_name=first_name,
    )
    snapshot = {
        "template_code": template.code,
        "template_version": version.version,
        "locale": locale,
        "channel": channel,
        "caller_persona": template.caller_persona,
        "reason_code": template.reason_code,
        "allowed_followup_facts": version.call_followup_facts_json or [],
        "service_identity_value": service_identity_value,
        "service_identity_type": service_identity_type,
        "target_phone_number_id": target_phone_number_id,
    }
    if channel == Channel.call.value:
        snapshot.update(
            {
                "rendered_opening_line": rendering.render(version.call_opening_line_template, ctx),
                "call_system_prompt": rendering.render(version.call_system_prompt_template, ctx),
                "voice_profile_code": version.call_voice_profile_code,
                "max_duration_seconds": version.call_max_duration_seconds,
                "supports_interruptions": version.call_supports_interruptions,
            }
        )
    else:
        snapshot.update(
            {
                "rendered_sms_body": rendering.render(version.sms_body_template, ctx),
                "sms_sender_style": version.sms_sender_style,
            }
        )
    return snapshot
