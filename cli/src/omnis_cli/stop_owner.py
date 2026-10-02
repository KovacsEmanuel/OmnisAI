"""One-shot host Stop owner; anonymous handoff, no subprocess effect clients.

Only the launcher imports the three public functions. The fixed -I entrypoint
accepts three inherited FD numbers, never commands, URLs or resource selectors.
"""

import fcntl
import hashlib
import json
import math
import os
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

from .compose import _record
from .instance import private_dir, private_file, unique_pairs
from .lifecycle import (
    StartError,
    listener_owned,
    mapping,
    process_identity,
    read_record,
    socket_identity,
)
from .release import _installed_pointer, _manifest
from .start import _bound_instance, _check_pgdata, _owned_record, _pgdata_receipt
from .start_runtime import POSTGRES, SAFE_PATH, ControlRuntime
from .stop_engine import StopEngine, identifier
from .stop_receipt import (
    STAGES,
    completed_receipt,
    encoded,
    fingerprint,
    persist,
    receipt_path,
    validate_grant,
)


class _View(ControlRuntime):
    """Reuse the installed topology attestor, replacing *all* command execution."""

    def __init__(self, runtime: ControlRuntime, engine: StopEngine) -> None:
        self.deadline, self.engine = engine.deadline, engine
        self.release, self.digest, self.receipt = runtime.release, runtime.digest, runtime.receipt
        self.host, self.pg_image = runtime.host, runtime.pg_image
        self.attempt = runtime.attempt
        self.uncertain, self.family_drained = False, True

    def run(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cap: float = 15,
        success: bool = True,
        effect: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        raise StartError("STOP_COMMAND_EXECUTION_FORBIDDEN", 4)

    def check_daemon(self) -> None:
        self.engine.check_daemon()

    def inspect(self, kind: str, ident: str) -> dict[str, object] | None:
        if kind == "container":
            return self.engine.container(ident)
        if kind == "network":
            return self.engine.network(ident)
        raise StartError("STOP_INSPECT_FORBIDDEN", 4)

    def ids(self) -> list[str]:
        return self.engine.containers(self.receipt.project)

    def network(self, allowed: set[str]) -> str | None:
        self.check_daemon()
        rows = self.engine.networks(self.receipt.project)
        if not rows:
            return None
        if len(rows) != 1:
            raise StartError("STOP_NETWORK_DRIFT", 4)
        ident = identifier(str(rows[0].get("Id")))
        item = self.engine.network(ident)
        if item is None or (
            item.get("Name") != self.receipt.project + "_control"
            or mapping(item.get("Labels")).get("org.omnis.start-attempt") != self.attempt
            or mapping(item.get("Labels")).get("com.docker.compose.project") != self.receipt.project
            or item.get("Internal") is not True
            or item.get("Driver") != "bridge"
            or set(mapping(item.get("Containers"))) - allowed
        ):
            raise StartError("STOP_NETWORK_DRIFT", 4)
        return ident


def _load_runtime(data_home: Path, record: dict[str, object], deadline: float) -> ControlRuntime:
    # No ControlRuntime constructor: it executes Docker CLI clients.
    runtime = ControlRuntime.__new__(ControlRuntime)
    private_dir(data_home / "omnis")
    if not _installed_pointer(data_home / "omnis/installed.json"):
        raise StartError("STOP_RELEASE_INVALID", 4)
    runtime.release = data_home / "omnis/releases/0.1.0"
    manifest, runtime.files = _manifest(runtime.release)
    runtime.digest = hashlib.sha256(manifest).hexdigest()
    receipt = _record(data_home / "omnis/image.json", runtime.digest, complete=True)
    if receipt is None:
        raise StartError("STOP_RELEASE_INVALID", 4)
    runtime.receipt, runtime.host = receipt, receipt.docker_host
    runtime.attempt = str(record["attempt"])
    runtime.deadline, runtime.uncertain, runtime.family_drained = deadline, False, True
    engine = StopEngine(runtime.host, receipt.docker_id, deadline)
    engine.check_daemon()
    item = engine.container(str(mapping(record["containers"])["db"]))
    if item is None:
        raise StartError("STOP_CONTAINER_ABSENT_WITHOUT_ACK", 4)
    runtime.pg_image = str(item.get("Image"))
    image = engine.image(runtime.pg_image)
    if (
        image.get("Id") != runtime.pg_image
        or image.get("Os") != "linux"
        or image.get("Architecture") != "amd64"
        or POSTGRES.replace(":18.6-bookworm", "")
        not in cast(list[object], image.get("RepoDigests", []))
    ):
        raise StartError("STOP_IMAGE_DRIFT", 4)
    return runtime


def _view(runtime: ControlRuntime, deadline: float | None = None) -> _View:
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("STOP_PRIOR_UNCERTAINTY", 4)
    return _View(
        runtime,
        StopEngine(
            runtime.host,
            runtime.receipt.docker_id,
            runtime.deadline if deadline is None else deadline,
        ),
    )


def _static(runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]) -> None:
    _pgdata_receipt(record)
    _owned_record(record)
    _check_pgdata(root, record)
    _bound_instance(runtime, root, control, record)
    private_dir(root)
    private_dir(control)
    private_file(root / "db-password", limit=64)
    if os.path.lexists(root / "unreconciled.json"):
        raise StartError("RECOVERY_REQUIRED", 4)
    if read_record(root / "startup.json") != record:
        raise StartError("STOP_JOURNAL_DRIFT", 4)


