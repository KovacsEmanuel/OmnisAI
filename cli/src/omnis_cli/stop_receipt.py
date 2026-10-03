"""Durable, separate Stop receipts. Never writes startup.json or issues a grant."""

import hashlib
import json
import re
from pathlib import Path
from uuid import UUID

from .lifecycle import StartError, mapping, read_record, write_record

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
    try:
        issuer = uuid(grant.get("owner_uuid"))
    except ValueError:
        raise StartError("STOP_GRANT_INVALID", 4) from None
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
        "owner_uuid": issuer,
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


def validate_inventory(inventory: dict[str, object], record: dict[str, object]) -> None:
    if set(inventory) != {
        "version",
        "release",
        "project",
        "attempt",
        "pgdata",
        "system_id",
        "containers",
        "network",
        "forwarder",
        "ipc",
    }:
        raise StartError("STOP_INVENTORY_INVALID", 4)
    for key, expected in (
        ("version", 1),
        ("release", record["release_digest"]),
        ("project", record["project"]),
        ("attempt", record["attempt"]),
        ("pgdata", record["pgdata_identity"]),
        ("system_id", record["system_id"]),
    ):
        if encoded(inventory[key]) != encoded(expected):
            raise StartError("STOP_INVENTORY_INVALID", 4)

    def digest(value: object) -> bool:
        return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None

    containers = inventory["containers"]
    ids = mapping(record["containers"])
    if type(containers) is not list or len(containers) != 3:
        raise StartError("STOP_INVENTORY_INVALID", 4)
    for role, row in zip(("api", "supervisor", "db"), containers, strict=True):
        if (
            type(row) is not dict
            or set(row) != {"role", "id", "image", "config", "run"}
            or row["role"] != role
            or row["id"] != ids[role]
            or type(row["image"]) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", row["image"]) is None
            or role != "db"
            and row["image"] != record["image_id"]
            or not digest(row["config"])
            or not digest(row["run"])
        ):
            raise StartError("STOP_INVENTORY_INVALID", 4)
    network = inventory["network"]
    if (
        type(network) is not dict
        or set(network) != {"id", "config"}
        or not all(digest(v) for v in network.values())
    ):
        raise StartError("STOP_INVENTORY_INVALID", 4)
    process = mapping(record["forwarder"])
    expected_forwarder = {
        **{key: process[key] for key in ("pid", "start_ticks", "boot_id")},
        "identity": fingerprint(process),
        "listener": record["listener_inode"],
        "port": record["port"],
    }
    if encoded(inventory["forwarder"]) != encoded(expected_forwarder):
        raise StartError("STOP_INVENTORY_INVALID", 4)
    ipc = inventory["ipc"]
    if type(ipc) is not dict or set(ipc) != {
        "api",
        "control",
        "api_lock",
        "control_lock",
        "cap",
        "cap_digest",
    }:
        raise StartError("STOP_INVENTORY_INVALID", 4)
    for key in ("api", "control", "api_lock", "control_lock", "cap"):
        pair = ipc[key]
        if (
            type(pair) is not list
            or len(pair) != 2
            or any(type(v) is not int or v < 0 for v in pair)
            or pair[1] == 0
        ):
            raise StartError("STOP_INVENTORY_INVALID", 4)
    if (
        ipc["api"] != record["api_socket"]
        or ipc["control"] != record["control_socket"]
        or not digest(ipc["cap_digest"])
        or len(encoded(inventory)) > 2900
    ):
        raise StartError("STOP_INVENTORY_INVALID", 4)


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
    for key in ("owner", "launcher"):
        owner = value[key]
        if type(owner) is not dict or set(owner) != {"pid", "start_ticks", "boot_id"}:
            raise StartError("STOP_RECEIPT_UNVERIFIED", 4)
        if (
            type(owner["pid"]) is not int
            or owner["pid"] <= 1
            or type(owner["start_ticks"]) is not str
            or not owner["start_ticks"].isdecimal()
        ):
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
