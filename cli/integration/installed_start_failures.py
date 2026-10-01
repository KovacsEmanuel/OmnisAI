"""M09 installed first-start DB exit. Own resources only; no product fault flag."""

import json
import os
import select
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from installed_start import assert_resources_absent, save_probe
from omnis_cli.lifecycle import lifecycle_lock
from omnis_cli.start_runtime import ControlRuntime


def run_lock_expiry(data, receipt, cli):
    """Real 180s installed startup deadline, before any project/state creation."""
    state = Path(tempfile.mkdtemp(prefix="s2lock-", dir=os.environ["TMPDIR"]))
    root = state / "s/omnis"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    runtime = ControlRuntime(data, time.monotonic() + 30)
    assert runtime.ids() == []
    assert runtime.inspect("network", receipt["project"] + "_control") is None
    image_before = (data / "omnis/image.json").read_bytes()
    begin = time.monotonic()
    with lifecycle_lock(data / "omnis", begin + 200):
        p = subprocess.run(
            [cli, "start", "--no-open", "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=200,
        )
    elapsed = time.monotonic() - begin
    result = json.loads(p.stdout)
    assert p.returncode == 2 and result["reason"] == "LIFECYCLE_BUSY"
    assert result["dashboard_ready"] is False and result["assessment_ready"] is False
    assert 178 <= elapsed < 195, "Product lock deadline was not measured"
    assert not root.exists(), "Expired before-effects lock created state"
    assert not list(state.iterdir()), "Expired lock created runtime/HOME root effects"
    assert (data / "omnis/image.json").read_bytes() == image_before
    runtime.deadline = time.monotonic() + 30
    assert runtime.ids() == []
    assert runtime.inspect("network", receipt["project"] + "_control") is None
    print(
        f"INSTALLED_START_LOCK_EXPIRY project={receipt['project']} exit=2 elapsed={elapsed:.3f}s effects=none cleanup_allowance=not_entered",
        flush=True,
    )


def run_database_readiness_failure(data, receipt, cli):
    state = Path(tempfile.mkdtemp(prefix="s2db-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    runtime = ControlRuntime(data, time.monotonic() + 120)
    record = {}
    process = None
    pin = -1
    paused = False
    probe_ok = cleanup_ok = False
    save_probe(state, data, receipt["project"], root, record, probe="PREPARED", cleanup="NOT_RUN")
    begin = time.monotonic()
    try:
        process = subprocess.Popen(
            [cli, "start", "--no-open", "--port", str(port), "--json"],
            cwd=state,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        pin = os.pidfd_open(process.pid)
        until = begin + 40
        while time.monotonic() < until:
            journal = root / "startup.json"
            if journal.exists():
                record = json.loads(journal.read_text())
                if record.get("phase") == "STARTING" and record.get("containers", {}).get("db"):
                    runtime.attempt = record["attempt"]
                    cid = record["containers"]["db"]
                    item = runtime.attest(cid, "db", root, control, port)
                    if (
                        item["State"]["Running"]
                        and item["State"].get("Health", {}).get("Status") != "healthy"
                    ):
                        signal.pidfd_send_signal(pin, signal.SIGSTOP)
                        paused = True
                        assert runtime.ids() == [cid], "Fault missed DB-only first start"
                        runtime.run("container", "stop", "--time", "15", cid, cap=22, effect=True)
                        assert (
                            runtime.attest(cid, "db", root, control, port)["State"]["Status"]
                            == "exited"
                        )
                        signal.pidfd_send_signal(pin, signal.SIGCONT)
                        paused = False
                        break
            assert process.poll() is None, "DB fault phase missed"
            time.sleep(0.01)
        else:
            raise AssertionError("DB did not reach first-start unhealthy boundary")
        out, err = process.communicate(timeout=125)
        elapsed = time.monotonic() - begin
        record = json.loads((root / "startup.json").read_text())
        result = json.loads(out)
        assert process.returncode == 3, "Unreconciled DB failure; retain data/locator"
        assert result["reason"] == "SERVICE_READINESS_FAILED"
        assert result["dashboard_ready"] is False and result["assessment_ready"] is False
        assert record["failed_phase"] == "STARTING" and record["phase"] == "FAILED_CLEANED"
        assert record["cleanup"] == [] and set(record["containers"]) == {"db"}
        assert "system_id" not in record and "open_command" not in record
        assert not (root / "instance.json").exists()
        assert not (root / "forwarder.log").exists()
        assert elapsed < 180 + 100, "startup plus separately declared cleanup allowance exceeded"
        runtime.deadline = time.monotonic() + 30
        assert_resources_absent(runtime, root, control, record)
        assert (root / "postgres").is_dir()
        assert (root / "db-password").read_text().strip() not in out + err
        probe_ok = cleanup_ok = True
        print(
            f"INSTALLED_START_DB_FAILURE project={receipt['project']} exit=3 reason=SERVICE_READINESS_FAILED elapsed={elapsed:.3f}s cleanup_allowance=100s data_retained={root}",
            flush=True,
        )
    finally:
        try:
            if paused and pin >= 0:
                signal.pidfd_send_signal(pin, signal.SIGCONT)
            if process is not None and not select.select([pin], [], [], 0)[0]:
                signal.pidfd_send_signal(pin, signal.SIGTERM)
                process.wait(timeout=125)
            if (root / "startup.json").exists():
                record = json.loads((root / "startup.json").read_text())
        finally:
            if pin >= 0:
                os.close(pin)
            if process is not None:
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
            save_probe(
                state,
                data,
                receipt["project"],
                root,
                record,
                probe="PASS" if probe_ok else "FAIL",
                cleanup="VERIFIED" if cleanup_ok else "UNCERTAIN",
            )
