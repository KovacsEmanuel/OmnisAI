"""Bounded control/admission SOURCE tests; never native or persistent-PG proof."""

import importlib
import importlib.util
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs.managed_admission import BuildSource, ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import mapping, sequence
from omnis.policy import budgets
from omnis.policy.model_projection import SyntheticApproval, projection_input
from test_model_projection import source_graph, text_digests


def preflight_command() -> dict[str, object]:
    return {
        "op": "native_task",
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "instance_id": str(uuid4()),
        "expected_generation": 0,
        "expected_epoch": 1,
        "action": "model_preflight",
        "manifest_ref": records.reference(records.envelope("launch-manifest", {})),
        "data_approval": {
            "decision_id": str(uuid4()),
            "composition_ref": records.reference(records.envelope("prompt-composition", {})),
            "approved_text_digests": ["a" * 64],
        },
    }


def protocol_configuration(payload: dict[str, object]) -> dict[str, object]:
    """SOURCE protocol reply data only; NOT a native configuration or warm grant."""
    context = mapping(payload["model_context"])
    rows = sequence(mapping(mapping(payload["binding"])["payload"])["entries"])
    row = next(
        mapping(r)
        for r in rows
        if mapping(r)["task_id"] == context["task_id"]
        and mapping(r)["attempt_id"] == context["attempt_id"]
    )
    return {
        "version": 1,
        "source": "NATIVE_COLD_INITIALIZER",
        "mode": "NO_MODEL",
        "provider": None,
        "model_id": None,
        "native_child_id": row["native_child_id"],
        "native_session_id": row["native_session_id"],
        "native_parent_session_id": "SOURCE_PROTOCOL_PARENT_NOT_AUTHORITY",
    }


def test_private_control_accepts_explicit_data_decision_not_model_authority() -> None:
    command = preflight_command()
    try:
        checked = NativeTaskCommand.model_validate(command)
    except ValidationError:
        pytest.fail("private control has no qualified model preflight consumer")
    assert checked.model_dump(mode="json") == command


@pytest.mark.parametrize("field,value", [("expected_epoch", True), ("schema_version", True)])
def test_model_preflight_refuses_numeric_aliases(field: str, value: object) -> None:
    command = preflight_command()
    command[field] = value
    with pytest.raises((ValueError, ValidationError)):
        NativeTaskCommand.model_validate(command)


def test_data_decision_cannot_be_attached_to_cold_release() -> None:
    command = preflight_command()
    command["action"] = "release"
    with pytest.raises((ValueError, ValidationError)):
        NativeTaskCommand.model_validate(command)


