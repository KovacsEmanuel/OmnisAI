"""Actual v5 producer/serializers with SOURCE storage, never native or PG evidence."""

import json
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from fixtures.b06b_publication.consumer import Seed
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_test import REQUESTED, ModelTest
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping
from test_contract_method_producer import batch2_source
from test_owned_model_initialization import SourceOwner


def test_send_diagnostic_keeps_public_catalog_reason_only() -> None:
    import test_contract_method_pg as qa

    for reason in (
        "TASK_UNAVAILABLE",
        "TASK_REJECTED",
        "TASK_INDETERMINATE",
        "COMMAND_CONFLICT",
        "CONTROL_TIMEOUT",
        "CONTROL_UNAVAILABLE",
        "LEASE_LOST",
        "INVALID_REQUEST",
    ):
        assert qa.launch_exception_chain(CatalogError(reason)) == [
            {"type": "CatalogError", "reason": reason}
        ]
    assert qa.launch_exception_chain(CatalogError("PRIVATE_SEND_REASON")) == [
        {"type": "CatalogError", "reason": "UNCLASSIFIED"}
    ]
    from omnis.supervisor.runtime_client import RuntimeUnavailable

    assert qa.launch_exception_chain(RuntimeUnavailable("Runtime authority mismatch")) == [
        {"type": "RuntimeUnavailable", "reason": "Runtime authority mismatch"}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["reply", "exchange", "before", "after", "timeout"])
@pytest.mark.parametrize("broken_diagnostic", [False, True])
async def test_send_diagnostic_real_callback_and_control_arm(
    outcome: str, broken_diagnostic: bool
) -> None:
    """Real QA callback/control arm; only exchange, PG readback and control are doubles."""
    import ast
    import asyncio
    from collections.abc import Awaitable, Callable
    from contextlib import suppress
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import test_contract_method_pg as qa
    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.supervisor.runtime_client import RuntimeUnavailable

    tree = ast.parse(Path(qa.__file__).read_bytes())
    callback = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "committed_execution"
    )
    branch = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "model_execute" and callback in n.body
    )
    start = branch.body.index(callback)
    end = next(
        i for i, n in enumerate(branch.body) if ast.unparse(n).startswith("assert len(sends)")
    )
    probe = cast(ast.AsyncFunctionDef, ast.parse("async def probe(): pass").body[0])
    probe.body = branch.body[start:end] + ast.parse("return mt_result").body
    proof: dict[str, object] = {}
    marker = "PRIVATE_SEND_PAYLOAD"
    primary: BaseException = (
        TimeoutError(marker) if outcome == "timeout" else CatalogError("TASK_REJECTED")
    )
    refusal = RuntimeUnavailable("Runtime exchange unavailable")
    inner = RuntimeUnavailable("Runtime refused")
    refusal.__context__ = inner
    reply: dict[str, object] = {"state": "SETTLED", "private": marker}
    packet: dict[str, object] = {"private": marker}
    payload = {**packet, "mode": "SEND"}
    engine = MagicMock()
    consumer = SimpleNamespace(
        replay_execution=AsyncMock(return_value={}),
        execution_receipt=AsyncMock(return_value={"state": "SENT", "usage_state": "UNKNOWN"}),
        execution_packet=AsyncMock(return_value=packet),
    )
    exchanges = 0

    def checkpoint(**fields: object) -> None:
        if broken_diagnostic and "model_execute_commit" not in fields:
            raise RuntimeError(marker)
        proof.update(fields)

    async def actual_exchange(*args: object) -> dict[str, object]:
        nonlocal exchanges
        assert args == ("task_model_initialize", None, payload) and args[2] is payload
        exchanges += 1
        if outcome == "exchange":
            raise refusal
        return reply

    runtime = SimpleNamespace(_exchange=actual_exchange)

    async def control_task(*args: object) -> dict[str, object]:
        if outcome == "before":
            raise primary
        if exchanges and outcome == "timeout":
            raise primary
        try:
            answer = await runtime._exchange("task_model_initialize", None, payload)
        except RuntimeUnavailable:
            raise primary from None
        if outcome == "after":
            raise primary
        return {"state": "SENT"} if outcome == "timeout" else answer

    scope: dict[str, object] = {
        "asyncio": asyncio,
        "suppress": suppress,
        "RuntimeAuthority": RuntimeAuthority,
        "runtime": runtime,
        "actual_exchange": actual_exchange,
        "checkpoint": checkpoint,
        "launch_exception_chain": qa.launch_exception_chain,
        "monkeypatch": pytest.MonkeyPatch(),
        "control_task": control_task,
        "directory": None,
        "request_send": {},
        "engine": engine,
        "NativeTaskCommand": SimpleNamespace(model_validate=lambda value: value),
        "ModelTest": lambda domain: consumer,
        "domain": None,
        "seed": SimpleNamespace(owner="SOURCE"),
        "sends": [],
        "canonical": canonical,
        "mapping": mapping,
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[])),
            qa.__file__,
            "exec",
        ),
        scope,
    )
    invoke = cast(Callable[[], Awaitable[dict[str, object]]], scope["probe"])
    if outcome == "reply":
        assert await invoke() is reply
    else:
        with pytest.raises(BaseException) as caught:
            await invoke()
        assert caught.value is primary
        assert primary.__context__ is (refusal if outcome == "exchange" else None)
        assert refusal.__context__ is inner and inner.__context__ is None
    if broken_diagnostic:
        assert set(proof) == (set() if outcome == "before" else {"model_execute_commit"})
    else:
        assert proof["model_execute_exchange"] == (
            {"point": "NOT_ENTERED"}
            if outcome == "before"
            else {
                "point": "EXCHANGE_FAILED",
                "exceptions": [
                    {"type": "RuntimeUnavailable", "reason": "Runtime exchange unavailable"},
                    {"type": "RuntimeUnavailable", "reason": "Runtime refused"},
                ],
            }
            if outcome == "exchange"
            else {"point": "REPLY_RETURNED"}
        )
        if outcome != "reply":
            expected_control = [
                {
                    "type": "TimeoutError" if outcome == "timeout" else "CatalogError",
                    "reason": "UNCLASSIFIED" if outcome == "timeout" else "TASK_REJECTED",
                }
            ]
            if outcome == "exchange":
                expected_control.extend(
                    [
                        {"type": "RuntimeUnavailable", "reason": "Runtime exchange unavailable"},
                        {"type": "RuntimeUnavailable", "reason": "Runtime refused"},
                    ]
                )
            assert proof["model_execute_control_error"] == {
                "point": "SETTLEMENT_WAIT" if outcome == "timeout" else "CONTROL_REQUEST",
                "exceptions": expected_control,
            }
    assert marker not in canonical(proof).decode()
    assert engine.connect.call_count == (0 if outcome == "before" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("producer", ["heartbeat-only", "stock", "qa"])
@pytest.mark.parametrize("finish", ["expiry", "stop"])
@pytest.mark.parametrize("state", ["READY", "MANAGEMENT"])
async def test_model_prepare_qa_owner_preserves_host_until_intentional_stop(
    tmp_path: Path,
    ipc_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    producer: str,
    finish: str,
    state: str,
) -> None:
    """SOURCE owner/Host/UDS/observer; storage, native child and signal are doubles."""
    import ast
    import asyncio
    import os
    import sys
    from collections import deque
    from collections.abc import Awaitable, Callable, Coroutine
    from concurrent.futures import Future
    from types import CodeType, ModuleType, SimpleNamespace
    from unittest.mock import Mock
    from uuid import UUID

    from omnis_hermes import managed_admission_contract as contract
    from omnis_hermes import runtime_host
    from omnis_hermes.runtime_protocol import NativePeer

    import test_contract_method_pg as qa
    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.supervisor import runtime_client
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable

    tree = ast.parse(Path(qa.__file__).read_bytes())
    maintain = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "maintain_owner"
    )
    loop = cast(ast.While, maintain.body[0])
    if producer != "qa":
        loop.body = [loop.body[0], loop.body[-1]]
    if producer == "stock":
        stock = ast.parse((qa.ROOT / "api/src/omnis/supervisor/__main__.py").read_bytes())
        tick = next(
            n
            for n in ast.walk(stock)
            if isinstance(n, ast.ExceptHandler)
            and any(isinstance(c, ast.Attribute) and c.attr == "quiesce" for c in ast.walk(n))
        )
        work = next(n for n in tick.body if isinstance(n, ast.Try))
        heartbeat = next(
            i
            for i, n in enumerate(work.body)
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Await)
            and isinstance(n.value.value, ast.Call)
            and isinstance(n.value.value.func, ast.Attribute)
            and n.value.value.func.attr == "heartbeat"
        )
        loop.body[:1] = work.body[heartbeat:]

    clock = [10_000_000_000]
    monkeypatch.setattr(runtime_host, "time", SimpleNamespace(monotonic_ns=lambda: clock[0]))
    monkeypatch.setattr(runtime_client, "time", SimpleNamespace(monotonic_ns=lambda: clock[0]))
    host = runtime_host.RuntimeHost(ipc_directory)
    done = asyncio.Event()
    service = Mock(heartbeat=AsyncMock(), quiesce=AsyncMock())
    service.owned_status = AsyncMock(return_value=SimpleNamespace(generation=0))
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, clock[0] + 4_500_000_000)
    )
    process = Mock(pid=12345, returncode=None, wait=AsyncMock(return_value=0))
    monkeypatch.setattr(host, "_owned_pids", lambda: set())
    monkeypatch.setattr(os, "killpg", lambda *a: setattr(process, "returncode", 0))
    close = {
        "protocol": contract.PROTOCOL_V5,
        "mode": "CLOSE",
        "context_ref": {
            "id": str(uuid4()),
            "kind": "model-test-context",
            "revision": 1,
            "digest": "a" * 64,
        },
    }
    peer = object.__new__(NativePeer)
    peer.failure, peer.queued_bytes, peer.next_id, peer.timeout = None, 0, 0, 0.8
    peer.queue, peer.pending, peer.late = asyncio.Queue(32), {}, deque(maxlen=32)
    peer.bootstrap_inventory = {
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
    }
    monkeypatch.setattr(peer, "close", AsyncMock())
    observation = tmp_path / "native-observation.jsonl"
    observation.touch()
    root = ModuleType("run_agent")
    exec(
        compile("class AIAgent:\n def close(self): pass\n", str(tmp_path / "run_agent.py"), "exec"),
        root.__dict__,
    )
    monkeypatch.setitem(sys.modules, "run_agent", root)
    child = root.AIAgent()
    future: Future[None] = Future()
    child._model_test_preparation = contract.ModelTestPreparation.__new__(
        contract.ModelTestPreparation
    )
    child._model_test_record = SimpleNamespace(future=future)
    child._model_test_closed = __import__("threading").Event()

    def emit(test: str, status: str) -> None:
        with observation.open("ab") as output:
            output.write(canonical({"test": test, "status": status, "count": 1}) + b"\n")

    observer = {"sys": sys, "managed": tmp_path, "CodeType": CodeType, "emit": emit}
    exec(qa.MODEL_PREPARE_OBSERVER, observer)
    observe = cast(Callable[[object, str], bool], observer["prepare_observe"])

    def deliver(frame: dict[str, object]) -> None:
        assert host.state == "STOPPING" and mapping(frame["params"]) == close
        # The existing observer receives the exact SOURCE child code/carrier.
        frame_double = SimpleNamespace(
            f_code=root.AIAgent.close.__code__, f_locals={"self": child}, f_back=None
        )
        observe(frame_double, "call")
        child._model_test_closed.set()
        future.set_result(None)
        observe(frame_double, "return")
        peer.pending[(int, peer.next_id)].set_result({**close, "status": "CLOSED_JOINED"})

    monkeypatch.setattr(peer, "_enqueue", deliver)
    ticks = 0

    async def interval(wait: Coroutine[None, None, bool], timeout: float) -> None:
        nonlocal ticks
        assert timeout == 0.5
        wait.close()
        ticks += 1
        clock[0] += 500_000_000
        await asyncio.sleep(0.03)  # Yield to the real 25ms watchdog, not a grant extension.
        if host.state == "STOPPING":
            async with asyncio.timeout(1), host.stop_lock:
                pass
        if ticks == 12:
            done.set()
        raise TimeoutError

    async with host:
        host.state, host.epoch, host.generation = state, 1, 0
        host.deadline_ns = clock[0] + 4_500_000_000
        original_deadline = host.deadline_ns
        host.process, host.peer, host.model_preparation_close = process, peer, canonical(close)
        runtime = RuntimeClient(ipc_directory, generation=0, epoch=1)
        await runtime.connect()
        supervisor = uuid4()
        task_owner = NativeTaskOwner(ManagedAdmission(Mock()), service, supervisor, 1, runtime)
        scope = {
            "asyncio": SimpleNamespace(wait_for=interval),
            "done": done,
            "service": service,
            "supervisor": supervisor,
            "epoch": 1,
            "runtime": runtime,
            "model_prepare": True,
            "model_execute": False,
            "task_owner": task_owner,
            "startup_generation": 0,
            "probe": None,
        }
        scope["owner"] = scope["supervisor"]
        exec(compile(ast.Module(body=[maintain], type_ignores=[]), qa.__file__, "exec"), scope)
        invoke = cast(Callable[[], Awaitable[None]], scope["maintain_owner"])
        try:
            await invoke()
            assert clock[0] > original_deadline and service.heartbeat.await_count == 12
            if producer == "heartbeat-only":
                assert future.done() and host.state == "UNCERTAIN"
                assert [
                    json.loads(row)["status"] for row in observation.read_bytes().splitlines()
                ] == ["ENTERED", "COMPLETED"]
            else:
                assert host.state == state and observation.read_bytes() == b""
                assert not future.done() and service.runtime_authority.await_count == 12
                assert all(
                    call.kwargs
                    == ({"management": True} if state == "MANAGEMENT" else {"inert_probe": True})
                    for call in service.runtime_authority.await_args_list
                )
            calls = service.runtime_authority.await_count
            await invoke()  # doneEvent prevents renewal after the intentional Stop frontier.
            assert service.runtime_authority.await_count == calls
            if finish == "expiry":
                clock[0] = host.deadline_ns
                async with asyncio.timeout(1):
                    while host.state in {"READY", "MANAGEMENT", "STOPPING"}:
                        await asyncio.sleep(0.001)
            else:
                assert (await runtime._exchange("stop"))["state"] == "UNCERTAIN"
            assert future.done() and host.model_close_evidence == canonical(
                {**close, "status": "CLOSED_JOINED"}
            )
            with pytest.raises(RuntimeUnavailable):
                await runtime.renew(service, cast(UUID, scope["supervisor"]))
            assert observation.read_bytes().count(b"prepare-close") == 2
            if producer == "stock":
                assert service.owned_status.await_count == 12
                service.quiesce.assert_not_awaited()
        finally:
            await task_owner.close_model_test()
            assert task_owner.model_test_closing
            await runtime.close()
    assert not host.clients and host.watchdog is not None and host.watchdog.done()
    assert not (ipc_directory / "runtime.sock").exists()
    assert not (ipc_directory / "runtime.boot").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "false", "exception", "missing-close"])
