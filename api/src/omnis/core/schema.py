"""Physical authority schema contracts, including validated PostgreSQL 18 constraints."""

from sqlalchemy import text


# Each column is (type, required, exact default). Tables are never inferred from a stamp alone.
AUTHORITY_TABLES = {
    "pairing_challenge": ({
        "id": ("smallint", True, None),
        "digest": ("text", False, None),
        "expires_at": ("timestamp with time zone", False, None),
        "window_started_at": ("timestamp with time zone", True, "clock_timestamp()"),
        "attempts": ("integer", True, "0"),
    }, {
        ("pairing_challenge_pkey", "p", "PRIMARY KEY (id)", True, True),
        ("pairing_challenge_id_check", "c", "CHECK ((id = 1))", True, True),
        ("pairing_challenge_attempts_check", "c", "CHECK ((attempts >= 0))", True, True),
    }),
    "ui_session": ({
        "token_digest": ("text", True, None),
        "expires_at": ("timestamp with time zone", True, None),
    }, {
        ("ui_session_pkey", "p", "PRIMARY KEY (token_digest)", True, True),
    }),
}


async def authority_schema_matches(connection) -> bool:
    for table, (expected_columns, expected_constraints) in AUTHORITY_TABLES.items():
        columns = (await connection.execute(text(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, "
            "pg_get_expr(d.adbin, d.adrelid) FROM pg_attribute a "
            "LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
            "WHERE a.attrelid = to_regclass(:table) AND a.attnum > 0 AND NOT a.attisdropped"
        ), {"table": table})).all()
        constraints = (await connection.execute(text(
            "SELECT conname, contype, pg_get_constraintdef(oid), convalidated, conenforced "
            "FROM pg_constraint WHERE conrelid = to_regclass(:table)"
        ), {"table": table})).all()
        required = {
            (f"{table}_{name}_not_null", "n", f"NOT NULL {name}", True, True)
            for name, (_, not_null, _) in expected_columns.items() if not_null
        }
        if {name: (kind, not_null, default) for name, kind, not_null, default in columns} != expected_columns:
            return False
        if set(constraints) != expected_constraints | required:
            return False
    return (await connection.execute(text("SELECT count(*) FROM pairing_challenge WHERE id = 1"))).scalar_one() == 1