@pytest.mark.asyncio
async def test_qualified_projection_reaches_cold_admission_without_model_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    protocol_mode: bool = False,
    protocol_failure: str | None = None,
    cleanup_fault: str | None = None,
    protocol_case: str | None = None,
) -> None:
    """Real composer/reader/adapter; storage and native identity are SOURCE doubles."""
    name = "omnis.modules.runs.model_dispatch"
    assert importlib.util.find_spec(name) is not None, "qualified native consumer absent"
    module = importlib.import_module(name)
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    sources: list[BuildSource] = []
    owner, graph, manifest, composition = source_graph(tmp_path, source_out=sources)
    run = str(mapping(manifest["payload"])["run_id"])
    binding = next(item for item in graph if item["kind"] == "runtime-binding")
    classified: set[str] = set()
    original = SyntheticApproval.classified

    def inspect_classification(self: SyntheticApproval, value: object) -> str:
        result = original(self, value)
        classified.add(sha256(result.encode()).hexdigest())
        return result

    # Test-operator classification of the fixed synthetic seed only. Production
    # must receive an explicit private-control decision, never this tracing helper.
    with monkeypatch.context() as m:
        m.setattr(SyntheticApproval, "classified", inspect_classification)
        projection_input(
            composition,
            SyntheticApproval(
                owner, run, canonical(records.reference(composition)), text_digests(composition), ()
            ),
        )
    assert 1 <= len(classified) <= 32
    decision = {
        "decision_id": str(uuid4()),
        "composition_ref": records.reference(composition),
        "approved_text_digests": sorted(classified),
    }
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    monkeypatch.setattr(managed, "_verify_graph", AsyncMock())

    async def source_io(
        conn: AsyncConnection,
        actual_owner: str,
        request: dict[str, object],
        *,
        preparation_ref: dict[str, object],
    ) -> BuildSource:
        # SOURCE storage/material seam only; producer is actual selection_payload,
        # full publication/material qualification is tested independently in PG.
        source = sources[0]
        assert actual_owner == owner
        assert request["selection_ref"] == records.reference(source.selection)
        assert preparation_ref == source.preparation_ref
        return source

    monkeypatch.setattr(managed, "_source", source_io)
    monkeypatch.setattr(budgets, "_transaction", AsyncMock())
    real_reserve = budgets.reserve
    reserve = AsyncMock(side_effect=AssertionError("cold path reached ledger reserve"))
    monkeypatch.setattr(budgets, "reserve", reserve)
    monkeypatch.setattr(managed_store, "lock", AsyncMock())
    monkeypatch.setattr(
        managed_store,
        "state",
        AsyncMock(
            return_value={
                "run_id": run,
                "binding_id": binding["id"],
                "command_id": str(uuid4()),
            }
        ),
    )
    monkeypatch.setattr(managed_store, "graph", AsyncMock(side_effect=lambda *_: list(graph)))

    async def get(
        conn: object, actual_owner: str, actual_run: str, pin: object
    ) -> dict[str, object]:
        assert actual_owner == owner and actual_run == run
        return next(
            item for item in [*graph, sources[0].selection] if records.reference(item) == pin
        )

    async def put(conn: object, actual_owner: str, actual_run: str, value: object) -> None:
        assert actual_owner == owner and actual_run == run
        graph.append(mapping(value))

    monkeypatch.setattr(managed_store, "get", get)
    monkeypatch.setattr(managed_store, "put", put)
    connection = AsyncMock(spec=AsyncConnection)
    rows = Mock()
    rows.scalars.return_value.all.side_effect = lambda: [
        item
        for item in graph
        if item["kind"] == "model-data-approval"
        and mapping(item["payload"])["decision_id"]
        == mapping(connection.execute.call_args.args[1])["decision"]
    ]
    connection.execute.return_value = rows
    consumer = module.ModelDispatch(managed)
    prepared = mapping(
        await consumer.prepare(
            connection, owner, records.reference(manifest), records.reference(binding), decision
        )
    )
    assert prepared == await consumer.prepare(
        connection, owner, records.reference(manifest), records.reference(binding), decision
    )
    assert sum(item["kind"] == "model-data-approval" for item in graph) == 1
    assert sum(item["kind"] == "model-projection" for item in graph) == 1
    adapter = importlib.import_module("omnis_hermes.model_admission")
    payload = mapping(prepared["payload"])
    carrier = adapter.validate_preflight(payload)
    assert b"private=value" not in carrier and b"/synthetic/orders" not in carrier
    row = mapping(sequence(mapping(binding["payload"])["entries"])[0])
    receipt = adapter.cold_preflight(
        payload,
        native_root_id=mapping(binding["payload"])["native_root_id"],
        native_entries=[row],
        source_configuration=protocol_configuration(payload),
    )
    assert receipt["reason"] == "NO_MODEL"
    assert receipt["native_turn"] is None and receipt["model_calls"] == 0
    assert adapter.validate_preflight_result(receipt, payload) == receipt
    reserve.assert_not_awaited()
    assert not {"native-turn", "model-dispatch", "model-reservation"} & {
        str(r["kind"]) for r in graph
    }

    # Now enter through the real supervisor owner, not merely the new library.
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from uuid import UUID

    from omnis.modules.instance.service import InstanceService
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from omnis.supervisor.runtime_client import RuntimeClient

    authority = mapping(mapping(binding["payload"])["authority"])
    monkeypatch.setattr(
        managed,
        "readback",
        AsyncMock(
            return_value={
                "manifest_ref": records.reference(manifest),
                "manifest": manifest,
                "binding": binding,
                "results": [],
                "release_started": False,
            }
        ),
    )
    rows.scalar_one.return_value = authority["instance_id"]
    service = Mock(spec=InstanceService)
    events: list[str] = []

    @asynccontextmanager
    async def fence(*args: object) -> AsyncIterator[AsyncConnection]:
        assert args[0] == UUID(str(authority["owner"]))
        assert str(args[0]) != owner  # lease and data owner remain distinct
        events.append("begin")
        yield connection
        events.append("commit")

    service.native_preparation_commit = fence
    runtime = RuntimeClient(
        tmp_path, generation=int(str(authority["generation"])), epoch=int(str(authority["epoch"]))
    )
    runtime.boot = str(mapping(binding["payload"])["runtime_boot"])

    import time
    from types import SimpleNamespace

    host = importlib.import_module("omnis_hermes.runtime_host").RuntimeHost(tmp_path)
    host.boot = runtime.boot
    host.generation, host.epoch = runtime.generation, runtime.epoch
    host.state = "READY"
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    host.process = Mock(returncode=None)

    # Execute only the actual lifecycle methods as SOURCE-prefix units, with
    # explicitly synthetic registry/identities; no full native import/agent.
    import ast
    import json
    import sys
    import threading
    from types import ModuleType

    source = (
        Path(__file__).resolve().parents[2]
        / "integrations/hermes/upstream/managed-source/agent/subagent_lifecycle.py"
    )
    tree = ast.parse(source.read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SubagentLifecycleService"
    )
    methods = {"__init__", "_cold_batch", "_require_cold_root", "model_preflight"}
    assert methods <= {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}, (
        "native lifecycle consumer missing"
    )
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    prefix = ModuleType("native_source_prefix")
    prefix.__dict__.update(
        {
            "time": time,
            "json": json,
            "_REGISTRY": SimpleNamespace(lock=threading.RLock()),
            "SubagentState": SimpleNamespace(PENDING="PENDING"),
        }
    )
    exec("from __future__ import annotations\n" + ast.unparse(cls), prefix.__dict__)
    factory = prefix.SubagentLifecycleService
    assert callable(factory)
    parent = SimpleNamespace(
        session_id="synthetic-parent-session",
        _subagent_id=mapping(binding["payload"])["native_root_id"],
    )
    parent._cold_state = SimpleNamespace(
        closed=False, session_id=parent.session_id, native_id=parent._subagent_id
    )
    lifecycle = factory(lambda: parent)
    child = SimpleNamespace(
        session_id=row["native_session_id"],
        _subagent_id=row["native_child_id"],
        _parent_session_id=parent.session_id,
        provider=None,
        model=None,
        tools=(),
        enabled_toolsets=(),
        _cold_state=SimpleNamespace(
            closed=False,
            session_id=row["native_session_id"],
            native_id=row["native_child_id"],
            parent_session_id=parent.session_id,
        ),
    )
    lifecycle._cold_batches[manifest["id"]] = {
        "manifest": manifest,
        "composition_material": (canonical(composition),),
        "response": {
            "protocol": payload["protocol"],
            "ticket": payload["ticket"],
            "manifest_ref": payload["manifest_ref"],
            "native_root_id": parent._subagent_id,
            "entries": [row],
        },
        "parent": parent,
        "parent_session_id": parent.session_id,
        "binding": None,
        "records": [SimpleNamespace(state="PENDING", agent=child)],
        "expires": time.monotonic() + 4.5,
    }
    cold = ModuleType("agent.cold_admission")
    monkeypatch.setitem(sys.modules, "agent.cold_admission", cold)
    # Pure producer code is real; identities remain SOURCE doubles, not native proof.
    exec((source.parent / "cold_admission.py").read_text(), cold.__dict__)
    child._cold_state = cold.ColdState(child.session_id, child._subagent_id, parent.session_id)

    async def peer_call(method: str, value: object, **kwargs: object) -> dict[str, object]:
        assert method == "omnis.managed.model_preflight"
        return mapping(lifecycle.model_preflight(value))

    host.peer = SimpleNamespace(call=peer_call, failure=None)

    async def native_call(operation: str, grant: object, payload: object) -> dict[str, object]:
        assert events == ["begin", "commit"]
        assert operation == "task_model_preflight"
        events.append("native-data-preflight")
        frame: dict[str, object] = {
            "version": 1,
            "id": str(uuid4()),
            "boot": host.boot,
            "capability": host.capability,
            "generation": host.generation,
            "epoch": host.epoch,
            "op": operation,
            "deadline_ns": host.deadline_ns,
            "payload": payload,
        }
        host._validate(frame)
        return {"managed": await host._managed(frame)}

    from omnis.modules.instance.service import RuntimeAuthority

    service.runtime_authority = AsyncMock(
        return_value=RuntimeAuthority(
            runtime.generation, runtime.epoch, time.monotonic_ns() + 1_000_000_000
        )
    )
    monkeypatch.setattr(runtime, "_exchange", native_call)
    request = NativeTaskCommand.model_validate(
        {
            **preflight_command(),
            "owner_id": owner,
            "instance_id": authority["instance_id"],
            "expected_epoch": authority["epoch"],
            "expected_generation": authority["generation"],
            "manifest_ref": records.reference(manifest),
            "data_approval": decision,
        }
    )
    handler = NativeTaskOwner(
        managed, service, UUID(str(authority["owner"])), int(str(authority["epoch"])), runtime
    )
    reply = await handler.handle(request)
    assert reply["task_status"] == "BLOCKED"
    assert mapping(reply["model_admission"])["reason"] == "NO_MODEL"
    assert mapping(reply["model_admission"])["projection_ref"] == payload["projection_ref"]
    assert events == ["begin", "commit", "native-data-preflight", "begin", "commit"]
    reserve.assert_not_awaited()

    from omnis.modules.settings.catalog_models import CatalogError

    before = canonical(graph)
    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED"):
        await consumer.prepare(
            connection,
            owner,
            records.reference(manifest),
            records.reference(binding),
            {
                **decision,
                "decision_id": str(uuid4()),
                "approved_text_digests": ["0" * 64],
            },
        )
    assert canonical(graph) == before
    with pytest.raises(CatalogError, match="MODEL_DATA_DECISION_CONFLICT"):
        await consumer.prepare(
            connection,
            owner,
            records.reference(manifest),
            records.reference(binding),
            {
                **decision,
                "approved_text_digests": ["0" * 64],
            },
        )
    assert canonical(graph) == before
    for key, bad in [("model_calls", False), ("native_turn", str(uuid4())), ("reason", "READY")]:
        with pytest.raises(CatalogError, match="MODEL_PREFLIGHT_REJECTED"):
            consumer.accept_preflight({**receipt, key: bad}, prepared)
        with pytest.raises(ValueError):
            adapter.validate_preflight_result({**receipt, key: bad}, payload)
    saved_id = child._subagent_id
    child._subagent_id = "forged-child"
    with pytest.raises(ValueError, match="lineage"):
        lifecycle.model_preflight(payload)
    child._subagent_id = saved_id
    assert lifecycle.model_preflight(payload)["reason"] == "NO_MODEL"
    original_parent = parent
    lifecycle._parent_agent_resolver = lambda: SimpleNamespace(**vars(original_parent))
    with pytest.raises(ValueError, match="lineage"):
        lifecycle.model_preflight(payload)
    lifecycle._parent_agent_resolver = lambda: original_parent
    assert lifecycle.model_preflight(payload)["reason"] == "NO_MODEL"
    runtime.boot = str(uuid4())
    with pytest.raises(CatalogError, match="TASK_INDETERMINATE"):
        await handler.handle(request)
    assert canonical(graph) == before
    reserve.assert_not_awaited()

    if not protocol_mode:
        return
    # SYNTHETIC_PROTOCOL_SEED_NOT_NATIVE_PROOF. SQL storage/fences are SOURCE
    # doubles; producer, ledger, qualified readers, owner and both UDS are real.
    import asyncio
    import os
    import tempfile

    from omnis.supervisor.native_tasks import control_task
    from omnis.transport.local_control import LocalControl
    from test_native_task_client import backpressured_client, peer_client
    from test_ready_model_configuration import configuration

    monkeypatch.setattr(budgets, "reserve", real_reserve)
    monkeypatch.setattr(budgets, "_scope_lock", AsyncMock())
    state: dict[str, object] = {
        "run_id": run,
        "binding_id": None,
        "stage_started": False,
        "release_started": False,
        "final_id": None,
    }
    monkeypatch.setattr(managed_store, "state", AsyncMock(side_effect=lambda *a, **k: dict(state)))

    async def owned(conn: object, actual_owner: str, pin: object) -> tuple[str, dict[str, object]]:
        return run, await get(conn, actual_owner, run, pin)

    monkeypatch.setattr(managed_store, "owned", owned)

    async def execute(statement: object, params: object = None) -> Mock:
        query = str(statement)
        args = {} if params is None else mapping(params)
        found: list[dict[str, object]] = []
        if "model-data-approval" in query:
            found = [
                r
                for r in graph
                if r["kind"] == "model-data-approval"
                and mapping(r["payload"])["decision_id"] == args["decision"]
            ]
        elif "contract-input-command" in query:
            found = [
                r
                for r in graph
                if r["kind"] == "contract-input-command"
                and mapping(r["payload"])["command_id"] == args["command"]
            ]
        elif "model-usage-receipt" in query:
            found = [
                r
                for r in graph
                if r["kind"] == "model-usage-receipt"
                and mapping(mapping(r["payload"])["usage"])["receipt_id"] == args["receipt"]
            ]
        elif "instance_id" not in query:
            raise AssertionError("unexpected SOURCE SQL")
        answer = Mock()
        answer.scalar_one.return_value = authority["instance_id"]
        answer.scalars.return_value.all.return_value = found
        return answer

    connection.execute = execute
    monkeypatch.setattr(managed.engine, "begin", lambda: fence(UUID(str(authority["owner"]))))
    service.engine = managed.engine
    monkeypatch.setattr(
        "omnis.transport.local_control.readiness_reason", AsyncMock(return_value=None)
    )
    back: dict[str, object] = {
        "manifest_ref": records.reference(manifest),
        "manifest": manifest,
        "binding": None,
        "results": [],
        "stage_started": False,
        "release_started": False,
    }
    monkeypatch.setattr(managed, "readback", AsyncMock(side_effect=lambda *_: dict(back)))
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(
            runtime.generation, runtime.epoch, time.monotonic_ns() + 4_000_000_000
        )
    )
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="dap-") as directory:
        root = Path(directory)
        requests: list[dict[str, object]] = []
        backpressure = protocol_case == "backpressure"
        measured: dict[str, int] = {}

        observed = asyncio.Event()

        def cold_result(payload: dict[str, object]) -> dict[str, object]:
            result = mapping(lifecycle.model_preflight(payload))
            return {**result, "model_calls": 1} if protocol_failure == "invalid_ack" else result

        peer = peer_client(
            root,
            requests,
            result=cold_result,
            reply=protocol_failure != "eof",
            failure=protocol_failure,
            observed=observed,
            runtime_boot=str(mapping(binding["payload"])["runtime_boot"]),
        )
        if backpressure:
            peer = backpressured_client(
                root, str(mapping(binding["payload"])["runtime_boot"]), measured
            )
        async with peer as real:
            handler.runtime = real
            drained = asyncio.Event()
            drain_writer = real.writer
            assert drain_writer is not None
            actual_drain = drain_writer.drain

            async def observed_drain() -> None:
                if backpressure:
                    measured["buffer_before_failure"] = (
                        drain_writer.transport.get_write_buffer_size()
                    )
                    observed.set()
                await actual_drain()
                drained.set()

            monkeypatch.setattr(drain_writer, "drain", observed_drain)
            async with LocalControl(
                root, service, handler.owner, handler.epoch, native_task=handler.handle
            ):
                config_reply = await control_task(
                    root,
                    {
                        **request.model_dump(mode="json", exclude={"data_approval"}),
                        "action": "model_configuration",
                        "configuration": configuration(),
                    },
                )
                state.update(binding_id=binding["id"], stage_started=True)
                back.update(binding=binding, stage_started=True)
                protocol_command = {
                    **request.model_dump(mode="json"),
                    "action": "model_protocol_prepare",
                    "provider_config_ref": config_reply["provider_config_ref"],
                    "protocol_id": str(uuid4()),
                    "protocol_caps": {
                        "calls": 1,
                        "output_tokens": 64,
                        "wall_seconds": 1 if backpressure else 3,
                    },
                }
                entered = 0

                @asynccontextmanager
                async def protocol_fence(*args: object) -> AsyncIterator[AsyncConnection]:
                    nonlocal entered
                    entered += 1
                    this_entry = entered
                    transport = real.writer.transport if real.writer is not None else None
                    if this_entry == 2 and protocol_failure == "before_sent":
                        raise CatalogError("TASK_INDETERMINATE")
                    try:
                        async with fence(*args) as conn:
                            yield conn
                    finally:
                        if this_entry == 2 and protocol_failure in {
                            "cancel",
                            "eof",
                            "timeout",
                            "invalid_ack",
                        }:
                            assert real.writer is None and real.reader is None
                            assert transport is not None and transport.is_closing()
                            if backpressure:
                                measured["buffer_at_a_exit"] = transport.get_write_buffer_size()

                service.native_preparation_commit = protocol_fence
                if protocol_case in {"duplicate", "conflict"}:
                    from omnis.modules.runs import model_protocol
                    from omnis.modules.runs.model_dispatch import ModelDispatch
                    from omnis.supervisor.runtime_client import FrozenPreflight

                    # SOURCE transaction/storage doubles: force BOTH actual initial
                    # replay reads to miss before either enters serialized T0.
                    # The public owner, replay/reserve/ledger and UDS remain real.
                    first_miss, both_missed = asyncio.Event(), asyncio.Event()
                    second_finished = asyncio.Event()
                    first_committed = asyncio.Event()
                    transaction_lock = asyncio.Lock()
                    actual_replay = model_protocol.replay
                    actual_reserve = model_protocol.reserve
                    replay_calls: dict[object, int] = {}
                    initial_misses = 0
                    first_handler: object = None
                    reserve_calls = 0
                    baseline = canonical(graph)
                    baseline_ids = {str(r["id"]) for r in graph}
                    t0_records = b""
                    service.runtime_authority.reset_mock()

                    async def replay_barrier(
                        conn: AsyncConnection, value: NativeTaskCommand
                    ) -> dict[str, object] | None:
                        nonlocal initial_misses, first_handler
                        task = asyncio.current_task()
                        replay_calls[task] = replay_calls.get(task, 0) + 1
                        result = await actual_replay(conn, value)
                        if replay_calls[task] == 1:
                            assert result is None
                            initial_misses += 1
                            if initial_misses == 1:
                                first_handler = task
                            first_miss.set()
                            if initial_misses == 2:
                                both_missed.set()
                            await asyncio.wait_for(both_missed.wait(), 0.75)
                        return result

                    async def counted_reserve(
                        conn: AsyncConnection,
                        dispatch: ModelDispatch,
                        value: NativeTaskCommand,
                        prepared: dict[str, object],
                        config: dict[str, object],
                        frozen: FrozenPreflight,
                    ) -> dict[str, object]:
                        nonlocal reserve_calls
                        reserve_calls += 1
                        return await actual_reserve(conn, dispatch, value, prepared, config, frozen)

                    @asynccontextmanager
                    async def serialized_t0(*args: object) -> AsyncIterator[AsyncConnection]:
                        nonlocal t0_records
                        # Model only transaction serialization, not PostgreSQL locks.
                        # Pause the winning caller AFTER its T0 has committed; let
                        # the losing T0 finish before A, avoiding a fake SETTLED reply.
                        if asyncio.current_task() is not first_handler:
                            await asyncio.wait_for(first_committed.wait(), 0.75)
                        async with transaction_lock:
                            async with protocol_fence(*args) as conn:
                                yield conn
                            current = entered
                        if current == 1:
                            t0_records = canonical(graph)
                            first_committed.set()
                            await asyncio.wait_for(second_finished.wait(), 0.75)

                    other_command = {
                        **protocol_command,
                        "protocol_caps": {
                            **mapping(protocol_command["protocol_caps"]),
                            "output_tokens": 63 if protocol_case == "conflict" else 64,
                        },
                    }
                    NativeTaskCommand.model_validate(other_command)
                    monkeypatch.setattr(model_protocol, "replay", replay_barrier)
                    monkeypatch.setattr(model_protocol, "reserve", counted_reserve)
                    service.native_preparation_commit = serialized_t0
                    first = asyncio.create_task(control_task(root, protocol_command))
                    second: asyncio.Task[dict[str, object]] | None = None
                    duplicate_accounting: dict[str, object] = {}
                    try:
                        await asyncio.wait_for(first_miss.wait(), 0.75)
                        second = asyncio.create_task(control_task(root, other_command))
                        await asyncio.wait_for(both_missed.wait(), 0.75)
                        if protocol_case == "conflict":
                            with pytest.raises(CatalogError) as denied:
                                await asyncio.wait_for(second, 1)
                            assert denied.value.reason == "COMMAND_CONFLICT"
                        else:
                            duplicate = await asyncio.wait_for(second, 1)
                            duplicate_accounting = mapping(duplicate["protocol_accounting"])
                            assert duplicate_accounting["state"] == "RESERVED"
                            assert duplicate_accounting["usage_state"] == "UNKNOWN"
                        assert not first.done() and not requests
                        assert initial_misses == 2 and reserve_calls == 1
                        assert canonical(graph) == t0_records
                        assert service.runtime_authority.await_count == 2
                        assert (
                            canonical([r for r in graph if str(r["id"]) in baseline_ids])
                            == baseline
                        )
                        second_finished.set()
                        reply = await asyncio.wait_for(first, 2)
                        first_accounting = mapping(reply["protocol_accounting"])
                        if protocol_case == "duplicate":
                            for key in ("descriptor_ref", "dispatch_ref", "request_id"):
                                assert duplicate_accounting[key] == first_accounting[key]
                        assert_protocol_records(
                            graph, baseline_ids, protocol_command, first_accounting
                        )
                        settled = canonical(graph)
                        # Existing receipt: conflict and original replay are both
                        # receive-only. No fresh authority/reservation/write/send.
                        monkeypatch.setattr(model_protocol, "replay", actual_replay)
                        service.runtime_authority.side_effect = AssertionError("replay grant")
                        service.native_preparation_commit = Mock(
                            side_effect=AssertionError("replay T0")
                        )
                        if protocol_case == "conflict":
                            with pytest.raises(CatalogError) as denied:
                                await control_task(root, other_command)
                            assert denied.value.reason == "COMMAND_CONFLICT"
                        again = await control_task(root, protocol_command)
                        assert again["protocol_accounting"] == first_accounting
                        assert canonical(graph) == settled
                        assert reserve_calls == 1 and len(requests) == 1
                    finally:
                        both_missed.set()
                        first_committed.set()
                        second_finished.set()
                        tasks = [first] if second is None else [first, second]
                        for pending in tasks:
                            if not pending.done():
                                pending.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                elif protocol_failure is None:
                    reply = await control_task(root, protocol_command)
                else:
                    if protocol_failure == "cancel":
                        if cleanup_fault == "expired":
                            original_back = managed.readback

                            async def delayed_back(value: object) -> dict[str, object]:
                                await asyncio.sleep(1.25)
                                return await original_back(value)

                            monkeypatch.setattr(managed, "readback", delayed_back)
                        owner_started = asyncio.get_running_loop().time()
                        task = asyncio.create_task(
                            handler.handle(NativeTaskCommand.model_validate(protocol_command))
                        )
                        await asyncio.wait_for(observed.wait(), 2)
                        if not backpressure:
                            await asyncio.wait_for(drained.wait(), 0.2)
                        writer = real.writer
                        assert writer is not None
                        actual_wait_closed = writer.wait_closed
                        actual_readback = budgets.readback

                        async def broken_wait_closed() -> None:
                            await actual_wait_closed()
                            raise OSError("SYNTHETIC_CLOSE_ERROR")

                        async def broken_readback(
                            *args: object, **kwargs: object
                        ) -> dict[str, object]:
                            from sqlalchemy.exc import SQLAlchemyError

                            if cleanup_fault in {"stall", "expired"}:
                                await asyncio.Event().wait()
                            raise SQLAlchemyError("SYNTHETIC_DB_CLEANUP_ERROR")

                        if cleanup_fault is not None:
                            monkeypatch.setattr(writer, "wait_closed", broken_wait_closed)
                            monkeypatch.setattr(budgets, "readback", broken_readback)
                        started = asyncio.get_running_loop().time()
                        if cleanup_fault != "expired":
                            task.cancel()
                        try:
                            async with asyncio.timeout(4.25):  # test fuse, not a product grant
                                with pytest.raises(
                                    TimeoutError
                                    if cleanup_fault == "expired"
                                    else asyncio.CancelledError
                                ):
                                    await task
                        finally:
                            monkeypatch.setattr(budgets, "readback", actual_readback)
                        assert asyncio.get_running_loop().time() - started < 4.1
                        assert asyncio.get_running_loop().time() - owner_started < 4.15
                    else:
                        with pytest.raises(
                            CatalogError,
                            match=(
                                "TASK_REJECTED"
                                if protocol_failure == "invalid_ack"
                                else "TASK_INDETERMINATE"
                            ),
                        ):
                            await control_task(root, protocol_command)
                    if protocol_failure != "before_sent":
                        assert real.writer is None and real.reader is None
                    reply = await control_task(root, protocol_command)
                if protocol_failure != "before_sent" and not backpressure:
                    assert drained.is_set()
                accounting = mapping(reply["protocol_accounting"])
                assert accounting["state"] == (
                    "SETTLED"
                    if protocol_failure is None
                    else "RELEASED"
                    if protocol_failure == "before_sent"
                    else "SENT"
                )
                assert accounting["usage_state"] == (
                    "KNOWN" if protocol_failure is None else "UNKNOWN"
                )
                assert (
                    accounting["protocol_calls"] == (0 if protocol_failure == "before_sent" else 1)
                    and accounting["model_calls"] == 0
                )
                assert accounting["output_tokens"] == (0 if protocol_failure is None else None)
                expected_requests = 0 if protocol_failure == "before_sent" or backpressure else 1
                assert len(requests) == expected_requests
                if protocol_case == "descriptor_version":
                    from omnis.modules.runs import model_protocol

                    command_dto = NativeTaskCommand.model_validate(protocol_command)
                    refs = await model_protocol.replay(connection, command_dto)
                    assert refs is not None
                    descriptor = next(r for r in graph if r["kind"] == "model-dispatch-owner")
                    forged = records.envelope(
                        "model-dispatch-owner", {**mapping(descriptor["payload"]), "version": True}
                    )
                    actual_owned, actual_budget_read = managed_store.owned, budgets.readback

                    async def forged_owned(
                        conn: AsyncConnection, who: str, pin: object
                    ) -> tuple[str, dict[str, object]]:
                        if pin == refs["descriptor_ref"]:
                            return run, forged
                        return await actual_owned(conn, who, pin)

                    async def forged_dispatch(
                        conn: AsyncConnection, who: str, pin: object
                    ) -> dict[str, object]:
                        value = await actual_budget_read(conn, who, pin)
                        dispatch = mapping(value["dispatch"])
                        return {
                            **value,
                            "dispatch": {
                                **dispatch,
                                "payload": {
                                    **mapping(dispatch["payload"]),
                                    "dispatch_owner_ref": records.reference(forged),
                                },
                            },
                        }

                    with monkeypatch.context() as mutation:
                        mutation.setattr(managed_store, "owned", forged_owned)
                        mutation.setattr(budgets, "readback", forged_dispatch)
                        with pytest.raises(CatalogError):
                            await model_protocol.qualified(connection, consumer, command_dto, refs)
                if protocol_case in {
                    "usage_tokens",
                    "usage_identity",
                    "usage_cost_observed",
                    "usage_cost_estimate",
                    "usage_provider_receipt",
                }:
                    from omnis.modules.runs import model_protocol
                    from omnis.modules.tasks.managed_contract import record

                    command_dto = NativeTaskCommand.model_validate(protocol_command)
                    usage_refs = await model_protocol.replay(connection, command_dto)
                    assert usage_refs is not None
                    usage = next(r for r in graph if r["kind"] == "model-usage-receipt")
                    original_usage = dict(usage)
                    usage_body = mapping(usage["payload"])
                    usage_value = mapping(usage_body["usage"])
                    changes: dict[str, dict[str, object]] = {
                        "usage_tokens": {"output_tokens": 1},
                        "usage_identity": {"receipt_id": str(uuid4())},
                        "usage_cost_observed": {"cost_observed": "0"},
                        "usage_cost_estimate": {"cost_estimate": "0"},
                        "usage_provider_receipt": {
                            "provider_receipt_ref": records.reference(
                                records.envelope("provider-receipt", {})
                            )
                        },
                    }
                    usage["payload"] = {
                        **usage_body,
                        "usage": {**usage_value, **changes[protocol_case]},
                    }
                    usage["digest"] = sha256(
                        canonical({k: v for k, v in usage.items() if k != "digest"})
                    ).hexdigest()
                    record(usage, "model-usage-receipt")
                    retained = canonical(graph)
                    try:
                        ledger = await budgets.readback(
                            connection, owner, usage_refs["dispatch_ref"]
                        )
                        assert ledger["state"] == "SETTLED"
                        assert ledger["charged_output_tokens"] == (
                            1 if protocol_case == "usage_tokens" else 0
                        )
                        with monkeypatch.context() as mutation:
                            mutation.setattr(
                                managed_store, "put", AsyncMock(side_effect=AssertionError("write"))
                            )
                            mutation.setattr(
                                service,
                                "native_preparation_commit",
                                Mock(side_effect=AssertionError("replay fence")),
                            )
                            mutation.setattr(
                                service,
                                "runtime_authority",
                                AsyncMock(side_effect=AssertionError("replay grant")),
                            )
                            with pytest.raises(CatalogError, match="MODEL_RECEIPT_CONFLICT"):
                                await model_protocol.readback(
                                    connection, consumer, command_dto, usage_refs
                                )
                            with pytest.raises(CatalogError, match="TASK_REJECTED"):
                                await control_task(root, protocol_command)
                        if canonical(graph) != retained:
                            raise AssertionError("readback mutated retained records")
                    finally:
                        usage.clear()
                        usage.update(original_usage)
                if protocol_case == "configuration_payload":
                    from omnis.modules.runs import model_protocol
                    from omnis.modules.tasks.managed_contract import record

                    command_dto = NativeTaskCommand.model_validate(protocol_command)
                    configuration_refs = await model_protocol.replay(connection, command_dto)
                    assert configuration_refs is not None
                    configuration_receipt = next(
                        r for r in graph if r["kind"] == "model-configuration-receipt"
                    )
                    protocol_receipt = next(
                        r for r in graph if r["kind"] == "model-protocol-receipt"
                    )
                    originals = [(r, dict(r)) for r in (configuration_receipt, protocol_receipt)]
                    configuration_receipt["payload"] = {
                        **mapping(configuration_receipt["payload"]),
                        "inference_authorized": True,
                    }
                    configuration_receipt["digest"] = sha256(
                        canonical({k: v for k, v in configuration_receipt.items() if k != "digest"})
                    ).hexdigest()
                    protocol_body = mapping(protocol_receipt["payload"])
                    protocol_receipt["payload"] = {
                        **protocol_body,
                        "model_admission": {
                            **mapping(protocol_body["model_admission"]),
                            "configuration_receipt_ref": records.reference(configuration_receipt),
                        },
                    }
                    protocol_receipt["digest"] = sha256(
                        canonical({k: v for k, v in protocol_receipt.items() if k != "digest"})
                    ).hexdigest()
                    record(configuration_receipt, "model-configuration-receipt")
                    record(protocol_receipt, "model-protocol-receipt")
                    retained = canonical(graph)
                    try:
                        with monkeypatch.context() as mutation:
                            mutation.setattr(
                                managed_store, "put", AsyncMock(side_effect=AssertionError("write"))
                            )
                            mutation.setattr(
                                service,
                                "native_preparation_commit",
                                Mock(side_effect=AssertionError("replay fence")),
                            )
                            mutation.setattr(
                                service,
                                "runtime_authority",
                                AsyncMock(side_effect=AssertionError("replay grant")),
                            )
                            with pytest.raises(CatalogError, match="MODEL_RECEIPT_CONFLICT"):
                                await model_protocol.readback(
                                    connection, consumer, command_dto, configuration_refs
                                )
                            with pytest.raises(CatalogError, match="TASK_REJECTED"):
                                await control_task(root, protocol_command)
                        if canonical(graph) != retained:
                            raise AssertionError("readback mutated retained records")
                    finally:
                        for changed, original_record in originals:
                            changed.clear()
                            changed.update(original_record)
                if protocol_case == "receipt_extra":
                    receipt = next(r for r in graph if r["kind"] == "model-protocol-receipt")
                    original_receipt = dict(receipt)
                    receipt["payload"] = {
                        **mapping(receipt["payload"]),
                        "extra": "SYNTHETIC_SENTINEL",
                    }
                    receipt["digest"] = sha256(
                        canonical({k: v for k, v in receipt.items() if k != "digest"})
                    ).hexdigest()
                    try:
                        with pytest.raises(CatalogError):
                            await control_task(root, protocol_command)
                    finally:
                        receipt.clear()
                        receipt.update(original_receipt)
                service.runtime_authority.reset_mock()
                service.native_preparation_commit = Mock(side_effect=AssertionError("replay grant"))
                replay = await control_task(root, protocol_command)
                assert mapping(replay["protocol_accounting"]) == accounting
                assert len(requests) == expected_requests
                service.runtime_authority.assert_not_awaited()
        if backpressure:
            assert measured["buffer_before_failure"] > 0
            assert measured["buffer_at_a_exit"] == 0
            assert measured["buffer_at_return"] == 0
            assert measured["complete_frames_after_return"] == 0
            assert measured["received_after_return"] > 0
    assert not {"native-turn"} & {str(r["kind"]) for r in graph}


