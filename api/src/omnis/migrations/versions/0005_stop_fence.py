"""One non-expiring Stop grant, distinct from the supervisor heartbeat lease."""

from alembic import op

revision = "0005_stop_fence"
down_revision = "0004_pairing_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # An absent row means no Stop grant. id=1 permits at most one command; no
    # expiry column or TTL is allowed because a submitted host effect can be late.
    op.execute("""
        CREATE TABLE instance_stop_fence (
            id smallint PRIMARY KEY CHECK (id = 1),
            instance_id uuid NOT NULL,
            command_id uuid NOT NULL,
            finalize_command_id uuid NOT NULL,
            generation bigint NOT NULL CHECK (generation >= 0),
            owner_epoch bigint NOT NULL CHECK (owner_epoch > 0),
            daemon_id text NOT NULL CHECK (daemon_id <> ''),
            inventory jsonb NOT NULL CHECK (
                jsonb_typeof(inventory) = 'object' AND inventory <> '{}'::jsonb
            ),
            state text NOT NULL CHECK (state IN ('STOP_PENDING', 'STOP_UNCERTAIN'))
        )
    """)


def downgrade() -> None:
    raise RuntimeError("A Stop grant cannot be dropped without verified external recovery")
