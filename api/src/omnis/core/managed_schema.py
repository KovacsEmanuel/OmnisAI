"""Exact PostgreSQL18 managed lifecycle DDL; changes require a migration probe."""

type ManagedColumn = tuple[str, bool, str | None]
type ManagedConstraint = tuple[str, str, str, bool, bool]

# Independently pinned function body: readiness must not trust migration imports.
MISSION_REVISION_GUARD = """DECLARE
        root jsonb;
        predecessor jsonb;
        basis jsonb;
        mission_basis jsonb;
        mission_count bigint;
        BEGIN
        SELECT envelope INTO root FROM public.managed_record
            WHERE id = NEW.mission_id AND owner_id = NEW.owner_id AND run_id = NEW.run_id;
        IF NOT FOUND OR (root->'kind' = '"mission"'::jsonb
            AND root->'revision' = '1'::jsonb AND root->>'revision' = '1'
            AND root->'schema_version' = '1'::jsonb AND root->>'schema_version' = '1'
            AND root->'id' = to_jsonb(NEW.mission_id::text)
            AND jsonb_typeof(root->'digest') = 'string'
            AND root->>'digest' ~ '^[0-9a-f]{64}$') IS NOT TRUE THEN
            RAISE EXCEPTION 'invalid mission revision root';
        END IF;
        basis := NEW.envelope->'payload'->'basis_refs';
        IF jsonb_typeof(basis) IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'invalid mission predecessor';
        END IF;
        SELECT count(*) INTO mission_count FROM jsonb_array_elements(basis) AS refs(value)
            WHERE value->'kind' = '"mission"'::jsonb;
        IF mission_count <> 1 THEN
            RAISE EXCEPTION 'invalid mission predecessor';
        END IF;
        SELECT value INTO mission_basis FROM jsonb_array_elements(basis) AS refs(value)
            WHERE value->'kind' = '"mission"'::jsonb;
        predecessor := jsonb_build_object('kind', 'mission', 'id', NEW.mission_id::text,
            'revision', 1, 'digest', root->>'digest');
        IF (mission_basis = predecessor AND mission_basis->>'revision' = '1') IS NOT TRUE THEN
            RAISE EXCEPTION 'invalid mission predecessor';
        END IF;
        RETURN NEW;
        END;"""