def _file_identity(path: Path) -> list[int]:
    private_file(path, limit=16384)
    info = path.lstat()
    return [info.st_dev, info.st_ino]


def _process_stamp(identity: dict[str, object]) -> dict[str, object]:
    return {key: identity[key] for key in ("pid", "start_ticks", "boot_id")}


def _container_fingerprint(item: dict[str, object]) -> str:
    return fingerprint(
        {
            key: item.get(key)
            for key in (
                "Id",
                "Image",
                "Config",
                "HostConfig",
                "Mounts",
                "Path",
                "Args",
                "Name",
                "Created",
            )
        }
    )


def _network_fingerprint(item: dict[str, object]) -> str:
    return fingerprint({key: value for key, value in item.items() if key != "Containers"})


def _incarnation(item: dict[str, object]) -> str:
    state = mapping(item.get("State"))
    pid = state.get("Pid")
    if type(pid) is not int or pid <= 1:
        raise StartError("STOP_CONTAINER_PROCESS_INVALID", 4)
    details = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    if details[0] == "Z":
        raise StartError("STOP_CONTAINER_PROCESS_INVALID", 4)
    return fingerprint(
        {
            "pid": pid,
            "ticks": details[19],
            "started": state.get("StartedAt"),
            "restarts": item.get("RestartCount"),
        }
    )


