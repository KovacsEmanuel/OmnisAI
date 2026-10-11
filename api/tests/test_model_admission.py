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
        return next(item for item in graph if records.reference(item) == pin)

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
    cold.__dict__["ColdAdmissionDenied"] = ValueError
    monkeypatch.setitem(sys.modules, "agent.cold_admission", cold)

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
    assert events == ["begin", "commit", "native-data-preflight"]
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
