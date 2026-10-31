"""drop the user's display name

The name was typed freely and went into the call prompt. Nothing a user types
may reach the model, and the name had no other use, so it is gone, along with
any names already stored.

Revision ID: 0010_drop_user_display_name
Revises: 0009_template_version_names
Create Date: 2026-10-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_drop_user_display_name"
down_revision = "0009_template_version_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "display_name" not in columns:
        return
    with op.batch_alter_table("users") as batch:
        batch.drop_column("display_name")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("display_name", sa.String(120), nullable=True))
