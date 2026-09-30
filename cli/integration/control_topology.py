"""Opt-in, disposable exercise of the installed P0 control topology."""

import hashlib
import http.client
import json
import os
import platform
import re
import secrets
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Buffer
from pathlib import Path

from omnis_cli.compose import _docker_id, _one_image, _preflight, _record, _validate_image
from omnis_cli.instance import private_dir
from omnis_cli.release import _installed_pointer, _manifest

_POSTGRES = (
    "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
)
_POSTGRES_REPO_DIGEST = (
    "postgres@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
)


def strict_probe_environment() -> None:
    """Never let ambient Docker/Compose/libpq redirect a disposable probe."""
    if any(key.startswith(("DOCKER_", "COMPOSE_", "PG")) for key in os.environ):
        raise ValueError("Ambient Docker, Compose or libpq overrides are forbidden")


def validate_docker_engine(version: str) -> None:
    """Older Engines can expose localhost-published ports to same-L2 hosts."""
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:[+.-][A-Za-z0-9._-]+)?", version)
    if match is None or int(match.group(1)) < 28:
        raise ValueError("Docker Engine 28+ required for private localhost publishing")


def preflight_port(port: int) -> None:
    """A foreign listener is never evidence of our API; fail before Compose."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid loopback port")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        raise ValueError("Loopback port occupied") from None


def assert_no_host_listener(port: int) -> None:
    """Read back host TCP listeners without connecting to a foreign service.

    A recently closed owned connection may leave TCP TIME_WAIT even though the
    forwarder exited. This is not a free-port preflight for the next launch.
    """
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid loopback port")
    try:
        listeners: set[int] = set()
        for table in ("tcp", "tcp6"):
            with Path(f"/proc/net/{table}").open(encoding="ascii") as source:
                if "local_address" not in source.readline():
                    raise ValueError("Invalid host TCP table")
                for line in source:
                    columns = line.split()
                    if len(columns) < 4:
                        raise ValueError("Invalid host TCP row")
                    if columns[3] == "0A":
                        listeners.add(int(columns[1].rsplit(":", 1)[1], 16))
    except (OSError, UnicodeError, ValueError, IndexError):
        raise ValueError("Host TCP listener readback unavailable") from None
    if port in listeners:
        raise ValueError("Host TCP listener remains")


def prepare_disposable_postgres(state_root: Path) -> Path:
    """PG18's postgres UID must traverse the bind root; its host parent stays 0700."""
    private_dir(state_root)
    path = state_root / "postgres"
    path.mkdir(mode=0o711)
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise ValueError("Unsafe PostgreSQL bind root")
    path.chmod(0o711)
    if stat.S_IMODE(path.stat().st_mode) != 0o711:
        raise ValueError("PostgreSQL bind root cannot be traversed")
    return path


def _docker(
    host: str,
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 20,
    success: bool = True,
) -> subprocess.CompletedProcess[str]:
    argv = ["docker", "--host", host, *args]
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env or {"PATH": os.environ.get("PATH", "")},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate(timeout=5)
        raise
    result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    if success and result.returncode:
        diagnostic = result.stderr + "\n" + result.stdout
        if env is not None and "OMNIS_DATABASE_URL" in env:
            database_url = env["OMNIS_DATABASE_URL"]
            password = database_url.partition("omnis:")[2].partition("@")[0]
            diagnostic = diagnostic.replace(database_url, "<synthetic-db-url>")
            if password:
                diagnostic = diagnostic.replace(password, "<synthetic-db-password>")
        diagnostic = diagnostic[-1200:]
        raise AssertionError(f"Docker {args[0]} failed with exit {result.returncode}: {diagnostic}")
    return result


