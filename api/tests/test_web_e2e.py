"""Browser acceptance with a real owned PostgreSQL, supervisor and HTTP-served build."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import URL

from test_supervisor import start_supervisor, stop_process, wait_ready

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("case", ["flow", "expiry", "control", "database", "api", "accessibility"])
def test_built_web_against_real_control_plane(
    migrated_database_url: URL, ipc_directory: Path, case: str
) -> None:
    assert (ROOT / "web/dist/omnis-web.json").is_file(), "Run make build-web before E2E"
    supervisor = start_supervisor(migrated_database_url, ipc_directory)
    api: subprocess.Popen[str] | None = None
    output = Path(os.environ["TMPDIR"]) / "omnis-p03-e2e" / case
    output.mkdir(parents=True, exist_ok=True)
    try:
        wait_ready(supervisor)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(16)
            origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            api = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "uvicorn",
                    "omnis.api:create_app",
                    "--factory",
                    "--fd",
                    str(listener.fileno()),
                    "--no-access-log",
                    "--no-proxy-headers",
                    "--log-level",
                    "warning",
                    "--timeout-graceful-shutdown",
                    "3",
                ],
                cwd=ipc_directory,
                env={
                    "PATH": os.environ["PATH"],
                    "OMNIS_HTTP_PORT": str(listener.getsockname()[1]),
                    "OMNIS_DATABASE_URL": migrated_database_url.render_as_string(
                        hide_password=False
                    ),
                    "OMNIS_CONTROL_DIR": str(ipc_directory),
                    "OMNIS_WEB_ROOT": str(ROOT / "web/dist"),
                },
                pass_fds=(listener.fileno(),),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 10
            with httpx.Client(base_url=origin, trust_env=False, timeout=0.5) as client:
                while time.monotonic() < deadline:
                    assert api.poll() is None, "Owned API exited during startup"
                    try:
                        response = client.get("/health/ready")
                        if response.status_code == 200 and response.json()["dashboard_ready"]:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.05)
                else:
                    pytest.fail("Built dashboard/control failed real readiness")
        # The API is now the only owner of its reserved listener.
        result = subprocess.run(
            ["node", str(ROOT / "web/tests/e2e/run.mjs"), case],
            cwd=ROOT / "web",
            env={
                **os.environ,
                "OMNIS_E2E_ORIGIN": origin,
                "OMNIS_E2E_CONTROL": str(ipc_directory),
                "OMNIS_E2E_DATABASE_URL": migrated_database_url.render_as_string(
                    hide_password=False
                ),
                "OMNIS_E2E_PYTHON": sys.executable,
                "OMNIS_E2E_API_PID": str(api.pid),
                "OMNIS_E2E_SUPERVISOR_PID": str(supervisor.pid),
                "OMNIS_E2E_OUTPUT": str(output),
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"E2E PASS {case}" in result.stdout
        print(result.stdout.strip())
    finally:
        if api is not None:
            api_output = stop_process(api)
            assert api.returncode == -signal.SIGTERM
        else:
            api_output = ("", "")
        supervisor_output = stop_process(supervisor)
        assert supervisor.returncode in {0, 3}  # DB loss exits bounded with its documented error.
        combined = "".join((*api_output, *supervisor_output))
        assert "Traceback" not in combined
        # Node separately checks raw test codes/session/CSRF against browser output and storage.
        assert "omnis_session=" not in combined and "csrf_token" not in combined
