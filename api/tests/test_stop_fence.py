"""Real PostgreSQL checks for the durable, non-expiring Stop admission fence."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from conftest import connect_test_database
from omnis.core.db import ReadinessReason, database_engine, readiness_reason
from omnis.core.persistence import read_integer
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.records import InstanceRecord, LeaseRecord
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import ArmStopCommand


async def stopped_instance(service: InstanceService) -> tuple[UUID, UUID, UUID, UUID, int, int]:
    owner, command, finalized = uuid4(), uuid4(), uuid4()
    instance_id = (await service.status()).instance_id
    epoch = await service.acquire(owner)
    generation = await service.open(uuid4(), 0, owner, epoch)
    stopped = await service.shutdown(command, generation, owner, epoch)
    await service.quiesce(owner, epoch)
    await service.finalize(finalized, stopped, owner, epoch)
    return instance_id, owner, command, finalized, epoch, stopped


async def db_snapshot(engine: AsyncEngine) -> tuple[object, ...]:
    async with engine.connect() as connection:
        rows: list[object] = []
        for table in (
            "instance_control",
            "supervisor_lease",
            "instance_stop_fence",
            "instance_command",
        ):
            rows.append(tuple((await connection.execute(text(f"SELECT * FROM {table}"))).all()))
        return tuple(rows)


@pytest.mark.asyncio
async def test_arm_stop_readback_binds_issuer_and_exact_closed_state(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, generation = await stopped_instance(service)
        request = ArmStopCommand.model_validate(
            {
                "op": "arm_stop",
                "instance_id": instance,
                "command_id": command,
                "finalize_command_id": finalized,
                "generation": generation,
                "owner_epoch": epoch,
                "daemon_id": "daemon-a",
                "inventory": {"db": "a" * 64},
            }
        )
        await service.arm_stop(
            command,
            finalized,
            generation,
            instance,
            owner,
            epoch,
            request.daemon_id,
            request.inventory,
        )
        grant = await service.stop_grant_readback(request, owner)
        assert grant == {
            **request.model_dump(mode="json", exclude={"op"}),
            "owner_uuid": str(owner),
            "version": 1,
            "state": "STOP_PENDING",
        }
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE instance_stop_fence SET state = 'STOP_UNCERTAIN'")
            )
        assert (await service.stop_grant_readback(request, owner))["state"] == "STOP_UNCERTAIN"
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict):
            await service.stop_grant_readback(request, uuid4())
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


class PausedService(InstanceService):
    """Pause after both real row locks; do not replace any product decision."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine)
        self.entered = asyncio.Event()
        self.proceed = asyncio.Event()
        self.backend_pid: int | None = None

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        async with super()._locked() as locked:
            self.backend_pid = read_integer(
                (await locked[0].execute(text("SELECT pg_backend_pid()"))).scalar_one()
            )
            self.entered.set()
            await asyncio.wait_for(self.proceed.wait(), 3)
            yield locked


async def observe_blocked_on(engine: AsyncEngine, first: PausedService) -> None:
    await asyncio.wait_for(first.entered.wait(), 2)
    assert first.backend_pid is not None
    async with asyncio.timeout(1):
        while True:
            async with engine.connect() as reader:
                waiting = (
                    await reader.execute(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                            "AND :blocker = ANY(pg_blocking_pids(pid))"
                        ),
                        {"blocker": first.backend_pid},
                    )
                ).scalar_one()
            if waiting == 1:
                return
            await asyncio.sleep(0.01)


@pytest.mark.parametrize("contender", ["acquire", "open"])
@pytest.mark.asyncio
async def test_arm_commits_before_waiting_acquire_or_open_replay(
    migrated_database_url: URL, contender: str
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service, first = InstanceService(engine), PausedService(engine)
    tasks: list[asyncio.Task[object]] = []
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        async with engine.connect() as reader:
            opened = (
                await reader.execute(
                    text("SELECT command_id FROM instance_command WHERE kind='OPEN'")
                )
            ).scalar_one()
        assert isinstance(opened, UUID)
        before = await db_snapshot(engine)
        arming = asyncio.create_task(
            first.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
            )
        )
        tasks.append(arming)
        await asyncio.wait_for(first.entered.wait(), 2)
        waiting = asyncio.create_task(
            service.acquire(uuid4())
            if contender == "acquire"
            else service.open(opened, 0, owner, epoch)
        )
        tasks.append(waiting)
        await observe_blocked_on(engine, first)
        assert not arming.done() and not waiting.done()
        first.proceed.set()
        assert await asyncio.wait_for(arming, 2) == "STOP_PENDING"
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await asyncio.wait_for(waiting, 2)
        after = await db_snapshot(engine)
        assert after[:2] == before[:2] and after[3] == before[3]
        assert before[2] == ()
        assert isinstance(after[2], tuple) and len(after[2]) == 1
    finally:
        first.proceed.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 3)
        await engine.dispose()


