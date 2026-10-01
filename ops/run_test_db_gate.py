"""Private PG18.6 fixture lifecycle and canonical development gate.

Only a fresh scratch root is admitted. On every outcome, stop/remove the exact
attested container, retain PGDATA and the private synthetic password for recovery.
--check runs the full component gate; --probe-only never claims that gate passed.
"""

import argparse
import ctypes
import json
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

_IMAGE = (
    "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
)
_CMD = [
    "postgres",
    "-c",
    "listen_addresses=",
    "-c",
    "unix_socket_directories=/var/run/postgresql",
    "-c",
    "unix_socket_permissions=0600",
]
_COMPOSE = Path(__file__).resolve().with_name("compose.test.yaml")
_ROOT = _COMPOSE.parent.parent
_STOP_REQUESTED = False


class UnsafeFixture(ValueError):
    """A foreign or incompletely attested DB must never receive DDL."""


@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    socket: Path
    password: Path


def prepare_paths(root: Path) -> Paths:
    scratch = Path(os.environ["TMPDIR"]).resolve(strict=True)
    if (
        not root.is_absolute()
        or root.resolve() != root
        or scratch not in root.parents
        or root.exists()
        or len(os.fsencode(str(root / "socket" / ".s.PGSQL.5432"))) > 107
    ):
        raise UnsafeFixture("Only a new canonical scratch DB root is allowed")
    root.mkdir(mode=0o700)
    data, socket_dir, password = root / "data", root / "socket", root / "password"
    data.mkdir(mode=0o700)
    socket_dir.mkdir(mode=0o700)
    fd = os.open(password, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(secrets.token_hex(32) + "\n")
        output.flush()
        os.fsync(output.fileno())
    return Paths(root, data, socket_dir, password)


def _run(
    argv: list[str], env: dict[str, str], *, timeout: int = 20
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )


def _docker_endpoint(env: dict[str, str]) -> str:
    context = _run(["docker", "context", "show"], env)
    if context.returncode or not context.stdout.strip():
        raise UnsafeFixture("Local Docker context unavailable")
    endpoint = _run(
        [
            "docker",
            "context",
            "inspect",
            context.stdout.strip(),
            "--format",
            '{{(index .Endpoints "docker").Host}}',
        ],
        env,
    )
    if endpoint.returncode or not endpoint.stdout.strip().startswith("unix://"):
        raise UnsafeFixture("Only a local Docker Unix endpoint is allowed")
    path = Path(endpoint.stdout.strip()[7:]).resolve(strict=True)
    info = path.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid not in {0, os.getuid()}
        or info.st_mode & 0o002
    ):
        raise UnsafeFixture("Untrusted Docker endpoint")
    return f"unix://{path}"


def _private_file(path: Path, mode: int) -> None:
    info = path.lstat()
    if (
        info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != mode
        or (mode == 0o600 and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1))
        or (mode in (0o700, 0o3775) and not stat.S_ISDIR(info.st_mode))
    ):
        raise UnsafeFixture("Disposable fixture path lost private ownership")


