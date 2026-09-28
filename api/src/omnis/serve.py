"""Serve the P0 API through an owned private Unix socket, never a TCP bind."""

import asyncio
import fcntl
import os
import signal
import socket
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

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


def main() -> int:
    try:
        asyncio.run(serve())
    except (OSError, ValueError):
        print("API_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
