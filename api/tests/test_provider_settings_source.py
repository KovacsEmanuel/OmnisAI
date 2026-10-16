"""SOURCE simulation: real API/control/Host wiring; no native import or database."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.supervisor.runtime_client import RuntimeClient


@pytest.mark.asyncio
async def test_settings_management_retains_exact_selection_without_ready_inventory(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Loading the adapter source is not booting/importing native Hermes.
    adapter = Path(__file__).resolve().parents[2] / "integrations/hermes/src"
    monkeypatch.syspath_prepend(str(adapter))
    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.modules.instance.service import RuntimeAuthority

    assert hasattr(RuntimeClient, "settings"), "typed Settings consumer missing"
    host = RuntimeHost(ipc_directory)
    gate = asyncio.Event()
    selection: dict[str, object] = {
        "provider": "openai-codex",
        "model": "gpt-6.1-sol",
        "effort": "xhigh",
    }

    async def operation(action: str, value: object) -> dict[str, object]:
        await gate.wait()
        return selection

    monkeypatch.setattr(host, "_settings_native", operation)
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
    )
    async with host:
        client = RuntimeClient(ipc_directory, generation=0, epoch=1)
        await client.connect()
        try:
            operation_id = str(uuid4())
            command: dict[str, object] = {
                "operation_id": operation_id,
                "action": "save",
                "selection": selection,
            }
            result = await client.settings(service, uuid4(), command)
            assert result["status"] == "PENDING"
            assert (await client.status())["bootstrap_inventory"] is None
            # A pending operation must not block the owner's renewal exchange.
            await client.renew(service, uuid4(), management=True)
            gate.set()
            for _ in range(30):
                result = await client.settings_status(operation_id)
                if result["status"] != "PENDING":
                    break
                await asyncio.sleep(0.01)
            assert result["status"] == "CONFIRMED"
            assert result["selection"] == selection
            assert result["configured"] is True
            assert result["authenticated"] == "NOT_VERIFIED"
            assert result["reachable"] == "NOT_VERIFIED"
            assert result["inference_ready"] is False
            assert (await client.status())["assessment_ready"] is False
        finally:
            await client.close()
