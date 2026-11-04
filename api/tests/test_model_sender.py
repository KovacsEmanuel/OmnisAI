import asyncio
import gzip
import json
import os
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpcore
import httpx
import pytest

from omnis.modules.runs.model_test_contract import ACK, ENDPOINTS, Projection
from omnis.supervisor.model_relay import RelayFailure
from omnis.supervisor.model_relay_protocol import Authority, Scope
from omnis.supervisor.model_sender import ModelSender, ResponseStream, SendDenied


@asynccontextmanager
async def guard() -> AsyncIterator[Authority]:
    now = datetime.now(UTC)
    yield Authority(
        Scope(
            str(uuid4()),
            "METADATA_COMMAND",
            str(uuid4()),
            str(uuid4()),
            1,
            1,
            1,
            (now + timedelta(seconds=15)).isoformat(),
            "openrouter",
            1,
        ),
        (now + timedelta(seconds=0.4)).isoformat(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        pytest.param("eof", id="eof"),
        pytest.param("cert", id="cert"),
        pytest.param("network", id="network"),
        pytest.param("timeout", id="timeout"),
        pytest.param("broken", id="broken"),
        pytest.param("write", id="write"),
        pytest.param("cancel", id="cancel"),
        pytest.param("relay", id="relay"),
        pytest.param("control", id="control"),
    ],
)
async def test_tls_wrap_failure_closes_raw_and_preserves_control(
    monkeypatch: pytest.MonkeyPatch, error: str
) -> None:
    from unittest.mock import AsyncMock, Mock

    from anyio import BrokenResourceError, EndOfStream
    from anyio.abc import ByteStream
    from anyio.streams.tls import TLSStream

    from omnis.supervisor.model_sender import Stream

    faults: dict[str, BaseException] = {
        "eof": EndOfStream(),
        "cert": ssl.SSLCertVerificationError("fixture certificate"),
        "network": ConnectionResetError("fixture reset"),
        "timeout": TimeoutError("fixture deadline"),
        "broken": BrokenResourceError(),
        "write": httpcore.WriteError("fixture write"),
        "cancel": asyncio.CancelledError(),
        "relay": RelayFailure("fixture relay uncertainty"),
        "control": RuntimeError("fixture DB/control uncertainty"),
    }
    raw = Mock(spec=ByteStream)
    raw.aclose = AsyncMock()
    fault = faults[error]
    monkeypatch.setattr(TLSStream, "wrap", AsyncMock(side_effect=fault))
    expected = type(fault) if error in {"cancel", "relay", "control"} else httpcore.ConnectError
    with pytest.raises(expected) as caught:
        await Stream(raw).start_tls(ssl.create_default_context(), "openrouter.ai", 1)
    raw.aclose.assert_awaited_once()
    if error in {"cancel", "relay", "control"}:
        assert caught.value is fault


