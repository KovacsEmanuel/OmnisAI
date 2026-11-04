"""Empty and 0014 upgrade on the attested private PostgreSQL fixture."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from conftest import connect_test_database
from omnis.core.db import database_engine, readiness_reason

TABLES = (
    "model_record_v2",
    "system_operation",
    "model_command_v2",
    "model_dispatch_v2",
    "model_dispatch_event_v2",
    "system_operation_event",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, "0014_provider_settings"])
async def test_model_schema_empty_and_upgrade(
    empty_database_url: URL, tmp_path: Path, previous: str | None
) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": os.environ["PATH"],
        "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
    }
    for revision in (previous, "head") if previous else ("head",):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "alembic",
                "-c",
                str(root / "alembic.ini"),
                "upgrade",
                revision,
            ],
            cwd=root,
            env=env,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0
    physical: dict[str, object] = {}
    with connect_test_database(empty_database_url) as db:
        for name in TABLES:
            columns = db.execute(
                "SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(d.adbin,d.adrelid) "
                "FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
                "WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped",
                ("public." + name,),
            ).fetchall()
            constraints = db.execute(
                "SELECT conname,contype,pg_get_constraintdef(oid),convalidated,conenforced FROM pg_constraint "
                "WHERE conrelid=to_regclass(%s) AND contype<>'n'",
                ("public." + name,),
            ).fetchall()
            physical[name] = {"columns": columns, "constraints": constraints}
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0018_model_relay_authority",
        )
    (tmp_path / "model-schema.json").write_text(json.dumps(physical, sort_keys=True))
    engine = database_engine(empty_database_url.render_as_string(hide_password=False))
    try:
        assert await readiness_reason(engine) is None
        async with engine.begin() as db:
            await db.execute(text("ALTER TABLE system_operation ADD COLUMN drift text"))
        assert await readiness_reason(engine) is not None
    finally:
        await engine.dispose()
