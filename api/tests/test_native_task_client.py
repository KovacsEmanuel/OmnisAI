"""Managed operations on the existing stream; peer is explicitly synthetic."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.service import InstanceService, RuntimeAuthority
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable


@asynccontextmanager
async def peer_client(
    directory: Path, requests: list[dict[str, object]], *, reply: bool = True
) -> AsyncIterator[RuntimeClient]:
    boot = str(uuid4())
    settled = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await reader.readuntil(b"\n")
            value = json.loads(raw)
            requests.append(value)
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
                        "plugins": {"status": "NOT_INITIALIZED", "count": None, "entries": None},
                    },
                    "managed": {"protocol": "omnis-managed-admission-v1", "status": "STAGED"},
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


@pytest.mark.parametrize("operation", ["task_stage", "task_release", "task_status"])
@pytest.mark.asyncio
async def test_managed_exchange_uses_current_grant_and_existing_stream(
    ipc_directory: Path, operation: str
) -> None:
    requests: list[dict[str, object]] = []
    authority = RuntimeAuthority(0, 1, time.monotonic_ns() + 1_000_000_000)
    service = Mock(spec=InstanceService)
    service.runtime_authority = AsyncMock(return_value=authority)
    owner = uuid4()
    payload: dict[str, object] = {"protocol": "omnis-managed-admission-v1"}
    async with peer_client(ipc_directory, requests) as client:
        assert callable(getattr(client, "managed", None)), "managed runtime exchange absent"
        result = await client.managed(service, owner, operation, payload)
        assert result == {"protocol": "omnis-managed-admission-v1", "status": "STAGED"}
        service.runtime_authority.assert_awaited_once_with(owner, 1, 0, inert_probe=True)
    assert len(requests) == 1
    assert requests[0]["payload"] == payload
    assert requests[0]["op"] == operation
    assert requests[0]["deadline_ns"] == authority.deadline_ns


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
