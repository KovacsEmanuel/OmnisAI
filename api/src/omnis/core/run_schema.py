"""Readiness for the additive S1 tables; no schema creation during startup."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

RUN_COLUMNS = {
    "run_setup": {
        "instance_id": "uuid",
        "setup_id": "uuid",
        "engagement_id": "uuid",
        "draft_id": "uuid",
    },
    "agent_run": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "engagement_id": "uuid",
        "setup_id": "uuid",
        "revision": "bigint",
        "generation": "bigint",
        "owner_id": "uuid",
        "owner_epoch": "bigint",
        "fence": "bigint",
        "state": "text",
        "payload": "jsonb",
    },
    "run_task": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "task_id": "uuid",
        "role": "text",
        "parent_task_id": "uuid",
    },
    "run_attempt": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "task_id": "uuid",
        "attempt_id": "uuid",
        "role": "text",
        "state": "text",
        "payload": "jsonb",
    },
    "run_dispatch": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "task_id": "uuid",
        "attempt_id": "uuid",
        "dispatch_id": "uuid",
        "projection_id": "uuid",
        "relay_kind": "text",
        "state": "text",
        "deadline": "timestamp with time zone",
        "payload": "jsonb",
    },
    "run_inbox": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "result_id": "uuid",
        "consumed_decision_id": "uuid",
        "held": "boolean",
    },
    "run_dispatch_event": {
        "instance_id": "uuid",
        "dispatch_id": "uuid",
        "sequence": "smallint",
        "state": "text",
        "created_at": "timestamp with time zone",
    },
    "run_question": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "task_id": "uuid",
        "question_id": "uuid",
        "state": "text",
        "payload": "jsonb",
    },
    "run_event_counter": {"engagement_id": "uuid", "sequence": "bigint"},
    "run_event": {
        "instance_id": "uuid",
        "run_id": "uuid",
        "engagement_id": "uuid",
        "sequence": "bigint",
        "event_id": "uuid",
        "payload": "jsonb",
    },
    "run_command": {
        "instance_id": "uuid",
        "command_id": "uuid",
        "request_digest": "text",
        "payload": "jsonb",
    },
}
NULLABLE = {("run_task", "parent_task_id"), ("run_inbox", "consumed_decision_id")}
RUN_ROOT_GUARD = """BEGIN
    IF NOT (NEW.payload @> jsonb_build_object(
        'instance_id', NEW.instance_id::text, 'run_id', NEW.run_id::text,
        'engagement_id', NEW.engagement_id::text, 'revision', NEW.revision,
        'generation', NEW.generation, 'owner_id', NEW.owner_id::text,
        'owner_epoch', NEW.owner_epoch, 'fence', NEW.fence, 'state', NEW.state,
        'setup_ref', jsonb_build_object('id', NEW.setup_id::text))) THEN
        RAISE EXCEPTION 'run root payload mismatch';
    END IF;
    IF TG_OP = 'UPDATE' AND (
        (NEW.instance_id,NEW.run_id,NEW.engagement_id,NEW.setup_id,NEW.generation,NEW.owner_id,NEW.owner_epoch)
        IS DISTINCT FROM
        (OLD.instance_id,OLD.run_id,OLD.engagement_id,OLD.setup_id,OLD.generation,OLD.owner_id,OLD.owner_epoch)
        OR NEW.payload->'setup_ref' IS DISTINCT FROM OLD.payload->'setup_ref') THEN
        RAISE EXCEPTION 'run root is immutable';
    END IF;
    RETURN NEW;
END;"""
RUN_SETUP_GUARD = """BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.engagement_revision d
        JOIN public.model_record_v2 r ON r.instance_id=NEW.instance_id AND r.id=NEW.setup_id
        WHERE d.id=NEW.draft_id AND d.engagement_id=NEW.engagement_id
        AND r.kind='run-setup-v1'
        AND r.payload->>'engagement_id'=NEW.engagement_id::text
        AND r.payload#>>'{draft_ref,id}'=NEW.draft_id::text
        AND r.payload#>>'{draft_ref,digest}'=d.digest
        AND (r.payload#>>'{draft_ref,revision}')::bigint=d.revision
    ) THEN
        RAISE EXCEPTION 'run setup lineage mismatch';
    END IF;
    RETURN NEW;
