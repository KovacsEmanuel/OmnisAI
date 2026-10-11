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
            if owner != self.owner or run != self.run:
                raise CatalogError("REF_UNAVAILABLE")
            matches = [r for r in self.graph if records.reference(r) == pin]
            if len(matches) != 1:
                raise CatalogError("REF_UNAVAILABLE")
            return record(deepcopy(matches[0]))

        async def put(c: object, owner: str, run: str, value: object) -> None:
            assert owner == self.owner and run == self.run
            self.graph.append(record(value))

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


def test_owned_preclient_core_cannot_enter_public_turn_facade() -> None:
    """SOURCE getter body only; not native construction or turn proof."""
    import ast

    source = Path(__file__).resolve().parents[2] / "integrations/hermes/upstream/managed-source/run_agent.py"
    cls = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "AIAgent")
    getter = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__getattribute__")
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
