"""Managed operations on the existing stream; peer is explicitly synthetic."""

import asyncio
import json
import socket
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.service import InstanceService, RuntimeAuthority
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable


@asynccontextmanager
async def peer_client(
    directory: Path,
    requests: list[dict[str, object]],
    *,
    reply: bool = True,
    result: Callable[[dict[str, object]], dict[str, object]] | None = None,
    runtime_boot: str | None = None,
    failure: str | None = None,
    observed: asyncio.Event | None = None,
    hold: asyncio.Event | None = None,
) -> AsyncIterator[RuntimeClient]:
    boot = runtime_boot or str(uuid4())
    settled = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await reader.readuntil(b"\n")
            value = json.loads(raw)
            requests.append(value)
            if observed is not None:
                observed.set()
            if failure in {"timeout", "cancel"}:
                await reader.read()
                return
            if hold is not None:
                await hold.wait()
            if reply:
                response = {
                    "id": value["id"],
                    "boot": boot,
                    "ok": True,
                    "state": "READY",
                    "generation": 0,
                    "epoch": 1,
                    "assessment_ready": False,
                    "drained": False,
                    "bootstrap_inventory": {
                        "schema_version": 1,
                        "observation": "NATIVE_BOOTSTRAP",
                        "scope": "/state/active",
                        "registry": {
                            "status": "NOT_INITIALIZED",
                            "generation": None,
                            "count": None,
                            "entries": None,
                        },
                        "plugins": {
                            "status": "NOT_INITIALIZED",
                            "count": None,
                            "entries": None,
                        },
                    },
                    "managed": result(value["payload"])
                    if result is not None
                    else {"protocol": value["payload"]["protocol"], "status": "STAGED"},
                }
                writer.write(json.dumps(response).encode() + b"\n")
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            settled.set()

    server = await asyncio.start_unix_server(handle, path=str(directory / "peer.sock"))
    client = RuntimeClient(directory, generation=0, epoch=1)
    client.boot, client.capability = boot, "a" * 64
    client.reader, client.writer = await asyncio.open_unix_connection(str(directory / "peer.sock"))
    try:
        yield client
    finally:
        await client.close()
        await asyncio.wait_for(settled.wait(), 1)
        server.close()
        await server.wait_closed()


@asynccontextmanager
async def backpressured_client(
    directory: Path, runtime_boot: str, measured: dict[str, int]
) -> AsyncIterator[RuntimeClient]:
    """Real UDS; peer reads only after the caller has returned from its fence."""
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    left.setblocking(False)
    right.setblocking(False)
    client = RuntimeClient(directory, generation=0, epoch=1)
    client.boot, client.capability = runtime_boot, "c" * 64
    writer = None
    try:
        client.reader, client.writer = await asyncio.open_unix_connection(sock=left)
        writer = client.writer
        writer.transport.set_write_buffer_limits(high=1024, low=512)
        yield client
        measured["buffer_at_return"] = writer.transport.get_write_buffer_size()
        received = 0
        complete = 0
        async with asyncio.timeout(1):
            while part := await asyncio.get_running_loop().sock_recv(right, 65536):
                received += len(part)
                complete += part.count(b"\n")
        measured["received_after_return"] = received
        measured["complete_frames_after_return"] = complete
    finally:
        if writer is not None and left.fileno() != -1:
            writer.transport.abort()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)
        right.close()
        left.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "cancel"])
async def test_frozen_backpressure_discards_pending_bytes_before_return(
    ipc_directory: Path, failure: str
) -> None:
    measured: dict[str, int] = {}
    async with backpressured_client(ipc_directory, str(uuid4()), measured) as client:
        writer = client.writer
        assert writer is not None
        transport = writer.transport
        frozen = client.freeze_preflight(
            RuntimeAuthority(0, 1, time.monotonic_ns() + 4_500_000_000),
            {"protocol": "omnis-managed-admission-v3", "text": "x" * 32000},
            wall_seconds=1,
        )
        task = asyncio.create_task(client.exchange_frozen(frozen))
        try:
            async with asyncio.timeout(0.5):
                while transport.get_write_buffer_size() == 0:
                    await asyncio.sleep(0)
            measured["buffer_before_failure"] = transport.get_write_buffer_size()
            if failure == "cancel":
                task.cancel()
            with pytest.raises(
                asyncio.CancelledError if failure == "cancel" else RuntimeUnavailable
            ):
                await asyncio.wait_for(task, 2)
            assert client.reader is None and client.writer is None
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
    assert measured["buffer_before_failure"] > 0
    assert measured["buffer_at_return"] == 0
    assert measured["complete_frames_after_return"] == 0
    assert 0 < measured["received_after_return"] < len(frozen.frame)


