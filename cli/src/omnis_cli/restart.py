"""DB-only reconciliation for a new explicit Start. No retry/rebind or SQL authority."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from uuid import uuid4

from .instance import private_dir, unique_pairs
from .lifecycle import StartError, mapping, read_record, write_record
from .release import _put, _sync_dir
from .start_runtime import ControlRuntime
from .stop_receipt import encoded, receipt_path, uuid


def _bytes(path: Path) -> bytes:
    """Read exact private bytes: text-mode universal newlines would change the hash."""
    private_dir(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise StartError("RESTART_RECEIPT_INVALID", 4)
        raw = source.read(16385)
    if len(raw) > 16384:
        raise StartError("RESTART_RECEIPT_INVALID", 4)
    return raw


def _persist(path: Path, intent: dict[str, object], *, replace: bool = False) -> None:
    write_record(path, intent, replace=replace)
    if encoded(read_record(path)) != encoded(intent):
        raise StartError("RESTART_RECEIPT_UNVERIFIED", 4)


def prepare_restart(
    runtime: ControlRuntime, root: Path, control: Path, stopped: dict[str, object], attempt: str
) -> dict[str, object]:
    from .stop_owner import verify_stop_completion

    command = uuid(stopped.get("stop_command"))
    uuid(attempt)
    path = root / f"restart-{command}.json"
    if os.path.lexists(path):
        raise StartError("RESTART_RECONCILIATION_REQUIRED", 4)
    raw = _bytes(root / "startup.json")
    completion = _bytes(receipt_path(root, stopped))
    verify_stop_completion(runtime, root, control, stopped)
    if (
        encoded(json.loads(raw, object_pairs_hook=unique_pairs)) != encoded(stopped)
        or stopped.get("phase") != "STOPPED"
        or _bytes(receipt_path(root, stopped)) != completion
        or _bytes(root / "startup.json") != raw
    ):
        raise StartError("RESTART_RECEIPT_CHANGED", 4)
    owner = mapping(json.loads(completion, object_pairs_hook=unique_pairs))
    if owner.get("state") != "COMPLETED":
        raise StartError("RESTART_RECEIPT_INVALID", 4)
    saved = root / f"stopped-{command}.json"
    if not os.path.lexists(saved):
        _put(saved, raw)
        _sync_dir(root)
    if _bytes(saved) != raw:
        raise StartError("RESTART_RECEIPT_CHANGED", 4)
    payload = {
        "version": 1,
        "reconciliation_id": str(uuid4()),
        "system_identifier": stopped["system_id"],
        "grant": mapping(owner.get("grant")),
        "completion_sha256": hashlib.sha256(completion).hexdigest(),
    }
    if len(encoded(payload)) + 1 > 16384:
        raise StartError("RESTART_RECEIPT_INVALID", 4)
    intent: dict[str, object] = {
        "version": 1,
        "state": "PREPARED",
        "old_stop_command": command,
        "old_attempt": stopped["attempt"],
        "stopped_sha256": hashlib.sha256(raw).hexdigest(),
        "new_attempt": attempt,
        "request": payload,
        "network": None,
        "job": None,
        "ack": None,
    }
    _persist(path, intent)
    return intent


def reconcile_database(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    record: dict[str, object],
    intent: dict[str, object],
    env: dict[str, str],
) -> None:
    """One admitted job; any lost outcome preserves intent/DB and requires recovery."""
    command = uuid(intent.get("old_stop_command"))
    path = root / f"restart-{command}.json"
    payload = mapping(intent.get("request"))
    if (
        intent.get("state") != "PREPARED"
        or intent.get("new_attempt") != record["attempt"]
        or runtime.attempt != record["attempt"]
        or payload.get("system_identifier") != record["system_id"]
        or encoded(read_record(path)) != encoded(intent)
        or hashlib.sha256(_bytes(root / f"stopped-{command}.json")).hexdigest()
        != intent.get("stopped_sha256")
        or hashlib.sha256(_bytes(root / f"stop-{command}.json")).hexdigest()
        != payload.get("completion_sha256")
        or runtime.uncertain
        or not runtime.family_drained
    ):
        raise StartError("RESTART_RECEIPT_CHANGED", 4)
    ids = mapping(record["containers"])
    if set(ids) != {"db"} or set(runtime.ids()) != {ids["db"]}:
        raise StartError("RECONCILIATION_RESOURCE_MISMATCH", 4)
    network = runtime.network({str(ids["db"])})
    if network is None:
        raise StartError("RECONCILIATION_RESOURCE_MISMATCH", 4)
    intent.update(state="JOB_PENDING", network=network)
    _persist(path, intent, replace=True)  # A crash from here cannot launch another job.
    job = runtime.run(
        "create",
        "--name",
        f"{runtime.receipt.project}-reconcile",
        "--label",
        f"com.docker.compose.project={runtime.receipt.project}",
        "--label",
        "com.docker.compose.service=reconcile",
        "--label",
        f"org.omnis.start-attempt={runtime.attempt}",
        "--network",
        f"{runtime.receipt.project}_control",
        "--pull",
        "never",
        "--platform",
        "linux/amd64",
        "--restart",
        "no",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--interactive",
        "--attach",
        "stdin",
        "--attach",
        "stdout",
        "--attach",
        "stderr",
        "--env",
        "OMNIS_DATABASE_URL",
        "--env",
        "OMNIS_EXPECTED_SYSTEM_ID",
        runtime.receipt.image_id,
        "python",
        "-I",
        "-m",
        "omnis.stop_reconcile",
        env={
            "OMNIS_DATABASE_URL": env["OMNIS_DATABASE_URL"],
            "OMNIS_EXPECTED_SYSTEM_ID": str(payload["system_identifier"]),
        },
        effect=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{64}", job) is None:
        raise StartError("RECONCILIATION_RESOURCE_MISMATCH", 4)
    intent["job"] = job
    _persist(path, intent, replace=True)
    before = runtime.attest(job, "reconcile", root, control, int(str(record["port"])))
    if mapping(before.get("State")).get("Status") != "created":
        raise StartError("RECONCILIATION_RESOURCE_MISMATCH", 4)
    expected_ids = {str(ids["db"]), job}
    if set(runtime.ids()) != expected_ids or runtime.network(expected_ids) != network:
        raise StartError("RECONCILIATION_RESOURCE_MISMATCH", 4)
    result = runtime.run(
        "start",
        "--attach",
        "--interactive",
        job,
        stdin=encoded(payload) + b"\n",
        cap=25,
        effect=True,
    )
    after = runtime.attest(job, "reconcile", root, control, int(str(record["port"])))
    state = mapping(after.get("State"))
    expected_state = {
        "Status": "exited",
        "Running": False,
        "Pid": 0,
        "ExitCode": 0,
        "OOMKilled": False,
        "Dead": False,
        "Restarting": False,
        "Paused": False,
    }
    if (
        any(encoded(state.get(key)) != encoded(value) for key, value in expected_state.items())
        or result.returncode != 0
        or result.stderr != ""
        or len(result.stdout.encode()) > 16384
        or len(result.stdout.splitlines()) != 1
        or not result.stdout.endswith("\n")
        or runtime.uncertain
        or not runtime.family_drained
        or set(runtime.ids()) != expected_ids
        or runtime.network(expected_ids) != network
    ):
        raise StartError("RECONCILIATION_UNCERTAIN", 4)
    reply = mapping(json.loads(result.stdout, object_pairs_hook=unique_pairs))
    expected = {"ok": True, "correlation_id": payload["reconciliation_id"], "receipt": payload}
    if encoded(reply) != encoded(expected):
        raise StartError("RECONCILIATION_ACK_INVALID", 4)
    runtime.run("container", "rm", job, effect=True)
    if (
        runtime.inspect("container", job) is not None
        or set(runtime.ids()) != {ids["db"]}
        or runtime.network({str(ids["db"])}) != network
        or runtime.uncertain
        or not runtime.family_drained
    ):
        raise StartError("RECONCILIATION_CLEANUP_UNCERTAIN", 4)
    intent.update(state="ACKED", ack=reply)
    _persist(path, intent, replace=True)  # Mandatory before supervisor create/acquire/OPEN.
