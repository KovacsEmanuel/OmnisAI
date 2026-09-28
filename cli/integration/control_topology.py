"""Opt-in, disposable exercise of the installed P0 control topology."""

import os
import hashlib
import json
import platform
import secrets
import socket
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from omnis_cli.compose import _BASE, _checked_socket, _docker_id, _one_image, _preflight, _record, _validate_image
from omnis_cli.instance import private_dir
from omnis_cli.release import _installed_pointer, _manifest

_POSTGRES = "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"


def strict_probe_environment() -> None:
    """Never let ambient Docker/Compose/libpq redirect a disposable probe."""
    if any(key.startswith(("DOCKER_", "COMPOSE_", "PG")) for key in os.environ):
        raise ValueError("Ambient Docker, Compose or libpq overrides are forbidden")


def preflight_port(port: int) -> None:
    """A foreign listener is never evidence of our API; fail before Compose."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid loopback port")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        raise ValueError("Loopback port occupied") from None


def _docker(host: str, *args: str, cwd: Path, env: dict[str, str] | None = None,
            timeout: int = 20, success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", "--host", host, *args], cwd=cwd,
        env=env or {"PATH": os.environ.get("PATH", "")},
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if success and result.returncode:
        raise AssertionError(f"Docker {args[0]} failed with exit {result.returncode}")
    return result


def _compose(host: str, release: Path, project: str, empty_env: Path,
             env: dict[str, str], *args: str, timeout: int = 90,
             success: bool = True) -> subprocess.CompletedProcess[str]:
    return _docker(
        host, "compose", "--project-name", project,
        "--env-file", str(empty_env), "-f", str(release / "ops/compose.yaml"),
        *args, cwd=empty_env.parent, env=env, timeout=timeout, success=success,
    )


def _inspect(host: str, ident: str, scratch: Path) -> dict[str, object] | None:
    response = _docker(host, "container", "inspect", ident, cwd=scratch, success=False)
    if response.returncode:
        if "No such" in response.stderr:
            return None
        raise AssertionError("Container inspection unavailable")
    raw = json.loads(response.stdout)
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise AssertionError("Invalid container inspection")
    return raw[0]


def _owned_container(host: str, ident: str, scratch: Path, project: str,
                     image_id: str, state_root: Path, port: int) -> dict[str, object]:
    item = _inspect(host, ident, scratch)
    if item is None:
        raise AssertionError("Owned container missing")
    config = item["Config"]
    labels = config["Labels"]
    service = labels.get("com.docker.compose.service")
    expected = _POSTGRES if service == "db" else image_id
    if (
        labels.get("com.docker.compose.project") != project
        or service not in {"db", "api", "supervisor"}
        or config["Image"] != expected
        or item["Image"] != _expected_image_id(host, expected, scratch)
        or item["HostConfig"]["Privileged"] is not False
        or any(m.get("Destination") == "/var/run/docker.sock" for m in item["Mounts"])
    ):
        raise AssertionError("Foreign or incompatible container")
    mounts = item["Mounts"]
    ports = item["NetworkSettings"]["Ports"]
    if service == "db":
        if (
            not any(m["Type"] == "bind" and m["Source"] == str(state_root / "postgres")
                    and m["Destination"] == "/var/lib/postgresql" for m in mounts)
            or ports.get("5432/tcp")
        ):
            raise AssertionError("PostgreSQL bind or exposure mismatch")
    else:
        control = [m for m in mounts if m["Destination"] == "/run/omnis-control"]
        if (
            config["User"] != f"{os.getuid()}:{os.getgid()}"
            or len(control) != 1
            or control[0]["Source"] != str(state_root / "control")
            or control[0]["RW"] is (service == "api")
        ):
            raise AssertionError("Control UID or socket mount mismatch")
        if service == "api":
            exposed = ports.get("8765/tcp")
            if not exposed or len(exposed) != 1 or exposed[0] != {
                "HostIp": "127.0.0.1", "HostPort": str(port)
            }:
                raise AssertionError("API not bound solely to loopback")
        elif any(value for value in ports.values()):
            raise AssertionError("Supervisor port exposure")
    return item


def _expected_image_id(host: str, image: str, scratch: Path) -> str:
    response = _docker(host, "image", "inspect", image, cwd=scratch)
    return str(_one_image(response.stdout)["Id"])
