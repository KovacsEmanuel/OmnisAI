import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from conftest import connect_test_database
from omnis.core.db import SCHEMA_REVISION


def test_migration_creates_closed_instance_on_empty_postgres(empty_database_url):
    script = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")))
    assert script.get_current_head() == SCHEMA_REVISION
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone() == (0,)

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("Initial migration fixture timed out", pytrace=False)
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


def test_installed_wheel_migrates_without_checkout(empty_database_url, tmp_path):
    uv = os.environ.get("OMNIS_UV")
    assert uv, "OMNIS_UV must point to pinned uv 0.12.19"
    root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    requirements = tmp_path / "requirements.txt"
    venv_python = tmp_path / "venv/bin/python"

    def run(label, command, *, isolated_migration=False):
        env = None
        if isolated_migration:
            env = {
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
            }
        try:
            result = subprocess.run(
                command, cwd=tmp_path, env=env, capture_output=True, text=True,
                timeout=120, check=False,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"{label} exceeded its deadline", pytrace=False)
        if result.returncode:
            pytest.fail(f"{label} failed (exit {result.returncode})", pytrace=False)

    run("wheel build", [uv, "build", "--no-config", "--wheel", str(root), "--out-dir", str(wheel_dir)])
    wheel, = wheel_dir.glob("omnis_api-*.whl")
    run(
        "locked dependency export",
        [uv, "export", "--locked", "--no-config", "--directory", str(root),
         "--no-dev", "--no-emit-project", "--format", "requirements-txt",
         "--output-file", str(requirements)],
    )
    run("isolated venv", [uv, "venv", "--no-python-downloads", "--python", "3.13.15", str(tmp_path / "venv")])
    run("locked dependency install", [uv, "pip", "sync", "--python", str(venv_python),
                                      "--require-hashes", str(requirements)])
    run("wheel install", [uv, "pip", "install", "--python", str(venv_python),
                          "--no-deps", str(wheel)])
    run("installed dependency check", [uv, "pip", "check", "--python", str(venv_python)])
    run(
        "installed migration",
        [str(venv_python), "-I", "-m", "omnis.migrate"],
        isolated_migration=True,
    )
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (SCHEMA_REVISION,)
        assert connection.execute(
            "SELECT admission_open, generation FROM instance_control WHERE id = 1"
        ).fetchone() == (False, 0)


@pytest.mark.parametrize("marker", ["synthetic_migration_password_marker", "synthetic_malformed_url_marker"])
def test_failed_migration_does_not_echo_database_input(marker):
    database_url = (
        f"postgresql+psycopg://omnis_test:{marker}@127.0.0.1:1/omnis_test"
        if "password" in marker else marker
    )
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-m", "omnis.migrate"],
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_DATABASE_URL": database_url,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("Failed migration exceeded its deadline", pytrace=False)
    assert result.returncode != 0
    if marker in result.stdout + result.stderr:
        pytest.fail("Migration failure exposed database configuration", pytrace=False)


def test_migration_rejects_ambient_libpq_routing_before_connecting():
    result = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": "postgresql+psycopg://omnis_test:synthetic@127.0.0.1:1/omnis_test",
            "PGHOSTADDR": "127.0.0.2",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "Ambient libpq" in result.stderr


def test_migration_rejects_database_url_query_overrides_before_connecting():
    result = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": (
                "postgresql+psycopg://omnis_test:synthetic@127.0.0.1:1/omnis_test?host=127.0.0.2"
            ),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "query parameters are forbidden" in result.stderr


def test_migration_job_exits_when_schema_lock_is_held(migrated_database_url, tmp_path):
    with connect_test_database(migrated_database_url) as blocker:
        blocker.execute("LOCK TABLE alembic_version IN ACCESS EXCLUSIVE MODE")
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-m", "omnis.migrate"],
                cwd=tmp_path,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "OMNIS_DATABASE_URL": migrated_database_url.render_as_string(hide_password=False),
                },
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except subprocess.TimeoutExpired:
            pytest.fail("Migration job exceeded its bounded DB wait", pytrace=False)

    assert completed.returncode != 0
