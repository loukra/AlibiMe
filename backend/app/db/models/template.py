from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.db.base import Base, uuid_fk, uuid_pk


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    caller_persona: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ownership: NULL = built-in/system template; set = a user's custom template.
    # Custom templates reuse the same shared core + per-channel version model.
    owner_user_id: Mapped[uuid.UUID | None] = uuid_fk(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Sender identity, keyed by persona (not by template id) so different
    # templates from the same persona reuse one sender binding. Defaults derive
    # from caller_persona/display_name at seed time.
    sender_persona_key: Mapped[str] = mapped_column(String(48), nullable=False)
    sender_display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    supports_contact_save: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    versions: Mapped[list["TemplateVersion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    __table_args__ = (
        # Exactly one active version per (template, locale) is enforced in code;
        # this guards against duplicate (template, locale, version) rows.
        UniqueConstraint("template_id", "locale", "version", name="uq_template_locale_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    template_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    supports_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_sms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Call content
    call_system_prompt_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    call_opening_line_template: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    call_followup_facts_json: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    call_voice_profile_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    call_max_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    call_supports_interruptions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # SMS content
    sms_body_template: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sms_followup_body_template: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sms_sender_style: Mapped[str | None] = mapped_column(String(48), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    template: Mapped["Template"] = relationship(back_populates="versions")