def validate_compose_config(config: dict[str, object], paths: Paths | None = None) -> None:
    services = config.get("services")
    if not isinstance(services, dict) or set(services) != {"db"}:
        raise UnsafeFixture("Unexpected test DB service set")
    db = services["db"]
    if not isinstance(db, dict) or db.get("network_mode") != "none":
        raise UnsafeFixture("Test DB network must be none")
    if paths is None:
        raise UnsafeFixture("Expected private fixture paths")
    mounts = db.get("volumes")
    if not isinstance(mounts, list):
        raise UnsafeFixture("Expected exact private bind mounts")
    got = {
        (item.get("type"), item.get("source"), item.get("target"), item.get("read_only", False))
        for item in mounts
        if isinstance(item, dict)
    }
    expected = {
        ("bind", str(paths.data), "/var/lib/postgresql", False),
        ("bind", str(paths.socket), "/var/run/postgresql", False),
        ("bind", str(paths.password), "/run/omnis-db-password", True),
    }
    if db.get("environment") != {
        "POSTGRES_USER": "omnis_test",
        "POSTGRES_DB": "omnis_test",
        "POSTGRES_PASSWORD_FILE": "/run/omnis-db-password",
        "POSTGRES_INITDB_ARGS": "--auth-local=scram-sha-256 --auth-host=scram-sha-256",
    }:
        raise UnsafeFixture("Test DB authentication configuration mismatch")
    if (
        len(mounts) != len(expected)
        or got != expected
        or db.get("ports") not in (None, [])
        or db.get("networks") not in (None, [])
        or db.get("cap_add") not in (None, [])
        or db.get("privileged") not in (None, False)
        or db.get("security_opt") != ["no-new-privileges:true"]
        or db.get("entrypoint") not in (None, [])
        or any(
            db.get(key) not in (None, "") for key in ("pid", "ipc", "uts", "cgroup", "userns_mode")
        )
        or any(
            db.get(key) not in (None, [])
            for key in ("devices", "tmpfs", "secrets", "configs", "volumes_from", "expose")
        )
        or db.get("user") != f"{os.getuid()}:{os.getgid()}"
        or db.get("cap_drop") != ["ALL"]
        or db.get("pull_policy") != "never"
        or db.get("healthcheck", {}).get("test")
        != [
            "CMD",
            "pg_isready",
            "-h",
            "/var/run/postgresql",
            "-U",
            "omnis_test",
            "-d",
            "omnis_test",
        ]
        or db.get("command") != _CMD
        or db.get("image") != _IMAGE
        or db.get("read_only") is True  # Entrypoint needs ephemeral writable files.
    ):
        raise UnsafeFixture("Test DB Compose identity or confinement mismatch")


def _container(
    cid: str, docker: list[str], env: dict[str, str], paths: Paths, project: str, image_id: str
) -> dict[str, object]:
    inspected = _run([*docker, "inspect", cid], env)
    if inspected.returncode:
        raise UnsafeFixture("Owned DB container inspection unavailable")
    objects = json.loads(inspected.stdout)
    if not isinstance(objects, list) or len(objects) != 1:
        raise UnsafeFixture("Unexpected DB inspect response")
    obj = objects[0]
    host, cfg = obj["HostConfig"], obj["Config"]
    networks = obj["NetworkSettings"]["Networks"]
    mounts = {
        (item["Type"], item["Source"], item["Destination"], item["RW"]) for item in obj["Mounts"]
    }
    if not (
        obj["Id"] == cid
        and obj["Image"] == image_id
        and cfg["Labels"].get("com.docker.compose.project") == project
        and cfg["Labels"].get("com.docker.compose.service") == "db"
        and cfg.get("Entrypoint") == ["docker-entrypoint.sh"]
        and cfg["User"] == f"{os.getuid()}:{os.getgid()}"
        and cfg["Cmd"] == _CMD
        and host["NetworkMode"] == "none"
        and host["Privileged"] is False
        and host["PortBindings"] in ({}, None)
        and set(host["CapDrop"] or []) == {"ALL"}
        and host.get("CapAdd") in (None, [])
        and host.get("SecurityOpt") in (["no-new-privileges"], ["no-new-privileges:true"])
        and host.get("PidMode") in (None, "")
        and host.get("IpcMode") in (None, "private")
        and host.get("UTSMode") in (None, "")
        and host.get("UsernsMode") in (None, "")
        and host.get("CgroupnsMode") in (None, "private")
        and isinstance(networks, dict)
        and set(networks) <= {"none"}
        and all(
            endpoint.get("IPAddress") in (None, "")
            and endpoint.get("GlobalIPv6Address") in (None, "")
            and endpoint.get("Gateway") in (None, "")
            for endpoint in networks.values()
        )
        and mounts
        == {
            ("bind", str(paths.data), "/var/lib/postgresql", True),
            ("bind", str(paths.socket), "/var/run/postgresql", True),
            ("bind", str(paths.password), "/run/omnis-db-password", False),
        }
    ):
        raise UnsafeFixture("DB container identity, mounts or network changed")
    return obj


def _find_owned(docker: list[str], env: dict[str, str], project: str) -> list[str]:
    found = _run(
        [
            *docker,
            "ps",
            "-a",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.ID}}",
        ],
        env,
    )
    if found.returncode:
        raise UnsafeFixture("Cannot enumerate exact DB project")
    return [cid.strip() for cid in found.stdout.splitlines() if cid.strip()]


