"""One-shot T1 owner-loss recovery to Stop, never OPEN or uncertain-effect retry."""

import errno
import fcntl
import json
import os
import socket
import stat
import time
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
from .start import (
    _bound_instance,
    _check_pgdata,
    _ready_record,
    api_process,
    database_identity,
    service_ids,
)
from .start_runtime import ControlRuntime
from .stop import _containers, _integer, _stopping_record


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
    expected = runtime.files["web/index.html"]
    for directory in (root / "http", None):
        if (
            http_probe(
                port,
                "/",
                runtime.deadline,
                directory=directory,
                api_pid=api_process(runtime, ids["api"], root, control, port),
                limit=len(expected),
            )
            != expected
        ):
            raise StartError("SERVED_ASSET_MISMATCH", 4)
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("RECOVERY_UNCERTAIN", 4)
    return pid


def recover_barrier(
    runtime: ControlRuntime, root: Path, control: Path, record: dict[str, object]
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
    _inventory(runtime, root, control, record, dead=True)
    owner = _owner(runtime, record)
    intent = {
        "version": 1,
        "original": record,
        "owner": owner,
        "stop_command": str(uuid4()),
        "finalize_command": str(uuid4()),
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
    _inventory(runtime, root, control, record, dead=True)
    if (
        _owner(runtime, record) != owner
        or read_record(intent_path) != intent
        or read_record(journal) != pending
    ):
        raise StartError("RECOVERY_AUTHORITY_CHANGED", 4)
    remaining(runtime.deadline)
    runtime.run("start", _containers(record)["supervisor"], effect=True)
    if runtime.uncertain or not runtime.family_drained:
        raise StartError("RECOVERY_UNCERTAIN", 4)
    pid = _inventory(runtime, root, control, record, dead=False)
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
    socket = socket_identity(control / "control.sock")
    stopped = {
        **record,
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
