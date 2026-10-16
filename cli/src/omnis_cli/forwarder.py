"""Bounded host-loopback transport to one private Omnis API Unix socket."""

import argparse
import asyncio
import ipaddress
import logging
import os
import signal
import socket
import stat
import struct
import sys
import threading
from pathlib import Path
from uuid import UUID

from .instance import private_dir
from .lifecycle import process_identity, read_record, write_record

_MAX_REQUEST_BYTES = 2 * 1024 * 1024
# One trusted asset can be 2 MiB; keep room for headers and successive responses.
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
AuthAddress = tuple[
    int, int, int, str, tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes]
]


class ForwarderListener:
    """Own the listening socket and all accepted client tasks through shutdown."""

    def __init__(
        self,
        server: asyncio.Server,
        clients: set[asyncio.Task[None]],
        closing: asyncio.Event,
        uncertain: asyncio.Event | None = None,
    ) -> None:
        self._server = server
        self._clients = clients
        self._closing = closing
        self._uncertain = uncertain
        self._resolver: threading.Thread | None = None
        self.auth_identity: dict[str, object] | None = None

    @property
    def resolver_alive(self) -> bool:
        return self._resolver is not None and self._resolver.is_alive()

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
        if self.resolver_alive:
            raise ValueError("Auth resolver drainage unverified")
        if self._uncertain is not None and self._uncertain.is_set():
            raise ValueError("Private transport drainage unverified")


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
    uncertain = asyncio.Event()

    async def handle(client: asyncio.StreamReader, browser: asyncio.StreamWriter) -> None:
        nonlocal active
        if closing.is_set():
            browser.transport.abort()
            return
        if active >= 16:
            browser.transport.abort()
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
                        except TimeoutError:
                            uncertain.set()
                            logging.getLogger("omnis.forwarder").warning(
                                "FORWARDER_CLOSE_UNAVAILABLE"
                            )
                        except OSError:
                            pass  # connection_lost completed with an error: transport is closed.
            except asyncio.CancelledError:
                for writer in writers:
                    writer.transport.abort()
                for writer in writers:
                    try:
                        await asyncio.wait_for(asyncio.shield(writer.wait_closed()), timeout=1)
                    except (TimeoutError, asyncio.CancelledError):
                        uncertain.set()
                    except OSError:
                        pass  # Closed with a reset is drained, not a successful response.
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
    return ForwarderListener(listener, clients, closing, uncertain)


def auth_addresses(rows: list[AuthAddress]) -> list[AuthAddress]:
    """Reject the entire answer on any non-global or ambiguous sockaddr."""
    if not rows:
        raise ValueError("Empty auth DNS answer")
    for family, kind, protocol, _canon, address in rows:
        if (
            family not in (socket.AF_INET, socket.AF_INET6)
            or kind != socket.SOCK_STREAM
            or protocol != socket.IPPROTO_TCP
        ):
            raise ValueError("Invalid auth DNS answer")
        if (
            len(address) != (2 if family == socket.AF_INET else 4)
            or address[1] != 443
            or not isinstance(address[0], str)
        ):
            raise ValueError("Invalid auth sockaddr")
        ip = ipaddress.ip_address(address[0])
        try:
            socket.inet_pton(family, address[0])
        except OSError:
            raise ValueError("Auth sockaddr is not numeric") from None
        if (
            ip.version != (4 if family == socket.AF_INET else 6)
            or not ip.is_global
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or isinstance(ip, ipaddress.IPv6Address)
            and (ip.ipv4_mapped is not None or ip.is_site_local or address[2:] != (0, 0))
        ):
            raise ValueError("Non-global auth DNS answer")
    return rows


