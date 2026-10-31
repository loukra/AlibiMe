"""a first name picked from a fixed list

The typed display name is gone (0010). A caller may still say the user's
first name, but only one picked from app/domain/users/first_names.txt.

Revision ID: 0011_user_first_name
Revises: 0010_drop_user_display_name
Create Date: 2026-10-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_user_first_name"
down_revision = "0010_drop_user_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "first_name" in columns:
        return
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("first_name", sa.String(40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("first_name")
