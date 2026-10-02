"""SL04 installed stop/start proof on a fresh, owned P0 fixture only."""

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from installed_start import assert_resources_absent, resource_snapshot, save_probe, teardown
from omnis_cli.control import request
from omnis_cli.start_runtime import ControlRuntime


def run_installed_stop(data, receipt, cli):
    state = Path(tempfile.mkdtemp(prefix="s4-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    cwd = state / "cwd"
    cwd.mkdir(mode=0o700)
    (cwd / "compose.yaml").write_text("foreign: ignored\n")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    runtime = ControlRuntime(data, time.monotonic() + 30)
    assert runtime.receipt.image_id == receipt["image_id"]
    record = {}
    before = None
    before_journal = None
    proof = cleanup = False
    save_probe(state, data, receipt["project"], root, record, probe="PREPARED", cleanup="NOT_RUN")

    def command(*args, expected=0, timeout=330):
        result = subprocess.run(
            [cli, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode not in {0, 2, 3, 4}:
            raise RuntimeError("Unknown installed CLI child outcome")
        assert result.returncode == expected, f"Installed {args[0]} exit {result.returncode}"
        assert "Traceback" not in result.stderr
        return json.loads(result.stdout)

    try:
        started = command("start", "--no-open", "--port", str(port), "--json")
        assert started["state"] == "READY" and started["assessment_ready"] is False
        record = json.loads((root / "startup.json").read_text())
        runtime.attempt = record["attempt"]
        runtime.deadline = time.monotonic() + 30
        before = resource_snapshot(runtime, root, control, port)
        initial = request(control, {"op": "status"})
        assert initial["admission_open"] is True and initial["generation"] == 1
        before_journal = (root / "startup.json").read_bytes()
        db = record["containers"]["db"]
        runtime.psql(db, "CREATE TABLE sl04_sentinel (value integer NOT NULL)")
        runtime.psql(db, "INSERT INTO sl04_sentinel VALUES (7)")

        stopper = subprocess.Popen(
            [cli, "stop", "--json"],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            until = time.monotonic() + 40
            while time.monotonic() < until:
                if json.loads((root / "startup.json").read_text())["phase"] == "STOPPING":
                    break
                assert stopper.poll() is None, "Stop finished before durable intent was observed"
                time.sleep(0.005)
            else:
                raise AssertionError("Installed Stop did not publish STOPPING")
            stopping_status = subprocess.run(
                [cli, "status", "--json"],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=50,
            )
            queued = subprocess.run(
                [cli, "start", "--no-open", "--port", str(port), "--json"],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=220,
            )
            stop_out, stop_err = stopper.communicate(timeout=220)
            assert stopper.returncode == 0 and "Traceback" not in stop_err
            stopped = json.loads(stop_out)
            assert queued.returncode == 4, "Start queued behind Stop must not become restart"
            assert json.loads(queued.stdout)["reason"] == "INSTANCE_SHUTTING_DOWN"
            assert stopping_status.returncode == 4
            assert json.loads(stopping_status.stdout)["state"] == "STOPPING"
        finally:
            if stopper.poll() is None:
                stopper.terminate()  # Only this direct, still-live test child.
                stopper.wait(timeout=30)
        assert stopped["state"] == "STOPPED"
        assert stopped["dashboard_ready"] is False and stopped["assessment_ready"] is False
        record = json.loads((root / "startup.json").read_text())
        assert record["phase"] == "STOPPED"
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        assert (root / "postgres").is_dir() and (root / "db-password").is_file()
        first_receipt = (root / "startup.json").read_bytes()
        assert command("stop", "--json", timeout=50)["state"] == "STOPPED"
        assert (root / "startup.json").read_bytes() == first_receipt
        status = command("status", "--json", timeout=50)
        assert status["state"] == "STOPPED" and status["dashboard_ready"] is False

        # SO_REUSEADDR=False may retain the old port in TIME_WAIT; do not adopt it.
        until = time.monotonic() + 70
        while True:
            with socket.socket() as candidate:
                try:
                    candidate.bind(("127.0.0.1", port))
                    break
                except OSError:
                    if time.monotonic() >= until:
                        raise AssertionError("Owned listener did not release its port") from None
            time.sleep(0.2)
        restarted = command("start", "--no-open", "--port", str(port), "--json")
        assert restarted["state"] == "READY" and restarted["generation"] > initial["generation"]
        assert restarted["supervisor_epoch"] > initial["supervisor_epoch"]
        assert restarted["instance_id"] == started["instance_id"]
        record = json.loads((root / "startup.json").read_text())
        runtime.attempt = record["attempt"]
        runtime.deadline = time.monotonic() + 30
        assert runtime.psql(record["containers"]["db"], "SELECT value FROM sl04_sentinel") == "7"
        assert command("status", "--json", timeout=50)["state"] == "READY"
        assert command("stop", "--json")["state"] == "STOPPED"
        record = json.loads((root / "startup.json").read_text())
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        assert (root / "postgres").is_dir()
        proof = cleanup = True
        print(
            f"INSTALLED_STOP_VERIFIED project={receipt['project']} restart=explicit data=retained",
            flush=True,
        )
    finally:
        # An ordinary RED refusal with unchanged READY authority remains a
        # test-owned healthy instance. Only then can the existing observer
        # dismantle it; a partial Stop keeps its locator and UNCERTAIN verdict.
        if not cleanup and os.path.lexists(root / "startup.json"):
            record = json.loads((root / "startup.json").read_text())
            runtime.attempt = record["attempt"]
            runtime.deadline = time.monotonic() + 110
            if record["phase"] == "STOPPED":
                assert_resources_absent(runtime, root, control, record)
                cleanup = True
            elif record["phase"] == "READY":
                current = request(control, {"op": "status"})
                if current["admission_open"] is True and current["shutdown_command_id"] is None:
                    if (
                        before_journal is not None
                        and record["attempt"] == json.loads(before_journal)["attempt"]
                    ):
                        assert (root / "startup.json").read_bytes() == before_journal
                        assert resource_snapshot(runtime, root, control, port) == before
                    teardown(runtime, root, control, port, record)
                    assert_resources_absent(runtime, root, control, record)
                    cleanup = True
        save_probe(
            state,
            data,
            receipt["project"],
            root,
            record,
            probe="PASS" if proof else "FAIL",
            cleanup="VERIFIED" if cleanup else "UNCERTAIN",
        )


def run_emergency_stop(data, receipt, cli):
    """Unavailable own API is not a DB STOPPED receipt or permission to adopt peers."""
    state = Path(tempfile.mkdtemp(prefix="s4e-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    runtime = ControlRuntime(data, time.monotonic() + 30)
    record = {}
    proof = cleanup = False
    save_probe(state, data, receipt["project"], root, record, probe="PREPARED", cleanup="NOT_RUN")
    try:
        started = subprocess.run(
            [cli, "start", "--no-open", "--port", str(port), "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=330,
        )
        assert started.returncode == 0
        record = json.loads((root / "startup.json").read_text())
        runtime.attempt = record["attempt"]
        runtime.deadline = time.monotonic() + 35
        assert set(resource_snapshot(runtime, root, control, port)) == set(
            record["containers"].values()
        )
        api = record["containers"]["api"]
        runtime.attest(api, "api", root, control, port)
        runtime.run("container", "stop", "--time", "15", api, cap=25, effect=True)
        assert runtime.attest(api, "api", root, control, port)["State"]["Running"] is False
        stopped = subprocess.run(
            [cli, "stop", "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=220,
        )
        assert stopped.returncode == 4, f"Emergency must be UNCERTAIN, got {stopped.returncode}"
        result = json.loads(stopped.stdout)
        assert result["state"] == "UNCERTAIN" and result["dashboard_ready"] is False
        marker = root / "unreconciled.json"
        assert marker.is_file(), "Emergency took no durable unreconciled marker"
        receipt_bytes = marker.read_bytes()
        evidence = json.loads(receipt_bytes)
        assert evidence["instance_id"] == record["instance_id"]
        assert evidence["attempt"] == record["attempt"]
        assert evidence["project"] == receipt["project"]
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        refused = subprocess.run(
            [cli, "start", "--no-open", "--port", str(port), "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=50,
        )
        assert refused.returncode == 4 and json.loads(refused.stdout)["state"] == "UNCERTAIN"
        assert marker.read_bytes() == receipt_bytes, "Retry erased unreconciled intent"
        status = subprocess.run(
            [cli, "status", "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=50,
        )
        assert status.returncode == 4
        assert json.loads(status.stdout)["state"] == "RECOVERY_REQUIRED"
        assert (root / "postgres").is_dir()
        proof = cleanup = True
    finally:
        if not cleanup and os.path.lexists(root / "startup.json"):
            record = json.loads((root / "startup.json").read_text())
            runtime.attempt = record["attempt"]
            runtime.deadline = time.monotonic() + 110
            if runtime.ids():
                # Observer-only rescue of this exact fresh fixture is not proof
                # of the emergency implementation; its probe remains FAIL.
                teardown(runtime, root, control, port, record)
            assert_resources_absent(runtime, root, control, record)
            cleanup = True
        save_probe(
            state,
            data,
            receipt["project"],
            root,
            record,
            probe="PASS" if proof else "FAIL",
            cleanup="VERIFIED" if cleanup else "UNCERTAIN",
        )
    if proof and cleanup:
        print(f"INSTALLED_EMERGENCY_UNCERTAIN project={receipt['project']} marker=retained")
