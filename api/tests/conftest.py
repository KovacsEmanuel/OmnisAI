"""Dedicated PostgreSQL fixture; refuse an arbitrary operator database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def connect_test_database(url: URL, *, autocommit=False):
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
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.username != "omnis_test"
        or url.database != "omnis_test"
        or url.port is None
    ):
        pytest.fail("Test URL must point to a dedicated loopback omnis_test database")

    name = f"omnis_p01_{uuid4().hex}"
    with connect_test_database(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield url.set(database=name)
    finally:
        with connect_test_database(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def migrated_database_url(empty_database_url):
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
    return empty_database_url
