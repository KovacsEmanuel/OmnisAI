"""Host-owned instance Stop; no run Stop, Docker socket or assessment runtime."""

import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

from .control import ControlUnavailable, request
from .instance import control_dir, load_instance, private_dir, private_file, state_dir
from .lifecycle import (
    StartError,
    cleanup_startup_ipc,
    lifecycle_lock,
    listener_owned,
    mapping,
    process_identity,
    read_record,
    socket_identity,
    write_record,
)
from .start import (
    READY_FIELDS,
    STOP_FIELDS,
    _check_pgdata,
    _owned_record,
    _pgdata_receipt,
    _ready_record,
    database_identity,
    service_ids,
    verify_running,
)
from .start_runtime import ControlRuntime

STOP_STAGES = ("forwarder", "api", "supervisor", "db", "network", "ipc")


def _integer(record: dict[str, object], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise StartError("RECOVERY_REQUIRED", 4)
    return value


def _containers(record: dict[str, object]) -> dict[str, str]:
    value = record.get("containers")
    if not isinstance(value, dict) or set(value) != {"db", "api", "supervisor"}:
        raise StartError("RECOVERY_REQUIRED", 4)
    if any(not isinstance(cid, str) for cid in value.values()):
        raise StartError("RECOVERY_REQUIRED", 4)
    return value


def _expected_sockets(record: dict[str, object]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for stem, key in (("api", "api_socket"), ("control", "control_socket")):
        value = record.get(key)
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(type(part) is not int or part < 0 for part in value)
        ):
            raise StartError("RECOVERY_REQUIRED", 4)
        result[stem] = value
    return result


def _marker(root: Path, record: dict[str, object], runtime: ControlRuntime) -> None:
    """A durable unreconciled locator blocks all future ordinary Start attempts."""
    payload = {
        "format": 1,
        "project": runtime.receipt.project,
        "attempt": record["attempt"],
        "instance_id": record["instance_id"],
        "docker_id": runtime.receipt.docker_id,
        "release_digest": runtime.digest,
        "containers": _containers(record),
        "reason": "CONTROL_UNAVAILABLE",
    }
    path = root / "unreconciled.json"
    if os.path.lexists(path):
        if read_record(path) != payload:
            raise StartError("RECOVERY_REQUIRED", 4)
    else:
        write_record(path, payload)
    if read_record(path) != payload:
        raise StartError("RECOVERY_REQUIRED", 4)


def _listener_absent(record: dict[str, object]) -> None:
    inode, port = _integer(record, "listener_inode"), _integer(record, "port")
    for name in ("tcp", "tcp6"):
        for row in Path(f"/proc/net/{name}").read_text().splitlines()[1:]:
            fields = row.split()
            if fields[3] == "0A" and (
                fields[9] == str(inode) or int(fields[1].split(":")[1], 16) == port
            ):
                raise StartError("STOP_READBACK_UNCERTAIN", 4)


def _stopping_record(record: dict[str, object]) -> None:
    _pgdata_receipt(record)
    _owned_record(record)
    completed = record.get("teardown_completed")
    finalized = record.get("finalized_generation")
    if (
        set(record) != STOP_FIELDS
        or record.get("phase") not in {"STOPPING", "STOPPED"}
        or record.get("stop_generation") is not None
        and type(record["stop_generation"]) is not int
        or finalized is not None
        and type(finalized) is not int
        or not isinstance(completed, list)
        or completed != list(STOP_STAGES[: len(completed)])
        or finalized is not None
        and finalized != record.get("stop_generation")
        or completed
        and finalized is None
        or record.get("phase") == "STOPPED"
        and (finalized is None or completed != list(STOP_STAGES))
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    for key in ("attempt", "stop_command", "finalize_command"):
        value = record[key]
        if not isinstance(value, str):
            raise StartError("RECOVERY_REQUIRED", 4)
        try:
            if str(UUID(value)) != value:
                raise ValueError()
        except ValueError:
            raise StartError("RECOVERY_REQUIRED", 4) from None
    if _integer(record, "stop_expected") < 0 or (
        _integer(record, "generation") != _integer(record, "stop_expected")
        or record["stop_generation"] is not None
        and record["stop_generation"]
        not in {_integer(record, "stop_expected"), _integer(record, "stop_expected") + 1}
        or _integer(record, "supervisor_epoch") < 1
        or not 1024 <= _integer(record, "port") <= 65535
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    _containers(record)


def _preflight_record(record: dict[str, object]) -> None:
    """Reject unauthoritative journal shapes before locks, control or intents."""
    phase = record.get("phase")
    if phase == "READY":
        _ready_record(record)
    elif phase in {"STOPPING", "STOPPED"}:
        _stopping_record(record)
    elif phase == "FORWARDING":
        _pgdata_receipt(record)
        _owned_record(record)
    else:
        raise StartError("RECOVERY_REQUIRED", 4)


def readback_stopped(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
) -> None:
    """Offline receipt is usable only while its exact owned resources stay absent."""
    if os.path.lexists(root / "unreconciled.json"):
        raise StartError("RECOVERY_REQUIRED", 4)
    _stopping_record(record)
    _check_pgdata(root, record)
    if record["phase"] != "STOPPED" or record["stop_generation"] is None:
        raise StartError("RECOVERY_REQUIRED", 4)
    instance = load_instance(root)
    if (
        record["project"] != runtime.receipt.project
        or record["release_digest"] != runtime.digest
        or record["image_id"] != runtime.receipt.image_id
        or record["docker_id"] != runtime.receipt.docker_id
        or record["docker_host"] != runtime.host
        or record["control_dir"] != str(control)
        or record["instance_id"] != instance.instance_id
        or _integer(record, "port") != int(instance.origin.rsplit(":", 1)[1])
        or _integer(record, "stop_generation")
        not in {_integer(record, "stop_expected"), _integer(record, "stop_expected") + 1}
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    try:
        private_file(root / "db-password", limit=64)  # O_NOFOLLOW, owner/mode/link count.
    except (OSError, ValueError):
        raise StartError("RECOVERY_REQUIRED", 4) from None
    runtime.attempt = str(record["attempt"])
    if runtime.ids() or runtime.network(set()) is not None:
        raise StartError("STOP_READBACK_UNCERTAIN", 4)
    for cid in _containers(record).values():
        if runtime.inspect("container", cid) is not None:
            raise StartError("STOP_READBACK_UNCERTAIN", 4)
    for path in (root / "http/api.sock", control / "control.sock", control / "control.cap"):
        if os.path.lexists(path):
            raise StartError("STOP_READBACK_UNCERTAIN", 4)
    _listener_absent(record)
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("STOP_READBACK_UNCERTAIN", 4)


def _running_for_stop(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
) -> dict[str, object]:
    _stopping_record(record)
    _check_pgdata(root, record)
    instance = load_instance(root)
    port = _integer(record, "port")
    if (
        record["project"] != runtime.receipt.project
        or record["release_digest"] != runtime.digest
        or record["image_id"] != runtime.receipt.image_id
        or record["docker_id"] != runtime.receipt.docker_id
        or record["docker_host"] != runtime.host
        or record["control_dir"] != str(control)
        or record["instance_id"] != instance.instance_id
        or port != int(instance.origin.rsplit(":", 1)[1])
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    runtime.attempt = str(record["attempt"])
    ids = service_ids(runtime, root, control, port)
    if ids != _containers(record):
        raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
    if database_identity(runtime, ids["db"]) != (record["system_id"], instance.instance_id):
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    for role, cid in ids.items():
        if (
            mapping(runtime.attest(cid, role, root, control, port).get("State")).get("Running")
            is not True
        ):
            raise StartError("RECOVERY_REQUIRED", 4)
    listener_owned(mapping(record["forwarder"]), port, _integer(record, "listener_inode"))
    if (
        socket_identity(root / "http/api.sock") != record["api_socket"]
        or socket_identity(control / "control.sock") != record["control_socket"]
    ):
        raise StartError("IPC_IDENTITY_MISMATCH", 4)
    current = request(control, {"op": "status"}, deadline=runtime.deadline)
    if current["instance_id"] != instance.instance_id or current["assessment_ready"] is not False:
        raise StartError("INSTANCE_CONTROL_MISMATCH", 4)
    return current


def _emergency_inventory(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
) -> None:
    """Pin this exact attempt even if its API, supervisor or DB cannot reply."""
    _check_pgdata(root, record)
    if record.get("phase") == "STOPPING":
        _stopping_record(record)
        if record["finalized_generation"] is not None or record["teardown_completed"] != []:
            raise StartError("RECOVERY_REQUIRED", 4)
    elif record.get("phase") == "FORWARDING":
        command = record.get("open_command")
        if (
            set(record) != READY_FIELDS - {"generation", "supervisor_epoch"}
            or type(record.get("format")) is not int
            or record["format"] != 2
            or not isinstance(command, str)
        ):
            raise StartError("RECOVERY_REQUIRED", 4)
        try:
            if str(UUID(command)) != command:
                raise ValueError()
        except ValueError:
            raise StartError("RECOVERY_REQUIRED", 4) from None
        _owned_record(record)
    else:
        _ready_record(record)
    attempt = record["attempt"]
    if not isinstance(attempt, str) or str(UUID(attempt)) != attempt:
        raise StartError("RECOVERY_REQUIRED", 4)
    instance = load_instance(root)
    port = _integer(record, "port")
    if (
        record["project"] != runtime.receipt.project
        or record["release_digest"] != runtime.digest
        or record["image_id"] != runtime.receipt.image_id
        or record["docker_host"] != runtime.host
        or record["docker_id"] != runtime.receipt.docker_id
        or record["control_dir"] != str(control)
        or record["instance_id"] != instance.instance_id
        or port != int(instance.origin.rsplit(":", 1)[1])
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    runtime.attempt = attempt
    _expected_sockets(record)
    ids = _containers(record)
    if set(runtime.ids()) != set(ids.values()):
        raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
    for role, cid in ids.items():
        runtime.attest(cid, role, root, control, port)
    if runtime.network(set(ids.values())) is None:
        raise StartError("NETWORK_IDENTITY_MISMATCH", 4)


def _emergency_drain(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
) -> None:
    """Remove only pinned P0 effect paths; never publish a DB STOPPED receipt."""
    _check_pgdata(root, record)
    ids = _containers(record)
    port = _integer(record, "port")
    identity = mapping(record["forwarder"])
    pid = identity.get("pid")
    if type(pid) is not int:
        raise StartError("FORWARDER_IDENTITY_INVALID", 4)
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        _listener_absent(record)
    else:
        try:
            if process_identity(pid) != identity:
                raise StartError("FORWARDER_IDENTITY_MISMATCH", 4)
            listener_owned(identity, port, _integer(record, "listener_inode"))
            signal.pidfd_send_signal(fd, signal.SIGTERM)
            if not select.select([fd], [], [], 25)[0]:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
                raise StartError("FORWARDER_STOP_UNCERTAIN", 4)
        finally:
            os.close(fd)
    for role in ("api", "supervisor", "db"):
        cid = ids[role]
        if role == "db" and (runtime.uncertain or not runtime.family_drained):
            raise StartError("DATABASE_RETAINED_UNCERTAIN_WRITERS", 4)
        before = runtime.attest(cid, role, root, control, port)
        if mapping(before.get("State")).get("Running") is True:
            runtime.run("stop", "--time", "15", cid, cap=25, effect=True)
        after = runtime.inspect("container", cid)
        if after is None or mapping(after.get("State")).get("Running") is not False:
            raise StartError("CONTAINER_STOP_UNCERTAIN", 4)
        runtime.attest(cid, role, root, control, port)
        runtime.run("container", "rm", cid, effect=True)
        if runtime.inspect("container", cid) is not None:
            raise StartError("CONTAINER_REMOVAL_UNCERTAIN", 4)
    if runtime.ids():
        raise StartError("CONTAINERS_REMAIN", 4)
    network = runtime.network(set())
    if network is not None:
        runtime.run("network", "rm", network, effect=True)
    if runtime.network(set()) is not None:
        raise StartError("NETWORK_REMAINS", 4)
    if (
        runtime.uncertain
        or not runtime.family_drained
        or cleanup_startup_ipc(root, control, expected=_expected_sockets(record))
    ):
        raise StartError("STOP_CLEANUP_UNCERTAIN", 4)
    for path in (root / "http/api.sock", control / "control.sock", control / "control.cap"):
        if os.path.lexists(path):
            raise StartError("STOP_READBACK_UNCERTAIN", 4)
    _listener_absent(record)
    if not (root / "postgres").is_dir():
        raise StartError("DATA_READBACK_UNCERTAIN", 4)


def _emergency_stop(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
) -> None:
    if record.get("phase") == "READY":
        _ready_record(record)
    elif record.get("phase") == "STOPPING":
        _stopping_record(record)
    elif record.get("phase") == "FORWARDING":
        _pgdata_receipt(record)
        _owned_record(record)
    else:
        raise StartError("RECOVERY_REQUIRED", 4)
    _check_pgdata(root, record)
    # The marker path can be unwritable independently of the private journal.
    # Persist before inventory: an outage there must not leave READY reusable.
    journaled = False
    try:
        pending = {**record, "phase": "UNCERTAIN"}
        write_record(root / "startup.json", pending, replace=True)
        journaled = read_record(root / "startup.json") == pending
    except (OSError, ValueError):
        pass
    marked = False
    try:
        _marker(root, record, runtime)
        marked = True
    except (OSError, ValueError):
        pass
    if not (journaled or marked):
        # Neither durable channel can block a later Start. No effect may be
        # credited as clean; external recovery is required before retry.
        raise StartError("UNRECONCILED_INTENT_UNAVAILABLE", 4)
    _emergency_inventory(runtime, root, control, record)
    _emergency_drain(runtime, root, control, record)
    raise StartError("RECOVERY_REQUIRED" if marked else "UNRECONCILED_MARKER_UNAVAILABLE", 4)


def _complete_stage(path: Path, record: dict[str, object], stage: str) -> None:
    completed = record.get("teardown_completed")
    if not isinstance(completed, list) or len(completed) >= len(STOP_STAGES):
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    if STOP_STAGES[len(completed)] != stage:
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    record["teardown_completed"] = [*completed, stage]
    write_record(path, record, replace=True)
    if read_record(path) != record:
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)


def _finalized_db_readback(
    runtime: ControlRuntime, record: dict[str, object], db: str, instance_id: str
) -> None:
    generation = _integer(record, "finalized_generation")
    system_id, identity = database_identity(runtime, db)
    if (system_id, identity) != (record["system_id"], instance_id):
        raise StartError("DATABASE_IDENTITY_MISMATCH", 4)
    # UUIDs were canonicalized by _stopping_record; integers are exact at this
    # boundary. The host has read-only DB authority here, never a new writer.
    finalized = record["finalize_command"]
    query = (
        "SELECT generation::text || '|' || "
        "CASE WHEN admission_open THEN 't' ELSE 'f' END || '|' || "
        "shutdown_command_id::text || '|' || quiesced_generation::text || '|' || "
        "(SELECT count(*)::text FROM instance_command WHERE "
        f"command_id = '{finalized}'::uuid AND kind = 'FINALIZE' "
        f"AND expected_generation = {generation} AND result_generation = {generation} "
        f"AND owner_epoch = {_integer(record, 'supervisor_epoch')}) "
        "FROM instance_control WHERE id = 1"
    )
    expected = [str(generation), "f", record["stop_command"], str(generation), "1"]
    if runtime.psql(db, query).split("|") != expected:
        raise StartError("FINALIZE_READBACK_UNVERIFIED", 4)


def _resume_owned(
    runtime: ControlRuntime, root: Path, control: Path, path: Path, record: dict[str, object]
) -> None:
    """Resume only fsynced completed stages; an unacknowledged effect is uncertain."""
    _stopping_record(record)
    _check_pgdata(root, record)
    if record["finalized_generation"] is None or record["phase"] != "STOPPING":
        raise StartError("FINALIZE_UNVERIFIED", 4)
    instance = load_instance(root)
    port = _integer(record, "port")
    if (
        record["project"] != runtime.receipt.project
        or record["release_digest"] != runtime.digest
        or record["image_id"] != runtime.receipt.image_id
        or record["docker_id"] != runtime.receipt.docker_id
        or record["docker_host"] != runtime.host
        or record["control_dir"] != str(control)
        or record["instance_id"] != instance.instance_id
        or port != int(instance.origin.rsplit(":", 1)[1])
        or read_record(path) != record
    ):
        raise StartError("RECOVERY_REQUIRED", 4)
    runtime.attempt = str(record["attempt"])
    ids = _containers(record)
    present = set(runtime.ids())
    if present - set(ids.values()):
        raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
    completed = record["teardown_completed"]
    if not isinstance(completed, list):
        raise StartError("RECOVERY_REQUIRED", 4)
    for role in ("api", "supervisor", "db"):
        cid = ids[role]
        item = runtime.inspect("container", cid)
        if role in completed:
            if cid in present or item is not None:
                raise StartError("RESOURCE_IDENTITY_MISMATCH", 4)
        elif cid not in present or item is None:
            raise StartError("STOP_EFFECT_UNCERTAIN", 4)
        else:
            runtime.attest(cid, role, root, control, port)
    network = runtime.network(present)
    if network is None and "network" not in completed:
        raise StartError("NETWORK_READBACK_UNCERTAIN", 4)
    db = ids["db"]
    if db in present:
        state = mapping(runtime.attest(db, "db", root, control, port).get("State"))
        if state.get("Running") is not True:
            raise StartError("STOP_EFFECT_UNCERTAIN", 4)
        _finalized_db_readback(runtime, record, db, instance.instance_id)

    identity = mapping(record["forwarder"])
    pid = identity.get("pid")
    if type(pid) is not int:
        raise StartError("FORWARDER_IDENTITY_INVALID", 4)
    if "forwarder" in completed:
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            pass
        else:
            try:
                try:
                    same = process_identity(pid) == identity
                except (OSError, ValueError):
                    same = False
                if same:
                    raise StartError("FORWARDER_STILL_LIVE", 4)
            finally:
                os.close(fd)
        _listener_absent(record)
    else:
        fd = os.pidfd_open(pid)
        try:
            if process_identity(pid) != identity:
                raise StartError("FORWARDER_IDENTITY_MISMATCH", 4)
            listener_owned(identity, port, _integer(record, "listener_inode"))
            signal.pidfd_send_signal(fd, signal.SIGTERM)
            if not select.select([fd], [], [], 25)[0]:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
                raise StartError("FORWARDER_STOP_UNCERTAIN", 4)
        finally:
            os.close(fd)
        _listener_absent(record)
        _complete_stage(path, record, "forwarder")

    for role in ("api", "supervisor", "db"):
        if role in completed:
            continue
        cid = ids[role]
        if role == "db" and (runtime.uncertain or not runtime.family_drained):
            raise StartError("DATABASE_RETAINED_UNCERTAIN_WRITERS", 4)
        item = runtime.attest(cid, role, root, control, port)
        if mapping(item.get("State")).get("Running") is not True:
            raise StartError("STOP_EFFECT_UNCERTAIN", 4)
        runtime.run("stop", "--time", "15", cid, cap=25, effect=True)
        after = runtime.inspect("container", cid)
        if after is None or mapping(after.get("State")).get("Running") is not False:
            raise StartError("CONTAINER_STOP_UNCERTAIN", 4)
        runtime.attest(cid, role, root, control, port)
        runtime.run("container", "rm", cid, effect=True)
        if runtime.inspect("container", cid) is not None or cid in runtime.ids():
            raise StartError("CONTAINER_REMOVAL_UNCERTAIN", 4)
        _complete_stage(path, record, role)

    if runtime.ids():
        raise StartError("CONTAINERS_REMAIN", 4)
    if "network" not in completed:
        network = runtime.network(set())
        if network is None:
            raise StartError("NETWORK_READBACK_UNCERTAIN", 4)
        runtime.run("network", "rm", network, effect=True)
        if runtime.network(set()) is not None:
            raise StartError("NETWORK_REMAINS", 4)
        _complete_stage(path, record, "network")
    elif runtime.network(set()) is not None:
        raise StartError("NETWORK_REMAINS", 4)

    if runtime.uncertain or not runtime.family_drained:
        raise StartError("STOP_CLEANUP_UNCERTAIN", 4)
    if "ipc" not in completed:
        if cleanup_startup_ipc(root, control, expected=_expected_sockets(record)):
            raise StartError("STOP_CLEANUP_UNCERTAIN", 4)
        _complete_stage(path, record, "ipc")
    for candidate in (root / "http/api.sock", control / "control.sock", control / "control.cap"):
        if os.path.lexists(candidate):
            raise StartError("STOP_READBACK_UNCERTAIN", 4)
    _listener_absent(record)


def _publish_stopped(
    runtime: ControlRuntime, root: Path, control: Path, path: Path, record: dict[str, object]
) -> None:
    _check_pgdata(root, record)
    record["phase"] = "STOPPED"
    write_record(path, record, replace=True)
    if read_record(path) != record:
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    readback_stopped(runtime, root, control, record)


def stop_instance() -> dict[str, object]:
    root = state_dir()
    # A legacy receipt has no original inode: refuse before even creating a lock.
    if os.path.lexists(root / "startup.json"):
        preflight = read_record(root / "startup.json")
        _preflight_record(preflight)
        _check_pgdata(root, preflight)
    data = os.environ.get("XDG_DATA_HOME")
    data_home = Path(data) if data else Path.home() / ".local/share"
    runtime = ControlRuntime(data_home, time.monotonic() + 180)
    control = control_dir(root)
    private_dir(root)
    deadline = runtime.deadline
    with lifecycle_lock(data_home / "omnis", deadline), lifecycle_lock(root, deadline):
        path = root / "startup.json"
        record = read_record(path)
        _preflight_record(record)
        _check_pgdata(root, record)
        if os.path.lexists(root / "unreconciled.json"):
            raise StartError("RECOVERY_REQUIRED", 4)
        if record.get("phase") == "STOPPED":
            readback_stopped(runtime, root, control, record)
        elif record.get("phase") == "STOPPING" and record.get("finalized_generation") is not None:
            try:
                _resume_owned(runtime, root, control, path, record)
                _publish_stopped(runtime, root, control, path, record)
            except (OSError, ValueError, ControlUnavailable, subprocess.SubprocessError):
                raise StartError("STOP_UNCERTAIN", 4) from None
        else:
            if record.get("phase") == "READY":
                try:
                    verify_running(runtime, root, control, record, _integer(record, "port"))
                    current = request(control, {"op": "status"}, deadline=deadline)
                except (OSError, ValueError, ControlUnavailable, subprocess.SubprocessError):
                    _emergency_stop(runtime, root, control, record)
                    raise StartError("RECOVERY_REQUIRED", 4) from None
                if (
                    current["instance_id"] != record["instance_id"]
                    or current["generation"] != record["generation"]
                    or current["supervisor_epoch"] != record["supervisor_epoch"]
                    or current["admission_open"] is not True
                ):
                    raise StartError("RECOVERY_REQUIRED", 4)
                record.update(
                    phase="STOPPING",
                    stop_command=str(uuid4()),
                    stop_expected=current["generation"],
                    stop_generation=None,
                    finalize_command=str(uuid4()),
                    finalized_generation=None,
                    teardown_completed=[],
                )
                write_record(path, record, replace=True)
            elif record.get("phase") == "FORWARDING":
                # OPEN may have committed even if the launcher died before READY.
                # This is never a normal STOPPED DB receipt; fence it locally and
                # eliminate only the exact attested effect paths.
                _emergency_stop(runtime, root, control, record)
            elif record.get("phase") != "STOPPING":
                raise StartError("RECOVERY_REQUIRED", 4)
            try:
                current = _running_for_stop(runtime, root, control, record)
                expected = _integer(record, "stop_expected")
                if current["generation"] not in {expected, expected + 1}:
                    raise StartError("RECOVERY_REQUIRED", 4)
                closed = request(
                    control,
                    {
                        "op": "shutdown",
                        "instance_id": record["instance_id"],
                        "command_id": record["stop_command"],
                        "expected_generation": expected,
                    },
                    deadline=deadline,
                )
                if (
                    closed["shutdown_command_id"] != record["stop_command"]
                    or closed["admission_open"] is not False
                    or closed["supervisor_epoch"] != current["supervisor_epoch"]
                ):
                    raise StartError("STOP_BARRIER_UNVERIFIED", 4)
                record["stop_generation"] = closed["generation"]
                write_record(path, record, replace=True)
                until = min(deadline, time.monotonic() + 15)
                while time.monotonic() < until:
                    current = request(control, {"op": "status"}, deadline=until)
                    if (
                        current["instance_id"] != record["instance_id"]
                        or current["generation"] != closed["generation"]
                        or current["shutdown_command_id"] != record["stop_command"]
                        or current["supervisor_epoch"] != closed["supervisor_epoch"]
                    ):
                        raise StartError("STOP_CONTROL_CHANGED", 4)
                    if current["quiesced_generation"] == closed["generation"]:
                        break
                    time.sleep(0.1)
                else:
                    raise StartError("QUIESCENCE_UNVERIFIED", 4)
                finalized = request(
                    control,
                    {
                        "op": "finalize",
                        "instance_id": record["instance_id"],
                        "command_id": record["finalize_command"],
                        "expected_generation": closed["generation"],
                    },
                    deadline=deadline,
                )
                if (
                    finalized["generation"] != closed["generation"]
                    or finalized["shutdown_finalized"] is not True
                    or finalized["quiesced_generation"] != closed["generation"]
                    or finalized["supervisor_epoch"] != closed["supervisor_epoch"]
                ):
                    raise StartError("FINALIZE_UNVERIFIED", 4)
                record["finalized_generation"] = closed["generation"]
                write_record(path, record, replace=True)
                if read_record(path) != record:
                    raise StartError("FINALIZE_RECEIPT_UNVERIFIED", 4)
                _resume_owned(runtime, root, control, path, record)
                _publish_stopped(runtime, root, control, path, record)
            except ControlUnavailable:
                if record["finalized_generation"] is None and record["teardown_completed"] == []:
                    _emergency_stop(runtime, root, control, record)
                raise StartError("STOP_UNCERTAIN", 4) from None
            except StartError as exc:
                if (
                    exc.reason == "LOCAL_SERVICE_COMMAND_FAILED"
                    and record["finalized_generation"] is None
                    and record["teardown_completed"] == []
                ):
                    _emergency_stop(runtime, root, control, record)
                raise StartError("STOP_UNCERTAIN", 4) from None
            except (OSError, ValueError, subprocess.SubprocessError):
                raise StartError("STOP_UNCERTAIN", 4) from None
        instance = load_instance(root)
        return {
            "state": "STOPPED",
            "instance_id": instance.instance_id,
            "origin": instance.origin,
            "generation": record["stop_generation"],
            "admission_open": False,
            "dashboard_ready": False,
            "assessment_ready": False,
            "browser_opened": False,
            "reason": None,
        }


def stop(*, as_json: bool) -> int:
    try:
        result = stop_instance()
        code = 0
    except (OSError, ValueError, ControlUnavailable, subprocess.SubprocessError) as exc:
        code = exc.code if isinstance(exc, StartError) else 4
        result = {
            "state": "REFUSED" if code == 2 else "UNCERTAIN",
            "reason": exc.reason if isinstance(exc, StartError) else "STOP_UNCERTAIN",
            "dashboard_ready": False,
            "assessment_ready": False,
            "browser_opened": False,
        }
    if as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Omnis: {result['state']} ({result.get('reason') or 'stopped'})")
        if code:
            print("Verificați starea privată; fără retry distructiv.", file=sys.stderr)
    return code