def prepare_stop_inventory(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
) -> dict[str, object]:
    """Read-only exact attestation; caller must hold both lifecycle locks."""
    _static(runtime, root, control, record)
    view = _view(runtime)
    view.attempt = str(record["attempt"])
    ids = mapping(record["containers"])
    if set(view.ids()) != set(ids.values()):
        raise StartError("STOP_CONTAINER_DRIFT", 4)
    network_id = view.network(set(cast(list[str], list(ids.values()))))
    if network_id is None:
        raise StartError("STOP_NETWORK_DRIFT", 4)
    network = view.engine.network(network_id)
    assert network is not None
    containers = []
    for role in ("api", "supervisor", "db"):
        cid = str(ids[role])
        item = view.attest(cid, role, root, control, int(str(record["port"])))
        state = mapping(item.get("State"))
        if (
            state.get("Running") is not True
            or state.get("Paused") is not False
            or state.get("Restarting") is not False
        ):
            raise StartError("STOP_CONTAINER_NOT_RUNNING", 4)
        nets = mapping(mapping(item.get("NetworkSettings")).get("Networks"))
        if mapping(nets.get(view.receipt.project + "_control")).get("NetworkID") != network_id:
            raise StartError("STOP_NETWORK_DRIFT", 4)
        containers.append(
            {
                "role": role,
                "id": cid,
                "image": item["Image"],
                "config": _container_fingerprint(item),
                "run": _incarnation(item),
            }
        )
    identity = mapping(record["forwarder"])
    listener_owned(identity, int(str(record["port"])), int(str(record["listener_inode"])))
    argv = identity.get("argv")
    if not isinstance(argv, list) or argv[-2:] != ["--stop-attempt", record["attempt"]]:
        raise StartError("STOP_FORWARDER_DRAIN_UNSUPPORTED", 4)
    api, ctl = socket_identity(root / "http/api.sock"), socket_identity(control / "control.sock")
    if api != record["api_socket"] or ctl != record["control_socket"]:
        raise StartError("STOP_IPC_DRIFT", 4)
    inventory: dict[str, object] = {
        "version": 1,
        "release": runtime.digest,
        "project": runtime.receipt.project,
        "attempt": record["attempt"],
        "pgdata": record["pgdata_identity"],
        "system_id": record["system_id"],
        "containers": containers,
        "network": {"id": network_id, "config": _network_fingerprint(network)},
        "forwarder": {
            **_process_stamp(identity),
            "identity": fingerprint(identity),
            "listener": record["listener_inode"],
            "port": record["port"],
        },
        "ipc": {
            "api": api,
            "control": ctl,
            "api_lock": _file_identity(root / "http/api.lock"),
            "control_lock": _file_identity(control / "control.lock"),
            "cap": _file_identity(control / "control.cap"),
            "cap_digest": fingerprint(private_file(control / "control.cap", limit=64)),
        },
    }
    # Leave room for the fixed arm-stop command and correlated 4096-byte reply.
    if len(encoded(inventory)) > 2900:
        raise StartError("STOP_INVENTORY_FRAME_LIMIT", 4)
    view.check_daemon()
    return inventory


def _validate_lock(fd: int, root: Path, parent: int) -> None:
    private_dir(root)
    info, current = os.fstat(fd), (root / "lifecycle.lock").lstat()
    parent_info = Path(f"/proc/{parent}/fd/{fd}").stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)
        or (info.st_dev, info.st_ino) != (parent_info.st_dev, parent_info.st_ino)
    ):
        raise StartError("STOP_ORIGINAL_LOCK_REQUIRED", 4)
    local = [
        line.split()[2:]
        for line in Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines()
        if line.startswith("lock:")
    ]
    original = [
        line.split()[2:]
        for line in Path(f"/proc/{parent}/fdinfo/{fd}").read_text().splitlines()
        if line.startswith("lock:")
    ]
    if len(local) != 1 or local != original or local[0][:3] != ["FLOCK", "ADVISORY", "WRITE"]:
        raise StartError("STOP_ORIGINAL_LOCK_REQUIRED", 4)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise StartError("STOP_OWNER_TIMEOUT", 4)
    return remaining


def _receive(channel: socket.socket, deadline: float, parent_fd: int | None = None) -> bytes:
    watched = [channel.fileno()] + ([] if parent_fd is None else [parent_fd])
    ready = select.select(watched, [], [], _remaining(deadline))[0]
    if not ready or parent_fd in ready:
        raise StartError("STOP_HANDOFF_REFUSED", 4)
    data, _anc, flags, _address = channel.recvmsg(16384)
    if not data or flags:
        raise StartError("STOP_HANDOFF_REFUSED", 4)
    return data


def _listener_absent(record: dict[str, object]) -> None:
    from .stop import _listener_absent as readback

    readback(record)


