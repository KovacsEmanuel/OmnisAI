"""Dedicated PostgreSQL fixture; refuse an arbitrary operator database."""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url


@pytest.fixture
def empty_database_url():
    raw = os.environ.get("OMNIS_TEST_DATABASE_URL")
    if not raw:
        pytest.fail("OMNIS_TEST_DATABASE_URL is required for PostgreSQL tests")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.username != "omnis_test"
        or url.database != "omnis_test"
        or url.port is None
    ):
        pytest.fail("Test URL must point to a dedicated loopback omnis_test database")

    name = f"omnis_p01_{uuid4().hex}"
    admin = url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield url.set(database=name)
    finally:
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
