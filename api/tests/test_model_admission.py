"""Bounded control/admission SOURCE tests; never native or persistent-PG proof."""

import asyncio
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
from omnis.modules.runs.model_dispatch import ModelDispatch
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import mapping, sequence
from omnis.policy import budgets
from omnis.policy.model_projection import SyntheticApproval, projection_input
from test_model_projection import source_graph, text_digests


async def wait_protocol_marker(
    marker: asyncio.Event, sender: asyncio.Task[dict[str, object]]
) -> None:
    """Race the marker against control_task's own deadline, never reset its budget."""
    waiter = asyncio.create_task(marker.wait())
    try:
        await asyncio.wait({waiter, sender}, return_when=asyncio.FIRST_COMPLETED)
        if sender.done():
            sender.result()  # Preserve the actual failure/cancellation, even if both are ready.
        assert marker.is_set(), "bounded control completed before protocol marker"
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


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
    catalog_boundary: str | None = None,
    legacy_catalog: bool = False,
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
        read_only: bool = False,
    ) -> BuildSource:
        # SOURCE storage/material seam only; producer is actual selection_payload,
        # full publication/material qualification is tested independently in PG.
        source = sources[0]
        assert type(read_only) is bool
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
    if catalog_boundary is not None:
        from collections.abc import AsyncIterator
        from contextlib import asynccontextmanager

        from omnis.modules.runs import model_protocol
        from omnis.modules.runs.plan_snapshot import snapshot_payload
        from omnis.modules.settings import candidate_catalog
        from omnis.modules.settings.catalog_models import CatalogError
        from omnis.modules.settings.catalog_publication import PublicationCatalog
        from omnis.supervisor.native_tasks import NativeTaskOwner
        from omnis.supervisor.runtime_client import FrozenPreflight

        # SOURCE lookup/descriptor doubles; stop just after the real legacy gate.
        # This is not full historical protocol replay or a persisted ledger.
        class PassedCatalogGuard(Exception):
            pass

        managed.root = tmp_path / "catalog"
        managed.root.mkdir(mode=0o700)
        monkeypatch.setattr(managed, "_source", ManagedAdmission._source.__get__(managed))
        selected = sources[0].selection
        candidate = records.envelope("candidate-snapshot", {})
        publication = records.envelope(
            "catalog-publication",
            {
                "compiler_revision": candidate_catalog.LEGACY_COMPILER_REVISION
                if legacy_catalog
                else candidate_catalog.COMPILER_REVISION,
                "evaluator_revision": candidate_catalog.LEGACY_EVALUATOR_REVISION
                if legacy_catalog
                else candidate_catalog.EVALUATOR_REVISION,
                "snapshot_ref": records.reference(candidate),
                "profile_ref": records.reference(records.envelope("profile", {})),
                "candidate_refs": [],
                "dependency_closure_refs": [],
                "dependency_artifact_refs": [],
                "material_digest": "c" * 64,
                "resolved_index_digest": "d" * 64,
                "dependency_closure_digest": "e" * 64,
                "created_by": owner,
            },
        )
        snapshot = records.envelope("run-snapshot", snapshot_payload(publication))
        group = str(uuid4())

        async def catalog_get(
            conn: AsyncConnection, actual_owner: str, pin: object
        ) -> tuple[str, dict[str, object]]:
            assert conn is connection and actual_owner == owner
            if pin == records.reference(selected):
                return group, selected
            if pin == mapping(selected["payload"])["snapshot_ref"]:
                return group, snapshot
            assert pin == records.reference(publication)
            return group, publication

        monkeypatch.setattr(records, "get", catalog_get)
        monkeypatch.setattr(
            PublicationCatalog,
            "_readback",
            AsyncMock(
                return_value={
                    "publication": publication,
                    "snapshot": candidate,
                    "resolved_index": {},
                }
            ),
        )
        monkeypatch.setattr(
            candidate_catalog.CandidateCatalog,
            "sources",
            AsyncMock(side_effect=PassedCatalogGuard),
        )
        command = NativeTaskCommand.model_validate(
            {
                **preflight_command(),
                "owner_id": owner,
                "manifest_ref": records.reference(manifest),
                "action": "model_protocol_prepare",
                "protocol_id": str(uuid4()),
                "provider_config_ref": records.reference(records.envelope("provider-config", {})),
                "protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 3},
            }
        )
        descriptor = records.envelope(
            "model-dispatch-owner",
            {
                "version": 1,
                "provenance": model_protocol.PROVENANCE,
                "owner_id": owner,
                "run_id": run,
                "manifest_ref": command.manifest_ref,
                "binding_ref": records.reference(binding),
                "authority": mapping(binding["payload"])["authority"],
                "runtime_boot": mapping(binding["payload"])["runtime_boot"],
                "purpose": "PREPARE",
                "provider_config_ref": command.provider_config_ref,
                "execution_selection_ref": records.reference(selected),
                "prepared": prepared,
                "requested_caps": command.protocol_caps,
                "admitted_caps": command.protocol_caps,
                "request_id": str(uuid4()),
                "body_digest": "a" * 64,
                "frame_digest": "b" * 64,
                "body": "{}",
                "deadline": "2030-01-01T00:00:00+00:00",
                "deadline_ns": 1,
            },
        )
        catalog_refs: dict[str, object] = {
            "descriptor_ref": records.reference(descriptor),
            "dispatch_ref": records.reference(records.envelope("model-dispatch", {})),
        }
        monkeypatch.setattr(managed_store, "command_replay", AsyncMock(return_value=catalog_refs))
        monkeypatch.setattr(managed_store, "owned", AsyncMock(return_value=(run, descriptor)))

        @asynccontextmanager
        async def begin() -> AsyncIterator[AsyncConnection]:
            yield connection

        monkeypatch.setattr(managed.engine, "begin", begin)
        handler = object.__new__(NativeTaskOwner)
        handler.domain = managed
        for sink, name in (
            (records, "put"),
            (records, "complete"),
            (managed_store, "put"),
            (managed_store, "command_complete"),
            (budgets, "create_budget"),
            (budgets, "reserve"),
            (budgets, "mark_sent"),
        ):
            monkeypatch.setattr(sink, name, AsyncMock(side_effect=AssertionError("write denied")))
        before = canonical(graph)
        legacy_denied = legacy_catalog and catalog_boundary in {"prepare", "reserve", "sent"}
        with pytest.raises(
            CatalogError if legacy_denied else PassedCatalogGuard,
            match="^LEGACY_READ_ONLY$" if legacy_denied else None,
        ):
            frozen = FrozenPreflight(
                str(uuid4()),
                str(mapping(binding["payload"])["runtime_boot"]),
                0,
                1,
                1,
                3,
                b"{}",
                b"{}",
            )
            if catalog_boundary == "replay":
                await handler._model_protocol(command, binding, 0.0)
            elif catalog_boundary == "read":
                await model_protocol.readback(connection, consumer, command, catalog_refs)
            elif catalog_boundary == "settle":
                await model_protocol.settle(connection, consumer, command, catalog_refs, {})
            elif catalog_boundary == "sent":
                await model_protocol.mark_sent(connection, consumer, command, catalog_refs, frozen)
            elif catalog_boundary == "reserve":
                from test_ready_model_configuration import configuration

                await model_protocol.reserve(
                    connection, consumer, command, prepared, configuration(), frozen
                )
            else:
                assert catalog_boundary == "prepare"
                await consumer.prepare(
                    connection,
                    owner,
                    records.reference(manifest),
                    records.reference(binding),
                    {**decision, "decision_id": str(uuid4())},
                )
        assert canonical(graph) == before
        return
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
            admission_case = protocol_case in {"budget", "budget_conflict", "deadline_b"}
            protocol_errors: list[str] = []

            async def observed_handle(value: NativeTaskCommand) -> dict[str, object]:
                try:
                    return await handler.handle(value)
                except CatalogError as error:
                    protocol_errors.append(error.reason)
                    raise

            async with LocalControl(
                root,
                service,
                handler.owner,
                handler.epoch,
                native_task=observed_handle if admission_case else handler.handle,
            ):
                config = configuration()
                if protocol_case == "budget":
                    config["technical_caps"] = {"calls": 1, "output_tokens": 64, "wall_seconds": 2}
                config_reply = await control_task(
                    root,
                    {
                        **request.model_dump(mode="json", exclude={"data_approval"}),
                        "action": "model_configuration",
                        "configuration": config,
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
                        "wall_seconds": 1 if backpressure or protocol_failure == "timeout" else 3,
                    },
                }
                entered = 0
                failure_baseline = {str(r["id"]) for r in graph}

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
                if admission_case:
                    from datetime import UTC, datetime, timedelta

                    from omnis.modules.runs import model_protocol
                    from omnis.policy import model_dispatch_contract
                    from omnis.supervisor.runtime_client import FrozenPreflight

                    # SOURCE-only rollback double. PostgreSQL rollback is exercised
                    # separately by the same public commands in the PG case.
                    @asynccontextmanager
                    async def rollback_fence(*args: object) -> AsyncIterator[AsyncConnection]:
                        snapshot = list(graph)
                        try:
                            async with protocol_fence(*args) as conn:
                                yield conn
                        except BaseException:
                            graph[:] = snapshot
                            raise

                    service.native_preparation_commit = rollback_fence
                    budget_reserve = AsyncMock(wraps=model_protocol.reserve)
                    monkeypatch.setattr(model_protocol, "reserve", budget_reserve)
                    service.runtime_authority.reset_mock()
                    baseline_ids = {str(r["id"]) for r in graph}
                    accepted: list[tuple[dict[str, object], dict[str, object]]] = []

                    if protocol_case == "budget_conflict":
                        run_record = next(r for r in graph if r["kind"] == "managed-run")
                        seeded = await budgets.create_budget(
                            connection,
                            owner,
                            records.reference(run_record),
                            {**model_protocol.LIMITS, "output_tokens": 127},
                        )
                        before_conflict = canonical(graph)
                        with pytest.raises(CatalogError) as denied:
                            await control_task(root, protocol_command)
                        assert denied.value.reason == "TASK_REJECTED"
                        assert protocol_errors == ["MODEL_BUDGET_CONFLICT"]
                        assert canonical(graph) == before_conflict
                        assert [r for r in graph if r["kind"] == "model-budget"] == [seeded]
                        assert not requests and budget_reserve.await_count == 1
                        return

                    if protocol_case == "budget":
                        # A qualified source cap is lower than the public DTO cap.
                        # The original request (wall=3) is valid DTO, but not admitted.
                        NativeTaskCommand.model_validate(protocol_command)
                        before_cap = canonical(graph)
                        with pytest.raises(CatalogError) as denied:
                            await control_task(root, protocol_command)
                        assert denied.value.reason == "TASK_REJECTED"
                        assert protocol_errors == ["MODEL_PROTOCOL_CAP_REJECTED"]
                        assert canonical(graph) == before_cap
                        assert not requests and budget_reserve.await_count == 0
                        protocol_command["protocol_caps"] = {
                            "calls": 1,
                            "output_tokens": 64,
                            "wall_seconds": 2,
                        }
                        for action, purpose in (
                            ("model_protocol_prepare", "PREPARE"),
                            ("model_protocol_validation", "VALIDATION"),
                        ):
                            if accepted:
                                # The existing synthetic peer handles one frame per
                                # connection. Reopen only for a NEW validation id,
                                # never as retry/resend of an accepted request.
                                await real.close()
                                real.reader, real.writer = await asyncio.open_unix_connection(
                                    str(root / "peer.sock")
                                )
                            value = {
                                **protocol_command,
                                "action": action,
                                "protocol_id": str(uuid4()),
                            }
                            prior_graph = canonical(graph)
                            prior_ids = {str(r["id"]) for r in graph}
                            reply = await control_task(root, value)
                            assert (
                                canonical([r for r in graph if str(r["id"]) in prior_ids])
                                == prior_graph
                            )
                            accounting = mapping(reply["protocol_accounting"])
                            assert_protocol_budget_accounting(accounting, value, purpose)
                            accepted.append((value, accounting))
                            before_denial = canonical(graph)
                            sent_count = len(requests)
                            # Fresh id is exhaustion, not replay/conflict. Settlement
                            # keeps the protocol call charged despite zero model use.
                            with pytest.raises(CatalogError) as denied:
                                await control_task(root, {**value, "protocol_id": str(uuid4())})
                            assert denied.value.reason == "TASK_REJECTED"
                            assert protocol_errors[-1] == "MODEL_BUDGET_EXHAUSTED"
                            assert canonical(graph) == before_denial
                            assert len(requests) == sent_count
                        assert budget_reserve.await_count == 4 and len(requests) == 2
                        assert_protocol_budget_records(graph, baseline_ids, accepted)
                    else:
                        # Deterministic SOURCE clock/lock doubles, NOT a PG expiry
                        # proof. Freeze/grant/request are unmodified; advance only
                        # the deadline guard's wall clock after B has begun waiting.
                        entered_b, release_b = asyncio.Event(), asyncio.Event()
                        actual_mark = model_protocol.mark_sent
                        frozen_values: list[FrozenPreflight] = []
                        actual_freeze = real.freeze_preflight

                        def freeze(
                            grant: RuntimeAuthority,
                            payload: dict[str, object],
                            *,
                            wall_seconds: int,
                        ) -> FrozenPreflight:
                            frozen = actual_freeze(grant, payload, wall_seconds=wall_seconds)
                            frozen_values.append(frozen)
                            return frozen

                        async def blocked_mark(
                            conn: AsyncConnection,
                            dispatch: ModelDispatch,
                            value: NativeTaskCommand,
                            refs: dict[str, object],
                            frozen: FrozenPreflight,
                        ) -> None:
                            assert entered == 2  # T0 completed, A entered.
                            entered_b.set()
                            await release_b.wait()
                            await actual_mark(conn, dispatch, value, refs, frozen)

                        monkeypatch.setattr(real, "freeze_preflight", freeze)
                        monkeypatch.setattr(model_protocol, "mark_sent", blocked_mark)
                        sender = asyncio.create_task(control_task(root, protocol_command))
                        try:
                            await wait_protocol_marker(entered_b, sender)
                            assert len(frozen_values) == 1 and not requests
                            descriptor = next(
                                r for r in graph if r["kind"] == "model-dispatch-owner"
                            )
                            deadline = datetime.fromisoformat(
                                str(mapping(descriptor["payload"])["deadline"])
                            )
                            assert (
                                mapping(descriptor["payload"])["deadline_ns"]
                                == frozen_values[0].deadline_ns
                            )

                            class ExpiredClock(datetime):
                                @classmethod
                                def now(cls, tz: object = None) -> "ExpiredClock":
                                    assert tz is UTC
                                    return cls.fromtimestamp(
                                        (deadline + timedelta(microseconds=1)).timestamp(), UTC
                                    )

                            with monkeypatch.context() as clock:
                                clock.setattr(model_dispatch_contract, "datetime", ExpiredClock)
                                release_b.set()
                                with pytest.raises(CatalogError) as denied:
                                    await sender
                            assert denied.value.reason == "TASK_REJECTED"
                            assert protocol_errors == ["MODEL_DEADLINE_EXPIRED"]
                        finally:
                            release_b.set()
                            if not sender.done():
                                sender.cancel()
                            await asyncio.gather(sender, return_exceptions=True)
                        # Monotonic time is intentionally still live in this SOURCE
                        # control, so cleanup can prove no-send and release. PG must
                        # retain RESERVED when its real frozen deadline has expired.
                        reply = await control_task(root, protocol_command)
                        accounting = mapping(reply["protocol_accounting"])
                        assert accounting["state"] == "RELEASED"
                        assert accounting["usage_state"] == "UNKNOWN"
                        assert accounting["protocol_calls"] == accounting["model_calls"] == 0
                        assert not requests and not drained.is_set()
                        assert all(
                            mapping(r["payload"])["state"] != "SENT"
                            for r in graph
                            if r["kind"] == "model-dispatch-transition"
                        )
                        accepted.append((protocol_command, accounting))
                    settled = canonical(graph)
                    calls = budget_reserve.await_count
                    service.runtime_authority.side_effect = AssertionError("replay grant")
                    service.native_preparation_commit = Mock(
                        side_effect=AssertionError("replay T0")
                    )
                    for value, accounting in accepted:
                        replay = await control_task(root, value)
                        assert replay["protocol_accounting"] == accounting
                        refs = await model_protocol.replay(
                            connection, NativeTaskCommand.model_validate(value)
                        )
                        assert refs is not None
                        assert (
                            await model_protocol.readback(
                                connection, consumer, NativeTaskCommand.model_validate(value), refs
                            )
                            == accounting
                        )
                    assert canonical(graph) == settled and budget_reserve.await_count == calls
                    assert len(requests) == (2 if protocol_case == "budget" else 0)
                    return
                if protocol_case in {"duplicate", "conflict"}:
                    from omnis.modules.runs import model_protocol
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
                                await second
                            assert denied.value.reason == "COMMAND_CONFLICT"
                        else:
                            duplicate = await second
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
                        reply = await first  # control_task retains its original 4s deadline.
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
                if protocol_failure in {"eof", "timeout", "cancel", "invalid_ack"}:
                    assert_protocol_failure_records(
                        graph, failure_baseline, protocol_command, accounting
                    )
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
                            await model_protocol.qualified(
                                connection, consumer, command_dto, refs, read_only=True
                            )
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


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("boundary", ["replay", "read", "settle", "prepare", "reserve", "sent"])
async def test_legacy_catalog_model_admission_intent_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, legacy: bool
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, catalog_boundary=boundary, legacy_catalog=legacy
    )