def _ipc_absent(root: Path, control: Path, inventory: dict[str, object]) -> None:
    _ipc_progress(root, control, inventory, {"api", "supervisor"})


def _ipc_progress(
    root: Path, control: Path, inventory: dict[str, object], stopped: set[str]
) -> None:
    # Existing service locks serialize legitimate writers; no pathname cleanup.
    expected = mapping(inventory["ipc"])
    fds: list[int] = []
    try:
        for directory, stem, role in (
            (root / "http", "api", "api"),
            (control, "control", "supervisor"),
        ):
            path = directory / f"{stem}.lock"
            if _file_identity(path) != expected[f"{stem}_lock"]:
                raise StartError("STOP_IPC_DRIFT", 4)
            sock = directory / f"{stem}.sock"
            if role not in stopped:
                if socket_identity(sock) != expected[stem]:
                    raise StartError("STOP_IPC_DRIFT", 4)
                if stem == "control" and (
                    _file_identity(control / "control.cap") != expected["cap"]
                    or fingerprint(private_file(control / "control.cap", limit=64))
                    != expected["cap_digest"]
                ):
                    raise StartError("STOP_IPC_DRIFT", 4)
                continue
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            fds.append(fd)  # Includes cleanup if the second acquisition fails.
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.path.lexists(sock) or (
                stem == "control" and os.path.lexists(control / "control.cap")
            ):
                raise StartError("STOP_IPC_REMAINS", 4)
    finally:
        for fd in reversed(fds):
            os.close(fd)


class _ContainerFamily:
    """Read-only cgroup-v2 evidence, not a cgroup manager or cleanup authority."""

    def __init__(self, cid: str, state: dict[str, object]) -> None:
        pid = state.get("Pid")
        if type(pid) is not int or pid <= 1:
            raise StartError("STOP_CONTAINER_FAMILY_UNVERIFIED", 4)
        self.fd = os.pidfd_open(pid)
        try:
            rows = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
            if len(rows) != 1 or not rows[0].startswith("0::/"):
                raise StartError("STOP_CONTAINER_FAMILY_UNVERIFIED", 4)
            relative = rows[0][4:]
            if cid not in relative or ".." in Path(relative).parts:
                raise StartError("STOP_CONTAINER_FAMILY_UNVERIFIED", 4)
            self.path = Path("/sys/fs/cgroup") / relative
            if self.path.resolve(strict=True) != self.path:
                raise StartError("STOP_CONTAINER_FAMILY_UNVERIFIED", 4)
            info = self.path.stat()
            self.identity = (info.st_dev, info.st_ino)
            if str(pid) not in (self.path / "cgroup.procs").read_text().splitlines():
                raise StartError("STOP_CONTAINER_FAMILY_UNVERIFIED", 4)
        except BaseException:
            os.close(self.fd)
            raise

    def drained(self) -> None:
        if not select.select([self.fd], [], [], 0)[0]:
            raise StartError("STOP_CONTAINER_FAMILY_LIVE", 4)
        if os.path.lexists(self.path):
            info = self.path.stat()
            if (info.st_dev, info.st_ino) != self.identity:
                raise StartError("STOP_CONTAINER_FAMILY_UNVERIFIED", 4)
            # populated includes descendants, unlike reading only cgroup.procs.
            events = dict(
                row.split() for row in (self.path / "cgroup.events").read_text().splitlines()
            )
            if events.get("populated") != "0":
                raise StartError("STOP_CONTAINER_FAMILY_LIVE", 4)

    def close(self) -> None:
        os.close(self.fd)


def _stopped(item: dict[str, object]) -> None:
    state = mapping(item.get("State"))
    if (
        state.get("Running") is not False
        or state.get("Paused") is not False
        or state.get("Restarting") is not False
        or state.get("Dead") is not False
        or state.get("OOMKilled") is not False
        or type(state.get("ExitCode")) is not int
        or state["ExitCode"] != 0
        or type(state.get("Pid")) is not int
        or state["Pid"] != 0
        or state.get("Status") != "exited"
        or state.get("Error") != ""
    ):
        raise StartError("STOP_CONTAINER_EXIT_UNCERTAIN", 4)


