"""Persist pairing issuance identity so retries cannot mint the same code twice."""

from alembic import op

revision = "0004_pairing_receipts"
down_revision = "0003_instance_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE pairing_issuance (
            issuance_id uuid PRIMARY KEY,
            digest text NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL
        )
    """)
    # Pre-receipt pending codes have no trustworthy issuance identity. Re-pair explicitly.
    op.execute("UPDATE pairing_challenge SET digest = NULL, expires_at = NULL WHERE id = 1")


def downgrade() -> None:
    raise RuntimeError("Pairing receipts are durable; restore a reviewed backup instead")