async def test_model_prepare_qa_shutdown_drains_before_closed_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    """Execute the real QA Stop arm and RuntimeClient drain; DB/Host are doubles."""
    import ast
    import asyncio
    from collections.abc import Awaitable, Callable
    from types import SimpleNamespace

    from omnis_hermes.managed_admission_contract import validate_model_close_result

    import test_contract_method_pg as qa
    from omnis.supervisor.runtime_client import RuntimeClient

    tree = ast.parse(Path(qa.__file__).read_bytes())
    baseline = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "mt_native_closed" for t in n.targets)
    )
    arm = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and baseline in n.body)
    start = next(i for i, n in enumerate(arm.body) if ast.unparse(n) == "done.set()")
    end = next(
        i
        for i, n in enumerate(arm.body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "mt_close_evidence" for t in n.targets)
    )
    probe = cast(ast.AsyncFunctionDef, ast.parse("async def probe(): pass").body[0])
    probe.body = arm.body[start : end + 1] + ast.parse("return mt_close_evidence").body
    events: list[str] = []
    done = asyncio.Event()
    context = {"kind": "model-test-context", "id": str(uuid4()), "revision": 1, "digest": "a" * 64}
    close = {
        "protocol": "omnis-managed-admission-v5",
        "mode": "CLOSE",
        "context_ref": context,
        "status": "CLOSED_JOINED",
    }

    async def joined() -> None:
        assert done.is_set()
        events.append("joined")

    heartbeat = asyncio.create_task(joined())

    async def shutdown(*args: object) -> None:
        assert heartbeat.done() and events == ["joined"]
        events.append("fenced")

    async def exchange(operation: str) -> dict[str, object]:
        assert operation == "stop" and events == ["joined", "fenced"]
        events.append("drain-enter")
        await asyncio.sleep(0)
        assert events[-1] == "drain-enter"  # No observation before the awaited barrier.
        if fault == "exception":
            raise RuntimeError("SOURCE_DRAIN_FAILURE")
        events.append("drain-return")
        return {"drained": fault != "false"}

    async def status() -> dict[str, object]:
        drained = "drain-return" in events and fault != "false"
        return {
            "state": "STOPPED" if drained else "READY",
            "drained": drained,
            "model_preparation_close": None if fault == "missing-close" else close,
        }

    def read() -> bytes:
        events.append("baseline")
        return b"SOURCE-observation"

    runtime = RuntimeClient(tmp_path, generation=0, epoch=1)
    stop = AsyncMock(side_effect=exchange)
    monkeypatch.setattr(runtime, "_exchange", stop)
    monkeypatch.setattr(runtime, "status", AsyncMock(side_effect=status))
    replay = AsyncMock()
    scope: dict[str, object] = {
        "done": done,
        "heartbeat": heartbeat,
        "service": SimpleNamespace(shutdown=shutdown),
        "uuid4": uuid4,
        "status": SimpleNamespace(generation=0),
        "supervisor": uuid4(),
        "epoch": 1,
        "runtime": runtime,
        "observation": SimpleNamespace(read_bytes=read),
        "native_after": b"SOURCE-observation",
        "control_task": replay,
        "directory": tmp_path,
        "request_prepare": {},
        "mt_answer": {"context_ref": context},
        "validate_model_close_result": validate_model_close_result,
    }
    exec(compile(ast.Module(body=[probe], type_ignores=[]), qa.__file__, "exec"), scope)
    invoke = cast(Callable[[], Awaitable[object]], scope["probe"])
    if fault is None:
        assert await invoke() == close
        assert events == ["joined", "fenced", "drain-enter", "drain-return", "baseline"]
    else:
        expected: type[Exception] = RuntimeError if fault == "exception" else AssertionError
        if fault == "missing-close":
            expected = ValueError
        with pytest.raises(expected):
            await invoke()
        stop.assert_awaited_once_with("stop")
        if fault != "missing-close":
            assert "baseline" not in events
            replay.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execute,authenticated",
    [(False, "LOCAL_PRESENT"), (True, "LOCAL_PRESENT"), (True, "ABSENT"), (True, "NOT_VERIFIED")],
)
async def test_model_test_qa_settings_sequence(
    tmp_path: Path,
    ipc_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    execute: bool,
    authenticated: str,
) -> None:
    """Actual QA AST/Client/Host/owner; authority, storage and native lifecycle are SOURCE doubles."""
    import ast
    import asyncio
    import time
    from collections.abc import Awaitable, Callable
    from unittest.mock import Mock

    from omnis_hermes.managed_admission_contract import preparation_result
    from omnis_hermes.runtime_host import RuntimeHost

    import test_contract_method_pg as qa
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.modules.tasks import managed_store as store
    from omnis.supervisor.runtime_client import RuntimeClient

    tree = ast.parse(Path(qa.__file__).read_bytes())
    arm = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "model_prepare"
        and any(
            isinstance(child, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "settings_id" for t in child.targets)
            for child in node.body
        )
    )
    start = next(
        i for i, node in enumerate(arm.body) if ast.unparse(node).startswith("settings_id =")
    )
    branch = next(
        node
        for node in arm.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "model_execute"
    )
    end = next(
        i for i, node in enumerate(branch.body) if ast.unparse(node).startswith("mt_answer =")
    )
    branch.body = branch.body[: end + 1]
    probe = cast(ast.AsyncFunctionDef, ast.parse("async def probe(): pass").body[0])
    probe.body = arm.body[start : arm.body.index(branch) + 1]
    module = ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[]))

    owner, _, _, manifest, _ = await prepared_source(tmp_path, monkeypatch)
    monkeypatch.setattr(
        owner.handler.domain, "readback", AsyncMock(return_value={"manifest_ref": manifest})
    )
    host = RuntimeHost(ipc_directory)
    runtime = owner.runtime
    runtime.directory = ipc_directory
    # SourceOwner normally replaces managed IPC; this regression uses the real Client/Host.
    monkeypatch.setattr(runtime, "managed", RuntimeClient.managed.__get__(runtime))
    monkeypatch.setattr(
        owner.handler.service,
        "runtime_authority",
        AsyncMock(
            side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
        ),
    )
    selected: object = None
    actions: list[str] = []
    operations: list[str] = []
    payloads: list[dict[str, object]] = []

    async def native_settings(action: str, selection: object) -> object:
        nonlocal selected
        actions.append(action)
        if action == "save":
            selected = selection
        if action == "auth_read":
            return {"selection": selected, "authenticated": authenticated}
        return selected

    async def stopped() -> None:
        host.state = "STOPPED"
        host.process, host.peer = None, None

    async def native_call(
        operation: str, payload: dict[str, object], *, timeout: float
    ) -> dict[str, object]:
        assert operation == "omnis.managed.model_initialize"
        assert 0 < timeout <= 4.5
        assert owner.events[-1] == "commit"
        payloads.append(payload)
        return preparation_result(
            payload,
            native_root_id=str(uuid4()),
            native_child_id=str(uuid4()),
            native_session_id="SOURCE-settings-session",
            native_turn={
                "task_id": mapping(mapping(payload["context"])["payload"])["task_id"],
                "turn_id": "SOURCE-settings-turn",
            },
        )

    async def launched(body: dict[str, object]) -> None:
        host.state, host.deadline_ns = "READY", cast(int, body["deadline_ns"])
        host.process = Mock(returncode=None)
        host.peer = Mock(
            failure=None,
            bootstrap_inventory={
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
            call=AsyncMock(side_effect=native_call),
        )

    monkeypatch.setattr(host, "_settings_native", native_settings)
    monkeypatch.setattr(host, "stop", AsyncMock(side_effect=stopped))
    monkeypatch.setattr(host, "_launch", AsyncMock(side_effect=launched))
    original_get = store.get

    async def owned(conn: AsyncConnection, who: str, pin: object) -> tuple[str, dict[str, object]]:
        item = next(r for r in owner.graph if records.reference(r) == pin)
        run = str(mapping(item["payload"]).get("run_id", owner.run))
        return run, await original_get(conn, who, run, pin)

    monkeypatch.setattr(store, "owned", owned)

    async def control_task(directory: Path, request: dict[str, object]) -> dict[str, object]:
        operations.append(str(request["settings_operation_id"]))
        assert directory == ipc_directory and request["action"] == "model_test_start"
        current = mapping(host.settings_result)
        assert current["authenticated"] == "LOCAL_PRESENT" and current["inference_ready"] is False
        assert request["settings_operation_id"] == current["operation_id"]
        assert runtime.boot == host.boot
        stale = next(identity for identity in host.settings_seen if identity != operations[0])
        assert (await runtime.settings_status(stale))["status"] == "UNAVAILABLE"
        command = NativeTaskCommand.model_validate(request)
        before = canonical(owner.graph)
        with pytest.raises(CatalogError, match="^MODEL_TEST_SETTINGS_REQUIRED$"):
            await owner.handler.handle(command.model_copy(update={"settings_operation_id": stale}))
        assert canonical(owner.graph) == before and payloads == []
        answer = await owner.handler.handle(command)
        host.settings_result = {**current, "operation_id": stale}
        try:
            with pytest.raises(ValueError, match="^Owned saved Settings readback required$"):
                await host._managed(
                    {
                        "payload": payloads[0],
                        "op": "task_model_initialize",
                        "epoch": 1,
                        "generation": 0,
                        "deadline_ns": time.monotonic_ns() + 4_000_000_000,
                    }
                )
        finally:
            host.settings_result = current
        context = next(r for r in owner.graph if records.reference(r) == answer["context_ref"])
        assert mapping(context["payload"])["settings_operation_id"] == operations[0]
        assert (
            mapping(mapping(payloads[0]["context"])["payload"])["settings_operation_id"]
            == operations[0]
        )
        before = canonical(owner.graph)
        assert await owner.handler.handle(command) == answer
        with pytest.raises(CatalogError, match="^COMMAND_CONFLICT$"):
            await owner.handler.handle(command.model_copy(update={"settings_operation_id": stale}))
        assert canonical(owner.graph) == before and len(payloads) == 1
        return answer

    scope: dict[str, object] = {
        "asyncio": asyncio,
        "uuid4": uuid4,
        "runtime": runtime,
        "service": owner.handler.service,
        "supervisor": owner.lease,
        "REQUESTED": REQUESTED,
        "model_execute": execute,
        "lifecycle": {**owner.base, "owner_id": owner.owner, "manifest_ref": manifest},
        "directory": ipc_directory,
        "control_task": control_task,
    }
    exec(compile(module, qa.__file__, "exec"), scope)
    invoke = cast(Callable[[], Awaitable[None]], scope["probe"])
    async with host:
        await runtime.connect()
        try:
            if execute and authenticated != "LOCAL_PRESENT":
                with pytest.raises(AssertionError):
                    await invoke()
                assert host.settings_result is not None
                assert host.settings_result["authenticated"] == authenticated
                assert actions == ["save", "auth_read"] and not operations and not payloads
                request = next(
                    node for node in branch.body if ast.unparse(node).startswith("request_start =")
                )
                scope["settings_id"] = host.settings_result["operation_id"]
                exec(
                    compile(ast.Module(body=[request], type_ignores=[]), qa.__file__, "exec"), scope
                )
                with pytest.raises(CatalogError, match="^TASK_INDETERMINATE$"):
                    await owner.handler.handle(
                        NativeTaskCommand.model_validate(scope["request_start"])
                    )
                assert actions == ["save", "auth_read", "read", "auth_read"] and not payloads
                cast(AsyncMock, host._launch).assert_not_awaited()
            else:
                await invoke()
                assert actions == (
                    ["save", "auth_read", "read", "auth_read"] if execute else ["save"]
                )
                assert len(operations) == len(payloads) == int(execute)
                assert host.settings_result is not None
                assert host.settings_result["inference_ready"] is False
        finally:
            await runtime.close()
    owner.reserve.assert_not_awaited()


async def prepared_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, padding: str = "", objective_suffix: str = ""
) -> tuple[SourceOwner, ModelTest, AsyncConnection, dict[str, object], dict[str, object]]:
    from fixtures import c03_records

    seed = c03_records.records_seed

    def authored(root: Path) -> Seed:
        result = seed(root)
        path = result.package / "templates/procedures/map-records.yaml"
        if objective_suffix:
            path.write_text(
                path.read_text().replace(
                    "objective: Map supplied structured synthetic records.",
                    "objective: Map supplied structured synthetic records." + objective_suffix,
                )
            )
        # Comments are real retained source bytes, not an invented v5 payload.
        with path.open("a") as output:
            output.write("\n# " + padding + "\n")
        return result

    monkeypatch.setattr(c03_records, "records_seed", authored)

    build = ManagedAdmission._build

    async def one_task(
        domain: ManagedAdmission, connection: AsyncConnection, who: str, request: dict[str, object]
    ) -> list[dict[str, object]]:
        return await build(domain, connection, who, {**request, "task_count": 1})

    # v5 consumes one original task; do not spend the two-task fixture's old budget.
    monkeypatch.setattr(ManagedAdmission, "_build", one_task)
    graph, bundle, source, who = await batch2_source(tmp_path / "material", monkeypatch)
    owner = SourceOwner(tmp_path, monkeypatch)
    owner.owner = who
    owner.graph[:] = graph
    owner.run = str(next(r for r in graph if r["kind"] == "managed-run")["id"])
    owner.state["run_id"] = owner.run
    owner.handler.domain.root = tmp_path
    catalog_get = records.get

    async def catalog_read(
        connection: AsyncConnection, identity: str, pin: object
    ) -> tuple[str, dict[str, object]]:
        if pin == source.preparation_ref:
            return "SOURCE-CATALOG-GROUP", records.envelope(
                "native-preparation-receipt",
                {
                    "bundle_ref": records.reference(bundle),
                },
            )
        return await catalog_get(connection, identity, mapping(pin))

    monkeypatch.setattr(records, "get", catalog_read)
    connection = owner.handler.service.native_preparation_commit
    async with connection(owner.lease, 1, 0) as conn:
        pass
    consumer = ModelTest(owner.handler.domain)
    authority = {
        "instance_id": owner.instance,
        "owner": str(owner.lease),
        "epoch": 1,
        "generation": 0,
    }
    return owner, consumer, conn, records.reference(graph[-1]), authority


