import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine


@pytest.mark.asyncio
async def test_startup_lease_is_bounded_preserved_and_cannot_resurrect_pg(
    migrated_database_url: URL,
) -> None:
    import time

    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        ordinary = await service.runtime_authority(owner, epoch, 0, inert_probe=True)
        assert 0 < ordinary.deadline_ns - time.monotonic_ns() <= 4_500_000_000
        for startup in (True, "renew"):
            with pytest.raises(ControlConflict):
                await service.runtime_authority(owner, epoch, 0, inert_probe=True, startup=startup)
        with pytest.raises(ControlConflict):
            await service.runtime_authority(uuid4(), epoch, 0, inert_probe=True, startup="launch")
        grant = await service.runtime_authority(owner, epoch, 0, inert_probe=True, startup="launch")
        assert 9_000_000_000 < grant.deadline_ns - time.monotonic_ns() <= 10_000_000_000
        async with engine.connect() as conn:
            expiry = (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one()
            remaining = (
                await conn.execute(
                    text(
                        "SELECT EXTRACT(EPOCH FROM expires_at-clock_timestamp()) FROM supervisor_lease WHERE id=1"
                    )
                )
            ).scalar_one()
            assert 10 < remaining <= 11
        await service.heartbeat(owner, epoch)
        async with engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one() == expiry
        ordinary = await service.runtime_authority(owner, epoch, 0, inert_probe=True)
        assert 0 < ordinary.deadline_ns - time.monotonic_ns() <= 4_500_000_000
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at=clock_timestamp()+interval '5 seconds' WHERE id=1"
                )
            )
        await service.heartbeat(owner, epoch)
        async with engine.connect() as conn:
            assert (
                await conn.execute(
                    text(
                        "SELECT EXTRACT(EPOCH FROM expires_at-clock_timestamp()) FROM supervisor_lease WHERE id=1"
                    )
                )
            ).scalar_one() <= 5
        # Actual blocking UPDATE crosses the original expiry; the extension must roll back.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE FUNCTION delay_lease_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(0.3); RETURN NEW; END $$"
                )
            )
            await conn.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at=clock_timestamp()+interval '0.2 seconds' WHERE id=1"
                )
            )
            await conn.execute(
                text(
                    "CREATE TRIGGER delay_lease BEFORE UPDATE ON supervisor_lease FOR EACH ROW EXECUTE FUNCTION delay_lease_update()"
                )
            )
            original = (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one()
        before_update = time.monotonic()
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.runtime_authority(owner, epoch, 0, inert_probe=True, startup="launch")
        assert time.monotonic() - before_update >= 0.3
        async with engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one() == original
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.heartbeat(owner, epoch)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_shutdown_serializes_with_real_admission_and_requires_explicit_restart(
    migrated_database_url: URL,
) -> None:
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        startup = uuid4()
        generation = await service.open(startup, 0, owner, epoch)
        assert generation == 1
        assert await service.open(startup, 0, owner, epoch) == generation
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE inert_marker (generation bigint NOT NULL)"))
        # This is only a fully transactional inert marker, never an external effect.
        entered = asyncio.Event()
        finish = asyncio.Event()

        async def admitted() -> None:
            async with service.admission(generation, owner, epoch) as connection:
                entered.set()
                await finish.wait()
                await connection.execute(
                    text("INSERT INTO inert_marker VALUES (:generation)"),
                    {"generation": generation},
                )

        work = asyncio.create_task(admitted())
        await entered.wait()
        stop_id = uuid4()
        stopping = asyncio.create_task(service.shutdown(stop_id, generation, owner, epoch))
        await asyncio.sleep(0.05)
        assert not stopping.done()
        finish.set()
        await work
        closed_generation = await stopping
        assert closed_generation == 2
        assert await service.shutdown(stop_id, generation, owner, epoch) == closed_generation
        with pytest.raises(ControlConflict, match="INSTANCE_SHUTTING_DOWN"):
            async with service.admission(closed_generation, owner, epoch):
                pytest.fail("closed instance admitted work")
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.open(uuid4(), closed_generation, owner, epoch)
        await service.quiesce(owner, epoch)
        await service.finalize(uuid4(), closed_generation, owner, epoch)
        with pytest.raises(ControlConflict, match="RESTART_REQUIRED"):
            await service.open(uuid4(), closed_generation, owner, epoch)
        await service.release(owner, epoch)
        new_owner = uuid4()
        new_epoch = await service.acquire(new_owner)
        assert new_epoch > epoch
        assert (await service.status()).admission_open is False
        reopened = await service.open(uuid4(), closed_generation, new_owner, new_epoch)
        assert reopened == 3
        # A historical retry never reopens, shuts down or changes a new generation.
        assert (
            await service.shutdown(stop_id, generation, new_owner, new_epoch) == closed_generation
        )
        assert (await service.status()).generation == reopened
        with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
            await service.shutdown(stop_id, reopened, new_owner, new_epoch)
        with pytest.raises(ControlConflict, match="GENERATION_CONFLICT"):
            await service.shutdown(uuid4(), generation, new_owner, new_epoch)
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT generation FROM inert_marker"))
            ).scalars().all() == [generation]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_owner_is_fenced_and_takeover_never_reopens(
    migrated_database_url: URL,
) -> None:
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        with pytest.raises(ControlConflict, match="SUPERVISOR_OWNED"):
            await service.acquire(uuid4())
        generation = await service.open(uuid4(), 0, owner, epoch)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            async with service.admission(generation, owner, epoch):
                pytest.fail("expired owner admitted work")
        replacement = uuid4()
        next_epoch = await service.acquire(replacement)
        status = await service.status()
        assert status.admission_open is False and status.shutdown_command_id is not None
        assert status.generation > generation and next_epoch > epoch
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.heartbeat(owner, epoch)
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.quiesce(owner, epoch)
        await service.quiesce(replacement, next_epoch)
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.open(uuid4(), status.generation, replacement, next_epoch)
    finally:
        await engine.dispose()
