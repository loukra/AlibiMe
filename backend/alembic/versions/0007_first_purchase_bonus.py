"""first-purchase bonus claims

Revision ID: 0007_first_purchase_bonus
Revises: 0006_account_deletion
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_first_purchase_bonus"
down_revision = "0006_account_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "first_purchase_bonus_claims" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "first_purchase_bonus_claims",
            sa.Column("phone_hash", sa.String(length=64), primary_key=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("first_purchase_bonus_claims")
