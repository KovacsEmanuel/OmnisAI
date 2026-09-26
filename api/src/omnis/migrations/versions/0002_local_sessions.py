"""Durable one-use pairing and opaque UI sessions."""

from alembic import op

revision = "0002_local_sessions"
down_revision = "0001_instance_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE pairing_challenge (
            id smallint PRIMARY KEY CHECK (id = 1),
            digest text,
            expires_at timestamptz,
            window_started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0)
        )
    """)
    op.execute("INSERT INTO pairing_challenge (id) VALUES (1)")
    op.execute("""
        CREATE TABLE ui_session (
            token_digest text PRIMARY KEY,
            expires_at timestamptz NOT NULL
        )
    """)


def downgrade() -> None:
    raise RuntimeError("Session authority is durable; restore a reviewed backup instead")
