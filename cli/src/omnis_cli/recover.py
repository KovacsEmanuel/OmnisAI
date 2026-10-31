"""One-shot T1 owner-loss recovery to Stop, never OPEN or uncertain-effect retry."""

import errno
import fcntl
import json
import os
import socket
import stat
import time
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

from .control import ControlUnavailable, _uuid, request
from .health import http_probe
from .instance import private_dir, private_file, unique_pairs
from .lifecycle import (
    StartError,
    listener_owned,
    mapping,
    read_record,
    remaining,
    socket_identity,
    write_record,
)
from .release import _sync_dir, publish_directory
from .start import (
    ForwarderOwnership,
    _bound_instance,
    _check_pgdata,
    _publish_forwarder,
    _ready_record,
    api_process,
    database_identity,
    launch_forwarder,
    preflight_port,
    service_ids,
    stop_forwarder,
)
from .start_runtime import ControlRuntime
from .stop import _containers, _integer, _listener_absent, _stopping_record


def _owner(
    runtime: ControlRuntime, record: dict[str, object], current: dict[str, object] | None = None
) -> str:
    generation = _integer(record, "generation")
    epoch = _integer(record, "supervisor_epoch")
    if current is None:
        predicate = (
            f"c.generation = {generation} AND l.epoch = {epoch} "
            "AND l.expires_at <= clock_timestamp() AND c.admission_open "
            "AND c.shutdown_command_id IS NULL AND c.quiesced_generation IS NULL "
            "AND EXISTS (SELECT 1 FROM instance_command WHERE "
            f"command_id = '{record['open_command']}'::uuid AND kind = 'OPEN' "
            f"AND expected_generation = {generation - 1} AND result_generation = {generation} "
            f"AND owner_epoch = {epoch})"
        )
    else:
        implicit = current.get("shutdown_command_id")
        if not _uuid(implicit):
            raise StartError("RECOVERY_BARRIER_UNVERIFIED", 4)
        predicate = (
            f"c.generation = {generation + 1} AND l.epoch = {epoch + 1} "
            "AND l.expires_at > clock_timestamp() AND NOT c.admission_open "
            f"AND c.shutdown_command_id = '{implicit}'::uuid "
            "AND c.quiesced_generation = c.generation AND c.quiesced_at IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM instance_command WHERE "
            "command_id = c.shutdown_command_id) "
            "AND NOT EXISTS (SELECT 1 FROM instance_command WHERE kind = 'FINALIZE' "
            "AND result_generation = c.generation)"
        )
    query = (
        "SELECT json_build_object('owner', l.owner, 'eligible', "
        f"c.instance_id = '{record['instance_id']}'::uuid AND l.owner IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM instance_stop_fence WHERE id = 1) AND "
        + predicate
        + ") FROM instance_control c CROSS JOIN supervisor_lease l WHERE c.id = 1 AND l.id = 1"
    )
    value = json.loads(
        runtime.psql(_containers(record)["db"], query), object_pairs_hook=unique_pairs
    )
    if (
        type(value) is not dict
        or set(value) != {"owner", "eligible"}
        or value["eligible"] is not True
        or not _uuid(value["owner"])
    ):
        raise StartError("RECOVERY_AUTHORITY_UNVERIFIED", 4)
    owner = value["owner"]
    assert isinstance(owner, str)
    return owner