def _compose(
    host: str,
    release: Path,
    project: str,
    empty_env: Path,
    env: dict[str, str],
    *args: str,
    timeout: int = 90,
    success: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _docker(
        host,
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(empty_env),
        "-f",
        str(release / "ops/compose.yaml"),
        *args,
        cwd=empty_env.parent,
        env=env,
        timeout=timeout,
        success=success,
    )


def _stop_installed_api(
    host: str, release: Path, project: str, empty_env: Path, env: dict[str, str]
) -> None:
    """Allow the API process owner's full 10s deadline plus reaping margin."""
    _compose(host, release, project, empty_env, env, "stop", "-t", "15", "api", timeout=30)


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


def _attest_container_identity(
    host: str, ident: str, scratch: Path, project: str, image_id: str, state_root: Path
) -> dict[str, object]:
    item = _inspect(host, ident, scratch)
    if item is None:
        raise AssertionError("Owned container missing")
    host_config = item["HostConfig"]
    mounts = item["Mounts"]
    if (
        not isinstance(host_config, dict)
        or not isinstance(mounts, list)
        or any(not isinstance(m, dict) for m in mounts)
    ):
        raise AssertionError("Invalid runtime confinement or mounts")
    config = item["Config"]
    labels = config["Labels"]
    service = labels.get("com.docker.compose.service")
    expected = _POSTGRES if service == "db" else image_id
    if (
        item.get("Id") != ident
        or labels.get("com.docker.compose.project") != project
        or service not in {"db", "api", "supervisor"}
        or config["Image"] != expected
        or item["Image"] != _expected_image_id(host, expected, scratch)
        or host_config["Privileged"] is not False
        or any(
            m.get("Destination") == "/var/run/docker.sock"
            or m.get("Source") in {"/var/run/docker.sock", "/run/docker.sock"}
            for m in mounts
        )
    ):
        raise AssertionError("Foreign or incompatible container")
    actual_mounts = {
        (m.get("Type"), m.get("Source"), m.get("Destination"), m.get("RW")) for m in mounts
    }
    if service == "db":
        expected_mounts = {
            ("bind", str(state_root / "postgres"), "/var/lib/postgresql", True),
            ("bind", str(state_root / "db-password"), "/run/secrets/db_password", False),
        }
        if len(mounts) != len(expected_mounts) or actual_mounts != expected_mounts:
            raise AssertionError("PostgreSQL data or secret mount mismatch")
    else:
        expected_mounts = {
            ("bind", str(state_root / "control"), "/run/omnis-control", service == "supervisor")
        }
        if service == "api":
            expected_mounts.add(("bind", str(state_root / "http"), "/run/omnis-http", True))
        if (
            config["User"] != f"{os.getuid()}:{os.getgid()}"
            or host_config.get("ReadonlyRootfs") is not True
            or host_config.get("CapDrop") != ["ALL"]
            or host_config.get("SecurityOpt") != ["no-new-privileges:true"]
            or len(mounts) != len(expected_mounts)
            or actual_mounts != expected_mounts
        ):
            raise AssertionError("Control UID, confinement or mount mismatch")
    return item


def _owned_container(
    host: str, ident: str, scratch: Path, project: str, image_id: str, state_root: Path, port: int
) -> dict[str, object]:
    item = _attest_container_identity(host, ident, scratch, project, image_id, state_root)
    ports = item["NetworkSettings"]["Ports"]
    expected_networks = {f"{project}_control"}
    if (
        item.get("State", {}).get("Running", True)
        and set(item["NetworkSettings"]["Networks"]) != expected_networks
    ):
        raise AssertionError("Unexpected runtime network membership")
    if item["HostConfig"].get("PortBindings") or any(value for value in ports.values()):
        raise AssertionError("Docker port exposure")
    return item


def _expected_image_id(host: str, image: str, scratch: Path) -> str:
    response = _docker(host, "image", "inspect", image, cwd=scratch)
    return str(_one_image(response.stdout)["Id"])


def _service_id(
    host: str, release: Path, project: str, empty_env: Path, env: dict[str, str], name: str
) -> str:
    value = _compose(host, release, project, empty_env, env, "ps", "-q", name).stdout.strip()
    if not value or "\n" in value:
        raise AssertionError("Expected one owned service")
    return value


def _psql(
    host: str, release: Path, project: str, empty_env: Path, env: dict[str, str], query: str
) -> str:
    return _compose(
        host,
        release,
        project,
        empty_env,
        env,
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "omnis",
        "-d",
        "omnis",
        "-Atc",
        query,
        timeout=20,
    ).stdout.strip()


class _DeadlineSocket(socket.socket):
    """Apply one monotonic budget to every HTTP socket operation, including makefile reads."""

    def __init__(self, family: int, *, deadline: float) -> None:
        super().__init__(family, socket.SOCK_STREAM)
        self._deadline = deadline

    def _budget(self) -> None:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Installed HTTP reply exceeded total deadline")
        self.settimeout(min(2, remaining))

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        self._budget()
        return super().recv(bufsize, flags)

    def recv_into(self, buffer: Buffer, nbytes: int = 0, flags: int = 0) -> int:
        self._budget()
        return super().recv_into(memoryview(buffer), nbytes, flags)


def _http(port: int, path: str) -> tuple[int, bytes]:
    """Only the fixed loopback origin, never redirects, proxies or unbounded trickle."""
    if type(port) is not int or not 1 <= port <= 65535 or path not in {"/", "/health/ready"}:
        raise ValueError("Invalid installed HTTP probe destination")
    with _DeadlineSocket(socket.AF_INET, deadline=time.monotonic() + 4) as connection:
        connection._budget()
        connection.connect(("127.0.0.1", port))
        connection._budget()
        connection.sendall(
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode()
        )
        response = http.client.HTTPResponse(connection)
        response.begin()
        limit = 2 * 1024 * 1024 if response.status == 200 else 4096
        body = response.read(limit + 1)
        status = response.status
        response.close()
    if len(body) > limit:
        raise ValueError("Installed HTTP response exceeds limit")
    return status, body


def _uds_http(directory: Path, port: int, request_path: str) -> tuple[int, bytes]:
    """Probe only the owned API UDS; never follow an HTTP redirect or URL."""
    private_dir(directory)
    path = directory / "api.sock"
    info = path.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or request_path not in {"/health/ready", "/"}
    ):
        raise ValueError("Untrusted API socket or request path")
    with _DeadlineSocket(socket.AF_UNIX, deadline=time.monotonic() + 4) as connection:
        connection._budget()
        connection.connect(str(path))
        credentials = connection.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        )
        _pid, uid, _gid = struct.unpack("3i", credentials)
        if uid != os.getuid():
            raise ValueError("Wrong API socket peer UID")
        connection._budget()
        connection.sendall(
            f"GET {request_path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode()
        )
        response = http.client.HTTPResponse(connection)
        response.begin()
        body = response.read(2 * 1024 * 1024 + 1)
        status = response.status
        response.close()
    if len(body) > 2 * 1024 * 1024:
        raise ValueError("API response exceeds limit")
    return status, body


