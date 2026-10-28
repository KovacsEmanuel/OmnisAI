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
@pytest.mark.parametrize("fault", ["acquire_refused", "missing_keys", "runtime", "egress"])
async def test_model_sender_preparation_preserves_guards_and_closes_on_acquire_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fault: str
) -> None:
    from omnis.modules.instance.domain import ControlCode, ControlConflict
    from omnis.supervisor import model_sender

    engine = Mock(dispose=AsyncMock())
    refusal = ControlConflict(ControlCode.SUPERVISOR_OWNED)
    service = Mock(
        acquire=AsyncMock(
            side_effect=refusal if fault == "acquire_refused" else None, return_value=1
        ),
        owned_status=AsyncMock(return_value=Mock(instance_id=uuid4())),
        release=AsyncMock(),
    )
    senders: list[model_sender.ModelSender] = []
    construct = model_sender.ModelSender.__init__

    def prepare(sender: model_sender.ModelSender, path: Path) -> None:
        construct(sender, path)
        senders.append(sender)

    monkeypatch.setattr(model_sender.ModelSender, "__init__", prepare)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.delenv("OMNIS_RUNTIME_DIR", raising=False)
    for key, value in {
        "OMNIS_DATABASE_URL": "synthetic",
        "OMNIS_CONTROL_DIR": str(tmp_path / "control"),
        "OMNIS_VAULT_DIR": str(tmp_path / "vault"),
        "OMNIS_VAULT_KEY_DIR": str(tmp_path / "keys"),
        "OMNIS_MODEL_EGRESS_DIR": "/vault",
    }.items():
        monkeypatch.setenv(key, value)
    if fault == "missing_keys":
        monkeypatch.delenv("OMNIS_VAULT_KEY_DIR")
    elif fault == "runtime":
        monkeypatch.setenv("OMNIS_RUNTIME_DIR", str(tmp_path / "runtime"))
    elif fault == "egress":
        monkeypatch.setenv("OMNIS_MODEL_EGRESS_DIR", str(tmp_path / "egress"))
    if fault == "acquire_refused":
        with pytest.raises(ControlConflict) as raised:
            await consumer.run()
        assert raised.value is refusal
        service.acquire.assert_awaited_once()
        assert len(senders) == 1 and senders[0].http.is_closed
    else:
        with pytest.raises(ValueError, match="explicit owner-only storage|Release-bound"):
            await consumer.run()
        assert not senders
        service.acquire.assert_not_awaited()
    service.owned_status.assert_not_awaited()
    service.release.assert_not_awaited()
    engine.dispose.assert_awaited_once()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("historical_shutdown", [False, True])