def test_protocol_private_failure_channel_source(tmp_path: Path) -> None:
    """Exact finite PG guards on real pytest line reports; synthetic values only."""
    import ast
    import os
    import subprocess
    import sys

    source = Path(__file__).with_name("test_model_admission_pg.py")
    tree = ast.parse(source.read_text())
    checker = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "private_channels"
    )
    comparison = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.Assert, ast.If))
        and isinstance(n.test, ast.Compare)
        and ast.unparse(n.test.left) == "census()"
        and [ast.unparse(v) for v in n.test.comparators] == ["prior"]
    )
    probe = tmp_path / "test_private_channel.py"
    probe.write_text(
        "import json\nfrom types import SimpleNamespace\n"
        "logs = SimpleNamespace(text='')\n"
        "capsys = SimpleNamespace(readouterr=lambda: SimpleNamespace(out='', err=''))\n"
        "public_errors = []\n"
        "runtime = SimpleNamespace(capability='b' * 64)\n"
        "control = SimpleNamespace(capability='c' * 64)\n"
        "dsn = 'postgresql+psycopg://owned:SYNTHETIC_DSN_PASSWORD@private/owned'\n"
        "url = SimpleNamespace(password='SYNTHETIC_DSN_PASSWORD')\n"
        "private_values = ('SYNTHETIC_PRIVATE_I1', 'SYNTHETIC_PRIVATE_ACK_ERROR', "
        "runtime.capability, control.capability, dsn, url.password)\n"
        "prior = {'managed_record': [{'private': private_values[0], 'revision': 1}]}\n"
        "def census():\n"
        "    return {'managed_record': [{'private': private_values[0], 'revision': 2}]}\n"
        + ast.unparse(checker)
        + "\ndef test_empty():\n    private_channels({})\n    prior = census()\n"
        + "\n".join("    " + line for line in ast.unparse(comparison).splitlines())
        + "\n"
        + "def test_census():\n"
        + "\n".join("    " + line for line in ast.unparse(comparison).splitlines())
        + "\n"
        + "\n".join(
            f"def test_private_{i}():\n    logs.text = private_values[{i}]\n    private_channels({{}})\n"
            for i in range(6)
        )
    )
    probe.chmod(0o600)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            str(Path(__file__).parents[1] / "pyproject.toml"),
            str(probe),
            "-q",
            "--tb=line",
        ],
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=15,
        check=False,
    )
    if any(
        marker in result.stdout
        for marker in (
            b"SYNTHETIC_PRIVATE_I1",
            b"SYNTHETIC_PRIVATE_ACK_ERROR",
            b"b" * 64,
            b"c" * 64,
            b"SYNTHETIC_DSN_PASSWORD",
        )
    ):
        raise AssertionError("private admission report escaped")
    report_lines = [line for line in result.stdout.splitlines() if not line.startswith(b"FAILED")]
    if (
        result.returncode != 1
        or b"7 failed, 1 passed" not in result.stdout
        or sum(
            line.endswith(b": AssertionError: private admission sentinel escaped")
            for line in report_lines
        )
        != 6
        or sum(
            line.endswith(b": AssertionError: private admission census changed")
            for line in report_lines
        )
        != 1
    ):
        raise AssertionError("private admission report control mismatch")


