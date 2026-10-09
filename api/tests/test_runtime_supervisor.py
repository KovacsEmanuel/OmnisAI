"""Supervisor wiring: no runtime in P0; explicit inert launch, no OPEN."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.supervisor import __main__ as consumer


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_state", ["IDLE", "READY"])
async def test_case_consumer_restores_before_launch_and_archives_before_release(
    monkeypatch: pytest.MonkeyPatch,
    initial_state: str,
) -> None:
    events: list[str] = []
    engine = Mock(dispose=AsyncMock())
    service = Mock()
    instance_id, case_id, boot = uuid4(), uuid4(), str(uuid4())
    service.acquire = AsyncMock(return_value=1)
    service.owned_status = AsyncMock(return_value=Mock(generation=0, instance_id=instance_id))
    service.quiesce = AsyncMock()
    service.heartbeat = AsyncMock()

    async def released(*args: object) -> None:
        events.append("release")

    service.release = AsyncMock(side_effect=released)
    client = Mock(boot=boot)
    client.connect = AsyncMock()
    client.renew = AsyncMock()
    client.close = AsyncMock()
    stopped: dict[str, object] = {"state": "STOPPED", "drained": True}
    client.status = AsyncMock(side_effect=[{"state": initial_state}, stopped])

    async def launched(*args: object) -> dict[str, object]:
        events.append("launch")
        return {"state": "READY"}

    async def drained() -> bool:
        events.append("drain")
        return True

    client.launch_inert = AsyncMock(side_effect=launched)
    client.drain = AsyncMock(side_effect=drained)
    slot = Mock(close=AsyncMock())

    async def prepared(*args: object) -> None:
        events.append("restore")

    async def archived(*args: object) -> None:
        events.append("archive")

    slot.prepare = AsyncMock(side_effect=prepared)
    slot.observe = AsyncMock()
    slot.archive = AsyncMock(side_effect=archived)
    engagement = Mock(read=AsyncMock())

    @asynccontextmanager
    async def control(*args: object, native_prepare: object = None) -> AsyncIterator[None]:
        assert native_prepare is None  # No preparation catalog opt-in in this legacy journey.
        yield

    class Stopped:
        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            return True

    monkeypatch.setattr(asyncio, "Event", Stopped)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.setattr(consumer, "EngagementService", lambda raw: engagement, raising=False)
    monkeypatch.setattr(consumer, "CaseSlot", lambda *args: slot, raising=False)
    monkeypatch.setattr(consumer, "LocalControl", control)
    monkeypatch.setattr(consumer, "RuntimeClient", lambda *args, **kwargs: client)
    for key, value in {
        "OMNIS_DATABASE_URL": "synthetic",
        "OMNIS_CONTROL_DIR": "/synthetic",
        "OMNIS_RUNTIME_DIR": "/synthetic-runtime",
        "OMNIS_RUNTIME_INERT_PROBE": "1",
        "OMNIS_RUNTIME_CASE_ID": str(case_id),
        "OMNIS_RUNTIME_STATE_ROOT": "/synthetic-state",
    }.items():
        monkeypatch.setenv(key, value)
    if initial_state == "READY":
        with pytest.raises(ValueError, match="Fresh runtime"):
            await consumer.run()
        slot.prepare.assert_not_awaited()
        slot.archive.assert_not_awaited()
        return
    await consumer.run()
    assert events == ["restore", "launch", "drain", "archive", "release"]
    engagement.read.assert_awaited_once_with(case_id)
    slot.observe.assert_awaited_once_with({"state": "READY"})
    slot.archive.assert_awaited_once_with(service, 0, stopped)


@pytest.mark.asyncio
async def test_supervisor_runtime_is_opt_in_and_drained_before_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hasattr(consumer, "RuntimeClient"), "runtime opt-in wiring missing"
    engine = Mock()
    engine.dispose = AsyncMock()
    service = Mock()
    service.acquire = AsyncMock(return_value=1)
    service.owned_status = AsyncMock(return_value=Mock(generation=0))
    service.quiesce = AsyncMock()
    service.heartbeat = AsyncMock()
    service.release = AsyncMock()
    client = Mock()
    client.connect = AsyncMock()
    client.launch_inert = AsyncMock()
    client.renew = AsyncMock()
    client.status = AsyncMock(return_value={"state": "READY"})
    client.drain = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client_factory = Mock(return_value=client)
    service_factory = Mock(return_value=service)

    @asynccontextmanager
    async def control(*args: object, native_prepare: object = None) -> AsyncIterator[None]:
        assert native_prepare is None
        yield

    class Stopped:
        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            return True

    monkeypatch.setattr(asyncio, "Event", Stopped)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", service_factory)
    monkeypatch.setattr(consumer, "LocalControl", control)
    monkeypatch.setattr(consumer, "RuntimeClient", client_factory)
    monkeypatch.setenv("OMNIS_DATABASE_URL", "synthetic")
    monkeypatch.setenv("OMNIS_CONTROL_DIR", "/synthetic")
    monkeypatch.delenv("OMNIS_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("OMNIS_RUNTIME_INERT_PROBE", raising=False)
    await consumer.run()
    client_factory.assert_not_called()
    monkeypatch.setenv("OMNIS_RUNTIME_DIR", "/synthetic-runtime")
    monkeypatch.setenv("OMNIS_RUNTIME_INERT_PROBE", "1")
    await consumer.run()
    client_factory.assert_called_once_with(Path("/synthetic-runtime"), generation=0, epoch=1)
    client.launch_inert.assert_awaited_once()
    service.heartbeat.assert_awaited_once()
    client.renew.assert_awaited_once_with(service, service.acquire.call_args.args[0])
    client.drain.assert_awaited_once()
    client.close.assert_awaited_once()
    assert service.runtime_drain == client.drain
    service.open.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,shutdown_recorded,quiesced,unavailable",
    [
        ("STOPPED", False, False, True),
        ("UNCERTAIN", True, True, True),
        ("STOPPED", True, False, True),
        ("STOPPED", True, True, False),
    ],
)
async def test_supervisor_does_not_silently_continue_after_unexpected_runtime_loss(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    shutdown_recorded: bool,
    quiesced: bool,
    unavailable: bool,
) -> None:
    engine = Mock()
    engine.dispose = AsyncMock()
    service = Mock()
    service.acquire = AsyncMock(return_value=1)
    service.owned_status = AsyncMock(
        return_value=Mock(
            generation=0,
            shutdown_command_id=uuid4() if shutdown_recorded else None,
            quiesced_generation=0 if quiesced else None,
        )
    )
    service.quiesce = AsyncMock()
    service.heartbeat = AsyncMock()
    service.release = AsyncMock()
    client = Mock()
    client.connect = AsyncMock()
    client.launch_inert = AsyncMock()
    client.renew = AsyncMock()
    client.status = AsyncMock(return_value={"state": state})
    client.drain = AsyncMock(return_value=True)
    client.close = AsyncMock()

    @asynccontextmanager
    async def control(*args: object, native_prepare: object = None) -> AsyncIterator[None]:
        assert native_prepare is None
        yield

    class OneCycle:
        cycles = 0

        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            self.cycles += 1
            return self.cycles > 1

        async def wait(self) -> None:
            raise TimeoutError

    monkeypatch.setattr(asyncio, "Event", OneCycle)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.setattr(consumer, "LocalControl", control)
    monkeypatch.setattr(consumer, "RuntimeClient", lambda *args, **kwargs: client)
    monkeypatch.setenv("OMNIS_DATABASE_URL", "synthetic")
    monkeypatch.setenv("OMNIS_CONTROL_DIR", "/synthetic")
    monkeypatch.setenv("OMNIS_RUNTIME_DIR", "/synthetic-runtime")
    monkeypatch.setenv("OMNIS_RUNTIME_INERT_PROBE", "1")
    if unavailable:
        with pytest.raises(ValueError, match="Runtime unavailable"):
            await consumer.run()
    else:
        await consumer.run()
    assert client.renew.await_count == 1  # Initial post-launch refresh only; no resurrection.
    client.drain.assert_awaited_once()
    client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()