async def produce(
    owner: SourceOwner,
    consumer: ModelTest,
    conn: AsyncConnection,
    manifest: dict[str, object],
    authority: dict[str, object],
) -> dict[str, object]:
    from omnis.modules.instance.schemas import NativeTaskCommand

    identity, settings_id = str(uuid4()), str(uuid4())
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "owner_id": owner.owner,
            "manifest_ref": manifest,
            "action": "model_test_prepare",
            "initialization_id": identity,
            "settings_operation_id": settings_id,
        }
    )
    context, created = await consumer.prepare(
        conn,
        owner.owner,
        manifest,
        identity,
        settings_id,
        {"status": "CONFIRMED", "selection": REQUESTED},
        authority,
        str(owner.runtime.boot),
        command,
    )
    assert created
    payload, observation = await consumer.dispatch(conn, owner.owner, context, True)
    assert observation is None
    return payload


@pytest.mark.parametrize(
    "applicability,expected",
    [
        ("model-test-execute", True),
        ("model-test-prepare", True),
        ("owned-initialization", True),
        ("mission-consumer", True),
        ("result-qualification", True),
        ("evidence-full", True),
        ("partial-requirement-prefix", True),
        (None, False),
        ("support-zero", False),
    ],
)
def test_model_test_public_listener_selection(applicability: str | None, expected: bool) -> None:
    """Evaluate the actual listener guard without creating a listener, DB or child."""
    import ast

    source = Path(__file__).with_name("test_contract_method_pg.py")
    tree = ast.parse(source.read_bytes())
    guards = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and any(
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "public_control"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Await)
            and isinstance(statement.value.value, ast.Call)
            and isinstance(statement.value.value.func, ast.Attribute)
            and statement.value.value.func.attr == "__aenter__"
            and isinstance(statement.value.value.func.value, ast.Call)
            and isinstance(statement.value.value.func.value.func, ast.Name)
            and statement.value.value.func.value.func.id == "LocalControl"
            for statement in node.body
        )
    ]
    assert len(guards) == 1
    scope = {"h03": False, "batch2": False, "h04": None, "applicability": applicability}
    assert eval(compile(ast.Expression(guards[0].test), str(source), "eval"), scope) is expected