def assert_protocol_failure_records(
    graph: list[dict[str, object]],
    baseline_ids: set[str],
    command: dict[str, object],
    accounting: dict[str, object],
) -> None:
    """Same SOURCE/PG oracle: uncertain send is neither usage nor refund."""
    from collections import Counter

    added = [r for r in graph if str(r["id"]) not in baseline_ids]
    assert Counter(str(r["kind"]) for r in added) == {
        "model-budget": 1,
        "model-dispatch-owner": 1,
        "model-reservation": 1,
        "model-dispatch": 1,
        "contract-input-command": 1,
        "model-dispatch-transition": 1,
    }
    assert accounting["state"] == "SENT" and accounting["usage_state"] == "UNKNOWN"
    assert accounting["protocol_calls"] == 1 and accounting["model_calls"] == 0
    assert accounting["requested_caps"] == accounting["admitted_caps"] == command["protocol_caps"]
    assert all(
        accounting[k] is None
        for k in ("output_tokens", "cost_observed", "cost_estimate", "provider_receipt_ref")
    )
    by_kind = {str(r["kind"]): r for r in added}
    descriptor = by_kind["model-dispatch-owner"]
    dispatch = by_kind["model-dispatch"]
    assert accounting["descriptor_ref"] == records.reference(descriptor)
    assert accounting["dispatch_ref"] == records.reference(dispatch)
    assert mapping(dispatch["payload"])["dispatch_owner_ref"] == records.reference(descriptor)
    assert mapping(dispatch["payload"])["reservation_ref"] == records.reference(
        by_kind["model-reservation"]
    )
    transition = mapping(by_kind["model-dispatch-transition"]["payload"])
    assert (transition["state"], transition["sequence"]) == ("SENT", 1)
    assert transition["dispatch_ref"] == accounting["dispatch_ref"]
    receipt = mapping(by_kind["contract-input-command"]["payload"])
    assert receipt["command_id"] == command["protocol_id"]
    assert receipt["operation"] == command["action"]
    assert (
        receipt["request_digest"]
        == sha256(
            canonical(NativeTaskCommand.model_validate(command).model_dump(mode="json"))
        ).hexdigest()
    )
    assert receipt["result_refs"] == {
        "descriptor_ref": accounting["descriptor_ref"],
        "dispatch_ref": accounting["dispatch_ref"],
    }


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