def _execute(
    view: _View,
    root: Path,
    control: Path,
    record: dict[str, object],
    grant: dict[str, object],
    receipt: dict[str, object],
    forwarder_fd: int,
) -> None:
    inventory = mapping(grant["inventory"])
    path = receipt_path(root, record)
    completed: list[dict[str, object]] = []
    receipt["completed"] = completed
    stopped: set[str] = set()

    def prepare(stage: str) -> None:
        _remaining(view.deadline)
        _static(view, root, control, record)
        _ipc_progress(root, control, inventory, stopped)
        view.check_daemon()
        receipt.update(state="PREPARED", pending=stage)
        persist(path, receipt, replace=True)

    def complete(stage: str, ack: object, evidence: object) -> None:
        view.check_daemon()
        completed.append({"stage": stage, "ack": ack, "proof": fingerprint(evidence)})
        receipt.update(state="RUNNING", pending=None)
        persist(path, receipt, replace=True)

    # Refuse unsupported/unpinnable families before even signalling forwarder.
    for pinned in cast(list[dict[str, object]], inventory["containers"]):
        item = view.attest(
            str(pinned["id"]), str(pinned["role"]), root, control, int(str(record["port"]))
        )
        if _incarnation(item) != pinned["run"]:
            raise StartError("STOP_CONTAINER_DRIFT", 4)
        family = _ContainerFamily(str(pinned["id"]), mapping(item.get("State")))
        family.close()
    identity = mapping(record["forwarder"])
    prepare("forwarder")
    listener_owned(identity, int(str(record["port"])), int(str(record["listener_inode"])))
    intent = {
        "version": 1,
        "attempt": record["attempt"],
        "command_id": record["stop_command"],
        "forwarder": identity,
        "listener_inode": record["listener_inode"],
    }
    persist(root / f"stop-forwarder-{record['attempt']}.json", intent)
    signal.pidfd_send_signal(forwarder_fd, signal.SIGTERM)
    if not select.select([forwarder_fd], [], [], min(25, _remaining(view.deadline)))[0]:
        raise StartError("STOP_FORWARDER_DRAIN_UNCERTAIN", 4)
    drain = read_record(root / f"stop-forwarder-{record['attempt']}-drained.json")
    if encoded(drain) != encoded({**intent, "drained": True}):
        raise StartError("STOP_FORWARDER_DRAIN_UNCERTAIN", 4)
    _listener_absent(record)
    complete("forwarder", "DRAINED", drain)
    containers = cast(list[dict[str, object]], inventory["containers"])
    remaining_ids = {str(row["id"]) for row in containers}
    network = mapping(inventory["network"])
    for pinned in containers:
        role, cid = str(pinned["role"]), str(pinned["id"])
        if set(view.ids()) != remaining_ids or view.network(remaining_ids) != network["id"]:
            raise StartError("STOP_RESOURCE_DRIFT", 4)
        item = view.attest(cid, role, root, control, int(str(record["port"])))
        if _container_fingerprint(item) != pinned["config"] or _incarnation(item) != pinned["run"]:
            raise StartError("STOP_CONTAINER_DRIFT", 4)
        family = _ContainerFamily(cid, mapping(item.get("State")))
        try:
            prepare(role + ".stop")
            ack = view.engine.stop_container(cid)
            after = view.attest(cid, role, root, control, int(str(record["port"])))
            if _container_fingerprint(after) != pinned["config"]:
                raise StartError("STOP_CONTAINER_DRIFT", 4)
            _stopped(after)
            family.drained()
            stopped.add(role)
            _ipc_progress(root, control, inventory, stopped)
            complete(role + ".stop", ack, {"state": after["State"], "family_empty": True})
            prepare(role + ".rm")
            after = view.attest(cid, role, root, control, int(str(record["port"])))
            if _container_fingerprint(after) != pinned["config"]:
                raise StartError("STOP_CONTAINER_DRIFT", 4)
            _stopped(after)
            family.drained()
            ack = view.engine.remove_container(cid)
            if view.engine.container(cid) is not None:
                raise StartError("STOP_CONTAINER_REMOVAL_UNCERTAIN", 4)
            remaining_ids.remove(cid)
            if set(view.ids()) != remaining_ids:
                raise StartError("STOP_RESOURCE_DRIFT", 4)
            complete(role + ".rm", ack, {"absent": cid})
        finally:
            family.close()
    prepare("network.rm")
    if view.ids() or view.network(set()) != network["id"]:
        raise StartError("STOP_RESOURCE_DRIFT", 4)
    current = view.engine.network(str(network["id"]))
    if (
        current is None
        or _network_fingerprint(current) != network["config"]
        or mapping(current.get("Containers"))
    ):
        raise StartError("STOP_NETWORK_DRIFT", 4)
    ack = view.engine.remove_network(str(network["id"]))
    if view.engine.network(str(network["id"])) is not None or view.engine.networks(
        view.receipt.project
    ):
        raise StartError("STOP_NETWORK_REMOVAL_UNCERTAIN", 4)
    complete("network.rm", ack, {"absent": network["id"]})
    prepare("ipc")
    _ipc_absent(root, control, inventory)
    _listener_absent(record)
    complete("ipc", "DRAINED", inventory["ipc"])
    if [entry["stage"] for entry in completed] != list(STAGES):
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    receipt.update(state="COMPLETED", pending=None)
    persist(path, receipt, replace=True)


