"""Template catalog, version resolution, content rendering, and snapshotting."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, TemplateChannelNotSupported
from app.db.models.enums import Channel
from app.db.models.template import Template, TemplateVersion
from app.domain.templates import rendering

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


def list_catalog(db: Session, locale: str) -> list[dict]:
    templates = db.execute(
        select(Template).where(Template.active.is_(True)).order_by(Template.code)
    ).scalars().all()
    catalog = []
    for tmpl in templates:
        try:
            version = resolve_version(db, tmpl.id, locale)
        except NotFound:
            continue
        ctx = rendering.build_context(
            locale=locale, caller_persona=tmpl.caller_persona, reason_code=tmpl.reason_code
        )
        catalog.append(
            {
                "id": str(tmpl.id),
                "code": tmpl.code,
                "display_name": tmpl.display_name,
                "description": tmpl.description,
                "category": tmpl.category,
                "caller_persona": tmpl.caller_persona,
                "reason_code": tmpl.reason_code,
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
        )
    return catalog


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
