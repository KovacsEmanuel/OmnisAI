"""Installed P0 headless startup. No assessment, GUI, implicit install or recovery."""

import http.client
import json
import os
import re
import secrets
import select
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from uuid import UUID, uuid4

from .control import ControlUnavailable, request
from .health import dashboard
from .instance import Instance, control_dir, load_instance, private_dir, private_file, state_dir
from .lifecycle import (
    StartError,
    cleanup_startup_ipc,
    ensure_private,
    lifecycle_lock,
    listener_owned,
    mapping,
    process_identity,
    process_sockets,
    read_record,
    remaining,
    socket_identity,
    write_record,
)
from .release import _put
from .start_runtime import POSTGRES, SAFE_PATH, ControlRuntime

EXPECTED_SCHEMA = "0004_pairing_receipts"
READY_FIELDS = {
    "format",
    "phase",
    "attempt",
    "project",
    "release_digest",
    "image_id",
    "docker_host",
    "docker_id",
    "control_dir",
    "port",
    "containers",
    "system_id",
    "instance_id",
    "forwarder",
    "listener_inode",
    "api_socket",
    "control_socket",
    "open_command",
    "generation",
    "supervisor_epoch",
}


def preflight_port(port: int) -> None:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise StartError("PORT_INVALID")
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))  # No reuse: bound-but-not-listening is foreign too.
    except OSError:
        raise StartError("PORT_CONFLICT") from None


def environment(runtime: ControlRuntime, root: Path, control: Path, port: int) -> dict[str, str]:
    password = private_file(root / "db-password", limit=64).strip()
    if re.fullmatch(r"[0-9a-f]{48}", password) is None:
        raise StartError("DATABASE_SECRET_INVALID")
    return {
        "OMNIS_PROJECT": runtime.receipt.project,
        "OMNIS_START_ATTEMPT": str(runtime.attempt),
        "OMNIS_IMAGE_ID": runtime.receipt.image_id,
        "OMNIS_UID": str(os.getuid()),
        "OMNIS_GID": str(os.getgid()),
        "OMNIS_HTTP_PORT": str(port),
        "OMNIS_STATE_ROOT": str(root),
        "OMNIS_CONTROL_DIR": str(control),
        "OMNIS_HTTP_BIND_DIR": str(root / "http"),
        "OMNIS_DB_PASSWORD_FILE": str(root / "db-password"),
        "OMNIS_DATABASE_URL": f"postgresql+psycopg://omnis:{password}@db:5432/omnis",
    }


def validate_config(runtime: ControlRuntime, env: dict[str, str]) -> None:
    config = mapping(json.loads(runtime.compose(env, "config", "--format", "json").stdout))
    services = mapping(config.get("services"))
    networks = mapping(config.get("networks"))
    if (
        config.get("name") != runtime.receipt.project
        or set(services) != {"db", "api", "supervisor"}
        or set(networks) != {"control"}
        or mapping(networks["control"])
        != {
            "name": f"{runtime.receipt.project}_control",
            "internal": True,
            "ipam": {},
            "labels": {"org.omnis.start-attempt": runtime.attempt},
        }
    ):
        raise StartError("COMPOSE_TOPOLOGY_INVALID")
    for role, raw in services.items():
        service = mapping(raw)
        if (
            mapping(service.get("labels")) != {"org.omnis.start-attempt": runtime.attempt}
            or service.get("image") != (POSTGRES if role == "db" else runtime.receipt.image_id)
            or service.get("pull_policy") != "never"
            or service.get("platform") != "linux/amd64"
            or set(mapping(service.get("networks"))) != {"control"}
            or any(
                service.get(key) is not None
                for key in (
                    "build",
                    "ports",
                    "network_mode",
                    "entrypoint",
                    "pid",
                    "ipc",
                    "devices",
                    "cap_add",
                    "env_file",
                    "extends",
                )
            )
            or service.get("privileged", False)
            or service.get("restart") != "no"
        ):
            raise StartError("COMPOSE_SERVICE_INVALID")
        if role != "db" and (
            service.get("user") != f"{os.getuid()}:{os.getgid()}"
            or service.get("read_only") is not True
            or service.get("cap_drop") != ["ALL"]
            or service.get("security_opt") != ["no-new-privileges:true"]
        ):
            raise StartError("COMPOSE_CONFINEMENT_INVALID")


