import asyncio
import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from conftest import connect_test_database
from test_local_control import request


@pytest.mark.parametrize(
    "delay", ["cold", "before_acquire", "model_import", "sender_construct", "owner_loss"]
)
def test_cold_model_preparation_does_not_consume_execution_lease(
    migrated_database_url: URL, ipc_directory: Path, tmp_path: Path, delay: str
) -> None:
    # Declared latency fault, not attribution of a historical startup timeout.
    script = """
import asyncio
import os
from pathlib import Path
import signal
import socket
import sys
import time

source, delay = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(source))

def no_egress(event, args):
    if (event.startswith('socket.getaddrinfo')
        or (event == 'socket.__new__' and args[1] != socket.AF_UNIX)
        or (event == 'socket.connect' and args[1] != sys.argv[3])
        or event in {'subprocess.Popen', 'os.system', 'os.posix_spawn'}):
        os._exit(81)

sys.addaudithook(no_egress)
from omnis.supervisor import __main__ as consumer
assert Path(consumer.__file__).resolve() == source / 'omnis/supervisor/__main__.py'
assert 'openai' not in sys.modules and 'omnis.supervisor.model_sender' not in sys.modules
print('COLD_SOURCE', flush=True)
sender_path = str(source / 'omnis/supervisor/model_sender.py')
held = False
stopping = False

def started(code, offset):
    global held
    if code.co_filename == sender_path and code.co_qualname in {
        'ModelSender.send', 'ModelSender.metadata', 'Backend.connect_tcp'
    }:
        os._exit(82)
    if not held and (
        (delay == 'before_acquire' and code is consumer.InstanceService.acquire.__code__)
        or (delay == 'owner_loss' and code is consumer.InstanceService.quiesce.__code__)
        or (code.co_filename == sender_path and (
            (delay == 'model_import' and code.co_name == '<module>')
            or (delay == 'sender_construct' and code.co_qualname == 'ModelSender.__init__')
        ))
    ):
        held = True
        print('LATENCY_FAULT', flush=True)
        time.sleep(5.25)

def returned(code, offset, value):
    global stopping
    if code.co_filename == sender_path and code.co_qualname == 'ModelSender.close':
        print('SENDER_CLOSED', flush=True)
    if code is consumer.InstanceService.heartbeat.__code__ and not stopping:
        stopping = True
        print('HEARTBEAT', flush=True)
        asyncio.get_running_loop().call_soon(os.kill, os.getpid(), signal.SIGTERM)

def raised(code, offset, error):
    if code is consumer.InstanceService._require_owner.__code__:
        assert isinstance(error, consumer.ControlConflict)
        print(error.code.value, flush=True)

monitor = sys.monitoring.PROFILER_ID
sys.monitoring.use_tool_id(monitor, 'cold-supervisor-regression')
for event, callback in (
    (sys.monitoring.events.PY_START, started),
    (sys.monitoring.events.PY_RETURN, returned),
    (sys.monitoring.events.RAISE, raised),
):
    sys.monitoring.register_callback(monitor, event, callback)
sys.monitoring.set_events(monitor, sys.monitoring.events.PY_START
                          | sys.monitoring.events.PY_RETURN | sys.monitoring.events.RAISE)
try:
    result = consumer.main()
finally:
    sys.monitoring.set_events(monitor, 0)
    sys.monitoring.free_tool_id(monitor)
raise SystemExit(result)
"""
    vault, keys = tmp_path / "vault", tmp_path / "keys"
    for path in (vault, keys):
        path.mkdir(mode=0o700)
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(Path(__file__).resolve().parents[1] / "src"),
            delay,
            str(Path(os.environ["OMNIS_TEST_SOCKET_DIR"]) / ".s.PGSQL.5432"),
        ],
        cwd=ipc_directory,
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": migrated_database_url.render_as_string(hide_password=False),
            "OMNIS_CONTROL_DIR": str(ipc_directory),
            "OMNIS_VAULT_DIR": str(vault),
            "OMNIS_VAULT_KEY_DIR": str(keys),
            "OMNIS_MODEL_EGRESS_DIR": "/vault",
        },
        capture_output=True,
        text=True,
        timeout=20,
    )
    markers = process.stdout.splitlines()
    assert "COLD_SOURCE" in markers
    assert markers.count("LATENCY_FAULT") == int(delay != "cold")
    assert markers.count("SENDER_CLOSED") == 1
    assert not (ipc_directory / "control.sock").exists()
    assert not list(keys.iterdir())
    assert {path.name for path in vault.iterdir()} <= {"vault.pending"}
    with connect_test_database(migrated_database_url) as db:
        assert db.execute("SELECT generation, admission_open FROM instance_control").fetchone() == (
            0,
            False,
        )
        assert db.execute("SELECT count(*) FROM system_operation").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM model_dispatch_v2").fetchone() == (0,)
        lease = db.execute(
            "SELECT epoch, owner IS NOT NULL, expires_at > clock_timestamp() FROM supervisor_lease"
        ).fetchone()
    if delay == "owner_loss":
        assert process.returncode == 3
        assert process.stderr == "SUPERVISOR_UNAVAILABLE\n"
        assert "LEASE_LOST" in markers and "SUPERVISOR_READY" not in markers
        assert "HEARTBEAT" not in markers
        assert lease == (1, True, False)
    else:
        assert process.returncode == 0, f"Supervisor exit {process.returncode}: {markers}"
        assert process.stderr == ""
        assert markers.count("SUPERVISOR_READY") == 1 and markers.count("HEARTBEAT") == 1
        assert "LEASE_LOST" not in markers
        assert lease == (1, False, None)