def assert_protocol_budget_accounting(
    accounting: dict[str, object],
    command: dict[str, object],
    purpose: str,
) -> None:
    assert accounting["state"] == "SETTLED" and accounting["usage_state"] == "KNOWN"
    assert accounting["purpose"] == purpose
    assert accounting["protocol_calls"] == 1
    assert accounting["model_calls"] == accounting["output_tokens"] == 0
    assert accounting["requested_caps"] == accounting["admitted_caps"] == command["protocol_caps"]
    assert all(
        accounting[key] is None
        for key in ("cost_observed", "cost_estimate", "provider_receipt_ref")
    )


def assert_protocol_budget_records(
    graph: list[dict[str, object]],
    baseline_ids: set[str],
    accepted: list[tuple[dict[str, object], dict[str, object]]],
) -> None:
    """Full immutable ledger/receipt identities; NO_MODEL never invents token usage."""
    from collections import Counter

    from omnis.modules.runs import model_protocol

    assert len(accepted) == 2
    added = [r for r in graph if str(r["id"]) not in baseline_ids]
    assert Counter(str(r["kind"]) for r in added) == {
        "model-budget": 1,
        "model-dispatch-owner": 2,
        "model-reservation": 2,
        "model-dispatch": 2,
        "contract-input-command": 2,
        "model-dispatch-transition": 2,
        "model-usage-receipt": 2,
        "model-protocol-receipt": 2,
    }
    budget = next(r for r in added if r["kind"] == "model-budget")
    assert (
        mapping(budget["payload"])["limits"]
        == model_protocol.LIMITS
        == {
            "calls": 2,
            "output_tokens": 128,
            "validation_calls": 1,
            "validation_output_tokens": 64,
            "cost_limit": None,
        }
    )
    for command, accounting in accepted:
        dispatch = next(r for r in added if records.reference(r) == accounting["dispatch_ref"])
        allocation = next(
            r
            for r in added
            if records.reference(r) == mapping(dispatch["payload"])["reservation_ref"]
        )
        assert mapping(allocation["payload"])["budget_ref"] == records.reference(budget)
        req = mapping(mapping(allocation["payload"])["request"])
        assert (
            req["purpose"]
            == model_protocol.PURPOSE[str(command["action"])]
            == accounting["purpose"]
        )
        assert req["technical_caps"] == command["protocol_caps"]
        assert req["native_turn_ref"] is None
        # Reuse the existing exact eight-kind/receipt oracle for this allocation,
        # sharing the original budget, and treating only the other allocation as baseline.
        relevant = {
            str(budget["id"]),
            str(dispatch["id"]),
            str(allocation["id"]),
            str(mapping(accounting["descriptor_ref"])["id"]),
        }
        relevant.update(
            str(r["id"])
            for r in added
            if mapping(r["payload"]).get("dispatch_ref") == accounting["dispatch_ref"]
        )
        relevant.update(
            str(r["id"])
            for r in added
            if r["kind"] == "contract-input-command"
            and mapping(r["payload"])["command_id"] == command["protocol_id"]
        )
        assert_protocol_records(
            graph, {str(r["id"]) for r in graph} - relevant, command, accounting
        )
        reserved = budgets.reduce_history(dispatch, allocation, [])
        assert (reserved["charged_calls"], reserved["charged_output_tokens"]) == (1, 64)
    # Two calls, each at most 64: the public 128-token ceiling cannot be
    # independently exhausted before the call ceiling. Actual settled usage=0.
    calls = model_protocol.LIMITS["calls"]
    assert calls is not None
    assert calls * 64 == model_protocol.LIMITS["output_tokens"]
    assert not any(r["kind"] == "native-turn" for r in graph)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["budget", "budget_conflict", "deadline_b"])