def assert_protocol_records(
    graph: list[dict[str, object]],
    baseline_ids: set[str],
    command: dict[str, object],
    accounting: dict[str, object],
) -> None:
    """One shared SOURCE/PG oracle over actual producer envelopes, not RPC frames."""
    from collections import Counter

    added = [r for r in graph if str(r["id"]) not in baseline_ids]
    assert Counter(str(r["kind"]) for r in added) == {
        "model-budget": 1,
        "model-dispatch-owner": 1,
        "model-reservation": 1,
        "model-dispatch": 1,
        "contract-input-command": 1,
        "model-dispatch-transition": 1,
        "model-usage-receipt": 1,
        "model-protocol-receipt": 1,
    }
    by_kind = {str(r["kind"]): r for r in added}
    for kind in ("model-data-approval", "model-projection", "model-configuration-receipt"):
        assert sum(r["kind"] == kind for r in graph) == 1
    descriptor = by_kind["model-dispatch-owner"]
    dispatch = by_kind["model-dispatch"]
    assert accounting["descriptor_ref"] == records.reference(descriptor)
    assert accounting["dispatch_ref"] == records.reference(dispatch)
    assert mapping(dispatch["payload"])["dispatch_owner_ref"] == records.reference(descriptor)
    assert mapping(dispatch["payload"])["reservation_ref"] == records.reference(
        by_kind["model-reservation"]
    )
    receipt = mapping(by_kind["contract-input-command"]["payload"])
    assert receipt["command_id"] == command["protocol_id"]
    assert receipt["operation"] == command["action"]
    checked = NativeTaskCommand.model_validate(command).model_dump(mode="json")
    assert receipt["request_digest"] == sha256(canonical(checked)).hexdigest()
    assert receipt["result_refs"] == {
        "descriptor_ref": accounting["descriptor_ref"],
        "dispatch_ref": accounting["dispatch_ref"],
    }
    for kind in ("model-dispatch-transition", "model-usage-receipt", "model-protocol-receipt"):
        assert mapping(by_kind[kind]["payload"])["dispatch_ref"] == accounting["dispatch_ref"]
    sent = mapping(by_kind["model-dispatch-transition"]["payload"])
    usage = mapping(by_kind["model-usage-receipt"]["payload"])
    assert (sent["state"], sent["sequence"]) == ("SENT", 1)
    assert (usage["state"], usage["sequence"]) == ("SETTLED", 2)
    assert mapping(usage["usage"])["receipt_id"] == accounting["request_id"]
    assert (
        mapping(by_kind["model-protocol-receipt"]["payload"])["request_id"]
        == accounting["request_id"]
    )
    assert mapping(descriptor["payload"])["requested_caps"] == command["protocol_caps"]
    assert mapping(descriptor["payload"])["admitted_caps"] == command["protocol_caps"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["duplicate", "conflict"])