END;"""

# PostgreSQL 18 deparser output, compared without lossy SQL normalization.
CONSTRAINTS: dict[str, set[str]] = {
    "run_setup": {
        "PRIMARY KEY (instance_id, setup_id)",
        "UNIQUE (instance_id, setup_id, engagement_id)",
        "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
        "FOREIGN KEY (engagement_id) REFERENCES engagement(id)",
        "FOREIGN KEY (draft_id) REFERENCES engagement_revision(id)",
        "FOREIGN KEY (instance_id, setup_id) REFERENCES model_record_v2(instance_id, id)",
    },
    "agent_run": {
        "PRIMARY KEY (instance_id, run_id)",
        "UNIQUE (instance_id, run_id, engagement_id)",
        "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
        "FOREIGN KEY (engagement_id) REFERENCES engagement(id)",
        "FOREIGN KEY (instance_id, setup_id, engagement_id) REFERENCES run_setup(instance_id, setup_id, engagement_id)",
        "CHECK ((revision > 0))",
        "CHECK ((generation >= 0))",
        "CHECK ((owner_epoch > 0))",
        "CHECK ((fence > 0))",
        "CHECK ((state = ANY (ARRAY['RUNNING'::text, 'PAUSING'::text, 'PAUSED'::text, 'HOLD'::text, 'STOPPING'::text, 'STOPPED'::text, 'COMPLETED'::text, 'LIMITED'::text, 'NEEDS_RECONCILIATION'::text])))",
        "CHECK ((jsonb_typeof(payload) = 'object'::text))",
        "CHECK ((((payload ->> 'run_id'::text) = (run_id)::text) AND ((payload ->> 'instance_id'::text) = (instance_id)::text) AND ((payload ->> 'engagement_id'::text) = (engagement_id)::text) AND ((payload ->> 'state'::text) = state) AND (((payload ->> 'revision'::text))::bigint = revision)))",
    },
    "run_task": {
        "PRIMARY KEY (instance_id, run_id, task_id)",
        "UNIQUE (instance_id, run_id, task_id, role)",
        "CHECK ((role = ANY (ARRAY['BRAIN'::text, 'RECON'::text])))",
        "FOREIGN KEY (instance_id, run_id) REFERENCES agent_run(instance_id, run_id)",
        "FOREIGN KEY (instance_id, run_id, parent_task_id) REFERENCES run_task(instance_id, run_id, task_id)",
    },
    "run_attempt": {
        "PRIMARY KEY (instance_id, run_id, attempt_id)",
        "UNIQUE (instance_id, run_id, task_id, attempt_id)",
        "CHECK ((role = ANY (ARRAY['BRAIN'::text, 'RECON'::text])))",
        "CHECK ((state = ANY (ARRAY['RUNNING'::text, 'SUCCEEDED'::text, 'INCONCLUSIVE'::text, 'FAILED'::text, 'CANCELLED'::text, 'NEEDS_RECONCILIATION'::text])))",
        "CHECK ((jsonb_typeof(payload) = 'object'::text))",
        "FOREIGN KEY (instance_id, run_id, task_id, role) REFERENCES run_task(instance_id, run_id, task_id, role)",
        "CHECK ((((payload ->> 'attempt_id'::text) = (attempt_id)::text) AND ((payload ->> 'task_id'::text) = (task_id)::text) AND ((payload ->> 'run_id'::text) = (run_id)::text) AND ((payload ->> 'role'::text) = role) AND ((payload ->> 'state'::text) = state)))",
    },
    "run_dispatch": {
        "PRIMARY KEY (instance_id, dispatch_id)",
        "CHECK ((relay_kind = 'MODEL_DISPATCH'::text))",
        "CHECK ((state = ANY (ARRAY['RESERVED'::text, 'SENT'::text, 'SETTLED'::text, 'RELEASED'::text, 'UNKNOWN'::text])))",
        "CHECK ((jsonb_typeof(payload) = 'object'::text))",
        "FOREIGN KEY (instance_id, run_id, task_id, attempt_id) REFERENCES run_attempt(instance_id, run_id, task_id, attempt_id)",
        "FOREIGN KEY (instance_id, projection_id) REFERENCES model_record_v2(instance_id, id)",
        "FOREIGN KEY (instance_id, relay_kind, dispatch_id) REFERENCES model_relay_authority(instance_id, kind, id)",
    },
    "run_dispatch_event": {
        "PRIMARY KEY (instance_id, dispatch_id, sequence)",
        "UNIQUE (instance_id, dispatch_id, state)",
        "CHECK (((sequence >= 1) AND (sequence <= 3)))",
        "CHECK ((state = ANY (ARRAY['RESERVED'::text, 'SENT'::text, 'SETTLED'::text, 'RELEASED'::text, 'UNKNOWN'::text])))",
        "FOREIGN KEY (instance_id, dispatch_id) REFERENCES run_dispatch(instance_id, dispatch_id)",
    },
    "run_inbox": {
        "PRIMARY KEY (instance_id, run_id, result_id)",
        "FOREIGN KEY (instance_id, run_id) REFERENCES agent_run(instance_id, run_id)",
        "FOREIGN KEY (instance_id, result_id) REFERENCES model_record_v2(instance_id, id)",
        "FOREIGN KEY (instance_id, consumed_decision_id) REFERENCES model_record_v2(instance_id, id)",
    },
    "run_question": {
        "PRIMARY KEY (instance_id, run_id, question_id)",
        "CHECK ((state = ANY (ARRAY['PENDING'::text, 'ANSWER_ADMITTED'::text, 'CONSUMED'::text])))",
        "CHECK ((jsonb_typeof(payload) = 'object'::text))",
        "FOREIGN KEY (instance_id, run_id, task_id) REFERENCES run_task(instance_id, run_id, task_id)",
    },
    "run_event_counter": {
        "PRIMARY KEY (engagement_id)",
        "FOREIGN KEY (engagement_id) REFERENCES engagement(id)",
        "CHECK ((sequence >= 0))",
    },
    "run_event": {
        "PRIMARY KEY (engagement_id, sequence)",
        "UNIQUE (event_id)",
        "CHECK ((sequence > 0))",
        "CHECK (((jsonb_typeof(payload) = 'object'::text) AND (octet_length((payload)::text) <= 16384)))",
        "FOREIGN KEY (instance_id, run_id, engagement_id) REFERENCES agent_run(instance_id, run_id, engagement_id)",
    },
    "run_command": {
        "PRIMARY KEY (instance_id, command_id)",
        "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
        "CHECK ((request_digest ~ '^[0-9a-f]{64}$'::text))",
        "CHECK ((jsonb_typeof(payload) = 'object'::text))",
    },
}
DEFAULTS = {
    ("run_dispatch", "relay_kind"): "'MODEL_DISPATCH'::text",
    ("run_dispatch_event", "created_at"): "clock_timestamp()",
}
INDEXES = {
    "agent_run_one_active": (
        "agent_run",
        "1",
        "(state <> ALL (ARRAY['STOPPED'::text, 'COMPLETED'::text, 'LIMITED'::text]))",
    ),
    "run_attempt_one_worker": (
        "run_attempt",
        "1 2",
        "((role = 'RECON'::text) AND (state = ANY (ARRAY['RUNNING'::text, 'NEEDS_RECONCILIATION'::text])))",
    ),
    "run_dispatch_one_active": (
        "run_dispatch",
        "1",
        "(state = ANY (ARRAY['RESERVED'::text, 'SENT'::text]))",
    ),
}
IMMUTABLE = {"run_setup", "run_task", "run_event", "run_command", "run_dispatch_event"}
IMMUTABLE_TRIGGER = (
    "run_no_change",
    58,
    "O",
    "model_v2_immutable",
    "BEGIN\n        RAISE EXCEPTION 'model V2 history is immutable';\n        END;",
    "plpgsql",
    False,
    0,
    0,
    True,
    "",
    "trigger",
    None,
    "public",
    False,
    False,
    True,
    True,
)


TRIGGERS: dict[str, list[tuple[object, ...]]] = {
    name: [IMMUTABLE_TRIGGER] if name in IMMUTABLE else [] for name in RUN_COLUMNS
}
for _table, _name, _type, _body in (
    ("agent_run", "run_root_guard", 23, RUN_ROOT_GUARD),
    ("run_setup", "run_setup_binding", 7, RUN_SETUP_GUARD),
):
    TRIGGERS[_table].append(
        (
            _name,
            _type,
            "O",
            _name,
            _body,
            "plpgsql",
            False,
            0,
            0,
            True,
            "",
            "trigger",
            ["search_path=pg_catalog, pg_temp"],
            "public",
            False,
            False,
            True,
            True,
        )
    )
    TRIGGERS[_table].sort(key=lambda row: str(row[0]))
TRIGGERS["agent_run"].insert(0, ("run_no_delete", 42, *IMMUTABLE_TRIGGER[2:]))


async def run_schema_matches(connection: AsyncConnection) -> bool:
    for name, expected in RUN_COLUMNS.items():
        oid = await connection.scalar(
            text(
                "SELECT c.oid FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=:name AND c.relkind='r' AND c.relpersistence='p' AND NOT c.relrowsecurity AND NOT c.relforcerowsecurity AND NOT c.relispartition AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid)"
            ),
            {"name": name},
        )
        if type(oid) is not int or oid <= 0:
            return False
        columns = (
            await connection.execute(
                text(
                    "SELECT a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_catalog.pg_get_expr(d.adbin,d.adrelid),a.attidentity,a.attgenerated FROM pg_catalog.pg_attribute a LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=:oid AND a.attnum>0 AND NOT a.attisdropped"
                ),
                {"oid": oid},
            )
        ).all()
        if {tuple(row) for row in columns} != {
            (key, kind, (name, key) not in NULLABLE, DEFAULTS.get((name, key)), "", "")
            for key, kind in expected.items()
        }:
            return False
        constraints = (
            await connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_constraintdef(c.oid),c.convalidated,c.conenforced,c.condeferrable,c.condeferred,CASE WHEN c.contype='f' THEN c.confrelid=pg_catalog.to_regclass('public.'||r.relname) ELSE true END FROM pg_catalog.pg_constraint c LEFT JOIN pg_catalog.pg_class r ON r.oid=c.confrelid WHERE c.conrelid=:oid AND c.contype<>'n'"
                ),
                {"oid": oid},
            )
        ).all()
        if {tuple(row) for row in constraints} != {
            (definition, True, True, False, False, True) for definition in CONSTRAINTS[name]
        }:
            return False
        triggers = (
            await connection.execute(
                text(
                    "SELECT t.tgname,t.tgtype,t.tgenabled,p.proname,p.prosrc,l.lanname,p.prosecdef,p.pronargs,t.tgnargs,t.tgqual IS NULL,t.tgattr::text,p.prorettype::regtype::text,p.proconfig,p.pronamespace::regnamespace::text,t.tgdeferrable,t.tginitdeferred,t.tgconstraint=0,t.tgargs=''::bytea FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid JOIN pg_catalog.pg_language l ON l.oid=p.prolang WHERE t.tgrelid=:oid AND NOT t.tgisinternal ORDER BY t.tgname"
                ),
                {"oid": oid},
            )
        ).all()
        if [tuple(row) for row in triggers] != TRIGGERS[name]:
            return False
        # Constraint-backed unique indexes must also be usable, not merely present.
        if (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_constraint c JOIN pg_catalog.pg_index i ON i.indexrelid=c.conindid WHERE c.conrelid=:oid AND c.contype IN ('p','u') AND (NOT i.indisunique OR NOT i.indisvalid OR NOT i.indisready OR NOT i.indislive OR NOT i.indimmediate OR i.indexprs IS NOT NULL OR i.indpred IS NOT NULL)"
                ),
                {"oid": oid},
            )
            != 0
        ):
            return False
    for index, (table, keys, predicate) in INDEXES.items():
        rows = (
            await connection.execute(
                text(
                    "SELECT i.indisunique,i.indisvalid,i.indisready,i.indislive,i.indimmediate,i.indkey::text,pg_catalog.pg_get_expr(i.indpred,i.indrelid),i.indexprs IS NULL,i.indnkeyatts,i.indnatts,i.indnullsnotdistinct,a.amname FROM pg_catalog.pg_index i JOIN pg_catalog.pg_class c ON c.oid=i.indexrelid JOIN pg_catalog.pg_am a ON a.oid=c.relam WHERE i.indexrelid=pg_catalog.to_regclass(:index) AND i.indrelid=pg_catalog.to_regclass(:table) AND c.relkind='i' AND c.relpersistence='p'"
                ),
                {"index": "public." + index, "table": "public." + table},
            )
        ).all()
        count = len(keys.split())
        if [tuple(row) for row in rows] != [
            (True, True, True, True, True, keys, predicate, True, count, count, False, "btree")
        ]:
            return False
    return True