def verify_stop_completion(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    record: dict[str, object],
    grant: dict[str, object] | None = None,
) -> None:
    """Strict read-only Stop repeat/Start gate; never replays a pending effect."""
    _static(runtime, root, control, record)
    path = receipt_path(root, record)
    stored = read_record(path)
    saved_grant = mapping(stored.get("grant"))
    if grant is not None and encoded(grant) != encoded(saved_grant):
        raise StartError("STOP_GRANT_DRIFT", 4)
    inventory = mapping(saved_grant.get("inventory"))
    validate_grant(saved_grant, record, inventory)
    completed_receipt(path, saved_grant)
    if (
        inventory.get("release") != runtime.digest
        or inventory.get("project") != runtime.receipt.project
        or inventory.get("attempt") != record["attempt"]
        or inventory.get("pgdata") != record["pgdata_identity"]
        or inventory.get("system_id") != record["system_id"]
    ):
        raise StartError("STOP_INVENTORY_DRIFT", 4)
    rows = inventory.get("containers")
    if not isinstance(rows, list) or len(rows) != 3:
        raise StartError("STOP_INVENTORY_DRIFT", 4)
    if {str(mapping(row).get("role")): mapping(row).get("id") for row in rows} != record[
        "containers"
    ]:
        raise StartError("STOP_INVENTORY_DRIFT", 4)
    view = _view(runtime)
    view.check_daemon()
    if view.ids() or view.engine.networks(runtime.receipt.project):
        raise StartError("STOP_RESOURCES_REMAIN", 4)
    for row in rows:
        if view.engine.container(str(mapping(row)["id"])) is not None:
            raise StartError("STOP_RESOURCES_REMAIN", 4)
    if view.engine.network(str(mapping(inventory["network"])["id"])) is not None:
        raise StartError("STOP_RESOURCES_REMAIN", 4)
    _ipc_absent(root, control, inventory)
    _listener_absent(record)
    intent = {
        "version": 1,
        "attempt": record["attempt"],
        "command_id": record["stop_command"],
        "forwarder": record["forwarder"],
        "listener_inode": record["listener_inode"],
        "drained": True,
    }
    if encoded(read_record(root / f"stop-forwarder-{record['attempt']}-drained.json")) != encoded(
        intent
    ):
        raise StartError("STOP_FORWARDER_DRAIN_UNCERTAIN", 4)
    try:
        if process_identity(int(str(mapping(record["forwarder"])["pid"]))) == record["forwarder"]:
            raise StartError("STOP_FORWARDER_STILL_LIVE", 4)
    except (FileNotFoundError, ProcessLookupError):
        pass
    except StartError as exc:
        if exc.reason != "FORWARDER_NOT_LIVE":
            raise
    view.check_daemon()


