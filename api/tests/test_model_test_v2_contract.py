import json
from uuid import uuid4

import pytest

from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.runs.model_test_contract import ModelTestView, Outcome
from omnis.modules.runs.model_test_models import ModelTestControl, ModelTestRequest


@pytest.mark.asyncio
async def test_latest_entry_uses_retained_snapshot_and_existing_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from omnis.modules.runs import model_test_store as store
    from omnis.modules.runs.model_test_contract import EntrySnapshot, Operation, Ref
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.modules.settings import provider_model_test

    instance, entry, identity, connection = (str(uuid4()) for _ in range(4))
    reference = Ref(
        instance_id=instance, id=str(uuid4()), kind="model-entry-snapshot-v1", digest="a" * 64
    )
    snapshot = EntrySnapshot.model_validate(
        {
            "entry": {
                "entry_id": entry,
                "revision": 2,
                "connection_id": connection,
                "connection_revision": 1,
                "model": "Exact/model",
                "output_tokens": 128,
            },
            "connection": {
                "connection_id": connection,
                "revision": 1,
                "provider": "openrouter",
                "enabled": True,
                "credential_revision": 1,
                "secret_id": str(uuid4()),
            },
            "capabilities_ref": {**reference.model_dump(), "kind": "model-entry-capabilities-v1"},
            "endpoint": "https://openrouter.ai/api/v1",
        }
    )
    op = Operation(
        instance_id=instance,
        operation_id=identity,
        command_id=identity,
        payload_digest="b" * 64,
        config_snapshot_ref=reference,
        input_projection_ref=reference,
        execution_owner_id=str(uuid4()),
        generation=4,
        owner_epoch=6,
        cancel_epoch=1,
        deadline=datetime.now(UTC),
        state_revision=1,
        state="RUNNING",
        finish_reason=None,
        outcome_ref=None,
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(
        mappings=lambda: SimpleNamespace(one_or_none=lambda: op.model_dump())
    )

    @asynccontextmanager
    async def connect() -> AsyncIterator[AsyncMock]:
        yield db

    runtime = object.__new__(ApiKeyModelTest)
    runtime.instance = instance
    monkeypatch.setattr(
        runtime, "service", SimpleNamespace(engine=SimpleNamespace(connect=connect)), raising=False
    )
    monkeypatch.setattr(
        runtime, "settings", SimpleNamespace(selection=AsyncMock(return_value=None)), raising=False
    )
    monkeypatch.setattr(runtime, "latest", AsyncMock(return_value=None))
    resolved = AsyncMock(return_value=snapshot.model_dump(mode="json"))
    monkeypatch.setattr(store, "resolve", resolved)
    monkeypatch.setattr(provider_model_test, "current", AsyncMock(return_value=False))
    result = await runtime.handle(
        ModelTestControl(op="entry_model_test", action="read", entry_id=entry)
    )
    assert (
        result["entry_id"] == entry
        and result["operation_id"] == identity
        and result["current"] is False
    )
    resolved.assert_awaited_once_with(db, instance, reference, "model-entry-snapshot-v1")
    sql, values = db.execute.await_args.args
    assert values == {"instance": instance, "entry": entry}
    assert "model_record_v2" in str(sql) and "payload->'entry'->>'entry_id'" in str(sql)
    assert (
        "generation DESC" in str(sql)
        and "owner_epoch DESC" in str(sql)
        and "deadline DESC" in str(sql)
    )
    assert "created_at" not in str(sql)
    resolved.side_effect = store.ModelConflict("REF_UNAVAILABLE")
    with pytest.raises(store.ModelConflict, match="REF_UNAVAILABLE"):
        await runtime.handle(ModelTestControl(op="entry_model_test", action="read", entry_id=entry))
    db.execute.return_value = SimpleNamespace(
        mappings=lambda: SimpleNamespace(one_or_none=lambda: None)
    )
    with pytest.raises(store.ModelConflict, match="NOT_FOUND"):
        await runtime.handle(ModelTestControl(op="entry_model_test", action="read", entry_id=entry))


def test_entry_read_has_exactly_one_target_and_keeps_wire_limits() -> None:
    identity = str(uuid4())
    for target in ("entry_id", "operation_id"):
        command = ModelTestControl.model_validate(
            {"op": "entry_model_test", "action": "read", target: identity}
        )
        frame = ControlRequest(version=1, capability="a" * 64, command=command)
        assert len(command.model_dump_json().encode()) <= 3600
        assert len(frame.model_dump_json().encode() + b"\n") <= 4096
        assert ControlRequest.model_validate_json(frame.model_dump_json()).command == command
    for extra in (
        {},
        {"entry_id": identity, "operation_id": identity},
        {"entry_id": identity, "command_id": identity},
        {"entry_id": identity, "consent": True},
        {"entry_id": identity, "expected_entry_revision": 1},
        {"entry_id": identity, "expected_connection_revision": 1},
        {"entry_id": identity, "catalog_command_id": identity},
        {"entry_id": identity, "expected_state_revision": 1},
        {"entry_id": identity, "expected_selection_revision": 1},
    ):
        with pytest.raises(ValueError):
            ModelTestControl.model_validate({"op": "entry_model_test", "action": "read", **extra})
    with pytest.raises(ValueError):
        ModelTestControl(op="model_test", action="read", entry_id=identity)


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens", "reasoning_tokens"])
def test_usage_bounds_match_public_and_outcome(field: str) -> None:
    from typing import Annotated

    from pydantic import TypeAdapter

    for model in (ModelTestView, Outcome):
        info = model.model_fields[field]
        adapter: TypeAdapter[object] = TypeAdapter(Annotated[info.annotation, *info.metadata])
        assert adapter.validate_python(9007199254740991) == 9007199254740991
        assert adapter.validate_python(0) == 0
        assert adapter.validate_python(None) is None
        for invalid in (-1, 9007199254740992, True, "9", 1.5):
            with pytest.raises(ValueError):
                adapter.validate_python(invalid)


def test_complete_new_command_frames_are_bounded() -> None:
    identity, command = str(uuid4()), str(uuid4())
    maximum = 9223372036854775807
    for payload in (
        {"action": "read", "operation_id": identity},
        {"action": "read", "command_id": command},
        {
            "action": "start",
            "operation_id": identity,
            "expected_selection_revision": maximum,
            "consent": True,
        },
        {
            "action": "cancel",
            "operation_id": identity,
            "command_id": command,
            "expected_state_revision": maximum,
        },
        {"action": "refresh", "command_id": command, "expected_selection_revision": maximum},
    ):
        value = ModelTestControl.model_validate({"op": "model_test", **payload})
        assert len(value.model_dump_json().encode()) <= 3600
        frame = (
            ControlRequest(version=1, capability="a" * 64, command=value).model_dump_json().encode()
            + b"\n"
        )
        assert len(frame) <= 4096
        assert json.loads(frame)["command"]["op"] == "model_test"


def test_no_caller_authority_or_coerced_consent() -> None:
    intent = {"operation_id": str(uuid4()), "expected_selection_revision": 1, "consent": True}
    ModelTestRequest.model_validate(intent)
    for consent in (False, 1, "true", None):
        with pytest.raises(ValueError):
            ModelTestRequest.model_validate({**intent, "consent": consent})
        with pytest.raises(ValueError):
            ModelTestControl.model_validate(
                {"op": "model_test", "action": "start", **intent, "consent": consent}
            )
    for field in ("secret", "epoch", "config_snapshot_ref", "prompt", "url", "scope_kind"):
        with pytest.raises(ValueError):
            ModelTestRequest.model_validate({**intent, field: "caller-data"})