async def test_protocol_caps_validation_immutable_budget_and_deadline_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path,
        monkeypatch,
        protocol_mode=True,
        protocol_case=case,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,invalid", [("output_tokens", 65), ("calls", 2), ("wall_seconds", 4)]
)
async def test_protocol_caps_dto_refuses_before_control_io(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    invalid: int,
) -> None:
    from omnis.supervisor.native_tasks import control_task

    value = {
        **preflight_command(),
        "action": "model_protocol_prepare",
        "protocol_id": str(uuid4()),
        "provider_config_ref": records.reference(records.envelope("provider-config", {})),
        "protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 3},
    }
    assert NativeTaskCommand.model_validate(value).protocol_caps == value["protocol_caps"]
    io = Mock(side_effect=AssertionError("invalid DTO reached control metadata"))
    monkeypatch.setattr("omnis.modules.runs.native_preparation.existing_private_root", io)
    value["protocol_caps"] = {**mapping(value["protocol_caps"]), field: invalid}
    with pytest.raises(ValidationError):
        await control_task(Path("/unused"), value)
    io.assert_not_called()


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
    import inspect

    from omnis.supervisor.native_tasks import NativeTaskOwner
    from omnis.supervisor.runtime_client import FrozenPreflight, RuntimeClient, RuntimeUnavailable

    delayed = produced = 0
    original_read = ModelDispatch.read_configuration
    original_exchange = RuntimeClient.exchange_frozen

    async def read(
        self: ModelDispatch,
        conn: AsyncConnection,
        owner: str,
        manifest_ref: object,
        provider_config_ref: object,
        authority: dict[str, object],
    ) -> dict[str, object]:
        nonlocal delayed
        frame = inspect.currentframe()
        if (
            failure == "timeout"
            and frame is not None
            and frame.f_back is not None
            and frame.f_back.f_code is NativeTaskOwner._model_protocol.__code__
        ):
            delayed += 1
            await asyncio.sleep(1.25)  # Below DB2; the original outer deadline stays 4s.
        return await original_read(self, conn, owner, manifest_ref, provider_config_ref, authority)

    async def exchange(self: RuntimeClient, frozen: FrozenPreflight) -> dict[str, object]:
        nonlocal produced
        if failure == "timeout":
            assert frozen.wall_seconds == 1
        try:
            return await original_exchange(self, frozen)
        except RuntimeUnavailable as error:
            if failure == "timeout":
                assert type(error.__context__) is TimeoutError
                produced += 1
            raise

    if failure == "timeout":
        monkeypatch.setattr(ModelDispatch, "read_configuration", read)
        monkeypatch.setattr(RuntimeClient, "exchange_frozen", exchange)
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path,
        monkeypatch,
        protocol_mode=True,
        protocol_failure=failure,
    )
    if failure == "timeout":
        assert delayed == produced == 1


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    ["slow_marker", "deadline_before", "deadline_after", "failed", "cancelled", "returned"],
)
async def test_protocol_marker_observes_bounded_control_completion(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Real control_task/UDS/4s timeout; only readiness and task work are SOURCE seams."""
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import control_task
    from omnis.transport.local_control import LocalControl
    from test_native_task_control import task_command

    marker, entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(
        "omnis.transport.local_control.readiness_reason", AsyncMock(return_value=None)
    )

    async def handle(value: NativeTaskCommand) -> dict[str, object]:
        entered.set()
        if case == "failed":
            raise CatalogError("COMMAND_CONFLICT")
        if case in {"slow_marker", "deadline_after"}:
            await asyncio.sleep(2.1)  # Past all old 1/1.5/2s observer caps, inside control's 4s.
            marker.set()
        if case != "returned":
            await release.wait()
        return {
            "ok": True,
            "manifest_ref": value.manifest_ref,
            "binding_ref": records.reference(records.envelope("runtime-binding", {})),
            "task_status": "BOUND",
        }

    service = InstanceService(Mock(spec=AsyncEngine))
    async with LocalControl(ipc_directory, service, uuid4(), 1, native_task=handle) as local:
        started = asyncio.get_running_loop().time()
        sender = asyncio.create_task(control_task(ipc_directory, task_command()))
        try:
            # Rescue fuse only: never grants a new budget to the marker or join.
            async with asyncio.timeout_at(started + 4.25):
                await entered.wait()
                if case == "cancelled":
                    sender.cancel()
                tasks_before = asyncio.all_tasks()
                if case == "slow_marker":
                    await wait_protocol_marker(marker, sender)
                    assert not sender.done() and marker.is_set()
                    release.set()
                    assert (await sender)["task_status"] == "BOUND"
                    assert 2.1 <= asyncio.get_running_loop().time() - started < 4
                elif case.startswith("deadline"):
                    with pytest.raises(TimeoutError):
                        await wait_protocol_marker(marker, sender)
                        await sender
                    assert sender.done() and not sender.cancelled()
                    assert type(sender.exception()) is TimeoutError
                    assert 4 <= asyncio.get_running_loop().time() - started < 4.25
                    assert marker.is_set() is (case == "deadline_after")
                elif case == "failed":
                    with pytest.raises(CatalogError) as denied:
                        await wait_protocol_marker(marker, sender)
                    assert denied.value is sender.exception()
                    assert denied.value.reason == "COMMAND_CONFLICT"
                elif case == "cancelled":
                    with pytest.raises(asyncio.CancelledError):
                        await wait_protocol_marker(marker, sender)
                    assert sender.cancelled()
                else:
                    with pytest.raises(AssertionError, match="completed before protocol marker"):
                        await wait_protocol_marker(marker, sender)
                    assert sender.done() and sender.exception() is None
                assert not (asyncio.all_tasks() - tasks_before)  # No orphan marker waiter.
        finally:
            release.set()
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
    assert not local.clients
    assert not (ipc_directory / "control.sock").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["simultaneous_failure", "observer_cancel"])
async def test_protocol_marker_preserves_failure_and_owns_only_its_waiter(case: str) -> None:
    from omnis.modules.settings.catalog_models import CatalogError

    before = asyncio.all_tasks()
    marker, entered = asyncio.Event(), asyncio.Event()
    primary = CatalogError("COMMAND_CONFLICT")

    async def send() -> dict[str, object]:
        async with asyncio.timeout(4):
            entered.set()
            if case == "simultaneous_failure":
                marker.set()
                raise primary
            await asyncio.Event().wait()
        raise AssertionError("unreachable")

    sender = asyncio.create_task(send())
    observer: asyncio.Task[None] | None = None
    try:
        await entered.wait()
        if case == "simultaneous_failure":
            assert sender.done() and marker.is_set()
            with pytest.raises(CatalogError) as caught:
                await wait_protocol_marker(marker, sender)
            assert caught.value is primary
        else:
            observer = asyncio.create_task(wait_protocol_marker(marker, sender))
            await asyncio.sleep(0)  # Enter the helper before cancelling its observation.
            observer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observer
            assert not sender.done()  # Caller, not the observer, owns command cancellation.
    finally:
        tasks = [sender] if observer is None else [sender, observer]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert asyncio.all_tasks() == before


@pytest.mark.asyncio
async def test_protocol_budget_observer_tracks_fourth_command_failure() -> None:
    """SOURCE control of the exact PG wrappers; no SQL/native effects or timeout inflation."""
    import ast
    import inspect

    from test_model_admission_pg import ProtocolTiming, protocol_pg_consumer

    tree = ast.parse(inspect.getsource(protocol_pg_consumer))
    wrappers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name in {"observed_handle", "measured_control"}
    ]
    assert len(wrappers) == 2
    source = (
        "def bind(protocol_handle, control_task, timing, root):\n"
        "    concurrent, admission_case = False, True\n"
        "    request_count, second_handler = 0, None\n"
        + "\n".join("    " + line for node in wrappers for line in ast.unparse(node).splitlines())
        + "\n    return observed_handle, measured_control\n"
    )
    namespace: dict[str, object] = {"asyncio": asyncio}
    exec("from __future__ import annotations\n" + source, namespace)
    bind = namespace["bind"]
    assert callable(bind)
    timing = ProtocolTiming()
    command = NativeTaskCommand.model_validate(preflight_command())
    token: dict[str, object] = {"synthetic": True}
    primary = TimeoutError("SYNTHETIC_DIAGNOSTIC_OMIT_ME")
    called = 0
    task = asyncio.current_task()

    async def handle(value: NativeTaskCommand) -> dict[str, object]:
        nonlocal called
        assert value is command and asyncio.current_task() is task
        called += 1
        if called == 4:
            raise primary
        return token

    async def control(root: object, value: object) -> dict[str, object]:
        assert root is token and value is command
        pending = observed(command)
        assert inspect.isawaitable(pending)
        assert id(await pending) == id(token)
        return token

    observers = bind(handle, control, timing, token)
    assert isinstance(observers, tuple) and len(observers) == 2
    observed, measured = observers
    assert callable(observed) and callable(measured)
    for _ in range(3):
        pending = measured(command, "sender")
        assert inspect.isawaitable(pending)
        assert await pending is token
    with pytest.raises(TimeoutError) as caught:
        pending = measured(command, "sender")
        assert inspect.isawaitable(pending)
        await pending
    assert caught.value is primary and called == 4 and not timing.handlers
    rows = timing.snapshot()
    assert [row["outcome"] for row in rows if row["phase"] == "owner"] == [
        "RETURNED",
        "RETURNED",
        "RETURNED",
        "RAISED",
    ], "budget observer lost the actual fourth owner failure"
    assert [row["outcome"] for row in rows if row["phase"] == "control"] == [
        "RETURNED",
        "RETURNED",
        "RETURNED",
        "RAISED",
    ]
    assert "SYNTHETIC_DIAGNOSTIC_OMIT_ME" not in str(rows)


@pytest.mark.asyncio
async def test_protocol_phase_timing_delegates_without_task_or_error_changes() -> None:
    """SOURCE observer control: real elapsed time, pending/return/raise, finite storage."""
    from time import monotonic

    from test_model_admission_pg import ProtocolTiming

    timing = ProtocolTiming()
    task = asyncio.current_task()
    timing.handlers[task] = "sender"
    token = object()
    error = ValueError("SYNTHETIC_DIAGNOSTIC_OMIT_ME")
    called = 0

    async def actual(value: object, *, fail: bool = False) -> object:
        nonlocal called
        called += 1
        assert asyncio.current_task() is task and value is token
        if task in timing.handlers:
            pending = timing.snapshot()
            assert pending[-1]["outcome"] == "PENDING"
        await asyncio.sleep(0.01)
        if fail:
            raise error
        return value

    measured = timing.delegate("protocol.readback", actual)
    start = monotonic()
    assert await measured(token) is token
    with pytest.raises(ValueError) as caught:
        await measured(token, fail=True)
    assert caught.value is error and called == 2
    rows = timing.snapshot()
    assert [row["outcome"] for row in rows] == ["RETURNED", "RAISED"]
    assert all(0 < row["elapsed_ms"] <= 1000 * (monotonic() - start) for row in rows)
    assert "SYNTHETIC_DIAGNOSTIC_OMIT_ME" not in str(rows)
    # Untracked readers cannot inflate the first-two-command observation.
    timing.handlers.clear()
    assert await measured(token) is token
    assert len(timing.snapshot()) == 2
    for _ in range(62):
        with timing.phase("sender", "qa.before_a"):
            pass
    with pytest.raises(AssertionError, match="protocol timing capacity"):
        with timing.phase("sender", "qa.before_a"):
            pass
    assert len(timing.snapshot()) == 64


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["nominal", "duplicate", "conflict"])
async def test_protocol_phase_timing_existing_source_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    """Actual SOURCE callers/qualification; not PG graph/lock or QA-pause timing."""
    import json

    from omnis.modules.runs import model_protocol
    from omnis.supervisor import native_tasks
    from test_model_admission_pg import ProtocolCaller, ProtocolTiming

    timing = ProtocolTiming()
    original_handle = native_tasks.NativeTaskOwner.handle
    original_control = native_tasks.control_task
    owner_count = control_count = 0
    limit = 1 if case == "nominal" else 2

    async def handle(
        self: native_tasks.NativeTaskOwner, value: NativeTaskCommand
    ) -> dict[str, object]:
        nonlocal owner_count
        if value.action != "model_protocol_prepare" or owner_count >= limit:
            return await original_handle(self, value)
        owner_count += 1
        caller: ProtocolCaller = "sender" if owner_count == 1 else "second"
        task = asyncio.current_task()
        timing.handlers[task] = caller
        try:
            with timing.phase(caller, "owner"):
                return await original_handle(self, value)
        finally:
            timing.handlers.pop(task)

    async def control(root: Path, value: object) -> dict[str, object]:
        nonlocal control_count
        if mapping(value)["action"] != "model_protocol_prepare" or control_count >= limit:
            return await original_control(root, value)
        control_count += 1
        with timing.phase("sender" if control_count == 1 else "second", "control"):
            return await original_control(root, value)

    monkeypatch.setattr(native_tasks.NativeTaskOwner, "handle", handle)
    monkeypatch.setattr(native_tasks, "control_task", control)
    monkeypatch.setattr(
        model_protocol, "qualified", timing.delegate("protocol.qualified", model_protocol.qualified)
    )
    monkeypatch.setattr(ModelDispatch, "read", timing.delegate("dispatch.read", ModelDispatch.read))
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_case=None if case == "nominal" else case
    )
    rows = timing.snapshot()
    reads = [r for r in rows if r["phase"] == "dispatch.read"]
    assert len([r for r in reads if r["caller"] == "sender"]) == 3
    assert len([r for r in reads if r["caller"] == "second"]) == int(case == "duplicate")
    qualified = [r for r in rows if r["phase"] == "protocol.qualified"]
    assert len(qualified) == (3 if case == "duplicate" else 2)
    assert all(r["outcome"] == "RETURNED" and r["elapsed_ms"] > 0 for r in qualified)
    assert owner_count == control_count == limit and not timing.handlers
    assert [r["caller"] for r in qualified].count("second") == int(case == "duplicate")
    with capsys.disabled():
        print(
            "\nP2_PROTOCOL_TIMING "
            + json.dumps(
                {
                    "scope": "SOURCE_CONTROL",
                    "order": case,
                    "timing": rows,
                },
                sort_keys=True,
            ),
            flush=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["settle", "persist_configuration", "readback"])
@pytest.mark.parametrize("fault", ["context", "schema", "receipt", "eligibility"])
async def test_protocol_t2_strict_wrappers_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, fault: str
) -> None:
    """Real SOURCE owner/UDS; challenge each public wrapper in the same T2 call."""
    from dataclasses import replace

    from omnis.modules.runs import model_protocol
    from omnis.modules.settings.catalog_models import CatalogError

    original_settle = model_protocol.settle
    challenged = 0

    async def settle(
        conn: AsyncConnection,
        consumer: ModelDispatch,
        command: NativeTaskCommand,
        references: dict[str, object],
        result: object,
    ) -> object:
        nonlocal challenged
        body, _ = await model_protocol.qualified(
            conn, consumer, command, references, read_only=True
        )
        prepared = mapping(body["prepared"])
        before = canonical(await managed_store.graph(conn, command.owner_id, str(body["run_id"])))
        original_context = consumer._context
        original_get = managed_store.get

        async def context(
            connection: AsyncConnection,
            owner: str,
            run: str,
            binding: dict[str, object],
            manifest: dict[str, object],
            projection: dict[str, object],
            *,
            read_only: bool,
        ) -> dict[str, object]:
            original_source = consumer.projections.managed._source

            async def source(
                connection: AsyncConnection,
                owner: str,
                request: dict[str, object],
                *,
                preparation_ref: dict[str, object],
                read_only: bool = False,
            ) -> BuildSource:
                return replace(
                    await original_source(
                        connection,
                        owner,
                        request,
                        preparation_ref=preparation_ref,
                        read_only=read_only,
                    ),
                    role="VALIDATOR",
                )

            with monkeypatch.context() as local:
                local.setattr(consumer.projections.managed, "_source", source)
                return await original_context(
                    connection, owner, run, binding, manifest, projection, read_only=read_only
                )

        async def get(
            connection: AsyncConnection, owner: str, run: str, pin: object
        ) -> dict[str, object]:
            item = await original_get(connection, owner, run, pin)
            if item["kind"] == "model-data-approval" and fault in {"schema", "receipt"}:
                return records.envelope(
                    "model-data-approval",
                    {
                        **mapping(item["payload"]),
                        **({"version": True} if fault == "schema" else {"policy_digest": "0" * 64}),
                    },
                )
            return item

        with monkeypatch.context() as mutation:
            if fault == "context":
                mutation.setattr(consumer, "_context", context)
            elif fault == "eligibility":
                # Challenge the actual manifest lookup with a resealed unsupported
                # version; refusal may precede or occur at the stage eligibility guard.
                async def unsupported(
                    connection: AsyncConnection, owner: str, run: str, pin: object
                ) -> dict[str, object]:
                    item = await original_get(connection, owner, run, pin)
                    if item["kind"] == "launch-manifest":
                        return records.envelope(
                            "launch-manifest",
                            {**mapping(item["payload"]), "composition_version": 4},
                        )
                    return item

                mutation.setattr(managed_store, "get", unsupported)
            else:
                mutation.setattr(managed_store, "get", get)
            with pytest.raises(CatalogError):
                if boundary == "settle":
                    await original_settle(conn, consumer, command, references, result)
                elif boundary == "persist_configuration":
                    await consumer.persist_configuration(conn, command.owner_id, prepared, result)
                else:
                    await model_protocol.readback(conn, consumer, command, references)
        assert (
            canonical(await managed_store.graph(conn, command.owner_id, str(body["run_id"])))
            == before
        )
        challenged += 1
        return await original_settle(conn, consumer, command, references, result)

    monkeypatch.setattr(model_protocol, "settle", settle)
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True
    )
    assert challenged == 1


@pytest.mark.asyncio
async def test_protocol_t2_commit_failure_never_returns_success_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real owner/control UDS; SOURCE transaction-exit failure, not PG rollback proof."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from sqlalchemy.exc import SQLAlchemyError

    from omnis.modules.runs import model_protocol
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import NativeTaskOwner

    original_handle, original_settle = NativeTaskOwner.handle, model_protocol.settle
    settled = failed_commit = returned = False

    async def settle(
        conn: AsyncConnection,
        consumer: ModelDispatch,
        command: NativeTaskCommand,
        references: dict[str, object],
        result: object,
    ) -> object:
        nonlocal settled
        answer = await original_settle(conn, consumer, command, references, result)
        settled = True
        return answer

    async def handle(self: NativeTaskOwner, command: NativeTaskCommand) -> dict[str, object]:
        nonlocal returned
        if command.action != "model_protocol_prepare":
            return await original_handle(self, command)
        original_begin = self.domain.engine.begin

        @asynccontextmanager
        async def begin() -> AsyncIterator[AsyncConnection]:
            nonlocal failed_commit
            async with original_begin() as conn:
                yield conn
                if settled:
                    failed_commit = True
                    raise SQLAlchemyError("SYNTHETIC_COMMIT_FAILURE")

        with monkeypatch.context() as local:
            local.setattr(self.domain.engine, "begin", begin)
            answer = await original_handle(self, command)
        returned = True
        return answer

    monkeypatch.setattr(model_protocol, "settle", settle)
    monkeypatch.setattr(NativeTaskOwner, "handle", handle)
    with pytest.raises(CatalogError, match="CONTROL_UNAVAILABLE"):
        await test_qualified_projection_reaches_cold_admission_without_model_reservation(
            tmp_path, monkeypatch, protocol_mode=True
        )
    assert settled and failed_commit and not returned


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["duplicate", "conflict"])
async def test_protocol_join_uses_existing_control_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """The real public SOURCE consumer's first join must allow its bounded reply."""
    from omnis.supervisor.native_tasks import NativeTaskOwner

    original = NativeTaskOwner.handle
    calls = 0
    delayed = False

    async def slow_reply(self: NativeTaskOwner, value: NativeTaskCommand) -> dict[str, object]:
        nonlocal calls, delayed
        selected = value.action == "model_protocol_prepare"
        if selected:
            calls += 1
        first = selected and calls == 1
        reply = await original(self, value)
        if first:
            # Still inside the real LocalControl/control_task deadlines. Never
            # delay the second reply needed to release the original T0 pause.
            await asyncio.sleep(2.1)
            delayed = True
        return reply

    monkeypatch.setattr(NativeTaskOwner, "handle", slow_reply)
    await test_qualified_projection_reaches_cold_admission_without_model_reservation(
        tmp_path, monkeypatch, protocol_mode=True, protocol_case=case
    )
    assert delayed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,expected",
    [
        ("failed", {"state": "FAILED", "type": "CatalogError", "reason": "CONTROL_UNAVAILABLE"}),
        ("pending", {"state": "PENDING"}),
        ("pg_waiter", {"state": "PENDING"}),
        ("cancelled", {"state": "CANCELLED"}),
        ("primary_cancelled", {"state": "PENDING"}),
        ("join_timeout", {"state": "CANCELLED"}),
        ("returned", {"state": "RETURNED"}),
        ("unknown_reason", {"state": "FAILED", "type": "CatalogError", "reason": "OTHER"}),
        ("unknown_type", {"state": "FAILED", "type": "OTHER", "reason": None}),
    ],
)
async def test_protocol_failure_observation_before_cleanup_on_line_channel(
    capsys: pytest.CaptureFixture[str], case: str, expected: dict[str, object]
) -> None:
    """SOURCE: a real marker timeout must not erase an earlier sender failure."""
    import asyncio
    import json
    from time import monotonic

    from omnis.modules.settings.catalog_models import CatalogError

    pg = importlib.import_module("test_model_admission_pg")
    timing = pg.ProtocolTiming()
    marker, started = asyncio.Event(), asyncio.Event()
    if case == "pg_waiter":
        marker.set()  # SOURCE: ready already reached; the lock observation stalls.
    completed = int(marker.is_set())
    readiness_start = monotonic()
    synthetic = "SYNTHETIC_DIAGNOSTIC_OMIT_ME"

    class UnlistedError(Exception):
        def __str__(self) -> str:
            raise AssertionError("diagnostic must not format an exception")

    async def send() -> None:
        started.set()
        if case == "failed":
            error = CatalogError("CONTROL_UNAVAILABLE")
            error.args = (synthetic,)
            raise error
        if case == "unknown_reason":
            raise CatalogError(synthetic)
        if case == "unknown_type":
            raise UnlistedError(synthetic)
        if case != "returned":
            await asyncio.Event().wait()

    sender = asyncio.create_task(timing.delegate("domain.readback", send)())
    timing.handlers[sender] = "sender"
    snapshot: dict[str, object] | None = None
    primary: BaseException | None = None
    try:
        await started.wait()
        if case == "cancelled":
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
        primary_type = asyncio.CancelledError if case == "primary_cancelled" else TimeoutError
        with pytest.raises(primary_type) as caught:
            try:
                if case == "primary_cancelled":
                    raise asyncio.CancelledError(synthetic)
                elif case == "join_timeout":
                    await asyncio.wait_for(sender, 0)
                else:
                    async with asyncio.timeout(0):
                        await (asyncio.Event() if case == "pg_waiter" else marker).wait()
            except BaseException as error:
                primary = error
                # Without the observation the old marker/finally path loses
                # precisely this state. Keep the RED about missing evidence.
                observe = getattr(pg, "report_protocol_failure", None)
                if observe is not None:
                    snapshot = observe(
                        capsys,
                        error,
                        order="duplicate",
                        await_site={
                            "join_timeout": "join_sender",
                            "pg_waiter": "duplicate_pg_waiter",
                        }.get(case, "t0_ready"),
                        markers={"t0_ready": marker},
                        tasks={"sender": sender},
                        progress={
                            "owner_entered": completed,
                            "fence_entered": completed,
                            "readiness_entered": 1,
                            "readiness_completed": completed,
                            "readiness_started": readiness_start,
                            "readiness_finished": readiness_start if completed else None,
                        },
                        timing=timing,
                        source_control=True,
                    )
                raise
        assert caught.value is primary
    finally:
        if not sender.done():
            sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
    assert snapshot is not None, "first-error observation missing before cleanup"
    assert snapshot["tasks"] == {"sender": expected}
    rows = sequence(snapshot["timing"])
    assert len(rows) == 1
    span = mapping(rows[0])
    assert span["phase"] == "domain.readback" and span["caller"] == "sender"
    assert (
        span["outcome"]
        == {
            "PENDING": "PENDING",
            "RETURNED": "RETURNED",
            "FAILED": "RAISED",
            "CANCELLED": "RAISED",
        }[str(expected["state"])]
    )
    assert snapshot["error"] == {"type": primary_type.__name__, "reason": None}
    assert snapshot["scope"] == "SOURCE_CONTROL"
    assert snapshot["markers"] == {"t0_ready": bool(completed)}
    assert snapshot["owner_entered"] == snapshot["fence_entered"] == completed
    assert snapshot["readiness_entered"] == 1 and snapshot["readiness_completed"] == completed
    elapsed = snapshot["readiness_elapsed_ms"]
    assert type(elapsed) is int and elapsed >= 0
    assert synthetic not in json.dumps(snapshot)
    # This is printed outside capture, on the SAME --tb=line terminal channel
    # used by PG. The command's actual stdout is checked alongside these controls.
    assert "P2_PROTOCOL_FAILURE" not in capsys.readouterr().out
