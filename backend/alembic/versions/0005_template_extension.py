"""template model extension + user context profile

Adds richer structured shared-core fields to ``templates`` and a new
``user_context_profiles`` table (reusable, optional, all-nullable user context).
Additive and idempotent like prior migrations.

Revision ID: 0005_template_extension
Revises: 0004_custom_templates
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_template_extension"
down_revision = "0004_custom_templates"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


_TEMPLATE_COLUMNS = [
    ("urgency_code", sa.String(length=24)),
    ("outcome_code", sa.String(length=32)),
    ("setting_code", sa.String(length=32)),
    ("tone_code", sa.String(length=24)),
    ("detail_profile_code", sa.String(length=24)),
    ("discretion_level_code", sa.String(length=24)),
    ("formality_code", sa.String(length=24)),
    ("expected_response_code", sa.String(length=32)),
    ("followup_behavior_code", sa.String(length=32)),
    ("continuity_scope_code", sa.String(length=24)),
    ("context_modules_json", sa.JSON()),
]


def upgrade() -> None:
    for name, type_ in _TEMPLATE_COLUMNS:
        _add_column_if_missing("templates", sa.Column(name, type_, nullable=True))

    if "user_context_profiles" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "user_context_profiles",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False, unique=True,
            ),
            sa.Column("work_industry_code", sa.String(length=32), nullable=True),
            sa.Column("work_role_level_code", sa.String(length=32), nullable=True),
            sa.Column("work_setting_code", sa.String(length=32), nullable=True),
            sa.Column("work_schedule_code", sa.String(length=32), nullable=True),
            sa.Column("work_travel_scope_code", sa.String(length=32), nullable=True),
            sa.Column("living_setup_code", sa.String(length=32), nullable=True),
            sa.Column("home_responsibility_codes_json", sa.JSON(), nullable=True),
            sa.Column("dependent_context_codes_json", sa.JSON(), nullable=True),
            sa.Column("family_support_level_code", sa.String(length=32), nullable=True),
            sa.Column("family_proximity_code", sa.String(length=32), nullable=True),
            sa.Column("relationship_visibility_code", sa.String(length=32), nullable=True),
            sa.Column("relationship_stage_code", sa.String(length=32), nullable=True),
            sa.Column("privacy_preference_code", sa.String(length=32), nullable=True),
            sa.Column("transition_state_code", sa.String(length=32), nullable=True),
            sa.Column("transition_horizon_code", sa.String(length=32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_user_context_profiles_user_id", "user_context_profiles", ["user_id"]
        )


def downgrade() -> None:
    op.drop_table("user_context_profiles")
    with op.batch_alter_table("templates") as batch:
        for name, _ in reversed(_TEMPLATE_COLUMNS):
            batch.drop_column(name)
