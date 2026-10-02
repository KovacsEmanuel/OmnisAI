import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import URL

from conftest import connect_test_database, verify_test_database
from omnis.core.db import SCHEMA_REVISION
from process_probe import exercise_installed_control


def test_startup_migration_refuses_wrong_cluster_before_ddl(empty_database_url: URL) -> None:
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate", "--initialize"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
            "OMNIS_EXPECTED_SYSTEM_ID": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    with connect_test_database(empty_database_url) as connection:
        tables = connection.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        ).fetchone()
    assert completed.returncode != 0, "Startup must reject a different connected cluster"
    assert tables == (0,), "Identity must be checked before any migration DDL"


def run_startup_migration(url: URL, identity: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate", "--initialize"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": url.render_as_string(hide_password=False),
            "OMNIS_EXPECTED_SYSTEM_ID": identity,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_startup_migration_only_initializes_empty_schema(empty_database_url: URL) -> None:
    identity = verify_test_database(empty_database_url.set(database="omnis_test")).system_identifier
    first = run_startup_migration(empty_database_url, identity)
    assert first.returncode == 0, "Verified empty database must initialize"
    with connect_test_database(empty_database_url) as connection:
        before = connection.execute("SELECT * FROM instance_control").fetchall()
        connection.execute("UPDATE alembic_version SET version_num = 'future_revision'")
    second = run_startup_migration(empty_database_url, identity)
    assert second.returncode != 0
    assert "Explicit update/backup required" in second.stderr
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT * FROM instance_control").fetchall() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "future_revision",
        )


def test_startup_migration_serializes_with_dedicated_db_lock(empty_database_url: URL) -> None:
    identity = verify_test_database(empty_database_url.set(database="omnis_test")).system_identifier
    with connect_test_database(empty_database_url) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(5714308421745685321)")
        blocked = run_startup_migration(empty_database_url, identity)
        assert blocked.returncode != 0
        assert "migration failed or timed out" in blocked.stderr
        assert connection.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        ).fetchone() == (0,)
    assert run_startup_migration(empty_database_url, identity).returncode == 0


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT lo_from_bytea(0, decode('0102', 'hex'))",
        'CREATE COLLATION public.synthetic_existing FROM pg_catalog."C"',
        "CREATE PUBLICATION synthetic_existing",
        "CREATE FOREIGN DATA WRAPPER synthetic_existing",
    ],
)
def test_startup_migration_rejects_non_table_database_objects(
    empty_database_url: URL, sql: str
) -> None:
    identity = verify_test_database(empty_database_url.set(database="omnis_test")).system_identifier
    with connect_test_database(empty_database_url) as connection:
        connection.execute(sql)
    result = run_startup_migration(empty_database_url, identity)
    assert result.returncode != 0, "An existing non-table object is not an empty database"
    assert "Explicit update/backup required" in result.stderr
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        ).fetchone() == (0,)


def test_migration_creates_closed_instance_on_empty_postgres(empty_database_url: URL) -> None:
    script = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    )
    assert script.get_current_head() == SCHEMA_REVISION
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        ).fetchone() == (0,)

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
    assert revision == (SCHEMA_REVISION,)
    assert len(rows) == 1
    identity, admission_open, shutdown_command_id, generation, quiesced_generation, quiesced_at = (
        rows[0]
    )
    assert isinstance(identity, UUID)
    assert admission_open is False
    assert shutdown_command_id is None
    assert generation == 0
    assert quiesced_generation is None
    assert quiesced_at is None