def service_ids(runtime: ControlRuntime, root: Path, control: Path, port: int) -> dict[str, str]:
    result: dict[str, str] = {}
    for ident in runtime.ids():
        raw = runtime.inspect("container", ident)
        if raw is None:
            raise StartError("CONTAINER_READBACK_CHANGED", 3)
        role = mapping(mapping(raw.get("Config")).get("Labels")).get("com.docker.compose.service")
        if not isinstance(role, str) or role in result:
            raise StartError("DUPLICATE_SERVICE", 3)
        runtime.attest(ident, role, root, control, port)
        result[role] = ident
    runtime.network(set(result.values()))
    return result


def database_identity(runtime: ControlRuntime, ident: str) -> tuple[str, str]:
    system_id = runtime.psql(ident, "SELECT system_identifier FROM pg_control_system()")
    instance_id = runtime.psql(ident, "SELECT instance_id FROM instance_control WHERE id = 1")
    if not system_id.isdecimal() or str(UUID(instance_id)) != instance_id:
        raise StartError("DATABASE_IDENTITY_INVALID", 3)
    if runtime.psql(ident, "SELECT version_num FROM alembic_version") != EXPECTED_SCHEMA:
        raise StartError("SCHEMA_UPDATE_REQUIRED", 3)
    return system_id, instance_id


def api_process(runtime: ControlRuntime, ident: str, root: Path, control: Path, port: int) -> int:
    state = mapping(runtime.attest(ident, "api", root, control, port).get("State"))
    pid = state.get("Pid")
    if state.get("Running") is not True or type(pid) is not int or pid <= 1:
        raise StartError("API_NOT_RUNNING", 3)
    return pid


def wait_dashboard(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    port: int,
    instance_id: str,
    api_pid: int,
    *,
    allow_closed: bool = False,
) -> dict[str, object]:
    end = min(runtime.deadline, time.monotonic() + 30)
    while time.monotonic() < end:
        try:
            return dashboard(
                control,
                root / "http",
                port,
                instance_id,
                runtime.files,
                end,
                forwarded=False,
                api_pid=api_pid,
                allow_closed=allow_closed,
            )
        except (OSError, ValueError, ControlUnavailable, http.client.HTTPException):
            time.sleep(min(0.2, remaining(end)))
    raise StartError("DASHBOARD_READINESS_FAILED", 3)


class ForwarderStartError(StartError):
    """Hand ownership to outer cleanup even when the readiness handshake fails."""

    def __init__(self, process: subprocess.Popen[bytes], pidfd: int, reason: str) -> None:
        super().__init__(reason, 3)
        self.process = process
        self.pidfd = pidfd


@dataclass
class ForwarderOwnership:
    """Caller-owned before spawn; a failed return/finally cannot erase these handles."""

    process: subprocess.Popen[bytes] | None = None
    pidfd: int = -1


@contextmanager
def _publish_forwarder() -> Iterator[None]:
    """Defer CLI Python interrupts through birth/publication, not via thread masks.

    Python handlers run on the main thread even if delivery is to another thread.
    Record every stop here, restore the previous handlers, then enter cleanup once
    ownership is published. Do not replace an arbitrary library caller's handler.
    """
    pending = False

    def defer(signum: int, frame: FrameType | None) -> None:
        nonlocal pending
        pending = True

    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    if any(
        handler not in (_interrupt, signal.default_int_handler, signal.SIG_DFL, signal.SIG_IGN)
        for handler in previous.values()
    ):
        raise StartError("FORWARDER_SIGNAL_POLICY_UNSUPPORTED")
    changed = []
    try:
        for sig, handler in previous.items():
            if handler in (_interrupt, signal.default_int_handler):
                signal.signal(sig, defer)  # Main-thread restriction enforced before spawn.
                changed.append(sig)
        yield
    finally:
        for sig in changed:
            signal.signal(sig, previous[sig])
    if pending:
        raise KeyboardInterrupt()


