"""Method execution migration contract; real PG upgrade is tested separately."""

import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import URL

from conftest import connect_test_database, verify_test_database


def test_method_execution_schema_is_explicit_and_chained() -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "src/omnis/migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "0017_model_removal"
    revision = scripts.get_revision("0012_contract_methods")
    assert revision is not None
    assert revision.down_revision == "0011_managed_tasks"
    from omnis.core.db import SCHEMA_REVISION

    assert SCHEMA_REVISION == scripts.get_current_head()


def test_pg_method_upgrade_preserves_history_and_exact_constraints(empty_database_url: URL) -> None:
    root = Path(__file__).resolve().parents[1]
    for revision in ("0011_managed_tasks", "0012_contract_methods"):
        verify_test_database(empty_database_url.set(database="omnis_test"))
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "alembic",
                "-c",
                str(root / "alembic.ini"),
                "upgrade",
                revision,
            ],
            cwd=root,
            env={
                **os.environ,
                "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
            },
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, f"method migration exit={result.returncode}"
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0012_contract_methods",
        )
        actual = {
            tuple(row)
            for row in connection.execute(
                "SELECT conname,contype,pg_get_constraintdef(oid),convalidated,conenforced FROM pg_constraint WHERE conrelid='managed_task'::regclass AND contype IN ('c','f','p','u')"
            ).fetchall()
        }
        from omnis.core.managed_schema import MANAGED_TABLES

        assert actual == MANAGED_TABLES["managed_task"][1]
