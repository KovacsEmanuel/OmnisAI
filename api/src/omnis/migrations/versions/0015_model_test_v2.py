"""Add owned system operations and append-only model dispatch V2; never rewrite V1."""

from alembic import op

revision = "0015_model_test_v2"
down_revision = "0014_provider_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.model_record_v2 (
        instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
        id uuid NOT NULL,
        kind text NOT NULL,
        revision bigint NOT NULL CHECK (revision = 1),
        digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(instance_id,id), UNIQUE(instance_id,kind,id,revision,digest)
    );
    CREATE TABLE public.system_operation (
        schema_version smallint NOT NULL CHECK (schema_version = 1),
        instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
        operation_id uuid NOT NULL,
        command_id uuid NOT NULL CHECK (command_id = operation_id),
        payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
        config_snapshot_ref jsonb NOT NULL,
        input_projection_ref jsonb NOT NULL,
        purpose text NOT NULL CHECK (purpose = 'SETTINGS_TEST'),
        execution_owner_id uuid NOT NULL,
        generation bigint NOT NULL CHECK (generation >= 0),
        owner_epoch bigint NOT NULL CHECK (owner_epoch >= 1),
        cancel_epoch bigint NOT NULL CHECK (cancel_epoch >= 1),
        deadline timestamptz NOT NULL,
        state_revision bigint NOT NULL CHECK (state_revision >= 1),
        state text NOT NULL CHECK (state IN ('PENDING','RUNNING','STOPPING','FINISHED','NEEDS_RECONCILIATION')),
        finish_reason text CHECK (finish_reason IN ('COMPLETED','FAILED','CANCELLED','DEADLINE','OWNER_LOST')),
        outcome_ref jsonb,
        PRIMARY KEY(instance_id,operation_id), UNIQUE(instance_id,command_id)
    );
    CREATE UNIQUE INDEX model_test_one_active ON public.system_operation(instance_id)
        WHERE state <> 'FINISHED';
    CREATE TABLE public.model_command_v2 (
        instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
        command_id uuid NOT NULL,
        request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
        operation_id uuid,
        action text NOT NULL CHECK (action IN ('start','cancel','refresh')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(instance_id,command_id)
    );
    CREATE TABLE public.model_dispatch_v2 (
        instance_id uuid NOT NULL,
        dispatch_attempt_id uuid NOT NULL,
        operation_id uuid NOT NULL,
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        PRIMARY KEY(instance_id,dispatch_attempt_id), UNIQUE(instance_id,operation_id),
        FOREIGN KEY(instance_id,operation_id) REFERENCES public.system_operation(instance_id,operation_id)
    );
    CREATE TABLE public.model_dispatch_event_v2 (
        instance_id uuid NOT NULL,
        dispatch_attempt_id uuid NOT NULL,
        sequence smallint NOT NULL CHECK (sequence BETWEEN 1 AND 3),
        state text NOT NULL CHECK (state IN ('RESERVED','SENT','SETTLED','RELEASED')),
        receipt_ref jsonb,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(instance_id,dispatch_attempt_id,sequence),
        UNIQUE(instance_id,dispatch_attempt_id,state),
        FOREIGN KEY(instance_id,dispatch_attempt_id) REFERENCES public.model_dispatch_v2(instance_id,dispatch_attempt_id)
    );
    CREATE TABLE public.system_operation_event (
        instance_id uuid NOT NULL,
        operation_id uuid NOT NULL,
        state_revision bigint NOT NULL CHECK (state_revision >= 1),
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        PRIMARY KEY(instance_id,operation_id,state_revision),
        FOREIGN KEY(instance_id,operation_id) REFERENCES public.system_operation(instance_id,operation_id)
    );
    CREATE FUNCTION public.model_v2_immutable() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'model V2 history is immutable'; END;$$;
    CREATE TRIGGER model_v2_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON public.model_record_v2
        FOR EACH STATEMENT EXECUTE FUNCTION public.model_v2_immutable();
    CREATE TRIGGER model_v2_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON public.model_command_v2
        FOR EACH STATEMENT EXECUTE FUNCTION public.model_v2_immutable();
    CREATE TRIGGER model_v2_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON public.model_dispatch_v2
        FOR EACH STATEMENT EXECUTE FUNCTION public.model_v2_immutable();
    CREATE TRIGGER model_v2_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON public.model_dispatch_event_v2
        FOR EACH STATEMENT EXECUTE FUNCTION public.model_v2_immutable();
    CREATE TRIGGER model_v2_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON public.system_operation_event
        FOR EACH STATEMENT EXECUTE FUNCTION public.model_v2_immutable();
    """)


def downgrade() -> None:
    raise RuntimeError("Model history requires reviewed backup restoration")
