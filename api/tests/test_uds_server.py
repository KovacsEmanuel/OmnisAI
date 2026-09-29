"""The installed API owns one private Unix listener, never a TCP admin port."""

import asyncio
import http.client
import os
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from omnis.serve import PrivateServer, private_http_listener, serve, server_config


def test_uds_server_has_a_finite_graceful_shutdown_budget() -> None:
    config = server_config()
    assert config.timeout_graceful_shutdown == 5


def test_stalled_server_shutdown_has_a_hard_process_deadline() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        code = (
            "import asyncio\n"
            "import omnis.serve as m\n"
            "async def stalled(self, sockets=None):\n"
            "    print('STALLED_SERVER_STARTED', flush=True)\n"
            "    while True: await asyncio.sleep(1)\n"
            "m.uvicorn.Server.serve = stalled\n"
            "raise SystemExit(m.main())\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            cwd=directory,
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_HTTP_DIR": str(directory),
                "OMNIS_HTTP_PORT": "8765",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            readable, _, _ = select.select([process.stdout], [], [], 5)
            assert readable, "The injected stalled server did not start"
            assert process.stdout.readline().strip() == "STALLED_SERVER_STARTED"
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=11)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)
                raise AssertionError("API shutdown exceeded its hard deadline") from None
            assert process.returncode == 4
            assert not (directory / "api.sock").exists()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)


def test_blocked_api_event_loop_is_killed_by_an_independent_owner() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        code = (
            "import os, time\n"
            "import omnis.serve as m\n"
            "async def blocked(self, sockets=None):\n"
            "    print('BLOCKED_API_STARTED', os.getpid(), flush=True)\n"
            "    while True: time.sleep(60)\n"
            "m.uvicorn.Server.serve = blocked\n"
            "raise SystemExit(m.main())\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            cwd=directory,
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_HTTP_DIR": str(directory),
                "OMNIS_HTTP_PORT": "8765",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            readable, _, _ = select.select([process.stdout], [], [], 5)
            assert readable, "The blocked API process did not start"
            marker, child_pid = process.stdout.readline().split()
            assert marker == "BLOCKED_API_STARTED"
            assert int(child_pid) > 0
            os.kill(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)
                raise AssertionError("Blocked API event loop outlived the process owner") from None
            assert process.returncode == 4
            assert not Path(f"/proc/{child_pid}").exists()
            with private_http_listener(directory):
                assert (directory / "api.sock").is_socket()
            assert not (directory / "api.sock").exists()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)


def test_cancel_resistant_lifespan_task_is_killed_by_the_process_owner() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        code = (
            "import asyncio, os\n"
            "import omnis.serve as m\n"
            "async def leaked():\n"
            "    while True:\n"
            "        try: await asyncio.sleep(1)\n"
            "        except asyncio.CancelledError: pass\n"
            "async def stopped(self, sockets=None):\n"
            "    asyncio.create_task(leaked())\n"
            "    print('LEAKING_API_STARTED', os.getpid(), flush=True)\n"
            "    while not self.should_exit: await asyncio.sleep(0.05)\n"
            "m.uvicorn.Server.serve = stopped\n"
            "raise SystemExit(m.main())\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            cwd=directory,
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_HTTP_DIR": str(directory),
                "OMNIS_HTTP_PORT": "8765",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            readable, _, _ = select.select([process.stdout], [], [], 5)
            assert readable, "The cancellation-resistant API process did not start"
            marker, child_pid = process.stdout.readline().split()
            assert marker == "LEAKING_API_STARTED"
            assert int(child_pid) > 0
            os.kill(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)
                raise AssertionError("Lingering lifespan task outlived the process owner") from None
            assert process.returncode == 4
            assert not Path(f"/proc/{child_pid}").exists()
            assert not (directory / "api.sock").exists()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)


