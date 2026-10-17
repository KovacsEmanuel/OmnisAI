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


@pytest.mark.parametrize("fault", [None, "caught-forbidden", "unknown-row", "unjoined-close"])
def test_model_prepare_real_early_return_finally(tmp_path: Path, fault: str | None) -> None:
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
    path = tmp_path / "observation.jsonl"
    path.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))
    checkpoint = Mock()
    scope: dict[str, object] = {
        "sys": sys,
        "model_prepare": True,
        "observation": path,
        "require_native_observation": owner.require_native_observation,
        "checkpoint": checkpoint,
    }
    exec(compile(ast.fix_missing_locations(probe), owner.__file__, "exec"), scope)
    invoke = scope["probe"]
    assert callable(invoke)
    if fault is None:
        assert invoke() == "EARLY"
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
        "over-managed": time.monotonic_ns() + 4_800_000_000,
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
        assert host.deadline_ns == 14_000_000_000
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