@pytest.mark.parametrize("winner", ["acquire", "open"])
@pytest.mark.asyncio
async def test_new_owner_commits_before_waiting_old_stop_arm(
    migrated_database_url: URL, winner: str
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service, first = InstanceService(engine), PausedService(engine)
    tasks: list[asyncio.Task[object]] = []
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        await service.release(owner, epoch)
        successor, reopened_command = uuid4(), uuid4()
        if winner == "open":
            assert await service.acquire(successor) == epoch + 1
        winning = asyncio.create_task(
            first.acquire(successor)
            if winner == "acquire"
            else first.open(reopened_command, stopped, successor, epoch + 1)
        )
        tasks.append(winning)
        await asyncio.wait_for(first.entered.wait(), 2)
        arming = asyncio.create_task(
            service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
            )
        )
        tasks.append(arming)
        await observe_blocked_on(engine, first)
        assert not winning.done() and not arming.done()
        first.proceed.set()
        assert await asyncio.wait_for(winning, 2) == (
            epoch + 1 if winner == "acquire" else stopped + 1
        )
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await asyncio.wait_for(arming, 2)
        async with engine.connect() as reader:
            assert (
                await reader.execute(text("SELECT count(*) FROM instance_stop_fence"))
            ).scalar_one() == 0
            assert (
                await reader.execute(text("SELECT owner, epoch FROM supervisor_lease WHERE id=1"))
            ).one() == (successor, epoch + 1)
        current = await service.status()
        assert current.generation == stopped + (winner == "open")
        assert current.admission_open is (winner == "open")
    finally:
        first.proceed.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 3)
        await engine.dispose()


