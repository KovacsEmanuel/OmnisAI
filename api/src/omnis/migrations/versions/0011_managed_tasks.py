"""Managed task lifecycle, deliberately separate from the catalog ledger."""

from alembic import op

revision = "0011_managed_tasks"
down_revision = "0010_catalog_publications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE managed_record (
            id uuid PRIMARY KEY, owner_id uuid NOT NULL, run_id uuid NOT NULL,
            envelope jsonb NOT NULL CHECK (jsonb_typeof(envelope) = 'object'),
            CHECK ((envelope->>'id')::uuid = id),
            CHECK (envelope->>'schema_version' = '1'),
            CHECK (envelope->>'revision' = '1')
        );
        CREATE INDEX managed_record_run ON managed_record(owner_id, run_id);
        CREATE FUNCTION managed_record_immutable() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'managed records are immutable';
        END;$$;
        CREATE TRIGGER managed_record_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON managed_record
            FOR EACH STATEMENT EXECUTE FUNCTION managed_record_immutable();
        CREATE TABLE managed_run (
            run_id uuid PRIMARY KEY REFERENCES managed_record(id), owner_id uuid NOT NULL,
            command_id uuid NOT NULL, request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
            manifest_id uuid NOT NULL UNIQUE REFERENCES managed_record(id),
            binding_id uuid UNIQUE REFERENCES managed_record(id),
            final_id uuid UNIQUE REFERENCES managed_record(id),
            stage_started boolean NOT NULL DEFAULT false, release_started boolean NOT NULL DEFAULT false,
            runtime_boot uuid, ticket uuid, native_root_id text,
            UNIQUE(owner_id, command_id), UNIQUE(runtime_boot, ticket), UNIQUE(runtime_boot, native_root_id),
            CHECK (NOT release_started OR binding_id IS NOT NULL),
            CHECK (final_id IS NULL OR release_started),
            CHECK ((binding_id IS NULL) = (runtime_boot IS NULL)),
            CHECK ((binding_id IS NULL) = (ticket IS NULL)),
            CHECK ((binding_id IS NULL) = (native_root_id IS NULL))
        );
        CREATE TABLE managed_task (
            task_id uuid PRIMARY KEY, attempt_id uuid NOT NULL UNIQUE,
            run_id uuid NOT NULL REFERENCES managed_run(run_id), batch_index integer NOT NULL CHECK (batch_index BETWEEN 0 AND 1),
            brief_id uuid NOT NULL UNIQUE REFERENCES managed_record(id),
            result_id uuid UNIQUE REFERENCES managed_record(id), check_id uuid UNIQUE REFERENCES managed_record(id),
            state text NOT NULL CHECK (state IN ('QUEUED','BOUND','BLOCKED')),
            runtime_boot uuid, native_child_id text, native_session_id text,
            UNIQUE(run_id, batch_index), UNIQUE(runtime_boot, native_child_id), UNIQUE(runtime_boot, native_session_id),
            CHECK (check_id IS NULL OR result_id IS NOT NULL)
        );
        CREATE TABLE managed_inbox (
            result_id uuid PRIMARY KEY REFERENCES managed_record(id),
            task_id uuid NOT NULL UNIQUE REFERENCES managed_task(task_id),
            delivered boolean NOT NULL, admitted boolean NOT NULL,
            turn_completed boolean NOT NULL, domain_result_consumed boolean NOT NULL,
            disposition text NOT NULL CHECK (disposition IN ('RECEIVED','HELD_FOR_RECONCILIATION')),
            CHECK (delivered AND NOT admitted AND NOT turn_completed)
        )
    """)


def downgrade() -> None:
    raise RuntimeError("Managed task history requires reviewed backup restoration")