async def start_auth_forwarder(directory: Path) -> ForwarderListener:
    """Private raw TLS relay; fixed TCB client enforces the OAuth L7 contract.

    No DNS at startup. A cancelled resolver is not killed: its result is revoked,
    its daemon thread remains owned, and drain refuses while it is outstanding.
    """
    private_dir(directory)
    path = directory / "auth-egress.sock"
    if os.path.lexists(path):
        raise ValueError("Auth socket already exists")
    closing, uncertain = asyncio.Event(), asyncio.Event()
    clients: set[asyncio.Task[None]] = set()
    owner: ForwarderListener

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if closing.is_set() or clients or owner.resolver_alive:
            writer.transport.abort()
            return
        task = asyncio.current_task()
        assert task is not None
        clients.add(task)
        upstream: asyncio.StreamWriter | None = None
        raw: socket.socket | None = None
        try:
            peer = writer.get_extra_info("socket")
            if (
                peer is None
                or struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[
                    1
                ]
                != os.getuid()
            ):
                raise ValueError("Wrong auth peer UID")
            async with asyncio.timeout(15):
                result: list[AuthAddress] = []
                done = threading.Event()

                def resolve() -> None:
                    try:
                        result.extend(
                            socket.getaddrinfo(
                                "auth.openai.com",
                                443,
                                type=socket.SOCK_STREAM,
                                proto=socket.IPPROTO_TCP,
                            )
                        )
                    except OSError:
                        pass  # Empty result is a refusal, never fallback.
                    finally:
                        done.set()

                owner._resolver = threading.Thread(
                    target=resolve, daemon=True, name="omnis-auth-dns"
                )
                owner._resolver.start()
                async with asyncio.timeout(2):
                    while not done.is_set():
                        await asyncio.sleep(0.01)
                if closing.is_set():
                    raise ValueError("Auth relay closed")
                family, kind, protocol, _canon, address = auth_addresses(result)[0]
                raw = socket.socket(family, kind, protocol)
                raw.setblocking(False)
                # Numeric sockaddr was validated above: no second lookup/fallback.
                await asyncio.wait_for(asyncio.get_running_loop().sock_connect(raw, address), 2)
                remote, upstream = await asyncio.open_connection(sock=raw)
                raw = None  # Stream owns it now.
                copies = (
                    asyncio.create_task(_copy(reader, upstream, limit=_MAX_REQUEST_BYTES)),
                    asyncio.create_task(_copy(remote, writer, limit=_MAX_REQUEST_BYTES)),
                )
                try:
                    await asyncio.gather(*copies)
                finally:
                    for copy in copies:
                        copy.cancel()
                    await asyncio.gather(*copies, return_exceptions=True)
        except (OSError, ValueError, TimeoutError):
            pass  # No addresses, provider response or challenge in logs.
        finally:
            if raw is not None:
                raw.close()
            for channel in (upstream, writer):
                if channel is not None:
                    channel.transport.abort()
                    try:
                        await asyncio.wait_for(asyncio.shield(channel.wait_closed()), 1)
                    except (TimeoutError, asyncio.CancelledError):
                        uncertain.set()
                    except OSError:
                        pass  # connection_lost with an error still closed.
            clients.discard(task)

    raw_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        raw_listener.bind(str(path))
        path.chmod(0o600)
        raw_listener.listen(1)
        raw_listener.setblocking(False)
        server = await asyncio.start_unix_server(
            handle, sock=raw_listener, start_serving=False, cleanup_socket=False
        )
        owner = ForwarderListener(server, clients, closing, uncertain)
        info = path.lstat()
        owner.auth_identity = {
            "socket": [info.st_dev, info.st_ino],
            "listener": os.fstat(raw_listener.fileno()).st_ino,
        }
        await server.start_serving()
        return owner
    except BaseException:
        raw_listener.close()
        # Path is retained for locked startup cleanup, never stale adoption.
        raise


async def run(
    directory: Path,
    port: int,
    *,
    stop_attempt: str | None = None,
    auth_directory: Path | None = None,
) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("Explicit local port required")
    if stop_attempt is not None and str(UUID(stop_attempt)) != stop_attempt:
        raise ValueError("Invalid Stop attempt")
    listener = await start_forwarder(directory, port=port)
    auth = None
    try:
        if auth_directory is not None:
            if auth_directory != directory.parent / "native-ipc" or stop_attempt is None:
                raise ValueError("Invalid auth directory")
            auth = await start_auth_forwarder(auth_directory)
    except BaseException:
        listener.close()
        await listener.wait_closed()
        raise
    identity = process_identity(os.getpid()) if stop_attempt is not None else None
    inode = os.fstat(listener.sockets[0].fileno()).st_ino
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    try:
        print("FORWARDER_READY", flush=True)
        await stopped.wait()
    finally:
        listener.close()
        if auth is not None:
            auth.close()
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    listener.wait_closed(), *([auth.wait_closed()] if auth is not None else [])
                ),
                timeout=20,
            )
            # A fixed private Stop intent is optional for ordinary startup cleanup.
            # Never publish evidence before listener, copy tasks and transports drain.
            if stop_attempt is not None:
                root = directory.parent
                intent_path = root / f"stop-forwarder-{stop_attempt}.json"
                if os.path.lexists(intent_path):
                    intent = read_record(intent_path)
                    command = intent.get("command_id")
                    if (
                        type(command) is not str
                        or str(UUID(command)) != command
                        or intent
                        != {
                            "version": 2 if auth is not None else 1,
                            "attempt": stop_attempt,
                            "command_id": command,
                            "forwarder": identity,
                            "listener_inode": inode,
                            **({"auth": auth.auth_identity} if auth is not None else {}),
                        }
                    ):
                        raise ValueError("Stop drain identity changed")
                    receipt = {**intent, "drained": True}
                    path = root / f"stop-forwarder-{stop_attempt}-drained.json"
                    write_record(path, receipt)
                    if read_record(path) != receipt:
                        raise ValueError("Stop drain receipt unverified")
        finally:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnis-forwarder")
    parser.add_argument("--socket-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--stop-attempt")
    parser.add_argument("--auth-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        asyncio.run(
            run(
                args.socket_dir,
                args.port,
                stop_attempt=args.stop_attempt,
                auth_directory=args.auth_directory,
            )
        )
    except (OSError, ValueError, TimeoutError):
        print("FORWARDER_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