@pytest.mark.parametrize("encoding", ["text", "binary", "string"])
@pytest.mark.parametrize("fault", [None, "run_id", "attempt_id", "batch_index", "state"])
def test_model_prepare_committed_task_identity(encoding: str, fault: str | None) -> None:
    """Run the existing QA assertion against real driver values, without PG/native."""
    import ast

    from psycopg.types.uuid import UUIDBinaryLoader, UUIDLoader

    import test_contract_method_pg as owner

    tree = ast.parse(Path(owner.__file__).read_bytes())
    callbacks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "committed_prepare"
    ]
    assert len(callbacks) == 1
    assertions = [
        node
        for node in ast.walk(callbacks[0])
        if isinstance(node, ast.Assert)
        and {"run_id", "attempt_id", "batch_index", "state"}
        <= {
            item.slice.value
            for item in ast.walk(node)
            if isinstance(item, ast.Subscript)
            and isinstance(item.value, ast.Name)
            and item.value.id == "task"
            and isinstance(item.slice, ast.Constant)
        }
    ]
    assert len(assertions) == 1
    code = compile(ast.Module(body=[assertions[0]], type_ignores=[]), owner.__file__, "exec")
    identities = {"run_id": uuid4(), "attempt_id": uuid4()}
    context = {key: str(value) for key, value in identities.items()}
    task: dict[str, object] = {
        "batch_index": 1 if fault == "batch_index" else 0,
        "state": "RUNNING" if fault == "state" else "QUEUED",
    }
    for key, value in identities.items():
        if fault == key:
            value = uuid4()
        task[key] = {
            "text": UUIDLoader(2950).load(str(value).encode()),
            "binary": UUIDBinaryLoader(2950).load(value.bytes),
            "string": str(value),
        }[encoding]
    scope = {"task": task, "mt_context": context}
    if fault is None:
        exec(code, scope)
    else:
        with pytest.raises(AssertionError):
            exec(code, scope)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "padding", ["", 'ă雪😀"\\' * 80], ids=["canonical", "escaped-unicode-quotes"]
)
async def test_actual_v5_producer_serializers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, padding: str
) -> None:
    owner, consumer, conn, manifest, authority = await prepared_source(
        tmp_path, monkeypatch, padding, 'ă雪😀"\\' if padding else ""
    )
    payload = await produce(owner, consumer, conn, manifest, authority)
    validate_initialization = import_module(
        "omnis_hermes.managed_admission_contract"
    ).validate_initialization
    encode = import_module("omnis_hermes.runtime_protocol").encode

    assert validate_initialization(payload) == payload
    native = encode(
        {
            "jsonrpc": "2.0",
            "id": 2**63 - 1,
            "method": "omnis.managed.model_initialize",
            "params": payload,
        }
    )
    host = encode(
        {
            "version": 1,
            "id": "f" * 36,
            "boot": "f" * 36,
            "capability": "f" * 64,
            "generation": 2**63 - 1,
            "epoch": 2**63 - 1,
            "deadline_ns": 2**63 - 1,
            "op": "task_model_initialize",
            "payload": payload,
        }
    )
    assert len(canonical(payload)) <= 32768
    assert len(native) <= 65536 and len(host) <= 65536
    assert json.loads(native)["params"] == json.loads(host)["payload"] == payload
    owner.reserve.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_prepare_manifest_negative_uses_actual_qa_oracle(
    tmp_path: Path, ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual retained SOURCE reply/UDS and consumer assertion; no PG/native proof."""
    import ast

    import test_contract_method_pg as qa
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.supervisor.native_tasks import NativeTaskOwner, control_task
    from omnis.transport import local_control
    from test_owned_model_initialization import (
        test_model_test_prepare_owns_fresh_qualified_context_and_holds,
    )

    captured: list[tuple[NativeTaskOwner, NativeTaskCommand, dict[str, object]]] = []
    handle = NativeTaskOwner.handle

    async def capture(self: NativeTaskOwner, command: NativeTaskCommand) -> dict[str, object]:
        answer = await handle(self, command)
        captured.append((self, command, answer))
        return answer

    with monkeypatch.context() as producer:
        producer.setattr(NativeTaskOwner, "handle", capture)
        await test_model_test_prepare_owns_fresh_qualified_context_and_holds(
            tmp_path, producer, False
        )
        handler, command, expected = captured[0]
        handler.service.engine = handler.domain.engine
        producer.setattr(local_control, "readiness_reason", AsyncMock(return_value=None))
        async with local_control.LocalControl(
            ipc_directory, handler.service, handler.owner, handler.epoch, native_task=handler.handle
        ):
            answer = await control_task(ipc_directory, command.model_dump(mode="json"))
            assert {k: v for k, v in answer.items() if k != "correlation_id"} == expected
            tree = ast.parse(Path(qa.__file__).read_bytes())
            loops = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.For)
                and any(
                    isinstance(target, ast.Name) and target.id == "mt_changed"
                    for target in ast.walk(node.target)
                )
            ]
            assert len(loops) == 1
            loop = loops[0]
            scope: dict[str, object] = {
                "mapping": mapping,
                "uuid4": uuid4,
                "lifecycle": command.model_dump(mode="json"),
                "pytest": pytest,
                "CatalogError": CatalogError,
                "control_task": control_task,
                "directory": ipc_directory,
                "request_prepare": command.model_dump(mode="json"),
            }
            rows = eval(compile(ast.Expression(loop.iter), qa.__file__, "eval"), scope)
            assert len(rows) == 3
            # Run only the demonstrated manifest guard, not identity-blind fixture denials.
            loop.iter = ast.Name(id="manifest_row", ctx=ast.Load())
            scope["manifest_row"] = rows[2:]
            probe = cast(ast.AsyncFunctionDef, ast.parse("async def probe(): pass").body[0])
            probe.body = [
                ast.For(target=loop.target, iter=loop.iter, body=[loop.body[0]], orelse=[])
            ]
            module = ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[]))
            exec(compile(module, qa.__file__, "exec"), scope)
            from collections.abc import Awaitable, Callable

            await cast(Callable[[], Awaitable[None]], scope["probe"])()


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_reason", [None, "TASK_REJECTED", "PRIVATE_OWNER_REASON"])
async def test_model_execute_budget_negative_uses_actual_qa_oracle(
    tmp_path: Path, ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, wrong_reason: str | None
) -> None:
    """Real QA callback/loop and LocalControl/control_task UDS; owner/PG/SDK doubled."""
    import ast
    from collections.abc import Awaitable, Callable

    import test_contract_method_pg as qa
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.supervisor.native_tasks import control_task
    from omnis.transport import local_control

    owner = SourceOwner(tmp_path, monkeypatch)
    handler = owner.handler
    handler.service.engine = handler.domain.engine
    decision = {
        "decision_id": str(uuid4()),
        "composition_ref": {**records.reference(owner.manifest), "kind": "prompt-composition"},
        "approved_text_digests": ["a" * 64],
    }
    request_send = {
        **owner.base,
        "action": "model_test_send",
        "initialization_id": str(uuid4()),
        "protocol_id": str(uuid4()),
        "data_approval": decision,
    }

    async def deny(command: NativeTaskCommand) -> dict[str, object]:
        reason = "COMMAND_CONFLICT"
        if command.protocol_id != request_send["protocol_id"]:
            reason = wrong_reason or "MODEL_BUDGET_EXHAUSTED"
        raise CatalogError(reason)

    handle = AsyncMock(side_effect=deny)
    monkeypatch.setattr(handler, "handle", handle)
    monkeypatch.setattr(local_control, "readiness_reason", AsyncMock(return_value=None))
    proof: dict[str, object] = {}
    scope: dict[str, object] = {
        "NativeTaskCommand": NativeTaskCommand,
        "CatalogError": CatalogError,
        "owner": handler,
        "checkpoint": lambda **fields: proof.update(fields),
        "proof": proof,
        "LocalControl": local_control.LocalControl,
        "directory": ipc_directory,
        "service": handler.service,
        "supervisor": handler.owner,
        "epoch": handler.epoch,
        "applicability": "model-test-execute",
        "model_execute": True,
        "pytest": pytest,
        "uuid4": uuid4,
        "decision": decision,
        "request_send": request_send,
        "control_task": control_task,
    }
    tree = ast.parse(Path(qa.__file__).read_bytes())
    callback = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "observe_native_task"
    )
    listener = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "LocalControl"
        and any(k.arg == "native_task" for k in n.keywords)
    )
    loop = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.For) and "mt_execution_changes" in ast.unparse(n.target)
    )
    probe = cast(ast.AsyncFunctionDef, ast.parse("async def probe(): pass").body[0])
    probe.body = [loop]
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[callback, probe], type_ignores=[])),
            qa.__file__,
            "exec",
        ),
        scope,
    )
    listener_instance = cast(
        local_control.LocalControl,
        eval(compile(ast.Expression(listener), qa.__file__, "eval"), scope),
    )
    invoke = cast(Callable[[], Awaitable[None]], scope["probe"])
    async with listener_instance:
        if wrong_reason is None:
            await invoke()
            assert handle.await_count == 2
        else:
            with pytest.raises(AssertionError, match="^MODEL_EXECUTION_OWNER_REASON_MISMATCH$"):
                await invoke()
            assert handle.await_count == 1
            assert mapping(proof["public_owner_error"])["reason"] != "MODEL_BUDGET_EXHAUSTED"
    assert "PRIVATE_OWNER_REASON" not in canonical(proof).decode()


@pytest.mark.asyncio
async def test_actual_v5_producer_limit_before_first_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, consumer, conn, manifest, authority = await prepared_source(
        tmp_path, monkeypatch, "x" * 5000
    )
    before = canonical(owner.graph)
    cast(AsyncMock, conn.execute).reset_mock()
    with pytest.raises(CatalogError, match="^MODEL_TEST_LIMIT$"):
        await produce(owner, consumer, conn, manifest, authority)
    assert canonical(owner.graph) == before
    assert [str(call.args[0]) for call in cast(AsyncMock, conn.execute).await_args_list] == [
        "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"
    ]
    owner.native.assert_not_awaited()
    owner.reserve.assert_not_awaited()


def test_settings_operation_types_and_actual_control_layout() -> None:
    from pydantic import ValidationError

    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.settings.provider_models import ProviderCommand, SettingsControl

    identity = str(uuid4())
    command = ProviderCommand.model_validate(
        {"operation_id": identity, "action": "save", "selection": REQUESTED}
    )
    control = SettingsControl(op="settings", command=command, operation_id=identity)
    assert len(command.model_dump_json().encode()) < 3600
    assert len(control.model_dump_json().encode()) < 3600
    invalid: tuple[object, ...] = (True, 1, {}, "x" * 36)
    for value in invalid:
        with pytest.raises(ValidationError):
            ProviderCommand.model_validate(
                {"operation_id": value, "action": "save", "selection": REQUESTED}
            )
    # NativeTaskCommand validates operation UUIDs and exact ref revision types.
    base = {
        "op": "native_task",
        "schema_version": 1,
        "owner_id": identity,
        "command_id": identity,
        "instance_id": identity,
        "expected_epoch": 1,
        "expected_generation": 0,
        "action": "model_test_prepare",
        "initialization_id": identity,
        "settings_operation_id": identity,
        "manifest_ref": {
            "kind": "launch-manifest",
            "id": identity,
            "revision": 1,
            "digest": "a" * 64,
        },
    }
    assert NativeTaskCommand.model_validate(base).settings_operation_id == identity
    for key, value in (("settings_operation_id", True), ("settings_operation_id", "x" * 36)):
        with pytest.raises((ValidationError, CatalogError)):
            NativeTaskCommand.model_validate({**base, key: value})
    bad = deepcopy(base)
    bad["manifest_ref"] = {**mapping(bad["manifest_ref"]), "revision": True}
    with pytest.raises((ValidationError, CatalogError)):
        NativeTaskCommand.model_validate(bad)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overflow", [False, True], ids=["producer-MAX32768", "resealed-negative-MAXplus1"]
)
async def test_actual_producer_exact_aggregate_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overflow: bool
) -> None:
    owner, consumer, conn, manifest, authority = await prepared_source(
        tmp_path, monkeypatch, "x" * 4838, "X"
    )
    validate_initialization = import_module(
        "omnis_hermes.managed_admission_contract"
    ).validate_initialization

    from omnis.modules.runs import model_test

    original_envelope = records.envelope
    if overflow:

        def negative(kind: str, body: dict[str, object]) -> dict[str, object]:
            if kind == "run-snapshot" and body.get("execution_purpose") == "MODEL_TEST_PREPARE":
                body = {**body, "created_by": str(body["created_by"]) + "x"}
            return original_envelope(kind, body)

        monkeypatch.setattr(records, "envelope", negative)
    sizes: list[int] = []
    samples: list[dict[str, object]] = []
    original_qualify = model_test.qualify

    def observed(payload: object) -> dict[str, object]:
        sizes.append(len(canonical(payload)))
        samples.append(deepcopy(mapping(payload)))
        return original_qualify(payload)

    monkeypatch.setattr(model_test, "qualify", observed)
    before = canonical(owner.graph)
    cast(AsyncMock, conn.execute).reset_mock()
    if overflow:
        with pytest.raises(CatalogError, match="^MODEL_TEST_LIMIT$"):
            await produce(owner, consumer, conn, manifest, authority)
        assert sizes == [32769]
        assert canonical(owner.graph) == before
        assert [str(call.args[0]) for call in cast(AsyncMock, conn.execute).await_args_list] == [
            "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"
        ]
    else:
        payload = await produce(owner, consumer, conn, manifest, authority)
        assert sizes == [32768, 32768]
        assert validate_initialization(payload) == payload
        assert set(payload) == {"protocol", "mode", "context", "records", "material"}
        assert (
            len(cast(list[object], payload["records"])) == 7
            and mapping(payload["material"])["bundle"]
        )
    import asyncio
    from collections import deque

    transport = import_module("omnis_hermes.runtime_protocol")
    peer = object.__new__(transport.NativePeer)
    peer.next_id, peer.pending = 2**63 - 2, {}
    if overflow:
        with pytest.raises(ValueError):
            await peer.call("omnis.managed.model_initialize", samples[0])
        assert peer.next_id == 2**63 - 2 and peer.pending == {}
    else:
        peer.failure, peer.queued_bytes, peer.timeout = None, 0, 1
        peer.queue, peer.late = asyncio.Queue(32), deque(maxlen=32)
        enqueue = peer._enqueue

        def capture(frame: dict[str, object]) -> None:
            enqueue(frame)
            peer.pending[(int, peer.next_id)].set_result("SOURCE_REPLY_DOUBLE")

        monkeypatch.setattr(peer, "_enqueue", capture)
        assert (
            await peer.call("omnis.managed.model_initialize", samples[0]) == "SOURCE_REPLY_DOUBLE"
        )
        raw, _ = peer.queue.get_nowait()
        frame = json.loads(raw)
        assert frame["id"] == 2**63 - 1 and type(frame["id"]) is int
        assert frame["params"] == samples[0] and peer.pending == {}
    owner.native.assert_not_awaited()
    owner.reserve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("overflow", [False, True], ids=["wire65536", "wire65537"])
async def test_actual_transport_serializers_exact_wire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overflow: bool
) -> None:
    """Serializer controls are mutations, NOT accepted v5 producer positives."""
    import asyncio
    from unittest.mock import Mock

    transport = import_module("omnis_hermes.runtime_protocol")
    NativePeer, ProtocolError, encode = (
        transport.NativePeer,
        transport.ProtocolError,
        transport.encode,
    )

    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable

    args = await prepared_source(tmp_path, monkeypatch)
    payload = await produce(*args)
    payload["wire_control"] = '雪"\\' * 40
    runtime = RuntimeClient(tmp_path, generation=2**63 - 1, epoch=2**63 - 1)
    runtime.boot, runtime.capability = "f" * 36, "f" * 64
    runtime.reader = Mock()
    runtime.writer = Mock()

    # Capture only at the actual writer after the real serializer/limit predicate.
    class Captured(BaseException):
        pass

    runtime.writer.write.side_effect = Captured()
    grant = RuntimeAuthority(generation=2**63 - 1, epoch=2**63 - 1, deadline_ns=2**63 - 1)
    request = {
        "version": 1,
        "id": "f" * 36,
        "boot": runtime.boot,
        "capability": runtime.capability,
        "generation": runtime.generation,
        "epoch": runtime.epoch,
        "deadline_ns": grant.deadline_ns,
        "op": "task_model_initialize",
        "payload": payload,
    }
    payload["padding"] = ""
    size = len(json.dumps(request, separators=(",", ":")).encode()) + 1
    payload["padding"] = "x" * (65536 + int(overflow) - size)
    with pytest.raises(
        RuntimeUnavailable if overflow else Captured,
        match="Runtime managed-task limit" if overflow else None,
    ):
        await runtime._exchange_locked("task_model_initialize", grant, payload)
    assert runtime.writer.write.call_count == int(not overflow)
    if not overflow:
        raw = runtime.writer.write.call_args.args[0]
        assert len(raw) == 65536
        assert json.loads(raw)["payload"] == payload
    peer = object.__new__(NativePeer)
    peer.failure, peer.queued_bytes = None, 0
    peer.queue = asyncio.Queue(32)
    native = {
        "jsonrpc": "2.0",
        "id": 2**63 - 1,
        "method": "omnis.managed.model_initialize",
        "params": payload,
    }
    payload["padding"] = ""
    size = len(json.dumps(native, separators=(",", ":")).encode()) + 1
    payload["padding"] = "x" * (65536 + int(overflow) - size)
    if overflow:
        with pytest.raises(ProtocolError, match="^Frame limit$"):
            peer._enqueue(native)
        assert peer.queue.empty() and peer.queued_bytes == 0
    else:
        peer._enqueue(native)
        raw, key = peer.queue.get_nowait()
        assert len(raw) == peer.queued_bytes == 65536 and key is None
        assert raw == encode(native)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["opaque", "public-context", "cancel", "hostile-traceback"])
@pytest.mark.parametrize("secondary", [None, "cleanup", "checkpoint"])
async def test_model_prepare_primary_error_before_real_finally(
    tmp_path: Path, failure: str, secondary: str | None
) -> None:
    """Run the consumer's actual handler/finally; substitute only resource seams."""
    import ast
    import asyncio
    import sys
    from collections.abc import Awaitable, Callable
    from types import SimpleNamespace
    from unittest.mock import Mock

    import test_contract_method_pg as owner

    tree = ast.parse(Path(owner.__file__).read_bytes())
    consumer = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_contract_method_real_native_pg_owner_receipts_check_inbox"
    )
    run = next(
        node
        for node in consumer.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run"
    )
    original = next(node for node in run.body if isinstance(node, ast.Try) and node.finalbody)
    probe = ast.parse(
        "async def probe():\n try:\n  await fail()\n except BaseException:\n  pass\n finally:\n  pass\n"
    )
    statement = cast(ast.Try, cast(ast.AsyncFunctionDef, probe.body[0]).body[0])
    statement.handlers, statement.finalbody = original.handlers, original.finalbody
    marker = "PUBLIC_SYNTHETIC_PRIVATE_PRIMARY_ERROR"

    class OpaqueFailure(RuntimeError):
        def __str__(self) -> str:
            raise AssertionError("PRIVATE_EXCEPTION_STR_EVALUATED")

        def __repr__(self) -> str:
            raise AssertionError("PRIVATE_EXCEPTION_REPR_EVALUATED")

    opaque = OpaqueFailure(marker)
    hostile = type(
        "HostileTraceback",
        (OpaqueFailure,),
        {"__traceback__": property(lambda self: SimpleNamespace(tb_lineno=marker))},
    )(marker)
    primary: BaseException = {
        "opaque": opaque,
        "public-context": ValueError("Runtime exchange unavailable"),
        "cancel": asyncio.CancelledError(marker),
        "hostile-traceback": hostile,
    }[failure]
    if failure == "public-context":
        primary.__context__ = opaque
    context = primary.__context__

    async def fail() -> None:
        raise primary

    proof: dict[str, object] = {}
    path = tmp_path / "method-history-proof.json"
    scope: dict[str, object] = {"proof": proof, "proof_path": path, "canonical": canonical}
    writer = next(
        node
        for node in consumer.body
        if isinstance(node, ast.FunctionDef) and node.name == "checkpoint"
    )
    exec(compile(ast.Module(body=[writer], type_ignores=[]), owner.__file__, "exec"), scope)
    write_checkpoint = scope["checkpoint"]
    assert callable(write_checkpoint)
    events: list[str] = []
    snapshots: list[dict[str, object]] = []

    def checkpoint(**fields: object) -> None:
        if "model_prepare_primary_error" in fields:
            events.append("primary")
            if secondary == "checkpoint":
                raise OpaqueFailure(marker)
        write_checkpoint(**fields)

    async def close() -> None:
        events.append("cleanup")
        snapshots.append(json.loads(path.read_bytes()) if path.exists() else {})
        if secondary == "cleanup":
            raise OpaqueFailure(marker)

    h03_state = {"docker_unknown": False, "reader_unknown": False, "cleanup_failed": False}
    db_fence: dict[str, object] = {"unsettled": True}
    observation = Mock()
    scope.update(
        asyncio=asyncio,
        sys=sys,
        fail=fail,
        installed_native=True,
        model_prepare=True,
        checkpoint=checkpoint,
        launch_exception_chain=owner.launch_exception_chain,
        h03_state=h03_state,
        db_fence=db_fence,
        dispatch_waiters=[],
        done=asyncio.Event(),
        heartbeat=None,
        runtime=SimpleNamespace(close=close),
        public_control=None,
        engine=SimpleNamespace(dispose=AsyncMock()),
        batch2=False,
        startup=False,
        h04=None,
        h03=False,
        host=None,
        applicability="model-test-prepare",
        require_native_observation=observation,
    )
    exec(compile(ast.fix_missing_locations(probe), owner.__file__, "exec"), scope)
    invoke = cast(Callable[[], Awaitable[None]], scope["probe"])
    with pytest.raises(BaseException) as caught:
        await invoke()
    assert caught.value is primary and primary.__context__ is context
    assert events == ["primary", "cleanup"]
    assert h03_state["cleanup_failed"] is True and db_fence["unsettled"] is True
    assert proof["status"] == "UNCERTAIN"
    assert proof["h03_resource_cleanup"] == "NOT_SETTLED_DB_RETAINED"
    observation.assert_not_called()
    if secondary == "checkpoint":
        assert "model_prepare_primary_error" not in proof
    else:
        diagnostic = mapping(proof["model_prepare_primary_error"])
        expected = {
            "opaque": [{"type": "OTHER_EXCEPTION", "reason": "UNCLASSIFIED"}],
            "public-context": [
                {"type": "ValueError", "reason": "Runtime exchange unavailable"},
                {"type": "OTHER_EXCEPTION", "reason": "UNCLASSIFIED"},
            ],
            "cancel": [{"type": "CancelledError", "reason": "UNCLASSIFIED"}],
            "hostile-traceback": [{"type": "OTHER_EXCEPTION", "reason": "UNCLASSIFIED"}],
        }[failure]
        assert set(diagnostic) == {"exceptions", "source", "consumer_line"}
        assert diagnostic["exceptions"] == expected
        assert diagnostic["source"] == "test_contract_method_pg.py"
        trace = BaseException.__dict__["__traceback__"].__get__(primary, type(primary))
        assert trace is not None and trace.tb_next is not None
        assert type(diagnostic["consumer_line"]) is int
        assert diagnostic["consumer_line"] == trace.tb_next.tb_lineno == statement.body[0].lineno
        assert snapshots == [{"model_prepare_primary_error": diagnostic}]
    assert marker not in canonical(proof).decode()