def _wait_ready(port: int) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            code, body = _http(port, "/health/ready")
            if code == 200:
                result = json.loads(body)
                if isinstance(result, dict) and result.get("api_ready") is True:
                    return result
        except (OSError, ValueError, TimeoutError):
            pass
        time.sleep(0.4)
    raise AssertionError("Installed API did not become ready within budget")


def _wait_uds_ready(directory: Path, port: int) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            code, body = _uds_http(directory, port, "/health/ready")
            if code == 200:
                result = json.loads(body)
                if isinstance(result, dict) and result.get("api_ready") is True:
                    return result
        except (OSError, ValueError, TimeoutError):
            pass
        time.sleep(0.4)
    raise AssertionError("Installed private API socket did not become ready")


def _probe_installed_api_stop(
    host: str,
    release: Path,
    project: str,
    empty_env: Path,
    env: dict[str, str],
    state_root: Path,
    image_id: str,
    port: int,
    expected_ready: dict[str, object],
) -> None:
    """Fault-inject an installed API event-loop stall without target or model work."""
    scratch = empty_env.parent
    _stop_installed_api(host, release, project, empty_env, env)
    if (state_root / "http/api.sock").exists():
        raise AssertionError("Normal API stop left a private socket")
    name = f"{project}-api-stall"
    program = (
        "import time\n"
        "import omnis.serve as owned\n"
        "async def stalled(self, sockets=None):\n"
        "    print('STALLED_INSTALLED_API', flush=True)\n"
        "    while True: time.sleep(60)\n"
        "owned.uvicorn.Server.serve = stalled\n"
        "raise SystemExit(owned.main())\n"
    )
    _compose(
        host,
        release,
        project,
        empty_env,
        env,
        "run",
        "-d",
        "--no-deps",
        "--pull",
        "never",
        "--name",
        name,
        "--entrypoint",
        "python",
        "api",
        "-I",
        "-c",
        program,
        timeout=30,
    )
    item = _inspect(host, name, scratch)
    ident = item.get("Id") if item is not None else None
    if not isinstance(ident, str):
        raise AssertionError("Installed stalled API identity unavailable")
    owned = _owned_container(host, ident, scratch, project, image_id, state_root, port)
    config = owned.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict) or labels.get("com.docker.compose.oneoff") != "True":
        raise AssertionError("Stalled API is not an owned one-off")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = _inspect(host, ident, scratch)
        state = current.get("State") if current is not None else None
        if not isinstance(state, dict) or state.get("Running") is not True:
            raise AssertionError("Stalled API exited before owner stop")
        logs = _docker(host, "logs", "--tail", "30", ident, cwd=scratch, success=False)
        if logs.returncode == 0 and "STALLED_INSTALLED_API" in logs.stdout + logs.stderr:
            break
        time.sleep(0.2)
    else:
        raise AssertionError("Installed stalled API did not reach the blocked loop")
    _docker(host, "container", "stop", "--time", "15", ident, cwd=scratch, timeout=30)
    result = _inspect(host, ident, scratch)
    stopped = result.get("State") if result is not None else None
    if (
        not isinstance(stopped, dict)
        or stopped.get("Running") is not False
        or stopped.get("ExitCode") != 4
        or stopped.get("OOMKilled") is not False
    ):
        raise AssertionError("Docker preempted the API owner's exit-4 deadline")
    _owned_container(host, ident, scratch, project, image_id, state_root, port)
    _docker(host, "container", "rm", ident, cwd=scratch, timeout=30)
    _compose(
        host,
        release,
        project,
        empty_env,
        env,
        "up",
        "-d",
        "--no-deps",
        "--no-build",
        "--pull",
        "never",
        "api",
        timeout=90,
    )
    api_id = _service_id(host, release, project, empty_env, env, "api")
    restarted = _owned_container(host, api_id, scratch, project, image_id, state_root, port)
    restart_state = restarted.get("State")
    if not isinstance(restart_state, dict) or restart_state.get("Running") is not True:
        raise AssertionError("Installed API did not restart after blocked stop")
    if _wait_uds_ready(state_root / "http", port) != expected_ready:
        raise AssertionError("Installed API did not reconcile its stale socket")
    print(f"INSTALLED_API_STOP_DEADLINE_VERIFIED project={project} exit=4")


