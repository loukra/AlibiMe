"""per-locale names for built-in templates

A built-in's name and description now live on each locale's version, so a
German account sees "Chef: dringender Reiseauftrag". Own alibis keep the name
on the template.

Revision ID: 0009_template_version_names
Revises: 0008_template_overrides
Create Date: 2026-10-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_template_version_names"
down_revision = "0008_template_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("template_versions")}
    if "display_name" in columns:
        return
    with op.batch_alter_table("template_versions") as batch:
        batch.add_column(sa.Column("display_name", sa.String(120), nullable=True))
        batch.add_column(sa.Column("description", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("template_versions") as batch:
        batch.drop_column("description")
        batch.drop_column("display_name")