@pytest.mark.parametrize("case", ["sdk", "foreign", "argv", "hold"])
def test_model_execute_cold_sdk_metadata_is_denied_and_qualified(tmp_path: Path, case: str) -> None:
    """Real cold OpenAI/default_headers + generated audit; no request/native/exec."""
    import ast
    import subprocess
    import sys

    import test_contract_method_pg as qa

    observer = ast.parse(
        qa.batch2_native_observer(startup=False, model_prepare=True, model_execute=case != "hold")
    )
    audit = next(n for n in observer.body if isinstance(n, ast.FunctionDef) and n.name == "audit")
    script = """
import json, os, sys, platform, subprocess, openai
from pathlib import Path
assert openai.__version__ == "2.24.0"
assert not platform._platform_cache
libraries = Path(openai.__file__).parent.parent
home = Path(sys.argv[1])
allowed = (Path(sys.base_prefix), Path(sys.prefix), home)
installed = False
bootstrap_path = home / "unused.py"
rows = []
def emit(test, status, count=1):
    rows.append({"test": test, "status": status, "count": count})
"""
    script += ast.unparse(audit) + "\nsys.addaudithook(audit)\n"
    if case == "argv":
        script += """
original = subprocess.check_output
def changed_argv(args, **kwargs):
    return original(["uname", "-s"], **kwargs)
subprocess.check_output = changed_argv
"""
    if case == "foreign":
        script += """
try:
    subprocess.check_output(["uname", "-p"])
except RuntimeError as error:
    assert error.args == ("Forbidden native effect",)
else:
    raise AssertionError("SUBPROCESS_NOT_DENIED")
"""
    else:
        script += """
client = openai.OpenAI(api_key="SYNTHETIC", max_retries=0)
assert client.default_headers["X-Stainless-OS"] == "Unknown"
client.close()
"""
    script += "print(json.dumps(rows))\n"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(tmp_path)],
        capture_output=True,
        timeout=15,
        check=True,
    )
    rows = json.loads(result.stdout)
    expected = {"test": "denied-sdk-metadata", "status": "UNAME_P", "count": 1}
    assert rows == (
        [expected]
        if case == "sdk"
        else [{"test": "forbidden-effect", "status": "subprocess.Popen", "count": 1}]
    )
    prefix = [{"test": "observer", "status": "READY", "count": 1}]
    for phase in qa.BOOTSTRAP_PHASES:
        for edge in ("ENTER", "END"):
            prefix.append(
                {
                    "test": "bootstrap-phase",
                    "status": phase,
                    "count": 1,
                    "edge": edge,
                    "elapsed_ms": 0,
                    "audit_ms": 0,
                    "audit_calls": 0,
                }
            )
    path = tmp_path / "sdk-observation.jsonl"
    path.write_bytes(b"".join(canonical(row) + b"\n" for row in prefix + rows))
    if case == "sdk":
        assert qa.require_native_observation(path, model_execute=True)[-1] == expected
        with pytest.raises(AssertionError):
            qa.require_native_observation(path)
        for invalid in ([], rows * 2, [{**expected, "count": 0}]):
            path.write_bytes(b"".join(canonical(row) + b"\n" for row in prefix + invalid))
            with pytest.raises(AssertionError, match="^SDK_METADATA_DENIAL_UNCONFIRMED"):
                qa.require_native_observation(path, model_execute=True)
        qa.batch2_installed_entry(tmp_path, model_prepare=True, model_execute=True)
    else:
        with pytest.raises(AssertionError):
            qa.require_native_observation(path, model_execute=True)


@pytest.mark.parametrize("fault", [None, "caught-forbidden", "unknown-row", "unjoined-close"])
@pytest.mark.parametrize("model_execute", [False, True], ids=["hold", "execute"])
def test_model_prepare_real_early_return_finally(
    tmp_path: Path, fault: str | None, model_execute: bool
) -> None:
    """Execute the original shared finally arm, not a parallel permissive oracle."""
    import ast
    import sys
    from unittest.mock import Mock

    import test_contract_method_pg as owner

    tree = ast.parse(Path(owner.__file__).read_bytes())
    arm = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "model_prepare and sys.exc_info()[0] is None"
    )
    probe = ast.parse("def probe():\n try:\n  return 'EARLY'\n finally:\n  pass\n")
    function = cast(ast.FunctionDef, probe.body[0])
    statement = cast(ast.Try, function.body[0])
    statement.finalbody = [arm]
    rows: list[dict[str, object]] = [{"test": "observer", "status": "READY", "count": 1}]
    for phase in owner.BOOTSTRAP_PHASES:
        for edge in ("ENTER", "END"):
            rows.append(
                {
                    "test": "bootstrap-phase",
                    "status": phase,
                    "count": 1,
                    "edge": edge,
                    "elapsed_ms": 0,
                    "audit_ms": 0,
                    "audit_calls": 0,
                }
            )
    for name in (
        "configure_model_test",
        "run_conversation",
        "build_turn_context",
        "_bind_turn_identity",
        "close",
    ):
        for edge in ("ENTERED", "COMPLETED"):
            if fault == "unjoined-close" and name == "close" and edge == "COMPLETED":
                continue
            rows.append({"test": "prepare-" + name, "status": edge, "count": 1})
    if fault == "caught-forbidden":
        rows.append({"test": "forbidden-sink", "status": "MODEL_PREPARE_IDENTITY", "count": 1})
    if fault == "unknown-row":
        rows.append({"test": "UNKNOWN", "status": "UNKNOWN", "count": 1})
    if model_execute:
        rows.extend(
            [
                {"test": "denied-sdk-metadata", "status": "UNAME_P", "count": 1},
                {"test": "model-test-http", "status": "HEADERS", "count": 1},
            ]
        )
    path = tmp_path / "observation.jsonl"
    path.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))
    checkpoint = Mock()
    scope: dict[str, object] = {
        "sys": sys,
        "model_prepare": True,
        "model_execute": model_execute,
        "observation": path,
        "require_native_observation": owner.require_native_observation,
        "checkpoint": checkpoint,
    }
    exec(compile(ast.fix_missing_locations(probe), owner.__file__, "exec"), scope)
    invoke = scope["probe"]
    assert callable(invoke)
    if fault is None:
        assert invoke() == "EARLY"
        if model_execute:
            checkpoint.assert_called_once_with(
                status="PASS_MODEL_TEST_CONTROLLED_NATIVE_NOT_LIVE",
                model_execute_denied_sdk_metadata_count=1,
            )
        else:
            checkpoint.assert_called_once_with(
                status="PASS_MODEL_TEST_PREPARE_HOLD_NOT_ACCOUNT_OR_INFERENCE"
            )
    else:
        with pytest.raises(AssertionError):
            invoke()
        checkpoint.assert_not_called()


@pytest.mark.parametrize("fault", [None, "wrong-carrier", "wrong-caller", "unjoined-close"])
def test_model_prepare_observer_exact_carrier_and_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    """Code-object controls only; never import or construct native AIAgent."""
    import sys
    from types import CodeType, ModuleType, SimpleNamespace
    from unittest.mock import Mock

    import test_contract_method_pg as owner

    root, init, contract = (
        ModuleType(name)
        for name in ("run_agent", "agent.agent_init", "omnis_hermes.managed_admission_contract")
    )
    exec(
        compile(
            "class AIAgent:\n def __init__(self, model_test_preparation=None): pass\n def close(self): pass\n",
            str(tmp_path / "run_agent.py"),
            "exec",
        ),
        root.__dict__,
    )
    exec(
        compile(
            "def configure_model_test(agent, carrier): pass\n",
            str(tmp_path / "agent/agent_init.py"),
            "exec",
        ),
        init.__dict__,
    )
    exec("class ModelTestPreparation: pass", contract.__dict__)
    for module in (root, init, contract):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    actor = object.__new__(root.AIAgent)
    carrier = contract.ModelTestPreparation() if fault != "wrong-carrier" else object()
    actor.__dict__.update(
        _model_test_preparation=carrier,
        _model_test_record=Mock(future=Mock(done=Mock(return_value=fault != "unjoined-close"))),
        _model_test_closed=Mock(is_set=Mock(return_value=True)),
    )
    events = Mock()
    scope = {"sys": sys, "managed": tmp_path, "CodeType": CodeType, "emit": events}
    exec(owner.MODEL_PREPARE_OBSERVER, scope)
    observe = scope["prepare_observe"]
    assert callable(observe)
    frame = SimpleNamespace(
        f_code=init.configure_model_test.__code__,
        f_locals={"agent": actor, "carrier": carrier},
        f_back=SimpleNamespace(
            f_code=(lambda: None).__code__
            if fault == "wrong-caller"
            else root.AIAgent.__init__.__code__,
            f_locals={"self": actor, "model_test_preparation": carrier},
        ),
    )
    if fault == "unjoined-close":
        frame = SimpleNamespace(
            f_code=root.AIAgent.close.__code__, f_locals={"self": actor}, f_back=None
        )
    if fault is None:
        assert observe(frame, "call") is True
        assert observe(frame, "return") is True
        assert events.call_count == 2
    else:
        for _ in range(2):
            with pytest.raises(RuntimeError, match="^Forbidden native sink$"):
                observe(frame, "return" if fault == "unjoined-close" else "call")
        assert events.call_count == 2
        assert all(call.args[0] == "forbidden-sink" for call in events.call_args_list)


