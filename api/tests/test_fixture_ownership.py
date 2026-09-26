"""Test-only guard before creating or dropping any PostgreSQL database."""

import os

import psycopg
import pytest
from sqlalchemy.engine import make_url

from conftest import connect_test_database, verify_test_database


def test_rejects_a_different_compose_project(monkeypatch):
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv("OMNIS_TEST_PROJECT", "omnis-p01-unowned")
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_rejects_a_mismatched_published_port():
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).set(port=1)
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


@pytest.mark.parametrize("override", ["host", "port", "dbname", "user"])
def test_rejects_uri_query_overrides_before_connecting(override):
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).update_query_dict(
        {override: "foreign.invalid" if override == "host" else "1"}
    )
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_connection_helper_cannot_use_an_overridden_destination(monkeypatch):
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).update_query_dict(
        {"host": "foreign.invalid"}
    )
    monkeypatch.setattr(
        psycopg, "connect", lambda *args, **kwargs: pytest.fail("driver called", pytrace=False)
    )
    with pytest.raises(RuntimeError, match="dedicated test project"):
        connect_test_database(url)


@pytest.mark.parametrize("name", ["PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPORT"])
def test_rejects_ambient_libpq_redirection_before_driver(monkeypatch, name):
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv(name, "127.0.0.2" if name == "PGHOSTADDR" else "untrusted")
    monkeypatch.setattr(
        psycopg, "connect", lambda *args, **kwargs: pytest.fail("driver called", pytrace=False)
    )
    with pytest.raises(RuntimeError, match="Ambient libpq"):
        verify_test_database(url)
    with pytest.raises(RuntimeError, match="Ambient libpq"):
        connect_test_database(url)


def test_accepts_only_its_own_running_compose_database():
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    verify_test_database(url)
