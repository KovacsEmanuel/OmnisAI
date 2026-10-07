"""Real PG case transition guard: expiry and overlapping lock ownership, no mocks."""

import asyncio
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from conftest import connect_test_database
from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlCode, ControlConflict
from omnis.modules.instance.service import InstanceService


@pytest.mark.asyncio
async def test_case_transition_fences_expiry_and_observed_postgres_lock_overlap(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        status = await service.owned_status(owner, epoch)
        assert hasattr(service, "case_transition"), "typed case transition guard missing"
        before = None
        async with engine.connect() as connection:
            before = (
                await connection.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one()
        async with service.case_transition(
            owner, epoch, status.generation, status.instance_id, restoring=True
        ) as guard:
            assert guard.deadline_ns > time.monotonic_ns()
            contender = asyncio.create_task(service.open(uuid4(), status.generation, owner, epoch))
            try:
                with connect_test_database(migrated_database_url, autocommit=True) as observer:
                    until = time.monotonic() + 1
                    blocked = False
                    while time.monotonic() < until:
                        row = observer.execute(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE datname=current_database() AND query LIKE "
                            "'SELECT * FROM instance_control%%' AND cardinality(pg_blocking_pids(pid))>0)"
                        ).fetchone()
                        assert row is not None
                        blocked = row[0] is True
                        if blocked:
                            break
                        await asyncio.sleep(0.02)
                    assert blocked, "case guard must visibly block OPEN in pg_blocking_pids"
                await guard.verify()
            finally:
                contender.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await contender
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one() == before
        with connect_test_database(migrated_database_url, autocommit=True) as observer:
            observer.execute(
                "UPDATE supervisor_lease SET expires_at=clock_timestamp() "
                "+ interval '150 milliseconds' WHERE id=1"
            )
        with pytest.raises(ControlConflict) as caught:
            async with service.case_transition(
                owner, epoch, status.generation, status.instance_id, restoring=True
            ) as guard:
                await asyncio.sleep(0.22)
                await guard.verify()
        assert caught.value.code == ControlCode.LEASE_LOST
        with pytest.raises(ControlConflict) as caught:
            async with service.case_transition(
                owner, epoch, status.generation, status.instance_id, restoring=True
            ):
                pytest.fail("expired owner may not enter transition")
        assert caught.value.code == ControlCode.LEASE_LOST
        observed = await service.status()
        assert not observed.admission_open and observed.generation == status.generation
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_case_slot_and_stock_engagement_service_use_the_same_pg_authority(
    migrated_database_url: URL,
    tmp_path: Path,
) -> None:
    from omnis.modules.engagements.schemas import EngagementDraft
    from omnis.modules.engagements.service import EngagementService
    from omnis.supervisor.case_slot import CaseSlot
    from test_case_slot import private_write, provision, snapshot
    from test_engagements import draft

    assert isinstance(tmp_path, Path)
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    engagements = EngagementService(engine)
    slot: CaseSlot | None = None
    try:
        a = await engagements.create(EngagementDraft.model_validate(draft()))
        b = await engagements.create(EngagementDraft.model_validate(draft()))
        owner = uuid4()
        epoch = await service.acquire(owner)
        status = await service.owned_status(owner, epoch)
        root = tmp_path / "slot"
        provision(root, status.instance_id)
        for view, expected in ((a, None), (b, None), (a, b"A")):
            assert (await engagements.read(view.engagement_id)).engagement_id == view.engagement_id
            slot = CaseSlot(
                root,
                view.engagement_id,
                status.instance_id,
                owner,
                epoch,
                status.generation,
                str(uuid4()),
            )
            await slot.prepare(service)
            if expected is not None:
                assert (root / "active/state.db").read_bytes() == expected
            else:
                assert not (root / "active/state.db").exists()
            await slot.observe(snapshot(slot))
            private_write(root / "active/state.db", b"A" if view is a else b"B")
            await slot.archive(service, status.generation, snapshot(slot, "STOPPED"))
            await slot.close()
        await service.release(owner, epoch)
    finally:
        if slot is not None:
            await slot.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_pg_owner_cannot_start_case_archive_moves(
    migrated_database_url: URL,
    tmp_path: Path,
) -> None:
    from omnis.supervisor.case_slot import CaseSlot
    from test_case_slot import private_write, provision, snapshot

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    slot: CaseSlot | None = None
    try:
        owner = uuid4()
        epoch = await service.acquire(owner)
        status = await service.owned_status(owner, epoch)
        root = tmp_path / "slot"
        provision(root, status.instance_id)
        slot = CaseSlot(
            root, uuid4(), status.instance_id, owner, epoch, status.generation, str(uuid4())
        )
        await slot.prepare(service)
        await slot.observe(snapshot(slot))
        private_write(root / "active/state.db", b"owned-case")
        with connect_test_database(migrated_database_url, autocommit=True) as clock:
            clock.execute(
                "UPDATE supervisor_lease SET expires_at=clock_timestamp() "
                "- interval '1 second' WHERE id=1"
            )
        with pytest.raises(ControlConflict) as caught:
            await slot.archive(service, status.generation, snapshot(slot, "STOPPED"))
        assert caught.value.code == ControlCode.LEASE_LOST
        assert (root / "active/state.db").read_bytes() == b"owned-case"
        assert not (slot.archive_root / "receipt.json").exists()
    finally:
        if slot is not None:
            await slot.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_lease_expiry_during_real_pg_row_wait_denies_transition_entry(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        status = await service.owned_status(owner, epoch)
        with connect_test_database(migrated_database_url, autocommit=True) as clock:
            clock.execute(
                "UPDATE supervisor_lease SET expires_at=clock_timestamp() "
                "+ interval '250 milliseconds' WHERE id=1"
            )
        with connect_test_database(migrated_database_url) as blocker:
            blocker.execute("SELECT * FROM instance_control WHERE id=1 FOR UPDATE")

            async def transition() -> None:
                async with service.case_transition(
                    owner, epoch, status.generation, status.instance_id, restoring=True
                ):
                    pytest.fail("expired lease entered filesystem transition")

            pending = asyncio.create_task(transition())
            try:
                with connect_test_database(migrated_database_url, autocommit=True) as observer:
                    until = time.monotonic() + 1
                    blocked = False
                    while time.monotonic() < until:
                        row = observer.execute(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE datname=current_database() AND "
                            "cardinality(pg_blocking_pids(pid))>0)"
                        ).fetchone()
                        assert row is not None
                        blocked = row[0] is True
                        if blocked:
                            break
                        await asyncio.sleep(0.02)
                    assert blocked, "real PG lock wait was not observed"
                    await asyncio.sleep(0.3)
                blocker.commit()
                with pytest.raises(ControlConflict) as caught:
                    await pending
                assert caught.value.code == ControlCode.LEASE_LOST
            finally:
                if not pending.done():
                    pending.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await pending
    finally:
        await engine.dispose()
