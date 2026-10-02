"""Fresh launcher for parent/owner-death probes; no resource creation of its own."""

import json
import os
import runpy
import socket
import subprocess
import sys
import time
from pathlib import Path

from omnis_cli.lifecycle import lifecycle_lock, process_identity
from omnis_cli.stop_owner import (
    _load_runtime,
    _process_stamp,
    prepare_stop_inventory,
    run_stop_owner,
)
from omnis_cli.stop_receipt import encoded, persist, receipt_path


def main():
    payload = json.loads(sys.stdin.buffer.readline())
    root, control, data = (Path(payload[key]) for key in ("root", "control", "data"))
    record = payload["record"]
    runtime = _load_runtime(data, record, time.monotonic() + 12)
    helper = runpy.run_path(payload["fixture_module"])
    with (
        lifecycle_lock(data / "omnis", runtime.deadline) as data_fd,
        lifecycle_lock(root, runtime.deadline) as state_fd,
    ):
        inventory = prepare_stop_inventory(runtime, root, control, record)
        grant = {
            "version": 1,
            "state": "STOP_PENDING",
            "instance_id": record["instance_id"],
            "command_id": record["stop_command"],
            "finalize_command_id": record["finalize_command"],
            "generation": 2,
            "owner_epoch": 1,
            "daemon_id": record["docker_id"],
            "inventory": inventory,
        }
        if payload["mode"] == "pre-admit":
            persist(
                receipt_path(root, record),
                {
                    "version": 1,
                    "grant": grant,
                    "owner": None,
                    "launcher": _process_stamp(process_identity(os.getpid())),
                    "state": "PREPARED",
                    "pending": None,
                    "completed": [],
                },
            )
            parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            owner = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "omnis_cli.stop_owner",
                    str(child.fileno()),
                    str(data_fd),
                    str(state_fd),
                ],
                pass_fds=(child.fileno(), data_fd, state_fd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            child.close()
            pin = os.pidfd_open(owner.pid)
            parent.send(
                encoded(
                    {
                        "root": str(root),
                        "control": str(control),
                        "data_home": str(data),
                        "record": record,
                        "grant": grant,
                        "deadline_ns": int(runtime.deadline * 1_000_000_000),
                    }
                )
            )
            parent.settimeout(5)
            assert parent.recv(128) == b"READY"
            observer = socket.socket(fileno=int(payload["observer_fd"]))
            observer.sendmsg(
                [str(owner.pid).encode()],
                [
                    (
                        socket.SOL_SOCKET,
                        socket.SCM_RIGHTS,
                        __import__("array").array("i", [parent.fileno()]),
                    )
                ],
            )
            print(owner.pid, flush=True)
            sys.stdin.buffer.read(1)  # Kept alive until observer kills this pinned launcher.
            os.close(pin)
            return
        original = subprocess.Popen

        def popen(argv, **kwargs):
            owner = original(helper["owner_test_argv"](argv), **kwargs)
            print(owner.pid, flush=True)
            return owner

        subprocess.Popen = popen
        run_stop_owner(runtime, root, control, record, grant, lock_fds=(data_fd, state_fd))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError):
        raise SystemExit(4) from None
