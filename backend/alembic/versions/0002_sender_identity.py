"""sender identity + save-contact feature

Adds the stable sender-identity model:
  - ``service_identities`` gains Twilio/Vapi sender handles + an internal label
    (the table doubles as the spec's "sender lines" pool).
  - ``templates`` gain persona fields that key sender bindings.
  - new ``user_sender_bindings`` table (the core stable mapping).
  - ``requests`` gain a sender-binding ref + an immutable sender snapshot.

Idempotent on purpose: the baseline 0001 migration builds the schema from live
metadata via ``create_all``, so a fresh DB already has these columns/table. This
migration therefore only adds what is missing, so it is safe on both fresh and
already-deployed databases.

Revision ID: 0002_sender_identity
Revises: 0001_initial
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_sender_identity"
down_revision = "0001_initial"
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
    # service_identities: sender-line infrastructure handles.
    _add_column_if_missing(
        "service_identities",
        sa.Column("twilio_messaging_service_sid", sa.String(length=64), nullable=True),
    )
    _add_column_if_missing(
        "service_identities",
        sa.Column("vapi_phone_number_id", sa.String(length=64), nullable=True),
    )
    _add_column_if_missing(
        "service_identities",
        sa.Column("display_label", sa.String(length=64), nullable=True),
    )

    # templates: persona fields (added nullable + backfilled for existing rows).
    if "templates" in _inspector().get_table_names():
        _add_column_if_missing(
            "templates", sa.Column("sender_persona_key", sa.String(length=48), nullable=True)
        )
        _add_column_if_missing(
            "templates", sa.Column("sender_display_name", sa.String(length=120), nullable=True)
        )
        _add_column_if_missing(
            "templates",
            sa.Column(
                "supports_contact_save", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
        )
        # Backfill unconditionally (NULL-only) so a partially-applied run repairs.
        op.execute(
            "UPDATE templates SET sender_persona_key = caller_persona "
            "WHERE sender_persona_key IS NULL"
        )
        op.execute(
            "UPDATE templates SET sender_display_name = display_name "
            "WHERE sender_display_name IS NULL"
        )

    # user_sender_bindings: the new core table.
    if "user_sender_bindings" not in _inspector().get_table_names():
        op.create_table(
            "user_sender_bindings",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sender_persona_key", sa.String(length=48), nullable=False),
            sa.Column("channel", sa.String(length=8), nullable=False),
            sa.Column(
                "sender_line_id",
                sa.Uuid(),
                sa.ForeignKey("service_identities.id"),
                nullable=False,
            ),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("first_bound_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_from_template_id",
                sa.Uuid(),
                sa.ForeignKey("templates.id"),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "user_id",
                "sender_persona_key",
                "channel",
                name="uq_user_persona_channel",
            ),
        )
        op.create_index(
            "ix_user_sender_bindings_user_id", "user_sender_bindings", ["user_id"]
        )

    # requests: sender binding ref + immutable snapshot.
    # SQLite cannot ALTER TABLE ADD COLUMN with an inline FOREIGN KEY, so add a
    # plain column there (fresh SQLite DBs still get the FK via create_all in the
    # 0001 baseline); keep the real FK on Postgres.
    if "sender_binding_id" not in _columns("requests"):
        fk = [] if op.get_bind().dialect.name == "sqlite" else [
            sa.ForeignKey("user_sender_bindings.id")
        ]
        op.add_column(
            "requests", sa.Column("sender_binding_id", sa.Uuid(), *fk, nullable=True)
        )
    _add_column_if_missing(
        "requests", sa.Column("sender_persona_key", sa.String(length=48), nullable=True)
    )
    _add_column_if_missing(
        "requests",
        sa.Column("sender_display_name_snapshot", sa.String(length=120), nullable=True),
    )
    _add_column_if_missing(
        "requests",
        sa.Column("sender_phone_e164_snapshot", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("requests") as batch:
        for col in (
            "sender_phone_e164_snapshot",
            "sender_display_name_snapshot",
            "sender_persona_key",
            "sender_binding_id",
        ):
            batch.drop_column(col)
    op.drop_table("user_sender_bindings")
    with op.batch_alter_table("templates") as batch:
        for col in ("supports_contact_save", "sender_display_name", "sender_persona_key"):
            batch.drop_column(col)
    with op.batch_alter_table("service_identities") as batch:
        for col in ("display_label", "vapi_phone_number_id", "twilio_messaging_service_sid"):
            batch.drop_column(col)
