"""credit packages (add credits feature)

Adds the catalog/fulfillment metadata to ``plans`` and a ``credit_package_claims``
audit table backing the user-facing Add Credits flow. Credit packs reuse the
existing ``plans`` + ``credit_ledger`` architecture.

Idempotent on purpose (like 0002): only adds what is missing, so it is safe on
both fresh databases (built by the 0001 baseline's create_all) and already-
deployed ones.

Revision ID: 0003_credit_packages
Revises: 0002_sender_identity
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_credit_packages"
down_revision = "0002_sender_identity"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set[str]:
    insp = _inspector()
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    # plans: catalog / fulfillment metadata.
    _add_column_if_missing("plans", sa.Column("display_name", sa.String(length=64), nullable=True))
    _add_column_if_missing("plans", sa.Column("badge_text", sa.String(length=32), nullable=True))
    _add_column_if_missing(
        "plans",
        sa.Column(
            "fulfillment_mode",
            sa.String(length=24),
            nullable=False,
            server_default="free_dev",
        ),
    )
    _add_column_if_missing(
        "plans",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("plans", sa.Column("price_minor", sa.Integer(), nullable=True))
    _add_column_if_missing("plans", sa.Column("currency_code", sa.String(length=3), nullable=True))

    # credit_package_claims: audit trail + idempotency for acquisitions.
    if "credit_package_claims" not in _inspector().get_table_names():
        op.create_table(
            "credit_package_claims",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("plans.id"), nullable=True),
            sa.Column("plan_code", sa.String(length=48), nullable=False),
            sa.Column("credits_granted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "fulfillment_mode",
                sa.String(length=24),
                nullable=False,
                server_default="free_dev",
            ),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("client_request_id", sa.String(length=128), nullable=False),
            sa.Column("store_transaction_id", sa.String(length=128), nullable=True),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failure_reason", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "user_id", "client_request_id", name="uq_claim_user_client_request"
            ),
        )
        op.create_index(
            "ix_credit_package_claims_user_id", "credit_package_claims", ["user_id"]
        )


def downgrade() -> None:
    op.drop_table("credit_package_claims")
    with op.batch_alter_table("plans") as batch:
        for col in (
            "currency_code",
            "price_minor",
            "sort_order",
            "fulfillment_mode",
            "badge_text",
            "display_name",
        ):
            batch.drop_column(col)
