from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_fk, uuid_pk


class UserContextProfile(Base):
    """Reusable, structured, *optional* facts about the user's own life context
    (work, home, family, relationship, transition) that let the composer pick
    more believable wording without the user re-entering it per template.

    Every field is nullable: the row may not exist, or exist mostly empty. This
    is separate from caller persona (who contacts the user) and sender identity.
    All values are safe coded options, never free-form provider text.
    """

    __tablename__ = "user_context_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Work
    work_industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_role_level_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_setting_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_schedule_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_travel_scope_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Home
    living_setup_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    home_responsibility_codes_json: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    dependent_context_codes_json: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)

    # Family / care
    family_support_level_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    family_proximity_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Relationship / privacy
    relationship_visibility_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    relationship_stage_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    privacy_preference_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Transition / travel
    transition_state_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transition_horizon_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)