async def test_protocol_concurrent_initial_replay_misses_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_case=case
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [None, "eof", "invalid_ack", "timeout", "cancel", "before_sent"]
)
async def test_protocol_data_reserve_sent_transport_settlement_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path,
        monkeypatch,
        protocol_mode=True,
        protocol_failure=failure,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "cancel"])
async def test_protocol_backpressure_retires_before_owner_a_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path,
        monkeypatch,
        protocol_mode=True,
        protocol_failure=failure,
        protocol_case="backpressure",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["receipt_extra", "descriptor_version"])
async def test_protocol_replay_rejects_resealed_receipt_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_case=case
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "usage_tokens",
        "usage_identity",
        "usage_cost_observed",
        "usage_cost_estimate",
        "usage_provider_receipt",
    ],
)
async def test_protocol_replay_rejects_resealed_usage_contradiction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_case=case
    )


@pytest.mark.asyncio
async def test_protocol_replay_rejects_resealed_configuration_contradiction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_case="configuration_payload"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["db_error", "stall", "expired"])
async def test_protocol_cancel_preserves_primary_and_bounds_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_failure="cancel", cleanup_fault=fault
    )


@pytest.mark.asyncio
async def test_protocol_command_reaches_owner_not_receive_fallback() -> None:
    """RED tracer at the actual owner entry; storage is a SOURCE boundary double."""
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from omnis.supervisor.runtime_client import RuntimeClient

    value = {
        **preflight_command(),
        "action": "model_protocol_prepare",
        "protocol_id": str(uuid4()),
        "protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 3},
        "provider_config_ref": records.reference(records.envelope("provider-config", {})),
    }
    command = NativeTaskCommand.model_validate(value)
    domain = Mock(spec=ManagedAdmission)
    domain.readback = AsyncMock(side_effect=CatalogError("OWNED_SOURCE_LOOKUP"))
    owner = NativeTaskOwner(
        domain,
        Mock(spec=InstanceService),
        uuid4(),
        1,
        RuntimeClient(Path("/unused"), generation=0, epoch=1),
    )
    with pytest.raises(CatalogError, match="OWNED_SOURCE_LOOKUP"):
        await owner.handle(command)
    domain.readback.assert_awaited_once()


