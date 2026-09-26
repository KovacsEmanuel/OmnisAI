"""Exercise installed supervisor + Uvicorn over real Unix/TCP sockets."""

import asyncio
import hashlib
import os
import secrets
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx

from test_local_control import request
from test_supervisor import stop_process, wait_ready


def assert_clean_guard_report(events):
    assert events and events[0] == "GUARD_READY", "missing audit channel readiness"
    assert events.count("GUARD_READY") == 1, "duplicate audit readiness"
    assert set(events) <= {"GUARD_READY", "CONNECT_ALLOWED", "DNS_ALLOWED"}, "forbidden or unknown audit event"


def exercise_installed_control(python, database_url):
    with tempfile.TemporaryDirectory(prefix="omnis-live-", dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        guard = str(Path(__file__).with_name("process_guard.py"))
        env = {"PATH": os.environ.get("PATH", ""),
               "OMNIS_DATABASE_URL": database_url.render_as_string(hide_password=False),
               "OMNIS_CONTROL_DIR": name}
        for mode, event in (("negative", "EGRESS_DENIED"), ("positive", "CONNECT_ALLOWED")):
            with tempfile.TemporaryFile(dir=directory) as audit:
                guard_result = subprocess.run([str(python), "-I", guard, mode], cwd=directory,
                    env={**env, "OMNIS_TEST_AUDIT_FD": str(audit.fileno())}, pass_fds=(audit.fileno(),),
                    capture_output=True, text=True, timeout=5)
                assert guard_result.returncode == 0
                audit.seek(0)
                assert audit.read().decode().splitlines() == ["GUARD_READY", event]
        processes = []
        expected_exits = []
        audits = []
        def launch_guarded(command, *, pass_fds=(), extra_env=None, expected_exit=0):
            audit = tempfile.TemporaryFile(dir=directory)
            audits.append(audit)
            process = subprocess.Popen(command, cwd=directory,
                env={**env, **(extra_env or {}), "OMNIS_TEST_AUDIT_FD": str(audit.fileno())},
                pass_fds=(*pass_fds, audit.fileno()), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append(process)
            expected_exits.append(expected_exit)
            return process
        sensitive = []
        try:
            supervisor = launch_guarded([str(python), "-I", guard, "omnis.supervisor"])
            wait_ready(supervisor)
            capability = (directory / "control.cap").read_text()
            sensitive.append(capability)
            async def control(command):
                return await request(directory, capability, command)
            status = asyncio.run(control({"op": "status"}))["status"]
            code = secrets.token_urlsafe(24)
            sensitive.append(code)
            issuance = {"op": "pairing", "instance_id": status["instance_id"],
                        "issuance_id": str(uuid4()), "digest": hashlib.sha256(code.encode()).hexdigest()}
            paired = asyncio.run(control(issuance))
            assert paired["ok"] and code not in str(paired)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(16)
                port = listener.getsockname()[1]
                origin = f"http://127.0.0.1:{port}"
                api_command = [str(python), "-I", guard, "uvicorn", "omnis.api:create_app", "--factory",
                               "--fd", str(listener.fileno()), "--no-access-log", "--no-proxy-headers",
                               "--log-level", "warning", "--timeout-graceful-shutdown", "3"]
                def launch_api():
                    return launch_guarded(api_command, pass_fds=(listener.fileno(),),
                                          extra_env={"OMNIS_HTTP_PORT": str(port)}, expected_exit=-signal.SIGTERM)
                def ready(client, process):
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        assert process.poll() is None, "Installed API exited before readiness"
                        try:
                            response = client.get("/health/ready")
                            if response.status_code == 200:
                                assert response.json()["dashboard_ready"] is False
                                return
                        except httpx.TransportError:
                            pass
                        time.sleep(0.05)
                    raise AssertionError("Installed API did not become ready")
                api = launch_api()
                with httpx.Client(base_url=origin, trust_env=False, timeout=0.3) as client:
                    ready(client, api)
                    assert client.get("/api/instance").status_code == 401
                    response = client.post("/api/pairing", json={"code": code}, headers={"origin": origin})
                    assert response.status_code == 200
                    sensitive.append(client.cookies["omnis_session"])
                    assert asyncio.run(control(issuance))["ok"]
                    assert client.post("/api/pairing", json={"code": code}, headers={"origin": origin}).status_code == 401
                    csrf = response.json()["csrf_token"]
                    sensitive.append(csrf)
                    actual = client.get("/api/instance").json()
                    assert actual["instance_id"] == status["instance_id"]
                    assert actual["supervisor_epoch"] == status["supervisor_epoch"]
                    assert actual["supervisor_ready"] and not actual["admission_open"]
                    # Actual API process restart: session persists, no new supervisor/admission.
                    stop_process(api)
                    replacement = launch_api()
                    ready(client, replacement)
                    assert client.get("/api/instance").json() == actual
                    assert client.post("/api/logout", headers={"origin": origin, "x-csrf-token": csrf}).status_code == 204
                    assert client.get("/api/session").status_code == 401
                    assert client.get("/health/live", headers={"host": "attacker.invalid"}).status_code == 400
        finally:
            outputs = [stop_process(process) for process in reversed(processes)]
            reports = []
            try:
                for audit in audits:
                    audit.seek(0)
                    reports.append(audit.read().decode().splitlines())
            finally:
                for audit in audits:
                    audit.close()
            # Pinned Uvicorn deliberately re-raises SIGTERM after graceful shutdown.
            assert [process.returncode for process in processes] == expected_exits
            for events in reports:
                assert_clean_guard_report(events)
            for stdout, stderr in outputs:
                assert "TEST_EGRESS_DENIED" not in stdout + stderr
                assert "TEST_PROCESS_DENIED" not in stdout + stderr
                assert not any(value in stdout + stderr for value in sensitive), "Process logs exposed a synthetic secret"