def _project_networks(docker: list[str], env: dict[str, str], project: str) -> list[str]:
    found = _run(
        [
            *docker,
            "network",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.ID}}",
        ],
        env,
    )
    if found.returncode:
        raise UnsafeFixture("Cannot enumerate disposable DB networks")
    return [value.strip() for value in found.stdout.splitlines() if value.strip()]


def cleanup_owned(
    cid: str,
    docker: list[str],
    env: dict[str, str],
    paths: Paths,
    project: str,
    image_id: str,
    daemon_id: str,
) -> bool:
    """Try every safe teardown step; a failed readback never means absent."""
    uncertain = False

    def attest() -> bool:
        nonlocal uncertain
        for _attempt in range(2):
            try:
                current = _run([*docker, "info", "--format", "{{.ID}}"], env, timeout=10)
                if current.returncode or current.stdout.strip() != daemon_id:
                    raise UnsafeFixture("Cleanup daemon identity changed")
                _container(cid, docker, env, paths, project, image_id)
                return True
            except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
                uncertain = True
        return False

    if attest():
        try:
            stopped = _run([*docker, "stop", "--time", "20", cid], env, timeout=30)
            if stopped.returncode:
                uncertain = True
        except (OSError, subprocess.TimeoutExpired):
            uncertain = True
    if attest():
        try:
            removed = _run([*docker, "rm", "-f", cid], env, timeout=20)
            if removed.returncode:
                uncertain = True
        except (OSError, subprocess.TimeoutExpired):
            uncertain = True

    absent = networks_absent = socket_absent = False
    try:
        inspected = _run([*docker, "inspect", cid, "--format", "{{.Id}}"], env, timeout=10)
        absent = inspected.returncode != 0 and f"No such object: {cid}" in inspected.stderr
        if not absent:
            uncertain = True
    except (OSError, subprocess.TimeoutExpired):
        uncertain = True
    try:
        listing = _run(
            [*docker, "ps", "-a", "--no-trunc", "--filter", f"id={cid}", "--format", "{{.ID}}"],
            env,
            timeout=10,
        )
        if listing.returncode or listing.stdout.strip():
            uncertain = True
    except (OSError, subprocess.TimeoutExpired):
        uncertain = True
    try:
        if _find_owned(docker, env, project):
            uncertain = True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        uncertain = True
    try:
        networks_absent = not _project_networks(docker, env, project)
        if not networks_absent:
            uncertain = True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        uncertain = True
    try:
        current = _run([*docker, "info", "--format", "{{.ID}}"], env, timeout=10)
        if current.returncode or current.stdout.strip() != daemon_id:
            uncertain = True
    except (OSError, subprocess.TimeoutExpired):
        uncertain = True
    try:
        (paths.socket / ".s.PGSQL.5432").lstat()
        uncertain = True
    except FileNotFoundError:
        socket_absent = True
    except OSError:
        uncertain = True
    print(
        f"OWNED_DB_READBACK absent={absent} networks_absent={networks_absent} "
        f"socket_absent={socket_absent} uncertain={uncertain}"
    )
    return not uncertain and absent and networks_absent and socket_absent


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise UnsafeFixture("Duplicate private fixture field")
        result[key] = value
    return result