def launch_forwarder(
    root: Path, port: int, deadline: float, *, ownership: ForwarderOwnership | None = None
) -> tuple[subprocess.Popen[bytes], int, dict[str, object], int]:
    # The private intent and caller holder exist before birth. The tuple is NOT
    # the ownership transfer: finally/close and tuple unpacking remain interruptible.
    owner = ownership if ownership is not None else ForwarderOwnership()
    remaining(deadline)
    log_fd = os.open(
        root / "forwarder.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(log_fd, "wb") as log:
            with _publish_forwarder():
                owner.process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-m",
                        "omnis_cli.forwarder",
                        "--socket-dir",
                        str(root / "http"),
                        "--port",
                        str(port),
                    ],
                    cwd=root,
                    env={"PATH": SAFE_PATH},
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=log,
                    start_new_session=True,
                )
                owner.pidfd = os.pidfd_open(owner.process.pid)
        process = owner.process
        assert process is not None and process.stdout is not None
        try:
            end = min(deadline, time.monotonic() + 8)
            message = bytearray()
            while b"\n" not in message and len(message) <= 128:
                if not select.select([process.stdout], [], [], remaining(end, 8))[0]:
                    raise StartError("FORWARDER_READINESS_TIMEOUT", 3)
                chunk = os.read(process.stdout.fileno(), 129 - len(message))
                if not chunk:
                    raise StartError("FORWARDER_EXITED", 3)
                message.extend(chunk)
            if bytes(message) != b"FORWARDER_READY\n" or process.poll() is not None:
                raise StartError("FORWARDER_READINESS_FAILED", 3)
            identity = process_identity(process.pid)
            inodes = process_sockets(process.pid)
            rows = Path("/proc/net/tcp").read_text().splitlines()[1:]
            listeners = [
                int(row.split()[9])
                for row in rows
                if row.split()[1] == f"0100007F:{port:04X}"
                and row.split()[3] == "0A"
                and int(row.split()[9]) in inodes
            ]
            if len(listeners) != 1:
                raise StartError("FORWARDER_LISTENER_UNVERIFIED", 3)
            listener_owned(identity, port, listeners[0])
        finally:
            process.stdout.close()
        return process, owner.pidfd, identity, listeners[0]
    except BaseException as exc:
        if owner.process is None:
            raise
        # Includes log/pipe finalizers. Outer holder remains authoritative even
        # if a second interrupt cancels construction/delivery of this exception.
        try:
            if owner.process.stdout is not None and not owner.process.stdout.closed:
                owner.process.stdout.close()
        finally:
            raise ForwarderStartError(
                owner.process,
                owner.pidfd,
                exc.reason if isinstance(exc, StartError) else "FORWARDER_START_FAILED",
            ) from None


def stop_forwarder(process: subprocess.Popen[bytes], pidfd: int) -> None:
    if process.poll() is None:
        signal.pidfd_send_signal(pidfd, signal.SIGTERM)
        try:
            process.wait(timeout=22)
        except subprocess.TimeoutExpired:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            process.wait(timeout=5)
            raise StartError("FORWARDER_CLEANUP_UNCERTAIN", 4) from None
    if process.returncode not in {0, 3}:
        raise StartError("FORWARDER_CLEANUP_UNCERTAIN", 4)


