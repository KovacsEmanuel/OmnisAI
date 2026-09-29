"""Test-only guard before creating or dropping any PostgreSQL database."""

import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

from conftest import connect_test_database, verify_host_loopback_route, verify_test_database


def test_host_loopback_route_preflight_has_positive_and_negative_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Route:
        def __init__(self, value: str) -> None:
            self.value = value

        def read_text(self) -> str:
            return self.value

    routes = [Route("0"), Route("0")]
    monkeypatch.setattr(Path, "glob", lambda *_args: routes)
    verify_host_loopback_route()
    routes[1].value = "1"
    with pytest.raises(RuntimeError, match="Host loopback route"):
        verify_host_loopback_route()


def test_fixture_accepts_only_attested_host_loopback_without_docker_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = "omnis-p01-synthetic-host-only"
    port = 54329
    monkeypatch.setenv("OMNIS_TEST_PROJECT", project)
    monkeypatch.setenv("OMNIS_TEST_DB_PORT", str(port))
    url = make_url(f"postgresql+psycopg://omnis_test:synthetic@127.0.0.1:{port}/omnis_test")
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        endpoint = Path(name) / "daemon.sock"
        with socket.socket(socket.AF_UNIX) as local:
            local.bind(str(endpoint))
            for variant in ("safe", "published", "privileged", "extra-cap"):

                def fake_run(
                    command: list[str], *, variant_now: str = variant, **_kwargs: object
                ) -> subprocess.CompletedProcess[str]:
                    if command == ["docker", "context", "show"]:
                        return subprocess.CompletedProcess(command, 0, "synthetic-local\n", "")
                    if command[:3] == ["docker", "context", "inspect"]:
                        return subprocess.CompletedProcess(command, 0, f"unix://{endpoint}\n", "")
                    if "ps" in command and "--format" in command:
                        publishers = (
                            [
                                {
                                    "URL": "127.0.0.1",
                                    "TargetPort": 5432,
                                    "PublishedPort": port,
                                    "Protocol": "tcp",
                                }
                            ]
                            if variant_now == "published"
                            else []
                        )
                        service = {
                            "ID": "owned-synthetic-db",
                            "Project": project,
                            "Service": "db",
                            "State": "running",
                            "Image": "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650",
                            "Publishers": publishers,
                        }
                        return subprocess.CompletedProcess(
                            command, 0, json.dumps(service) + "\n", ""
                        )
                    if command[:3] == ["docker", "inspect", "owned-synthetic-db"]:
                        mounts = [
                            {
                                "Type": "volume",
                                "Name": f"{project}_pgdata",
                                "Destination": "/var/lib/postgresql",
                            }
                        ]
                        host = {
                            "NetworkMode": "host",
                            "PortBindings": {},
                            "Privileged": variant_now == "privileged",
                            "CapAdd": ["SYS_ADMIN"] if variant_now == "extra-cap" else None,
                        }
                        tcp = {"5432/tcp": None}
                        cmd = [
                            "postgres",
                            "-c",
                            "listen_addresses=127.0.0.1",
                            "-c",
                            f"port={port}",
                        ]
                        inspected = "\n".join(
                            json.dumps(value) for value in (mounts, host, tcp, cmd)
                        )
                        return subprocess.CompletedProcess(command, 0, inspected, "")
                    pytest.fail("Unexpected Docker CLI command", pytrace=False)

                with monkeypatch.context() as scoped:
                    scoped.setattr(subprocess, "run", fake_run)
                    scoped.setattr("conftest.verify_host_loopback_route", lambda: None)
                    if variant != "safe":
                        with pytest.raises(RuntimeError, match="dedicated test project"):
                            verify_test_database(url)
                    else:
                        verify_test_database(url)


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
