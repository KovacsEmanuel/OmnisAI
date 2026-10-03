"""Physical authority schema contracts, including validated PostgreSQL 18 constraints."""

from sqlalchemy import text
from sqlalchemy.dialects.postgresql.base import PGIdentifierPreparer
from sqlalchemy.ext.asyncio import AsyncConnection

type ColumnSpec = tuple[str, bool, str | None]
type ConstraintSpec = tuple[str, str, str, bool, bool]
type AuthoritySpec = tuple[dict[str, ColumnSpec], set[ConstraintSpec]]

# Each column is (type, required, exact default). Tables are never inferred from a stamp alone.
AUTHORITY_TABLES: dict[str, AuthoritySpec] = {
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


async def authority_schema_matches(connection: AsyncConnection) -> bool:
    quote_identifier = PGIdentifierPreparer(connection.dialect).quote
    for table, (expected_columns, expected_constraints) in AUTHORITY_TABLES.items():
        columns = (
            await connection.execute(
                text(
                    "SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, "
                    "pg_get_expr(d.adbin, d.adrelid) FROM pg_attribute a "
                    "LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
                    "WHERE a.attrelid = to_regclass(:table) AND a.attnum > 0 AND NOT a.attisdropped"
                ),
                {"table": table},
            )
        ).all()
        constraints = (
            await connection.execute(
                text(
                    "SELECT conname, contype, pg_get_constraintdef(oid), convalidated, conenforced "
                    "FROM pg_constraint WHERE conrelid = to_regclass(:table)"
                ),
                {"table": table},
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
        if set(constraints) != expected_constraints | required:
            return False
    immutable = (
        await connection.execute(
            text(
                "SELECT t.tgname, t.tgtype, t.tgenabled, p.proname, p.prosrc, "
                "l.lanname, p.prosecdef, p.pronargs, t.tgnargs, t.tgqual IS NULL, "
                "t.tgattr::text, p.prorettype::regtype::text "
                "FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
                "JOIN pg_language l ON l.oid = p.prolang "
                "WHERE t.tgrelid = 'instance_stop_reconciliation'::regclass AND NOT t.tgisinternal"
            )
        )
    ).all()
    if [tuple(row) for row in immutable] != [
        (
            "stop_reconciliation_immutable",
            58,
            "O",
            "reject_stop_reconciliation_mutation",
            "BEGIN\n        RAISE EXCEPTION 'Stop reconciliation receipts are immutable';\n        END;",
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
