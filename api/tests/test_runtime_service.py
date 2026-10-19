"""Authority and quiescence boundary (DB records simulated, not PG proof)."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.records import InstanceRecord, LeaseRecord
from omnis.modules.instance.service import InstanceService


@pytest.mark.asyncio
async def test_runtime_authority_checks_current_db_lease_and_exact_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InstanceService(Mock(spec=AsyncEngine))
    assert hasattr(service, "runtime_authority"), "runtime authority grant missing"
    owner = uuid4()
    now = datetime.now(timezone.utc)
    instance = InstanceRecord(
        id=1,
        instance_id=uuid4(),
        generation=2,
        admission_open=False,
        shutdown_command_id=None,
        quiesced_generation=None,
        quiesced_at=None,
    )
    lease = LeaseRecord(id=1, owner=owner, epoch=3, expires_at=now + timedelta(seconds=0.8))
    connection = Mock(spec=AsyncConnection)
    result = Mock()
    result.scalar_one.return_value = now
    result.scalar_one_or_none.return_value = None
    connection.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        yield connection, instance, lease

    monkeypatch.setattr(service, "_locked", locked)
    before = time.monotonic_ns()
    grant = await service.runtime_authority(owner, 3, 2, inert_probe=True)
    assert grant.generation == 2 and grant.epoch == 3
    assert before < grant.deadline_ns <= time.monotonic_ns() + 800_000_000
    for generation, epoch, probe in ((True, 3, True), (2, True, True), (3, 3, True), (2, 3, False)):
        with pytest.raises(ControlConflict):
            await service.runtime_authority(owner, epoch, generation, inert_probe=probe)
    lease = LeaseRecord(id=1, owner=owner, epoch=3, expires_at=now + timedelta(seconds=5))
    full = await service.runtime_authority(owner, 3, 2, inert_probe=True)
    assert time.monotonic_ns() + 4_000_000_000 < full.deadline_ns
    assert full.deadline_ns <= time.monotonic_ns() + 4_500_000_000
    result.scalar_one.return_value = now + timedelta(seconds=6)
    with pytest.raises(ControlConflict):
        await service.runtime_authority(owner, 3, 2, inert_probe=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "startup",
    [
        "launch",
        None,
        True,
        False,
        "renew",
        {},
        {"protocol": "omnis-managed-admission-v6", "mode": "SEND"},
    ],
)
async def test_startup_lease_is_narrow_and_original_owner_must_survive_update(
    monkeypatch: pytest.MonkeyPatch,
    startup: object,
) -> None:
    service = InstanceService(Mock(spec=AsyncEngine))
    owner = uuid4()
    now = datetime.now(timezone.utc)
    instance = InstanceRecord(
        id=1,
        instance_id=uuid4(),
        generation=0,
        admission_open=False,
        shutdown_command_id=None,
        quiesced_generation=None,
        quiesced_at=None,
    )
    lease = LeaseRecord(id=1, owner=owner, epoch=1, expires_at=now + timedelta(seconds=5))
    connection = Mock(spec=AsyncConnection)
    updated = []
    expired = False

    async def execute(statement: object, params: object = None) -> Mock:
        result = Mock()
        if str(statement).startswith("UPDATE"):
            updated.append(params)
        result.scalar_one.return_value = now + timedelta(seconds=6 if expired and updated else 0)
        result.scalar_one_or_none.return_value = None
        return result

    connection.execute = AsyncMock(side_effect=execute)

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        yield connection, instance, lease

    monkeypatch.setattr(service, "_locked", locked)
    if startup is not None and startup != "launch":
        with pytest.raises((ControlConflict, ValueError)):
            await service.runtime_authority(owner, 1, 0, inert_probe=True, startup=startup)
        assert not updated
        return
    grant = await service.runtime_authority(owner, 1, 0, inert_probe=True, startup=startup)
    assert (
        0
        < grant.deadline_ns - time.monotonic_ns()
        <= (10_000_000_000 if startup else 4_500_000_000)
    )
    assert updated == ([{"expires": now + timedelta(seconds=11)}] if startup else [])
    updated.clear()
    with pytest.raises(ControlConflict):
        await service.runtime_authority(uuid4(), 1, 0, inert_probe=True, startup=startup)
    assert not updated
    if startup:
        expired = True
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.runtime_authority(owner, 1, 0, inert_probe=True, startup=startup)
        assert len(updated) == 1  # Original lease, not the just-written extension, is checked.


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [5, 6])
async def test_startup_authenticates_complete_retained_producer_before_lease_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: int
) -> None:
    from copy import deepcopy
    from hashlib import sha256
    from uuid import UUID

    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.runs.model_test import REQUESTED
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.modules.settings.catalog_schema import canonical
    from omnis.modules.tasks.managed_contract import mapping, sequence
    from test_model_test_prepare_source import prepared_source

    source, consumer, conn, manifest, authority = await prepared_source(tmp_path, monkeypatch)
    identity, settings = str(uuid4()), str(uuid4())
    command = NativeTaskCommand.model_validate(
        {
            **source.base,
            "owner_id": source.owner,
            "manifest_ref": manifest,
            "action": "model_test_prepare" if version == 5 else "model_test_start",
            "initialization_id": identity,
            "settings_operation_id": settings,
        }
    )
    context, _ = await consumer.prepare(
        conn,
        source.owner,
        manifest,
        identity,
        settings,
        {"status": "CONFIRMED", "selection": REQUESTED},
        authority,
        str(source.runtime.boot),
        command,
    )
    payload, _ = await consumer.dispatch(conn, source.owner, context, True)
    before_graph = canonical(source.graph)
    service = InstanceService(Mock(spec=AsyncEngine))
    now = datetime.now(timezone.utc)
    instance = InstanceRecord(
        id=1,
        instance_id=UUID(source.instance),
        generation=0,
        admission_open=False,
        shutdown_command_id=None,
        quiesced_generation=None,
        quiesced_at=None,
    )
    lease = LeaseRecord(id=1, owner=source.lease, epoch=1, expires_at=now + timedelta(seconds=5))
    updated: list[object] = []
    persisted = lease.expires_at

    async def execute(statement: object, params: object = None) -> Mock:
        nonlocal persisted
        if str(statement).startswith("UPDATE"):
            updated.append(params)
            expires = mapping(params)["expires"]
            assert isinstance(expires, datetime)
            persisted = expires
        result = Mock()
        result.scalar_one.return_value = now
        result.scalar_one_or_none.return_value = None
        return result

    connection = Mock(spec=AsyncConnection)
    connection.execute = AsyncMock(side_effect=execute)

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        yield connection, instance, lease

    monkeypatch.setattr(service, "_locked", locked)
    grant = await service.runtime_authority(source.lease, 1, 0, inert_probe=True, startup=payload)
    assert 9_000_000_000 < grant.deadline_ns - time.monotonic_ns() <= 10_000_000_000
    assert updated == [{"expires": now + timedelta(seconds=11)}]
    updated.clear()
    for case in (
        "boolean_epoch",
        "missing_authority",
        "missing_owner_id",
        "extra_context_field",
        "material_empty",
        "foreign_owner",
        "foreign_instance",
        "foreign_epoch",
        "foreign_generation",
        "extra_record",
        "resealed_record",
        "boolean_ref",
        "unretained_context",
    ):
        bad = deepcopy(payload)
        bad_context = mapping(bad["context"])
        c = mapping(bad_context["payload"])
        if case == "boolean_epoch":
            c["authority"] = {**authority, "epoch": True}
        elif case == "missing_authority":
            del c["authority"]
        elif case == "missing_owner_id":
            del c["owner_id"]
        elif case == "extra_context_field":
            c["untrusted"] = True
        elif case == "material_empty":
            bad["material"] = {}
        elif case.startswith("foreign_"):
            field = {"instance": "instance_id"}.get(case[8:], case[8:])
            c["authority"] = {
                **authority,
                field: str(uuid4()) if field in ("owner", "instance_id") else 2,
            }
        elif case == "extra_record":
            rows = sequence(bad["records"])
            bad["records"] = [*rows, deepcopy(rows[0])]
        elif case == "resealed_record":
            rows = sequence(bad["records"])
            item = mapping(rows[0])
            item["payload"] = {**mapping(item["payload"]), "untrusted": True}
            item["digest"] = sha256(
                canonical({k: v for k, v in item.items() if k != "digest"})
            ).hexdigest()
            bad["records"] = [item, *rows[1:]]
            c["managed_run_ref"] = {**mapping(c["managed_run_ref"]), "digest": item["digest"]}
        elif case == "boolean_ref":
            c["managed_run_ref"] = {**mapping(c["managed_run_ref"]), "revision": True}
        elif case == "unretained_context":
            bad_context["id"] = str(uuid4())
        bad_context["payload"] = c
        bad_context["digest"] = sha256(
            canonical({k: v for k, v in bad_context.items() if k != "digest"})
        ).hexdigest()
        bad["context"] = bad_context
        before_expiry = persisted
        with pytest.raises((ControlConflict, CatalogError), match="."):
            await service.runtime_authority(source.lease, 1, 0, inert_probe=True, startup=bad)
        assert updated == [], case
        assert persisted == before_expiry, case
        assert canonical(source.graph) == before_graph, case
    receipt = next(
        r
        for r in source.graph
        if r["kind"] == "contract-input-command" and mapping(r["payload"])["command_id"] == identity
    )
    source.graph.remove(receipt)
    with pytest.raises(CatalogError):
        await service.runtime_authority(source.lease, 1, 0, inert_probe=True, startup=payload)
    assert updated == [] and persisted == before_expiry
    source.graph.append(receipt)
    from omnis.supervisor.runtime_client import RuntimeClient

    exchange = AsyncMock(return_value={"managed": {}})
    monkeypatch.setattr(source.runtime, "_exchange", exchange)
    # The unchanged producer also passes the real client-to-service admission.
    await RuntimeClient.managed(
        source.runtime, service, source.lease, "task_model_initialize", payload
    )
    exchange.assert_awaited_once()
    assert len(updated) == 1


@pytest.mark.asyncio
async def test_quiescence_requires_observed_runtime_drain_before_db_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "runtime_drain" in __import__("inspect").signature(InstanceService).parameters, (
        "drain guard missing"
    )
    drain = AsyncMock(return_value=False)
    service = InstanceService(Mock(spec=AsyncEngine), runtime_drain=drain)
    owner = uuid4()
    now = datetime.now(timezone.utc)
    instance = InstanceRecord(
        id=1,
        instance_id=uuid4(),
        generation=2,
        admission_open=False,
        shutdown_command_id=uuid4(),
        quiesced_generation=None,
        quiesced_at=None,
    )
    lease = LeaseRecord(id=1, owner=owner, epoch=1, expires_at=now + timedelta(seconds=5))
    connection = Mock(spec=AsyncConnection)
    result = Mock()
    result.scalar_one.return_value = now
    result.scalar_one_or_none.return_value = None
    connection.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        yield connection, instance, lease

    monkeypatch.setattr(service, "_locked", locked)
    with pytest.raises(ControlConflict):
        await service.quiesce(owner, 1)
    assert not any(
        "UPDATE instance_control" in str(call.args[0]) for call in connection.execute.call_args_list
    )
    drain.return_value = True
    await service.quiesce(owner, 1)
    assert any(
        "UPDATE instance_control" in str(call.args[0]) for call in connection.execute.call_args_list
    )
