"""custom templates (ownership)

Adds ``templates.owner_user_id`` so a template can be a user's custom template
(NULL = built-in/system). Custom templates reuse the existing Template +
TemplateVersion model; content is composed server-side from approved skeletons.

Idempotent like prior migrations: only adds the column if missing, so it is safe
on fresh and already-deployed databases.

Revision ID: 0004_custom_templates
Revises: 0003_credit_packages
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_custom_templates"
down_revision = "0003_credit_packages"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "owner_user_id" not in _columns("templates"):
        # SQLite can't ALTER ADD COLUMN with an inline FK; add a plain column
        # there (fresh SQLite DBs get the FK via create_all in the 0001 baseline)
        # and keep the real FK on Postgres.
        fk = [] if op.get_bind().dialect.name == "sqlite" else [
            sa.ForeignKey("users.id", ondelete="CASCADE")
        ]
        op.add_column("templates", sa.Column("owner_user_id", sa.Uuid(), *fk, nullable=True))
        op.create_index("ix_templates_owner_user_id", "templates", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_templates_owner_user_id", table_name="templates")
    with op.batch_alter_table("templates") as batch:
        batch.drop_column("owner_user_id")
