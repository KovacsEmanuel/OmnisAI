"""Bind Stop grants to their issuer and retain append-only reconciliation receipts."""

from alembic import op

revision = "0006_stop_reconciliation"
down_revision = "0005_stop_fence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Never guess the owner of an existing grant after lease release. Legacy NULL
    # grants remain fenced and cannot be reconciled by this version of the job.
    op.execute("ALTER TABLE instance_stop_fence ADD COLUMN owner_uuid uuid")
    op.execute("""
        CREATE TABLE instance_stop_reconciliation (
            reconciliation_id uuid PRIMARY KEY,
            system_identifier text NOT NULL,
            "grant" jsonb NOT NULL,
            completion_sha256 text NOT NULL
        )
    """)
    op.execute("""
        CREATE FUNCTION reject_stop_reconciliation_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'Stop reconciliation receipts are immutable';
        END;$$
    """)
    op.execute("""
        CREATE TRIGGER stop_reconciliation_immutable
        BEFORE UPDATE OR DELETE OR TRUNCATE ON instance_stop_reconciliation
        FOR EACH STATEMENT EXECUTE FUNCTION reject_stop_reconciliation_mutation()
    """)


def downgrade() -> None:
    raise RuntimeError("Stop reconciliation history cannot be removed by downgrade")