def attest_fixture(manifest: Path) -> dict[str, object]:
    """Read-only proof shared by the runner and every fixture DDL admission."""
    if any(k.startswith(("DOCKER_", "COMPOSE_", "PG")) for k in os.environ):
        raise UnsafeFixture("Ambient Docker/Compose/libpq overrides forbidden")
    scratch = Path(os.environ["TMPDIR"]).resolve(strict=True)
    if (
        not manifest.is_absolute()
        or manifest.resolve(strict=True) != manifest
        or manifest.name != "fixture.json"
        or scratch not in manifest.parents
    ):
        raise UnsafeFixture("Expected canonical private fixture manifest")
    _private_file(manifest.parent, 0o700)
    _private_file(manifest, 0o600)
    with manifest.open("rb") as source:
        raw = source.read(8193)
    if len(raw) > 8192:
        raise UnsafeFixture("Oversized private fixture manifest")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    fields = {
        "schema_version",
        "root",
        "project",
        "container_id",
        "image_id",
        "daemon_id",
        "docker_endpoint",
        "system_identifier",
    }
    if (
        not isinstance(data, dict)
        or set(data) != fields
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
    ):
        raise UnsafeFixture("Invalid private fixture schema")
    if any(not isinstance(data[key], str) or not data[key] for key in fields - {"schema_version"}):
        raise UnsafeFixture("Invalid private fixture fields")
    root = manifest.parent
    if data["root"] != str(root) or not re.fullmatch(r"omnis-p01-[a-z0-9-]+", data["project"]):
        raise UnsafeFixture("Private fixture ownership mismatch")
    if (
        not re.fullmatch(r"[0-9a-f]{64}", data["container_id"])
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", data["image_id"])
        or not data["system_identifier"].isdecimal()
    ):
        raise UnsafeFixture("Invalid private fixture identities")
    paths = Paths(root, root / "data", root / "socket", root / "password")
    for path in (paths.data, paths.socket, paths.password):
        if path.resolve(strict=True) != path:
            raise UnsafeFixture("Private fixture path is not canonical")
    _private_file(paths.data, 0o700)
    _private_file(paths.password, 0o600)
    _private_file(paths.socket, 0o3775)
    sock = (paths.socket / ".s.PGSQL.5432").lstat()
    if (
        not stat.S_ISSOCK(sock.st_mode)
        or sock.st_uid != os.getuid()
        or stat.S_IMODE(sock.st_mode) != 0o600
    ):
        raise UnsafeFixture("Untrusted private database socket")
    endpoint = data["docker_endpoint"]
    if not endpoint.startswith("unix://"):
        raise UnsafeFixture("Only local Docker Unix endpoints are admitted")
    daemon_socket = Path(endpoint[7:])
    if daemon_socket.resolve(strict=True) != daemon_socket:
        raise UnsafeFixture("Docker socket changed canonical identity")
    info = daemon_socket.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid not in {0, os.getuid()}
        or info.st_mode & 0o002
    ):
        raise UnsafeFixture("Untrusted local Docker socket")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ["HOME"]}
    docker = ["docker", "--host", endpoint]
    before = _run([*docker, "info", "--format", "{{.ID}}"], env, timeout=10)
    if before.returncode or before.stdout.strip() != data["daemon_id"]:
        raise UnsafeFixture("Private fixture daemon changed")
    obj = _container(data["container_id"], docker, env, paths, data["project"], data["image_id"])
    if obj.get("State", {}).get("Running") is not True:
        raise UnsafeFixture("Private fixture is not running")
    after = _run([*docker, "info", "--format", "{{.ID}}"], env, timeout=10)
    if after.returncode or after.stdout.strip() != data["daemon_id"]:
        raise UnsafeFixture("Private fixture daemon changed during attestation")
    return {
        "schema_version": 1,
        "project": data["project"],
        "socket_directory": str(paths.socket),
        "system_identifier": data["system_identifier"],
        "container_id": data["container_id"],
    }


def write_fixture_manifest(
    paths: Paths,
    project: str,
    cid: str,
    image_id: str,
    endpoint: str,
    daemon_id: str,
    system_identifier: str,
) -> Path:
    manifest = paths.root / "fixture.json"
    data = {
        "schema_version": 1,
        "root": str(paths.root),
        "project": project,
        "container_id": cid,
        "image_id": image_id,
        "daemon_id": daemon_id,
        "docker_endpoint": endpoint,
        "system_identifier": system_identifier,
    }
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as target:
        json.dump(data, target, sort_keys=True)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    return manifest


