"""Supervisor wiring: no runtime in P0; explicit inert launch, no OPEN."""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MethodType
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from omnis.supervisor import __main__ as consumer


@pytest.mark.asyncio
@pytest.mark.parametrize("historical_shutdown", [False, True])
@pytest.mark.parametrize("ending", ["stop", "startup-failure", "early-close"])
async def test_fresh_model_owner_survives_historical_quiescence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    historical_shutdown: bool,
    ending: str,
) -> None:
    from omnis.modules.instance.records import InstanceRecord, LeaseRecord
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.model_test_models import ModelTestControl
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from sqlalchemy.ext.asyncio import AsyncConnection

    engine = Mock(dispose=AsyncMock())
    service = InstanceService(engine)
    state = InstanceRecord(
        id=1,
        instance_id=uuid4(),
        generation=2 if historical_shutdown else 0,
        admission_open=False,
        shutdown_command_id=uuid4() if historical_shutdown else None,
        quiesced_generation=2 if historical_shutdown else None,
        quiesced_at=datetime.now(UTC) if historical_shutdown else None,
    )
    lease = LeaseRecord(
        id=1, owner=uuid4(), epoch=2, expires_at=datetime.now(UTC) + timedelta(seconds=5)
    )
    connection = Mock(spec=AsyncConnection, execute=AsyncMock())

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        yield connection, state, lease

    monkeypatch.setattr(service, "_locked", locked)
    monkeypatch.setattr(service, "_require_owner", AsyncMock())
    monkeypatch.setattr(service, "acquire", AsyncMock(return_value=2))
    monkeypatch.setattr(service, "owned_status", AsyncMock(side_effect=lambda *args: state))
    monkeypatch.setattr(service, "heartbeat", AsyncMock())
    monkeypatch.setattr(service, "_receipt", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_record", AsyncMock())
    monkeypatch.setattr(service, "_stop_fence", AsyncMock())
    monkeypatch.setattr(service, "_finalized_epoch", AsyncMock(return_value=1))
    release = AsyncMock()
    monkeypatch.setattr(service, "release", release)
    runtime = Mock(
        connect=AsyncMock(),
        status=AsyncMock(return_value={"state": "IDLE"}),
        drain=AsyncMock(return_value=True),
        close=AsyncMock(),
        boot=str(uuid4()),
    )
    owners: list[NativeTaskOwner] = []
    task_joined = False

    async def active() -> None:
        nonlocal task_joined
        try:
            await asyncio.Future[None]()
        finally:
            task_joined = True

    @asynccontextmanager
    async def control(*args: object, **kwargs: object) -> AsyncIterator[Mock]:
        callback = kwargs["native_task"]
        assert isinstance(callback, MethodType)
        owner = callback.__self__
        assert isinstance(owner, NativeTaskOwner)
        owners.append(owner)
        assert runtime.drain.await_count == int(historical_shutdown)
        assert not owner.model_test_closing
        if ending == "startup-failure":
            raise ValueError("SOURCE startup failure")
        yield Mock()

    class Cycles:
        cycles = 0

        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            self.cycles += 1
            if self.cycles <= 3:
                assert not owners[0].model_test_closing
            return ending == "early-close" or self.cycles > 3

        async def wait(self) -> None:
            nonlocal state
            if self.cycles == 3:
                owner = owners[0]
                opened = await service.open(uuid4(), state.generation, owner.owner, owner.epoch)
                state = state.model_copy(
                    update={
                        "generation": opened,
                        "admission_open": True,
                        "shutdown_command_id": None,
                        "quiesced_generation": None,
                        "quiesced_at": None,
                    }
                )
                owner.model_test_task = asyncio.create_task(active())
                await asyncio.sleep(0)
                shutdown_id = uuid4()
                stopped = await service.shutdown(
                    shutdown_id, state.generation, owner.owner, owner.epoch
                )
                state = state.model_copy(
                    update={
                        "generation": stopped,
                        "admission_open": False,
                        "shutdown_command_id": shutdown_id,
                        "quiesced_generation": None,
                        "quiesced_at": None,
                    }
                )

                async def drained() -> bool:
                    assert owner.model_test_closing
                    assert owner.model_test_task is not None
                    assert owner.model_test_task.done() and task_joined
                    with pytest.raises(CatalogError, match="TASK_UNAVAILABLE"):
                        await owner.model_test(
                            ModelTestControl(
                                op="model_test",
                                action="start",
                                operation_id=str(uuid4()),
                                expected_selection_revision=1,
                                consent=True,
                            )
                        )
                    return True

                runtime.drain.side_effect = drained
            raise TimeoutError

    monkeypatch.setattr(asyncio, "Event", Cycles)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.setattr(consumer, "RuntimeClient", lambda *args, **kwargs: runtime)
    monkeypatch.setattr(consumer, "LocalControl", control)
    for key in ("OMNIS_RUNTIME_INERT_PROBE", "OMNIS_RUNTIME_CASE_ID", "OMNIS_RUNTIME_STATE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "OMNIS_DATABASE_URL": "synthetic",
        "OMNIS_CONTROL_DIR": "/synthetic-control",
        "OMNIS_RUNTIME_DIR": "/synthetic-runtime",
        "OMNIS_NATIVE_PREPARATION_CATALOG_ROOT": str(tmp_path),
        "OMNIS_MODEL_TEST_SOURCE_ROOT": "/opt/omnis/model-test",
        "OMNIS_MANAGED_TASKS": "1",
    }.items():
        monkeypatch.setenv(key, value)
    if ending == "startup-failure":
        with pytest.raises(ValueError, match="SOURCE startup failure"):
            await consumer.run()
    else:
        await consumer.run()
    assert owners[0].model_test_closing
    assert runtime.drain.await_count == int(historical_shutdown) + (2 if ending == "stop" else 1)
    if ending == "stop":
        assert task_joined
    runtime.close.assert_awaited_once()
    release.assert_awaited_once()
    engine.dispose.assert_awaited_once()


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
    async def control(
        *args: object, native_prepare: object = None, native_task: object = None
    ) -> AsyncIterator[None]:
        assert native_prepare is None  # No preparation catalog opt-in in this legacy journey.
        assert native_task is None
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
    capsys: pytest.CaptureFixture[str],
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
    async def control(
        *args: object, native_prepare: object = None, native_task: object = None
    ) -> AsyncIterator[None]:
        assert native_prepare is None
        assert native_task is None
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
    assert capsys.readouterr().err == ""


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
    async def control(
        *args: object, native_prepare: object = None, native_task: object = None
    ) -> AsyncIterator[None]:
        assert native_prepare is None
        assert native_task is None
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


@pytest.mark.asyncio
@pytest.mark.parametrize("drained", [True, False])
@pytest.mark.parametrize("phase", ["READINESS", "HEARTBEAT", "QUIESCE", "RUNTIME_STATUS", "RENEW"])
@pytest.mark.parametrize("mode", ["error", "cancel", "write_failure"])
async def test_loop_failure_is_recorded_before_control_exit_and_drain(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    drained: bool,
    phase: str,
    mode: str,
) -> None:
    from omnis.supervisor.runtime_client import RuntimeUnavailable

    primary = (
        asyncio.CancelledError("PRIVATE_EXCEPTION_TEXT")
        if mode == "cancel"
        else RuntimeUnavailable("PRIVATE_EXCEPTION_TEXT")
    )
    engine = Mock(dispose=AsyncMock())
    service = Mock(
        acquire=AsyncMock(return_value=1),
        owned_status=AsyncMock(return_value=Mock(generation=0)),
        heartbeat=AsyncMock(),
        quiesce=AsyncMock(),
        release=AsyncMock(),
    )
    client = Mock(
        connect=AsyncMock(),
        status=AsyncMock(return_value={"state": "READY"}),
        renew=AsyncMock(),
        drain=AsyncMock(return_value=drained),
        close=AsyncMock(),
    )
    readiness = AsyncMock(return_value=None)
    if phase == "READINESS":
        readiness.side_effect = [None, primary]
    elif phase == "HEARTBEAT":
        service.heartbeat.side_effect = primary
    elif phase == "QUIESCE":
        service.quiesce.side_effect = [None, primary]
    elif phase == "RUNTIME_STATUS":
        client.status.side_effect = [{"state": "IDLE"}, primary]
    else:
        client.renew.side_effect = primary
    captured: list[str] = []

    @asynccontextmanager
    async def control(*args: object, **kwargs: object) -> AsyncIterator[Mock]:
        try:
            yield Mock()
        finally:
            captured.append(capsys.readouterr().err)

    class OneCycle:
        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            return False

        async def wait(self) -> None:
            raise TimeoutError

    monkeypatch.setattr(asyncio, "Event", OneCycle)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", readiness)
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.setattr(consumer, "LocalControl", control)
    monkeypatch.setattr(consumer, "RuntimeClient", lambda *args, **kwargs: client)
    monkeypatch.setenv("OMNIS_DATABASE_URL", "synthetic")
    monkeypatch.setenv("OMNIS_CONTROL_DIR", "/synthetic")
    monkeypatch.setenv("OMNIS_RUNTIME_DIR", "/synthetic-runtime")
    for name in (
        "OMNIS_RUNTIME_INERT_PROBE",
        "OMNIS_RUNTIME_CASE_ID",
        "OMNIS_RUNTIME_STATE_ROOT",
        "OMNIS_NATIVE_PREPARATION_CATALOG_ROOT",
        "OMNIS_MANAGED_TASKS",
    ):
        monkeypatch.delenv(name, raising=False)
    with monkeypatch.context() as io:
        if mode == "write_failure":
            io.setattr(sys, "stderr", Mock(write=Mock(side_effect=OSError("PRIVATE_IO"))))
        with pytest.raises(type(primary) if drained else ValueError) as raised:
            await consumer.run()
    if drained:
        assert raised.value is primary
        service.release.assert_awaited_once()
    else:
        assert raised.value.__context__ is primary
        service.release.assert_not_awaited()
    kind = "CANCELLED" if mode == "cancel" else "RUNTIME_UNAVAILABLE"
    expected = f"SUPERVISOR_FAILURE phase={phase} error={kind}\n" if mode != "write_failure" else ""
    assert captured == [expected]
    assert capsys.readouterr().err == ""
    client.drain.assert_awaited_once()
    client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()