def cleanup_attempt(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    port: int,
    process: subprocess.Popen[bytes] | None,
    pidfd: int,
) -> list[str]:
    """Not omnis stop: only this fresh attempt, with no adopted running instance."""
    problems: list[str] = []
    drained = not runtime.uncertain and runtime.family_drained
    runtime.deadline = time.monotonic() + 100  # Separate finite cleanup allowance.
    if process is not None:
        try:
            stop_forwarder(process, pidfd)
        except (OSError, ValueError, subprocess.SubprocessError):
            problems.append("forwarder")
            drained = False
    try:
        ids = runtime.ids()
    except (OSError, ValueError, subprocess.SubprocessError):
        return [*problems, "container inventory"]
    roles: dict[str, str] = {}
    for ident in ids:
        try:
            item = runtime.inspect("container", ident)
            role = mapping(mapping(item.get("Config") if item else None).get("Labels")).get(
                "com.docker.compose.service"
            )
            if not isinstance(role, str):
                raise StartError("INVALID_ROLE")
            runtime.attest(ident, role, root, control, port)
            roles[ident] = role
        except (OSError, ValueError, subprocess.SubprocessError):
            problems.append("identity")
            drained = False
    for ident, role in sorted(roles.items(), key=lambda pair: pair[1] == "db"):
        if role == "db" and (not drained or runtime.uncertain or not runtime.family_drained):
            problems.append("database retained under uncertain writers")
            continue
        try:
            runtime.attest(ident, role, root, control, port)
            runtime.run("container", "stop", "--time", "15", ident, cap=22, effect=True)
            stopped = runtime.inspect("container", ident)
            if stopped is None or mapping(stopped.get("State")).get("Running") is not False:
                raise StartError("STOP_UNVERIFIED", 4)
        except (OSError, ValueError, subprocess.SubprocessError):
            problems.append("container stop")
            drained = False
            continue
        try:
            runtime.run("container", "rm", ident, effect=True)
            if runtime.inspect("container", ident) is not None:
                raise StartError("REMOVAL_UNVERIFIED", 4)
        except (OSError, ValueError, subprocess.SubprocessError):
            problems.append("container removal")  # A stopped container is not a live DB writer.
    try:
        if runtime.ids():
            problems.append("containers remain")
        else:
            net = runtime.network(set())
            if net is not None:
                runtime.run("network", "rm", net, effect=True)
                if runtime.network(set()) is not None:
                    problems.append("network remains")
    except (OSError, ValueError, subprocess.SubprocessError):
        problems.append("network readback")
    if not problems and not runtime.uncertain and runtime.family_drained:
        problems.extend(cleanup_startup_ipc(root, control))
    for path in (root / "http/api.sock", control / "control.sock", control / "control.cap"):
        if os.path.lexists(path):
            problems.append("IPC retained")  # Never unlink an uncertain/stale peer.
    if not runtime.family_drained:
        problems.append("CLI descendants uncertain")
    if runtime.uncertain:
        problems.append("daemon outcome uncertain")
    return problems


def _socket_receipt(value: object) -> bool:
    return type(value) is list and len(value) == 2 and all(type(part) is int for part in value)