def test_signal_after_reap_never_targets_a_recycled_child_pid() -> None:
    code = (
        "import os, signal\n"
        "import omnis.serve as m\n"
        "real_kill, real_waitpid = os.kill, os.waitpid\n"
        "retired = [-1]\n"
        "def checked_kill(pid, signum):\n"
        "    if pid == retired[0]:\n"
        "        print('SENT_TO_REAPED_PID', flush=True)\n"
        "        raise RuntimeError('Reaped child was targeted')\n"
        "    return real_kill(pid, signum)\n"
        "def injected_waitpid(pid, options):\n"
        "    result = real_waitpid(pid, options)\n"
        "    if result[0] == pid and retired[0] == -1:\n"
        "        retired[0] = pid\n"
        "        os.kill(os.getpid(), signal.SIGTERM)\n"
        "    return result\n"
        "os.kill, os.waitpid = checked_kill, injected_waitpid\n"
        "m._child_main = lambda: 0\n"
        "raise SystemExit(m.main())\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "SENT_TO_REAPED_PID" not in process.stdout
    assert process.returncode == 0  # The child had already finished successfully.


@pytest.mark.asyncio
async def test_cancelled_api_start_releases_the_private_socket_and_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        monkeypatch.setenv("OMNIS_HTTP_DIR", str(directory))
        monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
        entered = asyncio.Event()

        async def stalled(self: PrivateServer, sockets: list[socket.socket] | None = None) -> None:
            entered.set()
            await asyncio.Future()

        monkeypatch.setattr(PrivateServer, "serve", stalled)
        task = asyncio.create_task(serve())
        await asyncio.wait_for(entered.wait(), timeout=2)
        path = directory / "api.sock"
        assert path.is_socket()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)
        assert not path.exists()
        with private_http_listener(directory):
            assert path.is_socket()
        assert not path.exists()


def test_real_api_process_serves_liveness_on_owned_uds_only() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        path = directory / "api.sock"
        process = subprocess.Popen(
            [sys.executable, "-I", "-m", "omnis.serve"],
            cwd=directory,
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_HTTP_DIR": str(directory),
                "OMNIS_HTTP_PORT": "8765",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 10
            while not path.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            assert process.poll() is None and path.is_socket()
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

            def request(host: str) -> tuple[int, bytes]:
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(2)
                    connection.connect(str(path))
                    connection.sendall(
                        f"GET /health/live HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode()
                    )
                    response = http.client.HTTPResponse(connection)
                    response.begin()
                    result = response.status, response.read(4096)
                    response.close()
                    return result

            assert request("127.0.0.1:8765") == (200, b'{"status":"live"}')
            denied, _body = request("attacker.invalid:8765")
            assert denied == 400
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            try:
                _stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                _stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, f"API process exit {process.returncode}: {stderr[-400:]}"
        assert not path.exists()


def test_private_http_listener_is_owned_and_removed_after_shutdown() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        path = directory / "api.sock"
        with private_http_listener(directory) as listener:
            info = path.lstat()
            assert stat.S_ISSOCK(info.st_mode)
            assert info.st_uid == os.getuid()
            assert stat.S_IMODE(info.st_mode) == 0o600
            assert listener.family == socket.AF_UNIX
            assert listener.getsockname() == str(path)
            with socket.socket(socket.AF_UNIX) as peer:
                peer.settimeout(1)
                peer.connect(str(path))
        assert not path.exists()


def test_private_http_listener_refuses_a_symlink_without_replacing_it() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        target = directory / "target"
        target.write_text("synthetic")
        path = directory / "api.sock"
        path.symlink_to(target)
        with pytest.raises(ValueError):
            with private_http_listener(directory):
                pass
        assert path.is_symlink()
        assert target.read_text() == "synthetic"


def test_second_start_cannot_unlink_a_bound_listener_before_listen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        path = directory / "api.sock"
        bound = threading.Event()
        resume = threading.Event()
        errors: list[BaseException] = []

        class PausingSocket(socket.socket):
            def listen(self, backlog: int = 0) -> None:
                if threading.current_thread().name == "first-api":
                    bound.set()
                    if not resume.wait(timeout=3):
                        raise TimeoutError("First listener was not released")
                super().listen(backlog)

        monkeypatch.setattr(socket, "socket", PausingSocket)

        def first_start() -> None:
            try:
                with private_http_listener(directory):
                    pass
            except BaseException as exc:
                errors.append(exc)

        first = threading.Thread(target=first_start, name="first-api", daemon=True)
        first.start()
        assert bound.wait(timeout=2), "The first listener must be bound but not serving"
        inode = path.lstat().st_ino
        try:
            with pytest.raises(BlockingIOError):
                with private_http_listener(directory):
                    pass
            assert path.lstat().st_ino == inode
        finally:
            resume.set()
            first.join(timeout=2)
        assert not first.is_alive()
        assert not errors
        assert not path.exists()
