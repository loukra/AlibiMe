"""initial baseline schema

Creates the full MVP schema from the SQLAlchemy metadata. This baseline is
dialect-neutral (works on PostgreSQL and SQLite). Subsequent migrations should
be generated with ``alembic revision --autogenerate``.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-13
"""
from alembic import op

from app.db.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