def _authenticated(
    paths: Paths, password: str, env: dict[str, str], docker: list[str], cid: str
) -> str:
    uds = paths.socket / ".s.PGSQL.5432"
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        if _STOP_REQUESTED:
            raise UnsafeFixture("Interrupted during private DB startup")
        state = _run([*docker, "inspect", cid, "--format", "{{json .State}}"], env)
        if state.returncode or not json.loads(state.stdout).get("Running"):
            raise UnsafeFixture("Owned PostgreSQL exited before final readiness")
        logs = _run([*docker, "logs", cid], env)
        if logs.returncode or len(logs.stdout) + len(logs.stderr) > 65536:
            raise UnsafeFixture("Cannot distinguish init server from final PostgreSQL")
        if "PostgreSQL init process complete; ready for start up." not in logs.stdout + logs.stderr:
            time.sleep(1)
            continue
        try:
            info = uds.lstat()
        except FileNotFoundError:
            time.sleep(1)
            continue
        _private_file(paths.root, 0o700)
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or paths.socket.lstat().st_uid != os.getuid()
            or stat.S_IMODE(paths.socket.lstat().st_mode) != 0o3775
        ):
            raise UnsafeFixture("Untrusted or not-yet-private test DB socket")
        query = [
            "psql",
            "-X",
            "-A",
            "-t",
            "-h",
            str(paths.socket),
            "-p",
            "5432",
            "-U",
            "omnis_test",
            "-d",
            "omnis_test",
            "-c",
            "SELECT current_user, current_database(), inet_server_addr() IS NULL, current_setting('server_version'), system_identifier FROM pg_control_system()",
        ]
        rejected = _run(
            query,
            {**env, "PGPASSWORD": password + "-wrong", "PGCONNECT_TIMEOUT": "3"},
            timeout=5,
        )
        if rejected.returncode == 0:
            raise UnsafeFixture("Private PostgreSQL socket accepted a wrong password")
        if "password authentication failed" not in rejected.stderr:
            time.sleep(1)
            continue  # A startup race is not evidence of SCRAM rejection.
        checked = _run(
            query,
            {**env, "PGPASSWORD": password, "PGCONNECT_TIMEOUT": "3"},
            timeout=5,
        )
        if checked.returncode == 0:
            fields = checked.stdout.strip().split("|")
            if (
                len(fields) != 5
                or fields[:3] != ["omnis_test", "omnis_test", "t"]
                or not fields[3].startswith("18.6")
                or not fields[4].isdecimal()
            ):
                raise UnsafeFixture("Authenticated PostgreSQL identity/version mismatch")
            return fields[4]
        time.sleep(1)
    raise UnsafeFixture("Authenticated private UDS did not become ready")


def _request_stop(_signum, _frame) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


class GateCleanupUncertain(UnsafeFixture):
    """Keep the DB alive when the owned test family cannot be proven drained."""


def _direct_children() -> list[int]:
    return [
        int(value) for value in Path(f"/proc/self/task/{os.getpid()}/children").read_text().split()
    ]


def _admit_family_owner() -> None:
    # This runs only in the fresh --gate-command subprocess. Its only child producer
    # for the entire ownership lifetime is the one Popen below, never a shared pytest.
    if (
        __name__ != "__main__"
        or _direct_children()
        or len(list(Path("/proc/self/task").iterdir())) != 1
    ):
        raise GateCleanupUncertain("Gate family requires an exclusive fresh owner")
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER, this process only.
        raise GateCleanupUncertain("Cannot establish gate family ownership")


def _reap_finished_adopted(leader: int) -> None:
    """Act as init for already-dead adoptees; never stop live tests during execution."""
    for pid in _direct_children():
        if pid == leader:
            continue
        fd = os.pidfd_open(pid)
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[1]) != os.getpid():
                raise GateCleanupUncertain("Adopted process lost parent identity")
            os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
        finally:
            os.close(fd)


def _drain_adopted(leader: int) -> tuple[bool, bool]:
    handles: dict[int, int] = {}
    uncertain = seen = False
    deadline = time.monotonic() + 5
    try:
        while time.monotonic() < deadline:
            try:
                children = [pid for pid in _direct_children() if pid != leader]
                seen = seen or bool(children)
                for pid in children:
                    if pid in handles:
                        continue
                    fd = os.pidfd_open(pid)
                    try:
                        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                        if int(fields[1]) != os.getpid():
                            raise GateCleanupUncertain("Adopted process lost parent identity")
                        handles[pid] = fd
                    except BaseException:
                        os.close(fd)
                        raise
            except (OSError, ValueError, IndexError):
                uncertain = True
            for pid, fd in list(handles.items()):
                try:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    if os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG) is not None:
                        os.close(fd)
                        del handles[pid]
                except (OSError, ChildProcessError):
                    uncertain = True
            try:
                if not handles and not [p for p in _direct_children() if p != leader]:
                    return not uncertain, seen
            except OSError:
                uncertain = True
            # Re-scan after each parent exit: grandchildren can become direct adoptees late.
            time.sleep(0.02)
        return False, seen
    finally:
        for fd in handles.values():
            os.close(fd)


def _live_group_members(pgid: int) -> list[int]:
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pgid and fields[0] != "Z":
                members.append(int(entry.name))
        except FileNotFoundError:
            continue
    return members


