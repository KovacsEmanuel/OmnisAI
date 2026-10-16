"""SOURCE simulation: real API/control/Host wiring; no native import or database."""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.domain import ControlCode, ControlConflict
from omnis.modules.instance.service import RuntimeAuthority
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable


@pytest.mark.asyncio
async def test_normal_supervisor_settings_after_open_uses_its_single_client(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Normal entry wiring + real adapter UDS; DB and native save are SOURCE doubles."""
    from contextlib import asynccontextmanager

    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.modules.settings.provider_models import SettingsControl
    from omnis.supervisor import __main__ as consumer

    service = Mock()
    engine = Mock(dispose=AsyncMock())
    generation = 0
    service.acquire = AsyncMock(return_value=1)
    service.release = AsyncMock()
    service.heartbeat = AsyncMock()
    service.owned_status = AsyncMock(
        side_effect=lambda *a: SimpleNamespace(
            generation=generation, admission_open=generation == 1, shutdown_command_id=None
        )
    )

    async def grant(
        owner: object, epoch: int, current: int, *, management: bool
    ) -> RuntimeAuthority:
        if current != generation:
            raise ControlConflict(ControlCode.GENERATION_CONFLICT)
        return RuntimeAuthority(current, epoch, time.monotonic_ns() + 4_000_000_000)

    service.runtime_authority = AsyncMock(side_effect=grant)
    ready = asyncio.Event()
    closed = asyncio.Event()
    ctl = SimpleNamespace(settings=None)

    @asynccontextmanager
    async def control(*args: object, **kwargs: object) -> AsyncIterator[SimpleNamespace]:
        assert kwargs == {"native_prepare": None, "native_task": None}
        try:
            yield ctl
        finally:
            closed.set()

    async def quiesce(*args: object) -> None:
        ready.set()

    service.quiesce = AsyncMock(side_effect=quiesce)
    host = RuntimeHost(ipc_directory)
    selected = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}
    native = AsyncMock(return_value=selected)
    monkeypatch.setattr(host, "_settings_native", native)
    monkeypatch.setattr(consumer, "database_engine", lambda _: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", lambda _: service)
    monkeypatch.setattr(consumer, "LocalControl", control)
    clients: list[RuntimeClient] = []

    def client(directory: Path, *, generation: int, epoch: int) -> RuntimeClient:
        value = RuntimeClient(directory, generation=generation, epoch=epoch)
        clients.append(value)
        return value

    monkeypatch.setattr(consumer, "RuntimeClient", client)
    for key in (
        "OMNIS_RUNTIME_INERT_PROBE",
        "OMNIS_RUNTIME_CASE_ID",
        "OMNIS_RUNTIME_STATE_ROOT",
        "OMNIS_NATIVE_PREPARATION_CATALOG_ROOT",
        "OMNIS_MANAGED_TASKS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OMNIS_DATABASE_URL", "synthetic")
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(ipc_directory / "unused-control"))
    monkeypatch.setenv("OMNIS_RUNTIME_DIR", str(ipc_directory))
    async with host:
        task = asyncio.create_task(consumer.run())
        try:
            await asyncio.wait_for(ready.wait(), 1)
            assert len(clients) == 1 and clients[0].generation == 0
            assert host.state == "IDLE"
            native.assert_not_awaited()
            generation = 1  # SOURCE DB OPEN commit, not a client-authorized generation.
            operation_id = str(uuid4())
            command = SettingsControl.model_validate(
                {
                    "op": "settings",
                    "operation_id": operation_id,
                    "command": {
                        "operation_id": operation_id,
                        "action": "save",
                        "selection": selected,
                    },
                }
            )
            result = await ctl.settings(command)
            assert result["status"] == "PENDING"
            async with asyncio.timeout(1):
                while result["status"] == "PENDING":
                    await asyncio.sleep(0.001)
                    result = await ctl.settings(
                        SettingsControl.model_validate(
                            {"op": "settings", "operation_id": operation_id, "command": None}
                        )
                    )
            assert result["selection"] == selected and result["status"] == "CONFIRMED"
            assert clients[0].generation == host.generation == 1
            assert service.runtime_drain == clients[0].drain
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        assert closed.is_set()
        service.release.assert_awaited_once()


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cut",
    ["open", "prior-quiesce", "stopped", "uncertain", "active", "jump", "closed", "owner", "race"],
)
async def test_first_settings_binds_only_current_open_idle_generation(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, cut: str
) -> None:
    """Installed ordering, real Host/UDS, explicit SOURCE DB-authority double."""
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(ipc_directory)
    calls: list[str] = []

    async def native(action: str, selection: object) -> dict[str, object]:
        calls.append(action)
        return {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}

    monkeypatch.setattr(host, "_settings_native", native)
    owner = uuid4()
    current = 12 if cut == "jump" else 11
    service = Mock()
    service.owned_status = AsyncMock(
        return_value=SimpleNamespace(
            generation=current, admission_open=cut != "closed", shutdown_command_id=None
        )
    )
    seen: list[int] = []

    async def grant(
        who: object, epoch: int, generation: int, *, management: bool
    ) -> RuntimeAuthority:
        assert who == owner and epoch == 7 and management is True
        seen.append(generation)
        if cut == "owner":
            raise ControlConflict(ControlCode.LEASE_LOST)
        if generation != current:
            raise ControlConflict(ControlCode.GENERATION_CONFLICT)
        if cut == "race":
            await client.drain()  # Stop wins before binding: never resurrect Host.
        return RuntimeAuthority(current, 7, time.monotonic_ns() + 4_000_000_000)

    service.runtime_authority = AsyncMock(side_effect=grant)
    async with host:
        client = RuntimeClient(ipc_directory, generation=10, epoch=7)
        await client.connect()
        boot, writer = client.boot, client.writer
        try:
            if cut == "prior-quiesce":
                # The supervisor quiesces the previous finalized generation
                # before OPEN; a cold Host with no process remains IDLE.
                assert await client.drain()
                assert (await client.status())["state"] == "IDLE"
            elif cut == "stopped":
                host.state = "STOPPED"
                host.generation, host.epoch = 10, 7
            elif cut == "uncertain":
                host.state = "UNCERTAIN"
                host.generation, host.epoch = 10, 7
            elif cut == "active":
                host.state = "MANAGEMENT"
                host.generation, host.epoch = 10, 7
                host.deadline_ns = time.monotonic_ns() + 4_000_000_000
            command: dict[str, object] = {
                "operation_id": str(uuid4()),
                "action": "read",
                "selection": None,
            }
            if cut in {"open", "prior-quiesce"}:
                result = await client.settings(service, owner, command)
                assert result["status"] == "PENDING"
                assert client.generation == 11 and host.generation == 11
                assert client.boot == boot and client.writer is writer
                async with asyncio.timeout(1):
                    while (await client.settings_status(str(command["operation_id"])))[
                        "status"
                    ] == "PENDING":
                        await asyncio.sleep(0.001)
                assert calls == ["read"]
                assert seen == [10, 11]
                # A subsequent OPEN-like change cannot rebind an active writer.
                current = 12
                with pytest.raises((ControlConflict, RuntimeUnavailable)):
                    await client.settings(service, owner, command)
                assert client.generation == 11
            else:
                with pytest.raises((ControlConflict, RuntimeUnavailable)):
                    await client.settings(service, owner, command)
                assert client.generation == 10
                assert calls == []
        finally:
            await client.close()
