"""edited copies of built-in templates

A user's edit of a built-in template is stored as their own template that
points at the original (``overrides_template_id``); deleting it resets.

Revision ID: 0008_template_overrides
Revises: 0007_first_purchase_bonus
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_template_overrides"
down_revision = "0007_first_purchase_bonus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("templates")}
    if "overrides_template_id" in columns:
        return
    with op.batch_alter_table("templates") as batch:
        batch.add_column(sa.Column("overrides_template_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_templates_overrides_template_id",
            "templates",
            ["overrides_template_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_templates_overrides_template_id", ["overrides_template_id"])


def downgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.drop_index("ix_templates_overrides_template_id")
        batch.drop_constraint("fk_templates_overrides_template_id", type_="foreignkey")
        batch.drop_column("overrides_template_id")
