"""One DB lock order for lease, admission, shutdown and idempotency.

P0 supports only transactional inert work. Future effect producers must use the
same admission transaction AND provide real adapters before extending quiescence.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from json import dumps
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.persistence import read_datetime, read_integer, read_record
from omnis.modules.instance.domain import ControlCode, ControlConflict, InstanceStatus
from omnis.modules.instance.records import (
    CommandKind,
    CommandRecord,
    InstanceRecord,
    LeaseRecord,
    StopFenceRecord,
    StopFenceState,
)
from omnis.modules.instance.stop_contract import ArmStopCommand, StopGrant, canonical_json
from omnis.security.sessions import SessionStore


def _exact_json_shape(value: object) -> bool:
    # json.dumps otherwise coerces integer keys and tuples, changing an owned
    # resource identity between the caller and durable JSONB.
    if type(value) is dict:
        return all(type(key) is str and _exact_json_shape(item) for key, item in value.items())
    if type(value) is list:
        return all(_exact_json_shape(item) for item in value)
    # Resource identities are discrete. JSONB can normalize a floating-point
    # representation, so accepting floats would make exact replay ambiguous.
    return type(value) in (str, int, bool, type(None))


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

    async def _stop_fence(self, connection: AsyncConnection) -> None:
        # The instance row is already locked. A fence has no expiry and must be
        # checked before lease takeover can close admission or increment epoch.
        if (
            await connection.execute(text("SELECT 1 FROM instance_stop_fence WHERE id = 1"))
        ).scalar_one_or_none() is not None:
            raise ControlConflict(ControlCode.STOP_IN_PROGRESS)

    async def acquire(self, owner: UUID) -> int:
        async with self._locked() as (connection, instance, lease):
            await self._stop_fence(connection)
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
            await self._stop_fence(connection)
            await self._require_owner(connection, lease, owner, epoch)
            previous = await self._receipt(connection, command_id, "OPEN", expected)
            await self._require_owner(connection, lease, owner, epoch)
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
            await self._require_owner(connection, lease, owner, epoch)
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

    async def shutdown(self, command_id: UUID, expected: int, owner: UUID, epoch: int) -> int:
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            previous = await self._receipt(connection, command_id, "SHUTDOWN", expected)
            await self._require_owner(connection, lease, owner, epoch)
            if previous is not None:
                return previous
            self._require_generation(instance, expected)
            if instance.shutdown_command_id is not None:
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            result = expected
            result += 1
            await connection.execute(
                text(
                    "UPDATE instance_control SET admission_open = false, shutdown_command_id = :command, "
                    "generation = :generation, quiesced_generation = NULL, quiesced_at = NULL WHERE id = 1"
                ),
                {"command": command_id, "generation": result},
            )
            await self._record(connection, command_id, "SHUTDOWN", expected, result, lease.epoch)
            await self._require_owner(connection, lease, owner, epoch)
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
                # An UPDATE table-lock wait can outlive the lease checked above.
                # Roll back the quiescence receipt before transaction commit.
                await self._require_owner(connection, lease, owner, epoch)

    async def finalize(self, command_id: UUID, expected: int, owner: UUID, epoch: int) -> int:
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            previous = await self._receipt(connection, command_id, "FINALIZE", expected)
            await self._require_owner(connection, lease, owner, epoch)
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
            await self._require_owner(connection, lease, owner, epoch)
            return expected

    async def arm_stop(
        self,
        command_id: UUID,
        finalize_command_id: UUID,
        generation: int,
        instance_id: UUID,
        owner: UUID,
        epoch: int,
        daemon_id: str,
        inventory: dict[str, object],
    ) -> StopFenceState:
        """Commit the sole Stop authority before any host effect; never expire it.

        The caller must independently attest the daemon and exact owned inventory.
        This DB slice records their identity, but grants no Docker capability.
        """
        if (
            type(generation) is not int
            or not 1 <= generation <= 9223372036854775807
            or type(epoch) is not int
            or not 1 <= epoch <= 9223372036854775807
            or not isinstance(daemon_id, str)
            or not daemon_id
            or type(inventory) is not dict
            or not inventory
            or not _exact_json_shape(inventory)
        ):
            raise ControlConflict(ControlCode.COMMAND_CONFLICT)
        try:
            expected_grant = StopGrant.model_validate(
                {
                    "version": 1,
                    "state": "STOP_PENDING",
                    "instance_id": instance_id,
                    "command_id": command_id,
                    "finalize_command_id": finalize_command_id,
                    "generation": generation,
                    "owner_epoch": epoch,
                    "owner_uuid": owner,
                    "daemon_id": daemon_id,
                    "inventory": inventory,
                }
            )
            inventory_json = dumps(
                inventory, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError):
            raise ControlConflict(ControlCode.COMMAND_CONFLICT) from None
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            existing = (
                (await connection.execute(text("SELECT * FROM instance_stop_fence WHERE id = 1")))
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                fence = read_record(StopFenceRecord, existing)
                if (
                    fence.owner_uuid != owner
                    or fence.instance_id != instance_id
                    or fence.command_id != command_id
                    or fence.finalize_command_id != finalize_command_id
                    or fence.generation != generation
                    or fence.owner_epoch != epoch
                    or fence.daemon_id != daemon_id
                    # Python dict equality treats True == 1; Stop identities do not.
                    or dumps(fence.inventory, sort_keys=True, separators=(",", ":"))
                    != inventory_json
                ):
                    raise ControlConflict(ControlCode.COMMAND_CONFLICT)
                await self._closed_stop(connection, instance, lease, expected_grant)
                await self._require_owner(connection, lease, owner, epoch)
                return fence.state
            if instance.instance_id != instance_id:
                raise ControlConflict(ControlCode.INSTANCE_MISMATCH)
            self._require_generation(instance, generation)
            if (
                instance.admission_open
                or instance.shutdown_command_id != command_id
                or instance.quiesced_generation != generation
                or instance.quiesced_at is None
            ):
                raise ControlConflict(ControlCode.SHUTDOWN_INCOMPLETE)
            shutdown = await connection.execute(
                text(
                    "SELECT 1 FROM instance_command WHERE command_id = :command "
                    "AND kind = 'SHUTDOWN' AND result_generation = :generation "
                    "AND expected_generation = :expected AND owner_epoch = :epoch"
                ),
                {
                    "command": command_id,
                    "generation": generation,
                    "expected": generation - 1,
                    "epoch": epoch,
                },
            )
            finalized = await connection.execute(
                text(
                    "SELECT 1 FROM instance_command WHERE command_id = :command "
                    "AND kind = 'FINALIZE' AND expected_generation = :generation "
                    "AND result_generation = :generation AND owner_epoch = :epoch"
                ),
                {"command": finalize_command_id, "generation": generation, "epoch": epoch},
            )
            if shutdown.scalar_one_or_none() is None or finalized.scalar_one_or_none() is None:
                raise ControlConflict(ControlCode.SHUTDOWN_INCOMPLETE)
            await connection.execute(
                text(
                    "INSERT INTO instance_stop_fence "
                    "(id, instance_id, command_id, finalize_command_id, generation, "
                    "owner_epoch, daemon_id, inventory, state, owner_uuid) VALUES "
                    "(1, :instance, :command, :finalized, :generation, :epoch, "
                    ":daemon, CAST(:inventory AS jsonb), 'STOP_PENDING', :owner)"
                ),
                {
                    "instance": instance_id,
                    "command": command_id,
                    "finalized": finalize_command_id,
                    "generation": generation,
                    "epoch": epoch,
                    "daemon": daemon_id,
                    "inventory": inventory_json,
                    "owner": owner,
                },
            )
            stored = await self._grant(connection)
            if stored is None or canonical_json(stored.model_dump(mode="json")) != canonical_json(
                expected_grant.model_dump(mode="json")
            ):
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            await self._closed_stop(connection, instance, lease, stored)
            await self._require_owner(connection, lease, owner, epoch)
            return "STOP_PENDING"

    async def _closed_stop(
        self,
        connection: AsyncConnection,
        instance: InstanceRecord,
        lease: LeaseRecord,
        grant: StopGrant,
    ) -> None:
        if instance.instance_id != grant.instance_id:
            raise ControlConflict(ControlCode.INSTANCE_MISMATCH)
        if (
            instance.generation != grant.generation
            or lease.epoch != grant.owner_epoch
            or (lease.owner is not None and lease.owner != grant.owner_uuid)
            or instance.admission_open
            or instance.shutdown_command_id != grant.command_id
            or instance.quiesced_generation != grant.generation
            or instance.quiesced_at is None
        ):
            raise ControlConflict(ControlCode.COMMAND_CONFLICT)
        for command_id, kind, expected in (
            (grant.command_id, "SHUTDOWN", grant.generation - 1),
            (grant.finalize_command_id, "FINALIZE", grant.generation),
        ):
            row = (
                (
                    await connection.execute(
                        text("SELECT * FROM instance_command WHERE command_id = :command"),
                        {"command": command_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ControlConflict(ControlCode.SHUTDOWN_INCOMPLETE)
            receipt = read_record(CommandRecord, row)
            if (
                receipt.kind != kind
                or receipt.expected_generation != expected
                or receipt.result_generation != grant.generation
                or receipt.owner_epoch != grant.owner_epoch
            ):
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)

    async def _grant(self, connection: AsyncConnection) -> StopGrant | None:
        row = (
            (await connection.execute(text("SELECT * FROM instance_stop_fence WHERE id = 1")))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        fence = read_record(StopFenceRecord, row)
        if fence.owner_uuid is None:
            raise ControlConflict(ControlCode.COMMAND_CONFLICT)
        try:
            return StopGrant.model_validate(
                {
                    **fence.model_dump(exclude={"id"}),
                    "version": 1,
                }
            )
        except ValidationError:
            raise ControlConflict(ControlCode.COMMAND_CONFLICT) from None

    async def stop_grant_readback(
        self,
        command: ArmStopCommand,
        owner: UUID,
    ) -> dict[str, object]:
        # A second transaction after arm commit. Never build a reply by mixing
        # command input with a later unrelated status/epoch.
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, command.owner_epoch)
            grant = await self._grant(connection)
            if grant is None:
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            expected = StopGrant.model_validate(
                {
                    **command.model_dump(exclude={"op"}),
                    "version": 1,
                    "state": grant.state,
                    "owner_uuid": owner,
                }
            )
            if canonical_json(grant.model_dump(mode="json")) != canonical_json(
                expected.model_dump(mode="json")
            ):
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            await self._closed_stop(connection, instance, lease, grant)
            await self._require_owner(connection, lease, owner, command.owner_epoch)
            return grant.model_dump(mode="json")

    async def command_readback(
        self,
        command_id: UUID,
        kind: CommandKind,
        expected: int,
        result: int,
        owner: UUID,
        epoch: int,
    ) -> InstanceStatus:
        """Bind a committed receipt and current state under one DB row lock.

        Another command between commit and this read can only cause refusal,
        never a successful reply mixing two generations or owner epochs.
        """
        async with self._locked() as (connection, instance, lease):
            await self._require_owner(connection, lease, owner, epoch)
            data = (
                (
                    await connection.execute(
                        text("SELECT * FROM instance_command WHERE command_id = :command"),
                        {"command": command_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if data is None:
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            receipt = read_record(CommandRecord, data)
            if (
                receipt.kind != kind
                or receipt.expected_generation != expected
                or receipt.result_generation != result
                or receipt.owner_epoch != epoch
                or instance.generation != result
            ):
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            status = await self._status(connection, instance, lease)
            if (
                kind == "OPEN"
                and (not status.admission_open or status.shutdown_command_id is not None)
                or kind == "SHUTDOWN"
                and (status.admission_open or status.shutdown_command_id is None)
                or kind == "FINALIZE"
                and (
                    status.admission_open
                    or status.quiesced_generation != result
                    or not status.shutdown_finalized
                )
            ):
                raise ControlConflict(ControlCode.COMMAND_CONFLICT)
            await self._require_owner(connection, lease, owner, epoch)
            return status

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
