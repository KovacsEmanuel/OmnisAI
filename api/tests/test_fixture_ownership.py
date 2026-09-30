"""Test-only guard before creating or dropping any PostgreSQL database."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import URL, make_url

from conftest import connect_test_database, verify_test_database


def test_compose_fixture_has_no_network_or_published_port_and_only_private_binds() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        root = Path(name)
        data, shared = root / "data", root / "socket"
        data.mkdir(mode=0o700)
        shared.mkdir(mode=0o700)
        password = root / "password"
        password.write_text("synthetic-only")
        password.chmod(0o600)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_TEST_PROJECT": "omnis-p01-synthetic-private-uds",
            "OMNIS_TEST_UID": str(os.getuid()),
            "OMNIS_TEST_GID": str(os.getgid()),
            "OMNIS_TEST_DATA_DIR": str(data),
            "OMNIS_TEST_SOCKET_DIR": str(shared),
            "OMNIS_TEST_PASSWORD_FILE": str(password),
        }
        completed = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(Path(__file__).resolve().parents[2] / "ops/compose.test.yaml"),
                "config",
                "--no-normalize",
                "--format",
                "json",
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert completed.returncode == 0, "private fixture Compose contract did not render"
        rendered = json.loads(completed.stdout)
        assert set(rendered["services"]) == {"db"}
        service = rendered["services"]["db"]
        assert service["network_mode"] == "none"
        assert service.get("ports") in (None, [])
        assert service.get("networks") in (None, [])
        assert service.get("privileged") in (None, False)
        assert service.get("cap_add") in (None, [])
        assert service.get("tmpfs") in (None, [])
        assert service.get("secrets") in (None, [])
        assert service.get("configs") in (None, [])
        assert service.get("devices") in (None, [])
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert (
            service["image"]
            == "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
        )
        assert service["pull_policy"] == "never"
        assert service["environment"] == {
            "POSTGRES_USER": "omnis_test",
            "POSTGRES_DB": "omnis_test",
            "POSTGRES_PASSWORD_FILE": "/run/omnis-db-password",
            "POSTGRES_INITDB_ARGS": "--auth-local=scram-sha-256 --auth-host=scram-sha-256",
        }
        assert service["healthcheck"]["test"] == [
            "CMD",
            "pg_isready",
            "-h",
            "/var/run/postgresql",
            "-U",
            "omnis_test",
            "-d",
            "omnis_test",
        ]
        assert service["user"] == f"{os.getuid()}:{os.getgid()}"
        # Compose's config renderer omits false bind options. Check the source
        # declaration here; the opt-in runner also probes a missing bind live.
        source = (Path(__file__).resolve().parents[2] / "ops/compose.test.yaml").read_text()
        assert source.count("          create_host_path: false") == 3
        assert "create_host_path: true" not in source
        mounts = {
            (
                item["type"],
                item["source"],
                item["target"],
                item.get("read_only", False),
            )
            for item in service["volumes"]
        }
        assert mounts == {
            ("bind", str(data), "/var/lib/postgresql", False),
            ("bind", str(shared), "/var/run/postgresql", False),
            ("bind", str(password), "/run/omnis-db-password", True),
        }
        assert service["command"] == [
            "postgres",
            "-c",
            "listen_addresses=",
            "-c",
            "unix_socket_directories=/var/run/postgresql",
            "-c",
            "unix_socket_permissions=0600",
        ]


def test_private_uds_receipt_is_required_before_fixture_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from urllib.parse import quote

    project = "omnis-p01-synthetic-uds"
    socket_dir = "/run/omnis-synthetic/socket"
    monkeypatch.setenv("OMNIS_TEST_PROJECT", project)
    monkeypatch.setenv("OMNIS_TEST_SOCKET_DIR", socket_dir)
    monkeypatch.setenv("OMNIS_TEST_FIXTURE", "/run/omnis-synthetic/fixture.json")
    url = make_url(
        f"postgresql+psycopg://omnis_test:synthetic@{quote(socket_dir, safe='')}/omnis_test"
    )
    receipts = [
        {
            "schema_version": 1,
            "project": project,
            "socket_directory": socket_dir,
            "system_identifier": "123456789",
            "container_id": "a" * 64,
        }
    ]

    def attest(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert "--attest" in command
        return subprocess.CompletedProcess(command, 0, json.dumps(receipts[0]), "")

    monkeypatch.setattr(subprocess, "run", attest)
    verify_test_database(url)
    receipts[0]["project"] = "omnis-p01-foreign"
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_rejects_a_different_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv("OMNIS_TEST_PROJECT", "omnis-p01-unowned")
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_rejects_a_mismatched_unix_socket_port() -> None:
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


def test_failed_attestation_is_rejected_before_the_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])

    def refused(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert "--attest" in command
        raise subprocess.CalledProcessError(2, command, output="PRIVATE_DB_ATTESTATION_BLOCKED")

    monkeypatch.setattr(subprocess, "run", refused)
    monkeypatch.setattr(
        psycopg, "connect", lambda *args, **kwargs: pytest.fail("driver called", pytrace=False)
    )
    with pytest.raises(RuntimeError, match="dedicated test project"):
        connect_test_database(url)


def test_connection_rejects_a_mismatched_cluster_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    original_run = subprocess.run

    def fake_cluster_read(
        command: list[str], *, capture_output: bool, text: bool, timeout: int, check: bool
    ) -> subprocess.CompletedProcess[str]:
        assert text is True
        result = original_run(
            command, capture_output=capture_output, text=True, timeout=timeout, check=check
        )
        if "--attest" in command:
            receipt = json.loads(result.stdout)
            receipt["system_identifier"] = "0"
            return subprocess.CompletedProcess(command, 0, json.dumps(receipt), "")
        return result

    monkeypatch.setattr(subprocess, "run", fake_cluster_read)
    with pytest.raises(RuntimeError, match="cluster identity"):
        with connect_test_database(url):
            pass


def test_owned_uds_fixture_creates_and_drops_only_its_generated_database(
    empty_database_url: URL,
) -> None:
    with connect_test_database(empty_database_url, autocommit=True) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            empty_database_url.database,
        )
        connection.execute("CREATE TABLE fixture_canary (value text NOT NULL)")
        connection.execute("INSERT INTO fixture_canary VALUES ('synthetic-only')")
    with connect_test_database(empty_database_url) as connection:
        assert connection.execute("SELECT value FROM fixture_canary").fetchone() == (
            "synthetic-only",
        )


def test_accepts_only_its_own_running_compose_database() -> None:
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    verify_test_database(url)
    with connect_test_database(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == ("omnis_test",)
