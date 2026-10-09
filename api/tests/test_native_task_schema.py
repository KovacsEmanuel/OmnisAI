"""Real PostgreSQL authority admission of the new lifecycle schema."""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy.engine import URL

from conftest import connect_test_database
from omnis.core.db import ReadinessReason, database_engine, readiness_reason


@pytest.mark.asyncio
async def test_managed_schema_missing_constraint_refuses_ready(migrated_database_url: URL) -> None:
    database_url = migrated_database_url
    engine = database_engine(database_url.render_as_string(hide_password=False))
    try:
        assert await readiness_reason(engine) is None
        with connect_test_database(database_url) as conn:
            schema: dict[str, object] = {}
            for table in ("managed_record", "managed_run", "managed_task", "managed_inbox"):
                columns = conn.execute(
                    "SELECT a.attname, format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(d.adbin,d.adrelid) "
                    "FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
                    "WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
                    (table,),
                ).fetchall()
                constraints = conn.execute(
                    "SELECT conname,contype,pg_get_constraintdef(oid),convalidated,conenforced FROM pg_constraint "
                    "WHERE conrelid=to_regclass(%s) AND contype<>'n' ORDER BY conname",
                    (table,),
                ).fetchall()
                schema[table] = {"columns": columns, "constraints": constraints}
            # Public schema only, no DSN, credentials or data. Parent can inspect exact PG forms.
            output = Path(os.environ["OMNIS_TEST_FIXTURE"]).parent / "managed-schema.json"
            output.write_text(json.dumps(schema, indent=2) + "\n")
            conn.execute("ALTER TABLE managed_run ALTER COLUMN stage_started DROP NOT NULL")
            conn.commit()
        assert await readiness_reason(engine) == ReadinessReason.SCHEMA_INCOMPATIBLE
    finally:
        await engine.dispose()