def _owner_set(host: str, project: str, scratch: Path) -> list[str]:
    response = _docker(
        host,
        "ps",
        "-a",
        "--no-trunc",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--format",
        "{{.ID}}",
        cwd=scratch,
    )
    return [line for line in response.stdout.splitlines() if line]


def _cleanup(
    host: str,
    release: Path,
    project: str,
    empty_env: Path,
    env: dict[str, str],
    state_root: Path,
    image_id: str,
    port: int,
) -> None:
    """Stop only an attested fresh Compose project; never delete its data bind."""
    scratch = empty_env.parent
    ids = _owner_set(host, project, scratch)
    owned: dict[str, dict[str, object]] = {}
    problems: list[str] = []
    for ident in ids:
        try:
            owned[ident] = _attest_container_identity(
                host, ident, scratch, project, image_id, state_root
            )
        except (
            AssertionError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ):
            problems.append("unverifiable container")
    for name, internal in (("control", True),):
        try:
            network = _docker(
                host, "network", "inspect", f"{project}_{name}", cwd=scratch, success=False
            )
            if network.returncode == 0:
                (details,) = json.loads(network.stdout)
                if (
                    details["Labels"].get("com.docker.compose.project") != project
                    or details["Internal"] is not internal
                    or any(ident not in ids for ident in details.get("Containers", {}))
                ):
                    problems.append("foreign network member or identity")
            elif "not found" not in network.stderr:
                problems.append("network inspection unavailable")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            problems.append("network inspection unavailable")
    if problems:
        for ident in owned:
            try:
                _attest_container_identity(host, ident, scratch, project, image_id, state_root)
                _docker(host, "container", "stop", "--time", "15", ident, cwd=scratch, timeout=30)
                _docker(host, "container", "rm", ident, cwd=scratch, timeout=30)
            except (
                AssertionError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            ):
                problems.append("owned container stop uncertain")
        raise AssertionError("Owned cleanup incomplete: " + ", ".join(problems))
    for ident, item in owned.items():
        if item["Config"]["Labels"].get("com.docker.compose.oneoff") == "True":
            try:
                _attest_container_identity(host, ident, scratch, project, image_id, state_root)
                _docker(host, "container", "rm", "-f", ident, cwd=scratch, timeout=30)
            except (
                AssertionError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            ):
                problems.append("owned one-off removal uncertain")
    _compose(host, release, project, empty_env, env, "down", timeout=90)
    if _owner_set(host, project, scratch):
        raise AssertionError("Owned containers survived down")
    for name in ("control",):
        absent = _docker(
            host, "network", "inspect", f"{project}_{name}", cwd=scratch, success=False
        )
        if absent.returncode == 0 or "not found" not in absent.stderr:
            raise AssertionError("Owned network survived down")
    if not (state_root / "postgres").is_dir():
        raise AssertionError("PostgreSQL bind disappeared")
    if (state_root / "http/api.sock").exists():
        raise AssertionError("Private API socket survived shutdown")
    if problems:
        raise AssertionError("Owned cleanup incomplete: " + ", ".join(problems))


