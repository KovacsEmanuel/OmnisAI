"""Test-only guard before creating or dropping any PostgreSQL database."""

import os
import subprocess

import psycopg
import pytest
from sqlalchemy.engine import make_url

from conftest import connect_test_database, verify_test_database


def test_rejects_a_different_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv("OMNIS_TEST_PROJECT", "omnis-p01-unowned")
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_rejects_a_mismatched_published_port() -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).set(port=1)
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


@pytest.mark.parametrize("override", ["host", "port", "dbname", "user"])
def test_rejects_uri_query_overrides_before_connecting(override: str) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).update_query_dict(
        {override: "foreign.invalid" if override == "host" else "1"}
    )
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_connection_helper_cannot_use_an_overridden_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).update_query_dict(
        {"host": "foreign.invalid"}
    )
    monkeypatch.setattr(
        psycopg, "connect", lambda *args, **kwargs: pytest.fail("driver called", pytrace=False)
    )
    with pytest.raises(RuntimeError, match="dedicated test project"):
        connect_test_database(url)


@pytest.mark.parametrize("name", ["PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPORT"])
def test_rejects_ambient_libpq_redirection_before_driver(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv(name, "127.0.0.2" if name == "PGHOSTADDR" else "untrusted")
    monkeypatch.setattr(
        psycopg, "connect", lambda *args, **kwargs: pytest.fail("driver called", pytrace=False)
    )
    with pytest.raises(RuntimeError, match="Ambient libpq"):
        verify_test_database(url)
    with pytest.raises(RuntimeError, match="Ambient libpq"):
        connect_test_database(url)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DOCKER_HOST", "tcp://203.0.113.9:2375"),
        ("DOCKER_CONTEXT", "remote"),
        ("DOCKER_CONFIG", "/untrusted/docker-config"),
    ],
)
def test_rejects_remote_docker_settings_before_cli(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("Docker CLI called", pytrace=False)
    )
    with pytest.raises(RuntimeError, match="local Docker"):
        verify_test_database(url)


def test_rejects_remote_active_context_before_fixture_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command == ["docker", "context", "show"]:
            return subprocess.CompletedProcess(command, 0, "remote\n", "")
        if command[:3] == ["docker", "context", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "tcp://203.0.113.9:2375\n", "")
        pytest.fail("Fixture inspected a service through a remote daemon", pytrace=False)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="local Docker"):
        verify_test_database(url)


def test_connection_rejects_a_mismatched_cluster_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    original_run = subprocess.run

    def fake_cluster_read(
        command: list[str], *, capture_output: bool, text: bool, timeout: int, check: bool
    ) -> subprocess.CompletedProcess[str]:
        if "exec" in command and any("pg_control_system()" in str(part) for part in command):
            return subprocess.CompletedProcess(command, 0, "0\n", "")
        assert text is True
        return original_run(
            command, capture_output=capture_output, text=True, timeout=timeout, check=check
        )

    monkeypatch.setattr(subprocess, "run", fake_cluster_read)
    with pytest.raises(RuntimeError, match="cluster identity"):
        with connect_test_database(url):
            pass


def test_accepts_only_its_own_running_compose_database() -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    verify_test_database(url)
    with connect_test_database(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == ("omnis_test",)
