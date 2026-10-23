"""ACKed opaque ciphertext channel used by the public AnyIO TLS transport."""

import asyncio
import os
import socket
import stat
import struct
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpcore
from anyio import EndOfStream
from anyio.abc import ByteStream

from omnis.supervisor.model_relay_protocol import (
    MAX_INT,
    Authority,
    Scope,
    decode,
    encode,
    integer,
    utc,
)


class RelayFailure(RuntimeError):
    pass


class Relay:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.capability: str | None = None
        self.identity: tuple[int, int] | None = None
        self.scopes: set[Scope] = set()
        self.failed = False

    async def rpc(
        self,
        action: str,
        scope: Scope,
        connection: str | None = None,
        sequence: int = 0,
        data: bytes = b"",
        size: int = 0,
        timeout: float = 1,
        write_deadline: str | None = None,
    ) -> tuple[str, bytes]:
        writer: asyncio.StreamWriter | None = None
        self.scopes.add(scope)
        try:
            info = self.path.lstat()
            parent = self.path.parent.stat()
            if (
                not stat.S_ISSOCK(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or parent.st_uid != os.getuid()
                or stat.S_IMODE(parent.st_mode) != 0o700
            ):
                raise RelayFailure("RELAY_BINDING_UNAVAILABLE")
            identity = info.st_dev, info.st_ino
            if self.identity is None:
                cap_path = self.path.parent / "model-relay.cap"
                fd = os.open(cap_path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd) as cap:
                    meta = os.fstat(cap.fileno())
                    if (
                        not stat.S_ISREG(meta.st_mode)
                        or meta.st_uid != os.getuid()
                        or stat.S_IMODE(meta.st_mode) != 0o600
                    ):
                        raise RelayFailure("RELAY_CAPABILITY_UNAVAILABLE")
                    self.capability = cap.read(65)
                self.identity = identity
            if self.identity != identity:
                raise RelayFailure("RELAY_BINDING_CHANGED")
            request: dict[str, object] = {
                "version": 1,
                "action": action,
                "request_id": str(uuid4()),
                "connection_id": connection,
                "scope": scope.wire(),
                "sequence": sequence,
                "size": len(data) if action == "WRITE" else size,
                "timeout_ms": max(1, min(300000, int(timeout * 1000))),
                "write_deadline": write_deadline,
                "capability": self.capability,
            }
            async with asyncio.timeout(timeout + 0.25):
                reader, writer = await asyncio.open_unix_connection(self.path, limit=4096)
                peer = writer.get_extra_info("socket")
                if (
                    peer is None
                    or struct.unpack(
                        "3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                    )[1]
                    != os.getuid()
                ):
                    raise RelayFailure("RELAY_UID_CHANGED")
                writer.write(encode(request))
                writer.write(data)
                await writer.drain()
                reply = decode(await reader.readline())
                if set(reply) != {
                    "version",
                    "request_id",
                    "connection_id",
                    "scope",
                    "sequence",
                    "status",
                    "size",
                }:
                    raise RelayFailure("RELAY_ACK_INVALID")
                integer(reply["version"], 1, 1)
                integer(reply["sequence"], 0, MAX_INT)
                Scope.parse(reply["scope"])
                if any(
                    reply[k] != request[k]
                    for k in ("version", "request_id", "connection_id", "scope", "sequence")
                ):
                    raise RelayFailure("RELAY_ACK_STALE")
                length = reply["size"]
                status = reply["status"]
                if (
                    type(length) is not int
                    or not 0 <= length <= (size if action == "READ" else 0)
                    or status not in ("OK", "BUSY", "DENIED", "UPSTREAM_UNAVAILABLE")
                ):
                    raise RelayFailure("RELAY_ACK_INVALID")
                payload = await reader.readexactly(length)
                if not isinstance(status, str):
                    raise RelayFailure("RELAY_ACK_INVALID")
                if status == "DENIED":
                    raise RelayFailure("RELAY_AUTHORITY_DENIED")
                return status, payload
        except (OSError, ValueError, TimeoutError, asyncio.IncompleteReadError, RelayFailure):
            self.failed = True
            raise RelayFailure("RELAY_CONTROL_UNCERTAIN") from None
        finally:
            if writer is not None:
                writer.transport.abort()

    async def drain(self) -> None:
        async with asyncio.timeout(1.5):
            for scope in tuple(self.scopes):
                status, _ = await self.rpc("FENCE", scope)
                if status != "OK":
                    raise RelayFailure("RELAY_FENCE_UNCERTAIN")
            for scope in tuple(self.scopes):
                while True:
                    status, _ = await self.rpc("DRAIN", scope)
                    if status == "OK":
                        break
                    if status != "BUSY":
                        self.failed = True
                        raise RelayFailure("RELAY_DRAIN_UNCERTAIN")
                    await asyncio.sleep(0.01)
        if self.failed:
            raise RelayFailure("RELAY_CONTROL_UNCERTAIN")
        self.scopes.clear()


class CipherStream(ByteStream):
    def __init__(
        self,
        relay: Relay,
        identity: str,
        scope: Scope,
        guard: Callable[[], AbstractAsyncContextManager[Authority]],
    ) -> None:
        self.relay, self.identity, self.scope = relay, identity, scope
        self.guard = guard
        self.sequence = 0

    async def send(self, item: bytes) -> None:
        # Guard callback resolves CURRENT, including when this TLS stream is reused.
        for start in range(0, len(item), 65536):
            async with self.guard() as authority:
                self.scope = authority.scope
                self.sequence += 1
                try:
                    status, _ = await self.relay.rpc(
                        "WRITE",
                        self.scope,
                        self.identity,
                        self.sequence,
                        data=item[start : start + 65536],
                        timeout=0.5,
                        write_deadline=authority.write_deadline,
                    )
                except (RelayFailure, asyncio.CancelledError):
                    # Never unlock SQL while an unacknowledged host write could still be admitted.
                    delay = max(
                        0, (utc(authority.write_deadline) - datetime.now(UTC)).total_seconds()
                    )
                    await asyncio.shield(asyncio.sleep(min(delay, 0.5)))
                    raise
                if status != "OK":
                    raise httpcore.WriteError("UPSTREAM_UNAVAILABLE")

    async def receive(self, max_bytes: int = 65536) -> bytes:
        self.sequence += 1
        status, data = await self.relay.rpc(
            "READ",
            self.scope,
            self.identity,
            self.sequence,
            size=min(max_bytes, 65536),
            timeout=15,
        )
        if status != "OK":
            raise httpcore.ReadError("UPSTREAM_UNAVAILABLE")
        if not data:
            raise EndOfStream
        return data

    async def send_eof(self) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        # Closing a local SDK pool is not physical quiescence; require the broker ACK.
        await self.relay.rpc("FENCE", self.scope)
        if (await self.relay.rpc("DRAIN", self.scope))[0] != "OK":
            raise RelayFailure("RELAY_DRAIN_UNCERTAIN")
