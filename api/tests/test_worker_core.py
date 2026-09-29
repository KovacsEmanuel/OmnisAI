"""The exec worker stays inert behind a parent-bound anonymous pipe gate."""

import http.client
import os
import select
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

_GATE_SCRIPT = (
    "import os, sys\n"
    "from omnis.worker import bootstrap\n"
    "gate = int(sys.argv[1])\n"
    "real_read = os.read\n"
    "def observed_read(fd, size):\n"
    "    if fd == gate: print('GATE_WAIT', flush=True)\n"
    "    return real_read(fd, size)\n"
    "os.read = observed_read\n"
    "def app():\n"
    "    print('APP_STARTED', flush=True)\n"
    "    return 0\n"
    "raise SystemExit(bootstrap(gate, int(sys.argv[2]), app))\n"
)

_FIFO_SCRIPT = (
    "import sys\n"
    "from omnis.worker import bootstrap\n"
    "def app():\n"
    "    print('APP_STARTED', flush=True)\n"
    "    return 0\n"
    "print('WORKER_BOOT', flush=True)\n"
    "raise SystemExit(bootstrap(int(sys.argv[1]), int(sys.argv[2]), app))\n"
)

_REAL_MODULE = (
    "import os, runpy, sys\n"
    "gate = int(sys.argv[1])\n"
    "real_read = os.read\n"
    "def observed_read(fd, size):\n"
    "    if fd == gate: print('GATE_WAIT', flush=True)\n"
    "    return real_read(fd, size)\n"
    "os.read = observed_read\n"
    "sys.argv = ['omnis.worker', '--gate-fd', str(gate), '--owner-pid', sys.argv[2]]\n"
    "runpy.run_module('omnis.worker', run_name='__main__')\n"
)


