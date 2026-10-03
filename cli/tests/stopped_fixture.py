"""Synthetic COMPLETED authority for receipt-consumer tests, not host completion proof.

The production receipt/grant/inventory/IPC validators all run. Only Engine readback
is substituted; the Stop-owner process suite separately produces genuine receipts.
"""

import contextlib
import os
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.lifecycle import write_record
from omnis_cli.stop_receipt import STAGES, fingerprint, receipt_path


@contextlib.contextmanager
def completed_fixture(root, control, record, runtime):
    if not os.path.lexists(root / "startup.json"):
        write_record(root / "startup.json", record)
    pins = {}
    for directory, stem in ((root / "http", "api"), (control, "control")):
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / f"{stem}.lock"
        path.touch(mode=0o600)
        info = path.stat()
        pins[f"{stem}_lock"] = [info.st_dev, info.st_ino]
    runtime.pg_image = "sha256:" + "9" * 64
    inventory = {
        "version": 1,
        "release": record["release_digest"],
        "project": record["project"],
        "attempt": record["attempt"],
        "pgdata": record["pgdata_identity"],
        "system_id": record["system_id"],
        "containers": [
            {
                "role": role,
                "id": record["containers"][role],
                "image": runtime.pg_image if role == "db" else record["image_id"],
                "config": "a" * 64,
                "run": "b" * 64,
            }
            for role in ("api", "supervisor", "db")
        ],
        "network": {"id": "8" * 64, "config": "c" * 64},
        "forwarder": {
            **{key: record["forwarder"][key] for key in ("pid", "start_ticks", "boot_id")},
            "identity": fingerprint(record["forwarder"]),
            "listener": record["listener_inode"],
            "port": record["port"],
        },
        "ipc": {
            **pins,
            "api": record["api_socket"],
            "control": record["control_socket"],
            "cap": [1, 5],
            "cap_digest": "d" * 64,
        },
    }
    grant = {
        "version": 1,
        "state": "STOP_PENDING",
        "instance_id": record["instance_id"],
        "command_id": record["stop_command"],
        "finalize_command_id": record["finalize_command"],
        "generation": record["stop_generation"],
        "owner_epoch": record["supervisor_epoch"],
        "owner_uuid": str(uuid4()),
        "daemon_id": record["docker_id"],
        "inventory": inventory,
    }
    stamp = {"pid": 999, "start_ticks": "1", "boot_id": str(uuid4())}
    write_record(
        receipt_path(root, record),
        {
            "version": 1,
            "grant": grant,
            "owner": stamp,
            "launcher": stamp,
            "state": "COMPLETED",
            "pending": None,
            "completed": [
                {
                    "stage": stage,
                    "ack": "DRAINED" if stage in {"forwarder", "ipc"} else 204,
                    "proof": "e" * 64,
                }
                for stage in STAGES
            ],
        },
    )
    write_record(
        root / f"stop-forwarder-{record['attempt']}-drained.json",
        {
            "version": 1,
            "attempt": record["attempt"],
            "command_id": record["stop_command"],
            "forwarder": record["forwarder"],
            "listener_inode": record["listener_inode"],
            "drained": True,
        },
    )
    engine = SimpleNamespace(
        networks=lambda _project: [] if runtime.network(set()) is None else [{}],
        container=lambda cid: runtime.inspect("container", cid),
        network=lambda _cid: runtime.network(set()),
    )
    view = SimpleNamespace(engine=engine, ids=runtime.ids, check_daemon=lambda: None)
    with patch("omnis_cli.stop_owner._view", return_value=view):
        yield