@pytest.mark.asyncio
async def test_tls_cleanup_failure_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, Mock

    from anyio import EndOfStream
    from anyio.abc import ByteStream
    from anyio.streams.tls import TLSStream

    from omnis.supervisor.model_sender import Stream

    raw = Mock(spec=ByteStream)
    raw.aclose = AsyncMock(side_effect=RelayFailure("RELAY_DRAIN_UNCERTAIN"))
    monkeypatch.setattr(TLSStream, "wrap", AsyncMock(side_effect=EndOfStream()))
    with pytest.raises(RelayFailure, match="^RELAY_DRAIN_UNCERTAIN$"):
        await Stream(raw).start_tls(ssl.create_default_context(), "openrouter.ai", 1)
    raw.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_tls_handshake_cut_allows_explicit_healthy_metadata_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import os
    import socket
    import sys
    import tempfile
    from dataclasses import replace

    from test_model_test_v2 import tls_contexts

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli/src"))
    forwarder = importlib.import_module("omnis_cli.forwarder")
    tasks: set[asyncio.Task[None]] = set()
    connected: list[object] = []
    requests: list[bytes] = []

    async def peer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            if writer.get_extra_info("ssl_object") is None:
                assert await reader.read(65536)  # Cut the actual ClientHello handshake.
                return
            requests.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
            await writer.drain()
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        root = Path(name)
        root.chmod(0o700)
        server_context, client_context = tls_contexts(root)
        cut = await asyncio.start_server(peer, "127.0.0.1", 0)
        healthy = await asyncio.start_server(peer, "127.0.0.1", 0, ssl=server_context)
        original = asyncio.get_running_loop().sock_connect

        async def connect(sock: socket.socket, target: str | tuple[object, ...]) -> None:
            if sock.family == socket.AF_UNIX:
                await original(sock, target)
            else:
                assert target == ("8.8.8.8", 443)
                server = cut if not connected else healthy
                address = server.sockets[0].getsockname()
                connected.append(address)
                await original(sock, address)

        def dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))]

        monkeypatch.setattr(socket, "getaddrinfo", dns)
        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        broker = await forwarder.start_auth_forwarder(root, model=True)
        sender = ModelSender(root / "model-egress.sock", client_context)
        async with guard() as authority:
            scope = authority.scope

        @asynccontextmanager
        async def current_guard() -> AsyncIterator[Authority]:
            yield Authority(scope, (datetime.now(UTC) + timedelta(seconds=0.4)).isoformat())

        try:
            with pytest.raises(SendDenied, match="^METADATA_UNAVAILABLE$"):
                await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", current_guard)
            assert len(connected) == 1 and not requests  # No implicit second handshake.
            relay = sender.transport.backend.relay
            assert not relay.failed
            assert await relay.rpc("DRAIN", scope) == ("OK", b"")
            scope = replace(scope, id=str(uuid4()), operation_serial=scope.operation_serial + 1)
            assert (
                await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", current_guard)
                == {}
            )
            assert len(connected) == 2 and len(requests) == 1
            assert requests[0].startswith(b"GET /api/v1/models HTTP/1.1\r\n")
            await sender.drain()
        finally:
            await sender.close()
            broker.close()
            await broker.wait_closed()
            for server in (cut, healthy):
                server.close()
                await server.wait_closed()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tuple(tasks)), 2)


@pytest.mark.asyncio
async def test_missing_broker_is_control_failure_not_provider_outage(ipc_directory: Path) -> None:
    path = ipc_directory / "missing"
    assert len(os.fsencode(path)) < 108 and not path.exists()
    sender = ModelSender(path)
    try:
        with pytest.raises(RelayFailure, match="^RELAY_CONTROL_UNCERTAIN$"):
            await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        with pytest.raises(RelayFailure, match="^RELAY_CONTROL_UNCERTAIN$"):
            await sender.send(
                ENDPOINTS["openrouter"],
                "fixture-secret",
                Projection(model="fixture/model", output_tokens=64),
                guard,
            )
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [httpcore.ReadError, httpcore.RemoteProtocolError, httpcore.ReadTimeout]
)
async def test_streaming_outage_is_sanitized(error: type[Exception]) -> None:
    async def broken() -> AsyncIterator[bytes]:
        yield b"{"
        raise error("private diagnostic must not escape")

    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, stream=ResponseStream(httpcore.Response(200, content=broken()), 131072)
            )
        )
    )
    try:
        with pytest.raises(SendDenied, match="^METADATA_UNAVAILABLE$"):
            await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            "fixture-secret",
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        assert reply.result_state == "UNKNOWN" and reply.reason == "RESULT_UNKNOWN"
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,size,error",
    [
        ([(b"Content-Encoding", b"gzip")], 3000000, "ENCODED_RESPONSE_DENIED"),
        ([(b"content-encoding", b"gzip")], 3000000, "ENCODED_RESPONSE_DENIED"),
        ([(b"CONTENT-ENCODING", b"GZIP")], 3000000, "ENCODED_RESPONSE_DENIED"),
        (
            [(b"Content-Encoding", b"gzip"), (b"content-encoding", b"identity")],
            3000000,
            "ENCODED_RESPONSE_DENIED",
        ),
        (
            [(b"content-encoding", b"gzip"), (b"Content-Encoding", b"identity")],
            3000000,
            "ENCODED_RESPONSE_DENIED",
        ),
        ([(b"Content-Encoding", b"Identity")], 128, None),
        ([], 2097152, None),
        ([(b"Content-Encoding", b"identity")], 2097153, "RESPONSE_LIMIT"),
    ],
)
async def test_metadata_page_encoding_and_size_at_real_httpx_boundary(
    monkeypatch: pytest.MonkeyPatch,
    headers: list[tuple[bytes, bytes]],
    size: int,
    error: str | None,
) -> None:
    from unittest.mock import AsyncMock

    from omnis.modules.settings.provider_catalog import CatalogIngest

    raw = b'{"data":[{"id":"exact"}],"total_count":1}'
    raw += b" " * (size - len(raw))
    wire = gzip.compress(raw, mtime=0) if error == "ENCODED_RESPONSE_DENIED" else raw
    if error == "ENCODED_RESPONSE_DENIED":
        assert len(wire) < 2097152 < len(raw) == 3000000

    class Body:
        closed = False
        read = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            self.read = True
            yield wire

        async def aclose(self) -> None:
            self.closed = True

    body = Body()

    async def reply(request: httpcore.Request) -> httpcore.Response:
        assert request.method == b"GET"
        assert request.url.target == b"/api/v1/models?offset=0&limit=1000"
        assert httpx.Headers(request.headers)["accept-encoding"] == "identity"
        return httpcore.Response(200, headers=headers, content=body)

    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    monkeypatch.setattr(sender.transport.pool, "handle_async_request", reply)
    monkeypatch.setattr(
        sender.transport.backend, "connect_tcp", AsyncMock(side_effect=AssertionError("NO_IO"))
    )
    try:
        if error is not None:
            with pytest.raises(SendDenied, match=f"^{error}$"):
                await sender.metadata_page(ENDPOINTS["openrouter"], "fixture-secret", guard, 0)
        else:
            value, received = await sender.metadata_page(
                ENDPOINTS["openrouter"], "fixture-secret", guard, 0
            )
            assert received == len(raw) == size
            ingest = CatalogIngest("openrouter")
            assert ingest.add(value) is None and ingest.complete
            assert list(ingest.entries) == ["exact"]
        assert body.closed and body.read == (error != "ENCODED_RESPONSE_DENIED")
    finally:
        await sender.close()


