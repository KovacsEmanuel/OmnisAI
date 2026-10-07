"""Authority and quiescence boundary (DB records simulated, not PG proof)."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
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
