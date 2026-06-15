"""Reusable, optional user-context profile (work/home/family/relationship/
transition). One row per user; every field nullable. Used by the composer to add
safe, generic anchors and edited from the Profile tab. Missing data is normal
and must never be treated as an error."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.db.models.user_context_profile import UserContextProfile
from app.domain.templates import catalogs

# Scalar code field -> the allow-list it must belong to (when set).
_SCALAR_FIELDS = {
    "work_industry_code": catalogs.WORK_INDUSTRIES,
    "work_role_level_code": catalogs.WORK_ROLE_LEVELS,
    "work_setting_code": catalogs.WORK_SETTINGS,
    "work_schedule_code": catalogs.WORK_SCHEDULES,
    "work_travel_scope_code": catalogs.WORK_TRAVEL_SCOPES,
    "living_setup_code": catalogs.LIVING_SETUPS,
    "family_support_level_code": catalogs.FAMILY_SUPPORT_LEVELS,
    "family_proximity_code": catalogs.FAMILY_PROXIMITIES,
    "relationship_visibility_code": catalogs.RELATIONSHIP_VISIBILITIES,
    "relationship_stage_code": catalogs.RELATIONSHIP_STAGES,
    "privacy_preference_code": catalogs.PRIVACY_PREFERENCES,
    "transition_state_code": catalogs.TRANSITION_STATES,
    "transition_horizon_code": catalogs.TRANSITION_HORIZONS,
}
_MULTI_FIELDS = {
    "home_responsibility_codes_json": catalogs.HOME_RESPONSIBILITIES,
    "dependent_context_codes_json": catalogs.DEPENDENT_CONTEXTS,
}

ALL_FIELDS = list(_SCALAR_FIELDS) + list(_MULTI_FIELDS)


def get_profile(db: Session, user_id: uuid.UUID) -> UserContextProfile | None:
    return db.execute(
        select(UserContextProfile).where(UserContextProfile.user_id == user_id)
    ).scalar_one_or_none()


def profile_to_dict(profile: UserContextProfile | None) -> dict:
    """All fields (None where unset), for the API response."""
    if profile is None:
        return {f: None for f in ALL_FIELDS}
    return {f: getattr(profile, f) for f in ALL_FIELDS}


def context_dict(db: Session, user_id: uuid.UUID) -> dict:
    """Only the *present* fields, for the composer."""
    return {k: v for k, v in profile_to_dict(get_profile(db, user_id)).items() if v}


def upsert_profile(db: Session, user_id: uuid.UUID, values: dict) -> UserContextProfile:
    """Validate and write the user's context profile. Unknown keys are ignored;
    None clears a field; every field is optional."""
    clean: dict = {}
    for field, allowed in _SCALAR_FIELDS.items():
        if field in values:
            val = values[field]
            if val is not None and val not in allowed:
                raise ValidationFailed(f"Invalid value for {field}.")
            clean[field] = val
    for field, allowed in _MULTI_FIELDS.items():
        if field in values:
            val = values[field]
            if val is None:
                clean[field] = None
            else:
                if not isinstance(val, list) or any(v not in allowed for v in val):
                    raise ValidationFailed(f"Invalid value for {field}.")
                clean[field] = val

    profile = get_profile(db, user_id)
    if profile is None:
        profile = UserContextProfile(user_id=user_id)
        db.add(profile)
    for field, val in clean.items():
        setattr(profile, field, val)
    db.commit()
    db.refresh(profile)
    return profile