def test_model_prepare_bootstrap_matches_current_native_entry() -> None:
    import ast

    import test_contract_method_pg as owner

    root = Path(__file__).resolve().parents[2] / "integrations/hermes/upstream"
    entry = ast.parse((root / "managed-source/tui_gateway/entry.py").read_text())
    main = next(n for n in entry.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    ready = next(
        n
        for n in main.body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "_write_or_exit"
    )
    following = main.body[main.body.index(ready) + 1]
    observer = ast.parse(owner.batch2_native_observer(startup=False, model_prepare=True))
    inventory = next(
        n
        for n in observer.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "phase_inventory" for t in n.targets)
    )
    scope: dict[str, object] = {"managed": root / "managed-source", "inert": root / "inert-source"}
    exec(
        compile(ast.Module(body=[inventory], type_ignores=[]), "SOURCE-phase-inventory", "exec"),
        scope,
    )
    phases = cast(
        dict[tuple[str, str, int], tuple[str, dict[int, tuple[str, str]]]], scope["phase_inventory"]
    )
    key = (str(root / "managed-source/tui_gateway/entry.py"), "main", main.lineno)
    assert phases[key] == (
        "ENTRY_MAIN_BEGIN",
        {
            ready.lineno: ("ENTRY_READY_WRITE_BEGIN", "ENTER"),
            following.lineno: ("ENTRY_READY_WRITE_BEGIN", "END"),
        },
    )


def test_model_prepare_prefix_denies_before_stock_branch() -> None:
    import ast
    import sys
    from unittest.mock import Mock

    import test_contract_method_pg as owner

    tree = ast.parse(owner.batch2_native_observer(startup=False, model_prepare=True))
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "monitor_line"
    )
    code = compile("pass", "SOURCE-prefix-control", "exec")
    events = Mock()
    scope: dict[str, object] = {"sys": sys, "prepare_prefixes": {code: 1011}, "emit": events}
    exec(compile(ast.Module(body=[function], type_ignores=[]), owner.__file__, "exec"), scope)
    invoke = scope["monitor_line"]
    assert callable(invoke)
    assert invoke(code, 1011) is None
    for _ in range(2):
        with pytest.raises(RuntimeError, match="^Forbidden native sink$"):
            invoke(code, 1012)
    assert events.call_count == 2


