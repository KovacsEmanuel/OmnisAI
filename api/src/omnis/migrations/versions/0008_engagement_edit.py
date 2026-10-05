"""Bind each accepted draft edit command to exactly one immutable revision."""

from alembic import op

revision = "0008_engagement_edit"
down_revision = "0007_engagement_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE engagement_revision ADD COLUMN command_id uuid
    """)
    op.execute("""
        ALTER TABLE engagement_revision ADD CONSTRAINT ck_revision_command
        CHECK ((revision = 1 AND command_id IS NULL) OR
               (revision > 1 AND command_id IS NOT NULL))
    """)
    op.execute("""
        ALTER TABLE engagement_revision ADD CONSTRAINT uq_revision_command
        UNIQUE (engagement_id, command_id)
    """)


def downgrade() -> None:
    raise RuntimeError("Engagement edit receipts are durable; restore a reviewed backup instead")
