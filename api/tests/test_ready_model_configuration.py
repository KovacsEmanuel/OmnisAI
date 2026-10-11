"""First actual owner producer→storage readback→initialization-data reader SOURCE.

Storage/domain/session seams are doubles, never native/warm/inference authority.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import mapping
from omnis.policy import budgets
from omnis.supervisor.native_tasks import NativeTaskOwner
from omnis.supervisor.runtime_client import RuntimeClient
from test_managed_contract import manifest as manifest_fixture


def configuration() -> dict[str, object]:
    # Explicit isolated SOURCE material, not a real account/compatible model grant.
    return {
        "version": 1,
        "decision_id": str(uuid4()),
        "provider": "owned-fixture-provider",
        "model_id": "owned-fixture-model",
        "base_url": "https://fixture.invalid/v1",
        "api_mode": "chat_completions",
        "reasoning_config": {"enabled": True, "effort": "high"},
        "max_tokens": 64,
        "capabilities": {},
        "technical_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 10},
        "native_config": {
            "reasoning_echo": False,
            "prompt_caching": False,
            "context_length": 8192,
            "compression": {"enabled": False},
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("stage_cut", [None, 1, 2])
async def test_owner_produced_ready_source_is_first_reader_input_with_all_grants_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage_cut: int | None
) -> None:
    manifest = manifest_fixture()
    run = str(mapping(manifest["payload"])["run_id"])
    owner, lease, instance, command_id = str(uuid4()), uuid4(), str(uuid4()), str(uuid4())
    request = {
        "op": "native_task",
        "schema_version": 1,
        "owner_id": owner,
        "command_id": command_id,
        "instance_id": instance,
        "expected_epoch": 1,
        "expected_generation": 0,
        "action": "model_configuration",
        "manifest_ref": records.reference(manifest),
        "configuration": configuration(),
    }
    command = NativeTaskCommand.model_validate(request)  # missing actual owner consumer is RED
    graph = [manifest]
    domain = ManagedAdmission(Mock(spec=AsyncEngine))
    readback = AsyncMock(
        return_value={
            "manifest_ref": records.reference(manifest),
            "manifest": manifest,
            "binding": None,
            "results": [],
            "stage_started": False,
            "release_started": False,
        }
    )
    monkeypatch.setattr(domain, "readback", readback)
    conn = Mock(spec=AsyncConnection)
    row = Mock()
    row.scalar_one.return_value = instance
    conn.execute = AsyncMock(return_value=row)
    monkeypatch.setattr(budgets, "_transaction", AsyncMock())
    state_calls = 0

    async def state_read(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal state_calls
        state_calls += 1
        return {
            "run_id": run,
            "binding_id": None,
            "stage_started": state_calls == stage_cut,
            "release_started": False,
            "final_id": None,
        }

    monkeypatch.setattr(store, "state", state_read)
    monkeypatch.setattr(store, "graph", AsyncMock(side_effect=lambda *_: list(graph)))

    async def get(c: object, o: str, r: str, pin: object) -> dict[str, object]:
        assert o == owner and r == run
        return next(item for item in graph if records.reference(item) == pin)

    async def put(c: object, o: str, r: str, value: object) -> None:
        assert o == owner and r == run
        graph.append(mapping(value))

    monkeypatch.setattr(store, "get", get)
    monkeypatch.setattr(store, "put", put)
    replies: dict[str, dict[str, object]] = {}

    async def replay(c: object, o: str, k: str, op: str, value: object) -> dict[str, object] | None:
        return replies.get(k)

    async def complete(
        c: object, o: str, r: str, k: str, op: str, value: object, refs: dict[str, object]
    ) -> None:
        replies[k] = refs

    monkeypatch.setattr(store, "command_replay", replay)
    monkeypatch.setattr(store, "command_complete", complete)
    service = Mock(spec=InstanceService)
    events = []

    @asynccontextmanager
    async def fence(*args: object) -> AsyncIterator[AsyncConnection]:
        events.append("begin")
        yield conn
        events.append("commit")

    service.native_preparation_commit = fence
    runtime = RuntimeClient(tmp_path, generation=0, epoch=1)
    native_call = AsyncMock(side_effect=AssertionError("configuration DATA reached native"))
    monkeypatch.setattr(runtime, "managed", native_call)
    reserve = AsyncMock(side_effect=AssertionError("configuration DATA reserved inference"))
    monkeypatch.setattr(budgets, "reserve", reserve)
    handler = NativeTaskOwner(domain, service, lease, 1, runtime)
    if stage_cut is not None:
        from omnis.modules.settings.catalog_models import CatalogError

        with pytest.raises(CatalogError, match="MODEL_CONFIGURATION_REJECTED"):
            await handler.handle(command)
        assert len([x for x in graph if x["kind"] == "provider-config"]) == (
            0 if stage_cut == 1 else 1
        )
        native_call.assert_not_awaited()
        reserve.assert_not_awaited()
        return
    answer = await handler.handle(command)
    assert (
        answer["configuration_status"] == "READY"
        and answer["initialization_status"] == answer["inference_status"] == "HOLD"
    )
    pin = mapping(answer["provider_config_ref"])
    assert pin["kind"] == "provider-config"
    item = await get(conn, owner, run, pin)
    body = mapping(item["payload"])
    data = json.loads(str(answer["initialization_data"]))
    requested = mapping(request["configuration"])
    assert data["provider"] == requested["provider"]
    assert data["reasoning_config"] == requested["reasoning_config"]
    assert data["max_tokens"] == 64 and data["native_config"]["context_length"] == 8192
    assert (
        body["configuration"] == request["configuration"] and body["inference_authorized"] is False
    )
    assert events == ["begin", "commit", "begin", "commit"]
    assert answer == await handler.handle(command)
    assert len([x for x in graph if x["kind"] == "provider-config"]) == 1
    native_call.assert_not_awaited()
    reserve.assert_not_awaited()


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "READY"),
        ("api_key", "UNTRUSTED"),
        ("version", True),
        ("api_mode", "codex_responses"),
        ("max_tokens", 65),
        ("base_url", "https://fixture.invalid:/v1"),
        ("base_url", "https://user:secret@fixture.invalid/v1"),
        ("base_url", "https://fixture.invalid/v1?"),
        ("base_url", "https://fixture.invalid/v1#"),
    ],
)
def test_ready_source_rejects_authority_secret_alias_and_implicit_route(
    field: str, value: object
) -> None:
    from omnis.policy.ready_model_configuration import validate_ready_source

    source = configuration()
    source[field] = value
    with pytest.raises(ValueError):
        validate_ready_source(source)


def test_ready_source_detaches_alias_and_preserves_exact_initialization_material() -> None:
    from omnis.policy.ready_model_configuration import initialization_data, validate_ready_source

    source = configuration()
    qualified = validate_ready_source(source)
    native = source["native_config"]
    assert isinstance(native, dict)
    native["context_length"] = 65536
    source["model_id"] = "DIFFERENT_EXPLICIT_INPUT"
    assert json.loads(initialization_data(qualified))["model_id"] == "owned-fixture-model"
    assert json.loads(initialization_data(source))["model_id"] == "DIFFERENT_EXPLICIT_INPUT"
    assert json.loads(initialization_data(qualified))["native_config"]["context_length"] == 8192
    assert json.loads(initialization_data(source))["native_config"]["context_length"] == 65536
    assert (
        json.loads(initialization_data(qualified))["reasoning_config"]
        == qualified["reasoning_config"]
    )


@pytest.mark.parametrize("field", ["provider", "model_id", "base_url", "effort", "capability"])
@pytest.mark.parametrize("control", ["\x7f", "\x85", "\u2028"])
def test_ready_identifiers_reject_controls_without_repair(field: str, control: str) -> None:
    from omnis.policy.ready_model_configuration import validate_ready_source

    source = configuration()
    if field == "effort":
        assert isinstance(source["reasoning_config"], dict)
        source["reasoning_config"]["effort"] = "high" + control
    elif field == "capability":
        source["capabilities"] = {"tool" + control: False}
    else:
        source[field] = str(source[field]) + control
    with pytest.raises(ValueError):
        validate_ready_source(source)


@pytest.mark.parametrize("field", ["provider", "native_config"])
def test_source_exact_types_before_canonicalization(field: str) -> None:
    from omnis.policy.ready_model_configuration import validate_ready_source

    class ForgedString(str):
        pass

    class ForgedDict(dict[str, object]):
        pass

    source = configuration()
    source[field] = (
        ForgedString("owner-provider")
        if field == "provider"
        else ForgedDict(mapping(source[field]))
    )
    with pytest.raises(ValueError):
        validate_ready_source(source)
