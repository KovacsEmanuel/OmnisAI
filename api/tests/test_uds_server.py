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

_OWNER_DEATH_FUSE = (
    "import os, threading\n"
    "fuse_read, fuse_write = os.pipe()\n"
    "original_child_main = m._child_main\n"
    "def fused_child_main():\n"
    "    os.close(fuse_write)\n"
    "    def owner_gone():\n"
    "        try: os.read(fuse_read, 1)\n"
    "        finally: os._exit(4)\n"
    "    threading.Thread(target=owner_gone, daemon=True).start()\n"
    "    return original_child_main()\n"
    "m._child_main = fused_child_main\n"
)


def test_uds_server_has_a_finite_graceful_shutdown_budget() -> None:
    config = server_config()
    assert config.timeout_graceful_shutdown == 5


def test_stalled_server_shutdown_has_a_hard_process_deadline() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        code = (
            ("import asyncio\nimport omnis.serve as m\n")
            + _OWNER_DEATH_FUSE
            + (
                "async def stalled(self, sockets=None):\n"
                "    print('STALLED_SERVER_STARTED', flush=True)\n"
                "    while True: await asyncio.sleep(1)\n"
                "m.uvicorn.Server.serve = stalled\n"
                "raise SystemExit(m.main())\n"
            )
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
            ("import os, time\nimport omnis.serve as m\n")
            + _OWNER_DEATH_FUSE
            + (
                "async def blocked(self, sockets=None):\n"
                "    print('BLOCKED_API_STARTED', os.getpid(), flush=True)\n"
                "    while True: time.sleep(60)\n"
                "m.uvicorn.Server.serve = blocked\n"
                "raise SystemExit(m.main())\n"
            )
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
            ("import asyncio, os\nimport omnis.serve as m\n")
            + _OWNER_DEATH_FUSE
            + (
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


def test_owner_death_before_server_marker_releases_its_child() -> None:
    code = (
        (
            "import os, time\n"
            "import omnis.serve as m\n"
            "def blocked_child():\n"
            "    while True: time.sleep(60)\n"
            "m._child_main = blocked_child\n"
        )
        + _OWNER_DEATH_FUSE
        + (
            "def owner_exits(pid):\n"
            "    print('SPAWNED_CHILD', pid, flush=True)\n"
            "    os._exit(3)\n"
            "os.pidfd_open = owner_exits\n"
            "raise SystemExit(m.main())\n"
        )
    )
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    child_pid: int | None = None
    child_fd: int | None = None
    try:
        assert process.stdout is not None
        readable, _, _ = select.select([process.stdout], [], [], 5)
        assert readable, "Owner never reported the child it spawned"
        marker, pid = process.stdout.readline().split()
        assert marker == "SPAWNED_CHILD"
        child_pid = int(pid)
        path = Path(f"/proc/{child_pid}")
        if path.exists():
            before = (path / "stat").read_text().split(") ", 1)[1].split()
            candidate = os.pidfd_open(child_pid)
            try:
                after = (path / "stat").read_text().split(") ", 1)[1].split()
                assert (
                    before[19] == after[19]
                    and int(after[2]) == process.pid
                    and int(after[3]) == process.pid
                    and path.stat().st_uid == os.getuid()
                ), "Early-exit child identity is not owned"
            except BaseException:
                os.close(candidate)
                raise
            child_fd = candidate
        process.communicate(timeout=3)
        assert process.returncode == 3
        if child_fd is not None:
            exited = select.poll()
            exited.register(child_fd, select.POLLIN)
            assert exited.poll(2000), "Child stayed alive after its owner exited"
        deadline = time.monotonic() + 2
        while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not Path(f"/proc/{child_pid}").exists(), "Early-exit child not reaped"
    finally:
        if child_fd is not None:
            try:
                signal.pidfd_send_signal(child_fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(child_fd)
        if process.poll() is None:
            process.kill()  # Unreaped direct child, never a recycled numeric PID.
        process.communicate(timeout=5)


def test_signal_after_reap_never_targets_a_recycled_child_pid() -> None:
    code = (
        "import os, signal, sys\n"
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
        "        print('REAP_OBSERVED', flush=True)\n"
        "        if sys.argv[1] == 'fault': os.kill(pid, signal.SIGTERM)\n"
        "        os.kill(os.getpid(), signal.SIGTERM)\n"
        "    return result\n"
        "os.kill, os.waitpid = checked_kill, injected_waitpid\n"
        "m._child_main = lambda: 0\n"
        "raise SystemExit(m.main())\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, "normal"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "REAP_OBSERVED" in process.stdout
    assert "SENT_TO_REAPED_PID" not in process.stdout
    assert process.returncode == 0  # The child had already finished successfully.
    fault = subprocess.run(
        [sys.executable, "-I", "-c", code, "fault"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "REAP_OBSERVED" in fault.stdout
    assert "SENT_TO_REAPED_PID" in fault.stdout
    assert fault.returncode != 0


def test_pidfd_failure_never_targets_child_pid_after_reap() -> None:
    code = (
        "import os, signal, sys\n"
        "import omnis.serve as m\n"
        "read_fd, write_fd = os.pipe()\n"
        "def child():\n"
        "    os.close(write_fd)\n"
        "    try: os.read(read_fd, 1)\n"
        "    finally: os.close(read_fd)\n"
        "    return 0\n"
        "real_kill, real_waitpid = os.kill, os.waitpid\n"
        "retired = [-1]\n"
        "def checked_kill(pid, signum):\n"
        "    if pid == retired[0]:\n"
        "        print('PIDFD_FAILURE_TARGETED_REAPED_PID', flush=True)\n"
        "        raise RuntimeError('Reaped child was targeted')\n"
        "    return real_kill(pid, signum)\n"
        "def injected_waitpid(pid, options):\n"
        "    result = real_waitpid(pid, options)\n"
        "    if result[0] == pid and retired[0] == -1:\n"
        "        retired[0] = pid\n"
        "        print('REAP_OBSERVED', flush=True)\n"
        "        os.kill(os.getpid(), signal.SIGTERM)\n"
        "    return result\n"
        "def unavailable(pid):\n"
        "    print('OWNED_PID', pid, flush=True)\n"
        "    sys.stdin.buffer.read(1)\n"
        "    raise OSError('pidfd unavailable')\n"
        "os.kill, os.waitpid, os.pidfd_open = checked_kill, injected_waitpid, unavailable\n"
        "m._child_main = child\n"
        "raise SystemExit(m.main())\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    owned_pid: int | None = None
    owned_fd: int | None = None
    owner_fd: int | None = None
    try:
        owner_fd = os.pidfd_open(process.pid)
        assert process.stdout is not None
        readable, _, _ = select.select([process.stdout], [], [], 5)
        assert readable, "Owner did not report its child identity"
        marker, pid = process.stdout.readline().split()
        assert marker == "OWNED_PID"
        owned_pid = int(pid)
        path = Path(f"/proc/{owned_pid}")
        before = (path / "stat").read_text().split(") ", 1)[1].split()
        candidate = os.pidfd_open(owned_pid)
        try:
            after = (path / "stat").read_text().split(") ", 1)[1].split()
            assert (
                before[19] == after[19]
                and int(after[1]) == process.pid
                and int(after[2]) == process.pid
                and int(after[3]) == process.pid
                and path.stat().st_uid == os.getuid()
            ), "Reported child identity does not belong to the new session"
        except BaseException:
            os.close(candidate)
            raise
        owned_fd = candidate
        assert process.stdin is not None
        process.stdin.write("1")
        process.stdin.flush()
        stdout, _stderr = process.communicate(timeout=5)
        assert "REAP_OBSERVED" in stdout
        assert "PIDFD_FAILURE_TARGETED_REAPED_PID" not in stdout
        assert process.returncode == 4
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()  # The owner can leave its handshake even on early failure.
            process.stdin = None
        if owned_fd is not None:
            try:
                signal.pidfd_send_signal(owned_fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(owned_fd)
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            if owner_fd is not None:
                try:
                    signal.pidfd_send_signal(owner_fd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()  # This unreaped direct child cannot have a recycled PID.
            process.communicate(timeout=5)
        if owner_fd is not None:
            os.close(owner_fd)
        if owned_pid is not None:
            deadline = time.monotonic() + 2
            while Path(f"/proc/{owned_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert not Path(f"/proc/{owned_pid}").exists(), "Owned child survived the test"


def test_pidfd_failure_preserves_a_child_that_already_exited_cleanly() -> None:
    code = (
        "import os, time\n"
        "from pathlib import Path\n"
        "import omnis.serve as m\n"
        "def unavailable(pid):\n"
        "    deadline = time.monotonic() + 2\n"
        "    while time.monotonic() < deadline:\n"
        "        state = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()[0]\n"
        "        if state == 'Z':\n"
        "            print('PIDFD_FAILED_AFTER_ZOMBIE', flush=True)\n"
        "            raise OSError('pidfd unavailable after exit')\n"
        "        time.sleep(0.01)\n"
        "    raise RuntimeError('child did not exit for the injected failure')\n"
        "os.pidfd_open = unavailable\n"
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

    def verify_failure(completed: subprocess.CompletedProcess[str]) -> None:
        assert "PIDFD_FAILED_AFTER_ZOMBIE" in completed.stdout
        assert completed.returncode == 0

    verify_failure(process)
    bypass = subprocess.run(
        [sys.executable, "-I", "-c", code.replace("os.pidfd_open = unavailable\n", "")],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    with pytest.raises(AssertionError, match="PIDFD_FAILED_AFTER_ZOMBIE"):
        verify_failure(bypass)


def test_signal_after_reap_preserves_the_child_startup_exit() -> None:
    code = (
        "import os, signal\n"
        "import omnis.serve as m\n"
        "real_waitpid = os.waitpid\n"
        "sent = [False]\n"
        "def injected_waitpid(pid, options):\n"
        "    result = real_waitpid(pid, options)\n"
        "    if result[0] == pid and not sent[0]:\n"
        "        sent[0] = True\n"
        "        print('REAP_OBSERVED', flush=True)\n"
        "        os.kill(os.getpid(), signal.SIGTERM)\n"
        "    return result\n"
        "os.waitpid = injected_waitpid\n"
        "m._child_main = lambda: 3\n"
        "raise SystemExit(m.main())\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "REAP_OBSERVED" in process.stdout
    assert process.returncode == 3


def test_inherited_ignored_sigchld_never_forwards_to_an_auto_reaped_pid() -> None:
    code = (
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "import omnis.serve as m\n"
        "signal.signal(signal.SIGCHLD, signal.SIG_IGN)\n"
        "real_kill, real_waitpid = os.kill, os.waitpid\n"
        "tracked = {'pid': None, 'freed': False, 'retired': False}\n"
        "def checked_kill(pid, signum):\n"
        "    if pid == tracked['pid'] and (tracked['freed'] or tracked['retired']):\n"
        "        print('FREED_PID_SIGNAL_ATTEMPT', flush=True)\n"
        "        raise RuntimeError('refuse numeric signal to a freed PID')\n"
        "    return real_kill(pid, signum)\n"
        "def observed_waitpid(pid, options):\n"
        "    result = real_waitpid(pid, options)\n"
        "    if result[0] == tracked['pid']:\n"
        "        tracked['retired'] = True\n"
        "        print('REAP_OBSERVED', flush=True)\n"
        "        if sys.argv[1] == 'fault': os.kill(pid, signal.SIGTERM)\n"
        "    return result\n"
        "def unavailable(pid):\n"
        "    tracked['pid'] = pid\n"
        "    deadline = time.monotonic() + 2\n"
        "    while time.monotonic() < deadline:\n"
        "        path = Path(f'/proc/{pid}/stat')\n"
        "        if not path.exists():\n"
        "            tracked['freed'] = True\n"
        "            break\n"
        "        if path.read_text().split(') ', 1)[1].split()[0] == 'Z': break\n"
        "        time.sleep(0.01)\n"
        "    else: raise RuntimeError('owned child did not exit')\n"
        "    os.kill(os.getpid(), signal.SIGTERM)\n"
        "    raise OSError('pidfd unavailable')\n"
        "os.kill, os.waitpid, os.pidfd_open = checked_kill, observed_waitpid, unavailable\n"
        "m._child_main = lambda: 0\n"
        "raise SystemExit(m.main())\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, "normal"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "REAP_OBSERVED" in process.stdout
    assert "FREED_PID_SIGNAL_ATTEMPT" not in process.stdout
    assert process.returncode == 0
    fault = subprocess.run(
        [sys.executable, "-I", "-c", code, "fault"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "REAP_OBSERVED" in fault.stdout
    assert "FREED_PID_SIGNAL_ATTEMPT" in fault.stdout
    assert fault.returncode != 0


def test_inherited_blocked_stop_signals_do_not_wait_for_natural_child_exit() -> None:
    read_fd, release_fd = os.pipe()
    code = (
        "import os, signal, time\n"
        "import omnis.serve as m\n"
        "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})\n"
        "real_pidfd_open = os.pidfd_open\n"
        "def ready(pid):\n"
        "    fd = real_pidfd_open(pid)\n"
        "    print('OWNER_CHILD', pid, flush=True)\n"
        "    return fd\n"
        "def child():\n"
        "    os.read(int(os.environ['OMNIS_TEST_WAIT_FD']), 1)\n"
        "    return 0\n"
        "os.pidfd_open = ready\n"
        "m._child_main = child\n"
        "raise SystemExit(m.main())\n"
    )
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            pass_fds=(read_fd,),
            env={**os.environ, "OMNIS_TEST_WAIT_FD": str(read_fd)},
        )
    except BaseException:
        os.close(read_fd)
        os.close(release_fd)
        raise
    os.close(read_fd)
    try:
        assert process.stdout is not None
        readable, _, _ = select.select([process.stdout], [], [], 5)
        assert readable, "Owner did not start a child"
        marker, pid = process.stdout.readline().split()
        assert marker == "OWNER_CHILD"
        os.kill(process.pid, signal.SIGTERM)
        process.communicate(timeout=5)
        assert process.returncode == 4
        assert not Path(f"/proc/{pid}").exists()
    finally:
        # Rescue the owned child on any assertion failure; it cannot finish
        # naturally before the stop observation, even under a delayed scheduler.
        os.close(release_fd)
        if process.poll() is None:
            assert os.getpgid(process.pid) == process.pid
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)


def test_owner_refuses_to_fork_with_another_unmasked_thread() -> None:
    code = (
        "import os, threading\n"
        "import omnis.serve as m\n"
        "release = threading.Event()\n"
        "worker = threading.Thread(target=release.wait, daemon=True)\n"
        "worker.start()\n"
        "def forbidden_fork():\n"
        "    print('UNSAFE_FORK', flush=True)\n"
        "    raise OSError('threaded fork attempted')\n"
        "os.fork = forbidden_fork\n"
        "try: result = m.main()\n"
        "finally:\n"
        "    release.set()\n"
        "    worker.join(timeout=2)\n"
        "raise SystemExit(result)\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert "UNSAFE_FORK" not in process.stdout
    assert process.returncode == 3


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

            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert process.poll() is None, "Owned API exited before liveness"
                try:
                    if request("127.0.0.1:8765") == (200, b'{"status":"live"}'):
                        break
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("Owned API never served liveness within budget")
            assert path.is_socket()
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
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
