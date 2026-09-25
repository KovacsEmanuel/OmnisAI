import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from alembic.config import Config
from alembic.script import ScriptDirectory

from conftest import connect_test_database
from omnis.core.db import SCHEMA_REVISION


def test_migration_creates_closed_instance_on_empty_postgres(empty_database_url):
    script = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")))
    assert script.get_current_head() == SCHEMA_REVISION
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone() == (0,)

    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, f"migration failed (exit {completed.returncode})"

    with connect_test_database(empty_database_url) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        rows = connection.execute(
            "SELECT instance_id, admission_open, shutdown_command_id, generation, "
            "quiesced_generation, quiesced_at FROM instance_control"
        ).fetchall()
    assert revision == ("0001_instance_control",)
    assert len(rows) == 1
    identity, admission_open, shutdown_command_id, generation, quiesced_generation, quiesced_at = rows[0]
    assert isinstance(identity, UUID)
    assert admission_open is False
    assert shutdown_command_id is None
    assert generation == 0
    assert quiesced_generation is None
    assert quiesced_at is None
