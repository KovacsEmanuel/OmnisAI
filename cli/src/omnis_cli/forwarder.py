"""Bounded host-loopback transport to one private Omnis API Unix socket."""

import argparse
import asyncio
import logging
import os
import signal
import socket
import stat
import struct
import sys
from pathlib import Path

from .instance import private_dir

_MAX_REQUEST_BYTES = 2 * 1024 * 1024
# One trusted asset can be 2 MiB; keep room for headers and successive responses.
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class ForwarderListener:
    """Own the listening socket and all accepted client tasks through shutdown."""

    def __init__(
        self, server: asyncio.Server, clients: set[asyncio.Task[None]], closing: asyncio.Event
    ) -> None:
        self._server = server
        self._clients = clients
        self._closing = closing

    @property
    def sockets(self) -> tuple[socket.socket, ...]:
        return tuple(self._server.sockets or ())

    def close(self) -> None:
        self._closing.set()
        self._server.close()
        for client in tuple(self._clients):
            if not client.cancelling():
                client.cancel()

    async def wait_closed(self) -> None:
        # Let already-accepted callbacks enter their tasks before draining them.
        await asyncio.sleep(0)
        for client in tuple(self._clients):
            if not client.cancelling():
                client.cancel()
        if self._clients:
            _done, pending = await asyncio.wait(self._clients, timeout=5)
            if pending:
                raise TimeoutError("Private clients did not drain")
        await asyncio.wait_for(self._server.wait_closed(), timeout=2)


def private_api_socket(directory: Path) -> Path:
    private_dir(directory)
    path = directory / "api.sock"
    info = path.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise ValueError("Unsafe private API socket")
    return path


async def _copy(
    source: asyncio.StreamReader, destination: asyncio.StreamWriter, *, limit: int
) -> None:
    total = 0
    while True:
        data = await asyncio.wait_for(source.read(65536), timeout=10)
        if not data:
            break
        total += len(data)
        if total > limit:
            raise ValueError("Forwarded stream exceeds limit")
        destination.write(data)
        await asyncio.wait_for(destination.drain(), timeout=2)
    try:
        destination.write_eof()
    except (OSError, NotImplementedError):
        destination.close()


async def start_forwarder(directory: Path, *, port: int) -> ForwarderListener:
    """Bind only IPv4 loopback after validating the one allowed upstream path."""
    upstream_path = private_api_socket(directory)
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Invalid local port")
    active = 0
    clients: set[asyncio.Task[None]] = set()
    closing = asyncio.Event()

    async def handle(client: asyncio.StreamReader, browser: asyncio.StreamWriter) -> None:
        nonlocal active
        if closing.is_set():
            browser.transport.abort()
            return
        if active >= 16:
            browser.close()
            return
        active += 1  # No await before admission; the event loop serializes this counter.
        current = asyncio.current_task()
        assert current is not None  # Server callbacks always run in tasks.
        clients.add(current)
        upstream: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(15):
                server, channel = await asyncio.wait_for(
                    asyncio.open_unix_connection(str(upstream_path)), timeout=2
                )
                upstream = channel
                peer = channel.get_extra_info("socket")
                if peer is None:
                    raise ValueError("Missing private peer")
                credentials = peer.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                )
                _pid, uid, _gid = struct.unpack("3i", credentials)
                if uid != os.getuid():
                    raise ValueError("Wrong private peer UID")
                copies = (
                    asyncio.create_task(_copy(client, channel, limit=_MAX_REQUEST_BYTES)),
                    asyncio.create_task(_copy(server, browser, limit=_MAX_RESPONSE_BYTES)),
                )
                try:
                    await asyncio.gather(*copies)
                finally:
                    for copy in copies:
                        copy.cancel()
                    await asyncio.gather(*copies, return_exceptions=True)
        except (OSError, ValueError, TimeoutError):
            logging.getLogger("omnis.forwarder").warning("FORWARDER_UNAVAILABLE")
        finally:
            writers = tuple(writer for writer in (upstream, browser) if writer is not None)
            try:
                for writer in writers:
                    writer.close()
                for writer in writers:
                    try:
                        await asyncio.wait_for(asyncio.shield(writer.wait_closed()), timeout=2)
                    except (OSError, TimeoutError):
                        writer.transport.abort()
                        try:
                            await asyncio.wait_for(asyncio.shield(writer.wait_closed()), timeout=1)
                        except (OSError, TimeoutError):
                            logging.getLogger("omnis.forwarder").warning(
                                "FORWARDER_CLOSE_UNAVAILABLE"
                            )
            except asyncio.CancelledError:
                for writer in writers:
                    writer.transport.abort()
                raise
            finally:
                active -= 1
                clients.discard(current)

    listener = await asyncio.start_server(
        handle,
        host="127.0.0.1",
        port=port,
        family=socket.AF_INET,
        backlog=16,
        limit=65536,
        reuse_address=False,
        start_serving=False,
    )
    try:
        await listener.start_serving()
    except BaseException:
        listener.close()
        await listener.wait_closed()
        raise
    return ForwarderListener(listener, clients, closing)


async def run(directory: Path, port: int) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("Explicit local port required")
    listener = await start_forwarder(directory, port=port)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    try:
        print("FORWARDER_READY", flush=True)
        await stopped.wait()
    finally:
        listener.close()
        try:
            await asyncio.wait_for(listener.wait_closed(), timeout=20)
        finally:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnis-forwarder")
    parser.add_argument("--socket-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(args.socket_dir, args.port))
    except (OSError, ValueError, TimeoutError):
        print("FORWARDER_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
