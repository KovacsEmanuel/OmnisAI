"""Owner/profile publication CAS head; immutable records remain in the ledger."""

from alembic import op

revision = "0010_catalog_publications"
down_revision = "0009_catalog_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE catalog_publication_head (
            owner_id uuid NOT NULL, profile_key text NOT NULL,
            generation bigint NOT NULL CHECK (generation >= 1),
            draft_id uuid NOT NULL REFERENCES catalog_record(id),
            publication_id uuid REFERENCES catalog_record(id),
            PRIMARY KEY (owner_id, profile_key)
        )
    """)


def downgrade() -> None:
    raise RuntimeError("Publication heads require a reviewed backup restore")
