"""Serve the P0 API through an owned private Unix socket, never a TCP bind."""

import asyncio
import fcntl
import os
import signal
import socket
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

import uvicorn

from omnis.core.paths import (
    check_private_file,
    private_directory,
    remove_stale_socket,
    unlink_owned_inode,
)


@contextmanager
def private_http_listener(directory: Path) -> Iterator[socket.socket]:
    private_directory(directory)
    lock_fd = os.open(directory / "api.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        check_private_file(os.fstat(lock_fd))
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = directory / "api.sock"
        remove_stale_socket(path)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        inode: int | None = None
        try:
            listener.bind(str(path))
            inode = path.lstat().st_ino
            path.chmod(0o600)
            listener.listen(16)
            yield listener
        finally:
            listener.close()
            unlink_owned_inode(path, inode)
    finally:
        os.close(lock_fd)


def server_config() -> uvicorn.Config:
    return uvicorn.Config(
        "omnis.api:create_app",
        factory=True,
        proxy_headers=False,
        access_log=False,
        lifespan="on",
        timeout_keep_alive=5,
        timeout_graceful_shutdown=5,
        limit_concurrency=128,
    )


class PrivateServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        # The outer owner starts its shutdown deadline at the FIRST signal.
        yield


async def serve() -> None:
    raw_directory = os.environ.get("OMNIS_HTTP_DIR")
    if not raw_directory:
        raise ValueError("Explicit private HTTP directory required")
    with private_http_listener(Path(raw_directory)) as listener:
        config = server_config()
        server = PrivateServer(config)
        loop = asyncio.get_running_loop()
        stopped = asyncio.Event()

        def request_stop() -> None:
            server.should_exit = True
            stopped.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, request_stop)
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        notified = asyncio.create_task(stopped.wait())
        try:
            done, _pending = await asyncio.wait(
                {serving, notified}, return_when=asyncio.FIRST_COMPLETED
            )
            if notified in done and serving not in done:
                done, _pending = await asyncio.wait({serving}, timeout=8)
                if serving not in done:
                    serving.cancel()
                    done, _pending = await asyncio.wait({serving}, timeout=2)
                    if serving not in done:
                        os._exit(4)  # Own process only; next explicit start reconciles stale UDS.
                    try:
                        await serving
                    except asyncio.CancelledError:
                        pass
                    raise ValueError("API shutdown deadline exceeded")
            await serving
        finally:
            notified.cancel()
            await asyncio.gather(notified, return_exceptions=True)
            if not serving.done():
                serving.cancel()
                done, _pending = await asyncio.wait({serving}, timeout=2)
                if serving not in done:
                    os._exit(4)
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)


def _child_main() -> int:
    try:
        asyncio.run(serve())
    except (OSError, ValueError):
        print("API_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


@dataclass
class _StopRequest:
    at: float | None = None
    signum: int | None = None


def main() -> int:
    """Own a separate API process so a blocked event loop cannot stall SIGTERM."""
    child_pid: int | None = None
    child_pidfd: int | None = None
    stop = _StopRequest()

    def request_stop(signum: int, _frame: FrameType | None) -> None:
        if stop.at is None:
            stop.at = time.monotonic()
            stop.signum = signum
        if child_pidfd is not None:
            try:
                signal.pidfd_send_signal(child_pidfd, signum)
            except ProcessLookupError:
                pass
        elif child_pid is not None and child_pid > 0:
            # This child has not been reaped; its numeric PID cannot be reused yet.
            try:
                os.kill(child_pid, signum)
            except ProcessLookupError:
                pass

    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for sig in previous:
            signal.signal(sig, request_stop)
        try:
            child_pid = os.fork()
        except OSError:
            print("API_UNAVAILABLE", file=sys.stderr)
            return 3
        if child_pid == 0:
            for sig in previous:
                signal.signal(sig, signal.SIG_DFL)
            try:
                code = 4 if stop.at is not None else _child_main()
            except BaseException:
                print("API_UNAVAILABLE", file=sys.stderr, flush=True)
                code = 3
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)

        try:
            child_pidfd = os.pidfd_open(child_pid)
        except OSError:
            # Never keep serving without a stable identity for shutdown signals.
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            reap_deadline = time.monotonic() + 2
            while time.monotonic() < reap_deadline:
                reaped, _status = os.waitpid(child_pid, os.WNOHANG)
                if reaped == child_pid:
                    break
                time.sleep(0.05)
            return 4

        if stop.signum is not None:
            request_stop(stop.signum, None)
        while True:
            reaped, status = os.waitpid(child_pid, os.WNOHANG)
            if reaped == child_pid:
                code = os.waitstatus_to_exitcode(status)
                if stop.at is not None:
                    return 0 if code == 0 else 4
                return code if code in {0, 2, 3, 4} else 3
            if stop.at is not None and time.monotonic() - stop.at >= 10:
                try:
                    signal.pidfd_send_signal(child_pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                reap_deadline = time.monotonic() + 2
                while time.monotonic() < reap_deadline:
                    reaped, _status = os.waitpid(child_pid, os.WNOHANG)
                    if reaped == child_pid:
                        break
                    time.sleep(0.05)
                return 4
            time.sleep(0.05)
    finally:
        if child_pid != 0:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            if child_pidfd is not None:
                os.close(child_pidfd)


if __name__ == "__main__":
    raise SystemExit(main())
