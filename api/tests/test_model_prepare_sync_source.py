"""SOURCE cold prepare: real callers/UDS/Host/peer, storage and model reply doubles.

Never installed Hermes, PostgreSQL, provider authentication or native-turn evidence.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from omnis_hermes import managed_admission_contract as contract
from omnis_hermes.runtime_host import RuntimeHost
from omnis_hermes.runtime_host import TestLaunch as Launch
from omnis_hermes.runtime_protocol import NativePeer
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.instance.service import RuntimeAuthority
from omnis.modules.runs.model_test import REQUESTED, ModelTest
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor.native_tasks import control_task
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable
from omnis.transport import local_control
from test_model_test_prepare_source import prepared_source


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["fast", "cold", "expiry", "stop", "disconnect"])
async def test_cold_prepare_waits_through_real_callers(
    tmp_path: Path, ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    import sys

    owner, _, _, manifest, _ = await prepared_source(tmp_path, monkeypatch)
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "owner_id": owner.owner,
            "manifest_ref": manifest,
            "action": "model_test_prepare",
            "initialization_id": str(uuid4()),
            "settings_operation_id": str(uuid4()),
        }
    )
    events: list[str] = []
    grants: list[int] = []
    failures: list[str] = []
    ready = asyncio.Event()
    directory = ipc_directory / "r"
    directory.mkdir(mode=0o700)
    assert len(str(directory / "runtime.sock").encode()) < 108
    peer_fixture = Path(__file__).resolve().parents[2] / "integrations/hermes/tests/peer_fixture.py"
    host = RuntimeHost(
        directory,
        _test_launch=Launch(
            (
                sys.executable,
                "-I",
                "-B",
                str(peer_fixture),
                "normal" if case == "fast" else "slow_ready",
            ),
            directory,
        ),
    )
    runtime = owner.runtime
    host.boot = runtime.boot
    host.generation, host.epoch, host.state = 0, 1, "MANAGEMENT"
    host.settings_task = Mock(done=Mock(return_value=True))
    host.settings_result = {
        "status": "CONFIRMED",
        "operation_id": command.settings_operation_id,
        "selection": REQUESTED,
    }
    original_stop, original_handshake, original_call = (
        host.stop,
        NativePeer.handshake,
        NativePeer.call,
    )
    original_exchange, original_persist = runtime._exchange, ModelTest.persist

    async def readback(value: dict[str, object]) -> dict[str, object]:
        await asyncio.sleep(0.9)  # SOURCE pre-grant DB/readback work, not authority lifetime.
        return {"manifest_ref": manifest}

    async def grant(
        lease: UUID, epoch: int, generation: int, *, inert_probe: bool = False
    ) -> RuntimeAuthority:
        assert lease == owner.lease and (epoch, generation, inert_probe) == (1, 0, True)
        assert owner.events[-1] == "commit"
        events.append("COMMIT_BEFORE_GRANT")
        deadline = time.monotonic_ns() + (600_000_000 if case == "expiry" else 4_500_000_000)
        grants.append(deadline)
        return RuntimeAuthority(generation, epoch, deadline)

    async def committed_callback(
        operation: str, authority: RuntimeAuthority, payload: dict[str, object]
    ) -> dict[str, object]:
        assert operation == "task_model_initialize"
        assert mapping(payload["context"]) in owner.graph
        events.append("COMMITTED_SOURCE_READBACK")
        await asyncio.sleep(0.4)  # After grant, as in the real QA's independent PG callback.
        host.deadline_ns = authority.deadline_ns
        try:
            return await original_exchange(operation, authority, payload)
        except RuntimeUnavailable as error:
            failures.append(type(error.__context__).__name__)
            if type(error.__context__) is TimeoutError:
                events.append("CLIENT_EXCHANGE_TIMEOUT")
            raise

    async def saved_read(action: str, selected: object) -> dict[str, object]:
        assert action == "read" and selected is None
        events.append("SAVED_READ")
        await asyncio.sleep(1.2)
        return dict(REQUESTED)

    async def stop() -> None:
        if host.process is None:
            # No management subprocess in SOURCE; launched peer cleanup stays real.
            host.state = "STOPPED"
        else:
            await original_stop()

    async def handshake(
        peer: NativePeer, *, ready_timeout: float | None = None
    ) -> dict[str, object]:
        events.append("HANDSHAKE_ENTER")
        ready.set()
        try:
            result = await original_handshake(peer, ready_timeout=ready_timeout)
        except asyncio.CancelledError:
            events.append("HANDSHAKE_CANCELLED")
            print(
                f"SOURCE_CANCEL_GRANT_REMAINING_NS={host.deadline_ns - time.monotonic_ns()} "
                f"PEER_FAILURE={peer.failure is not None}"
            )
            raise
        events.append("HANDSHAKE_COMPLETED")
        return result

    async def call(
        peer: NativePeer, method: str, params: dict[str, object], *, timeout: float | None = None
    ) -> object:
        if method != contract.RPC["task_model_initialize"]:
            return await original_call(peer, method, params, timeout=timeout)
        if params["mode"] == "CLOSE":
            events.append("SOURCE_CLOSE_REPLY")
            return {**params, "status": "CLOSED_JOINED"}
        events.append("SOURCE_MODEL_REPLY")
        context = mapping(mapping(params["context"])["payload"])
        return contract.preparation_result(
            params,
            native_root_id=str(uuid4()),
            native_child_id=str(uuid4()),
            native_session_id="SOURCE-peer",
            native_turn={"task_id": context["task_id"], "turn_id": "SOURCE-turn"},
        )

    async def persist(
        consumer: ModelTest,
        connection: AsyncConnection,
        who: str,
        payload: dict[str, object],
        observation: object,
    ) -> dict[str, object]:
        await asyncio.sleep(0.2)  # SOURCE post-exchange persistence/commit work.
        result = await original_persist(consumer, connection, who, payload, observation)
        events.append("PERSISTED_SOURCE")
        return result

    monkeypatch.setattr(owner.handler.domain, "readback", readback)
    monkeypatch.setattr(owner.handler.service, "runtime_authority", grant)
    monkeypatch.setattr(runtime, "managed", RuntimeClient.managed.__get__(runtime))
    monkeypatch.setattr(runtime, "settings_status", AsyncMock(return_value=host.settings_result))
    monkeypatch.setattr(runtime, "_exchange", committed_callback)
    monkeypatch.setattr(host, "_settings_native", saved_read)
    monkeypatch.setattr(host, "stop", stop)
    monkeypatch.setattr(NativePeer, "handshake", handshake)
    monkeypatch.setattr(NativePeer, "call", call)
    monkeypatch.setattr(ModelTest, "persist", persist)
    monkeypatch.setattr(local_control, "readiness_reason", AsyncMock(return_value=None))
    owner.handler.service.engine = owner.handler.domain.engine
    runtime.directory = directory
    host.deadline_ns = time.monotonic_ns() + 4_500_000_000
    sender: asyncio.Task[dict[str, object]] | None = None
    started = time.monotonic()
    try:
        async with host:
            await runtime.connect()
            async with local_control.LocalControl(
                ipc_directory,
                owner.handler.service,
                owner.lease,
                1,
                native_task=owner.handler.handle,
            ) as local:
                sender = asyncio.create_task(
                    control_task(ipc_directory, command.model_dump(mode="json"))
                )
                if case in {"stop", "disconnect"}:
                    await asyncio.wait_for(ready.wait(), 4)
                    if case == "stop":
                        await host.stop()
                    else:
                        await runtime.close()  # Real owner EOF cancels Host's in-flight operation.
                if case in {"fast", "cold"}:
                    answer = await sender
                    assert answer["preparation_status"] == "TURN_BOUND_PRE_CLIENT_HOLD"
                    assert answer["inference_status"] == "HOLD"
                    assert answer["account_status"] == "NOT_VERIFIED"
                    assert "PERSISTED_SOURCE" in events
                    assert "CLIENT_EXCHANGE_TIMEOUT" not in events
                    assert "HANDSHAKE_CANCELLED" not in events
                    assert len([r for r in owner.graph if r["kind"] == "native-turn"]) == 1
                else:
                    with pytest.raises(CatalogError, match="^TASK_INDETERMINATE$"):
                        await sender
                    assert "SOURCE_MODEL_REPLY" not in events
                    assert "PERSISTED_SOURCE" not in events
                    assert not any(r["kind"] == "native-turn" for r in owner.graph)
                assert len(grants) == 1
                owner.reserve.assert_not_awaited()
                await runtime.close()
                async with asyncio.timeout(2):
                    while host.owner_writer is not None:
                        await asyncio.sleep(0.005)
                assert not local.clients
    finally:
        if sender is not None:
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
        await runtime.close()
        print(f"SOURCE_SYNC_CASE={case} EVENTS={events} FAILURE_CONTEXT={failures}")
    assert not host.clients and host.lock_fd is None
    assert not (directory / "runtime.sock").exists() and not (directory / "runtime.boot").exists()
    assert (
        not (ipc_directory / "control.sock").exists()
        and not (ipc_directory / "control.cap").exists()
    )
    if host.process is not None:
        assert (
            host.process.returncode is not None and not Path(f"/proc/{host.process.pid}").exists()
        )
    print(
        f"SOURCE_SYNC_ELAPSED_S={time.monotonic() - started:.3f} OWNED_PEER_REAPED=True ENDPOINTS_ABSENT=True"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation,protocol,mode,expected",
    [
        ("task_model_initialize", "omnis-managed-admission-v5", "CREATE", 5.5),
        ("task_model_initialize", "omnis-managed-admission-v5", "STATUS", 3.2),
        ("task_model_initialize", "omnis-managed-admission-v3", "CREATE", 3.2),
        ("task_stage", "omnis-managed-admission-v5", "CREATE", 3.2),
    ],
)
async def test_cold_wait_is_finite_and_does_not_extend_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    protocol: str,
    mode: str,
    expected: float,
) -> None:
    """Timeout-selection control only; synthetic frames are not native payload positives."""
    client = RuntimeClient(tmp_path, generation=0, epoch=1)
    writer = Mock(spec=asyncio.StreamWriter)
    client.reader, client.writer = Mock(spec=asyncio.StreamReader), writer
    timeout = asyncio.timeout
    waits: list[float] = []

    def observed_wait(seconds: float) -> asyncio.Timeout:
        waits.append(seconds)
        return timeout(seconds)

    class Captured(BaseException):
        pass

    writer.write.side_effect = Captured()
    monkeypatch.setattr(time, "monotonic_ns", lambda: 10_000_000_000)
    monkeypatch.setattr(asyncio, "timeout", observed_wait)
    with pytest.raises(Captured):
        await client._exchange_locked(
            operation,
            RuntimeAuthority(0, 1, 14_500_000_000),
            {"protocol": protocol, "mode": mode},
        )
    assert waits == [expected]
    writer.write.assert_called_once()