@pytest.mark.asyncio
async def test_new_work_after_shutdown_is_blocked_by_existing_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New/pending work still requires the unchanged current-authority fence."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from sqlalchemy.ext.asyncio import AsyncEngine

    from omnis.modules.instance.domain import ControlCode, ControlConflict
    from omnis.modules.instance.service import InstanceService

    service = InstanceService(Mock(spec=AsyncEngine))
    conn = Mock(spec=AsyncConnection)
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[object, object, object]]:
        yield conn, SimpleNamespace(generation=0, shutdown_command_id=uuid4()), object()

    monkeypatch.setattr(service, "_locked", locked)
    monkeypatch.setattr(service, "_require_owner", AsyncMock())
    monkeypatch.setattr(service, "_stop_fence", AsyncMock())
    with pytest.raises(ControlConflict) as caught:
        async with service.native_preparation_commit(uuid4(), 1, 0):
            pytest.fail("closed-admission replay unexpectedly entered receipt reader")
    assert caught.value.code == ControlCode.INSTANCE_SHUTTING_DOWN
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_compact_reply_finite_largest_layout_and_strict_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from test_model_preflight_control import consume
    from test_owned_model_initialization import (
        test_model_test_prepare_owns_fresh_qualified_context_and_holds,
    )

    captures: list[tuple[NativeTaskCommand, dict[str, object]]] = []
    handle = NativeTaskOwner.handle

    async def capture(self: NativeTaskOwner, command: NativeTaskCommand) -> dict[str, object]:
        answer = await handle(self, command)
        captures.append((command, answer))
        return answer

    with monkeypatch.context() as producer:
        producer.setattr(NativeTaskOwner, "handle", capture)
        await test_model_test_prepare_owns_fresh_qualified_context_and_holds(
            tmp_path, producer, False
        )
    command, answer = captures[0]
    response = {**answer, "correlation_id": str(uuid4())}
    assert await consume(monkeypatch, command.model_dump(mode="json"), response) == response
    # Every variable field in this finite success DTO is a canonical UUID or SHA;
    # record refs are immutable revision1, kinds/statuses/keys are fixed ASCII.
    maximum = deepcopy(response)
    for field in ("owner_id", "initialization_id", "run_id", "correlation_id"):
        maximum[field] = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    for field in ("context_ref", "turn_ref", "manifest_ref"):
        maximum[field] = {
            **mapping(maximum[field]),
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "digest": "f" * 64,
        }
    size = len(json.dumps(maximum).encode()) + 1
    assert size == len(json.dumps(response).encode()) + 1 < 3600 < 4096
    print(f"MODEL_TEST_COMPACT_REPLY_JSON_LF_CORRELATION={size}")
    # Serializer-only whitespace boundaries, not a legitimate maximum DTO layout.
    encoded = json.dumps(response).encode()
    at_limit = encoded + b" " * (4096 - len(encoded) - 1) + b"\n"
    assert len(at_limit) == 4096
    assert (
        await consume(monkeypatch, command.model_dump(mode="json"), response, at_limit) == response
    )
    with pytest.raises(CatalogError, match="TASK_REJECTED"):
        await consume(
            monkeypatch, command.model_dump(mode="json"), response, at_limit[:-1] + b" \n"
        )
    largest_command = {
        **command.model_dump(mode="json"),
        "expected_epoch": 2**63 - 1,
        "expected_generation": 2**63 - 1,
    }
    assert (
        len(canonical(NativeTaskCommand.model_validate(largest_command).model_dump(mode="json")))
        <= 3600
    )
    assert (
        len(json.dumps({"version": 1, "capability": "f" * 64, "command": largest_command}).encode())
        + 1
        <= 4096
    )
    for field, value in (
        ("kind", "launch-manifest"),
        ("id", True),
        ("digest", "g" * 64),
        ("revision", True),
        ("revision", 2),
    ):
        bad = deepcopy(response)
        bad["context_ref"] = {**mapping(bad["context_ref"]), field: value}
        with pytest.raises(CatalogError):
            await consume(monkeypatch, command.model_dump(mode="json"), bad)
    for field, value in (
        ("preparation_status", "READY"),
        ("inference_status", "READY"),
        ("initialization_id", str(uuid4())),
        ("owner_id", str(uuid4())),
        ("account_status", "VERIFIED"),
    ):
        with pytest.raises(CatalogError):
            await consume(monkeypatch, command.model_dump(mode="json"), {**response, field: value})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "grant",
    ["good", "bool", "expired", "over-managed", "read-expired", "read-stopped", "read-fenced"],
)
async def test_model_prepare_host_checks_grant_before_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, grant: str
) -> None:
    import time
    from unittest.mock import Mock

    from omnis_hermes.managed_admission_contract import preparation_result, ref
    from omnis_hermes.runtime_host import RuntimeHost

    clock = [10_000_000_000]
    monkeypatch.setattr(time, "monotonic_ns", lambda: clock[0])
    owner, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    payload = await produce(owner, consumer, conn, manifest, authority)
    host = RuntimeHost(tmp_path)
    host.boot = str(owner.runtime.boot)
    host.epoch, host.generation, host.state = 1, 0, "MANAGEMENT"
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    host.settings_task = Mock(done=Mock(return_value=True))
    context = mapping(mapping(payload["context"])["payload"])
    host.settings_result = {
        "status": "CONFIRMED",
        "operation_id": context["settings_operation_id"],
        "selection": REQUESTED,
    }
    read = AsyncMock(return_value=REQUESTED)
    stop = AsyncMock()
    launch = AsyncMock()

    async def stopped() -> None:
        host.state = "STOPPED"

    async def launched(body: dict[str, object]) -> None:
        host.state = "READY"
        host.process = Mock(returncode=None)
        host.peer = Mock(failure=None, call=call)

    call = AsyncMock(
        return_value=preparation_result(
            payload,
            native_root_id=str(uuid4()),
            native_child_id=str(uuid4()),
            native_session_id="SOURCE-session",
            native_turn={"task_id": str(context["task_id"]), "turn_id": "SOURCE-turn"},
        )
    )

    async def saved_read(action: str, selected: object) -> dict[str, object]:
        if grant == "read-expired":
            clock[0] += 200_000_000
        elif grant == "read-stopped":
            host.state = "STOPPED"
        elif grant == "read-fenced":
            host.generation += 1
        return dict(REQUESTED)

    read.side_effect = saved_read
    stop.side_effect, launch.side_effect = stopped, launched
    monkeypatch.setattr(host, "_settings_native", read)
    monkeypatch.setattr(host, "stop", stop)
    monkeypatch.setattr(host, "_launch", launch)
    deadline = {
        "good": time.monotonic_ns() + 4_000_000_000,
        "bool": True,
        "expired": time.monotonic_ns() - 1,
        "over-managed": time.monotonic_ns() + 10_800_000_000,
        "read-expired": time.monotonic_ns() + 100_000_000,
        "read-stopped": time.monotonic_ns() + 3_000_000_000,
        "read-fenced": time.monotonic_ns() + 3_000_000_000,
    }[grant]
    body = {
        "payload": payload,
        "op": "task_model_initialize",
        "epoch": 1,
        "generation": 0,
        "deadline_ns": deadline,
    }
    if grant == "good":
        assert mapping(await host._managed(body))["status"] == "TURN_BOUND_PRE_CLIENT_HOLD"
        assert host.deadline_ns == deadline
        assert host.model_preparation_close is not None
        assert json.loads(host.model_preparation_close) == {
            "protocol": payload["protocol"],
            "mode": "CLOSE",
            "context_ref": ref(mapping(payload["context"])),
        }
        read.assert_awaited_once()
        stop.assert_awaited_once()
        launch.assert_awaited_once_with(body)
        call.assert_awaited_once()
    elif grant.startswith("read-"):
        with pytest.raises(ValueError, match="Expired preparation request"):
            await host._managed(body)
        read.assert_awaited_once()
        for effect in (stop, launch, call):
            effect.assert_not_awaited()
        assert host.deadline_ns == deadline
        assert host.state == ("STOPPED" if grant == "read-stopped" else "MANAGEMENT")
    else:
        with pytest.raises(ValueError, match="Invalid (authority deadline|managed grant)"):
            await host._managed(body)
        for effect in (read, stop, launch, call):
            effect.assert_not_awaited()
        assert host.state == "MANAGEMENT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", [None, "absent", "join-error", "wrong-context", "wrong-status", "extra", "timeout"]
)
async def test_model_prepare_stop_requires_correlated_close_join(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    import asyncio
    import os
    from collections import deque
    from unittest.mock import Mock

    from omnis_hermes import runtime_host
    from omnis_hermes.managed_admission_contract import PROTOCOL_V5, ref
    from omnis_hermes.runtime_protocol import NativePeer, encode

    owner, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    payload = await produce(owner, consumer, conn, manifest, authority)
    close = {
        "protocol": PROTOCOL_V5,
        "mode": "CLOSE",
        "context_ref": ref(mapping(payload["context"])),
    }
    host = runtime_host.RuntimeHost(tmp_path)
    host.state, host.namespace_owned = "READY", True
    host.model_preparation_close = canonical(close)
    process = Mock(pid=12345, returncode=None, wait=AsyncMock(return_value=0))
    host.process = process
    monkeypatch.setattr(host, "_owned_pids", lambda: set())
    peer = object.__new__(NativePeer)
    peer.failure, peer.queued_bytes, peer.next_id, peer.timeout = None, 0, 2**63 - 2, 0.8
    peer.queue, peer.pending, peer.late = asyncio.Queue(32), {}, deque(maxlen=32)
    host.peer = peer
    effects = []
    enqueue = peer._enqueue

    def deliver(frame: dict[str, object]) -> None:
        assert host.state == "STOPPING"
        enqueue(frame)
        raw, _ = peer.queue.get_nowait()
        assert json.loads(raw)["params"] == close and len(raw) <= 65536
        effects.append("close")
        future = peer.pending[(int, peer.next_id)]
        result: dict[str, object] = {**close, "status": "CLOSED_JOINED"}
        if fault == "absent":
            future.set_result(None)
        elif fault == "join-error":
            future.set_exception(ValueError("Native preparation drain uncertain"))
        elif fault == "timeout":
            future.set_exception(TimeoutError())
        else:
            if fault == "wrong-context":
                result["context_ref"] = {**mapping(close["context_ref"]), "id": str(uuid4())}
            elif fault == "wrong-status":
                result["status"] = "UNKNOWN"
            elif fault == "extra":
                result["joined"] = True
            assert len(encode({"jsonrpc": "2.0", "id": peer.next_id, "result": result})) <= 65536
            future.set_result(result)

    monkeypatch.setattr(peer, "_enqueue", deliver)
    if fault is None:
        from omnis_hermes.managed_admission_contract import RPC

        for field, value in (
            ("revision", True),
            ("revision", 1.0),
            ("revision", "1"),
            ("revision", 2),
            ("kind", "launch-manifest"),
            ("id", True),
            ("digest", "g" * 64),
        ):
            invalid: dict[str, object] = {
                **close,
                "context_ref": {**mapping(close["context_ref"]), field: value},
            }
            with pytest.raises(ValueError):
                await peer.call(RPC["task_model_initialize"], invalid)
            assert peer.next_id == 2**63 - 2 and peer.pending == {} and effects == []
        print(
            "MODEL_CLOSE_NATIVE_REQUEST_BYTES="
            + str(
                len(
                    encode(
                        {
                            "jsonrpc": "2.0",
                            "id": 2**63 - 1,
                            "method": RPC["task_model_initialize"],
                            "params": close,
                        }
                    )
                )
            )
        )
        print(
            "MODEL_CLOSE_NATIVE_REPLY_BYTES="
            + str(
                len(
                    encode(
                        {
                            "jsonrpc": "2.0",
                            "id": 2**63 - 1,
                            "result": {**close, "status": "CLOSED_JOINED"},
                        }
                    )
                )
            )
        )
    retired = AsyncMock(side_effect=lambda: effects.append("retire"))
    monkeypatch.setattr(peer, "close", retired)

    def physical_kill(*args: object) -> None:
        effects.append("physical-kill")
        process.returncode = 0

    monkeypatch.setattr(os, "killpg", physical_kill)
    await host.stop()
    assert effects == ["close", "physical-kill", "retire"]
    assert host.state == ("STOPPED" if fault is None else "UNCERTAIN")
    assert (host.model_close_evidence is not None) is (fault is None)
    peer.bootstrap_inventory = None
    assert host.snapshot()["model_preparation_close"] == (
        {**close, "status": "CLOSED_JOINED"} if fault is None else None
    )
    if fault is not None:
        await host.stop()
        assert host.state == "UNCERTAIN" and effects.count("close") == 1


@pytest.mark.asyncio
async def test_execution_start_is_fresh_qualified_and_bounded_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis_hermes.managed_admission_contract import validate_model_prepare

    from omnis.modules.instance.schemas import NativeTaskCommand

    owner, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "owner_id": owner.owner,
            "manifest_ref": manifest,
            "action": "model_test_start",
            "initialization_id": str(uuid4()),
            "settings_operation_id": str(uuid4()),
        }
    )
    before = canonical(owner.graph)
    context, created = await consumer.prepare(
        conn,
        owner.owner,
        manifest,
        str(command.initialization_id),
        str(command.settings_operation_id),
        {"status": "CONFIRMED", "selection": REQUESTED},
        authority,
        str(owner.runtime.boot),
        command,
    )
    payload, observation = await consumer.dispatch(conn, owner.owner, context, created)
    assert observation is None and before == canonical(owner.graph[: len(json.loads(before))])
    assert payload["protocol"] == "omnis-managed-admission-v6"
    assert mapping(context["payload"])["purpose"] == "SETTINGS_TEST"
    assert validate_model_prepare(payload) == payload
    assert len(canonical(payload)) <= 32768


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    [
        "complete",
        "null",
        "lost",
        "stop",
        "expired",
        "blocked",
        "trickle",
        "malformed",
        "complete-stop",
        "missing-account",
        "malformed-token",
        "missing-token",
        "socket-detach",
        "reorder",
        "duplicate",
        "index-conflict",
        "identity-conflict",
        "terminal-unknown",
        "terminal-disagreement",
        "terminal-agrees",
        "receipt-overlap",
    ],
)
async def test_execution_owner_commits_reserve_and_sent_then_replays_without_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """SOURCE owners/ledger/native function+real SDK; storage/constructor/compiler/HTTP are doubles."""
    import base64
    import os
    import socket
    import threading
    import time
    from collections.abc import Iterator
    from datetime import tzinfo
    from types import ModuleType, SimpleNamespace

    import httpx

    if outcome == "socket-detach":
        probe, peer_probe = socket.socketpair()
        try:
            try:
                probe.shutdown(socket.SHUT_RDWR)
            except PermissionError:
                pytest.skip("Sandbox denies genuine socket shutdown; parent socket/TLS QA required")
        finally:
            probe.close()
            peer_probe.close()
    assert import_module("openai").__version__ == "2.24.0"  # existing native SDK, no network
    from hashlib import sha256
    from typing import Callable

    from omnis_hermes.managed_admission_contract import preparation_result, validate_initialization
    from omnis_hermes.management_oauth import NativeOAuth
    from omnis_hermes.model_request import CodexFinalRequest
    from omnis_hermes.model_terminal import ManagedModelTerminal
    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.tasks import managed_store as store
    from omnis.policy import budgets

    reserve = budgets.reserve
    owner, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/tests")
    )
    load = import_module("test_model_terminal").load

    monkeypatch.setattr(budgets, "reserve", reserve)
    cast(AsyncMock, conn.execute).return_value.scalars.return_value.all.return_value = []
    groups: dict[str, str] = {str(r["id"]): owner.run for r in owner.graph}
    original_put, original_get = store.put, store.get

    async def put(c: AsyncConnection, who: str, run: str, item: dict[str, object]) -> None:
        groups[str(item["id"])] = run
        await original_put(c, who, run, item)

    async def owned(c: AsyncConnection, who: str, pin: object) -> tuple[str, dict[str, object]]:
        run = groups[str(mapping(pin)["id"])]
        return run, await original_get(c, who, run, pin)

    monkeypatch.setattr(store, "put", put)
    monkeypatch.setattr(store, "owned", owned)
    monkeypatch.setattr(
        owner.runtime,
        "settings_status",
        AsyncMock(return_value={"status": "CONFIRMED", "selection": REQUESTED}),
    )
    monkeypatch.setattr(
        owner.handler.domain, "readback", AsyncMock(return_value={"manifest_ref": manifest})
    )
    starts: list[dict[str, object]] = []
    sends: list[dict[str, object]] = []
    physical: list[str] = []
    retained: dict[str, object] = {}

    async def native(*args: object) -> dict[str, object]:
        p = mapping(args[-1])
        assert owner.events[-1] == "commit"
        assert validate_initialization(p) == p
        if p["mode"] == "CREATE":
            starts.append(p)
            return preparation_result(
                p,
                native_root_id=str(uuid4()),
                native_child_id=str(uuid4()),
                native_session_id="SOURCE_NATIVE_SESSION",
                native_turn={
                    "task_id": mapping(mapping(p["context"])["payload"])["task_id"],
                    "turn_id": "SOURCE_TURN",
                },
            )
        if p["mode"] == "RECEIVE":
            return mapping(retained["result"])
        assert p["mode"] == "SEND"
        sends.append(p)
        assert any(r["kind"] == "model-test-send" for r in owner.graph)
        assert any(
            r["kind"] == "model-dispatch-transition" and mapping(r["payload"])["state"] == "SENT"
            for r in owner.graph
        )
        final = CodexFinalRequest(canonical(p))
        body = final.expected_body()
        kwargs = {k: v for k, v in body.items() if k != "stream"}
        kwargs.update(
            timeout=300.0, extra_headers={"x-client-request-id": body["prompt_cache_key"]}
        )
        assert final.consume_native(kwargs)["stream"] is True
        for key, changed in (
            ("model", "other"),
            ("reasoning", {"effort": "high"}),
            ("tools", []),
            ("extra_body", {}),
        ):
            with pytest.raises((ManagedModelTerminal, ValueError)):
                final.consume_native({**kwargs, key: changed})
        compiler = ModuleType("agent.transports.codex")

        class CompilerDouble:
            def build_kwargs(self, **values: object) -> dict[str, object]:
                assert values["model"] == "gpt-6.1-sol" and values["is_codex_backend"] is True
                return kwargs

        monkeypatch.setattr(compiler, "ResponsesApiTransport", CompilerDouble, raising=False)
        monkeypatch.setitem(__import__("sys").modules, "agent.transports.codex", compiler)
        # Immutable stock Hermes leaf (Nous Research, MIT; integrations/hermes/upstream/LICENSE).
        pinned = Path(__file__).resolve().parent / "fixtures/codex_headers.py.txt"
        pinned_bytes = pinned.read_bytes()
        assert sha256(pinned_bytes).hexdigest() == (
            "f294215fef55f229704cd3fc596ccb6840af126459f15a7ffd38f2c51ae62f6a"
        )
        headers_module = ModuleType("agent.codex_headers")
        exec(compile(pinned_bytes, str(pinned), "exec"), headers_module.__dict__)
        monkeypatch.setitem(__import__("sys").modules, "agent.codex_headers", headers_module)
        cli = ModuleType("hermes_cli")
        monkeypatch.setattr(cli, "__version__", "SOURCE_VERSION", raising=False)
        monkeypatch.setitem(__import__("sys").modules, "hermes_cli", cli)
        claims = (
            {}
            if outcome == "missing-account"
            else {
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": "SOURCE_ACCOUNT",
                    "chatgpt_data_residency": "eu",
                }
            }
        )
        token = (
            "synthetic."
            + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
            + ".unsigned"
        )
        if outcome == "malformed-token":
            token = "SYNTHETIC_NOT_A_CREDENTIAL"
        auth = ModuleType("hermes_cli.auth_codex")
        monkeypatch.setattr(
            auth,
            "_read_codex_tokens",
            lambda: {"tokens": {} if outcome == "missing-token" else {"access_token": token}},
            raising=False,
        )
        monkeypatch.setattr(
            auth, "_codex_access_token_is_expiring", lambda *a: False, raising=False
        )
        monkeypatch.setitem(__import__("sys").modules, "hermes_cli.auth_codex", auth)
        host = RuntimeHost(tmp_path)
        host.deadline_ns = time.monotonic_ns() + 4_000_000_000
        reader = host._open_management_lifeline()
        lifeline = NativeOAuth.from_owner_fd(reader)

        def transport(request: httpx.Request) -> httpx.Response:
            assert request.headers["originator"] == "hermes-agent"
            assert request.headers["user-agent"] == "HermesAgent/SOURCE_VERSION"
            assert request.headers["authorization"] == "Bearer " + token
            if outcome in {"missing-account", "malformed-token"}:
                assert "chatgpt-account-id" not in request.headers
                assert "x-openai-internal-codex-residency" not in request.headers
            else:
                assert request.headers["chatgpt-account-id"] == "SOURCE_ACCOUNT"
                assert request.headers["x-openai-internal-codex-residency"] == "eu"
            assert token.encode() not in final.raw
            if outcome in {"blocked", "trickle", "socket-detach"}:
                assert all(0 < value <= 0.3 for value in request.extensions["timeout"].values())
            final.validate_wire(request.content)
            if outcome == "stop":
                host._revoke_management_lifeline()  # real synchronous pipe EOF before simulated preheader
            if outcome == "expired":
                host.deadline_ns = time.monotonic_ns() + 1_000_000
                time.sleep(0.005)  # actual Host writer stays open; no watchdog runs
            trace = cast(Callable[[str, dict[str, object]], None], request.extensions["trace"])
            trace("http11.send_request_headers.started", {})
            physical.append("headers")
            if outcome == "lost":
                raise httpx.ReadError("SOURCE_LOST_RESPONSE", request=request)
            response = {
                "id": "SOURCE_PROVIDER_RECEIPT",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-6.1-sol",
                "output": None
                if outcome == "null"
                else [{"type": "unknown"}]
                if outcome == "malformed"
                else [],
                "reasoning": {"effort": "xhigh", "summary": "auto"},
                "usage": {
                    "input_tokens": 15,
                    "output_tokens": 12,
                    "total_tokens": 27,
                    "output_tokens_details": {"reasoning_tokens": 9},
                },
            }
            event = {"type": "response.completed", "response": response}
            item = {
                "id": "msg_source",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Synthetic reply.", "annotations": []}],
            }
            prefix = ""
            parser_cases = {
                "null",
                "reorder",
                "duplicate",
                "index-conflict",
                "identity-conflict",
                "terminal-unknown",
                "terminal-disagreement",
                "terminal-agrees",
                "receipt-overlap",
            }
            if outcome in parser_cases:
                second = {
                    **item,
                    "id": "msg_second",
                    "content": [{"type": "output_text", "text": " Second.", "annotations": []}],
                }
                done = {"type": "response.output_item.done", "output_index": 0, "item": item}
                events = [done]
                response["output"] = None
                if outcome == "reorder":
                    events = [{**done, "output_index": 1, "item": second}, done]
                elif outcome == "duplicate":
                    events.append(dict(done))
                elif outcome == "index-conflict":
                    events.append({**done, "item": second})
                elif outcome == "identity-conflict":
                    events.append({**done, "output_index": 1})
                elif outcome == "terminal-unknown":
                    response["output"] = [{"type": "unknown"}]
                elif outcome == "terminal-disagreement":
                    response["output"] = [second]
                elif outcome == "terminal-agrees":
                    response["output"] = [item]
                prefix = "".join(
                    "event: response.output_item.done\ndata: " + json.dumps(e) + "\n\n"
                    for e in events
                )
            if outcome in {"blocked", "trickle", "socket-detach"}:
                from httpcore._backends.sync import SyncStream

                closed = threading.Event()
                read_end = write_end = -1

                class PipeSocket:
                    def shutdown(self, how: int) -> None:
                        if not closed.is_set():
                            closed.set()
                            os.close(write_end)

                    def dup(self) -> "PipeSocket":
                        return self

                    def close(self) -> None:
                        pass

                    def recv(self, size: int) -> bytes:
                        return os.read(read_end, size)

                sock: socket.socket | PipeSocket
                if outcome in {"blocked", "trickle"}:
                    read_end, write_end = os.pipe()
                    sock = PipeSocket()
                else:
                    sock, peer_socket = socket.socketpair()
                connect_info: dict[str, object] = {"timeout": 300.0}
                trace("connection.connect_unix_socket.started", connect_info)
                assert 0 < cast(float, connect_info["timeout"]) <= 0.3
                if isinstance(sock, socket.socket):
                    trace(
                        "connection.connect_unix_socket.complete",
                        {"return_value": SyncStream(sock)},
                    )
                else:
                    trace(
                        "connection.connect_unix_socket.complete",
                        {"return_value": SimpleNamespace(get_extra_info=lambda key: sock)},
                    )
                if outcome == "socket-detach":
                    assert isinstance(sock, socket.socket)
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, fileno=sock.detach())

                class Body(httpx.SyncByteStream):
                    def __iter__(self) -> Iterator[bytes]:
                        retained["reader_entered"] = True
                        while data := sock.recv(1024):
                            yield data

                    def close(self) -> None:
                        closed.set()
                        if outcome in {"blocked", "trickle"}:
                            sock.shutdown(2)
                            os.close(read_end)
                        else:
                            peer_socket.close()
                            sock.close()

                if outcome == "trickle":

                    def trickle() -> None:
                        while not closed.wait(0.025):
                            try:
                                os.write(write_end, b": keepalive\n\n")
                            except OSError:
                                return

                    writer_thread = threading.Thread(target=trickle, daemon=True)
                    retained["writer_thread"] = writer_thread
                    writer_thread.start()
                # Safety bound for RED: original code otherwise blocks for 300 seconds.
                safety = threading.Timer(1.5, sock.shutdown, args=(2,))
                safety.start()
                retained["safety"] = safety
                return httpx.Response(
                    200, headers={"content-type": "text/event-stream"}, stream=Body()
                )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=prefix + "event: response.completed\ndata: " + json.dumps(event) + "\n\n",
            )

        monkeypatch.setattr(httpx, "HTTPTransport", lambda **k: httpx.MockTransport(transport))
        monkeypatch.setenv("HERMES_HOME", "/state/provider")
        from omnis_hermes.managed_admission_contract import ModelTestPreparation

        child = SimpleNamespace(
            _model_test_dispatch=final,
            _model_test_execution=True,
            _model_test_preparation=ModelTestPreparation(canonical(starts[0])),
            _model_test_bound=True,
            _model_test_lifeline=lifeline,
            _model_test_closed=threading.Event(),
            _api_call_count=0,
            _model_test_result=None,
        )
        function = load(
            "turn_api_request.py", {"run_model_test_request"}, {}
        ).run_model_test_request
        if outcome in {"blocked", "trickle", "socket-detach"}:
            import datetime as datetime_module
            from datetime import datetime

            class NearDeadline(datetime):
                @classmethod
                def now(cls, tz: tzinfo | None = None) -> "NearDeadline":
                    return cls.fromtimestamp(datetime.now(tz).timestamp() + 299.7, tz)

            monkeypatch.setattr(datetime_module, "datetime", NearDeadline)
        began = time.monotonic()
        try:
            function(child)
            if outcome in {"blocked", "trickle", "socket-detach"}:
                assert retained.get("reader_entered") is True
                assert 0.2 < time.monotonic() - began < 1.0
        finally:
            timer = retained.get("safety")
            if isinstance(timer, threading.Timer):
                timer.cancel()
                timer.join()
            writer_thread = retained.get("writer_thread")
            if isinstance(writer_thread, threading.Thread):
                writer_thread.join(timeout=1)
                assert not writer_thread.is_alive()
            host._revoke_management_lifeline()
            os.close(reader)
        assert token not in json.dumps(child._model_test_result)
        retained["result"] = child._model_test_result
        if outcome == "receipt-overlap":
            import asyncio
            from unittest.mock import Mock

            attempt = next(r for r in owner.graph if r["kind"] == "model-test-attempt")
            mutex = asyncio.Lock()
            first_lock, second_lock = asyncio.Event(), asyncio.Event()
            holders: set[object] = set()
            arrivals: list[object] = []
            graph_read = store.graph

            async def graph_snapshot(
                c: AsyncConnection, who: str, run: str
            ) -> list[dict[str, object]]:
                snapshot = await graph_read(c, who, run)
                await asyncio.sleep(0)  # overlap the actual first receipt reads
                return snapshot

            async def owner_lock(c: AsyncConnection, who: str) -> None:
                assert who == owner.owner
                task = asyncio.current_task()
                if task in holders:
                    return
                arrivals.append(task)
                if len(arrivals) == 1:
                    first_lock.set()
                    await second_lock.wait()
                else:
                    second_lock.set()
                await mutex.acquire()
                holders.add(task)

            async def settle_transaction(c: AsyncConnection, who: str) -> None:
                await owner_lock(c, who)

            async def execute(*args: object, **kw: object) -> object:
                rows = Mock()
                rows.scalars.return_value.all.return_value = [
                    r for r in owner.graph if r["kind"] == "model-usage-receipt"
                ]
                return rows

            async def receive() -> dict[str, object]:
                connection = cast(AsyncConnection, Mock(spec=AsyncConnection))
                cast(AsyncMock, connection.execute).side_effect = execute
                try:
                    return await consumer.execution_receipt(
                        connection, owner.owner, attempt, child._model_test_result
                    )
                finally:
                    task = asyncio.current_task()
                    if task in holders:
                        holders.remove(task)
                        mutex.release()  # simulated transaction completion

            with monkeypatch.context() as overlap:
                overlap.setattr(store, "graph", graph_snapshot)
                overlap.setattr(store, "lock", owner_lock)
                overlap.setattr(budgets, "_transaction", settle_transaction)
                overlap.setattr(conn, "execute", execute)
                async with asyncio.timeout(2):
                    readers = [asyncio.create_task(receive()) for _ in range(2)]
                    answers = await asyncio.gather(*readers)
                assert first_lock.is_set() and second_lock.is_set()
                assert answers[0] == answers[1]
                assert answers[0]["state"] == "SETTLED"
                assert len([r for r in owner.graph if r["kind"] == "provider-receipt"]) == 1
                assert len([r for r in owner.graph if r["kind"] == "model-usage-receipt"]) == 1
                assert len(sends) == len(physical) == 1
            # Keep real settlement replay on the outer serial/postStop controls.
            cast(AsyncMock, conn.execute).return_value.scalars.return_value.all.side_effect = (
                lambda: [r for r in owner.graph if r["kind"] == "model-usage-receipt"]
            )
        if outcome == "complete-stop":
            from omnis.modules.instance.domain import ControlCode, ControlConflict

            def stopped_commit(*args: object) -> object:
                raise ControlConflict(ControlCode.INSTANCE_SHUTTING_DOWN)

            monkeypatch.setattr(owner.handler.service, "native_preparation_commit", stopped_commit)
        return mapping(retained["result"])

    monkeypatch.setattr(owner.runtime, "managed", native)
    start = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "owner_id": owner.owner,
            "manifest_ref": manifest,
            "action": "model_test_start",
            "initialization_id": str(uuid4()),
            "settings_operation_id": str(uuid4()),
        }
    )
    ready = await owner.handler.handle(start)
    assert ready["inference_status"] == "AWAITING_SEND"
    composition = next(r for r in owner.graph if records.reference(r) == ready["composition_ref"])
    decision = {
        "decision_id": str(uuid4()),
        "composition_ref": records.reference(composition),
        "approved_text_digests": sorted(
            sha256(t.encode()).hexdigest()
            for t in (
                "Respond briefly to this synthetic model test. Use no tools.",
                str(mapping(composition["payload"])["text"]),
            )
        ),
    }
    send = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "owner_id": owner.owner,
            "manifest_ref": manifest,
            "action": "model_test_send",
            "initialization_id": start.initialization_id,
            "protocol_id": str(uuid4()),
            "data_approval": decision,
        }
    )
    result = await owner.handler.handle(send)
    if outcome in {
        "complete",
        "null",
        "complete-stop",
        "missing-account",
        "malformed-token",
        "reorder",
        "terminal-agrees",
        "receipt-overlap",
    }:
        assert (
            result["state"] == "SETTLED"
            and result["output_tokens"] == 12
            and result["reasoning_tokens"] == 9
        )
        assert result["inference_status"] == "VERIFIED" and result["cost_observed"] is None
        if outcome in {"null", "reorder", "terminal-agrees", "receipt-overlap"}:
            receipt = next(r for r in owner.graph if r["kind"] == "provider-receipt")
            assert mapping(mapping(receipt["payload"])["observed"])[
                "output_text"
            ] == "Synthetic reply." + (" Second." if outcome == "reorder" else "")
    else:
        assert result["state"] == "SENT" and result["usage_state"] == "UNKNOWN"
        assert result["output_tokens"] is None and result["provider_receipt_ref"] is None
    before = canonical(owner.graph)
    assert await owner.handler.handle(send) == result
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from omnis.modules.instance.domain import ControlCode, ControlConflict

    @asynccontextmanager
    async def stopped(*args: object) -> AsyncIterator[AsyncConnection]:
        if args:
            raise ControlConflict(ControlCode.INSTANCE_SHUTTING_DOWN)
        yield conn

    monkeypatch.setattr(owner.handler.service, "native_preparation_commit", stopped)
    assert await owner.handler.handle(send) == result
    restarted = send.model_copy(update={"expected_epoch": 2, "expected_generation": 1})
    assert await owner.handler.handle(restarted) == result
    with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
        await owner.handler.handle(
            restarted.model_copy(
                update={"data_approval": {**decision, "decision_id": str(uuid4())}}
            )
        )
    with pytest.raises((CatalogError, ControlConflict)):
        await owner.handler.handle(restarted.model_copy(update={"owner_id": str(uuid4())}))
    assert len(starts) == len(sends) == 1 and canonical(owner.graph) == before
    assert len(physical) == (0 if outcome in {"stop", "expired", "missing-token"} else 1)
    from omnis_hermes.runtime_protocol import encode

    measurements = {}
    for name, data in (("start", starts[0]), ("send", sends[0])):
        native_frame = encode(
            {
                "jsonrpc": "2.0",
                "id": "f" * 36,
                "method": "omnis.managed.model_initialize",
                "params": data,
            }
        )
        host_frame = encode(
            {
                "version": 1,
                "id": "f" * 36,
                "boot": "f" * 36,
                "capability": "f" * 64,
                "generation": 2**63 - 1,
                "epoch": 2**63 - 1,
                "deadline_ns": 2**63 - 1,
                "op": "task_model_initialize",
                "payload": data,
            }
        )
        measurements[name] = {
            "payload": len(canonical(data)),
            "native_frame": len(native_frame),
            "host_frame": len(host_frame),
        }
        assert (
            len(canonical(data)) <= 32768
            and len(native_frame) <= 65536
            and len(host_frame) <= 65536
        )
    print("EXECUTION_INPUT_SIZES", json.dumps(measurements))
