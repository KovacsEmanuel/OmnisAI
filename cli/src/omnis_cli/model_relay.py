"""The existing host forwarder's finite model channel; opaque verified TLS only."""

from __future__ import annotations

import asyncio
import hmac
import os
import secrets
import socket
import struct
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .forwarder import AuthAddress, ForwarderListener, auth_addresses
from .instance import private_dir
from .model_relay_protocol import HOSTS, Scope, decode, encode, utc, validate


@dataclass
class Connection:
    scope: Scope
    sequence: int = 0
    address: AuthAddress | None = None
    socket: socket.socket | None = None
    resolver: threading.Thread | None = None
    tasks: set[asyncio.Task[None]] = field(default_factory=set)
    sent: int = 0
    received: int = 0
    closed: bool = False

    def close(self) -> None:
        self.closed = True
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        current = asyncio.current_task()
        for task in tuple(self.tasks):
            if task is not current and not task.cancelling():
                task.cancel()

    def pending(self) -> bool:
        return bool(self.tasks) or self.resolver is not None and self.resolver.is_alive()


async def start_model_forwarder(directory: Path) -> ForwarderListener:
    private_dir(directory)
    path = directory / "model-egress.sock"
    if os.path.lexists(path):
        raise ValueError("Model relay already exists")
    capability = secrets.token_hex(32)
    # New release-owned listener, new capability; an old process cannot use this channel.
    cap_path = directory / "model-relay.cap"
    pending_cap = directory / ("model-relay-cap-" + secrets.token_hex(8))
    fd = os.open(pending_cap, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as cap:
        cap.write(capability)
    os.replace(pending_cap, cap_path)
    closing, uncertain = asyncio.Event(), asyncio.Event()
    clients: set[asyncio.Task[None]] = set()
    connections: dict[str, Connection] = {}
    fenced: set[Scope] = set()
    requests: set[str] = set()
    owner: ForwarderListener

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        if closing.is_set() or len(clients) >= 8:
            writer.transport.abort()
            return
        clients.add(task)
        connection = None
        scope = None
        frame: dict[str, object] | None = None
        status, data = "DENIED", b""
        try:
            peer = writer.get_extra_info("socket")
            if (
                peer is None
                or struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[
                    1
                ]
                != os.getuid()
            ):
                raise ValueError("Wrong model relay UID")
            async with asyncio.timeout(1):
                frame = decode(await reader.readline())
                scope = validate(frame)
                if not hmac.compare_digest(str(frame["capability"]), capability):
                    raise ValueError("Model relay capability denied")
                request = str(frame["request_id"])
                if request in requests or len(requests) >= 16384:
                    raise ValueError("Model relay request replay/limit")
                requests.add(request)
                action, identity = frame["action"], str(frame["connection_id"])
                body = (
                    await reader.readexactly(int(str(frame["size"]))) if action == "WRITE" else b""
                )
            if action in ("FENCE", "DRAIN"):
                if action == "FENCE":
                    if len(fenced) >= 3600 and scope not in fenced:
                        raise ValueError("Model relay scope limit")
                    fenced.add(scope)
                    for item in connections.values():
                        if item.scope == scope:
                            item.close()
                status = "OK" if scope in fenced else "DENIED"
                if action == "DRAIN" and any(
                    item.scope == scope and item.pending() for item in connections.values()
                ):
                    status = "BUSY"
            else:
                now = datetime.now(UTC)
                if scope in fenced or not now < utc(scope.deadline) <= now + timedelta(
                    seconds=3600
                ):
                    raise ValueError("Model relay scope expired/fenced")
                if action == "OPEN":
                    if (
                        identity in connections
                        or len(connections) >= 3600
                        or frame["sequence"] != 0
                    ):
                        raise ValueError("Model relay connection replay/limit")
                    # Only one live stream, including a not-yet-drained DNS resolver.
                    if any(not item.closed or item.pending() for item in connections.values()):
                        raise ValueError("Model relay busy")
                    connection = Connection(scope)
                    connections[identity] = connection
                    connection.tasks.add(task)
                    rows: list[AuthAddress] = []
                    done = threading.Event()

                    def resolve() -> None:
                        try:
                            rows.extend(
                                socket.getaddrinfo(
                                    HOSTS[scope.provider],
                                    443,
                                    type=socket.SOCK_STREAM,
                                    proto=socket.IPPROTO_TCP,
                                )
                            )
                        except OSError:
                            pass  # Empty answer is an ordinary upstream refusal.
                        finally:
                            done.set()

                    connection.resolver = threading.Thread(
                        target=resolve, daemon=True, name="omnis-model-dns"
                    )
                    owner._resolver = connection.resolver
                    connection.resolver.start()
                    async with asyncio.timeout(2):
                        while not done.is_set():
                            await asyncio.sleep(0.01)
                    if not connection.closed and scope not in fenced:
                        if not rows:
                            raise OSError("Model upstream DNS unavailable")
                        connection.address = auth_addresses(rows)[0]
                        status = "OK"
                else:
                    connection = connections.get(identity)
                    if connection is None or connection.closed or connection.tasks:
                        raise ValueError("Model relay connection unavailable")
                    if (
                        connection.scope.instance_id != scope.instance_id
                        or connection.scope.execution_owner_id != scope.execution_owner_id
                        or connection.scope.owner_epoch != scope.owner_epoch
                        or connection.scope.generation != scope.generation
                        or connection.scope.provider != scope.provider
                        or frame["sequence"] != connection.sequence + 1
                    ):
                        raise ValueError("Model relay stale scope/sequence")
                    connection.tasks.add(task)
                    connection.sequence += 1  # Consumed before effect; never resend on lost ACK.
                    connection.scope = scope  # Reused TLS writes use CURRENT operation, not OPEN's.
                    loop = asyncio.get_running_loop()
                    if action == "WRITE":
                        end = utc(frame["write_deadline"])
                        if not now < end <= min(utc(scope.deadline), now + timedelta(seconds=0.5)):
                            raise ValueError("Model relay authority window expired")
                        remaining = (end - now).total_seconds()
                        async with asyncio.timeout(remaining):
                            if connection.socket is None:
                                assert connection.address is not None
                                family, kind, protocol, _canon, address = connection.address
                                connection.socket = socket.socket(family, kind, protocol)
                                connection.socket.setblocking(False)
                                await loop.sock_connect(connection.socket, address)
                            # No queue/copy task survives this bounded write window.
                            if scope in fenced or connection.closed or datetime.now(UTC) >= end:
                                raise ValueError("Model relay fenced before handoff")
                            connection.sent += len(body)
                            if connection.sent > 4 * 1024 * 1024:
                                raise ValueError("Model relay write limit")
                            await loop.sock_sendall(connection.socket, body)
                            if datetime.now(UTC) >= end:
                                raise ValueError("Model relay handoff window uncertain")
                        status = "OK"
                    elif action == "READ":
                        if connection.socket is None:
                            raise ValueError("Model relay has no upstream")
                        async with asyncio.timeout(
                            min(
                                int(str(frame["timeout_ms"])) / 1000,
                                (utc(scope.deadline) - now).total_seconds(),
                            )
                        ):
                            data = await loop.sock_recv(connection.socket, int(str(frame["size"])))
                        connection.received += len(data)
                        if connection.received > 4 * 1024 * 1024:
                            raise ValueError("Model relay read limit")
                        status = "OK"
        except (OSError, TimeoutError):
            status = "UPSTREAM_UNAVAILABLE"
            if connection is not None:
                connection.close()
        except (ValueError, asyncio.IncompleteReadError, asyncio.CancelledError):
            if (
                connection is not None
                and connection.scope == scope
                and frame is not None
                and frame.get("action") == "WRITE"
            ):
                connection.close()
        finally:
            if connection is not None:
                connection.tasks.discard(task)
            try:
                if frame is not None:
                    reply = {
                        k: frame.get(k)
                        for k in ("request_id", "connection_id", "scope", "sequence")
                    }
                    writer.write(
                        encode({"version": 1, **reply, "status": status, "size": len(data)})
                    )
                    writer.write(data)
                    await asyncio.wait_for(writer.drain(), 0.25)
            except (OSError, ValueError, TimeoutError):
                pass  # Sender treats missing ACK as uncertain, never retries the write.
            finally:
                writer.transport.abort()
                clients.discard(task)

    server = await asyncio.start_unix_server(handle, path, limit=4096, cleanup_socket=True)
    path.chmod(0o600)

    class ModelListener(ForwarderListener):
        def close(self) -> None:
            for connection in connections.values():
                connection.close()
            super().close()

        async def wait_closed(self) -> None:
            await super().wait_closed()
            if any(item.pending() for item in connections.values()):
                raise ValueError("Model relay physical drain uncertain")

    owner = ModelListener(server, clients, closing, uncertain)
    return owner