def _spawn(
    read_fd: int, *, owner_pid: int, script: str = _GATE_SCRIPT, directory: Path | None = None
) -> subprocess.Popen[str]:
    environment = {"PATH": os.environ.get("PATH", "")}
    if directory is not None:
        environment.update({"OMNIS_HTTP_DIR": str(directory), "OMNIS_HTTP_PORT": "8765"})
    return subprocess.Popen(
        [sys.executable, "-I", "-c", script, str(read_fd), str(owner_pid)],
        pass_fds=(read_fd,),
        cwd=directory,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def _bounded_line(process: subprocess.Popen[str], *, timeout: float = 5) -> str:
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    data = bytearray()
    while len(data) < 64:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "Worker marker exceeded its total deadline"
        readable, _, _ = select.select([process.stdout.fileno()], [], [], remaining)
        assert readable, "Worker marker did not arrive within its total deadline"
        chunk = os.read(process.stdout.fileno(), 1)
        assert chunk, "Worker marker ended without a newline"
        if chunk == b"\n":
            return data.decode("ascii")
        data.extend(chunk)
    raise AssertionError("Worker marker exceeded its byte limit")


def _gate_wait(process: subprocess.Popen[str]) -> None:
    assert _bounded_line(process) == "GATE_WAIT"
    assert process.poll() is None


def _finish(process: subprocess.Popen[str], write_fd: int) -> None:
    os.close(write_fd)
    if process.poll() is None:
        process.kill()  # This unreaped direct child has no recycled numeric PID.
    process.communicate(timeout=5)


def test_worker_does_not_run_until_the_gate_byte_arrives() -> None:
    read_fd, write_fd = os.pipe()
    process = _spawn(read_fd, owner_pid=os.getpid())
    os.close(read_fd)
    try:
        _gate_wait(process)
        assert process.stdout is not None
        assert not select.select([process.stdout], [], [], 0.1)[0]
        os.write(write_fd, b"1")
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert stdout.strip() == "APP_STARTED"
    finally:
        _finish(process, write_fd)


def test_partial_gate_marker_cannot_hold_the_test_indefinitely() -> None:
    code = "import sys, time; sys.stdout.write('GATE'); sys.stdout.flush(); time.sleep(2)"
    read_fd, write_fd = os.pipe()
    process = _spawn(read_fd, owner_pid=os.getpid(), script=code)
    os.close(read_fd)
    try:
        with pytest.raises(AssertionError, match="total deadline"):
            _bounded_line(process, timeout=0.3)
    finally:
        _finish(process, write_fd)


def test_worker_refuses_an_unreleased_gate() -> None:
    read_fd, write_fd = os.pipe()
    process = _spawn(read_fd, owner_pid=os.getpid())
    os.close(read_fd)
    try:
        _gate_wait(process)
        os.close(write_fd)
        write_fd = -1
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 4, stderr
        assert "APP_STARTED" not in stdout
    finally:
        if write_fd >= 0:
            _finish(process, write_fd)
        elif process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


@pytest.mark.parametrize("read_write", [False, True])
def test_worker_rejects_a_named_fifo_as_a_gate(read_write: bool) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        path = Path(name) / "named-gate"
        os.mkfifo(path, 0o600)
        writer_fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        gate_fd = writer_fd if read_write else os.open(path, os.O_RDONLY)
        process = _spawn(gate_fd, owner_pid=os.getpid(), script=_FIFO_SCRIPT)
        try:
            assert _bounded_line(process) == "WORKER_BOOT"
            os.write(writer_fd, b"1")
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 4, stderr
            assert "APP_STARTED" not in stdout
        finally:
            if gate_fd != writer_fd:
                os.close(gate_fd)
            _finish(process, writer_fd)


def test_worker_refuses_a_valid_gate_from_another_parent() -> None:
    read_fd, write_fd = os.pipe()
    process = _spawn(read_fd, owner_pid=os.getpid() + 1)
    os.close(read_fd)
    try:
        os.write(write_fd, b"1")
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 4, stderr
        assert "APP_STARTED" not in stdout
    finally:
        _finish(process, write_fd)


def test_real_module_refuses_a_missing_gate_without_importing_app() -> None:
    code = (
        "import runpy, sys\n"
        "sys.argv = ['omnis.worker', *sys.argv[1:]]\n"
        "try: runpy.run_module('omnis.worker', run_name='__main__')\n"
        "except SystemExit as result: code = result.code\n"
        "print('SERVE_IMPORTED', 'omnis.serve' in sys.modules, flush=True)\n"
        "raise SystemExit(code)\n"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, "--gate-fd", "-1", "--owner-pid", str(os.getpid())],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert process.returncode == 4
    assert process.stdout.strip() == "SERVE_IMPORTED False"


def test_released_worker_serves_real_uds_http() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        read_fd, write_fd = os.pipe()
        process = _spawn(read_fd, owner_pid=os.getpid(), script=_REAL_MODULE, directory=directory)
        os.close(read_fd)
        try:
            path = directory / "api.sock"
            _gate_wait(process)
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                assert process.poll() is None
                assert not path.exists(), "Worker served before release"
                time.sleep(0.02)
            os.write(write_fd, b"1")
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert process.poll() is None
                try:
                    with socket.socket(socket.AF_UNIX) as peer:
                        peer.settimeout(2)
                        peer.connect(str(path))
                        peer.sendall(
                            b"GET /health/live HTTP/1.1\r\n"
                            b"Host: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
                        )
                        response = http.client.HTTPResponse(peer)
                        response.begin()
                        if (response.status, response.read(4096)) == (200, b'{"status":"live"}'):
                            break
                except (OSError, http.client.HTTPException):
                    time.sleep(0.1)
            else:
                raise AssertionError("Released worker did not serve HTTP")
            process.terminate()  # Direct child; PID cannot be recycled before our wait.
            process.communicate(timeout=15)
            assert process.returncode == 0
            assert not path.exists()
        finally:
            _finish(process, write_fd)
