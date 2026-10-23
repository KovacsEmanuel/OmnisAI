"""Scope isolation on the actual broker; opaque bytes to owned TCP, not SDK/TLS evidence."""

import asyncio
import importlib
import os
import socket
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.supervisor.model_relay import Relay, RelayFailure
from omnis.supervisor.model_relay_protocol import Scope, decode, encode


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["empty", "error", "nonglobal", "malformed"])
async def test_dns_failure_closes_open_and_allows_explicit_new_attempt(
    monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli/src"))
    forwarder = importlib.import_module("omnis_cli.forwarder")
    calls = 0
    connects: list[object] = []
    original_connect = asyncio.get_running_loop().sock_connect

    async def owned_connect(sock: socket.socket, target: str | tuple[object, ...]) -> None:
        if sock.family == socket.AF_UNIX:
            await original_connect(sock, target)
        else:
            assert target == ("8.8.8.8", 443)
            connects.append(target)  # Mock readiness; never connect to this DNS placeholder.

    def dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            if answer == "empty":
                return []
            if answer == "error":
                raise socket.gaierror("owned DNS failure")
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("127.0.0.1" if answer == "nonglobal" else "invalid", 443),
                )
            ]
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", owned_connect)
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        root = Path(name)
        root.chmod(0o700)
        broker = await forwarder.start_auth_forwarder(root, model=True)
        relay = Relay(root / "model-egress.sock")
        scope = Scope(
            str(uuid4()),
            "METADATA_COMMAND",
            str(uuid4()),
            str(uuid4()),
            1,
            1,
            1,
            (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
            "openrouter",
        )

        async def opening() -> tuple[str, bytes]:
            return await relay.rpc(
                "OPEN",
                scope,
                str(uuid4()),
                write_deadline=(datetime.now(UTC) + timedelta(seconds=0.4)).isoformat(),
            )

        try:
            if answer in {"empty", "error"}:
                assert await opening() == ("UPSTREAM_UNAVAILABLE", b"")
                assert not relay.failed
                assert calls == 1  # No implicit retry after an upstream failure.
                assert await opening() == ("OK", b"")
                assert calls == 2
                assert connects == [("8.8.8.8", 443)]
            else:
                with pytest.raises(RelayFailure):
                    await opening()
                assert relay.failed
                assert calls == 1
            await relay.rpc("FENCE", scope)
            assert await relay.rpc("DRAIN", scope) == ("OK", b"")
        finally:
            broker.close()
            await broker.wait_closed()


@pytest.mark.asyncio
async def test_stale_fence_owner_cancel_and_duplicate_write_do_not_cross_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli/src"))
    forwarder = importlib.import_module("omnis_cli.forwarder")
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        root = Path(name)
        root.chmod(0o700)
        received = bytearray()
        peer_done = asyncio.Event()

        async def peer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                while data := await reader.read(65536):
                    received.extend(data)
            finally:
                writer.close()
                await writer.wait_closed()
                peer_done.set()

        server = await asyncio.start_server(peer, "127.0.0.1", 0)
        address = server.sockets[0].getsockname()
        original = asyncio.get_running_loop().sock_connect

        async def connect(sock: socket.socket, target: str | tuple[object, ...]) -> None:
            if sock.family == socket.AF_UNIX:
                await original(sock, target)
            else:
                assert target == ("8.8.8.8", 443)
                await original(sock, address)

        def dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))]

        monkeypatch.setattr(socket, "getaddrinfo", dns)
        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        broker = await forwarder.start_auth_forwarder(root, model=True)
        identity = str(uuid4())
        scope = Scope(
            str(uuid4()),
            "MODEL_DISPATCH",
            str(uuid4()),
            str(uuid4()),
            1,
            1,
            1,
            (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
            "openrouter",
        ).wire()

        async def rpc(
            action: str, current: dict[str, object], seq: int = 0, data: bytes = b""
        ) -> str:
            reader, writer = await asyncio.open_unix_connection(root / "model-egress.sock")
            try:
                value: dict[str, object] = {
                    "version": 1,
                    "action": action,
                    "request_id": str(uuid4()),
                    "connection_id": None if action in {"FENCE", "DRAIN"} else identity,
                    "scope": current,
                    "sequence": seq,
                    "size": len(data),
                    "timeout_ms": 1000,
                    "write_deadline": (datetime.now(UTC) + timedelta(seconds=0.4)).isoformat()
                    if action in ("OPEN", "WRITE")
                    else None,
                    "capability": (root / "model-relay.cap").read_text(),
                }
                writer.write(encode(value) + data)
                await writer.drain()
                reply = decode(await asyncio.wait_for(reader.readline(), 2))
                assert reply["scope"] == current and reply["sequence"] == seq
                return str(reply["status"])
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            assert await rpc("OPEN", scope) == "OK"
            assert await rpc("WRITE", scope, 1, b"a") == "OK"
            newer = {**scope, "id": str(uuid4())}
            assert await rpc("WRITE", newer, 2, b"b") == "OK"
            assert await rpc("FENCE", scope) == "OK"
            assert await rpc("DRAIN", scope) == "OK"
            assert await rpc("WRITE", scope, 3, b"denied-old-op") == "DENIED"
            assert (
                await rpc(
                    "WRITE", {**newer, "execution_owner_id": str(uuid4())}, 3, b"denied-owner"
                )
                == "DENIED"
            )
            assert await rpc("FENCE", {**newer, "cancel_epoch": 2}) == "OK"
            assert await rpc("WRITE", newer, 3, b"c") == "OK"
            assert await rpc("WRITE", newer, 3, b"duplicate") == "DENIED"
            assert await rpc("FENCE", newer) == "OK"
            assert await rpc("DRAIN", newer) == "OK"
            await asyncio.wait_for(peer_done.wait(), 2)
            assert received == b"abc"
        finally:
            broker.close()
            await broker.wait_closed()
            server.close()
            await server.wait_closed()
