"""First inert engagement draft and immutable revision authority."""

from alembic import op

revision = "0007_engagement_drafts"
down_revision = "0006_stop_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE engagement (
            id uuid PRIMARY KEY,
            current_revision integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT ck_engagement_revision CHECK (current_revision >= 1)
        )
    """)
    op.execute("""
        CREATE TABLE engagement_revision (
            id uuid PRIMARY KEY,
            engagement_id uuid NOT NULL,
            revision integer NOT NULL,
            schema_version smallint NOT NULL,
            kind text NOT NULL,
            digest text NOT NULL,
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT fk_revision_engagement FOREIGN KEY (engagement_id)
                REFERENCES engagement(id),
            CONSTRAINT uq_engagement_revision_order UNIQUE (engagement_id, revision),
            CONSTRAINT ck_revision_number CHECK (revision >= 1),
            CONSTRAINT ck_revision_schema CHECK (schema_version = 1),
            CONSTRAINT ck_revision_kind CHECK (kind = 'engagement-revision'),
            CONSTRAINT ck_revision_digest CHECK (digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_revision_payload CHECK (jsonb_typeof(payload) = 'object')
        )
    """)
    op.execute("""
        ALTER TABLE engagement ADD CONSTRAINT fk_engagement_current_revision
        FOREIGN KEY (id, current_revision)
        REFERENCES engagement_revision(engagement_id, revision)
        DEFERRABLE INITIALLY DEFERRED
    """)
    op.execute("""
        CREATE FUNCTION reject_engagement_revision_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'Engagement revisions are immutable';
        END;$$
    """)
    op.execute("""
        CREATE TRIGGER engagement_revision_immutable
        BEFORE UPDATE OR DELETE OR TRUNCATE ON engagement_revision
        FOR EACH STATEMENT EXECUTE FUNCTION reject_engagement_revision_mutation()
    """)


def downgrade() -> None:
    raise RuntimeError("Engagement revisions are durable; restore a reviewed backup instead")
