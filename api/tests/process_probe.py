"""Exercise installed supervisor + Uvicorn over real Unix/TCP sockets."""

import asyncio
import hashlib
import os
import secrets

import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from test_local_control import request
from test_supervisor import stop_process, wait_ready


def exercise_installed_control(python, database_url):
    with tempfile.TemporaryDirectory(prefix="omnis-live-", dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        guard = str(Path(__file__).with_name("process_guard.py"))
        env = {"PATH": os.environ.get("PATH", ""),
               "OMNIS_DATABASE_URL": database_url.render_as_string(hide_password=False),
               "OMNIS_CONTROL_DIR": name}
        negative = subprocess.run([str(python), "-I", guard, "negative"], cwd=directory, env=env,
                                  capture_output=True, text=True, timeout=5)
        assert negative.returncode == 0 and negative.stdout.strip() == "GUARD_NEGATIVE_OK"
        supervisor = subprocess.Popen([str(python), "-I", guard, "omnis.supervisor"], cwd=directory, env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes = [supervisor]
        sensitive = []
        try:
            wait_ready(supervisor)
            capability = (directory / "control.cap").read_text()
            sensitive.append(capability)
            async def control(command):
                return await request(directory, capability, command)
            status = asyncio.run(control({"op": "status"}))["status"]
            code = secrets.token_urlsafe(24)
            sensitive.append(code)
            paired = asyncio.run(control({"op": "pairing", "instance_id": status["instance_id"],
                                          "digest": hashlib.sha256(code.encode()).hexdigest()}))
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
                    process = subprocess.Popen(api_command, cwd=directory, env={**env, "OMNIS_HTTP_PORT": str(port)},
                                               pass_fds=(listener.fileno(),), stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, text=True)
                    processes.append(process)
                    return process
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
            for stdout, stderr in outputs:
                assert "TEST_EGRESS_DENIED" not in stdout + stderr
                assert "TEST_PROCESS_DENIED" not in stdout + stderr
                assert not any(value in stdout + stderr for value in sensitive), "Process logs exposed a synthetic secret"