def start_supervisor(database_url: URL, directory: Path) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [sys.executable, "-I", "-m", "omnis.supervisor"],
        cwd=directory,
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_DATABASE_URL": database_url.render_as_string(hide_password=False),
            "OMNIS_CONTROL_DIR": str(directory),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process


def wait_ready(process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = selector.select(8)
        assert ready, "Supervisor did not produce bounded startup result"
        line = process.stdout.readline().strip()
    assert line == "SUPERVISOR_READY", f"Supervisor not ready (exit {process.poll()})"


def stop_process(process: subprocess.Popen[str], *, crash: bool = False) -> tuple[str, str]:
    if process.poll() is None:
        process.kill() if crash else process.terminate()
    return process.communicate(timeout=8)


@pytest.mark.parametrize(
    "crash_point", ["before_shutdown", "after_commit", "after_quiescence", "lost_ack"]
)
@pytest.mark.asyncio
async def test_real_supervisor_is_unique_and_restart_stays_closed(
    migrated_database_url: URL, ipc_directory: Path, crash_point: str
) -> None:
    first = start_supervisor(migrated_database_url, ipc_directory)
    processes = [first]
    try:
        wait_ready(first)
        capability = (ipc_directory / "control.cap").read_text()
        status = (await request(ipc_directory, capability, {"op": "status"}))["status"]
        instance = status["instance_id"]
        assert status["supervisor_ready"] and not status["admission_open"]
        second = start_supervisor(migrated_database_url, ipc_directory)
        processes.append(second)
        stdout, stderr = second.communicate(timeout=8)
        assert second.returncode != 0 and "SUPERVISOR_READY" not in stdout
        assert capability not in stdout + stderr
        opened = await request(
            ipc_directory,
            capability,
            {
                "op": "open",
                "instance_id": instance,
                "command_id": str(uuid4()),
                "expected_generation": status["generation"],
            },
        )
        assert opened["ok"]
        readback = opened["status"]
        stop_id = None
        if crash_point != "before_shutdown":
            stop_id = str(uuid4())
            command = {
                "op": "shutdown",
                "instance_id": instance,
                "command_id": stop_id,
                "expected_generation": opened["status"]["generation"],
            }
            if crash_point == "lost_ack":
                _, writer = await asyncio.open_unix_connection(str(ipc_directory / "control.sock"))
                writer.write(
                    json.dumps(
                        {"version": 1, "capability": capability, "command": command}
                    ).encode()
                    + b"\n"
                )
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                # No response is consumed. Resolve by readback, then retry the same UUID.
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    readback = (await request(ipc_directory, capability, {"op": "status"}))[
                        "status"
                    ]
                    if readback["shutdown_command_id"] == stop_id:
                        break
                    await asyncio.sleep(0.05)
                assert readback["shutdown_command_id"] == stop_id
            stopped = await request(ipc_directory, capability, command)
            assert stopped["ok"] and stopped["status"]["admission_open"] is False
            assert stopped["result_generation"] == opened["status"]["generation"] + 1
            if crash_point == "after_quiescence":
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    readback = (await request(ipc_directory, capability, {"op": "status"}))[
                        "status"
                    ]
                    if readback["quiesced_generation"] == readback["generation"]:
                        break
                    await asyncio.sleep(0.05)
                assert readback["quiesced_generation"] == readback["generation"]
        # Crash at the chosen boundary; no in-memory barrier may be relied on.
        stop_process(first, crash=True)
        await asyncio.sleep(5.2)
        third = start_supervisor(migrated_database_url, ipc_directory)
        processes.append(third)
        wait_ready(third)
        fresh_capability = (ipc_directory / "control.cap").read_text()
        assert fresh_capability != capability
        assert (await request(ipc_directory, capability, {"op": "status"}))[
            "error"
        ] == "CONTROL_DENIED"
        after = (await request(ipc_directory, fresh_capability, {"op": "status"}))["status"]
        assert after["instance_id"] == instance
        assert after["shutdown_command_id"] is not None
        if stop_id is not None:
            assert after["shutdown_command_id"] == stop_id
        assert not after["admission_open"] and not after["shutdown_finalized"]
        assert after["supervisor_epoch"] > status["supervisor_epoch"]
        refused = await request(
            ipc_directory,
            fresh_capability,
            {
                "op": "open",
                "instance_id": instance,
                "command_id": str(uuid4()),
                "expected_generation": after["generation"],
            },
        )
        assert refused["error"] == "SHUTDOWN_INCOMPLETE"
        # Quiescence is observed, not assumed from the request ACK.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            after = (await request(ipc_directory, fresh_capability, {"op": "status"}))["status"]
            if after["quiesced_generation"] == after["generation"]:
                break
            await asyncio.sleep(0.05)
        assert after["quiesced_generation"] == after["generation"]
        finalized = await request(
            ipc_directory,
            fresh_capability,
            {
                "op": "finalize",
                "instance_id": instance,
                "command_id": str(uuid4()),
                "expected_generation": after["generation"],
            },
        )
        assert finalized["ok"]
        out, err = stop_process(third)
        assert third.returncode == 0 and fresh_capability not in out + err
        fourth = start_supervisor(migrated_database_url, ipc_directory)
        processes.append(fourth)
        wait_ready(fourth)
        final_capability = (ipc_directory / "control.cap").read_text()
        assert not (await request(ipc_directory, final_capability, {"op": "status"}))["status"][
            "admission_open"
        ]
        resumed = await request(
            ipc_directory,
            final_capability,
            {
                "op": "open",
                "instance_id": instance,
                "command_id": str(uuid4()),
                "expected_generation": after["generation"],
            },
        )
        assert resumed["ok"] and resumed["status"]["admission_open"]
    finally:
        for process in processes:
            stop_process(process)


def test_supervisor_startup_failure_is_sanitized(ipc_directory: Path) -> None:
    process = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.supervisor"],
        cwd=ipc_directory,
        env={
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_CONTROL_DIR": str(ipc_directory),
            "OMNIS_DATABASE_URL": "synthetic-secret-marker",
        },
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert process.returncode != 0
    assert "synthetic-secret-marker" not in process.stdout + process.stderr
    assert "SUPERVISOR_UNAVAILABLE" in process.stderr
