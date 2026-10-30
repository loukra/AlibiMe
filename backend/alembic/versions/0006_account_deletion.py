"""free allowance claims, so account deletion can't farm starter credits

Revision ID: 0006_account_deletion
Revises: 0005_template_extension
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_account_deletion"
down_revision = "0005_template_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "free_allowance_claims" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "free_allowance_claims",
            sa.Column("phone_hash", sa.String(length=64), primary_key=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("free_allowance_claims")
