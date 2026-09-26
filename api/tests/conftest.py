"""Dedicated PostgreSQL fixture; refuse an arbitrary operator database."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def reject_ambient_libpq_config() -> None:
    if any(name.startswith("PG") for name in os.environ):
        raise RuntimeError("Ambient libpq configuration is forbidden for the dedicated test project")


def verify_test_database(url: URL) -> None:
    reject_ambient_libpq_config()
    project = os.environ.get("OMNIS_TEST_PROJECT", "")
    if not re.fullmatch(r"omnis-p01-[a-z0-9-]+", project):
        raise RuntimeError("Expected a dedicated test project")
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.username != "omnis_test"
        or url.database != "omnis_test"
        or url.port is None
        or url.query
    ):
        raise RuntimeError("Expected a dedicated test project database URL")

    compose = ["docker", "compose", "-f", str(Path(__file__).resolve().parents[2] / "ops/compose.test.yaml")]
    try:
        result = subprocess.run(
            [*compose, "ps", "--format", "json"], capture_output=True, text=True,
            timeout=10, check=True,
        )
        services = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if len(services) != 1:
            raise ValueError("unexpected service count")
        service = services[0]
        cid = service["ID"]
        mounts = subprocess.run(
            ["docker", "inspect", cid, "--format", "{{json .Mounts}}"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        volume = json.loads(mounts.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError):
        raise RuntimeError("Cannot verify dedicated test project") from None

    if not (
        service["Project"] == project
        and service["Service"] == "db"
        and service["State"] == "running"
        and service["Image"] == "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
        and service["Publishers"] == [
            {"URL": "127.0.0.1", "TargetPort": 5432, "PublishedPort": url.port, "Protocol": "tcp"}
        ]
        and any(
            mount["Type"] == "volume"
            and mount["Name"] == f"{project}_pgdata"
            and mount["Destination"] == "/var/lib/postgresql"
            for mount in volume
        )
    ):
        raise RuntimeError("Database URL does not belong to the dedicated test project")


def connect_test_database(url: URL, *, autocommit=False):
    reject_ambient_libpq_config()
    if url.query:
        raise RuntimeError("Expected a dedicated test project database URL")
    try:
        return psycopg.connect(
            url.set(drivername="postgresql").render_as_string(hide_password=False),
            autocommit=autocommit,
        )
    except psycopg.Error:
        raise RuntimeError("Dedicated PostgreSQL test database is unavailable") from None


@pytest.fixture
def empty_database_url():
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
def migrated_database_url(empty_database_url):
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
