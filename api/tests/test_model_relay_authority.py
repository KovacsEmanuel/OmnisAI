"""SOURCE storage decisions; PostgreSQL durability is a separate admitted gate."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as store
from omnis.supervisor.model_relay_protocol import Scope


def scope_fields() -> dict[str, object]:
    return {
        "instance_id": str(uuid4()),
        "kind": "MODEL_DISPATCH",
        "id": str(uuid4()),
        "execution_owner_id": str(uuid4()),
        "generation": 1,
        "owner_epoch": 1,
        "cancel_epoch": 1,
        "deadline": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
        "provider": "openrouter",
    }


@pytest.mark.asyncio
async def test_original_uuid_binding_repeated_or_changed_never_allocates() -> None:
    fields = scope_fields()
    original = Scope.parse({**fields, "operation_serial": 7})
    row = {**original.wire(), "state": "ACTIVE"}
    db = AsyncMock(spec=AsyncConnection)
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = row
    db.execute.return_value = result
    assert await store.relay_scope(db, fields, allocate=True) == original
    assert len(db.execute.await_args_list) == 1
    with pytest.raises(store.ModelConflict, match="RELAY_AUTHORITY_DENIED"):
        await store.relay_scope(db, {**fields, "operation_serial": 8}, allocate=True)
    for key, value in {
        "deadline": (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
        "generation": 2,
        "execution_owner_id": str(uuid4()),
        "owner_epoch": 2,
        "cancel_epoch": 2,
        "provider": "orcarouter",
    }.items():
        with pytest.raises(store.ModelConflict, match="RELAY_AUTHORITY_DENIED"):
            await store.relay_scope(db, {**fields, key: value}, allocate=True)
    assert all(str(call.args[0]).startswith("SELECT") for call in db.execute.await_args_list)
    row["state"] = "DRAINED"
    assert await store.relay_scope(db, fields, allocate=True) == original
    with pytest.raises(store.ModelConflict, match="RELAY_AUTHORITY_DENIED"):
        await store.relay_scope(db, fields)


@pytest.mark.asyncio
async def test_new_admitted_binding_writes_one_typed_serial_and_original_uuid() -> None:
    fields = scope_fields()
    expected = Scope.parse({**fields, "operation_serial": 8})
    db = AsyncMock(spec=AsyncConnection)
    lookup, allocation = Mock(), Mock()
    lookup.mappings.return_value.one_or_none.return_value = None
    allocation.scalar_one.return_value = 8
    db.execute.side_effect = [lookup, allocation, Mock()]
    assert await store.relay_scope(db, fields, allocate=True) == expected
    assert "max(operation_serial),0)+1" in str(db.execute.await_args_list[1].args[0])
    insertion = db.execute.await_args_list[2]
    assert str(insertion.args[0]).startswith("INSERT INTO model_relay_authority")
    assert insertion.args[1] == expected.wire()


@pytest.mark.asyncio
async def test_historical_missing_binding_is_read_only_no_guard_allocation() -> None:
    db = AsyncMock(spec=AsyncConnection)
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = None
    db.execute.return_value = result
    with pytest.raises(store.ModelConflict, match="RELAY_AUTHORITY_DENIED"):
        await store.relay_scope(db, scope_fields())
    assert len(db.execute.await_args_list) == 1
    assert str(db.execute.await_args.args[0]).startswith("SELECT")


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_ack,recovery", [(False, False), (True, False), (False, True)])
async def test_existing_owner_retires_original_scope_only_after_drain(
    monkeypatch: pytest.MonkeyPatch, lost_ack: bool, recovery: bool
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from dataclasses import replace
    from pathlib import Path

    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.supervisor.model_relay import RelayFailure
    from omnis.supervisor.model_sender import ModelSender

    original = Scope.parse({**scope_fields(), "operation_serial": 1})
    newer = replace(
        original,
        operation_serial=2,
        id=str(uuid4()),
        execution_owner_id=str(uuid4()),
        owner_epoch=2,
    )
    runtime = ApiKeyModelTest.__new__(ApiKeyModelTest)
    runtime.instance = original.instance_id
    runtime.settings = Mock(owner=original.execution_owner_id, epoch=original.owner_epoch)
    runtime.sender = ModelSender(Path("/unopened-owned-fixture/model.sock"))
    db = AsyncMock(spec=AsyncConnection)

    @asynccontextmanager
    async def transaction() -> AsyncIterator[AsyncConnection]:
        yield db

    runtime.service = Mock(engine=Mock(connect=transaction, begin=transaction))
    monkeypatch.setattr(store, "relay_pending", AsyncMock(return_value=(0, [original, newer])))
    retired = AsyncMock()
    monkeypatch.setattr(store, "retire_relay", retired)
    binds = AsyncMock(side_effect=AssertionError("drain must never allocate"))
    monkeypatch.setattr(store, "relay_scope", binds)

    async def physical_drain() -> None:
        retired.assert_not_awaited()
        assert runtime.sender.transport.backend.relay.scopes == (
            {original, newer} if recovery else {original}
        )
        if lost_ack:
            raise RelayFailure("RELAY_CONTROL_UNCERTAIN")

    monkeypatch.setattr(runtime.sender, "drain", physical_drain)
    try:
        if lost_ack:
            with pytest.raises(RelayFailure):
                await runtime.retire_relay(recovery=recovery)
            retired.assert_not_awaited()
        else:
            await runtime.retire_relay(recovery=recovery)
            assert [call.args[1] for call in retired.await_args_list] == (
                [original, newer] if recovery else [original]
            )
        binds.assert_not_awaited()
    finally:
        await runtime.sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("request_kind", ["metadata-request", "catalog-request"])
async def test_metadata_and_catalog_guards_read_original_binding_no_remint(
    monkeypatch: pytest.MonkeyPatch, request_kind: str
) -> None:
    import asyncio
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.modules.settings.provider_key_service import ConnectionRevision

    fields = {**scope_fields(), "kind": "METADATA_COMMAND"}
    original = Scope.parse({**fields, "operation_serial": 1})
    connection = ConnectionRevision(
        connection_id=str(uuid4()),
        revision=1,
        provider="openrouter",
        enabled=True,
        secret_id=str(uuid4()),
        credential_revision=1,
    )
    runtime = ApiKeyModelTest.__new__(ApiKeyModelTest)
    runtime.instance, runtime.closing = original.instance_id, False
    runtime.settings = Mock(owner=original.execution_owner_id, epoch=1, lock=asyncio.Lock())
    runtime.settings.require_connection = AsyncMock(return_value=connection)
    db = AsyncMock(spec=AsyncConnection)
    retained = {**original.wire(), "state": "ACTIVE"}

    async def query(statement: object, parameters: object) -> Mock:
        result = Mock()
        if "model_relay_authority" in str(statement):
            result.mappings.return_value.one_or_none.return_value = retained
        else:
            assert "supervisor_lease" in str(statement)
            now = datetime.now(UTC)
            result.one_or_none.return_value = (now, now + timedelta(seconds=10))
        return result

    db.execute.side_effect = query

    @asynccontextmanager
    async def admission(*args: object) -> AsyncIterator[AsyncConnection]:
        assert args == (1, original.execution_owner_id, 1)
        yield db

    runtime.service = Mock(admission=admission)
    request = {
        **fields,
        "command_id": original.id,
        "connection": connection.model_dump(mode="json"),
    }
    monkeypatch.setattr(runtime, "latest", AsyncMock(return_value=request))
    async with runtime.metadata_guard(original.id, connection, 1, request_kind) as authority:
        assert authority.scope == original and authority.scope.id == original.id
    request["deadline"] = (datetime.now(UTC) + timedelta(seconds=60)).isoformat()
    with pytest.raises(store.ModelConflict, match="RELAY_AUTHORITY_DENIED"):
        async with runtime.metadata_guard(original.id, connection, 1, request_kind):
            pytest.fail("mutated original deadline must not grant authority")
    assert all(str(call.args[0]).startswith("SELECT") for call in db.execute.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", [False, True])
async def test_cancel_never_rewrites_historical_operation_without_serial(
    monkeypatch: pytest.MonkeyPatch, bound: bool
) -> None:
    import asyncio
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from omnis.modules.runs.model_test_contract import Operation, Snapshot
    from omnis.modules.runs.model_test_models import ModelTestControl
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest

    runtime = ApiKeyModelTest.__new__(ApiKeyModelTest)
    runtime.instance, runtime.closing, runtime.settlement_failed = str(uuid4()), False, False
    runtime.tasks = set()
    runtime.settings = Mock(owner=uuid4(), epoch=2, lock=asyncio.Lock())
    db = AsyncMock(spec=AsyncConnection)
    result = Mock()
    result.first.return_value = (1,) if bound else None
    db.execute.return_value = result

    @asynccontextmanager
    async def connection(*args: object) -> AsyncIterator[AsyncConnection]:
        yield db

    runtime.service = Mock(engine=Mock(connect=connection), admission=connection)
    runtime.service.owned_status = AsyncMock(return_value=Mock(generation=2))
    operation = Mock(spec=Operation, state_revision=1, state="PENDING", cancel_epoch=1)
    operation.operation_id, operation.config_snapshot_ref = str(uuid4()), Mock()
    monkeypatch.setattr(store, "replay", AsyncMock(return_value=(False, None)))
    monkeypatch.setattr(store, "operation", AsyncMock(return_value=operation))
    monkeypatch.setattr(store, "snapshot", AsyncMock(return_value=Mock(spec=Snapshot)))
    save, receipt = AsyncMock(), AsyncMock()
    monkeypatch.setattr(store, "save_operation", save)
    monkeypatch.setattr(store, "command", receipt)
    monkeypatch.setattr(runtime, "drain_models", AsyncMock(return_value=True))
    monkeypatch.setattr(runtime, "view", AsyncMock(return_value={}))
    request = ModelTestControl(
        op="model_test",
        action="cancel",
        operation_id=operation.operation_id,
        command_id=str(uuid4()),
        expected_state_revision=1,
    )
    if bound:
        assert await runtime.handle(request) == {}
        save.assert_awaited_once()
        receipt.assert_awaited_once()
    else:
        with pytest.raises(store.ModelConflict, match="CONTROL_UNAVAILABLE"):
            await runtime.handle(request)
        save.assert_not_awaited()
        receipt.assert_not_awaited()