def _wait_owner(process: subprocess.Popen[bytes], deadline: float) -> None:
    while True:
        observed = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if observed is not None:
            code = observed.si_status if observed.si_code == os.CLD_EXITED else -observed.si_status
            if process.wait(timeout=_remaining(deadline)) != code or code != 0:
                raise StartError("STOP_OWNER_UNCERTAIN", 4)
            return
        time.sleep(min(0.01, _remaining(deadline)))


def run_stop_owner(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    record: dict[str, object],
    grant: dict[str, object],
    *,
    lock_fds: tuple[int, int],
    deadline: float | None = None,
) -> None:
    end = min(
        runtime.deadline, time.monotonic() + 180, runtime.deadline if deadline is None else deadline
    )
    _remaining(end)
    _validate_lock(lock_fds[0], runtime.release.parents[1], os.getpid())
    _validate_lock(lock_fds[1], root, os.getpid())
    inventory = prepare_stop_inventory(runtime, root, control, record)
    validate_grant(grant, record, inventory)
    path = receipt_path(root, record)
    if os.path.lexists(path):
        raise StartError("STOP_OWNER_REPLAY_REFUSED", 4)
    receipt: dict[str, object] = {
        "version": 1,
        "grant": grant,
        "owner": None,
        "launcher": _process_stamp(process_identity(os.getpid())),
        "state": "PREPARED",
        "pending": None,
        "completed": [],
    }
    persist(path, receipt)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    process: subprocess.Popen[bytes] | None = None
    pidfd = -1
    admitted = False
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-m",
                "omnis_cli.stop_owner",
                str(child.fileno()),
                str(lock_fds[0]),
                str(lock_fds[1]),
            ],
            pass_fds=(child.fileno(), *lock_fds),
            cwd=root,
            env={"PATH": SAFE_PATH},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        child.close()
        pidfd = os.pidfd_open(process.pid)
        payload = {
            "root": str(root),
            "control": str(control),
            "data_home": str(runtime.release.parents[2]),
            "record": record,
            "grant": grant,
            "deadline_ns": int(end * 1_000_000_000),
        }
        parent.settimeout(_remaining(end))
        if parent.send(encoded(payload)) != len(encoded(payload)):
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        if _receive(parent, end) != b"READY":
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        # The owner is pinned before one and only one admission write.
        if select.select([pidfd], [], [], 0)[0]:
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        admitted = True  # A fallible send can already deliver the command.
        if parent.send(b"ADMIT") != 5:
            raise StartError("STOP_HANDOFF_UNCERTAIN", 4)
        if _receive(parent, end) != b"DONE":
            raise StartError("STOP_OWNER_UNCERTAIN", 4)
        _wait_owner(process, end)
        verify_stop_completion(runtime, root, control, record, grant)
    finally:
        parent.close()
        child.close()
        if process is not None and process.returncode is None:
            # EOF is not an exit acknowledgement. Reap nonblocking/bounded even
            # on the failed-reply path; after ADMIT allow the owner its budget.
            try:
                process.wait(timeout=max(0.1, end - time.monotonic() + 1) if admitted else 3)
            except subprocess.TimeoutExpired:
                if pidfd >= 0:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    process.wait(timeout=2)
                # Missing pin never authorizes a numeric PID signal. Pre-ADMIT
                # EOF and the child's independent admission deadline fail closed.
        if pidfd >= 0:
            os.close(pidfd)


