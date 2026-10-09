"""Upgrade only on the parent's attested disposable PostgreSQL fixture."""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import URL

from conftest import connect_test_database, verify_test_database


def test_pg_managed_upgrade_0010_and_record_immutability(empty_database_url: URL) -> None:
    root = Path(__file__).resolve().parents[1]
    for revision in ("0010_catalog_publications", "0011_managed_tasks"):
        verify_test_database(empty_database_url.set(database="omnis_test"))
        completed = subprocess.run(
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
            text=True,
            timeout=30,
            check=False,
        )
        assert completed.returncode == 0, f"managed migration failed exit={completed.returncode}"
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0011_managed_tasks",
        )
        rows = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'managed_%' ORDER BY tablename"
        ).fetchall()
        assert rows == [
            ("managed_inbox",),
            ("managed_record",),
            ("managed_run",),
            ("managed_task",),
        ]
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            connection.execute("TRUNCATE managed_record CASCADE")
        connection.rollback()
        assert connection.execute("SELECT count(*) FROM managed_record").fetchone() == (0,)