def conclude_cleanup(project: str, state_root: Path, *, uncertain: bool) -> None:
    if uncertain:
        print(f"INSTALLED_CONTROL_OUTCOME_UNCERTAIN project={project} data_retained={state_root}")
        raise AssertionError("Compose daemon outcome uncertain; manual recovery required")
    print(f"INSTALLED_CONTROL_STOPPED project={project} data_retained={state_root}")


def _finish_probe(
    forwarder: subprocess.Popen[str] | None,
    *,
    port: int,
    launched: bool,
    host: str,
    release: Path,
    project: str,
    empty_env: Path,
    env: dict[str, str],
    state_root: Path,
    image_id: str,
    uncertain: bool,
) -> None:
    """Attempt every owned teardown even when the host forwarder exits mid-signal."""
    problems = ["probe outcome uncertain"] if uncertain else []
    cleanup_error: Exception | None = None
    try:
        if forwarder is not None:
            stdout = ""
            try:
                if forwarder.poll() is None:
                    try:
                        os.killpg(forwarder.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass  # The leader exited between poll and signal.
                try:
                    stdout, _stderr = forwarder.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    problems.append("forwarder timeout")
                    try:
                        os.killpg(forwarder.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, _stderr = forwarder.communicate(timeout=5)
                if forwarder.returncode != 0 or "FORWARDER_READY" not in stdout:
                    problems.append("forwarder exit uncertain")
            except (OSError, ValueError, subprocess.SubprocessError):
                problems.append("forwarder teardown uncertain")
            try:
                assert_no_host_listener(port)
            except (OSError, ValueError):
                problems.append("host listener readback uncertain")
    finally:
        if launched:
            try:
                _cleanup(host, release, project, empty_env, env, state_root, image_id, port)
            except (
                AssertionError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            ) as exc:
                cleanup_error = exc
                problems.append("owned Compose cleanup incomplete")
    if problems:
        print(f"INSTALLED_CONTROL_OUTCOME_UNCERTAIN project={project} data_retained={state_root}")
        raise AssertionError(
            "Installed cleanup incomplete: " + ", ".join(problems)
        ) from cleanup_error
    if launched:
        conclude_cleanup(project, state_root, uncertain=False)


def run_probe(data_home: Path, recorded: dict[str, object], scratch: Path, cli: str) -> None:
    """Opt-in disposable P0 DB→migration→control/API proof, not a launcher."""
    strict_probe_environment()
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise ValueError("Pinned linux/amd64 platform required")
    root = data_home / "omnis"
    private_dir(root)
    if not _installed_pointer(root / "installed.json"):
        raise ValueError("Installed release required")
    release = root / "releases/0.1.0"
    manifest, _ = _manifest(release)
    digest = hashlib.sha256(manifest).hexdigest()
    receipt = _record(root / "image.json", digest, complete=True)
    if receipt is None or recorded.get("image_id") != receipt.image_id:
        raise ValueError("Installed image receipt missing or changed")
    host = _preflight(release)
    if (
        host != receipt.docker_host
        or _docker_id(release, host) != receipt.docker_id
        or _validate_image(receipt.tag, release, receipt.project, digest, host=host)
        != receipt.image_id
    ):
        raise ValueError("Installed image/daemon identity mismatch")
    base = _docker(host, "image", "inspect", _POSTGRES, cwd=scratch)
    details = _one_image(base.stdout)
    if details.get("Architecture") != "amd64" or _POSTGRES_REPO_DIGEST not in details.get(
        "RepoDigests", []
    ):
        raise ValueError("Pinned PostgreSQL image unavailable")
    if os.getuid() == 0 or os.getgid() == 0:
        raise ValueError("Nonroot operator UID/GID required")
    project = receipt.project
    if _owner_set(host, project, scratch):
        raise ValueError("Refuse preexisting Compose project")
    for name in ("control",):
        network = _docker(
            host, "network", "inspect", f"{project}_{name}", cwd=scratch, success=False
        )
        if network.returncode == 0 or "not found" not in network.stderr:
            raise ValueError("Refuse preexisting or unverifiable network")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    preflight_port(port)
    state_root = Path(tempfile.mkdtemp(prefix="omnis-p04-control-", dir=os.environ["TMPDIR"]))
    private_dir(state_root)
    prepare_disposable_postgres(state_root)
    (state_root / "control").mkdir(mode=0o700)
    private_dir(state_root / "control")
    (state_root / "http").mkdir(mode=0o700)
    private_dir(state_root / "http")
    password = secrets.token_hex(24)
    password_file = state_root / "db-password"
    fd = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(password + "\n")
        output.flush()
        os.fsync(output.fileno())
    if stat.S_IMODE(password_file.stat().st_mode) != 0o600:
        raise AssertionError("Private DB password mode mismatch")
    empty_env = scratch / "empty-compose.env"
    empty_env.touch(mode=0o600, exist_ok=False)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "OMNIS_PROJECT": project,
        "OMNIS_START_ATTEMPT": project.removeprefix("omnis-local-"),
        "OMNIS_IMAGE_ID": receipt.image_id,
        "OMNIS_UID": str(os.getuid()),
        "OMNIS_GID": str(os.getgid()),
        "OMNIS_HTTP_PORT": str(port),
        "OMNIS_STATE_ROOT": str(state_root),
        "OMNIS_CONTROL_DIR": str(state_root / "control"),
        "OMNIS_HTTP_BIND_DIR": str(state_root / "http"),
        "OMNIS_DB_PASSWORD_FILE": str(password_file),
        "OMNIS_DATABASE_URL": f"postgresql+psycopg://omnis:{password}@db:5432/omnis",
    }
    print(
        f"CONTROL_PROBE_PREPARED project={project} image={receipt.image_id} "
        f"port=127.0.0.1:{port} disposable_data={state_root}",
        flush=True,
    )
    launched = False
    uncertain = False
    forwarder: subprocess.Popen[str] | None = None
    try:
        if _docker_id(release, host) != receipt.docker_id:
            raise AssertionError("Docker daemon changed before startup")
        launched = True
        db_up = _compose(
            host,
            release,
            project,
            empty_env,
            env,
            "up",
            "-d",
            "--wait",
            "--no-build",
            "--pull",
            "never",
            "db",
            timeout=120,
            success=False,
        )
        if db_up.returncode:
            for ident in _owner_set(host, project, scratch):
                item = _inspect(host, ident, scratch)
                if item and item["Config"]["Labels"].get("com.docker.compose.service") == "db":
                    owned = _owned_container(
                        host, ident, scratch, project, receipt.image_id, state_root, port
                    )
                    db_mount = next(
                        m for m in owned["Mounts"] if m["Destination"] == "/var/lib/postgresql"
                    )
                    print(
                        "DISPOSABLE_DB_MOUNT "
                        f"rw={db_mount['RW']} user={owned['Config']['User']!r} "
                        f"readonly_root={owned['HostConfig']['ReadonlyRootfs']}",
                        file=sys.stderr,
                    )
                    log = _docker(host, "logs", "--tail", "30", ident, cwd=scratch, success=False)
                    diagnostic = (log.stdout + log.stderr).replace(
                        password, "<synthetic-db-password>"
                    )
                    print(f"DISPOSABLE_DB_START_FAILED {diagnostic[-900:]}", file=sys.stderr)
            raise AssertionError(f"Disposable PostgreSQL startup exit {db_up.returncode}")
        db_id = _service_id(host, release, project, empty_env, env, "db")
        _owned_container(host, db_id, scratch, project, receipt.image_id, state_root, port)
        if (
            _psql(
                host,
                release,
                project,
                empty_env,
                env,
                "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'",
            )
            != "0"
        ):
            raise AssertionError("Disposable database is not empty; no automatic upgrade")
        system_id = _psql(
            host,
            release,
            project,
            empty_env,
            env,
            "SELECT system_identifier FROM pg_control_system()",
        )
        if not system_id.isdecimal():
            raise AssertionError("PostgreSQL cluster identity unavailable")

        _compose(
            host,
            release,
            project,
            empty_env,
            env,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "api",
            timeout=90,
        )
        api_id = _service_id(host, release, project, empty_env, env, "api")
        _owned_container(host, api_id, scratch, project, receipt.image_id, state_root, port)
        negative_deadline = time.monotonic() + 10
        while True:
            try:
                code, body = _uds_http(state_root / "http", port, "/health/ready")
                if code == 503:
                    projection = json.loads(body)
                    if projection.get("reason") == "SCHEMA_INCOMPATIBLE" and not projection.get(
                        "dashboard_ready"
                    ):
                        break
            except (OSError, ValueError, TimeoutError):
                pass
            if time.monotonic() > negative_deadline:
                raise AssertionError("Unmigrated API did not refuse readiness")
            time.sleep(0.3)
        print(f"INSTALLED_SCHEMA_NEGATIVE_VERIFIED project={project} status=503")
        _stop_installed_api(host, release, project, empty_env, env)
        _docker(host, "container", "rm", api_id, cwd=scratch, timeout=30)

        job = f"{project}-migrate"
        migration = _compose(
            host,
            release,
            project,
            empty_env,
            env,
            "run",
            "-T",
            "--no-deps",
            "--pull",
            "never",
            "--name",
            job,
            "supervisor",
            "python",
            "-I",
            "-m",
            "omnis.migrate",
            timeout=60,
            success=False,
        )
        job_info = _inspect(host, job, scratch)
        job_id = job_info.get("Id") if job_info is not None else None
        if not isinstance(job_id, str):
            raise AssertionError("Installed migration job identity unavailable")
        _owned_container(host, job_id, scratch, project, receipt.image_id, state_root, port)
        if migration.returncode:
            raise AssertionError(f"Installed migration failed with exit {migration.returncode}")
        _docker(host, "container", "rm", job_id, cwd=scratch)
        if (
            _psql(host, release, project, empty_env, env, "SELECT version_num FROM alembic_version")
            != "0004_pairing_receipts"
        ):
            raise AssertionError("Installed migration revision mismatch")
        if (
            _psql(
                host,
                release,
                project,
                empty_env,
                env,
                "SELECT system_identifier FROM pg_control_system()",
            )
            != system_id
        ):
            raise AssertionError("PostgreSQL cluster changed during migration")
        instance_id = _psql(
            host,
            release,
            project,
            empty_env,
            env,
            "SELECT instance_id FROM instance_control WHERE id = 1",
        )
        from uuid import UUID

        if str(UUID(instance_id)) != instance_id:
            raise AssertionError("Instance identity unavailable")
        _compose(
            host,
            release,
            project,
            empty_env,
            env,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "supervisor",
            "api",
            timeout=90,
        )
        for service in ("db", "supervisor", "api"):
            ident = _service_id(host, release, project, empty_env, env, service)
            item = _owned_container(
                host, ident, scratch, project, receipt.image_id, state_root, port
            )
            if item["State"]["Running"] is not True:
                raise AssertionError(f"Installed {service} did not remain running")
        expected_ready = {
            "api_ready": True,
            "dashboard_ready": True,
            "assessment_ready": False,
            "reason": None,
            "dashboard_reason": None,
        }
        if _wait_uds_ready(state_root / "http", port) != expected_ready:
            raise AssertionError("Installed private API readiness mismatch")
        cli_python = str(Path(cli).parent / "python")
        forwarder = subprocess.Popen(
            [
                cli_python,
                "-I",
                "-m",
                "omnis_cli.forwarder",
                "--socket-dir",
                str(state_root / "http"),
                "--port",
                str(port),
            ],
            cwd=scratch,
            env={"PATH": env["PATH"]},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        ready = _wait_ready(port)
        if forwarder.poll() is not None or ready != expected_ready:
            raise AssertionError("Installed dashboard readiness mismatch")
        status, index = _http(port, "/")
        if status != 200 or index != (release / "web/index.html").read_bytes():
            raise AssertionError("Installed same-origin assets mismatch")
        probe = subprocess.run(
            [
                cli_python,
                "-I",
                "-c",
                "import json,sys; from pathlib import Path; "
                "from omnis_cli.control import request; "
                "print(json.dumps(request(Path(sys.argv[1]), {'op':'status'})))",
                str(state_root / "control"),
            ],
            cwd=scratch,
            env={"PATH": env["PATH"]},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if probe.returncode or json.loads(probe.stdout).get("instance_id") != instance_id:
            raise AssertionError("Installed CLI private control identity mismatch")
        _probe_installed_api_stop(
            host,
            release,
            project,
            empty_env,
            env,
            state_root,
            receipt.image_id,
            port,
            expected_ready,
        )
        print(
            f"INSTALLED_CONTROL_VERIFIED project={project} image={receipt.image_id} "
            f"port=127.0.0.1:{port} instance={instance_id} db_system_id={system_id}"
        )
    except subprocess.TimeoutExpired:
        uncertain = True
        raise
    finally:
        _finish_probe(
            forwarder,
            port=port,
            launched=launched,
            host=host,
            release=release,
            project=project,
            empty_env=empty_env,
            env=env,
            state_root=state_root,
            image_id=receipt.image_id,
            uncertain=uncertain,
        )