def _inventory(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object], *, dead: bool
) -> int:
    _ready_record(record)
    _check_pgdata(root, record)
    _bound_instance(runtime, root, control, record)
    port = _integer(record, "port")
    runtime.attempt = str(record["attempt"])
    ids = service_ids(runtime, root, control, port)
    if ids != _containers(record):
        raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
    if database_identity(runtime, ids["db"]) != (record["system_id"], record["instance_id"]):
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    pid = 0
    for role, cid in ids.items():
        state = mapping(runtime.attest(cid, role, root, control, port).get("State"))
        if dead and role == "supervisor":
            if (
                state.get("Running") is not False
                or state.get("Status") != "exited"
                or state.get("Pid") != 0
                or type(state.get("Pid")) is not int
                or state.get("Paused") is not False
                or state.get("Restarting") is not False
                or state.get("Dead") is not False
                or state.get("Error") != ""
            ):
                raise StartError("SUPERVISOR_NOT_DEAD", 4)
        elif (
            state.get("Running") is not True
            or state.get("Paused") is not False
            or state.get("Restarting") is not False
        ):
            raise StartError("RECOVERY_RESOURCE_NOT_RUNNING", 4)
        if role == "supervisor" and not dead:
            raw = state.get("Pid")
            if type(raw) is not int or raw <= 1:
                raise StartError("RECOVERY_OWNER_UNVERIFIED", 4)
            pid = raw
    listener_owned(mapping(record["forwarder"]), port, _integer(record, "listener_inode"))
    if socket_identity(root / "http/api.sock") != record["api_socket"]:
        raise StartError("IPC_IDENTITY_MISMATCH", 4)
    private_dir(control)
    if dead:
        fd = os.open(control / "control.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
                or info.st_size != 0
            ):
                raise StartError("UNSAFE_IPC_LOCK", 4)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StartError("IPC_OWNERSHIP_UNCERTAIN", 4) from None
            path = control / "control.sock"
            if os.path.lexists(path):
                if socket_identity(path) != record["control_socket"]:
                    raise StartError("IPC_IDENTITY_MISMATCH", 4)
                with socket.socket(socket.AF_UNIX) as peer:
                    peer.settimeout(remaining(runtime.deadline, 0.2))
                    try:
                        peer.connect(str(path))
                    except OSError as exc:
                        if exc.errno != errno.ECONNREFUSED:
                            raise StartError("IPC_OWNERSHIP_UNCERTAIN", 4) from None
                    else:
                        raise StartError("IPC_PEER_STILL_LIVE", 4)
                if socket_identity(path) != record["control_socket"]:
                    raise StartError("IPC_IDENTITY_MISMATCH", 4)
            after = (control / "control.lock").lstat()
            if (after.st_dev, after.st_ino) != (info.st_dev, info.st_ino):
                raise StartError("IPC_IDENTITY_MISMATCH", 4)
        finally:
            os.close(fd)  # Probe only; the restarted supervisor must acquire its own lock.
    elif os.path.lexists(control / "control.lock"):
        private_file(control / "control.lock", limit=0)
    if dead and os.path.lexists(control / "control.cap"):
        capability = private_file(control / "control.cap", limit=64)
        if len(capability) != 64 or any(char not in "0123456789abcdef" for char in capability):
            raise StartError("RECOVERY_METADATA_INVALID", 4)
    development = runtime.development_workspace is not None
    expected = None if development else runtime.files["web/index.html"]
    for directory in (root / "http", None):
        body = http_probe(
            port,
            "/health/ready" if development else "/",
            runtime.deadline,
            directory=directory,
            api_pid=api_process(runtime, ids["api"], root, control, port),
            limit=4096 if development else len(runtime.files["web/index.html"]),
            **({"statuses": (200, 503)} if development else {}),
        )
        # Route ownership is independent of mutable build readiness during recovery.
        if expected is not None and body != expected:
            raise StartError("SERVED_ASSET_MISMATCH", 4)
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("RECOVERY_UNCERTAIN", 4)
    return pid


def _reboot_resources(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    record: dict[str, object],
    *,
    running: frozenset[str] = frozenset(),
) -> int:
    _ready_record(record)
    _check_pgdata(root, record)
    _bound_instance(runtime, root, control, record)
    if os.path.lexists(root / "unreconciled.json"):
        raise StartError("RECOVERY_REQUIRED", 4)
    runtime.attempt = str(record["attempt"])
    port = _integer(record, "port")
    ids = service_ids(runtime, root, control, port)
    if ids != _containers(record):
        raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
    pid = 0
    for role, cid in ids.items():
        state = mapping(runtime.attest(cid, role, root, control, port).get("State"))
        live = role in running
        raw = state.get("Pid")
        if (
            state.get("Running") is not live
            or state.get("Status") != ("running" if live else "exited")
            or type(raw) is not int
            or (raw <= 1 if live else raw != 0)
            or state.get("Paused") is not False
            or state.get("Restarting") is not False
            or state.get("Dead") is not False
            or state.get("Error") != ""
            or type(state.get("ExitCode")) is not int
        ):
            raise StartError("RECOVERY_RESOURCE_STATE_UNVERIFIED", 4)
        if role == "supervisor" and live:
            pid = raw
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("RECOVERY_UNCERTAIN", 4)
    return pid


