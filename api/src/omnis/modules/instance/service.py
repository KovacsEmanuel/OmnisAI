"""One DB lock order for lease, admission, shutdown and idempotency.

P0 supports only transactional inert work. Future effect producers must use the
same admission transaction AND provide real adapters before extending quiescence.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.persistence import read_datetime, read_integer, read_record
from omnis.modules.instance.domain import ControlCode, ControlConflict, InstanceStatus
from omnis.modules.instance.records import CommandKind, CommandRecord, InstanceRecord, LeaseRecord
from omnis.security.sessions import SessionStore


class InstanceService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        async with self.engine.begin() as connection:
            instance_data = (
                (
                    await connection.execute(
                        text("SELECT * FROM instance_control WHERE id = 1 FOR UPDATE")
                    )
                )
                .mappings()
                .one()
            )
            lease_data = (
                (
                    await connection.execute(
                        text("SELECT * FROM supervisor_lease WHERE id = 1 FOR UPDATE")
                    )
                )
                .mappings()
                .one()
            )
            yield (
                connection,
                read_record(InstanceRecord, instance_data),
                read_record(LeaseRecord, lease_data),
            )

    async def _live(self, connection: AsyncConnection, lease: LeaseRecord) -> bool:
        now = read_datetime(
            (await connection.execute(text("SELECT clock_timestamp()"))).scalar_one()
        )
        return lease.owner is not None and lease.expires_at is not None and lease.expires_at > now

    async def _require_owner(
        self, connection: AsyncConnection, lease: LeaseRecord, owner: UUID, epoch: int
    ) -> None:
        if lease.owner != owner or lease.epoch != epoch or not await self._live(connection, lease):
            raise ControlConflict(ControlCode.LEASE_LOST)

    async def _close_after_owner_loss(
        self, connection: AsyncConnection, instance: InstanceRecord
    ) -> None:
        if instance.admission_open:
            await connection.execute(
                text(
                    "UPDATE instance_control SET admission_open = false, generation = generation + 1, "
                    "shutdown_command_id = :command, quiesced_generation = NULL, quiesced_at = NULL WHERE id = 1"
                ),
                {"command": uuid4()},
            )

    async def acquire(self, owner: UUID) -> int:
        async with self._locked() as (connection, instance, lease):
            if await self._live(connection, lease):
                raise ControlConflict(ControlCode.SUPERVISOR_OWNED)
            await self._close_after_owner_loss(connection, instance)
            value = (
                await connection.execute(
                    text(
                        "UPDATE supervisor_lease SET owner = :owner, epoch = epoch + 1, "
                        "expires_at = clock_timestamp() + interval '5 seconds' WHERE id = 1 RETURNING epoch"
                    ),
                    {"owner": owner},
                )
            ).scalar_one()
            return read_integer(value)

    async def heartbeat(self, owner: UUID, epoch: int) -> None:
        async with self._locked() as (connection, _, lease):
            await self._require_owner(connection, lease, owner, epoch)
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() + interval '5 seconds' WHERE id = 1"
                )
            )

    async def release(self, owner: UUID, epoch: int) -> None:
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            await self._close_after_owner_loss(connection, instance)
            await connection.execute(
                text("UPDATE supervisor_lease SET owner = NULL, expires_at = NULL WHERE id = 1")
            )

    async def _receipt(
        self, connection: AsyncConnection, command_id: UUID, kind: CommandKind, expected: int
    ) -> int | None:
        receipt_data = (
            (
                await connection.execute(
                    text("SELECT * FROM instance_command WHERE command_id = :command"),
                    {"command": command_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        receipt = read_record(CommandRecord, receipt_data) if receipt_data is not None else None
        if receipt is not None and (
            receipt.kind != kind or receipt.expected_generation != expected
        ):
            raise ControlConflict(ControlCode.COMMAND_CONFLICT)
        return receipt.result_generation if receipt is not None else None

    async def _record(
        self,
        connection: AsyncConnection,
        command_id: UUID,
        kind: CommandKind,
        expected: int,
        result: int,
        epoch: int,
    ) -> None:
        await connection.execute(
            text(
                "INSERT INTO instance_command VALUES (:command, :kind, :expected, :result, :epoch)"
            ),
            {
                "command": command_id,
                "kind": kind,
                "expected": expected,
                "result": result,
                "epoch": epoch,
            },
        )

    def _require_generation(self, instance: InstanceRecord, expected: int) -> None:
        if instance.generation != expected:
            raise ControlConflict(ControlCode.GENERATION_CONFLICT)

    async def _finalized_epoch(self, connection: AsyncConnection, generation: int) -> int | None:
        value = (
            await connection.execute(
                text(
                    "SELECT min(owner_epoch) FROM instance_command WHERE kind = 'FINALIZE' AND result_generation = :generation"
                ),
                {"generation": generation},
            )
        ).scalar_one()
        return read_integer(value) if value is not None else None

    async def open(self, command_id: UUID, expected: int, owner: UUID, epoch: int) -> int:
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            previous = await self._receipt(connection, command_id, "OPEN", expected)
            if previous is not None:
                return previous
            self._require_generation(instance, expected)
            if instance.admission_open:
                raise ControlConflict(ControlCode.ALREADY_OPEN)
            if instance.shutdown_command_id is not None:
                finalized = await self._finalized_epoch(connection, expected)
                if instance.quiesced_generation != expected or finalized is None:
                    raise ControlConflict(ControlCode.SHUTDOWN_INCOMPLETE)
                if epoch <= finalized:
                    raise ControlConflict(ControlCode.RESTART_REQUIRED)
            result = expected + 1
            await connection.execute(
                text(
                    "UPDATE instance_control SET admission_open = true, generation = :generation, "
                    "shutdown_command_id = NULL, quiesced_generation = NULL, quiesced_at = NULL WHERE id = 1"
                ),
                {"generation": result},
            )
            await self._record(connection, command_id, "OPEN", expected, result, epoch)
            return result

    @asynccontextmanager
    async def admission(
        self, generation: int, owner: UUID, epoch: int
    ) -> AsyncIterator[AsyncConnection]:
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            if not instance.admission_open or instance.shutdown_command_id is not None:
                raise ControlConflict(ControlCode.INSTANCE_SHUTTING_DOWN)
            self._require_generation(instance, generation)
            # Caller may only persist admitted work; never wait for model/network/operator here.
            yield connection
            # Long-running transactions cannot publish work after their lease expired.
            await self._require_owner(connection, lease, owner, epoch)

    async def shutdown(self, command_id: UUID, expected: int) -> int:
        async with self._locked() as (connection, instance, lease):
            previous = await self._receipt(connection, command_id, "SHUTDOWN", expected)
            if previous is not None:
                return previous
            self._require_generation(instance, expected)
            result = expected
            if instance.shutdown_command_id is None:
                result += 1
                await connection.execute(
                    text(
                        "UPDATE instance_control SET admission_open = false, shutdown_command_id = :command, "
                        "generation = :generation, quiesced_generation = NULL, quiesced_at = NULL WHERE id = 1"
                    ),
                    {"command": command_id, "generation": result},
                )
            await self._record(connection, command_id, "SHUTDOWN", expected, result, lease.epoch)
            return result

    async def quiesce(self, owner: UUID, epoch: int) -> None:
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            if not instance.admission_open and instance.shutdown_command_id is not None:
                # P0 has no runtime, effect producer or background writer. Lock acquisition
                # drains the only supported work: committed, transactional inert admissions.
                await connection.execute(
                    text(
                        "UPDATE instance_control SET quiesced_generation = generation, quiesced_at = clock_timestamp() "
                        "WHERE id = 1 AND quiesced_generation IS DISTINCT FROM generation"
                    )
                )

    async def finalize(self, command_id: UUID, expected: int) -> int:
        async with self._locked() as (connection, instance, lease):
            previous = await self._receipt(connection, command_id, "FINALIZE", expected)
            if previous is not None:
                return previous
            self._require_generation(instance, expected)
            if (
                instance.admission_open
                or instance.shutdown_command_id is None
                or instance.quiesced_generation != expected
            ):
                raise ControlConflict(ControlCode.SHUTDOWN_INCOMPLETE)
            await self._record(connection, command_id, "FINALIZE", expected, expected, lease.epoch)
            return expected

    async def status(self) -> InstanceStatus:
        async with self._locked() as (connection, instance, lease):
            return await self._status(connection, instance, lease)

    async def owned_status(self, owner: UUID, epoch: int) -> InstanceStatus:
        """Validate serving authority without extending its lease on read traffic."""
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            return await self._status(connection, instance, lease)

    async def register_pairing(
        self, instance_id: UUID, digest: str, issuance_id: UUID, owner: UUID, epoch: int
    ) -> None:
        """Serialize issuance and shutdown under the same durable instance row lock."""
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            if instance.instance_id != instance_id:
                raise ControlConflict(ControlCode.INSTANCE_MISMATCH)
            if not instance.admission_open or instance.shutdown_command_id is not None:
                raise ControlConflict(ControlCode.INSTANCE_SHUTTING_DOWN)
            await SessionStore(self.engine).register_on(connection, digest, issuance_id=issuance_id)
            # A challenge-row wait can outlive the lease checked above. Roll back
            # both challenge and immutable issuance receipt if authority expired.
            await self._require_owner(connection, lease, owner, epoch)

    async def _status(
        self, connection: AsyncConnection, instance: InstanceRecord, lease: LeaseRecord
    ) -> InstanceStatus:
        return InstanceStatus(
            instance_id=instance.instance_id,
            generation=instance.generation,
            admission_open=instance.admission_open,
            shutdown_command_id=instance.shutdown_command_id,
            quiesced_generation=instance.quiesced_generation,
            supervisor_epoch=lease.epoch,
            supervisor_ready=await self._live(connection, lease),
            shutdown_finalized=await self._finalized_epoch(connection, instance.generation)
            is not None,
        )