MANAGED_TABLES: dict[str, tuple[dict[str, ManagedColumn], set[ManagedConstraint]]] = {
    "managed_inbox": (
        {
            "admitted": ("boolean", True, None),
            "delivered": ("boolean", True, None),
            "disposition": ("text", True, None),
            "domain_result_consumed": ("boolean", True, None),
            "result_id": ("uuid", True, None),
            "task_id": ("uuid", True, None),
            "turn_completed": ("boolean", True, None),
        },
        {
            (
                "managed_inbox_check",
                "c",
                "CHECK ((delivered AND (NOT admitted) AND (NOT turn_completed)))",
                True,
                True,
            ),
            (
                "managed_inbox_disposition_check",
                "c",
                "CHECK ((disposition = ANY (ARRAY['RECEIVED'::text, "
                "'HELD_FOR_RECONCILIATION'::text])))",
                True,
                True,
            ),
            ("managed_inbox_pkey", "p", "PRIMARY KEY (result_id)", True, True),
            (
                "managed_inbox_result_id_fkey",
                "f",
                "FOREIGN KEY (result_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            (
                "managed_inbox_task_id_fkey",
                "f",
                "FOREIGN KEY (task_id) REFERENCES managed_task(task_id)",
                True,
                True,
            ),
            ("managed_inbox_task_id_key", "u", "UNIQUE (task_id)", True, True),
        },
    ),
    "managed_record": (
        {
            "envelope": ("jsonb", True, None),
            "id": ("uuid", True, None),
            "owner_id": ("uuid", True, None),
            "run_id": ("uuid", True, None),
        },
        {
            (
                "managed_record_check",
                "c",
                "CHECK ((((envelope ->> 'id'::text))::uuid = id))",
                True,
                True,
            ),
            (
                "managed_record_envelope_check",
                "c",
                "CHECK ((jsonb_typeof(envelope) = 'object'::text))",
                True,
                True,
            ),
            (
                "managed_record_envelope_check1",
                "c",
                "CHECK (((envelope ->> 'schema_version'::text) = '1'::text))",
                True,
                True,
            ),
            (
                "managed_record_envelope_check2",
                "c",
                "CHECK (((envelope ->> 'revision'::text) = '1'::text))",
                True,
                True,
            ),
            ("managed_record_pkey", "p", "PRIMARY KEY (id)", True, True),
            (
                "managed_record_id_owner_run_key",
                "u",
                "UNIQUE (id, owner_id, run_id)",
                True,
                True,
            ),
        },
    ),
    "managed_mission_revision": (
        {
            "mission_id": ("uuid", True, None),
            "owner_id": ("uuid", True, None),
            "run_id": ("uuid", True, None),
            "revision": ("bigint", True, None),
            "envelope": ("jsonb", True, None),
        },
        {
            (
                "managed_mission_revision_pkey",
                "p",
                "PRIMARY KEY (mission_id, revision)",
                True,
                True,
            ),
            (
                "managed_mission_revision_root_fkey",
                "f",
                "FOREIGN KEY (mission_id, owner_id, run_id) REFERENCES managed_record(id, owner_id, run_id)",
                True,
                True,
            ),
            ("managed_mission_revision_number_check", "c", "CHECK ((revision = 2))", True, True),
            (
                "managed_mission_revision_object_check",
                "c",
                "CHECK ((jsonb_typeof(envelope) = 'object'::text))",
                True,
                True,
            ),
            (
                "managed_mission_revision_kind_check",
                "c",
                "CHECK ((((envelope -> 'kind'::text) = '\"mission\"'::jsonb) IS TRUE))",
                True,
                True,
            ),
            (
                "managed_mission_revision_id_check",
                "c",
                "CHECK ((((envelope -> 'id'::text) = to_jsonb((mission_id)::text)) IS TRUE))",
                True,
                True,
            ),
            (
                "managed_mission_revision_schema_check",
                "c",
                "CHECK (((((envelope -> 'schema_version'::text) = '1'::jsonb) AND "
                "((envelope ->> 'schema_version'::text) = '1'::text)) IS TRUE))",
                True,
                True,
            ),
            (
                "managed_mission_revision_revision_check",
                "c",
                "CHECK (((((envelope -> 'revision'::text) = '2'::jsonb) AND "
                "((envelope ->> 'revision'::text) = '2'::text)) IS TRUE))",
                True,
                True,
            ),
        },
    ),
    "managed_run": (
        {
            "binding_id": ("uuid", False, None),
            "command_id": ("uuid", True, None),
            "final_id": ("uuid", False, None),
            "manifest_id": ("uuid", True, None),
            "native_root_id": ("text", False, None),
            "owner_id": ("uuid", True, None),
            "release_started": ("boolean", True, "false"),
            "request_digest": ("text", True, None),
            "run_id": ("uuid", True, None),
            "runtime_boot": ("uuid", False, None),
            "stage_started": ("boolean", True, "false"),
            "ticket": ("uuid", False, None),
        },
        {
            (
                "managed_run_binding_id_fkey",
                "f",
                "FOREIGN KEY (binding_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            ("managed_run_binding_id_key", "u", "UNIQUE (binding_id)", True, True),
            (
                "managed_run_check",
                "c",
                "CHECK (((NOT release_started) OR (binding_id IS NOT NULL)))",
                True,
                True,
            ),
            (
                "managed_run_check1",
                "c",
                "CHECK (((final_id IS NULL) OR release_started))",
                True,
                True,
            ),
            (
                "managed_run_check2",
                "c",
                "CHECK (((binding_id IS NULL) = (runtime_boot IS NULL)))",
                True,
                True,
            ),
            (
                "managed_run_check3",
                "c",
                "CHECK (((binding_id IS NULL) = (ticket IS NULL)))",
                True,
                True,
            ),
            (
                "managed_run_check4",
                "c",
                "CHECK (((binding_id IS NULL) = (native_root_id IS NULL)))",
                True,
                True,
            ),
            (
                "managed_run_final_id_fkey",
                "f",
                "FOREIGN KEY (final_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            ("managed_run_final_id_key", "u", "UNIQUE (final_id)", True, True),
            (
                "managed_run_manifest_id_fkey",
                "f",
                "FOREIGN KEY (manifest_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            ("managed_run_manifest_id_key", "u", "UNIQUE (manifest_id)", True, True),
            (
                "managed_run_owner_id_command_id_key",
                "u",
                "UNIQUE (owner_id, command_id)",
                True,
                True,
            ),
            ("managed_run_pkey", "p", "PRIMARY KEY (run_id)", True, True),
            (
                "managed_run_request_digest_check",
                "c",
                "CHECK ((request_digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
            (
                "managed_run_run_id_fkey",
                "f",
                "FOREIGN KEY (run_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            (
                "managed_run_runtime_boot_native_root_id_key",
                "u",
                "UNIQUE (runtime_boot, native_root_id)",
                True,
                True,
            ),
            (
                "managed_run_runtime_boot_ticket_key",
                "u",
                "UNIQUE (runtime_boot, ticket)",
                True,
                True,
            ),
        },
    ),
    "managed_task": (
        {
            "attempt_id": ("uuid", True, None),
            "batch_index": ("integer", True, None),
            "brief_id": ("uuid", True, None),
            "check_id": ("uuid", False, None),
            "native_child_id": ("text", False, None),
            "native_session_id": ("text", False, None),
            "result_id": ("uuid", False, None),
            "run_id": ("uuid", True, None),
            "runtime_boot": ("uuid", False, None),
            "state": ("text", True, None),
            "task_id": ("uuid", True, None),
        },
        {
            ("managed_task_attempt_id_key", "u", "UNIQUE (attempt_id)", True, True),
            (
                "managed_task_batch_index_check",
                "c",
                "CHECK (((batch_index >= 0) AND (batch_index <= 1)))",
                True,
                True,
            ),
            (
                "managed_task_brief_id_fkey",
                "f",
                "FOREIGN KEY (brief_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            ("managed_task_brief_id_key", "u", "UNIQUE (brief_id)", True, True),
            (
                "managed_task_check",
                "c",
                "CHECK (((check_id IS NULL) OR (result_id IS NOT NULL)))",
                True,
                True,
            ),
            (
                "managed_task_check_id_fkey",
                "f",
                "FOREIGN KEY (check_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            ("managed_task_check_id_key", "u", "UNIQUE (check_id)", True, True),
            ("managed_task_pkey", "p", "PRIMARY KEY (task_id)", True, True),
            (
                "managed_task_result_id_fkey",
                "f",
                "FOREIGN KEY (result_id) REFERENCES managed_record(id)",
                True,
                True,
            ),
            ("managed_task_result_id_key", "u", "UNIQUE (result_id)", True, True),
            (
                "managed_task_run_id_batch_index_key",
                "u",
                "UNIQUE (run_id, batch_index)",
                True,
                True,
            ),
            (
                "managed_task_run_id_fkey",
                "f",
                "FOREIGN KEY (run_id) REFERENCES managed_run(run_id)",
                True,
                True,
            ),
            (
                "managed_task_runtime_boot_native_child_id_key",
                "u",
                "UNIQUE (runtime_boot, native_child_id)",
                True,
                True,
            ),
            (
                "managed_task_runtime_boot_native_session_id_key",
                "u",
                "UNIQUE (runtime_boot, native_session_id)",
                True,
                True,
            ),
            (
                "managed_task_state_check",
                "c",
                "CHECK ((state = ANY (ARRAY['QUEUED'::text, 'BOUND'::text, 'BLOCKED'::text, 'SUCCEEDED'::text])))",
                True,
                True,
            ),
            (
                "managed_task_success_check",
                "c",
                "CHECK (((state <> 'SUCCEEDED'::text) OR ((result_id IS NOT NULL) AND (check_id IS NOT NULL))))",
                True,
                True,
            ),
        },
    ),
}