@pytest.mark.parametrize("operation", ["task_stage", "task_release", "task_status"])
@pytest.mark.parametrize(
    "protocol",
    [
        "omnis-managed-admission-v1",
        "omnis-managed-admission-v2",
        "omnis-managed-admission-v3",
        "omnis-managed-admission-v4",
    ],
)
@pytest.mark.asyncio
async def test_managed_exchange_uses_current_grant_and_existing_stream(
    ipc_directory: Path, operation: str, protocol: str
) -> None:
    requests: list[dict[str, object]] = []
    authority = RuntimeAuthority(0, 1, time.monotonic_ns() + 1_000_000_000)
    service = Mock(spec=InstanceService)
    service.runtime_authority = AsyncMock(return_value=authority)
    owner = uuid4()
    payload: dict[str, object] = {"protocol": protocol}
    async with peer_client(ipc_directory, requests) as client:
        assert callable(getattr(client, "managed", None)), "managed runtime exchange absent"
        result = await client.managed(service, owner, operation, payload)
        assert result == {"protocol": protocol, "status": "STAGED"}
        service.runtime_authority.assert_awaited_once_with(owner, 1, 0, inert_probe=True)
    assert len(requests) == 1
    assert requests[0]["payload"] == payload
    assert requests[0]["op"] == operation
    assert requests[0]["deadline_ns"] == authority.deadline_ns


@pytest.mark.asyncio
async def test_frozen_preflight_uses_original_bytes(ipc_directory: Path) -> None:
    requests: list[dict[str, object]] = []
    authority = RuntimeAuthority(0, 1, time.monotonic_ns() + 1_000_000_000)
    payload: dict[str, object] = {"protocol": "omnis-managed-admission-v3"}
    async with peer_client(ipc_directory, requests) as client:
        frozen = client.freeze_preflight(authority, payload, wall_seconds=1)
        payload["protocol"] = "MUTATED_AFTER_FREEZE"
        await client.exchange_frozen(frozen)
        assert frozen.request_id == requests[0]["id"]
        assert client.capability not in repr(frozen)
    assert requests[0]["payload"] == {"protocol": "omnis-managed-admission-v3"}


@pytest.mark.asyncio
async def test_lost_managed_reply_closes_without_resend(ipc_directory: Path) -> None:
    requests: list[dict[str, object]] = []
    service = Mock(spec=InstanceService)
    service.runtime_authority = AsyncMock(
        return_value=RuntimeAuthority(0, 1, time.monotonic_ns() + 1_000_000_000)
    )
    async with peer_client(ipc_directory, requests, reply=False) as client:
        assert callable(getattr(client, "managed", None)), "managed runtime exchange absent"
        with pytest.raises(RuntimeUnavailable):
            await client.managed(
                service, uuid4(), "task_release", {"protocol": "omnis-managed-admission-v1"}
            )
        assert client.reader is None and client.writer is None
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_expired_grant_refuses_before_managed_write(ipc_directory: Path) -> None:
    requests: list[dict[str, object]] = []
    service = Mock(spec=InstanceService)
    service.runtime_authority = AsyncMock(
        return_value=RuntimeAuthority(0, 1, time.monotonic_ns() - 1)
    )
    async with peer_client(ipc_directory, requests) as client:
        with pytest.raises(RuntimeUnavailable, match="Expired runtime authority"):
            await client.managed(
                service, uuid4(), "task_release", {"protocol": "omnis-managed-admission-v1"}
            )
    assert requests == []


@pytest.mark.asyncio
async def test_arbitrary_operation_never_requests_authority(ipc_directory: Path) -> None:
    service = Mock(spec=InstanceService)
    service.runtime_authority = AsyncMock()
    client = RuntimeClient(ipc_directory, generation=0, epoch=1)
    with pytest.raises(RuntimeUnavailable, match="operation denied"):
        await client.managed(
            service, uuid4(), "prompt.submit", {"protocol": "omnis-managed-admission-v1"}
        )
    service.runtime_authority.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", [None, True, [], "omnis-managed-admission-v6"])
async def test_unknown_managed_version_never_requests_authority(
    ipc_directory: Path, protocol: object
) -> None:
    service = Mock(spec=InstanceService)
    service.runtime_authority = AsyncMock()
    client = RuntimeClient(ipc_directory, generation=0, epoch=1)
    with pytest.raises(RuntimeUnavailable, match="payload denied"):
        await client.managed(service, uuid4(), "task_stage", {"protocol": protocol})
    service.runtime_authority.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("over", [False, True])
async def test_frozen_payload_exact_wire_size_and_escaping(ipc_directory: Path, over: bool) -> None:
    requests: list[dict[str, object]] = []
    authority = RuntimeAuthority(0, 1, time.monotonic_ns() + 1_000_000_000)
    payload: dict[str, object] = {"protocol": "omnis-managed-admission-v3", "text": 'é"\n'}
    size = len(json.dumps(payload, separators=(",", ":"), allow_nan=False).encode())
    payload["padding"] = ""
    overhead = len(json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()) - size
    payload["padding"] = "x" * (32768 - size - overhead + int(over))
    async with peer_client(ipc_directory, requests) as client:
        if over:
            with pytest.raises(RuntimeUnavailable, match="payload limit"):
                client.freeze_preflight(authority, payload, wall_seconds=1)
        else:
            from dataclasses import FrozenInstanceError

            frozen = client.freeze_preflight(authority, payload, wall_seconds=1)
            assert len(frozen.body) == 32768 and len(frozen.frame) <= 65536
            with pytest.raises(FrozenInstanceError):
                frozen.__setattr__("body", b"mutated")
    assert requests == []
