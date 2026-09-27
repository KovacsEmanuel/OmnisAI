"""Installed CLI talks to a real supervisor/DB outside the source tree."""

import asyncio
import json
import os
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from test_local_control import request
from test_supervisor import start_supervisor, stop_process, wait_ready


def test_installed_cli_status_has_private_identity_and_no_http_claim(
    migrated_database_url: URL, ipc_directory: Path
) -> None:
    binary = os.environ["OMNIS_CLI_BIN"]
    control_dir = ipc_directory / "omnis"
    control_dir.mkdir(mode=0o700)
    state = ipc_directory / "state" / "omnis"
    state.mkdir(parents=True, mode=0o700)
    state.chmod(0o700)
    (ipc_directory / "state").chmod(0o700)
    supervisor = start_supervisor(migrated_database_url, control_dir)
    cap: str | None = None
    foreign: socket.socket | None = None
    try:
        wait_ready(supervisor)
        cap = (control_dir / "control.cap").read_text()
        private = asyncio.run(request(control_dir, cap, {"op": "status"}))
        assert private["ok"] and "status" in private
        identity = private["status"]["instance_id"]
        foreign = socket.socket()
        foreign.bind(("127.0.0.1", 0))
        foreign.listen(1)
        foreign.settimeout(0.2)
        record = {
            "version": 1,
            "instance_id": identity,
            "release": "0.1.0",
            "schema": "0004_pairing_receipts",
            "project": "omnis-local-1",
            "origin": f"http://127.0.0.1:{foreign.getsockname()[1]}",
        }
        metadata = state / "instance.json"
        metadata.write_text(json.dumps(record))
        metadata.chmod(0o600)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "XDG_STATE_HOME": str(state.parent),
            "XDG_RUNTIME_DIR": str(ipc_directory),
        }
        completed = subprocess.run(
            [binary, "status", "--json"],
            cwd=ipc_directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert completed.returncode == 0 and completed.stderr == ""
        result = json.loads(completed.stdout)
        assert result["instance_id"] == identity
        assert result["control_ready"] and result["dashboard_ready"] is False
        assert result["reason"] == "HTTP_UNVERIFIED"
        assert cap not in completed.stdout + completed.stderr
        with pytest.raises(TimeoutError):
            foreign.accept()  # The private status path must not adopt a foreign HTTP listener.
        record["instance_id"] = str(uuid4())
        metadata.write_text(json.dumps(record))
        wrong = subprocess.run(
            [binary, "status", "--json"],
            cwd=ipc_directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert wrong.returncode == 3
        assert json.loads(wrong.stdout)["control_ready"] is False
    finally:
        if foreign is not None:
            foreign.close()
        output = stop_process(supervisor)
        assert supervisor.returncode == 0, "Owned supervisor must stop before disposable DB drop"
        if cap is not None:
            assert cap not in "".join(output)
