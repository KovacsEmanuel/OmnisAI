"""Owned initialization orchestration SOURCE; storage/native reply are explicit doubles.

This is NOT real PostgreSQL, native constructor/turn, model/client or provider proof.
The DATA source and decision receipt are produced by actual owner/store code.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import mapping, record
from omnis.policy import budgets
from omnis.supervisor.native_tasks import NativeTaskOwner
from omnis.supervisor.runtime_client import RuntimeClient
from test_managed_contract import manifest as manifest_fixture
from test_ready_model_configuration import configuration


class SourceOwner:
    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.owner, self.lease, self.instance = str(uuid4()), uuid4(), str(uuid4())
        self.command_id = str(uuid4())
        self.manifest = manifest_fixture()
        self.run = str(mapping(self.manifest["payload"])["run_id"])
        self.graph: list[dict[str, object]] = [self.manifest]
        self.events: list[str] = []
        self.payloads: list[dict[str, object]] = []
        self.state: dict[str, object] = {
            "run_id": self.run,
            "binding_id": None,
            "stage_started": False,
            "release_started": False,
            "final_id": None,
        }
        domain = ManagedAdmission(Mock(spec=AsyncEngine))
        monkeypatch.setattr(
            domain,
            "readback",
            AsyncMock(
                return_value={
                    "manifest_ref": records.reference(self.manifest),
                    "manifest": self.manifest,
                    "binding": None,
                    "results": [],
                    "stage_started": False,
                    "release_started": False,
                }
            ),
        )
        conn = Mock(spec=AsyncConnection)
        row = Mock()
        row.scalar_one.return_value = self.instance
        conn.execute = AsyncMock(return_value=row)
        monkeypatch.setattr(budgets, "_transaction", AsyncMock())
        self.reserve = AsyncMock(side_effect=AssertionError("core phase reserved inference"))
        monkeypatch.setattr(budgets, "reserve", self.reserve)
        monkeypatch.setattr(store, "state", AsyncMock(side_effect=lambda *_a, **_k: self.state))
        monkeypatch.setattr(store, "graph", AsyncMock(side_effect=lambda *_a: list(self.graph)))

        async def get(c: object, owner: str, run: str, pin: object) -> dict[str, object]:
            if owner != self.owner or (
                run != self.run
                and not any(r["kind"] == "managed-run" and r["id"] == run for r in self.graph)
            ):
                raise CatalogError("REF_UNAVAILABLE")
            matches = [r for r in self.graph if records.reference(r) == pin]
            if len(matches) != 1:
                raise CatalogError("REF_UNAVAILABLE")
            return record(deepcopy(matches[0]))

        async def put(c: object, owner: str, run: str, value: object) -> None:
            item = record(value)
            assert owner == self.owner
            assert (
                run == self.run
                or (item["kind"] == "managed-run" and item["id"] == run)
                or any(r["kind"] == "managed-run" and r["id"] == run for r in self.graph)
            )
            self.graph.append(item)

        async def receipt(c: object, owner: str, command: str) -> dict[str, object]:
            if owner != self.owner:
                raise CatalogError("REF_UNAVAILABLE")
            matches = [
                r
                for r in self.graph
                if r["kind"] == "contract-input-command"
                and mapping(r["payload"])["command_id"] == command
            ]
            if not matches:
                raise CatalogError("REF_UNAVAILABLE")
            if len(matches) != 1:
                raise CatalogError("STORAGE_INCOMPATIBLE")
            return record(deepcopy(matches[0]))

        async def owned(c: object, owner: str, pin: object) -> tuple[str, dict[str, object]]:
            return self.run, await get(c, owner, self.run, pin)

        monkeypatch.setattr(store, "get", get)
        monkeypatch.setattr(store, "put", put)
        monkeypatch.setattr(store, "command_receipt", receipt)
        monkeypatch.setattr(store, "owned", owned)
        # command_complete/command_replay themselves remain actual product code.
        service = Mock(spec=InstanceService)

        @asynccontextmanager
        async def fence(owner: UUID, epoch: int, generation: int) -> AsyncIterator[AsyncConnection]:
            assert owner == self.lease and epoch == 1 and generation == 0
            self.events.append("begin")
            yield conn
            self.events.append("commit")

        @asynccontextmanager
        async def read_transaction() -> AsyncIterator[AsyncConnection]:
            yield conn

        monkeypatch.setattr(domain.engine, "begin", read_transaction)
        service.native_preparation_commit = fence
        runtime = RuntimeClient(root, generation=0, epoch=1)
        runtime.boot = str(uuid4())  # SOURCE transport identity, never a native-positive claim.
        self.runtime = runtime
        self.native = AsyncMock(side_effect=self.native_double)
        monkeypatch.setattr(runtime, "managed", self.native)
        self.handler = NativeTaskOwner(domain, service, self.lease, 1, runtime)
        self.base: dict[str, object] = {
            "op": "native_task",
            "schema_version": 1,
            "owner_id": self.owner,
            "command_id": self.command_id,
            "instance_id": self.instance,
            "expected_epoch": 1,
            "expected_generation": 0,
            "manifest_ref": records.reference(self.manifest),
        }

    async def native_double(
        self, service: InstanceService, owner: UUID, operation: str, payload: dict[str, object]
    ) -> dict[str, object]:
        assert operation == "task_model_initialize" and owner == self.lease
        assert self.events[-1] == "commit", "initialization IPC preceded intent commit"
        intent = mapping(payload["intent_ref"])
        assert any(records.reference(r) == intent for r in self.graph)
        source = record(payload["provider_config"], "provider-config")
        receipt = record(payload["producer_receipt"], "contract-input-command")
        assert source in self.graph and receipt in self.graph
        assert mapping(receipt["payload"])["operation"] == "model_configuration"
        self.payloads.append(deepcopy(payload))
        self.events.append("SOURCE_NATIVE_CORE_OBSERVATION_DOUBLE")
        observed = mapping(load_json(str(payload["initialization_data"])))
        return {
            **{
                k: payload[k]
                for k in (
                    "protocol",
                    "version",
                    "initialization_id",
                    "intent_ref",
                    "owner_id",
                    "run_id",
                    "manifest_ref",
                    "runtime_boot",
                    "authority",
                    "source_byte_digest",
                    "initialization_data_digest",
                )
            },
            "provider_config_ref": records.reference(source),
            "producer_receipt_ref": records.reference(receipt),
            "status": "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM",
            "native_session_id": "SOURCE-SESSION-DOUBLE",
            "native_instance_id": str(uuid4()),
            "observed_configuration": observed,
            "observed_configuration_digest": sha256(canonical(observed)).hexdigest(),
            "client_status": "DEFERRED_NO_CREDENTIAL",
            "native_turn": None,
            "inference_status": "HOLD",
            "model_calls": 0,
        }

    async def produce(self) -> dict[str, object]:
        command = NativeTaskCommand.model_validate(
            {**self.base, "action": "model_configuration", "configuration": configuration()}
        )
        answer = await self.handler.handle(command)
        assert answer["initialization_status"] == answer["inference_status"] == "HOLD"
        self.native.assert_not_awaited()
        return mapping(answer["provider_config_ref"])


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_reply", [False, True], ids=["prepared", "status-only-replay"])
async def test_model_test_prepare_owns_fresh_qualified_context_and_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lost_reply: bool
) -> None:
    from test_contract_method_producer import batch2_source

    graph, bundle, source, actual_owner = await batch2_source(tmp_path / "material", monkeypatch)
    owner = SourceOwner(tmp_path, monkeypatch)
    owner.owner = actual_owner
    owner.base["owner_id"] = actual_owner
    owner.graph[:] = graph
    old_run = next(r for r in graph if r["kind"] == "managed-run")
    owner.run = str(old_run["id"])
    owner.state["run_id"] = owner.run
    manifest = graph[-1]
    owner.base["manifest_ref"] = records.reference(manifest)
    monkeypatch.setattr(
        owner.handler.domain,
        "readback",
        AsyncMock(
            return_value={
                "manifest_ref": records.reference(manifest),
                "manifest": manifest,
                "binding": None,
                "results": [],
                "stage_started": False,
                "release_started": False,
            }
        ),
    )
    owner.handler.domain.root = tmp_path
    # Extend only the fixture's catalog storage seam; invoke the actual strict reader again.
    catalog_get = records.get

    async def catalog_read(
        connection: AsyncConnection, who: str, pin: dict[str, object]
    ) -> tuple[str, dict[str, object]]:
        if pin == source.preparation_ref:
            return "SOURCE-CATALOG-GROUP", records.envelope(
                "native-preparation-receipt",
                {
                    "bundle_ref": records.reference(bundle),
                },
            )
        return await catalog_get(connection, who, pin)

    monkeypatch.setattr(records, "get", catalog_read)
    saved_status = AsyncMock(
        return_value={
            "status": "CONFIRMED",
            "selection": {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"},
            "authenticated": "NOT_VERIFIED",
        }
    )
    monkeypatch.setattr(owner.runtime, "settings_status", saved_status)
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "action": "model_test_prepare",
            "initialization_id": str(uuid4()),
            "settings_operation_id": str(uuid4()),
        }
    )

    async def prepared_double(
        service: InstanceService, lease: UUID, operation: str, payload: dict[str, object]
    ) -> dict[str, object]:
        from omnis_hermes.managed_admission_contract import preparation_result

        assert owner.events[-1] == "commit"
        assert operation == "task_model_initialize"
        owner.payloads.append(deepcopy(payload))
        if lost_reply and len(owner.payloads) == 1:
            from omnis.supervisor.runtime_client import RuntimeUnavailable

            raise RuntimeUnavailable("SOURCE lost preparation reply")
        return preparation_result(
            payload,
            native_root_id=str(uuid4()),
            native_child_id=str(uuid4()),
            native_session_id="SOURCE-SESSION-DOUBLE",
            native_turn={
                "task_id": mapping(mapping(payload["context"])["payload"])["task_id"],
                "turn_id": "SOURCE-TURN-DOUBLE",
            },
        )

    owner.native.side_effect = prepared_double
    if lost_reply:
        with pytest.raises(CatalogError, match="TASK_INDETERMINATE"):
            await owner.handler.handle(command)
    answer = await owner.handler.handle(command)
    assert answer["preparation_status"] == "TURN_BOUND_PRE_CLIENT_HOLD"
    assert answer["inference_status"] == "HOLD"
    assert answer["account_status"] == "NOT_VERIFIED"
    import json

    assert len(json.dumps({**answer, "correlation_id": str(uuid4())}).encode()) + 1 <= 4096
    context = mapping(
        next(r for r in owner.graph if records.reference(r) == answer["context_ref"])["payload"]
    )
    assert context["purpose"] == "MODEL_TEST_PREPARE"
    assert context["requested"] == {
        "provider": "openai-codex",
        "model": "gpt-6.1-sol",
        "effort": "xhigh",
    }
    assert context["effective"] is None
    assert context["selection_ref"] != records.reference(source.selection)
    assert context["snapshot_ref"] != mapping(source.selection["payload"])["snapshot_ref"]
    before = canonical(owner.graph)
    assert owner.native.await_count == 1 + int(lost_reply)
    assert await owner.handler.handle(command) == answer
    assert owner.native.await_count == 1 + int(lost_reply)
    assert [p["mode"] for p in owner.payloads] == (
        ["CREATE", "STATUS"] if lost_reply else ["CREATE"]
    )
    saved_status.assert_awaited_once()
    assert canonical(owner.graph) == before
    from omnis_hermes.managed_admission_contract import (
        validate_initialization,
        validate_preparation_result,
    )
    from omnis_hermes.runtime_protocol import encode

    payload = owner.payloads[-1]
    assert validate_initialization(payload) == payload
    assert len(canonical(payload)) <= 32768
    assert (
        len(
            encode(
                {
                    "jsonrpc": "2.0",
                    "id": str(uuid4()),
                    "method": "omnis.managed.model_initialize",
                    "params": payload,
                }
            )
        )
        <= 65536
    )
    for key, value in (
        ("purpose", "CONTRACT_PROBE"),
        ("version", True),
        ("batch_index", True),
        ("effective", {"model": "fallback"}),
        ("account_status", "AUTHENTICATED"),
        ("task_id", str(uuid4())),
    ):
        bad = deepcopy(payload)
        body = mapping(mapping(bad["context"])["payload"])
        body[key] = value
        bad["context"] = records.envelope("model-test-context", body)
        with pytest.raises(ValueError):
            validate_initialization(bad)
    bad_result = deepcopy(
        mapping(
            next(r for r in owner.graph if records.reference(r) == answer["turn_ref"])["payload"]
        )
    )
    bad_result["model_calls"] = False
    with pytest.raises(ValueError):
        validate_preparation_result(bad_result, payload)
    owner.reserve.assert_not_awaited()
    # Complete immutable readback survives closed admission and a different boot.
    from omnis.modules.instance.domain import ControlCode, ControlConflict

    closed = Mock(side_effect=ControlConflict(ControlCode.INSTANCE_SHUTTING_DOWN))
    monkeypatch.setattr(owner.handler.service, "native_preparation_commit", closed)
    owner.runtime.boot = str(uuid4())
    saved_status.reset_mock()
    count = owner.native.await_count
    assert await owner.handler.handle(command) == answer
    assert canonical(owner.graph) == before
    assert owner.native.await_count == count
    saved_status.assert_not_awaited()
    closed.assert_not_called()
    # Typed callers may bypass model construction; reject before any receipt lookup.
    from pydantic import ValidationError

    from omnis.modules.runs.model_test import ModelTest

    rejected = []
    async with owner.handler.domain.engine.begin() as connection:
        consumer = ModelTest(owner.handler.domain)
        assert await consumer.completed(connection, command) is not None
        with monkeypatch.context() as invalid:
            lookups = [
                AsyncMock(wraps=getattr(store, name))
                for name in ("command_receipt", "owned", "command_replay")
            ]
            for name, lookup in zip(("command_receipt", "owned", "command_replay"), lookups):
                invalid.setattr(store, name, lookup)
            for entry in ("handle", "completed"):
                for field, good in (("expected_epoch", 1), ("expected_generation", 0)):
                    for value in (bool(good), float(good), str(good)):
                        bad = command.model_copy(update={field: value})
                        try:
                            if entry == "handle":
                                await owner.handler.handle(bad)
                            else:
                                await consumer.completed(connection, bad)
                        except (ValidationError, CatalogError):
                            rejected.append((entry, field, type(value)))
                for value in (True, 1.0, "1"):
                    bad = command.model_copy(
                        update={"manifest_ref": {**command.manifest_ref, "revision": value}}
                    )
                    try:
                        if entry == "handle":
                            await owner.handler.handle(bad)
                        else:
                            await consumer.completed(connection, bad)
                    except (ValidationError, CatalogError):
                        rejected.append((entry, "revision", type(value)))
            assert len(rejected) == 18
            for lookup in lookups:
                lookup.assert_not_awaited()
    assert owner.native.await_count == count
    saved_status.assert_not_awaited()
    closed.assert_not_called()
    assert canonical(owner.graph) == before
    for changes in (
        {"settings_operation_id": str(uuid4())},
        {"expected_generation": 1},
        {"instance_id": str(uuid4())},
    ):
        with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
            await owner.handler.handle(
                NativeTaskCommand.model_validate({**command.model_dump(mode="json"), **changes})
            )
    # Missing/pending observations still need current authority, never another CREATE.
    observation = next(r for r in owner.graph if records.reference(r) == answer["turn_ref"])
    owner.graph.remove(observation)
    for pending in (
        command,
        NativeTaskCommand.model_validate(
            {**command.model_dump(mode="json"), "initialization_id": str(uuid4())}
        ),
    ):
        with pytest.raises(ControlConflict):
            await owner.handler.handle(pending)
    assert owner.native.await_count == count
    owner.graph.append(observation)
    assert canonical(owner.graph) == before


def test_model_test_native_source_parks_actual_builder_before_stock_effects() -> None:
    """AST-only: no native import, constructor, thread, SDK, socket or provider execution."""
    import ast

    root = Path(__file__).resolve().parents[2] / "integrations/hermes/upstream/managed-source"
    loop = ast.parse((root / "agent/conversation_loop.py").read_bytes())
    turn = next(
        n for n in loop.body if isinstance(n, ast.FunctionDef) and n.name == "run_conversation"
    )
    source = ast.unparse(turn)
    assert source.index("_model_test_preparation") < source.index("native_turn_images")
    assert "return build_turn_context(" in source
    builder_tree = ast.parse((root / "agent/turn_context.py").read_bytes())
    builder = next(
        n
        for n in builder_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "build_turn_context"
    )
    preparation = next(n for n in builder.body if isinstance(n, ast.If))
    prefix = ast.unparse(preparation)
    assert "_bind_turn_identity(" in prefix
    assert (
        prefix.index("_bind_turn_identity(")
        < prefix.index("_model_test_ready.set()")
        < prefix.index("_model_test_closed.wait()")
    )
    assert "raise ValueError" in prefix
    assert "turn_context_compaction" not in prefix
    assert "install_safe_stdio()" not in prefix
    init = ast.parse((root / "agent/agent_init.py").read_bytes())
    configure = next(
        n for n in init.body if isinstance(n, ast.FunctionDef) and n.name == "configure_model_test"
    )
    text = ast.unparse(configure)
    assert "new_session_id(" in text and "agent.client = None" in text
    assert "agent._model_test_identity" in text
    assert "resolve_runtime" not in text and "config_operation" not in text


@pytest.mark.asyncio
async def test_private_owner_commits_source_and_intent_before_core_handoff_then_replays_readonly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = SourceOwner(tmp_path, monkeypatch)
    source_ref = await owner.produce()
    owner.events.clear()
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "action": "model_initialization",
            "provider_config_ref": source_ref,
            "initialization_id": str(uuid4()),
        }
    )
    answer = await owner.handler.handle(command)
    assert answer["initialization_status"] == "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM"
    assert answer["inference_status"] == "HOLD"
    owner.native.assert_awaited_once()
    assert len(owner.payloads) == 1 and owner.payloads[0]["mode"] == "CREATE"
    assert [r["kind"] for r in owner.graph].count("native-initialization-intent") == 1
    assert [r["kind"] for r in owner.graph].count("native-initialization-observation") == 1
    before = canonical(owner.graph)
    assert await owner.handler.handle(command) == answer
    owner.native.assert_awaited_once()
    assert canonical(owner.graph) == before
    owner.reserve.assert_not_awaited()
    assert not {"native-turn", "model-dispatch", "model-reservation"} & {
        str(r["kind"]) for r in owner.graph
    }


@pytest.mark.asyncio
async def test_uncertain_initialization_replays_status_without_another_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnis.supervisor.runtime_client import RuntimeUnavailable

    owner = SourceOwner(tmp_path, monkeypatch)
    source_ref = await owner.produce()
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "action": "model_initialization",
            "provider_config_ref": source_ref,
            "initialization_id": str(uuid4()),
        }
    )
    modes: list[object] = []

    async def lost(
        service: InstanceService, lease: UUID, operation: str, payload: dict[str, object]
    ) -> dict[str, object]:
        modes.append(payload["mode"])
        raise RuntimeUnavailable("SOURCE lost reply")

    owner.native.side_effect = lost
    for _ in range(2):
        with pytest.raises(CatalogError, match="TASK_INDETERMINATE"):
            await owner.handler.handle(command)
    assert modes == ["CREATE", "STATUS"]
    assert [r["kind"] for r in owner.graph].count("native-initialization-intent") == 1
    assert [r["kind"] for r in owner.graph].count("native-initialization-observation") == 0
    owner.reserve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["binding_id", "stage_started", "release_started", "final_id"])
async def test_initialization_refuses_progressed_state_before_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    owner = SourceOwner(tmp_path, monkeypatch)
    source_ref = await owner.produce()
    owner.state[field] = str(uuid4()) if field.endswith("_id") else True
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "action": "model_initialization",
            "provider_config_ref": source_ref,
            "initialization_id": str(uuid4()),
        }
    )
    before = canonical(owner.graph)
    with pytest.raises(CatalogError):
        await owner.handler.handle(command)
    owner.native.assert_not_awaited()
    assert canonical(owner.graph) == before


@pytest.mark.asyncio
async def test_native_source_binding_rejects_boolean_revision_before_python_equality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    adapter = importlib.import_module("omnis_hermes.managed_admission_contract")
    owner = SourceOwner(tmp_path, monkeypatch)
    source_ref = await owner.produce()
    command = NativeTaskCommand.model_validate(
        {
            **owner.base,
            "action": "model_initialization",
            "provider_config_ref": source_ref,
            "initialization_id": str(uuid4()),
        }
    )
    await owner.handler.handle(command)
    good = owner.payloads[0]
    assert adapter.validate_initialization(good) == good
    bad = deepcopy(good)
    source = mapping(bad["provider_config"])
    body = mapping(source["payload"])
    body["manifest_ref"] = {**mapping(body["manifest_ref"]), "revision": True}
    source["payload"] = body
    source["digest"] = sha256(
        canonical({k: v for k, v in source.items() if k != "digest"})
    ).hexdigest()
    bad["provider_config"] = source
    bad["source_byte_digest"] = sha256(canonical(source)).hexdigest()
    receipt = mapping(bad["producer_receipt"])
    receipt_body = mapping(receipt["payload"])
    receipt_body["result_refs"] = {"provider_config_ref": records.reference(source)}
    receipt["payload"] = receipt_body
    receipt["digest"] = sha256(
        canonical({k: v for k, v in receipt.items() if k != "digest"})
    ).hexdigest()
    bad["producer_receipt"] = receipt
    with pytest.raises(ValueError):
        adapter.validate_initialization(bad)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["missing", "foreign", "stale", "boolean", "digest"])
async def test_owner_refuses_unavailable_configuration_refs_before_initialization_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    from pydantic import ValidationError

    owner = SourceOwner(tmp_path, monkeypatch)
    source_ref = await owner.produce()
    mutations: dict[str, dict[str, object]] = {
        "foreign": {"id": str(uuid4())},
        "stale": {"revision": 2},
        "boolean": {"revision": True},
        "digest": {"digest": "0" * 64},
        "missing": {},
    }
    bad: object = {**source_ref, **mutations[mutation]}
    if mutation == "missing":
        bad = None
    before = canonical(owner.graph)
    with pytest.raises((CatalogError, ValidationError)):
        await owner.handler.handle(
            NativeTaskCommand.model_validate(
                {
                    **owner.base,
                    "action": "model_initialization",
                    "provider_config_ref": bad,
                    "initialization_id": str(uuid4()),
                }
            )
        )
    owner.native.assert_not_awaited()
    owner.reserve.assert_not_awaited()
    assert canonical(owner.graph) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", ["host", "peer"])
async def test_owner_initialization_crosses_existing_transport_validators(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, gate: str
) -> None:
    """Real UDS/NativePeer framing; storage, process and native reply remain doubles."""
    import asyncio
    import importlib
    import json
    import socket
    import sys
    import time

    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.policy.ready_model_configuration import validate_ready_source

    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    managed = importlib.import_module("omnis_hermes.managed_admission_contract")
    wire = importlib.import_module("omnis_hermes.runtime_protocol")
    host_type = importlib.import_module("omnis_hermes.runtime_host").RuntimeHost
    if gate == "host":
        # Qualify the actual producer at its existing configuration byte maximum.
        qualified = configuration()
        qualified.update(provider="p" * 256, model_id="m" * 256)
        qualified["capabilities"] = {str(i) + "x" * 63: False for i in range(4)}
        qualified["base_url"] = str(qualified["base_url"]) + "x" * (
            2048 - len(canonical(qualified))
        )
        assert len(canonical(validate_ready_source(qualified))) == 2048
        with pytest.raises(CatalogError):
            validate_ready_source({**qualified, "base_url": str(qualified["base_url"]) + "x"})
        monkeypatch.setattr(sys.modules[__name__], "configuration", lambda: deepcopy(qualified))
    owner = SourceOwner(ipc_directory, monkeypatch)
    source_ref = await owner.produce()
    left, right = socket.socketpair()
    reader, writer = await asyncio.open_connection(sock=left)
    remote_reader, remote_writer = await asyncio.open_connection(sock=right)
    process = Mock(spec=asyncio.subprocess.Process)
    process.stdin, process.stdout = writer, reader
    process.stderr = asyncio.StreamReader()
    process.stderr.feed_eof()
    process.returncode = None
    peer = wire.NativePeer(process)
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
    frames: list[dict[str, object]] = []

    async def native_reply() -> None:
        frame = wire.decode(await remote_reader.readuntil(b"\n"))
        assert frame["method"] == managed.RPC["task_model_initialize"]
        result = await owner.native_double(
            owner.handler.service, owner.lease, "task_model_initialize", frame["params"]
        )
        remote_writer.write(wire.encode({"jsonrpc": "2.0", "id": frame["id"], "result": result}))
        await remote_writer.drain()

    responding = asyncio.create_task(native_reply())
    try:
        async with host_type(ipc_directory) as host:
            host.state, host.generation, host.epoch = "READY", 0, 1
            host.deadline_ns = time.monotonic_ns() + 4_000_000_000
            host.process, host.peer = process, peer
            owner.runtime.boot = host.boot
            service = owner.handler.service
            monkeypatch.setattr(
                service,
                "runtime_authority",
                AsyncMock(
                    side_effect=lambda *_a, **_k: RuntimeAuthority(
                        generation=0, epoch=1, deadline_ns=time.monotonic_ns() + 3_000_000_000
                    )
                ),
            )
            validate = host._validate

            def observe(body: object) -> dict[str, object]:
                checked = mapping(validate(body))
                frames.append(deepcopy(checked))
                return checked

            monkeypatch.setattr(host, "_validate", observe)
            if gate == "host":
                monkeypatch.setattr(
                    owner.runtime, "managed", RuntimeClient.managed.__get__(owner.runtime)
                )
                await owner.runtime.connect()
            else:

                async def through_peer(
                    service: InstanceService, lease: UUID, op: str, payload: dict[str, object]
                ) -> dict[str, object]:
                    return mapping(await peer.call(managed.RPC[op], payload, timeout=3.2))

                monkeypatch.setattr(owner.runtime, "managed", through_peer)
            try:
                command = NativeTaskCommand.model_validate(
                    {
                        **owner.base,
                        "action": "model_initialization",
                        "provider_config_ref": source_ref,
                        "initialization_id": str(uuid4()),
                    }
                )
                answer = await owner.handler.handle(command)
                assert answer["initialization_status"] == "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM"
                assert answer["inference_status"] == "HOLD"
                await responding
                good = owner.payloads[0]
                observation = mapping(mapping(answer["initialization_observation"])["payload"])
                assert observation["model_calls"] == 0
                assert observation["native_turn"] is None
                assert observation["client_status"] == "DEFERRED_NO_CREDENTIAL"
                assert await owner.handler.handle(command) == answer
                assert [r["kind"] for r in owner.graph].count("native-initialization-intent") == 1
                assert [r["kind"] for r in owner.graph].count(
                    "native-initialization-observation"
                ) == 1
                owner.reserve.assert_not_awaited()
                assert peer.next_id == 1 and not peer.pending
                if gate == "host":
                    frame = frames[-1]
                    controller_bytes = json.dumps(frame, separators=(",", ":")).encode() + b"\n"
                    native_bytes = wire.encode(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": managed.RPC["task_model_initialize"],
                            "params": good,
                        }
                    )
                    assert len(canonical(good)) <= managed.MAX_BYTES == 32768
                    assert len(controller_bytes) <= wire.MAX_FRAME == 65536
                    print(
                        "initialization_sizes",
                        len(canonical(good)),
                        len(controller_bytes),
                        len(native_bytes),
                    )
                    # Generic frame max/max+1, not a claim of qualified DATA at 64 KiB.
                    boundary = {"jsonrpc": "2.0", "id": 1, "result": ""}
                    boundary["result"] = "x" * (wire.MAX_FRAME - len(wire.encode(boundary)))
                    assert len(wire.encode(boundary)) == wire.MAX_FRAME
                    assert wire.decode(wire.encode(boundary)) == boundary
                    boundary["result"] = str(boundary["result"]) + "x"
                    with pytest.raises(wire.ProtocolError, match="Frame limit"):
                        wire.encode(boundary)
                    with pytest.raises(wire.ProtocolError, match="Frame limit"):
                        wire.decode(json.dumps(boundary, separators=(",", ":")).encode() + b"\n")
                    for field, value in (
                        ("provider_config", None),
                        ("producer_receipt", None),
                        ("owner_id", str(uuid4())),
                        ("run_id", str(uuid4())),
                        ("source_byte_digest", "0" * 64),
                        ("initialization_data_digest", "0" * 64),
                        ("intent_ref", {**mapping(good["intent_ref"]), "revision": True}),
                        ("manifest_ref", {**mapping(good["manifest_ref"]), "revision": True}),
                    ):
                        bad = {**good, field: value}
                        with pytest.raises(ValueError):
                            validate({**frame, "payload": bad})
                        with pytest.raises(ValueError):
                            await peer.call(managed.RPC["task_model_initialize"], bad)
                    for field in ("provider_config", "producer_receipt", "intent_ref"):
                        bad = {k: v for k, v in good.items() if k != field}
                        with pytest.raises(ValueError):
                            validate({**frame, "payload": bad})
                        with pytest.raises(ValueError):
                            await peer.call(managed.RPC["task_model_initialize"], bad)
                    for bad in (
                        {**frame, "boot": str(uuid4())},
                        {**frame, "epoch": 2},
                        {**frame, "generation": 1},
                        {**frame, "capability": "foreign"},
                        {**frame, "epoch": True},
                        {**frame, "generation": False},
                    ):
                        with pytest.raises(ValueError):
                            validate(bad)
                    with pytest.raises(ValueError, match="Stale initialization authority"):
                        await host._managed(
                            {**frame, "payload": {**good, "runtime_boot": str(uuid4())}}
                        )
                    for fence_field, fence_value in (("generation", 1), ("epoch", 2)):
                        with monkeypatch.context() as stale:
                            stale.setattr(host, fence_field, fence_value)
                            with pytest.raises(ValueError, match="Stale initialization authority"):
                                await host._managed(frame)
                    for deadline in (
                        True,
                        time.monotonic_ns() - 1,
                        time.monotonic_ns() + 4_600_000_000,
                        time.monotonic_ns() + 5_100_000_000,
                    ):
                        with pytest.raises(ValueError):
                            await host._managed({**frame, "deadline_ns": deadline})
                    assert peer.next_id == 1 and not peer.pending and len(owner.payloads) == 1
            finally:
                # No process was launched; do not send synthetic PID/process-group signals.
                host.process, host.peer = None, None
                await owner.runtime.close()
    finally:
        responding.cancel()
        await asyncio.gather(responding, return_exceptions=True)
        await peer.close()
        remote_writer.close()
        await remote_writer.wait_closed()


def test_owned_preclient_core_cannot_enter_public_turn_facade() -> None:
    """SOURCE getter body only; not native construction or turn proof."""
    import ast

    source = (
        Path(__file__).resolve().parents[2]
        / "integrations/hermes/upstream/managed-source/run_agent.py"
    )
    cls = next(
        n
        for n in ast.parse(source.read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "AIAgent"
    )
    getter = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__getattribute__"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[getter], type_ignores=[]), str(source), "exec"), namespace)

    class SourceActor:
        def run_conversation(self) -> None:
            raise AssertionError("preclient actor entered turn facade")

    actor = SourceActor()
    get = namespace["__getattribute__"]
    assert callable(get)
    assert get(actor, "run_conversation") == actor.run_conversation
    actor.__dict__["_owned_initialization"] = object()  # marker denial, never authority
    with pytest.raises(ValueError, match="DEFERRED_NO_CREDENTIAL"):
        get(actor, "run_conversation")