@pytest.mark.asyncio
async def test_metadata_does_not_swallow_control_failures_or_cancellation() -> None:
    sender = ModelSender(Path("/nonexistent-owned-fixture"))

    async def fail(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("control failure")

    await sender.http.aclose()
    sender.http = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    try:
        with pytest.raises(RuntimeError, match="control failure"):
            await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        task = asyncio.create_task(
            sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        )
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("length,offset", [(512, 0), (31, 250)])
async def test_redacts_before_bounding_response_identifiers(length: int, offset: int) -> None:
    secret = "canary-" + "Z" * (length - 7)
    echoed = "x" * offset + secret
    payload = {
        "id": echoed,
        "model": echoed,
        "object": "chat.completion",
        "created": 0,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": ACK}, "finish_reason": "stop"}
        ],
    }
    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(payload))
        )
    )
    try:
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            secret,
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        leaked = any(secret[:6] in (value or "") for value in (reply.model, reply.response_id))
        assert not leaked
        assert reply.result_state == "COMPLETED"
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("component", ["prompt_tokens", "completion_tokens", "reasoning_tokens"])
@pytest.mark.parametrize("value", [-1, 9007199254740992, True, "9", 1.5])
async def test_original_usage_is_not_coerced(component: str, value: object) -> None:
    usage = {
        "prompt_tokens": 9,
        "completion_tokens": 7,
        "total_tokens": 16,
        "completion_tokens_details": {"reasoning_tokens": 2},
    }
    if component == "reasoning_tokens":
        usage["completion_tokens_details"] = {"reasoning_tokens": value}
    else:
        usage[component] = value
    payload = {
        "id": "fixture",
        "model": "fixture/model",
        "object": "chat.completion",
        "created": 0,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": ACK}, "finish_reason": "stop"}
        ],
        "usage": usage,
    }
    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(payload))
        )
    )
    try:
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            "fixture-secret",
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        assert reply.result_state == "COMPLETED"
        assert (
            getattr(
                reply,
                {
                    "prompt_tokens": "input_tokens",
                    "completion_tokens": "output_tokens",
                    "reasoning_tokens": "reasoning_tokens",
                }[component],
            )
            is None
        )
        assert reply.reason == "USAGE_INVALID"
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["healthy", "veto", "connect_expiry", "backpressure", "partial", "closed"]
)
async def test_sdk_tcp_readiness_outside_guard_and_current_write_veto(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """SOURCE lock-double, public SDK and actual broker/owned TLS; not SQL proof."""
    import importlib
    import os
    import socket
    import sys
    import tempfile

    from test_model_test_v2 import tls_contexts

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli/src"))
    forwarder = importlib.import_module("omnis_cli.forwarder")
    admission = asyncio.Lock()
    guards = 0
    connect_under_guard: list[bool] = []
    async_writes: list[int] = []
    requests: list[bytes] = []
    tasks: set[asyncio.Task[None]] = set()
    upstream: list[socket.socket] = []
    handoffs: list[bool] = []
    async with guard() as authority:
        scope = authority.scope

    @asynccontextmanager
    async def current_guard() -> AsyncIterator[Authority]:
        nonlocal guards
        async with admission:
            guards += 1
            if mode == "veto" and connect_under_guard:
                raise SendDenied("SOURCE_STOP_OR_REVOKE")
            yield Authority(scope, (datetime.now(UTC) + timedelta(seconds=0.4)).isoformat())

    async def peer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            requests.append(await reader.readexactly(length))
            body = json.dumps(
                {
                    "id": "source-owned",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "fixture/model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": ACK},
                            "finish_reason": "stop",
                        }
                    ],
                }
            ).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\n\r\n"
                + body
            )
            await writer.drain()
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        root = Path(name)
        root.chmod(0o700)
        server_context, client_context = tls_contexts(root)
        server = await asyncio.start_server(peer, "127.0.0.1", 0, ssl=server_context)
        address = server.sockets[0].getsockname()
        loop = asyncio.get_running_loop()
        original_connect, original_send = loop.sock_connect, loop.sock_sendall

        async def connect(sock: socket.socket, target: str | tuple[object, ...]) -> None:
            if sock.family == socket.AF_UNIX:
                await original_connect(sock, target)
            else:
                assert target == ("8.8.8.8", 443)
                connect_under_guard.append(admission.locked())
                upstream.append(sock)
                if mode == "connect_expiry":
                    await asyncio.sleep(1)
                await asyncio.sleep(0.02)  # Actual readiness wait must not own admission.
                await original_connect(sock, address)

        async def send(sock: socket.socket, data: bytes) -> None:
            if sock.family != socket.AF_UNIX:
                async_writes.append(len(data))
            await original_send(sock, data)

        def dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))]

        monkeypatch.setattr(socket, "getaddrinfo", dns)
        monkeypatch.setattr(loop, "sock_connect", connect)
        monkeypatch.setattr(loop, "sock_sendall", send)
        original_handoff = socket.socket.send

        def handoff(sock: socket.socket, data: bytes, flags: int = 0) -> int:
            if any(sock is item for item in upstream):
                handoffs.append(admission.locked())
                if mode == "backpressure":
                    raise BlockingIOError("owned full send buffer")
                if mode == "closed":
                    raise BrokenPipeError("owned closed peer")
                if mode == "partial":
                    return original_handoff(sock, data[:1], flags)
            return original_handoff(sock, data, flags)

        monkeypatch.setattr(socket.socket, "send", handoff)
        broker = await forwarder.start_auth_forwarder(root, model=True)
        sender = ModelSender(root / "model-egress.sock", client_context)
        try:
            reply = await sender.send(
                ENDPOINTS["openrouter"],
                "source-secret",
                Projection(model="fixture/model", output_tokens=64),
                current_guard,
            )
            assert connect_under_guard == [False]
            assert not async_writes
            assert guards >= (1 if mode == "connect_expiry" else 2)
            assert reply.result_state == ("COMPLETED" if mode == "healthy" else "UNKNOWN")
            assert len(requests) == (1 if mode == "healthy" else 0)
            if mode == "healthy":
                assert handoffs and all(handoffs)
            elif mode in {"veto", "connect_expiry"}:
                assert not handoffs
            else:
                assert handoffs == [True]  # Partial/backpressure/closed never retries.
            await sender.drain()
        finally:
            await sender.close()
            broker.close()
            await broker.wait_closed()
            server.close()
            await server.wait_closed()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tuple(tasks)), 2)