def _run_owned_gate(
    command: list[str], env: dict[str, str], log: Path, timeout_seconds: int
) -> tuple[int, bool]:
    """Bound one owned test process group; retain its leader until group cleanup."""
    _admit_family_owner()
    if _STOP_REQUESTED:
        return 130, True
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    timed_out = interrupted = orphaned = uncertain = False
    with os.fdopen(fd, "wb") as output:
        child = subprocess.Popen(
            command,
            cwd=_ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + timeout_seconds
            while True:
                _reap_finished_adopted(child.pid)
                state = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if state is not None:
                    orphaned = bool(_live_group_members(child.pid))
                    break
                if _STOP_REQUESTED:
                    interrupted = True
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                time.sleep(0.05)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            # WNOWAIT pins the session leader: its numeric PGID cannot be reused yet.
            try:
                if timed_out or interrupted or orphaned:
                    os.killpg(child.pid, signal.SIGTERM)
                    time.sleep(0.2)
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                uncertain = True
            try:
                deadline = time.monotonic() + 5
                while _live_group_members(child.pid) and time.monotonic() < deadline:
                    time.sleep(0.05)
                if _live_group_members(child.pid):
                    uncertain = True
            except (OSError, ValueError, IndexError):
                uncertain = True
            drained, adopted = _drain_adopted(child.pid)
            uncertain = uncertain or not drained
            if not timed_out and not interrupted:
                orphaned = orphaned or adopted
            try:
                result = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                uncertain = True
                result = 2
    if uncertain:
        return 125, False
    if orphaned:
        return 2, True
    if interrupted:
        return 130, True
    if timed_out:
        return 124, True
    return (result if result >= 0 else 128 - result), True


def run_gate(command: list[str], env: dict[str, str], log: Path, timeout_seconds: int) -> int:
    """One dedicated family owner, even when this helper is called from a shared test."""
    if _STOP_REQUESTED:
        return 130
    receipt = log.with_name(log.name + ".result.json")
    worker = subprocess.Popen(
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--gate-log",
            str(log),
            "--gate-result",
            str(receipt),
            "--timeout-seconds",
            str(timeout_seconds),
            "--gate-command",
            *command,
        ],
        cwd=_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + timeout_seconds + 30
    forwarded = False
    while True:
        if _STOP_REQUESTED and not forwarded:
            worker.send_signal(signal.SIGTERM)
            forwarded = True
        try:
            code = worker.wait(timeout=0.05)
            break
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline:
                worker.send_signal(signal.SIGTERM)
                # Never tear down the DB under a still-unresolved family.
                raise GateCleanupUncertain("Gate family owner did not finish") from None
        except KeyboardInterrupt:
            worker.send_signal(signal.SIGINT)
            forwarded = True
    try:
        with receipt.open("rb") as source:
            raw = source.read(4097)
        if len(raw) > 4096:
            raise ValueError("oversized gate receipt")
        result = json.loads(raw, object_pairs_hook=_unique_object)
        if (
            set(result) != {"schema_version", "code", "family_drained"}
            or type(result["schema_version"]) is not int
            or result["schema_version"] != 1
            or type(result["code"]) is not int
            or result["code"] != code
            or result["family_drained"] is not True
        ):
            raise ValueError("unverified gate family")
    except (OSError, ValueError, KeyError, TypeError):
        raise GateCleanupUncertain("Gate family readback is missing or uncertain") from None
    return code


def gate_label(target: str) -> str:
    return "CANONICAL_GATE" if target == "check-components" else "TARGETED_GATE"


def _preflight_gate(uv: str) -> str:
    base = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ["HOME"]}
    selected = shutil.which(uv)
    if selected is None:
        raise UnsafeFixture("Pinned uv is unavailable")
    checks = [
        ([selected, "--version"], "uv 0.12.19 (x86_64-unknown-linux-gnu)"),
        (["node", "--version"], "v24.21.0"),
        (["npm", "--version"], "11.19.0"),
    ]
    for component in ("api", "cli"):
        interpreter = _ROOT / component / ".venv/bin/python"
        if not interpreter.is_file():
            raise UnsafeFixture("Locked API/CLI environment missing")
        checks.append(
            (
                [str(interpreter), "-I", "-c", "import platform;print(platform.python_version())"],
                "3.13.15",
            )
        )
    for argv, expected in checks:
        observed = _run(argv, base, timeout=10)
        if observed.returncode or observed.stdout.strip() != expected:
            raise UnsafeFixture("Gate toolchain pin mismatch")
    return str(Path(selected).resolve())