@pytest.mark.parametrize("state", ["STOP_PENDING", "STOP_UNCERTAIN"])
@pytest.mark.parametrize("departure", ["expiry", "release"])
@pytest.mark.asyncio
async def test_fence_blocks_every_acquire_and_open_after_owner_departure(
    migrated_database_url: URL, state: str, departure: str
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        async with engine.connect() as reader:
            opened = (
                await reader.execute(
                    text("SELECT command_id FROM instance_command WHERE kind='OPEN'")
                )
            ).scalar_one()
        assert isinstance(opened, UUID)
        await service.arm_stop(
            command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
        )
        # State injection tests both consumers, not the future ACK-loss producer.
        async with engine.begin() as writer:
            await writer.execute(
                text("UPDATE instance_stop_fence SET state = :state WHERE id=1"), {"state": state}
            )
        if departure == "release":
            await service.release(owner, epoch)
        else:
            async with engine.begin() as writer:
                await writer.execute(
                    text(
                        "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                    )
                )
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.acquire(uuid4())
        assert await db_snapshot(engine) == before
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.open(uuid4(), stopped, owner, epoch)
        assert await db_snapshot(engine) == before
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.open(opened, 0, owner, epoch)
        assert await db_snapshot(engine) == before
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.arm_stop(
                command, finalized, stopped, instance, uuid4(), epoch, "daemon-a", {"db": "a" * 64}
            )
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


def test_migration_creates_empty_persistent_stop_fence(migrated_database_url: URL) -> None:
    with connect_test_database(migrated_database_url) as connection:
        assert connection.execute(
            "SELECT to_regclass('public.instance_stop_fence')"
        ).fetchone() == ("instance_stop_fence",)
        assert connection.execute("SELECT count(*) FROM instance_stop_fence").fetchone() == (0,)
        columns = connection.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid = 'instance_stop_fence'::regclass "
            "AND attnum > 0 AND NOT attisdropped"
        ).fetchall()
        assert {name for (name,) in columns} == {
            "id",
            "instance_id",
            "command_id",
            "finalize_command_id",
            "generation",
            "owner_epoch",
            "daemon_id",
            "inventory",
            "state",
        }


@pytest.mark.asyncio
async def test_readiness_rejects_a_fence_without_its_state_constraint(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        assert await readiness_reason(engine) is None
        with connect_test_database(migrated_database_url) as connection:
            connection.execute(
                "ALTER TABLE instance_stop_fence DROP CONSTRAINT instance_stop_fence_state_check"
            )
        assert await readiness_reason(engine) == ReadinessReason.SCHEMA_INCOMPATIBLE
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_arm_stop_persists_exact_finalized_owner_and_inventory(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner, command, finalized = uuid4(), uuid4(), uuid4()
    inventory: dict[str, object] = {
        "containers": {"db": "a" * 64, "api": "b" * 64, "supervisor": "c" * 64},
        "network": "d" * 64,
        "forwarder": {"pid": 12345, "start_ticks": 67890},
    }
    try:
        instance_id = (await service.status()).instance_id
        epoch = await service.acquire(owner)
        generation = await service.open(uuid4(), 0, owner, epoch)
        stopped = await service.shutdown(command, generation, owner, epoch)
        await service.quiesce(owner, epoch)
        await service.finalize(finalized, stopped, owner, epoch)
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance_id, owner, epoch, "daemon-a", inventory
            )
            == "STOP_PENDING"
        )
        async with engine.connect() as connection:
            row = (
                (await connection.execute(text("SELECT * FROM instance_stop_fence WHERE id = 1")))
                .mappings()
                .one()
            )
            assert dict(row) == {
                "id": 1,
                "instance_id": instance_id,
                "command_id": command,
                "finalize_command_id": finalized,
                "generation": stopped,
                "owner_epoch": epoch,
                "daemon_id": "daemon-a",
                "inventory": inventory,
                "state": "STOP_PENDING",
            }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_refuses_expired_lease_takeover_before_any_db_change(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
            )
            == "STOP_PENDING"
        )
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.acquire(uuid4())
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_refuses_open_before_receipt_replay_or_lease_checks(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        await service.arm_stop(
            command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
        )
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.open(uuid4(), stopped, owner, epoch)
        async with engine.connect() as connection:
            opened = (
                await connection.execute(
                    text(
                        "SELECT command_id, expected_generation FROM instance_command WHERE kind = 'OPEN'"
                    )
                )
            ).one()
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.open(opened.command_id, opened.expected_generation, owner, epoch)
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_takeover_and_open_committed_first_make_old_epoch_arm_refuse(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        replacement = uuid4()
        next_epoch = await service.acquire(replacement)
        assert next_epoch == epoch + 1
        assert await service.open(uuid4(), stopped, replacement, next_epoch) == stopped + 1
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
            )
        assert await db_snapshot(engine) == before
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM instance_stop_fence"))
            ).scalar_one() == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_arm_without_finalize_refuses_and_keeps_database_unchanged(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner, command, finalized = uuid4(), uuid4(), uuid4()
    try:
        instance = (await service.status()).instance_id
        epoch = await service.acquire(owner)
        generation = await service.open(uuid4(), 0, owner, epoch)
        stopped = await service.shutdown(command, generation, owner, epoch)
        await service.quiesce(owner, epoch)
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
            )
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_exact_replay_is_idempotent_but_any_identity_change_conflicts(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        inventory: dict[str, object] = {"db": "a" * 64, "network": "b" * 64}
        args: tuple[UUID, UUID, int, UUID, UUID, int, str, dict[str, object]] = (
            command,
            finalized,
            stopped,
            instance,
            owner,
            epoch,
            "daemon-a",
            inventory,
        )
        assert await service.arm_stop(*args) == "STOP_PENDING"
        before = await db_snapshot(engine)
        assert await service.arm_stop(*args) == "STOP_PENDING"
        assert await db_snapshot(engine) == before
        changed_cases: list[tuple[UUID, UUID, int, UUID, UUID, int, str, dict[str, object]]] = [
            (uuid4(), finalized, stopped, instance, owner, epoch, "daemon-a", inventory),
            (command, uuid4(), stopped, instance, owner, epoch, "daemon-a", inventory),
            (command, finalized, stopped + 1, instance, owner, epoch, "daemon-a", inventory),
            (command, finalized, stopped, uuid4(), owner, epoch, "daemon-a", inventory),
            (command, finalized, stopped, instance, owner, epoch, "daemon-b", inventory),
            (command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "c" * 64}),
        ]
        for changed in changed_cases:
            with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
                await service.arm_stop(*changed)
            assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_release_cannot_clear_pending_or_permit_epoch_increment(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        await service.arm_stop(
            command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
        )
        await service.release(owner, epoch)
        before = await db_snapshot(engine)
        async with engine.connect() as connection:
            row = (
                await connection.execute(text("SELECT owner, epoch FROM supervisor_lease"))
            ).one()
            assert row == (None, epoch)
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.acquire(uuid4())
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.open(uuid4(), stopped, owner, epoch)
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_uncertain_fence_survives_lost_ack_and_refuses_even_a_forced_successor_open(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        inventory: dict[str, object] = {"db": "a" * 64}
        await service.arm_stop(
            command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
        )
        # Fault injection only: the future Stop owner, not this slice, will mark
        # an unacknowledged effect UNCERTAIN. Neither state has any TTL release.
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE instance_stop_fence SET state = 'STOP_UNCERTAIN' WHERE id = 1")
            )
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
            )
            == "STOP_UNCERTAIN"
        )
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.acquire(uuid4())
        assert await db_snapshot(engine) == before
        successor = uuid4()
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET owner = :owner, epoch = :epoch, "
                    "expires_at = clock_timestamp() + interval '5 seconds' WHERE id = 1"
                ),
                {"owner": successor, "epoch": epoch + 1},
            )
        before_open = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
            await service.open(uuid4(), stopped, successor, epoch + 1)
        assert await db_snapshot(engine) == before_open
    finally:
        await engine.dispose()


