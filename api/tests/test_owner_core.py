"""The clean exec owner is separate from the API event loop and database."""

import fcntl
import http.client
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def test_exec_owner_reports_worker_startup_failure_without_an_http_directory() -> None:
    process = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.owner"],
        cwd=Path(os.environ["TMPDIR"]),
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert process.returncode == 3
    assert "API_UNAVAILABLE" in process.stderr


def test_owner_rejects_preexisting_native_thread_before_worker_spawn() -> None:
    code = (
        "import _thread, os, threading\n"
        "import omnis.owner as owner\n"
        "ready, release = threading.Event(), threading.Event()\n"
        "def other_thread():\n"
        "    ready.set()\n"
        "    release.wait(timeout=4)\n"
        "_thread.start_new_thread(other_thread, ())\n"
        "assert ready.wait(timeout=1)\n"
        "def forbidden_spawn(*_args, **_kwargs):\n"
        "    print('UNSAFE_WORKER_SPAWN', flush=True)\n"
        "    raise OSError('synthetic spawn refusal')\n"
        "os.posix_spawn = forbidden_spawn\n"
        "try: raise SystemExit(owner.main())\n"
        "finally: release.set()\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=Path(os.environ["TMPDIR"]),
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert process.returncode == 4
    assert "UNSAFE_WORKER_SPAWN" not in process.stdout


def test_owner_never_releases_a_worker_after_a_pending_stop() -> None:
    code = (
        "import os, signal, sys\n"
        "import omnis.owner as owner\n"
        "real_open, real_write = os.pidfd_open, os.write\n"
        "def observed_open(pid):\n"
        "    fd = real_open(pid)\n"
        "    if sys.argv[1] == 'stop': os.kill(os.getpid(), signal.SIGTERM)\n"
        "    return fd\n"
        "def observed_write(fd, payload):\n"
        "    if payload == b'1': print('GATE_RELEASED', flush=True)\n"
        "    return real_write(fd, payload)\n"
        "os.pidfd_open, os.write = observed_open, observed_write\n"
        "raise SystemExit(owner.main())\n"
    )
    for mode, expected in (("normal", 3), ("stop", 4)):
        process = subprocess.run(
            [sys.executable, "-I", "-c", code, mode],
            cwd=Path(os.environ["TMPDIR"]),
            env={"PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert process.returncode == expected
        assert ("GATE_RELEASED" in process.stdout) is (mode == "normal")


def test_full_stderr_pipe_cannot_hold_a_failed_spawn() -> None:
    code = (
        "import os\n"
        "import omnis.owner as owner\n"
        "def refused(*_args, **_kwargs):\n"
        "    print('SPAWN_REFUSED', flush=True)\n"
        "    raise OSError('synthetic exec failure')\n"
        "os.posix_spawn = refused\n"
        "raise SystemExit(owner.main())\n"
    )
    read_fd, write_fd = os.pipe()
    flags = fcntl.fcntl(write_fd, fcntl.F_GETFL)
    fcntl.fcntl(write_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    while True:
        try:
            os.write(write_fd, b"x" * 4096)
        except BlockingIOError:
            break
    fcntl.fcntl(write_fd, fcntl.F_SETFL, flags)
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", code],
        cwd=Path(os.environ["TMPDIR"]),
        env={"PATH": os.environ.get("PATH", "")},
        stdout=subprocess.PIPE,
        stderr=write_fd,
        text=True,
        start_new_session=True,
    )
    os.close(write_fd)
    try:
        stdout, _stderr = process.communicate(timeout=3)
        assert process.returncode == 3
        assert stdout.strip() == "SPAWN_REFUSED"
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        os.close(read_fd)


def test_owner_reconciles_child_when_pidfd_stop_signal_is_denied() -> None:
    code = (
        "import os, signal, sys, time\n"
        "import omnis.owner as owner\n"
        "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})\n"
        "signal.signal(signal.SIGTERM, lambda *_args: None)\n"
        "child = os.fork()\n"
        "if child == 0:\n"
        "    time.sleep(5)\n"
        "    os._exit(0)\n"
        "fd = os.pidfd_open(child)\n"
        "def denied(_fd, _signum):\n"
        "    print('PIDFD_SEND_DENIED', flush=True)\n"
        "    raise PermissionError('injected owned signal denial')\n"
        "signal.pidfd_send_signal = denied\n"
        "os.kill(os.getpid(), signal.SIGTERM)\n"
        "try: result = owner._watch(child, fd)\n"
        "finally:\n"
        "    try: reaped, _status = os.waitpid(child, os.WNOHANG)\n"
        "    except ChildProcessError: reaped = child\n"
        "    if reaped == 0:\n"
        "        os.kill(child, signal.SIGKILL)\n"
        "        os.waitpid(child, 0)\n"
        "    os.close(fd)\n"
        "    print('CHILD_GONE', flush=True)\n"
        "raise SystemExit(result)\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=Path(os.environ["TMPDIR"]),
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    assert "PIDFD_SEND_DENIED" in process.stdout
    assert "CHILD_GONE" in process.stdout
    assert process.returncode == 4


def test_owner_reconciles_child_when_signal_wait_fails() -> None:
    code = (
        "import os, signal, time\n"
        "import omnis.owner as owner\n"
        "child = os.fork()\n"
        "if child == 0:\n"
        "    time.sleep(5)\n"
        "    os._exit(0)\n"
        "fd = os.pidfd_open(child)\n"
        "def unavailable(_signals, _timeout):\n"
        "    print('WAIT_UNAVAILABLE', flush=True)\n"
        "    raise OSError('injected signal wait failure')\n"
        "signal.sigtimedwait = unavailable\n"
        "try: result = owner._watch(child, fd)\n"
        "finally:\n"
        "    try: reaped, _status = os.waitpid(child, os.WNOHANG)\n"
        "    except ChildProcessError: reaped = child\n"
        "    if reaped == 0:\n"
        "        os.kill(child, signal.SIGKILL)\n"
        "        os.waitpid(child, 0)\n"
        "    os.close(fd)\n"
        "    print('CHILD_GONE', flush=True)\n"
        "raise SystemExit(result)\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=Path(os.environ["TMPDIR"]),
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    assert "WAIT_UNAVAILABLE" in process.stdout
    assert "CHILD_GONE" in process.stdout
    assert process.returncode == 4


def test_exec_owner_serves_real_uds_and_stops_only_its_child() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        process = subprocess.Popen(
            [sys.executable, "-I", "-m", "omnis.owner"],
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
        child_fd: int | None = None
        child_pid: int | None = None
        try:
            deadline = time.monotonic() + 5
            children: list[str] = []
            while time.monotonic() < deadline:
                assert process.poll() is None, "API owner exited before spawning a worker"
                children = (
                    Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
                )
                if children:
                    break
                time.sleep(0.05)
            assert len(children) == 1, "API owner has an unexpected child set"
            child_pid = int(children[0])
            info = Path(f"/proc/{child_pid}/stat").read_text().rsplit(") ", 1)[1].split()
            child_fd = os.pidfd_open(child_pid)
            after = Path(f"/proc/{child_pid}/stat").read_text().rsplit(") ", 1)[1].split()
            assert info[19] == after[19] and int(after[1]) == process.pid
            assert int(after[2]) == process.pid and int(after[3]) == process.pid
            assert Path(f"/proc/{child_pid}").stat().st_uid == os.getuid()
            path = directory / "api.sock"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert process.poll() is None, "API owner exited before liveness"
                try:
                    with socket.socket(socket.AF_UNIX) as connection:
                        connection.settimeout(2)
                        connection.connect(str(path))
                        connection.sendall(
                            b"GET /health/live HTTP/1.1\r\n"
                            b"Host: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
                        )
                        response = http.client.HTTPResponse(connection)
                        response.begin()
                        if (response.status, response.read(4096)) == (200, b'{"status":"live"}'):
                            break
                except (OSError, http.client.HTTPException):
                    time.sleep(0.1)
            else:
                raise AssertionError("Owner did not release the real worker")
            os.kill(process.pid, signal.SIGTERM)
            process.communicate(timeout=15)
            assert process.returncode == 0
            assert not path.exists()
            stopped = select.poll()
            stopped.register(child_fd, select.POLLIN)
            assert stopped.poll(0), "Owned worker survived stop"
            assert not Path(f"/proc/{child_pid}").exists()
        finally:
            if child_fd is not None:
                os.close(child_fd)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)


def test_exec_worker_cannot_inherit_an_ambient_parent_fd() -> None:
    code = (
        "import os, sys\n"
        "import omnis.owner as owner\n"
        "fd = os.open(sys.argv[1], os.O_RDONLY)\n"
        "os.set_inheritable(fd, True)\n"
        "raise SystemExit(owner.main())\n"
    )
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        ambient = directory / "ambient-probe"
        ambient.write_text("synthetic")
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", code, str(ambient)],
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
            while time.monotonic() < deadline:
                assert process.poll() is None, "API owner exited before worker exec"
                if (directory / "api.sock").is_socket():
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("Installed-style worker never bound its private socket")
            children = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
            assert len(children) == 1
            worker_pid = int(children[0])
            targets: list[str] = []
            for descriptor in Path(f"/proc/{worker_pid}/fd").iterdir():
                try:
                    targets.append(os.readlink(descriptor))
                except FileNotFoundError:
                    pass
            assert str(ambient) not in targets, "Worker inherited a foreign parent descriptor"
            os.kill(process.pid, signal.SIGTERM)
            process.communicate(timeout=15)
            assert process.returncode == 0
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)


def test_full_stdout_pipe_cannot_block_owner_stop() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        read_fd, write_fd = os.pipe()
        flags = fcntl.fcntl(write_fd, fcntl.F_GETFL)
        fcntl.fcntl(write_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        while True:
            try:
                os.write(write_fd, b"x" * 4096)
            except BlockingIOError:
                break
        fcntl.fcntl(write_fd, fcntl.F_SETFL, flags)
        process = subprocess.Popen(
            [sys.executable, "-I", "-m", "omnis.owner"],
            cwd=directory,
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_HTTP_DIR": str(directory),
                "OMNIS_HTTP_PORT": "8765",
            },
            stdout=write_fd,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        os.close(write_fd)
        try:
            path = directory / "api.sock"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert process.poll() is None, "Owner exited before real worker liveness"
                try:
                    with socket.socket(socket.AF_UNIX) as connection:
                        connection.settimeout(2)
                        connection.connect(str(path))
                        connection.sendall(
                            b"GET /health/live HTTP/1.1\r\n"
                            b"Host: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
                        )
                        reply = http.client.HTTPResponse(connection)
                        reply.begin()
                        if (reply.status, reply.read(4096)) == (200, b'{"status":"live"}'):
                            break
                except (OSError, http.client.HTTPException):
                    time.sleep(0.1)
            else:
                raise AssertionError("Worker was not live with its owner stdout blocked")
            os.kill(process.pid, signal.SIGTERM)
            process.communicate(timeout=5)
            assert process.returncode == 0
            assert not path.exists()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)
            os.close(read_fd)
