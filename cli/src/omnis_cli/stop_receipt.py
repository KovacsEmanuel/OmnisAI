"""Durable, separate Stop receipts. Never writes startup.json or issues a grant."""

import hashlib
import json
import re
from pathlib import Path
from uuid import UUID

from .lifecycle import StartError, read_record, write_record

STAGES = (
    "forwarder",
    "api.stop",
    "api.rm",
    "supervisor.stop",
    "supervisor.rm",
    "db.stop",
    "db.rm",
    "network.rm",
    "ipc",
)


def discrete(value: object, depth: int = 0) -> None:
    if depth > 12:
        raise StartError("STOP_RECORD_INVALID", 4)
    if type(value) in {str, int, bool, type(None)}:
        return
    if type(value) is list:
        for item in value:
            discrete(item, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            discrete(item, depth + 1)
        return
    raise StartError("STOP_RECORD_INVALID", 4)


def encoded(value: object) -> bytes:
    discrete(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def uuid(value: object) -> str:
    if type(value) is not str or str(UUID(value)) != value:
        raise StartError("STOP_RECORD_INVALID", 4)
    return value


def validate_grant(
    grant: dict[str, object], record: dict[str, object], inventory: dict[str, object]
) -> None:
    raw = encoded(grant)
    for key in ("stop_command", "finalize_command", "instance_id"):
        uuid(record.get(key))
    for key in ("stop_generation", "finalized_generation", "stop_expected", "supervisor_epoch"):
        if type(record.get(key)) is not int:
            raise StartError("STOP_GRANT_INVALID", 4)
    expected = {
        "version": 1,
        "state": "STOP_PENDING",
        "instance_id": record["instance_id"],
        "command_id": record["stop_command"],
        "finalize_command_id": record["finalize_command"],
        "generation": record["stop_generation"],
        "owner_epoch": record["supervisor_epoch"],
        "daemon_id": record["docker_id"],
        "inventory": inventory,
    }
    if (
        raw != encoded(expected)
        or len(raw) > 3600
        or record["stop_generation"] != record["finalized_generation"]
        or int(str(record["stop_generation"])) != int(str(record["stop_expected"])) + 1
        or int(str(record["supervisor_epoch"])) < 1
    ):
        raise StartError("STOP_GRANT_INVALID", 4)


def receipt_path(root: Path, record: dict[str, object]) -> Path:
    return root / f"stop-{uuid(record.get('stop_command'))}.json"


def persist(path: Path, receipt: dict[str, object], *, replace: bool = False) -> None:
    encoded(receipt)
    write_record(path, receipt, replace=replace)
    if encoded(read_record(path)) != encoded(receipt):
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)


def completed_receipt(path: Path, grant: dict[str, object]) -> dict[str, object]:
    value = read_record(path)
    if (
        set(value) != {"version", "grant", "owner", "launcher", "state", "pending", "completed"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or encoded(value["grant"]) != encoded(grant)
        or value["state"] != "COMPLETED"
        or value["pending"] is not None
    ):
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    owner = value["owner"]
    if type(owner) is not dict or set(owner) != {"pid", "start_ticks", "boot_id"}:
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    if type(owner["pid"]) is not int or owner["pid"] <= 1 or type(owner["start_ticks"]) is not str:
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    uuid(owner["boot_id"])
    steps = value["completed"]
    if type(steps) is not list or len(steps) != len(STAGES):
        raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    for stage, entry in zip(STAGES, steps, strict=True):
        expected_ack: object = 204 if stage not in {"forwarder", "ipc"} else "DRAINED"
        if (
            type(entry) is not dict
            or set(entry) != {"stage", "ack", "proof"}
            or entry["stage"] != stage
            or encoded(entry["ack"]) != encoded(expected_ack)
            or type(entry["proof"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", entry["proof"]) is None
        ):
            raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
    return value
