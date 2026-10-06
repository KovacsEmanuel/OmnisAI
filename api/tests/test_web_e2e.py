"""Browser acceptance with a real owned PostgreSQL, supervisor and HTTP-served build."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from pydantic import TypeAdapter
from sqlalchemy.engine import URL

from e2e_processes import OwnedChildren, cleanup_all, owned_children
from e2e_secrets import assert_secret_free, decode_markers
from test_supervisor import start_supervisor, wait_ready

ROOT = Path(__file__).resolve().parents[2]


def launch_api(
    listener: socket.socket, database_url: URL, ipc_directory: Path
) -> subprocess.Popen[str]:
    return subprocess.Popen(
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
            "OMNIS_DATABASE_URL": database_url.render_as_string(hide_password=False),
            "OMNIS_CONTROL_DIR": str(ipc_directory),
            "OMNIS_WEB_ROOT": str(ROOT / "web/dist"),
        },
        pass_fds=(listener.fileno(),),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_api(api: subprocess.Popen[str], origin: str) -> None:
    deadline = time.monotonic() + 10
    with httpx.Client(base_url=origin, trust_env=False, timeout=0.5) as client:
        while time.monotonic() < deadline:
            assert api.poll() is None, "Owned API exited during startup"
            try:
                response = client.get("/health/ready")
                if response.status_code == 200 and response.json()["dashboard_ready"]:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.05)
    pytest.fail("Built dashboard/control failed real readiness")


@pytest.fixture
def e2e_family(migrated_database_url: URL) -> Iterator[OwnedChildren]:
    # Depend on the DB fixture so adoption cleanup precedes disposable DB deletion.
    with owned_children() as family:
        yield family


@pytest.mark.parametrize(
    "case",
    ["flow", "expiry", "control", "database", "api", "offline", "accessibility", "b03", "b04"],
)
def test_built_web_against_real_control_plane(
    migrated_database_url: URL, ipc_directory: Path, e2e_family: OwnedChildren, case: str
) -> None:
    assert (ROOT / "web/dist/omnis-web.json").is_file(), "Run make build-web before E2E"
    supervisor = start_supervisor(migrated_database_url, ipc_directory)
    api: subprocess.Popen[str] | None = None
    driver: subprocess.Popen[str] | None = None
    first_api: subprocess.Popen[str] | None = None
    first_driver: subprocess.Popen[str] | None = None
    restart_listener: socket.socket | None = None
    prior_output = ""
    output = Path(os.environ["TMPDIR"]) / "omnis-p03-e2e" / case
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").unlink(missing_ok=True)
    (output / "browser-result.json").unlink(missing_ok=True)
    marker_read, marker_write = os.pipe()
    os.set_blocking(marker_read, False)
    os.set_blocking(marker_write, False)
    try:
        wait_ready(supervisor)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(16)
            origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            if case == "b04":
                # dup() can reset the shared OFD to blocking. Reserve before uvicorn makes it nonblocking.
                restart_listener = listener.dup()
            api = launch_api(listener, migrated_database_url, ipc_directory)
            wait_api(api, origin)

        # Except for B04 restart, the API is now the only owner of its reserved listener.
        if case == "b04":
            with httpx.Client(base_url=origin, trust_env=False, timeout=3) as client:
                asset = client.get("/")
            assert asset.status_code == 200, (
                "B04 listener stopped serving before browser navigation"
            )
            print("B04_ASSET_AFTER_DUP status=200", flush=True)

        def launch_driver(stage: str, current_api: subprocess.Popen[str]) -> subprocess.Popen[str]:
            return subprocess.Popen(
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
                    "OMNIS_E2E_API_PID": str(current_api.pid),
                    "OMNIS_E2E_SUPERVISOR_PID": str(supervisor.pid),
                    "OMNIS_E2E_OUTPUT": str(output),
                    "OMNIS_E2E_MARKER_FD": str(marker_write),
                    "OMNIS_E2E_STAGE": stage,
                },
                pass_fds=(marker_write,),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )

        driver = launch_driver("before" if case == "b04" else "single", api)
        stdout, stderr = driver.communicate(timeout=120)
        prior_output += stdout + stderr
        assert driver.returncode == 0, stdout + stderr
        assert f"E2E PASS {case}" in stdout
        print(stdout.strip())
        if case == "b04":
            before = TypeAdapter(dict[str, object]).validate_json(
                (output / "browser-result.json").read_text(), strict=True
            )
            assert before["passed"] is True and before["stage"] == "before"
            assert restart_listener is not None
            first_api, first_driver = api, driver
            first_api.terminate()
            prior_output += "".join(first_api.communicate(timeout=5))
            assert first_api.returncode == -signal.SIGTERM, "Old API did not exit for restart"
            api = launch_api(restart_listener, migrated_database_url, ipc_directory)
            assert api.pid != first_api.pid, "Restart must use a new backend process"
            wait_api(api, origin)
            driver = launch_driver("after", api)
            stdout, stderr = driver.communicate(timeout=120)
            prior_output += stdout + stderr
            assert driver.returncode == 0, stdout + stderr
            assert "B04_G01_RESTART_PASS" in stdout and "E2E PASS b04" in stdout
            print(stdout.strip())
    finally:
        primary = sys.exception()
        cleanup_issues: list[Exception] = []
        resources = []
        if driver is not None:
            resources.append((driver, True))
        if first_driver is not None:
            resources.append((first_driver, True))
        if api is not None:
            resources.append((api, False))
        if first_api is not None:
            resources.append((first_api, False))
        resources.append((supervisor, False))
        outputs: list[tuple[str, str]] = []
        try:
            outputs = cleanup_all(resources, ownership=e2e_family)
        except Exception as exc:
            cleanup_issues.append(exc)
        try:
            if restart_listener is not None:
                restart_listener.close()
        except Exception as exc:
            cleanup_issues.append(exc)
        marker_evidence = b""
        try:
            os.close(marker_write)
            marker_evidence = os.read(marker_read, 16385)
        except Exception as exc:
            cleanup_issues.append(exc)
        finally:
            try:
                os.close(marker_read)
            except Exception as exc:
                cleanup_issues.append(exc)
        # Verdicts come only after every owned process has received teardown.
        for label, process, allowed in (
            ("api", api, {-signal.SIGTERM}),
            ("first_api", first_api, {-signal.SIGTERM}),
            ("supervisor", supervisor, {0, 3}),
        ):
            if process is not None and process.returncode not in allowed:
                cleanup_issues.append(
                    AssertionError(
                        f"E2E cleanup {label} PID {process.pid} exited {process.returncode}; expected {sorted(allowed)}"
                    )
                )
        combined = prior_output + "".join(part for output_pair in outputs for part in output_pair)
        markers: list[str] = []
        try:
            markers = decode_markers(marker_evidence)
            assert_secret_free(markers, [combined])
            assert "Traceback" not in combined
            # Independent parent channel checks unlabelled raw values in every process's logs too.
            assert "omnis_session=" not in combined and "csrf_token" not in combined
            if primary is None and case != "accessibility":
                assert len(markers) >= 4, "Expected code/capability/session/CSRF evidence"
        except Exception as exc:
            cleanup_issues.append(exc)
        if primary is None and not cleanup_issues and driver is not None and driver.returncode == 0:
            record = TypeAdapter(dict[str, object]).validate_json(
                (output / "browser-result.json").read_text(), strict=True
            )
            assert record["passed"] is True and record["scenario"] == case
            if case == "b04":
                assert record["stage"] == "after" and first_api is not None and api is not None
                record["backend_restart_verified"] = first_api.pid != api.pid
            assert_secret_free(markers, [json.dumps(record)])
            record.update(server_log_secret_check=True, cleanup_verified=True)
            (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        if cleanup_issues:
            if isinstance(primary, Exception):
                raise ExceptionGroup(
                    "E2E primary failure and separate teardown failures", [primary, *cleanup_issues]
                )
            if primary is not None:
                raise BaseExceptionGroup(
                    "E2E primary failure and separate teardown failures", [primary, *cleanup_issues]
                )
            raise ExceptionGroup("E2E teardown failures", cleanup_issues)