def _entry(channel_fd: int, data_fd: int, state_fd: int) -> int:
    parent_fd = forwarder_fd = -1
    channel = socket.socket(fileno=channel_fd)
    try:
        if (
            len({channel_fd, data_fd, state_fd}) != 3
            or channel.family != socket.AF_UNIX
            or channel.type != socket.SOCK_SEQPACKET
        ):
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        pid, uid, _gid = struct.unpack(
            "3i", channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        )
        if uid != os.getuid() or pid != os.getppid() or channel.getsockname() not in {"", b""}:
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        parent_fd = os.pidfd_open(pid)
        raw = _receive(channel, time.monotonic() + 5, parent_fd)
        payload = mapping(json.loads(raw, object_pairs_hook=unique_pairs))
        if (
            set(payload) != {"root", "control", "data_home", "record", "grant", "deadline_ns"}
            or type(payload["deadline_ns"]) is not int
        ):
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        end = int(str(payload["deadline_ns"])) / 1_000_000_000
        if not 0 < end - time.monotonic() <= 180:
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        signal.alarm(
            math.ceil(_remaining(end))
        )  # Fail closed if a syscall/parser unexpectedly stalls.
        root, control, data_home = (
            Path(str(payload[key])) for key in ("root", "control", "data_home")
        )
        _validate_lock(data_fd, data_home / "omnis", pid)
        _validate_lock(state_fd, root, pid)
        record, grant = mapping(payload["record"]), mapping(payload["grant"])
        runtime = _load_runtime(data_home, record, end)
        inventory = prepare_stop_inventory(runtime, root, control, record)
        validate_grant(grant, record, inventory)
        path = receipt_path(root, record)
        receipt = read_record(path)
        expected = {
            "version": 1,
            "grant": grant,
            "owner": None,
            "launcher": _process_stamp(process_identity(pid)),
            "state": "PREPARED",
            "pending": None,
            "completed": [],
        }
        if encoded(receipt) != encoded(expected):
            raise StartError("STOP_OWNER_REPLAY_REFUSED", 4)
        forwarder = mapping(record["forwarder"])
        forwarder_fd = os.pidfd_open(int(str(forwarder["pid"])))
        listener_owned(forwarder, int(str(record["port"])), int(str(record["listener_inode"])))
        receipt["owner"] = _process_stamp(process_identity(os.getpid()))
        persist(path, receipt, replace=True)
        _validate_lock(data_fd, data_home / "omnis", pid)
        _validate_lock(state_fd, root, pid)
        if select.select([parent_fd], [], [], 0)[0]:
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        channel.sendall(b"READY")
        if _receive(channel, end, parent_fd) != b"ADMIT":
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        os.close(parent_fd)
        parent_fd = -1  # No parent-death kill or parent liveness requirement after admission.
        if encoded(prepare_stop_inventory(runtime, root, control, record)) != encoded(inventory):
            raise StartError("STOP_INVENTORY_DRIFT", 4)
        _execute(_view(runtime), root, control, record, grant, receipt, forwarder_fd)
        verify_stop_completion(runtime, root, control, record, grant)
        try:
            channel.sendall(b"DONE")
        except (BrokenPipeError, ConnectionResetError):
            pass  # Durable completion is authoritative when the launcher has died.
        return 0
    finally:
        for fd in (forwarder_fd, parent_fd):
            if fd >= 0:
                os.close(fd)
        channel.close()
        # Process exit closes original lock descriptions; never LOCK_UN.


def main() -> int:
    try:
        if len(sys.argv) != 4 or not sys.flags.isolated:
            raise StartError("STOP_HANDOFF_REFUSED", 4)
        return _entry(*(int(value) for value in sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