@pytest.mark.parametrize("state", ["STOP_PENDING", "STOP_UNCERTAIN"])
@pytest.mark.asyncio
async def test_stop_replay_rechecks_owner_after_real_fence_select_wait(
    migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    checked = asyncio.Event()
    original = service._require_owner
    task: asyncio.Task[str] | None = None

    async def observed(
        connection: AsyncConnection, lease: LeaseRecord, owner: UUID, epoch: int
    ) -> None:
        await original(connection, lease, owner, epoch)
        # Only this adversarial fixture extends the SQL wait beyond the lease;
        # the product still has its ordinary two-second statement timeout.
        await connection.execute(text("SET LOCAL statement_timeout = 10000"))
        checked.set()

    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        inventory: dict[str, object] = {"db": "a" * 64}
        await service.arm_stop(
            command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
        )
        async with engine.begin() as writer:
            await writer.execute(
                text("UPDATE instance_stop_fence SET state = :state WHERE id = 1"),
                {"state": state},
            )
        before = await db_snapshot(engine)
        monkeypatch.setattr(service, "_require_owner", observed)
        async with engine.begin() as blocker:
            await blocker.execute(text("LOCK TABLE instance_stop_fence IN ACCESS EXCLUSIVE MODE"))
            blocker_pid = read_integer(
                (await blocker.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            )
            task = asyncio.create_task(
                service.arm_stop(
                    command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
                )
            )
            await asyncio.wait_for(checked.wait(), 2)
            async with asyncio.timeout(1):
                while True:
                    async with engine.connect() as reader:
                        waiting = (
                            await reader.execute(
                                text(
                                    "SELECT count(*) FROM pg_stat_activity "
                                    "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                                    "AND :blocker = ANY(pg_blocking_pids(pid))"
                                ),
                                {"blocker": blocker_pid},
                            )
                        ).scalar_one()
                    if waiting == 1:
                        break
                    await asyncio.sleep(0.01)
            async with asyncio.timeout(8):
                while True:
                    async with engine.connect() as reader:
                        expired = (
                            await reader.execute(
                                text(
                                    "SELECT expires_at <= clock_timestamp() "
                                    "FROM supervisor_lease WHERE id = 1"
                                )
                            )
                        ).scalar_one()
                    if expired is True:
                        break
                    await asyncio.sleep(0.1)
            assert not task.done(), "the replay must still wait on the real fence SELECT"
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await asyncio.wait_for(task, 2)
        assert await db_snapshot(engine) == before
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3)
        await engine.dispose()


@pytest.mark.parametrize("state", ["STOP_PENDING", "STOP_UNCERTAIN"])
@pytest.mark.parametrize(
    ("generation", "epoch"),
    [
        (True, 1),
        (1.0, 1),
        (1, True),
        (1, 1.0),
        (0, 1),
        (-1, 1),
        (1, 0),
        (1, -1),
        (2**63, 1),
        (1, 2**63),
    ],
)
@pytest.mark.asyncio
async def test_replay_requires_exact_positive_bigint_authority(
    migrated_database_url: URL, state: str, generation: int, epoch: int
) -> None:
    # Pytest supplies deliberately invalid runtime values to the typed service
    # boundary; bool/float equality must never turn them into the original grant.
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner, command, finalized = uuid4(), uuid4(), uuid4()
    inventory: dict[str, object] = {"db": "a" * 64}
    try:
        instance = (await service.status()).instance_id
        owned_epoch = await service.acquire(owner)
        stopped = await service.shutdown(command, 0, owner, owned_epoch)
        assert (stopped, owned_epoch) == (1, 1)
        await service.quiesce(owner, owned_epoch)
        await service.finalize(finalized, stopped, owner, owned_epoch)
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance, owner, owned_epoch, "daemon-a", inventory
            )
            == "STOP_PENDING"
        )
        if state == "STOP_UNCERTAIN":
            # Consumer-state control only; not a claim to produce a lost Docker ACK.
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE instance_stop_fence SET state = 'STOP_UNCERTAIN' WHERE id = 1")
                )
        before = await db_snapshot(engine)
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance, owner, owned_epoch, "daemon-a", inventory
            )
            == state
        )
        with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
            await service.arm_stop(
                command, finalized, generation, instance, owner, epoch, "daemon-a", inventory
            )
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_replay_distinguishes_boolean_from_numeric_inventory_identity(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        await service.arm_stop(
            command, finalized, stopped, instance, owner, epoch, "daemon-a", {"pid": True}
        )
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"pid": 1}
            )
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.parametrize("value", [1.0, 1e20, -0.0, float("nan"), float("inf")])
@pytest.mark.asyncio
async def test_stop_inventory_refuses_float_identity_before_arm(
    migrated_database_url: URL, value: float
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
            await service.arm_stop(
                command,
                finalized,
                stopped,
                instance,
                owner,
                epoch,
                "daemon-a",
                {"forwarder": {"identity": [value]}},
            )
        assert await db_snapshot(engine) == before
        # The same boundary accepts and replays exact integral identity, not a
        # serialized float that PostgreSQL JSONB may normalize to another type.
        inventory: dict[str, object] = {"forwarder": {"identity": [100000000000000000000]}}
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
            )
            == "STOP_PENDING"
        )
        armed = await db_snapshot(engine)
        assert (
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
            )
            == "STOP_PENDING"
        )
        assert await db_snapshot(engine) == armed
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_inventory_with_coercible_nested_keys_cannot_be_armed(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        before = await db_snapshot(engine)
        inventory: dict[str, object] = {"containers": {1: "a" * 64}}
        with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", inventory
            )
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stop_grant_rejects_finalize_from_different_owner_epoch(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        original = uuid4()
        instance = (await service.status()).instance_id
        epoch = await service.acquire(original)
        generation = await service.open(uuid4(), 0, original, epoch)
        command = uuid4()
        stopped = await service.shutdown(command, generation, original, epoch)
        await service.quiesce(original, epoch)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        successor = uuid4()
        next_epoch = await service.acquire(successor)
        finalized = uuid4()
        await service.finalize(finalized, stopped, successor, next_epoch)
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.arm_stop(
                command,
                finalized,
                stopped,
                instance,
                successor,
                next_epoch,
                "daemon-a",
                {"db": "a" * 64},
            )
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expiry_during_insert_rolls_back_stop_grant_before_commit(
    migrated_database_url: URL,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        instance, owner, command, finalized, epoch, stopped = await stopped_instance(service)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE SEQUENCE fence_insert_seen"))
            await connection.execute(
                text(
                    "CREATE FUNCTION delay_fence_insert() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN PERFORM nextval('fence_insert_seen'); PERFORM pg_sleep(1.1); "
                    "RETURN NEW; END $$"
                )
            )
            await connection.execute(
                text(
                    "CREATE TRIGGER delay_fence BEFORE INSERT ON instance_stop_fence "
                    "FOR EACH ROW EXECUTE FUNCTION delay_fence_insert()"
                )
            )
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() + interval '700 milliseconds'"
                )
            )
        before = await db_snapshot(engine)
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.arm_stop(
                command, finalized, stopped, instance, owner, epoch, "daemon-a", {"db": "a" * 64}
            )
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT is_called FROM fence_insert_seen"))
            ).scalar_one()
        assert await db_snapshot(engine) == before
    finally:
        await engine.dispose()
