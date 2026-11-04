"""SOURCE: real SDK HTTPX/TLS reused over owned UDS; no INET sockets or provider."""

import asyncio
import importlib
import socket
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from omnis.modules.runs.model_test_contract import ENDPOINTS
from omnis.supervisor.model_relay import Relay, RelayFailure
from omnis.supervisor.model_relay_protocol import Authority, Scope
from omnis.supervisor.model_sender import ModelSender
from test_model_test_v2 import tls_contexts


@pytest.mark.asyncio
async def test_reused_tls_binds_current_serial_and_retired_scope_cannot_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli/src"))
    forwarder = importlib.import_module("omnis_cli.forwarder")
    host_relay = importlib.import_module("omnis_cli.model_relay")
    tasks: set[asyncio.Task[None]] = set()
    requests: list[bytes] = []
    upstream: list[socket.socket] = []
    accepted = 0

    async def peer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal accepted
        accepted += 1
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            while True:
                try:
                    headers = await reader.readuntil(b"\r\n\r\n")
                except asyncio.IncompleteReadError:
                    break
                requests.append(headers)
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{"data":[]}')
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        root.chmod(0o700)
        context, client_context = tls_contexts(root)
        target = root / "upstream.sock"
        server = await asyncio.start_unix_server(peer, target, ssl=context)
        loop = asyncio.get_running_loop()
        original = loop.sock_connect

        def make_socket(family: int, kind: int, protocol: int) -> socket.socket:
            assert (family, kind, protocol) == (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
            )
            result = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.append(result)
            return result

        def dns(host: str, port: int, **kwargs: object) -> list[tuple[object, ...]]:
            assert (host, port) == ("openrouter.ai", 443)
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))]

        async def connect(sock: socket.socket, address: object) -> None:
            assert sock.family == socket.AF_UNIX
            if sock in upstream:
                assert address == ("8.8.8.8", 443)
                await original(sock, str(target))
            else:
                assert isinstance(address, (str, bytes))
                await original(sock, address)

        proxy = SimpleNamespace(**vars(socket))
        proxy.socket, proxy.getaddrinfo = make_socket, dns
        monkeypatch.setattr(host_relay, "socket", proxy)
        monkeypatch.setattr(loop, "sock_connect", connect)
        broker = await forwarder.start_auth_forwarder(root, model=True)
        sender = ModelSender(root / "model-egress.sock", client_context)
        first = Scope(
            str(uuid4()),
            "METADATA_COMMAND",
            str(uuid4()),
            str(uuid4()),
            1,
            1,
            1,
            (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
            "openrouter",
            1,
        )
        current = first

        @asynccontextmanager
        async def guard() -> AsyncIterator[Authority]:
            yield Authority(current, (datetime.now(UTC) + timedelta(seconds=0.4)).isoformat())

        try:
            assert await sender.metadata(ENDPOINTS["openrouter"], "synthetic", guard) == {
                "data": []
            }
            current = replace(first, id=str(uuid4()), operation_serial=2)
            assert await sender.metadata(ENDPOINTS["openrouter"], "synthetic", guard) == {
                "data": []
            }
            relay = sender.transport.backend.relay
            assert await relay.rpc("FENCE", first) == ("OK", b"")
            assert await relay.rpc("DRAIN", first, retire_through=1) == ("OK", b"")
            stale = Relay(root / "model-egress.sock")
            with pytest.raises(RelayFailure):
                await stale.rpc(
                    "OPEN",
                    replace(
                        first, deadline=(datetime.now(UTC) + timedelta(seconds=60)).isoformat()
                    ),
                    str(uuid4()),
                    write_deadline=(datetime.now(UTC) + timedelta(seconds=0.4)).isoformat(),
                )
            assert await sender.metadata(ENDPOINTS["openrouter"], "synthetic", guard) == {
                "data": []
            }
            assert len(requests) == 3 and accepted == len(upstream) == 1
            await sender.drain()
            assert relay.retired_through == 2 and not relay.scopes
        finally:
            await sender.close()
            broker.close()
            await broker.wait_closed()
            server.close()
            await server.wait_closed()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tuple(tasks)), 2)