@pytest.mark.parametrize("count", [32, 33])
def test_protocol_command_maximum_control_frame(count: int) -> None:
    value = {
        **preflight_command(),
        "action": "model_protocol_validation",
        "protocol_id": str(uuid4()),
        "protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 3},
        "provider_config_ref": records.reference(records.envelope("provider-config", {})),
    }
    approval = mapping(value["data_approval"])
    approval["approved_text_digests"] = [sha256(str(i).encode()).hexdigest() for i in range(count)]
    value["data_approval"] = approval
    if count == 33:
        with pytest.raises(ValueError):
            NativeTaskCommand.model_validate(value)
    else:
        checked = NativeTaskCommand.model_validate(value).model_dump(mode="json")
        assert len(canonical(checked)) <= 3600
        assert (
            len(canonical({"version": 1, "capability": "a" * 64, "command": checked})) + 1 <= 4096
        )


@pytest.mark.parametrize(
    "change",
    [
        {"purpose": "VALIDATION"},
        {"cost_limit": "0"},
        {"retry": True},
        {"extra_body": {}},
        {"protocol_caps": {"calls": 2, "output_tokens": 64, "wall_seconds": 3}},
        {"protocol_caps": {"calls": 1, "output_tokens": 65, "wall_seconds": 3}},
        {"protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 4}},
        {"protocol_caps": {"calls": True, "output_tokens": 64, "wall_seconds": 3}},
    ],
)
def test_protocol_command_rejects_untrusted_expansion(change: dict[str, object]) -> None:
    value = {
        **preflight_command(),
        "action": "model_protocol_prepare",
        "protocol_id": str(uuid4()),
        "protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 3},
        "provider_config_ref": records.reference(records.envelope("provider-config", {})),
        **change,
    }
    with pytest.raises(ValueError):
        NativeTaskCommand.model_validate(value)