def verify_running(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object], port: int
) -> dict[str, object]:
    if (
        set(record) != READY_FIELDS
        or record.get("phase") != "READY"
        or type(record.get("format")) is not int
        or record["format"] != 1
        or type(record.get("generation")) is not int
        or type(record.get("supervisor_epoch")) is not int
        or type(record.get("containers")) is not dict
        or type(record.get("forwarder")) is not dict
        or not _socket_receipt(record.get("api_socket"))
        or not _socket_receipt(record.get("control_socket"))
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    attempt = record.get("attempt")
    if not isinstance(attempt, str) or str(UUID(attempt)) != attempt:
        raise StartError("RECOVERY_REQUIRED", 4)
    runtime.attempt = attempt
    instance = load_instance(root)
    if (
        record.get("phase") != "READY"
        or record.get("format") != 1
        or record.get("release_digest") != runtime.digest
        or record.get("image_id") != runtime.receipt.image_id
        or record.get("docker_id") != runtime.receipt.docker_id
        or record.get("docker_host") != runtime.host
        or record.get("control_dir") != str(control)
        or record.get("port") != port
        or record.get("project") != runtime.receipt.project
        or instance.project != runtime.receipt.project
        or instance.release != "0.1.0"
        or instance.origin != f"http://127.0.0.1:{port}"
        or record.get("instance_id") != instance.instance_id
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    ids = service_ids(runtime, root, control, port)
    if set(ids) != {"db", "api", "supervisor"} or ids != record.get("containers"):
        raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
    if database_identity(runtime, ids["db"]) != (record.get("system_id"), instance.instance_id):
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    for role, ident in ids.items():
        if (
            mapping(runtime.attest(ident, role, root, control, port).get("State")).get("Running")
            is not True
        ):
            raise StartError("RECOVERY_REQUIRED", 4)
    identity = mapping(record.get("forwarder"))
    inode = record.get("listener_inode")
    if type(inode) is not int:
        raise StartError("FORWARDER_RECORD_INVALID", 4)

    def route_owned() -> None:
        listener_owned(identity, port, inode)
        if socket_identity(root / "http/api.sock") != record.get("api_socket") or socket_identity(
            control / "control.sock"
        ) != record.get("control_socket"):
            raise StartError("IPC_IDENTITY_MISMATCH", 4)

    route_owned()
    current = dashboard(
        control,
        root / "http",
        port,
        instance.instance_id,
        runtime.files,
        runtime.deadline,
        forwarded=True,
        api_pid=api_process(runtime, ids["api"], root, control, port),
    )
    route_owned()
    if (
        current.get("admission_open") is not True
        or current.get("generation") != record.get("generation")
        or current.get("supervisor_epoch") != record.get("supervisor_epoch")
    ):
        raise StartError("ADMISSION_CLOSED_OR_CHANGED", 4)
    return projection(instance, current, reused=True)


def projection(
    instance: Instance, current: dict[str, object], *, reused: bool
) -> dict[str, object]:
    return {
        "state": "READY",
        "instance_id": instance.instance_id,
        "release": instance.release,
        "schema": instance.schema,
        "origin": instance.origin,
        "dashboard_ready": True,
        "api_ready": True,
        "control_ready": True,
        "assessment_ready": False,
        "browser_opened": False,
        "admission_open": current["admission_open"],
        "generation": current["generation"],
        "supervisor_epoch": current["supervisor_epoch"],
        "reused": reused,
        "reason": None,
    }


def start_instance(port: int | None = None) -> dict[str, object]:
    from .stop import _integer, readback_stopped  # Import after start's module initialization.

    root = state_dir()
    # Capture the operator's invocation side of a queued Start. Reading again
    # after Stop releases the local lock must not turn that old Start into a
    # fresh explicit restart.
    initial_phase = None
    if os.path.lexists(root / "startup.json"):
        initial_phase = read_record(root / "startup.json").get("phase")
    if initial_phase == "STOPPING":
        raise StartError("INSTANCE_SHUTTING_DOWN", 4)
    deadline = time.monotonic() + 180
    data = os.environ.get("XDG_DATA_HOME")
    data_home = Path(data) if data else Path.home() / ".local/share"
    try:
        runtime = ControlRuntime(data_home, deadline)
    except StartError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError):
        raise StartError("RELEASE_OR_IMAGE_INVALID") from None
    control = control_dir(root)
    # Validate canonical paths before mkdir; no symlink aliases or partial Unix names.
    for path in (root, control, root / "http"):
        if (
            not path.is_absolute()
            or path.resolve() != path
            or len(os.fsencode(path / "control.sock")) >= 108
        ):
            raise StartError("PRIVATE_PATH_INVALID")
    if root == control or root in control.parents and control != root / "runtime-ipc":
        raise StartError("IPC_LAYOUT_INVALID")
    data_root = data_home / "omnis"
    if root == data_root or root in data_root.parents or data_root in root.parents:
        raise StartError("PRIVATE_PATH_OVERLAP")
    with ExitStack() as locks:
        locks.enter_context(lifecycle_lock(data_root, deadline))
        ensure_private(root)
        locks.enter_context(lifecycle_lock(root, deadline))
        journal = root / "startup.json"
        if os.path.lexists(root / "unreconciled.json"):
            raise StartError("RECOVERY_REQUIRED", 4)
        restarting: dict[str, object] | None = None
        if os.path.lexists(journal):
            record = read_record(journal)
            selected = record.get("port")
            if type(selected) is not int or (port is not None and selected != port):
                raise StartError("PORT_CHANGE_REQUIRES_STOP")
            if record.get("phase") == "STOPPED":
                if initial_phase != "STOPPED":
                    raise StartError("INSTANCE_SHUTTING_DOWN", 4)
                readback_stopped(runtime, root, control, record)
                restarting = record
            else:
                return verify_running(runtime, root, control, record, selected)
        if restarting is None and (
            os.path.lexists(root / "instance.json") or os.path.lexists(root / "postgres")
        ):
            raise StartError("UNOWNED_STATE_RECOVERY_REQUIRED", 4)
        if restarting is None:
            selected = port if port is not None else 8765
        else:
            selected = _integer(restarting, "port")
        preflight_port(selected)
        if (
            runtime.ids()
            or runtime.inspect("network", f"{runtime.receipt.project}_control") is not None
        ):
            raise StartError("PREEXISTING_RESOURCES_REFUSED", 4)
        for path in (control, root / "http"):
            if os.path.lexists(path):
                private_dir(path)
                allowed = {"control.lock"} if path == control else {"api.lock"}
                if any(item.name not in allowed for item in path.iterdir()):
                    raise StartError("PREEXISTING_IPC_REFUSED", 4)
        if restarting is not None:
            previous_log = root / "forwarder.log"
            archive = root / f"forwarder-{restarting['attempt']}.log"
            if os.path.lexists(previous_log):
                if os.path.lexists(archive):
                    raise StartError("RECOVERY_REQUIRED", 4)
                private_file(previous_log, limit=4 * 1024 * 1024)
                previous_log.rename(archive)
            elif not os.path.lexists(archive):
                raise StartError("RECOVERY_REQUIRED", 4)
        record = {
            "format": 1,
            "phase": "STARTING",
            "attempt": str(uuid4()),
            "project": runtime.receipt.project,
            "release_digest": runtime.digest,
            "image_id": runtime.receipt.image_id,
            "docker_host": runtime.host,
            "docker_id": runtime.receipt.docker_id,
            "control_dir": str(control),
            "port": selected,
            "containers": {},
        }
        runtime.attempt = str(record["attempt"])
        write_record(journal, record, replace=restarting is not None)
        owner = ForwarderOwnership()
        try:
            ensure_private(control)
            ensure_private(root / "http")
            if restarting is None:
                (root / "postgres").mkdir(mode=0o711)
                (root / "postgres").chmod(0o711)  # Only PG18's bind; root stays 0700.
                _put(root / "db-password", (secrets.token_hex(24) + "\n").encode())
            env = environment(runtime, root, control, selected)
            validate_config(runtime, env)
            runtime.compose(
                env, "create", "--no-recreate", "--no-build", "--pull", "never", "db", effect=True
            )
            ids = service_ids(runtime, root, control, selected)
            if set(ids) != {"db"}:
                raise StartError("UNEXPECTED_INITIAL_SERVICES", 3)
            record["containers"] = ids
            write_record(journal, record, replace=True)
            runtime.run("start", ids["db"], effect=True)
            runtime.wait_container(ids["db"], healthy=True)
            runtime.attest(ids["db"], "db", root, control, selected)
            system_id = runtime.psql(ids["db"], "SELECT system_identifier FROM pg_control_system()")
            if not re.fullmatch(r"[0-9]{1,20}", system_id):
                raise StartError("DATABASE_IDENTITY_INVALID", 3)
            record["system_id"] = system_id
            if restarting is None:
                record["phase"] = "MIGRATING"
                write_record(journal, record, replace=True)
                migration_env = {
                    "OMNIS_DATABASE_URL": env["OMNIS_DATABASE_URL"],
                    "OMNIS_EXPECTED_SYSTEM_ID": system_id,
                }
                job = runtime.run(
                    "create",
                    "--name",
                    f"{runtime.receipt.project}-migrate",
                    "--label",
                    f"com.docker.compose.project={runtime.receipt.project}",
                    "--label",
                    "com.docker.compose.service=migrate",
                    "--label",
                    f"org.omnis.start-attempt={runtime.attempt}",
                    "--network",
                    f"{runtime.receipt.project}_control",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "--env",
                    "OMNIS_DATABASE_URL",
                    "--env",
                    "OMNIS_EXPECTED_SYSTEM_ID",
                    runtime.receipt.image_id,
                    "python",
                    "-I",
                    "-m",
                    "omnis.migrate",
                    "--initialize",
                    env=migration_env,
                    effect=True,
                ).stdout.strip()
                runtime.attest(job, "migrate", root, control, selected)
                ids["migrate"] = job
                record["containers"] = ids
                write_record(journal, record, replace=True)
                runtime.run("start", job, effect=True)
                if runtime.wait_container(job).get("ExitCode") != 0:
                    raise StartError("MIGRATION_FAILED_UPDATE_REQUIRED", 3)
                runtime.attest(job, "migrate", root, control, selected)
                runtime.run("container", "rm", job, effect=True)
                if runtime.inspect("container", job) is not None:
                    raise StartError("MIGRATION_CLEANUP_UNCERTAIN", 4)
            elif system_id != restarting["system_id"]:
                raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
            verified_system, identity = database_identity(runtime, ids["db"])
            if verified_system != system_id or (
                restarting is not None and identity != restarting["instance_id"]
            ):
                raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
            record.update(phase="SERVICES", instance_id=identity)
            write_record(journal, record, replace=True)
            runtime.compose(
                env,
                "create",
                "--no-recreate",
                "--no-build",
                "--pull",
                "never",
                "supervisor",
                "api",
                effect=True,
            )
            ids = service_ids(runtime, root, control, selected)
            if set(ids) != {"db", "supervisor", "api"}:
                raise StartError("SERVICE_SET_MISMATCH", 3)
            record["containers"] = ids
            write_record(journal, record, replace=True)
            runtime.run("start", ids["supervisor"], ids["api"], effect=True)
            api_pid = api_process(runtime, ids["api"], root, control, selected)
            # VERIFYING is the HTTP/control wait, after the last Docker attestation.
            record["phase"] = "VERIFYING"
            write_record(journal, record, replace=True)
            current = wait_dashboard(
                runtime,
                root,
                control,
                selected,
                identity,
                api_pid,
                allow_closed=restarting is not None,
            )
            if restarting is None:
                if (
                    current["admission_open"] is not False
                    or current["generation"] != 0
                    or current["shutdown_command_id"] is not None
                ):
                    raise StartError("INITIAL_ADMISSION_CONFLICT", 4)
            elif (
                current["admission_open"] is not False
                or current["generation"] != restarting["stop_generation"]
                or current["shutdown_command_id"] != restarting["stop_command"]
                or current["quiesced_generation"] != restarting["stop_generation"]
                or current["shutdown_finalized"] is not True
                or _integer(current, "supervisor_epoch") <= _integer(restarting, "supervisor_epoch")
            ):
                raise StartError("RESTART_ADMISSION_CONFLICT", 4)
            record["phase"] = "FORWARDING"
            write_record(journal, record, replace=True)
            _, _, forwarder, inode = launch_forwarder(root, selected, deadline, ownership=owner)
            record.update(
                forwarder=forwarder,
                listener_inode=inode,
                api_socket=socket_identity(root / "http/api.sock"),
                control_socket=socket_identity(control / "control.sock"),
            )
            write_record(journal, record, replace=True)
            listener_owned(forwarder, selected, inode)
            dashboard(
                control,
                root / "http",
                selected,
                identity,
                runtime.files,
                deadline,
                forwarded=True,
                api_pid=api_pid,
                allow_closed=restarting is not None,
            )
            # Only this verified new instance may open; never reopen an existing closed barrier.
            remaining(deadline)
            command_id = str(uuid4())
            record["open_command"] = command_id
            write_record(journal, record, replace=True)
            opening_generation = (
                0 if restarting is None else _integer(restarting, "stop_generation")
            )
            current = request(
                control,
                {
                    "op": "open",
                    "instance_id": identity,
                    "command_id": command_id,
                    "expected_generation": opening_generation,
                },
                deadline=deadline,
            )
            if (
                current["admission_open"] is not True
                or current["generation"] != opening_generation + 1
            ):
                raise StartError("ADMISSION_OPEN_UNVERIFIED", 4)
            instance = Instance(
                identity,
                "0.1.0",
                EXPECTED_SCHEMA,
                runtime.receipt.project,
                f"http://127.0.0.1:{selected}",
            )
            if restarting is None:
                write_record(root / "instance.json", {"version": 1, **asdict(instance)})
            elif load_instance(root) != instance:
                raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
            record.update(
                phase="READY",
                generation=current["generation"],
                supervisor_epoch=current["supervisor_epoch"],
            )
            # Verify the candidate receipt before atomically publishing READY.
            result = verify_running(runtime, root, control, record, selected)
            write_record(journal, record, replace=True)
            result["reused"] = False
            return result
        except BaseException as exc:
            # Repeated terminal interrupts cannot abandon this attempt's bounded cleanup.
            for sig in (signal.SIGTERM, signal.SIGINT):
                if signal.getsignal(sig) is _interrupt:
                    signal.signal(sig, signal.SIG_IGN)
            failed_phase = record["phase"]
            if owner.process is not None:
                # Locator only, never authority to signal a metadata PID on retry.
                record["forwarder_spawn_pid"] = owner.process.pid
            problems = cleanup_attempt(runtime, root, control, selected, owner.process, owner.pidfd)
            record.update(
                failed_phase=failed_phase,
                failure=exc.reason if isinstance(exc, StartError) else "STARTUP_FAILED",
                phase="UNCERTAIN" if problems else "FAILED_CLEANED",
                cleanup=problems,
            )
            try:
                write_record(journal, record, replace=True)
            except (OSError, ValueError):
                problems.append("cleanup journal unavailable")
            if problems:
                raise StartError("STARTUP_CLEANUP_UNCERTAIN", 4) from None
            raise
        finally:
            if owner.pidfd >= 0:
                os.close(owner.pidfd)


def _interrupt(signum: int, frame: FrameType | None) -> None:
    # A handled retry exception is NOT cancellation. Only an existing stop,
    # failed forwarder handoff, or failure already propagated to start_instance
    # commits startup to unwind/cleanup. Its traceback exists even before the
    # outer except binds `exc`, so a repeated stop cannot skip cleanup entry.
    failure = sys.exception()
    if isinstance(failure, (KeyboardInterrupt, ForwarderStartError)):
        return
    trace = failure.__traceback__ if failure is not None else None
    while trace is not None:
        if trace.tb_frame.f_code is start_instance.__code__:
            return
        trace = trace.tb_next
    raise KeyboardInterrupt()


def start_result(port: int | None) -> tuple[int, dict[str, object]]:
    previous = {sig: signal.signal(sig, _interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        result = start_instance(port)
        code = 0
    except (
        OSError,
        ValueError,
        ControlUnavailable,
        http.client.HTTPException,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as exc:
        code = exc.code if isinstance(exc, StartError) else 3
        result = {
            "state": "REFUSED" if code == 2 else "UNCERTAIN" if code == 4 else "FAILED",
            "reason": exc.reason if isinstance(exc, StartError) else "STARTUP_FAILED",
            "dashboard_ready": False,
            "assessment_ready": False,
            "browser_opened": False,
        }
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return code, result


def start(*, port: int | None, as_json: bool) -> int:
    code, result = start_result(port)
    if as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"Omnis: {result['state']} ({result.get('reason') or 'dashboard ready; no assessment'})"
        )
        if result.get("origin"):
            print(f"{result['origin']}/")
        if code:
            print(
                "Verificați releaseul instalat, imaginea locală și starea privată; fără retry distructiv.",
                file=sys.stderr,
            )
    return code
