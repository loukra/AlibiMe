from __future__ import annotations

from pydantic import BaseModel


class ContextProfileBody(BaseModel):
    """User-context profile — every field optional. Omitted fields are left
    unchanged; explicit null clears a field."""

    model_config = {"extra": "ignore"}

    work_industry_code: str | None = None
    work_role_level_code: str | None = None
    work_setting_code: str | None = None
    work_schedule_code: str | None = None
    work_travel_scope_code: str | None = None
    living_setup_code: str | None = None
    home_responsibility_codes_json: list[str] | None = None
    dependent_context_codes_json: list[str] | None = None
    family_support_level_code: str | None = None
    family_proximity_code: str | None = None
    relationship_visibility_code: str | None = None
    relationship_stage_code: str | None = None
    privacy_preference_code: str | None = None
    transition_state_code: str | None = None
    transition_horizon_code: str | None = None


class ContextProfileOut(ContextProfileBody):
    """Full profile state (all fields, null where unset)."""
