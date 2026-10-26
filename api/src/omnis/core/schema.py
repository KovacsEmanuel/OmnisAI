"""Physical authority schema contracts, including validated PostgreSQL 18 constraints."""

from sqlalchemy import text
from sqlalchemy.dialects.postgresql.base import PGIdentifierPreparer
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.core.managed_schema import MANAGED_TABLES, MISSION_REVISION_GUARD
from omnis.core.model_schema import MODEL_TABLES
from omnis.core.provider_schema import PROVIDER_TABLES

type ColumnSpec = tuple[str, bool, str | None]
type ConstraintSpec = tuple[str, str, str, bool, bool]
type AuthoritySpec = tuple[dict[str, ColumnSpec], set[ConstraintSpec]]

# Each column is (type, required, exact default). Tables are never inferred from a stamp alone.
AUTHORITY_TABLES: dict[str, AuthoritySpec] = {
    "engagement": (
        {
            "id": ("uuid", True, None),
            "current_revision": ("integer", True, None),
            "created_at": ("timestamp with time zone", True, "clock_timestamp()"),
        },
        {
            ("engagement_pkey", "p", "PRIMARY KEY (id)", True, True),
            ("ck_engagement_revision", "c", "CHECK ((current_revision >= 1))", True, True),
            (
                "fk_engagement_current_revision",
                "f",
                "FOREIGN KEY (id, current_revision) REFERENCES engagement_revision(engagement_id, revision) DEFERRABLE INITIALLY DEFERRED",
                True,
                True,
            ),
        },
    ),
    "engagement_revision": (
        {
            "id": ("uuid", True, None),
            "engagement_id": ("uuid", True, None),
            "revision": ("integer", True, None),
            "command_id": ("uuid", False, None),
            "schema_version": ("smallint", True, None),
            "kind": ("text", True, None),
            "digest": ("text", True, None),
            "payload": ("jsonb", True, None),
            "created_at": ("timestamp with time zone", True, "clock_timestamp()"),
        },
        {
            ("engagement_revision_pkey", "p", "PRIMARY KEY (id)", True, True),
            ("uq_engagement_revision_order", "u", "UNIQUE (engagement_id, revision)", True, True),
            ("uq_revision_command", "u", "UNIQUE (engagement_id, command_id)", True, True),
            (
                "ck_revision_command",
                "c",
                "CHECK ((((revision = 1) AND (command_id IS NULL)) OR ((revision > 1) AND (command_id IS NOT NULL))))",
                True,
                True,
            ),
            (
                "fk_revision_engagement",
                "f",
                "FOREIGN KEY (engagement_id) REFERENCES engagement(id)",
                True,
                True,
            ),
            ("ck_revision_number", "c", "CHECK ((revision >= 1))", True, True),
            ("ck_revision_schema", "c", "CHECK ((schema_version = 1))", True, True),
            (
                "ck_revision_kind",
                "c",
                "CHECK ((kind = 'engagement-revision'::text))",
                True,
                True,
            ),
            (
                "ck_revision_digest",
                "c",
                "CHECK ((digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
            (
                "ck_revision_payload",
                "c",
                "CHECK ((jsonb_typeof(payload) = 'object'::text))",
                True,
                True,
            ),
        },
    ),
    "instance_stop_reconciliation": (
        {
            "reconciliation_id": ("uuid", True, None),
            "system_identifier": ("text", True, None),
            "grant": ("jsonb", True, None),
            "completion_sha256": ("text", True, None),
        },
        {("instance_stop_reconciliation_pkey", "p", "PRIMARY KEY (reconciliation_id)", True, True)},
    ),
    "instance_stop_fence": (
        {
            "id": ("smallint", True, None),
            "instance_id": ("uuid", True, None),
            "command_id": ("uuid", True, None),
            "finalize_command_id": ("uuid", True, None),
            "owner_uuid": ("uuid", False, None),
            "generation": ("bigint", True, None),
            "owner_epoch": ("bigint", True, None),
            "daemon_id": ("text", True, None),
            "inventory": ("jsonb", True, None),
            "state": ("text", True, None),
        },
        {
            ("instance_stop_fence_pkey", "p", "PRIMARY KEY (id)", True, True),
            ("instance_stop_fence_id_check", "c", "CHECK ((id = 1))", True, True),
            (
                "instance_stop_fence_generation_check",
                "c",
                "CHECK ((generation >= 0))",
                True,
                True,
            ),
            (
                "instance_stop_fence_owner_epoch_check",
                "c",
                "CHECK ((owner_epoch > 0))",
                True,
                True,
            ),
            (
                "instance_stop_fence_daemon_id_check",
                "c",
                "CHECK ((daemon_id <> ''::text))",
                True,
                True,
            ),
            (
                "instance_stop_fence_inventory_check",
                "c",
                "CHECK (((jsonb_typeof(inventory) = 'object'::text) AND (inventory <> '{}'::jsonb)))",
                True,
                True,
            ),
            (
                "instance_stop_fence_state_check",
                "c",
                "CHECK ((state = ANY (ARRAY['STOP_PENDING'::text, 'STOP_UNCERTAIN'::text])))",
                True,
                True,
            ),
        },
    ),
    "pairing_issuance": (
        {
            "issuance_id": ("uuid", True, None),
            "digest": ("text", True, None),
            "expires_at": ("timestamp with time zone", True, None),
        },
        {
            ("pairing_issuance_pkey", "p", "PRIMARY KEY (issuance_id)", True, True),
            ("pairing_issuance_digest_key", "u", "UNIQUE (digest)", True, True),
        },
    ),
    "pairing_challenge": (
        {
            "id": ("smallint", True, None),
            "digest": ("text", False, None),
            "expires_at": ("timestamp with time zone", False, None),
            "window_started_at": ("timestamp with time zone", True, "clock_timestamp()"),
            "attempts": ("integer", True, "0"),
        },
        {
            ("pairing_challenge_pkey", "p", "PRIMARY KEY (id)", True, True),
            ("pairing_challenge_id_check", "c", "CHECK ((id = 1))", True, True),
            ("pairing_challenge_attempts_check", "c", "CHECK ((attempts >= 0))", True, True),
        },
    ),
    "ui_session": (
        {
            "token_digest": ("text", True, None),
            "expires_at": ("timestamp with time zone", True, None),
        },
        {
            ("ui_session_pkey", "p", "PRIMARY KEY (token_digest)", True, True),
        },
    ),
    "supervisor_lease": (
        {
            "id": ("smallint", True, None),
            "owner": ("uuid", False, None),
            "epoch": ("bigint", True, "0"),
            "expires_at": ("timestamp with time zone", False, None),
        },
        {
            ("supervisor_lease_pkey", "p", "PRIMARY KEY (id)", True, True),
            ("supervisor_lease_id_check", "c", "CHECK ((id = 1))", True, True),
            ("supervisor_lease_epoch_check", "c", "CHECK ((epoch >= 0))", True, True),
        },
    ),
    "instance_command": (
        {
            "command_id": ("uuid", True, None),
            "kind": ("text", True, None),
            "expected_generation": ("bigint", True, None),
            "result_generation": ("bigint", True, None),
            "owner_epoch": ("bigint", True, None),
        },
        {
            ("instance_command_pkey", "p", "PRIMARY KEY (command_id)", True, True),
            (
                "instance_command_kind_check",
                "c",
                "CHECK ((kind = ANY (ARRAY['OPEN'::text, 'SHUTDOWN'::text, 'FINALIZE'::text])))",
                True,
                True,
            ),
            (
                "instance_command_expected_generation_check",
                "c",
                "CHECK ((expected_generation >= 0))",
                True,
                True,
            ),
            (
                "instance_command_result_generation_check",
                "c",
                "CHECK ((result_generation >= 0))",
                True,
                True,
            ),
            ("instance_command_owner_epoch_check", "c", "CHECK ((owner_epoch >= 0))", True, True),
        },
    ),
}


AUTHORITY_TABLES.update(
    {
        "catalog_record": (
            {
                "id": ("uuid", True, None),
                "owner_id": ("uuid", True, None),
                "group_id": ("uuid", True, None),
                "kind": ("text", True, None),
                "revision": ("integer", True, None),
                "digest": ("text", True, None),
                "envelope": ("jsonb", True, None),
            },
            {
                ("catalog_record_pkey", "p", "PRIMARY KEY (id)", True, True),
                ("catalog_record_id_revision_key", "u", "UNIQUE (id, revision)", True, True),
                ("catalog_record_revision_check", "c", "CHECK ((revision >= 1))", True, True),
                (
                    "catalog_record_digest_check",
                    "c",
                    "CHECK ((digest ~ '^[0-9a-f]{64}$'::text))",
                    True,
                    True,
                ),
                (
                    "catalog_record_envelope_check",
                    "c",
                    "CHECK ((jsonb_typeof(envelope) = 'object'::text))",
                    True,
                    True,
                ),
                (
                    "catalog_record_check",
                    "c",
                    "CHECK ((((envelope ->> 'id'::text))::uuid = id))",
                    True,
                    True,
                ),
                (
                    "catalog_record_check1",
                    "c",
                    "CHECK ((((envelope ->> 'revision'::text))::integer = revision))",
                    True,
                    True,
                ),
                (
                    "catalog_record_check2",
                    "c",
                    "CHECK (((envelope ->> 'kind'::text) = kind))",
                    True,
                    True,
                ),
                (
                    "catalog_record_check3",
                    "c",
                    "CHECK (((envelope ->> 'digest'::text) = digest))",
                    True,
                    True,
                ),
            },
        ),
        "catalog_identity": (
            {
                "id": ("uuid", True, None),
                "owner_id": ("uuid", True, None),
                "package_key": ("text", True, None),
                "entity_kind": ("text", True, None),
                "entity_key": ("text", True, None),
            },
            {
                ("catalog_identity_pkey", "p", "PRIMARY KEY (id)", True, True),
                (
                    "catalog_identity_package_key_entity_kind_entity_key_key",
                    "u",
                    "UNIQUE (package_key, entity_kind, entity_key)",
                    True,
                    True,
                ),
            },
        ),
        "catalog_reservation": (
            {
                "id": ("uuid", True, None),
                "revision": ("integer", True, None),
                "digest": ("text", True, None),
                "draft_id": ("uuid", True, None),
            },
            {
                ("catalog_reservation_pkey", "p", "PRIMARY KEY (id, revision)", True, True),
                ("catalog_reservation_id_digest_key", "u", "UNIQUE (id, digest)", True, True),
                ("catalog_reservation_revision_check", "c", "CHECK ((revision >= 1))", True, True),
                (
                    "catalog_reservation_digest_check",
                    "c",
                    "CHECK ((digest ~ '^[0-9a-f]{64}$'::text))",
                    True,
                    True,
                ),
                (
                    "catalog_reservation_id_fkey",
                    "f",
                    "FOREIGN KEY (id) REFERENCES catalog_identity(id)",
                    True,
                    True,
                ),
                (
                    "catalog_reservation_draft_id_fkey",
                    "f",
                    "FOREIGN KEY (draft_id) REFERENCES catalog_record(id)",
                    True,
                    True,
                ),
            },
        ),
        "catalog_command": (
            {
                "owner_id": ("uuid", True, None),
                "command_id": ("uuid", True, None),
                "operation": ("text", True, None),
                "request_digest": ("text", True, None),
                "result": ("jsonb", True, None),
            },
            {
                ("catalog_command_pkey", "p", "PRIMARY KEY (owner_id, command_id)", True, True),
                (
                    "catalog_command_request_digest_check",
                    "c",
                    "CHECK ((request_digest ~ '^[0-9a-f]{64}$'::text))",
                    True,
                    True,
                ),
                (
                    "catalog_command_result_check",
                    "c",
                    "CHECK ((jsonb_typeof(result) = 'object'::text))",
                    True,
                    True,
                ),
            },
        ),
    }
)


AUTHORITY_TABLES.update(MANAGED_TABLES)
AUTHORITY_TABLES.update(PROVIDER_TABLES)
AUTHORITY_TABLES.update(MODEL_TABLES)


async def authority_schema_matches(connection: AsyncConnection) -> bool:
    # Physical identity is required only for the new extension and its FK root;
    # historical authority contracts below remain unchanged. Never resolve the
    # extension again through the caller's search_path after this OID lookup.
    physical_oids: dict[str, int] = {}
    for name in ("managed_mission_revision", "managed_record", *MODEL_TABLES):
        identities = (
            await connection.execute(
                text(
                    "SELECT c.oid, n.nspname, c.relname, c.relkind, c.relpersistence "
                    "FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.oid = pg_catalog.to_regclass(:table)"
                ),
                {"table": f"public.{name}"},
            )
        ).all()
        if len(identities) != 1 or len(identities[0]) != 5:
            return False
        oid, namespace, relation, kind, persistence = identities[0]
        if (
            type(oid) is not int
            or oid <= 0
            or (namespace, relation, kind, persistence) != ("public", name, "r", "p")
        ):
            return False
        physical_oids[name] = oid
    mission_oid = physical_oids["managed_mission_revision"]
    root_oid = physical_oids["managed_record"]
    quote_identifier = PGIdentifierPreparer(connection.dialect).quote
    for table, (expected_columns, expected_constraints) in AUTHORITY_TABLES.items():
        mission = table == "managed_mission_revision"
        owned = mission or table in MODEL_TABLES
        catalog = "pg_catalog." if owned else ""
        relation_filter = ":relation_oid" if owned else "to_regclass(:table)"
        parameters: dict[str, str | int] = (
            {"relation_oid": physical_oids[table]} if owned else {"table": table}
        )
        columns = (
            await connection.execute(
                text(
                    f"SELECT a.attname, {catalog}format_type(a.atttypid, a.atttypmod), a.attnotnull, "
                    f"{catalog}pg_get_expr(d.adbin, d.adrelid) FROM {catalog}pg_attribute a "
                    f"LEFT JOIN {catalog}pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
                    f"WHERE a.attrelid = {relation_filter} AND a.attnum > 0 AND NOT a.attisdropped"
                ),
                parameters,
            )
        ).all()
        constraints = (
            await connection.execute(
                text(
                    f"SELECT conname, contype, {catalog}pg_get_constraintdef(oid), convalidated, conenforced"
                    + (", confrelid " if mission else " ")
                    + f"FROM {catalog}pg_constraint WHERE conrelid = {relation_filter}"
                ),
                parameters,
            )
        ).all()
        required = {
            (f"{table}_{name}_not_null", "n", f"NOT NULL {quote_identifier(name)}", True, True)
            for name, (_, not_null, _) in expected_columns.items()
            if not_null
        }
        if {
            name: (kind, not_null, default) for name, kind, not_null, default in columns
        } != expected_columns:
            return False
        if mission:
            if any(
                len(row) != 6 or row[5] != (root_oid if row[1] == "f" else 0) for row in constraints
            ):
                return False
            observed_constraints = {tuple(row[:5]) for row in constraints}
        else:
            observed_constraints = {tuple(row) for row in constraints}
        if observed_constraints != expected_constraints | required:
            return False
    index = (
        await connection.execute(
            text(
                "SELECT indisunique,indisvalid,indisready,indkey::text,pg_get_expr(indpred,indrelid) "
                "FROM pg_catalog.pg_index WHERE indexrelid=pg_catalog.to_regclass('public.model_test_one_active') "
                "AND indrelid=:table"
            ),
            {"table": physical_oids["system_operation"]},
        )
    ).one_or_none()
    if index is None or tuple(index) != (True, True, True, "2", "(state <> 'FINISHED'::text)"):
        return False
    for table, name, function, message in (
        (
            "managed_record",
            "managed_record_no_change",
            "managed_record_immutable",
            "managed records are immutable",
        ),
        (
            "instance_stop_reconciliation",
            "stop_reconciliation_immutable",
            "reject_stop_reconciliation_mutation",
            "Stop reconciliation receipts are immutable",
        ),
        (
            "engagement_revision",
            "engagement_revision_immutable",
            "reject_engagement_revision_mutation",
            "Engagement revisions are immutable",
        ),
        *(
            (
                table,
                "provider_settings_no_change",
                "provider_settings_immutable",
                "provider Settings history is immutable",
            )
            for table in PROVIDER_TABLES
        ),
        *(
            (table, "model_v2_no_change", "model_v2_immutable", "model V2 history is immutable")
            for table in MODEL_TABLES
            if table != "system_operation"
        ),
        *(
            (table, "catalog_immutable", "catalog_immutable", "immutable catalog ledger")
            for table in (
                "catalog_record",
                "catalog_identity",
                "catalog_reservation",
                "catalog_command",
            )
        ),
    ):
        immutable = (
            await connection.execute(
                text(
                    "SELECT t.tgname, t.tgtype, t.tgenabled, p.proname, p.prosrc, "
                    "l.lanname, p.prosecdef, p.pronargs, t.tgnargs, t.tgqual IS NULL, "
                    "t.tgattr::text, p.prorettype::regtype::text "
                    "FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
                    "JOIN pg_language l ON l.oid = p.prolang "
                    "WHERE t.tgrelid = to_regclass(:table) AND NOT t.tgisinternal"
                ),
                {"table": table},
            )
        ).all()
        if [tuple(row) for row in immutable] != [
            (
                name,
                58,
                "O",
                function,
                f"BEGIN\n        RAISE EXCEPTION '{message}';\n        END;",
                "plpgsql",
                False,
                0,
                0,
                True,
                "",
                "trigger",
            )
        ]:
            return False
    # Only the mission extension has a second guard. Preserve the exact single
    # immutable-trigger contract for every historical authority table above.
    mission_triggers = (
        await connection.execute(
            text(
                "SELECT t.tgname, t.tgtype, t.tgenabled, p.proname, p.prosrc, "
                "l.lanname, p.prosecdef, p.pronargs, t.tgnargs, t.tgqual IS NULL, "
                "t.tgattr::text, p.prorettype::regtype::text, p.proconfig, "
                "p.prokind, p.provolatile, p.proisstrict, t.tgdeferrable, t.tginitdeferred, "
                "t.tgconstraint = 0, t.tgargs = ''::bytea, p.pronamespace::regnamespace::text "
                "FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid = t.tgfoid "
                "JOIN pg_catalog.pg_language l ON l.oid = p.prolang "
                "WHERE t.tgrelid = :relation_oid AND NOT t.tgisinternal "
                "ORDER BY t.tgname"
            ),
            {"relation_oid": mission_oid},
        )
    ).all()
    if [tuple(row) for row in mission_triggers] != [
        (
            "managed_mission_revision_no_change",
            58,
            "O",
            "managed_mission_revision_immutable",
            "BEGIN\n        RAISE EXCEPTION 'mission revisions are immutable';\n        END;",
            "plpgsql",
            False,
            0,
            0,
            True,
            "",
            "trigger",
            None,
            "f",
            "v",
            False,
            False,
            False,
            True,
            True,
            "public",
        ),
        (
            "managed_mission_revision_root",
            7,
            "O",
            "managed_mission_revision_guard",
            MISSION_REVISION_GUARD,
            "plpgsql",
            False,
            0,
            0,
            True,
            "",
            "trigger",
            ["search_path=pg_catalog, pg_temp"],
            "f",
            "v",
            False,
            False,
            False,
            True,
            True,
            "public",
        ),
    ]:
        return False
    return all(
        (
            await connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM pairing_challenge WHERE id = 1) = 1, "
                    "(SELECT count(*) FROM supervisor_lease WHERE id = 1) = 1"
                )
            )
        ).one()
    )
