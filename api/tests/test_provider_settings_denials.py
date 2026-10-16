"""SOURCE denial controls; no native import, provider traffic or database."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.service import RuntimeAuthority
from omnis.modules.settings.provider_models import ProviderView
from omnis.supervisor.runtime_client import RuntimeClient


@pytest.mark.asyncio
@pytest.mark.parametrize("cut", ["stop", "expiry", "lost_readback", "busy", "expired_idle"])
async def test_settings_stop_expiry_busy_and_lost_readback(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, cut: str
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(ipc_directory)
    calls = 0
    gate = asyncio.Event()

    async def native(action: str, value: object) -> dict[str, object] | None:
        nonlocal calls
        calls += 1
        await gate.wait()
        if cut == "lost_readback":
            raise ValueError("synthetic missing readback")
        return None

    monkeypatch.setattr(host, "_settings_native", native)
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
    )
    owner = uuid4()
    async with host:
        client = RuntimeClient(ipc_directory, generation=0, epoch=1)
        await client.connect()
        try:
            command: dict[str, object] = {
                "operation_id": str(uuid4()),
                "action": "read",
                "selection": None,
            }
            assert (await client.settings(service, owner, command))["status"] == "PENDING"
            await asyncio.sleep(0)
            assert calls == 1
            if cut == "expired_idle":
                gate.set()
                await asyncio.sleep(0.01)
                assert (await client.settings_status(str(command["operation_id"])))[
                    "status"
                ] == "CONFIRMED"
                host.deadline_ns = time.monotonic_ns() - 1
                other_expired: dict[str, object] = {**command, "operation_id": str(uuid4())}
                assert (await client.settings(service, owner, other_expired))["status"] == "BUSY"
                assert calls == 1
                return
            if cut == "busy":
                other: dict[str, object] = {**command, "operation_id": str(uuid4())}
                assert (await client.settings(service, owner, other))["status"] == "BUSY"
                assert calls == 1
                gate.set()
                await asyncio.sleep(0.01)
                assert (await client.settings_status(str(command["operation_id"])))[
                    "status"
                ] == "CONFIRMED"
                # Execution is mutually exclusive even when management is idle.
                with pytest.raises(ValueError):
                    await client.launch_inert(service, owner)
                return
            if cut == "stop":
                assert await client.drain() is True  # no process existed in this simulation
            elif cut == "expiry":
                host.deadline_ns = time.monotonic_ns() - 1
                await asyncio.sleep(0.06)
            else:
                gate.set()
                await asyncio.sleep(0.06)
            result = await client.settings_status(str(command["operation_id"]))
            assert result["status"] == "INDETERMINATE"
            assert result["configured"] is False
            assert host.state == "STOPPED"
            assert calls == 1
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_cancelled_settings_exchange_retires_stream_without_resend(
    ipc_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes import runtime_host

    host = runtime_host.RuntimeHost(ipc_directory)
    admitted = asyncio.Event()

    async def native(action: str, value: object) -> None:
        admitted.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(host, "_settings_native", native)
    from omnis_hermes.runtime_protocol import encode as original_encode

    def lose_settings(frame: dict[str, object]) -> bytes:
        return b"" if "settings" in frame else original_encode(frame)

    monkeypatch.setattr(runtime_host, "encode", lose_settings)
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
    )
    async with host:
        client = RuntimeClient(ipc_directory, generation=0, epoch=1)
        await client.connect()
        task = asyncio.create_task(
            client.settings(
                service,
                uuid4(),
                {"operation_id": str(uuid4()), "action": "read", "selection": None},
            )
        )
        try:
            await asyncio.wait_for(admitted.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert client.writer is None
            async with asyncio.timeout(1):
                while host.state != "STOPPED":
                    await asyncio.sleep(0.01)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()


def test_public_view_does_not_coerce_false_readiness() -> None:
    with pytest.raises(ValueError):
        ProviderView.model_validate(
            {
                "operation_id": str(uuid4()),
                "status": "CONFIRMED",
                "selection": None,
                "configured": False,
                "authenticated": "NOT_VERIFIED",
                "reachable": "NOT_VERIFIED",
                "inference_ready": 0,
            }
        )
