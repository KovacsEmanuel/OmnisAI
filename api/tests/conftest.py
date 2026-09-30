"""Dedicated PostgreSQL fixture; refuse an arbitrary operator database."""

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


@pytest.fixture
def ipc_directory() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="omnis-ipc-", dir=os.environ["TMPDIR"]) as name:
        yield Path(name)


def reject_ambient_libpq_config() -> None:
    if any(name.startswith("PG") for name in os.environ):
        raise RuntimeError(
            "Ambient libpq configuration is forbidden for the dedicated test project"
        )


class FixtureReceipt(BaseModel):
    """Public fields from the shared, fail-closed disposable-fixture attestor."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1]
    project: str
    socket_directory: str
    system_identifier: str = Field(pattern=r"^[0-9]+$")
    container_id: str = Field(pattern=r"^[0-9a-f]{64}$")


def verify_test_database(url: URL) -> FixtureReceipt:
    reject_ambient_libpq_config()
    if any(name.startswith(("DOCKER_", "COMPOSE_")) for name in os.environ):
        raise RuntimeError("Only a local Docker context is allowed for test databases")
    project = os.environ.get("OMNIS_TEST_PROJECT", "")
    socket_directory = os.environ.get("OMNIS_TEST_SOCKET_DIR", "")
    fixture = Path(os.environ.get("OMNIS_TEST_FIXTURE", ""))
    if (
        not re.fullmatch(r"omnis-p01-[a-z0-9-]+", project)
        or not Path(socket_directory).is_absolute()
        or not fixture.is_absolute()
        or url.drivername != "postgresql+psycopg"
        or url.host != quote(socket_directory, safe="")
        or url.username != "omnis_test"
        or url.database != "omnis_test"
        or url.port not in (None, 5432)
        or not url.password
        or url.query
    ):
        raise RuntimeError("Expected a dedicated test project private database URL")
    script = Path(__file__).resolve().parents[2] / "ops/run_test_db_gate.py"
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(script), "--attest", str(fixture)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        receipt = FixtureReceipt.model_validate_json(result.stdout, strict=True)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise RuntimeError("Cannot verify dedicated test project") from None
    if receipt.project != project or receipt.socket_directory != socket_directory:
        raise RuntimeError("Receipt does not match the dedicated test project")
    return receipt


def connect_test_database(
    url: URL, *, autocommit: bool = False
) -> psycopg.Connection[tuple[object, ...]]:
    receipt = verify_test_database(url.set(database="omnis_test"))
    if url.database != "omnis_test" and not re.fullmatch(
        r"omnis_p01_[0-9a-f]{32}", url.database or ""
    ):
        raise RuntimeError("Expected a dedicated test project database name")
    try:
        connection: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
            host=receipt.socket_directory,
            port=5432,
            user=url.username,
            password=url.password,
            dbname=url.database,
            connect_timeout=3,
            options="-c statement_timeout=3000 -c lock_timeout=3000",
            autocommit=autocommit,
        )
    except psycopg.Error:
        raise RuntimeError("Dedicated PostgreSQL test database is unavailable") from None
    try:
        actual = connection.execute("SELECT system_identifier FROM pg_control_system()").fetchone()
        if actual is None or str(actual[0]) != receipt.system_identifier:
            raise RuntimeError("Dedicated PostgreSQL cluster identity mismatch")
    except (psycopg.Error, RuntimeError):
        connection.close()
        raise RuntimeError("Cannot verify dedicated PostgreSQL cluster identity") from None
    return connection


@pytest.fixture
def empty_database_url() -> Iterator[URL]:
    raw = os.environ.get("OMNIS_TEST_DATABASE_URL")
    if not raw:
        pytest.fail("OMNIS_TEST_DATABASE_URL is required for PostgreSQL tests")
    try:
        url = make_url(raw)
    except ArgumentError:
        raise RuntimeError("Invalid dedicated PostgreSQL test URL") from None
    verify_test_database(url)

    name = f"omnis_p01_{uuid4().hex}"
    with connect_test_database(url, autocommit=True) as connection:
        verify_test_database(url)
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield url.set(database=name)
    finally:
        verify_test_database(url)
        with connect_test_database(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def migrated_database_url(empty_database_url: URL) -> URL:
    verify_test_database(empty_database_url.set(database="omnis_test"))
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
        pytest.fail("Dedicated migration fixture timed out", pytrace=False)
    assert completed.returncode == 0, f"migration failed (exit {completed.returncode})"
    return empty_database_url