def _gate_environment(
    paths: Paths, env: dict[str, str], manifest: Path, password: str
) -> dict[str, str]:
    # Never pass ambient Make/pytest/Python/proxy/DB/probe configuration into the gate.
    result = {
        **env,
        "TMPDIR": str(Path(os.environ["TMPDIR"]).resolve()),
        "OMNIS_TEST_FIXTURE": str(manifest),
        "OMNIS_TEST_DB_PASSWORD": password,
        "OMNIS_TEST_DATABASE_URL": f"postgresql+psycopg://omnis_test:{password}@{quote(str(paths.socket), safe='')}/omnis_test",
    }
    for name in ("NPM_CONFIG_USERCONFIG", "NPM_CONFIG_GLOBALCONFIG"):
        path = paths.root / name.lower()
        with path.open("x"):
            pass
        result[name] = str(path)
    return result


def prove_private_fixture(
    gate_target: str | None = None, uv: str = "uv", timeout_seconds: int = 3600
) -> int:
    if any(k.startswith(("DOCKER_", "COMPOSE_", "PG")) for k in os.environ):
        raise UnsafeFixture("Ambient Docker/Compose/libpq overrides forbidden")
    if gate_target is not None:
        uv = _preflight_gate(uv)
    scratch = Path(os.environ["TMPDIR"]).resolve(strict=True)
    paths = prepare_paths(scratch / f"db-{uuid4().hex[:16]}")
    project = f"omnis-p01-{uuid4().hex}"
    print(f"DISPOSABLE_INTENT project={project} root={paths.root}", flush=True)
    base_env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ["HOME"]}
    env = {
        **base_env,
        "OMNIS_TEST_PROJECT": project,
        "OMNIS_TEST_UID": str(os.getuid()),
        "OMNIS_TEST_GID": str(os.getgid()),
        "OMNIS_TEST_DATA_DIR": str(paths.data),
        "OMNIS_TEST_SOCKET_DIR": str(paths.socket),
        "OMNIS_TEST_PASSWORD_FILE": str(paths.password),
    }
    endpoint = _docker_endpoint(base_env)
    docker = ["docker", "--host", endpoint]
    daemon = _run([*docker, "info", "--format", "{{.ID}}"], base_env)
    if daemon.returncode or not daemon.stdout.strip():
        raise UnsafeFixture("Docker daemon identity unavailable")
    image = _run(
        [*docker, "image", "inspect", _IMAGE, "--format", "{{.Id}} {{.Architecture}}"], base_env
    )
    if image.returncode or not image.stdout.strip().endswith(" amd64"):
        raise UnsafeFixture("Pinned PostgreSQL image unavailable")
    image_id = image.stdout.split()[0]
    compose = [
        *docker,
        "compose",
        "--env-file",
        "/dev/null",
        "--project-directory",
        str(paths.root),
        "-f",
        str(_COMPOSE),
        "-p",
        project,
    ]
    rendered = _run([*compose, "config", "--format", "json"], env)
    if rendered.returncode:
        raise UnsafeFixture("Private DB Compose contract did not render")
    validate_compose_config(json.loads(rendered.stdout), paths)
    if _find_owned(docker, base_env, project):
        raise UnsafeFixture("Disposable DB project already exists")
    cid = ""
    uncertain = False
    outcome = 2
    family_drained = True
    print(f"PINNED_DB_IMAGE image_id={image_id}", flush=True)
    try:
        missing = paths.root / "missing-data"
        denied_env = {**env, "OMNIS_TEST_DATA_DIR": str(missing)}
        denied = _run(
            [*compose, "create", "--no-build", "--pull", "never", "db"],
            denied_env,
            timeout=30,
        )
        try:
            missing.lstat()
        except FileNotFoundError:
            missing_absent = True
        else:
            missing_absent = False
        if (
            denied.returncode == 0
            or not missing_absent
            or _find_owned(docker, base_env, project)
            or _project_networks(docker, base_env, project)
        ):
            raise UnsafeFixture("Compose failed to refuse a missing private bind source")
        print("MISSING_BIND_DENIED create_host_path=false", flush=True)
        started = _run(
            [*compose, "up", "--no-build", "--pull", "never", "-d", "db"], env, timeout=60
        )
        if started.returncode:
            raise UnsafeFixture(f"Private DB startup refused (exit={started.returncode})")
        matches = _find_owned(docker, base_env, project)
        if len(matches) != 1:
            raise UnsafeFixture("Expected exactly one disposable DB container")
        cid = matches[0]
        _container(cid, docker, base_env, paths, project, image_id)
        print(f"DISPOSABLE_CREATED cid={cid}", flush=True)
        with paths.password.open() as source:
            password = source.readline().strip()
        identity = _authenticated(paths, password, base_env, docker, cid)
        _container(cid, docker, base_env, paths, project, image_id)
        current = _run([*docker, "info", "--format", "{{.ID}}"], base_env)
        if current.returncode or current.stdout.strip() != daemon.stdout.strip():
            raise UnsafeFixture("Docker daemon changed during DB proof")
        print(
            f"PRIVATE_DB_PROBE_OK version=18.6 network_none=true socket_private=true system_id={identity}"
        )
        if _STOP_REQUESTED:
            raise UnsafeFixture("Interrupted before gate admission")
        manifest = write_fixture_manifest(
            paths, project, cid, image_id, endpoint, daemon.stdout.strip(), identity
        )
        attest_fixture(manifest)
        outcome = 0
        if gate_target is not None:
            log = paths.root / "gate.log"
            print(f"{gate_label(gate_target)}_BEGIN target={gate_target} log={log}", flush=True)
            family_drained = False
            outcome = run_gate(
                ["make", "--no-print-directory", gate_target, f"UV={uv}"],
                _gate_environment(paths, env, manifest, password),
                log,
                timeout_seconds,
            )
            family_drained = True
            print(f"{gate_label(gate_target)}_EXIT code={outcome} log={log}", flush=True)
    except GateCleanupUncertain:
        family_drained = False
        uncertain = True
        print("GATE_FAMILY_UNCERTAIN database_retained_for_recovery=true")
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        uncertain = True
        print(f"PRIVATE_DB_PROBE_BLOCKED reason={type(exc).__name__}")
    finally:
        if not cid:
            try:
                matches = _find_owned(docker, base_env, project)
                if len(matches) == 1:
                    cid = matches[0]
                    uncertain = True  # Startup result did not pin the container in time.
                elif matches:
                    uncertain = True
            except (OSError, ValueError, subprocess.TimeoutExpired):
                uncertain = True
        if cid and family_drained:
            if not cleanup_owned(
                cid, docker, base_env, paths, project, image_id, daemon.stdout.strip()
            ):
                uncertain = True
        print(f"DISPOSABLE_DATA_RETAINED {paths.root}")
    return 2 if uncertain else outcome


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe one fresh private PostgreSQL test fixture")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe-only", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--gate-command", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    parser.add_argument("--gate-log", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--gate-result", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--target",
        choices=("check-components", "test-db-contract", "test-migrations", "test-e2e"),
        default="check-components",
    )
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    mode.add_argument("--attest", type=Path)
    args = parser.parse_args()
    if args.gate_command is not None:
        if (
            not args.gate_command
            or args.gate_log is None
            or args.gate_result is None
            or not 1 <= args.timeout_seconds <= 7200
        ):
            parser.error("Invalid internal gate request")
        signal.signal(signal.SIGTERM, _request_stop)
        signal.signal(signal.SIGINT, _request_stop)
        code, drained = _run_owned_gate(
            args.gate_command, dict(os.environ), args.gate_log, args.timeout_seconds
        )
        fd = os.open(args.gate_result, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump({"schema_version": 1, "code": code, "family_drained": drained}, output)
            output.flush()
            os.fsync(output.fileno())
        return code
    if args.attest is not None:
        try:
            print(json.dumps(attest_fixture(args.attest), sort_keys=True))
            return 0
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            print("PRIVATE_DB_ATTESTATION_BLOCKED")
            return 2
    if not 1 <= args.timeout_seconds <= 7200:
        parser.error("Gate deadline must be 1..7200 seconds")
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    try:
        return prove_private_fixture(
            args.target if args.check else None, args.uv, args.timeout_seconds
        )
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError):
        print("PRIVATE_DB_PREFLIGHT_BLOCKED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