@pytest.mark.parametrize("ending", ["stop", "startup-failure", "early-close"])
async def test_fresh_model_owner_survives_historical_quiescence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    historical_shutdown: bool,
    ending: str,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from omnis.modules.instance.records import InstanceRecord, LeaseRecord
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.model_test_models import ModelTestControl
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import NativeTaskOwner

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
@pytest.mark.parametrize("historical_shutdown", [False, True])
@pytest.mark.parametrize("ending", ["stop", "settlement-failure", "owner-loss"])
async def test_api_key_owner_admits_after_preopen_heartbeats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    historical_shutdown: bool,
    ending: str,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from omnis.modules.instance.domain import ControlCode, ControlConflict
    from omnis.modules.instance.records import InstanceRecord, LeaseRecord
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.model_test_models import ModelTestControl
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.modules.runs.model_test_store import ModelConflict
    from omnis.modules.settings.provider_vault import ProviderVault
    from omnis.supervisor import model_sender

    # SOURCE storage/transport doubles; lifecycle, admission and ModelTest callback are real.
    result = Mock(first=Mock(return_value=None), one_or_none=Mock(return_value=None))
    result.mappings.return_value.one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    connection = Mock(spec=AsyncConnection, execute=AsyncMock(return_value=result))

    @asynccontextmanager
    async def database() -> AsyncIterator[AsyncConnection]:
        yield connection

    engine = Mock(connect=database, begin=database, dispose=AsyncMock())
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

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        yield connection, state, lease

    monkeypatch.setattr(service, "_locked", locked)
    require_owner = AsyncMock()
    heartbeat = AsyncMock()
    monkeypatch.setattr(service, "_require_owner", require_owner)
    monkeypatch.setattr(service, "acquire", AsyncMock(return_value=2))
    monkeypatch.setattr(service, "owned_status", AsyncMock(side_effect=lambda *args: state))
    monkeypatch.setattr(service, "heartbeat", heartbeat)
    monkeypatch.setattr(service, "_receipt", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_record", AsyncMock())
    monkeypatch.setattr(service, "_stop_fence", AsyncMock())
    monkeypatch.setattr(service, "_finalized_epoch", AsyncMock(return_value=1))
    release = AsyncMock()
    monkeypatch.setattr(service, "release", release)
    sender = Mock(
        drain=AsyncMock(),
        close=AsyncMock(),
        send=AsyncMock(side_effect=AssertionError("No SOURCE provider IO")),
        metadata=AsyncMock(side_effect=AssertionError("No SOURCE metadata IO")),
    )
    monkeypatch.setattr(model_sender, "ModelSender", lambda path: sender)
    monkeypatch.setattr(ProviderVault, "quiescent", lambda vault: True)
    ctl = Mock()
    task_joined = False

    async def active() -> None:
        nonlocal task_joined
        try:
            await asyncio.Future[None]()
        finally:
            task_joined = True

    async def failed_settlement() -> None:
        raise ValueError("SOURCE settlement failure")

    def command() -> ModelTestControl:
        return ModelTestControl(
            op="model_test",
            action="start",
            operation_id=str(uuid4()),
            expected_selection_revision=1,
            consent=True,
        )

    @asynccontextmanager
    async def control(*args: object, **kwargs: object) -> AsyncIterator[Mock]:
        assert kwargs == {"native_prepare": None, "native_task": None}
        yield ctl

    class Cycles:
        cycles = 0

        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            self.cycles += 1
            return self.cycles > 5

        async def wait(self) -> None:
            nonlocal state
            callback = ctl.model_test
            assert isinstance(callback, MethodType)
            owner = callback.__self__
            assert isinstance(owner, ApiKeyModelTest)
            if self.cycles == 3:
                assert heartbeat.await_count == 2
                opened = await service.open(
                    uuid4(), state.generation, owner.settings.owner, owner.settings.epoch
                )
                state = state.model_copy(
                    update={
                        "generation": opened,
                        "admission_open": True,
                        "shutdown_command_id": None,
                        "quiesced_generation": None,
                        "quiesced_at": None,
                    }
                )
                connection.execute.reset_mock()
                with pytest.raises(ModelConflict, match="^REVISION_CONFLICT$"):
                    await callback(command())
                assert any(
                    "FROM public.provider_selection_revision" in str(call.args[0])
                    for call in connection.execute.await_args_list
                )  # Missing selection is reached only inside real admission, without provider IO.
                assert sender.drain.await_count == int(historical_shutdown)
                if ending == "stop":
                    owner.spawn(active())
                    await asyncio.sleep(0)
                    shutdown_id = uuid4()
                    stopped = await service.shutdown(
                        shutdown_id, state.generation, owner.settings.owner, owner.settings.epoch
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
                elif ending == "settlement-failure":
                    owner.spawn(failed_settlement())
                    await asyncio.gather(*owner.tasks, return_exceptions=True)
                    assert owner.settlement_failed
                else:
                    refusal = ControlConflict(ControlCode.LEASE_LOST)
                    require_owner.side_effect = refusal
                    with pytest.raises(ControlConflict, match="LEASE_LOST"):
                        await callback(command())
                    heartbeat.side_effect = refusal
            elif self.cycles > 3:
                if ending == "stop":
                    assert owner.closing and task_joined and not owner.tasks
                else:
                    assert owner.settlement_failed
                with pytest.raises(ModelConflict, match="^CONTROL_UNAVAILABLE$"):
                    await callback(command())
            raise TimeoutError

    monkeypatch.setattr(asyncio, "Event", Cycles)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.setattr(consumer, "LocalControl", control)
    for key in (
        "OMNIS_RUNTIME_DIR",
        "OMNIS_RUNTIME_INERT_PROBE",
        "OMNIS_RUNTIME_CASE_ID",
        "OMNIS_RUNTIME_STATE_ROOT",
        "OMNIS_NATIVE_PREPARATION_CATALOG_ROOT",
        "OMNIS_MANAGED_TASKS",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "OMNIS_DATABASE_URL": "synthetic",
        "OMNIS_CONTROL_DIR": str(tmp_path / "control"),
        "OMNIS_VAULT_DIR": str(tmp_path / "vault"),
        "OMNIS_VAULT_KEY_DIR": str(tmp_path / "keys"),
        "OMNIS_MODEL_EGRESS_DIR": "/vault",
    }.items():
        monkeypatch.setenv(key, value)
    if ending == "settlement-failure":
        with pytest.raises(ValueError, match="Model operation drain uncertain"):
            await consumer.run()
        release.assert_not_awaited()
    else:
        if ending == "owner-loss":
            with pytest.raises(ControlConflict, match="LEASE_LOST"):
                await consumer.run()
        else:
            await consumer.run()
        release.assert_awaited_once()
        sender.close.assert_awaited_once()
    with pytest.raises(ModelConflict, match="^CONTROL_UNAVAILABLE$"):
        await ctl.model_test(command())
    sender.send.assert_not_awaited()
    sender.metadata.assert_not_awaited()
    engine.dispose.assert_awaited_once()
    assert not list(tmp_path.iterdir())


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "OWNED_STATUS",
        "QUIESCE",
        "VALID",
        "COMMIT_ERROR",
        "STATUS_ERROR",
        "DB_ERROR",
        "POSTCHECK",
        "DIAG_ERROR",
        "SERIALIZE_ERROR",
        "WRITE_ERROR",
        "CLOCK_JUMP",
        "NEXT_HEARTBEAT",
    ],
)
async def test_idle_lease_boundary_source_trace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    """SOURCE clocks/SQL doubles; real loop, locks, heartbeat and owner checks, not incident proof."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from omnis.modules.instance import service as instance_service
    from omnis.modules.instance.domain import ControlCode, ControlConflict
    from omnis.modules.runs import model_test_runtime
    from omnis.modules.settings import provider_key_service, provider_vault
    from omnis.supervisor import model_sender

    owner = uuid4()
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    elapsed = 0
    transaction = 0
    primary = SQLAlchemyError("PRIVATE_SQL_EXCEPTION_CANARY")
    delayed = failure in {"OWNED_STATUS", "QUIESCE", "DIAG_ERROR", "SERIALIZE_ERROR", "WRITE_ERROR"}
    queries: list[str] = []
    instance: dict[str, object] = dict(
        id=1,
        instance_id=uuid4(),
        admission_open=True,
        generation=1,
        shutdown_command_id=None,
        quiesced_generation=None,
        quiesced_at=None,
    )
    lease: dict[str, object] = dict(
        id=1,
        owner=owner,
        epoch=1,
        expires_at=origin + timedelta(seconds=5),
    )

    async def execute(statement: object, params: object = None) -> Mock:
        nonlocal elapsed
        query = str(statement)
        queries.append(query)
        elapsed += 10
        result = Mock()
        if query == "SELECT * FROM instance_control WHERE id = 1 FOR UPDATE":
            result.mappings.return_value.one.return_value = dict(instance)
        elif query == "SELECT * FROM supervisor_lease WHERE id = 1 FOR UPDATE":
            result.mappings.return_value.one.return_value = dict(lease)
        elif query == "SELECT clock_timestamp()":
            result.scalar_one.return_value = origin + timedelta(
                milliseconds=elapsed,
                seconds=6 if failure == "CLOCK_JUMP" and transaction == 4 else 0,
            )
        elif query.startswith("SELECT min(owner_epoch)"):
            if failure == "STATUS_ERROR" and transaction == 4:
                raise primary
            result.scalar_one.return_value = None
        elif query == (
            "UPDATE supervisor_lease SET expires_at = GREATEST(expires_at, "
            "clock_timestamp() + interval '5 seconds') WHERE id = 1"
        ):
            lease["expires_at"] = origin + timedelta(milliseconds=elapsed, seconds=5)
            if failure == "POSTCHECK":
                elapsed += 6000
        else:
            raise AssertionError("Unexpected SOURCE SQL")
        return result

    connection = Mock(execute=AsyncMock(side_effect=execute))

    @asynccontextmanager
    async def begin() -> AsyncIterator[Mock]:
        nonlocal transaction, elapsed
        transaction += 1
        elapsed += 20
        if delayed and transaction == (5 if failure == "QUIESCE" else 4):
            elapsed += 6000  # SOURCE acquisition delay, never an operator fault.
        if failure == "NEXT_HEARTBEAT" and transaction == 6:
            elapsed += 6000
        if failure == "DB_ERROR" and transaction == 4:
            raise primary
        yield connection
        elapsed += 30  # SOURCE context commit/connection-return latency.
        if failure == "COMMIT_ERROR" and transaction == 3:
            raise primary
        if transaction == 3:
            instance["generation"] = 2  # Takes the real post-start quiesce branch.

    engine = Mock(begin=begin, dispose=AsyncMock())
    service = instance_service.InstanceService(engine)
    monkeypatch.setattr(service, "acquire", AsyncMock(return_value=1))
    monkeypatch.setattr(service, "release", AsyncMock())
    monkeypatch.setattr(
        instance_service,
        "time",
        Mock(
            monotonic_ns=lambda: elapsed * 1_000_000,
            time_ns=lambda: (
                1_000_000_000_000
                + elapsed * 1_000_000
                + (6_000_000_000 if failure == "CLOCK_JUMP" and transaction == 4 else 0)
            ),
        ),
    )
    settings = Mock(drain=AsyncMock(return_value=True))
    model = Mock(reconcile=AsyncMock(), drain=AsyncMock(return_value=True))
    sender = Mock(close=AsyncMock())
    monkeypatch.setattr(provider_key_service, "ProviderSettingsOwner", lambda *args: settings)
    monkeypatch.setattr(provider_vault, "ProviderVault", lambda *args: Mock())
    monkeypatch.setattr(model_test_runtime, "ApiKeyModelTest", lambda *args: model)
    monkeypatch.setattr(model_sender, "ModelSender", lambda *args: sender)

    @asynccontextmanager
    async def control(*args: object, **kwargs: object) -> AsyncIterator[Mock]:
        try:
            yield Mock()
        finally:
            assert instance_service._lease_trace.get() is None

    class OneCycle:
        cycles = 0

        def set(self) -> None:
            pass

        def is_set(self) -> bool:
            self.cycles += 1
            return self.cycles > (2 if failure == "NEXT_HEARTBEAT" else 1)

        async def wait(self) -> None:
            raise TimeoutError

    monkeypatch.setattr(asyncio, "Event", OneCycle)
    monkeypatch.setattr(consumer, "uuid4", lambda: owner)
    monkeypatch.setattr(consumer, "database_engine", lambda raw: engine)
    monkeypatch.setattr(consumer, "InstanceService", lambda raw: service)
    monkeypatch.setattr(consumer, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(consumer, "LocalControl", control)
    for key in (
        "OMNIS_RUNTIME_DIR",
        "OMNIS_RUNTIME_INERT_PROBE",
        "OMNIS_RUNTIME_CASE_ID",
        "OMNIS_RUNTIME_STATE_ROOT",
        "OMNIS_NATIVE_PREPARATION_CATALOG_ROOT",
        "OMNIS_MANAGED_TASKS",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "OMNIS_DATABASE_URL": "PRIVATE_DSN_CANARY",
        "OMNIS_CONTROL_DIR": "/PRIVATE_PATH_CANARY",
        "OMNIS_VAULT_DIR": "/vault",
        "OMNIS_VAULT_KEY_DIR": "/vault-key",
        "OMNIS_MODEL_EGRESS_DIR": "/vault",
    }.items():
        monkeypatch.setenv(key, value)
    if failure == "DIAG_ERROR":
        monkeypatch.setattr(
            instance_service.LeaseTrace, "mark", Mock(side_effect=RuntimeError("PRIVATE_DIAG"))
        )
    elif failure == "SERIALIZE_ERROR":
        monkeypatch.setattr(
            instance_service.LeaseTrace, "line", Mock(side_effect=RuntimeError("PRIVATE_DIAG"))
        )
    elif failure == "WRITE_ERROR":
        original_write = sys.stderr.write

        def write(line: str) -> int:
            if line.startswith("SUPERVISOR_LEASE_TRACE "):
                raise OSError("PRIVATE_DIAG")
            return original_write(line)

        monkeypatch.setattr(sys.stderr, "write", write)
    if failure == "VALID":
        await consumer.run()
        assert capsys.readouterr().err == ""
        assert sum(query.startswith("UPDATE") for query in queries) == 1
        assert transaction == 5
        assert instance_service._lease_trace.get() is None
        return
    db_error = failure in {"COMMIT_ERROR", "STATUS_ERROR", "DB_ERROR"}
    with pytest.raises(SQLAlchemyError if db_error else ControlConflict) as raised:
        await consumer.run()
    if db_error:
        assert raised.value is primary
    else:
        assert isinstance(raised.value, ControlConflict)
        assert raised.value.code is ControlCode.LEASE_LOST
    lines = capsys.readouterr().err.splitlines(keepends=True)
    phase = "HEARTBEAT" if failure in {"POSTCHECK", "COMMIT_ERROR", "NEXT_HEARTBEAT"} else "QUIESCE"
    kind = "DB_ERROR" if db_error else "CONTROL_CONFLICT"
    assert lines[0] == f"SUPERVISOR_FAILURE phase={phase} error={kind}\n"
    if failure in {"DIAG_ERROR", "SERIALIZE_ERROR", "WRITE_ERROR"}:
        assert len(lines) == 1
        return
    assert len(lines) == 2, "Missing precise caller/code/lease timing from the real producer"
    assert lines[1].startswith("SUPERVISOR_LEASE_TRACE ")
    trace = json.loads(lines[1].removeprefix("SUPERVISOR_LEASE_TRACE "))
    caller = (
        "HEARTBEAT"
        if phase == "HEARTBEAT"
        else ("QUIESCE" if failure == "QUIESCE" else "OWNED_STATUS")
    )
    assert trace["phase"] == caller
    assert trace["code"] == (None if db_error else "LEASE_LOST")
    assert len(lines[1].encode()) <= 4096
    assert "PRIVATE" not in lines[1] and str(owner) not in lines[1]
    if failure in {"POSTCHECK", "COMMIT_ERROR"}:
        assert trace["heartbeat"] == []  # UPDATE acknowledgement is not successful commit.
    else:
        assert [row[1] for row in trace["heartbeat"]] == [
            "UPDATE",
            "UPDATED",
            "LIVE_RESULT",
            "COMMIT",
            "TX_DONE",
        ]
        assert trace["heartbeat"][-1][2] - trace["heartbeat"][-2][2] == 30
    events = [row for row in trace["events"] if row[0] == caller]
    assert events[-1][1] == "TX_ERROR"
    if failure == "COMMIT_ERROR":
        assert events[-2][1] == "COMMIT"
    elif failure == "DB_ERROR":
        assert [row[1] for row in events] == ["CONNECT", "TX_ERROR"]
    elif failure == "STATUS_ERROR":
        assert "STATUS" in [row[1] for row in events]
        assert "STATUS_DONE" not in [row[1] for row in events]
    else:
        assert [row[1] for row in events][-2:] == ["ROLLBACK", "TX_ERROR"]
        refused = [row for row in events if row[1] == "LIVE_RESULT"][-1]
        assert refused[4] > refused[5]  # Existing DB clock and locked snapshot only.
        assert next(row for row in events if row[1] == "OWNER")[6:] == [True, True]
        if failure in {"OWNED_STATUS", "QUIESCE", "CLOCK_JUMP"}:
            assert events[1][2] - events[0][2] == (20 if failure == "CLOCK_JUMP" else 6020)
            assert events[1][3] - events[0][3] == 6020
            assert events[2][2] - events[1][2] == 10  # instance lock
            assert events[3][2] - events[2][2] == 10  # lease lock
    assert sum(query.startswith("UPDATE") for query in queries) == 1
    assert all("RETURNING" not in query for query in queries)
    if failure == "QUIESCE":
        status_steps = [row[1] for row in trace["events"] if row[0] == "OWNED_STATUS"]
        assert status_steps == [
            "CONNECT",
            "CONNECTED",
            "INSTANCE_LOCKED",
            "LEASE_LOCKED",
            "OWNER",
            "LIVE",
            "LIVE_RESULT",
            "OWNER_OK",
            "STATUS",
            "LIVE",
            "LIVE_RESULT",
            "STATUS_DONE",
            "COMMIT",
            "TX_DONE",
        ], "The intervening status acquisition/locks must survive the bounded idle-cycle ring"
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_lease_trace_bounds_and_task_isolation_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SOURCE extreme clocks/canaries; exercise the emitted serializer, not a length estimate."""
    import json

    from omnis.modules.instance import service as module
    from omnis.modules.instance.domain import ControlCode, ControlConflict
    from omnis.modules.instance.records import LeaseRecord

    elapsed = 0
    monkeypatch.setattr(
        module,
        "time",
        Mock(
            monotonic_ns=lambda: elapsed,
            time_ns=lambda: -elapsed,
        ),
    )
    trace = module.LeaseTrace()
    assert module._lease_trace.get() is None
    module._lease_mark("CONNECT")
    assert not trace.events
    with trace.cycle():
        trace.phase = "HEARTBEAT"
        module._lease_mark("UPDATE")
        elapsed = 10**30
        for _ in range(100):
            module._lease_mark("UPDATED")
        for step in ("LIVE_RESULT", "COMMIT", "TX_DONE"):
            module._lease_mark(step)
        assert len(trace.heartbeat) == 5, "Heartbeat anchor must have a finite shape"
        anchor = list(trace.heartbeat)
        before = list(trace.events)

        async def inherited_child() -> None:
            assert module._lease_trace.get() is trace
            lease = LeaseRecord(
                id=1, owner=uuid4(), epoch=1, expires_at=datetime(2026, 1, 2, tzinfo=UTC)
            )
            connection = Mock(
                execute=AsyncMock(
                    return_value=Mock(
                        scalar_one=Mock(return_value=datetime(2026, 1, 1, tzinfo=UTC)),
                    )
                )
            )
            service = module.InstanceService(Mock())
            assert lease.owner is not None
            await service._require_owner(connection, lease, lease.owner, 1)
            with pytest.raises(ControlConflict):
                await service._require_owner(connection, lease, uuid4(), 1)
            connection.execute.assert_awaited_once()

        await asyncio.create_task(inherited_child())
        assert list(trace.events) == before and trace.heartbeat == anchor
        trace.phase = "OWNED_STATUS"
        mismatched = LeaseRecord(
            id=1, owner=uuid4(), epoch=1, expires_at=datetime(2026, 1, 2, tzinfo=UTC)
        )
        connection = Mock(execute=AsyncMock())
        with pytest.raises(ControlConflict):
            await module.InstanceService(Mock())._require_owner(connection, mismatched, uuid4(), 2)
        connection.execute.assert_not_awaited()  # Preserve owner/epoch short-circuit; no DB clock.
        owner_row = trace.events[-2]
        assert owner_row[1] == "OWNER" and owner_row[4] is None
        assert owner_row[5] == int(datetime(2026, 1, 2, tzinfo=UTC).timestamp() * 1000)
        assert owner_row[6:] == [False, False]
        for _ in range(100):
            module._lease_mark("INSTANCE_LOCKED", now=datetime.min.replace(tzinfo=UTC))
        assert len(trace.events) == trace.MAX_EVENTS and trace.clipped
        assert trace.heartbeat == anchor
        assert trace.events[-1][2:4] == [trace.MAX_ELAPSED_MS, -trace.MAX_ELAPSED_MS]
        module._lease_mark("PRIVATE_EVENT_CANARY")
        trace.phase = "PRIVATE_PHASE_CANARY"
        module._lease_mark("OWNER")
        trace.phase = "OWNED_STATUS"
        failure = ControlConflict(ControlCode.LEASE_LOST)
        failure.args = ("PRIVATE_EXCEPTION_CANARY",)
        assert "PRIVATE" not in trace.line(failure)
        monkeypatch.setattr(failure, "code", "PRIVATE_CODE_CANARY")
        assert (
            json.loads(trace.line(failure).removeprefix("SUPERVISOR_LEASE_TRACE "))["code"] is None
        )
    assert module._lease_trace.get() is None
    with trace.cycle():
        assert not trace.events and trace.heartbeat == anchor
        trace.phase = "HEARTBEAT"
        module._lease_mark("CONNECT")
        module._lease_mark("TX_ERROR")
        assert trace.heartbeat == anchor  # Failure before the next UPDATE cannot erase it.

    # All fields at their maximum encoded width, including optional numeric DB fields.
    longest_phase = max(trace.PHASES, key=len)
    longest_step = max(trace.STEPS, key=len)
    row: list[object] = [
        longest_phase,
        longest_step,
        -trace.MAX_ELAPSED_MS,
        -trace.MAX_ELAPSED_MS,
        -trace.MAX_DB_MS,
        -trace.MAX_DB_MS,
        False,
        False,
    ]
    trace.phase = longest_phase
    trace.events.clear()
    trace.events.extend([row] * trace.MAX_EVENTS)
    trace.heartbeat = [row] * 5  # Conservative: longer labels than the five real anchor labels.
    trace.clipped = trace.incomplete = False  # JSON false is longer than true.
    code = max(ControlCode, key=lambda item: len(item.value))
    line = trace.line(ControlConflict(code))
    assert len(line.encode("utf-8")) <= 4096
    assert line.count("\n") == 1 and line.endswith("\n")
    assert json.loads(line.removeprefix("SUPERVISOR_LEASE_TRACE "))["code"] == code.value
    print(f"SOURCE maximum conservative serialized trace: {len(line.encode('utf-8'))} bytes")
