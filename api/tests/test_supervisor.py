import asyncio
import json
import os
import selectors
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from test_local_control import ipc_directory, request


def start_supervisor(database_url, directory):
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


def wait_ready(process):
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = selector.select(8)
        assert ready, "Supervisor did not produce bounded startup result"
        line = process.stdout.readline().strip()
    assert line == "SUPERVISOR_READY", f"Supervisor not ready (exit {process.poll()})"


def stop_process(process, *, crash=False):
    if process.poll() is None:
        process.kill() if crash else process.terminate()
    return process.communicate(timeout=8)


@pytest.mark.parametrize(
    "crash_point", ["before_shutdown", "after_commit", "after_quiescence", "lost_ack"]
)
@pytest.mark.asyncio
async def test_real_supervisor_is_unique_and_restart_stays_closed(
    migrated_database_url, ipc_directory, crash_point
):
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


def test_supervisor_startup_failure_is_sanitized(ipc_directory):
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