def test_installed_wheel_migrates_without_checkout(empty_database_url: URL, tmp_path: Path) -> None:
    uv = os.environ.get("OMNIS_UV")
    assert uv, "OMNIS_UV must point to pinned uv 0.12.19"
    root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    requirements = tmp_path / "requirements.txt"
    venv_python = tmp_path / "venv/bin/python"

    def run(label: str, command: list[str], *, isolated_migration: bool = False) -> None:
        env = None
        if isolated_migration:
            env = {
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
            }
        try:
            result = subprocess.run(
                command,
                cwd=tmp_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"{label} exceeded its deadline", pytrace=False)
        if result.returncode:
            pytest.fail(f"{label} failed (exit {result.returncode})", pytrace=False)

    run(
        "wheel build",
        [uv, "build", "--no-config", "--wheel", str(root), "--out-dir", str(wheel_dir)],
    )
    (wheel,) = wheel_dir.glob("omnis_api-*.whl")
    run(
        "locked dependency export",
        [
            uv,
            "export",
            "--locked",
            "--no-config",
            "--directory",
            str(root),
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
    )
    run(
        "isolated venv",
        [uv, "venv", "--no-python-downloads", "--python", "3.13.15", str(tmp_path / "venv")],
    )
    run(
        "locked dependency install",
        [uv, "pip", "sync", "--python", str(venv_python), "--require-hashes", str(requirements)],
    )
    run(
        "wheel install",
        [uv, "pip", "install", "--python", str(venv_python), "--no-deps", str(wheel)],
    )
    run("installed dependency check", [uv, "pip", "check", "--python", str(venv_python)])
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            empty_database_url.database,
        )
    run(
        "installed migration",
        [str(venv_python), "-I", "-m", "omnis.migrate"],
        isolated_migration=True,
    )
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            SCHEMA_REVISION,
        )
        assert connection.execute(
            "SELECT admission_open, generation FROM instance_control WHERE id = 1"
        ).fetchone() == (False, 0)
    exercise_installed_control(venv_python, empty_database_url)


@pytest.mark.parametrize(
    "previous_revision",
    [
        "0001_instance_control",
        "0002_local_sessions",
        "0003_instance_lifecycle",
        "0004_pairing_receipts",
    ],
)
def test_upgrade_from_previous_revision_preserves_instance_identity(
    empty_database_url: URL, tmp_path: Path, previous_revision: str
) -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
    }
    root = Path(__file__).resolve().parents[1]
    verify_test_database(empty_database_url.set(database="omnis_test"))
    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(root / "alembic.ini"),
            "upgrade",
            previous_revision,
        ],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert first.returncode == 0
    with connect_test_database(empty_database_url) as connection:
        before = connection.execute("SELECT * FROM instance_control").fetchone()
        if previous_revision != "0001_instance_control":
            connection.execute(
                "INSERT INTO ui_session VALUES ('synthetic_digest', clock_timestamp() + interval '12 hours')"
            )
            connection.execute(
                "UPDATE pairing_challenge SET digest = 'synthetic_pending_digest', expires_at = clock_timestamp() + interval '5 minutes'"
            )
    upgraded = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert upgraded.returncode == 0
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT * FROM instance_control").fetchone() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            SCHEMA_REVISION,
        )
        assert connection.execute("SELECT digest, attempts FROM pairing_challenge").fetchone() == (
            "synthetic_pending_digest" if previous_revision == "0004_pairing_receipts" else None,
            0,
        )
        assert connection.execute("SELECT count(*) FROM instance_stop_fence").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ui_session").fetchone() == (
            int(previous_revision != "0001_instance_control"),
        )


@pytest.mark.parametrize(
    "marker", ["synthetic_migration_password_marker", "synthetic_malformed_url_marker"]
)
def test_failed_migration_does_not_echo_database_input(
    marker: str, migrated_database_url: URL
) -> None:
    if "password" in marker:
        if marker == os.environ["OMNIS_TEST_DB_PASSWORD"]:
            pytest.fail("Test password unexpectedly equals denial marker", pytrace=False)
        verify_test_database(migrated_database_url.set(database="omnis_test"))
        database_url = migrated_database_url.set(password=marker).render_as_string(
            hide_password=False
        )
    else:
        database_url = marker
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


def test_migration_rejects_ambient_libpq_routing_before_connecting() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": "sqlite:///synthetic-do-not-open.db",
            "PGHOSTADDR": "127.0.0.2",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "Ambient libpq" in result.stderr


def test_migration_rejects_database_url_query_overrides_before_connecting() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.migrate"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": "sqlite:///synthetic-do-not-open.db?host=127.0.0.2",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "query parameters are forbidden" in result.stderr


def test_migration_job_exits_when_schema_lock_is_held(
    migrated_database_url: URL, tmp_path: Path
) -> None:
    with connect_test_database(migrated_database_url) as blocker:
        blocker.execute("LOCK TABLE alembic_version IN ACCESS EXCLUSIVE MODE")
        verify_test_database(migrated_database_url.set(database="omnis_test"))
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-m", "omnis.migrate"],
                cwd=tmp_path,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "OMNIS_DATABASE_URL": migrated_database_url.render_as_string(
                        hide_password=False
                    ),
                },
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except subprocess.TimeoutExpired:
            pytest.fail("Migration job exceeded its bounded DB wait", pytrace=False)

    assert completed.returncode != 0
