"""Lease and durable command receipts for inert instance control."""

from alembic import op

revision = "0003_instance_lifecycle"
down_revision = "0002_local_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE supervisor_lease (
            id smallint PRIMARY KEY CHECK (id = 1),
            owner uuid,
            epoch bigint NOT NULL DEFAULT 0 CHECK (epoch >= 0),
            expires_at timestamptz
        )
    """)
    op.execute("INSERT INTO supervisor_lease (id) VALUES (1)")
    op.execute("""
        CREATE TABLE instance_command (
            command_id uuid PRIMARY KEY,
            kind text NOT NULL CHECK (kind IN ('OPEN', 'SHUTDOWN', 'FINALIZE')),
            expected_generation bigint NOT NULL CHECK (expected_generation >= 0),
            result_generation bigint NOT NULL CHECK (result_generation >= 0),
            owner_epoch bigint NOT NULL CHECK (owner_epoch >= 0)
        )
    """)


def downgrade() -> None:
    raise RuntimeError("Lifecycle authority is durable; restore a reviewed backup instead")