def _stale_socket(path: Path, deadline: float) -> list[int] | None:
    private_dir(path.parent)
    if not os.path.lexists(path):
        return None
    identity = socket_identity(path)
    if path.lstat().st_nlink != 1:
        raise StartError("UNSAFE_IPC", 4)
    with socket.socket(socket.AF_UNIX) as peer:
        peer.settimeout(remaining(deadline, 0.2))
        try:
            peer.connect(str(path))
        except OSError as exc:
            if exc.errno != errno.ECONNREFUSED:
                raise StartError("IPC_OWNERSHIP_UNCERTAIN", 4) from None
        else:
            raise StartError("IPC_PEER_STILL_LIVE", 4)
    if socket_identity(path) != identity:
        raise StartError("IPC_IDENTITY_MISMATCH", 4)
    return identity


def _reboot_files(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    record: dict[str, object],
    *,
    locks: ExitStack | None = None,
) -> dict[str, object]:
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if not _uuid(boot) or mapping(record["forwarder"])["boot_id"] == boot:
        raise StartError("RECOVERY_BOOT_UNVERIFIED", 4)
    _listener_absent(record)
    preflight_port(_integer(record, "port"))
    result: dict[str, object] = {}
    for directory, stem in ((control, "control"), (root / "http", "api")):
        private_dir(directory)
        path = directory / f"{stem}.lock"
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
                or info.st_size != 0
            ):
                raise StartError("UNSAFE_IPC_LOCK", 4)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StartError("IPC_OWNERSHIP_UNCERTAIN", 4) from None
            identity = _stale_socket(directory / f"{stem}.sock", runtime.deadline)
            if identity is not None and identity != record[f"{stem}_socket"]:
                raise StartError("IPC_IDENTITY_MISMATCH", 4)
            after = path.lstat()
            if (after.st_dev, after.st_ino) != (info.st_dev, info.st_ino):
                raise StartError("IPC_IDENTITY_MISMATCH", 4)
            result[f"{stem}.lock"] = [info.st_dev, info.st_ino]
            result[f"{stem}.sock"] = identity
            if locks is not None:
                locks.callback(os.close, fd)
                fd = -1
        finally:
            if fd >= 0:
                os.close(fd)
    result["model-egress.sock"] = _stale_socket(root / "vault/model-egress.sock", runtime.deadline)
    for path in (control / "control.cap", root / "vault/model-relay.cap", root / "forwarder.log"):
        if not os.path.lexists(path):
            result[path.name] = None
            continue
        before = path.lstat()
        private_file(path, limit=4 * 1024 * 1024 if path.name == "forwarder.log" else 64)
        after = path.lstat()
        identity = [
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ]
        if identity != [
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ]:
            raise StartError("IPC_IDENTITY_MISMATCH", 4)
        result[path.name] = identity
    return result


def reap_forwarder(owner: ForwarderOwnership) -> None:
    """The recovering caller owns its child through Stop completion or failure."""
    try:
        if owner.process is not None:
            if owner.pidfd < 0 and owner.process.poll() is None:
                owner.pidfd = os.pidfd_open(owner.process.pid)
            # Reuse bounded child cleanup even when the operation budget expired.
            with _publish_forwarder():
                stop_forwarder(owner.process, owner.pidfd)
    finally:
        if owner.pidfd >= 0:
            os.close(owner.pidfd)
            owner.pidfd = -1


