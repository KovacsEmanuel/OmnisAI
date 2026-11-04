"""S1 owned RUN branch, additive to T1 and native history."""

from alembic import op

from omnis.core.run_schema import RUN_ROOT_GUARD, RUN_SETUP_GUARD

revision = "0019_agent_runs"
down_revision = "0018_model_relay_authority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE run_setup (
        instance_id uuid NOT NULL REFERENCES instance_control(instance_id),
        setup_id uuid NOT NULL,
        engagement_id uuid NOT NULL REFERENCES engagement(id),
        draft_id uuid NOT NULL REFERENCES engagement_revision(id),
        PRIMARY KEY(instance_id,setup_id),
        UNIQUE(instance_id,setup_id,engagement_id),
        FOREIGN KEY(instance_id,setup_id) REFERENCES model_record_v2(instance_id,id)
    );
    CREATE TABLE agent_run (
        instance_id uuid NOT NULL REFERENCES instance_control(instance_id),
        run_id uuid NOT NULL,
        engagement_id uuid NOT NULL REFERENCES engagement(id),
        setup_id uuid NOT NULL,
        revision bigint NOT NULL CHECK(revision > 0),
        generation bigint NOT NULL CHECK(generation >= 0),
        owner_id uuid NOT NULL,
        owner_epoch bigint NOT NULL CHECK(owner_epoch > 0),
        fence bigint NOT NULL CHECK(fence > 0),
        state text NOT NULL CHECK(state IN ('RUNNING','PAUSING','PAUSED','HOLD','STOPPING','STOPPED','COMPLETED','LIMITED','NEEDS_RECONCILIATION')),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        PRIMARY KEY(instance_id,run_id),
        UNIQUE(instance_id,run_id,engagement_id),
        FOREIGN KEY(instance_id,setup_id,engagement_id) REFERENCES run_setup(instance_id,setup_id,engagement_id),
        CHECK(payload->>'run_id'=run_id::text AND payload->>'instance_id'=instance_id::text AND payload->>'engagement_id'=engagement_id::text AND payload->>'state'=state AND (payload->>'revision')::bigint=revision)
    );
    CREATE UNIQUE INDEX agent_run_one_active ON agent_run(instance_id)
        WHERE state NOT IN ('STOPPED','COMPLETED','LIMITED');
    CREATE TABLE run_task (
        instance_id uuid NOT NULL,
        run_id uuid NOT NULL,
        task_id uuid NOT NULL,
        role text NOT NULL CHECK(role IN ('BRAIN','RECON')),
        parent_task_id uuid,
        PRIMARY KEY(instance_id,run_id,task_id),
        UNIQUE(instance_id,run_id,task_id,role),
        FOREIGN KEY(instance_id,run_id) REFERENCES agent_run(instance_id,run_id),
        FOREIGN KEY(instance_id,run_id,parent_task_id) REFERENCES run_task(instance_id,run_id,task_id)
    );
    CREATE TABLE run_attempt (
        instance_id uuid NOT NULL,
        run_id uuid NOT NULL,
        task_id uuid NOT NULL,
        attempt_id uuid NOT NULL,
        role text NOT NULL CHECK(role IN ('BRAIN','RECON')),
        state text NOT NULL CHECK(state IN ('RUNNING','SUCCEEDED','INCONCLUSIVE','FAILED','CANCELLED','NEEDS_RECONCILIATION')),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        PRIMARY KEY(instance_id,run_id,attempt_id),
        UNIQUE(instance_id,run_id,task_id,attempt_id),
        FOREIGN KEY(instance_id,run_id,task_id,role) REFERENCES run_task(instance_id,run_id,task_id,role),
        CHECK(payload->>'attempt_id'=attempt_id::text AND payload->>'task_id'=task_id::text AND payload->>'run_id'=run_id::text AND payload->>'role'=role AND payload->>'state'=state)
    );
    CREATE UNIQUE INDEX run_attempt_one_worker ON run_attempt(instance_id,run_id)
        WHERE role='RECON' AND state IN ('RUNNING','NEEDS_RECONCILIATION');
    CREATE TABLE run_dispatch (
        instance_id uuid NOT NULL,
        run_id uuid NOT NULL,
        task_id uuid NOT NULL,
        attempt_id uuid NOT NULL,
        dispatch_id uuid NOT NULL,
        projection_id uuid NOT NULL,
        relay_kind text NOT NULL DEFAULT 'MODEL_DISPATCH' CHECK(relay_kind='MODEL_DISPATCH'),
        state text NOT NULL CHECK(state IN ('RESERVED','SENT','SETTLED','RELEASED','UNKNOWN')),
        deadline timestamptz NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        PRIMARY KEY(instance_id,dispatch_id),
        FOREIGN KEY(instance_id,run_id,task_id,attempt_id) REFERENCES run_attempt(instance_id,run_id,task_id,attempt_id),
        FOREIGN KEY(instance_id,projection_id) REFERENCES model_record_v2(instance_id,id),
        FOREIGN KEY(instance_id,relay_kind,dispatch_id) REFERENCES model_relay_authority(instance_id,kind,id)
    );
    CREATE UNIQUE INDEX run_dispatch_one_active ON run_dispatch(instance_id)
        WHERE state IN ('RESERVED','SENT');
    CREATE TABLE run_dispatch_event (
        instance_id uuid NOT NULL,
        dispatch_id uuid NOT NULL,
        sequence smallint NOT NULL CHECK(sequence BETWEEN 1 AND 3),
        state text NOT NULL CHECK(state IN ('RESERVED','SENT','SETTLED','RELEASED','UNKNOWN')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(instance_id,dispatch_id,sequence),
        UNIQUE(instance_id,dispatch_id,state),
        FOREIGN KEY(instance_id,dispatch_id) REFERENCES run_dispatch(instance_id,dispatch_id)
    );
    CREATE TABLE run_inbox (
        instance_id uuid NOT NULL,
        run_id uuid NOT NULL,
        result_id uuid NOT NULL,
        consumed_decision_id uuid,
        held boolean NOT NULL,
        PRIMARY KEY(instance_id,run_id,result_id),
        FOREIGN KEY(instance_id,run_id) REFERENCES agent_run(instance_id,run_id),
        FOREIGN KEY(instance_id,result_id) REFERENCES model_record_v2(instance_id,id),
        FOREIGN KEY(instance_id,consumed_decision_id) REFERENCES model_record_v2(instance_id,id)
    );
    CREATE TABLE run_question (
        instance_id uuid NOT NULL,
        run_id uuid NOT NULL,
        task_id uuid NOT NULL,
        question_id uuid NOT NULL,
        state text NOT NULL CHECK(state IN ('PENDING','ANSWER_ADMITTED','CONSUMED')),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        PRIMARY KEY(instance_id,run_id,question_id),
        FOREIGN KEY(instance_id,run_id,task_id) REFERENCES run_task(instance_id,run_id,task_id)
    );
    CREATE TABLE run_event_counter (
        engagement_id uuid PRIMARY KEY REFERENCES engagement(id),
        sequence bigint NOT NULL CHECK(sequence >= 0)
    );
    CREATE TABLE run_event (
        instance_id uuid NOT NULL,
        run_id uuid NOT NULL,
        engagement_id uuid NOT NULL,
        sequence bigint NOT NULL CHECK(sequence > 0),
        event_id uuid NOT NULL UNIQUE,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object' AND octet_length(payload::text)<=16384),
        PRIMARY KEY(engagement_id,sequence),
        FOREIGN KEY(instance_id,run_id,engagement_id) REFERENCES agent_run(instance_id,run_id,engagement_id)
    );
    CREATE TABLE run_command (
        instance_id uuid NOT NULL REFERENCES instance_control(instance_id),
        command_id uuid NOT NULL,
        request_digest text NOT NULL CHECK(request_digest ~ '^[0-9a-f]{64}$'),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        PRIMARY KEY(instance_id,command_id)
    );
    """)
    for table in ("run_setup", "run_task", "run_event", "run_command", "run_dispatch_event"):
        op.execute(
            f"CREATE TRIGGER run_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION model_v2_immutable()"
        )

    op.execute(
        "CREATE FUNCTION public.run_root_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$"
        + RUN_ROOT_GUARD
        + "$$"
    )
    op.execute(
        "CREATE FUNCTION public.run_setup_binding() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$"
        + RUN_SETUP_GUARD
        + "$$"
    )
    op.execute(
        "CREATE TRIGGER run_root_guard BEFORE INSERT OR UPDATE ON agent_run FOR EACH ROW EXECUTE FUNCTION public.run_root_guard()"
    )
    op.execute(
        "CREATE TRIGGER run_setup_binding BEFORE INSERT ON run_setup FOR EACH ROW EXECUTE FUNCTION public.run_setup_binding()"
    )
    op.execute(
        "CREATE TRIGGER run_no_delete BEFORE DELETE OR TRUNCATE ON agent_run FOR EACH STATEMENT EXECUTE FUNCTION public.model_v2_immutable()"
    )


def downgrade() -> None:
    raise RuntimeError("Run history requires reviewed backup restoration")