def recover_barrier(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    record: dict[str, object],
    *,
    forwarder_owner: ForwarderOwnership,
) -> dict[str, object]:
    _ready_record(record)
    if (
        record["format"] != 5
        or not runtime.provider_settings
        or runtime.native
        or runtime.model_test
        or not 1 <= _integer(record, "generation") <= 9223372036854775804
        or not 1 <= _integer(record, "supervisor_epoch") < 9223372036854775807
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    reboot = (
        mapping(record["forwarder"])["boot_id"]
        != Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    )
    files: dict[str, object] = {}
    owner = None
    if reboot:
        _reboot_resources(runtime, root, control, record)
        files = _reboot_files(runtime, root, control, record)
        if os.path.lexists(root / f"recovery-{record['attempt']}"):
            raise StartError("RECOVERY_REQUIRED", 4)
    else:
        _inventory(runtime, root, control, record, dead=True)
        owner = _owner(runtime, record)
    intent: dict[str, object] = {
        "version": 1,
        "original": record,
        "owner": owner,
        "stop_command": str(uuid4()),
        "finalize_command": str(uuid4()),
        **({"files": files} if reboot else {}),
    }
    intent_path = root / f"recovery-{record['attempt']}.json"
    write_record(intent_path, intent)
    if read_record(intent_path) != intent:
        raise StartError("RECOVERY_INTENT_UNVERIFIED", 4)
    journal = root / "startup.json"
    pending = {**record, "phase": "RECOVERING"}
    write_record(journal, pending, replace=True)
    if read_record(journal) != pending:
        raise StartError("RECOVERY_INTENT_UNVERIFIED", 4)
    if reboot:
        _reboot_resources(runtime, root, control, record)
        if (
            _reboot_files(runtime, root, control, record) != files
            or read_record(intent_path) != intent
            or read_record(journal) != pending
        ):
            raise StartError("RECOVERY_AUTHORITY_CHANGED", 4)
        runtime.run("start", _containers(record)["db"], effect=True)
        if runtime.uncertain or not runtime.family_drained:
            raise StartError("RECOVERY_UNCERTAIN", 4)
        runtime.wait_container(_containers(record)["db"], healthy=True)
        _reboot_resources(runtime, root, control, record, running=frozenset({"db"}))
        if database_identity(runtime, _containers(record)["db"]) != (
            record["system_id"],
            record["instance_id"],
        ):
            raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
        owner = _owner(runtime, record)
        with ExitStack() as ipc_locks:
            if (
                _reboot_files(runtime, root, control, record, locks=ipc_locks) != files
                or read_record(intent_path) != intent
                or read_record(journal) != pending
            ):
                raise StartError("RECOVERY_AUTHORITY_CHANGED", 4)
            intent["owner"] = owner
            write_record(intent_path, intent, replace=True)
            archive = root / f"recovery-{record['attempt']}"
            archive.mkdir(mode=0o700)
            _sync_dir(root)
            for source in (
                root / "http/api.sock",
                control / "control.sock",
                root / "vault/model-egress.sock",
                control / "control.cap",
                root / "vault/model-relay.cap",
                root / "forwarder.log",
            ):
                expected = files[source.name]
                if expected is None:
                    if os.path.lexists(source):
                        raise StartError("IPC_IDENTITY_MISMATCH", 4)
                    continue
                info = source.lstat()
                actual = (
                    _stale_socket(source, runtime.deadline)
                    if source.suffix == ".sock"
                    else [
                        info.st_dev,
                        info.st_ino,
                        info.st_size,
                        info.st_mtime_ns,
                        info.st_ctime_ns,
                    ]
                )
                if actual != expected:
                    raise StartError("IPC_IDENTITY_MISMATCH", 4)
                publish_directory(source, archive / source.name)
                moved = (archive / source.name).lstat()
                if (moved.st_dev, moved.st_ino) != (info.st_dev, info.st_ino):
                    raise StartError("IPC_IDENTITY_MISMATCH", 4)
                _sync_dir(source.parent)
                _sync_dir(archive)
            for lock in (control / "control.lock", root / "http/api.lock"):
                info = lock.lstat()
                if [info.st_dev, info.st_ino] != files[lock.name]:
                    raise StartError("IPC_IDENTITY_MISMATCH", 4)
        _reboot_resources(runtime, root, control, record, running=frozenset({"db"}))
    else:
        _inventory(runtime, root, control, record, dead=True)
    if (
        _owner(runtime, record) != owner
        or read_record(intent_path) != intent
        or read_record(journal) != pending
    ):
        raise StartError("RECOVERY_AUTHORITY_CHANGED", 4)
    observed = dict(record)
    if reboot:
        _listener_absent(record)
        _, _, forwarder, inode = launch_forwarder(
            root,
            _integer(record, "port"),
            runtime.deadline,
            ownership=forwarder_owner,
            stop_attempt=str(record["attempt"]),
            model=True,
        )
        observed.update(forwarder=forwarder, listener_inode=inode)
        pending.update(forwarder=forwarder, listener_inode=inode)
        write_record(journal, pending, replace=True)
        if (
            read_record(journal) != pending
            or read_record(intent_path) != intent
            or _owner(runtime, record) != owner
        ):
            raise StartError("RECOVERY_AUTHORITY_CHANGED", 4)
        _reboot_resources(runtime, root, control, record, running=frozenset({"db"}))
    remaining(runtime.deadline)
    runtime.run("start", _containers(record)["supervisor"], effect=True)
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("RECOVERY_UNCERTAIN", 4)
    pid = (
        _reboot_resources(runtime, root, control, record, running=frozenset({"db", "supervisor"}))
        if reboot
        else _inventory(runtime, root, control, record, dead=False)
    )
    while True:
        remaining(runtime.deadline)
        try:
            current = request(control, {"op": "status"}, deadline=runtime.deadline, peer_pid=pid)
            break
        except ControlUnavailable:
            time.sleep(
                min(0.1, remaining(runtime.deadline))
            )  # Read-only readiness, never resend start.
    if (
        current["instance_id"] != record["instance_id"]
        or current["generation"] != _integer(record, "generation") + 1
        or current["supervisor_epoch"] != _integer(record, "supervisor_epoch") + 1
        or current["admission_open"] is not False
        or current["assessment_ready"] is not False
        or current["shutdown_finalized"] is not False
        or current["quiesced_generation"] != current["generation"]
        or _owner(runtime, record, current) == owner
        or read_record(journal) != pending
        or read_record(intent_path) != intent
    ):
        raise StartError("RECOVERY_BARRIER_UNVERIFIED", 4)
    if reboot:
        _reboot_resources(runtime, root, control, record, running=frozenset({"db", "supervisor"}))
        runtime.run("start", _containers(record)["api"], effect=True)
        if runtime.uncertain or not runtime.family_drained:
            raise StartError("RECOVERY_UNCERTAIN", 4)
        while True:
            remaining(runtime.deadline)
            try:
                observed["api_socket"] = socket_identity(root / "http/api.sock")
                _inventory(runtime, root, control, observed, dead=False)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(min(0.1, remaining(runtime.deadline)))
            except StartError as exc:
                if exc.reason != "HTTP_NOT_READY":
                    raise
                time.sleep(min(0.1, remaining(runtime.deadline)))
        if (
            _owner(runtime, record, current) == owner
            or read_record(journal) != pending
            or read_record(intent_path) != intent
        ):
            raise StartError("RECOVERY_BARRIER_UNVERIFIED", 4)
    socket = socket_identity(control / "control.sock")
    stopped = {
        **observed,
        "phase": "STOPPING",
        "generation": current["generation"],
        "supervisor_epoch": current["supervisor_epoch"],
        "control_socket": socket,
        "stop_command": intent["stop_command"],
        "stop_expected": current["generation"],
        "stop_generation": None,
        "finalize_command": intent["finalize_command"],
        "finalized_generation": None,
        "teardown_completed": [],
    }
    _stopping_record(stopped)
    write_record(journal, stopped, replace=True)
    if read_record(journal) != stopped:
        raise StartError("RECOVERY_INTENT_UNVERIFIED", 4)
    return stopped
