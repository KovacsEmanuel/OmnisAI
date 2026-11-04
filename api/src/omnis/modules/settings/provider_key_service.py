"""Supervisor-owned local Settings transactions; Save never contacts a provider."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from concurrent.futures import Future
from hashlib import sha256
from typing import Literal, overload
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.service import InstanceService
from omnis.modules.settings.provider_key_models import (
    MODEL_ROLES,
    ConnectionView,
    Identity,
    KeyDTO,
    KeySettingsControl,
    KeySettingsView,
    ModelRole,
    ModelSelection,
    PositiveRevision,
    Provider,
    ReadSettings,
    RevokeConnection,
    SaveConnection,
    SaveSelection,
    SaveSelectionV2,
    SelectionView,
    SelectionViewV2,
)
from omnis.modules.settings.provider_model_models import ModelRegistryControl, ModelRegistryView
from omnis.modules.settings.provider_vault import CredentialRef, ProviderVault


class SettingsConflict(ValueError):
    def __init__(self, code: str) -> None:
        if code not in {
            "COMMAND_CONFLICT",
            "REVISION_CONFLICT",
            "CONNECTION_UNAVAILABLE",
            "NOT_FOUND",
            "REGISTRY_FULL",
            "MODEL_NOT_REGISTERED",
            "MODEL_IN_USE",
            "OPERATION_ACTIVE",
        }:
            raise ValueError("Invalid Settings reason")
        self.code = code
        super().__init__(code)


class ConnectionRevision(KeyDTO):
    connection_id: Identity
    provider: Provider
    revision: PositiveRevision
    enabled: bool
    secret_id: Identity
    credential_revision: PositiveRevision

    def credential(self, instance: str) -> CredentialRef:
        return CredentialRef(instance, self.secret_id, self.credential_revision, self.provider)


class ProviderSettingsOwner:
    def __init__(
        self, service: InstanceService, owner: UUID, epoch: int, vault: ProviderVault
    ) -> None:
        self.service, self.owner, self.epoch, self.vault = service, owner, epoch, vault
        self.lock = asyncio.Lock()
        self.model_drain: Callable[[], Awaitable[bool]] | None = None
        self.writes: set[asyncio.Task[None]] = set()

    def _write_finished(self, task: asyncio.Task[None]) -> None:
        self.writes.discard(task)
        if not task.cancelled():
            task.exception()  # Observe orphan failures without exposing their payload/traceback.

    async def _vault_write(self, action: Callable[[], None]) -> None:
        reservation = self.vault.reserve_write()
        ownership = Future[None]()

        def write() -> None:
            if not ownership.set_running_or_notify_cancel():
                return
            try:
                action()
            finally:
                os.close(reservation)

        async def schedule() -> None:
            try:
                await asyncio.to_thread(write)
            finally:
                # Failed submit can leave write queued; revoke its claim before releasing the fd.
                if ownership.cancel():
                    os.close(reservation)

        task = asyncio.create_task(schedule())
        self.writes.add(task)
        task.add_done_callback(self._write_finished)
        # Control timeout rolls back DB, but cannot cancel a filesystem syscall.
        await asyncio.shield(task)

    async def drain(self) -> bool:
        pending = {task for task in self.writes if not task.done()}
        if pending:
            _, remaining = await asyncio.wait(pending, timeout=1)
            if remaining:
                return False
        return self.vault.quiescent()

    async def connections(self, db: AsyncConnection) -> list[ConnectionRevision]:
        rows = (
            (
                await db.execute(
                    text(
                        "SELECT DISTINCT ON (provider) connection_id::text, provider, revision, enabled, "
                        "secret_id::text, credential_revision FROM public.provider_connection_revision "
                        "WHERE instance_id=:instance ORDER BY provider, revision DESC"
                    ),
                    {"instance": self.vault.instance_id},
                )
            )
            .mappings()
            .all()
        )
        return [ConnectionRevision.model_validate(dict(row)) for row in rows]

    async def selection(self, db: AsyncConnection) -> SelectionView | SelectionViewV2 | None:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT selection_id::text, revision, payload FROM public.provider_selection_revision "
                        "WHERE instance_id=:instance ORDER BY revision DESC LIMIT 1"
                    ),
                    {"instance": self.vault.instance_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        selected: SaveSelection | SaveSelectionV2 = TypeAdapter(
            SaveSelection | SaveSelectionV2
        ).validate_python(row["payload"])
        fields = selected.model_dump(exclude={"action", "command_id", "expected_revision"})
        if isinstance(selected, SaveSelectionV2):
            return SelectionViewV2(
                selection_id=str(row["selection_id"]),
                revision=row["revision"],
                schema_version=2,
                **fields,
            )
        return SelectionView(
            selection_id=str(row["selection_id"]),
            revision=row["revision"],
            **fields,
        )

    async def view(self, db: AsyncConnection, command_id: str | None) -> KeySettingsView:
        connections = await self.connections(db)
        status: Literal["LOCKED", "UNLOCKED", "UNCONFIGURED"] = await asyncio.to_thread(
            lambda: self.vault.status
        )
        projected = []
        for row in connections:
            present = await asyncio.to_thread(
                self.vault.contains, row.credential(self.vault.instance_id)
            )
            if not present:
                status = "LOCKED"
            projected.append(
                ConnectionView(
                    connection_id=row.connection_id,
                    provider=row.provider,
                    revision=row.revision,
                    enabled=row.enabled,
                    credential_present=present,
                )
            )
        return KeySettingsView(
            command_id=command_id,
            vault_status=status,
            connections=projected,
            selection=await self.selection(db),
        )

    async def receipt(
        self, db: AsyncConnection, command_id: str
    ) -> tuple[str, KeySettingsView] | None:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT request_digest,result FROM public.provider_settings_command "
                        "WHERE instance_id=:instance AND command_id=:command"
                    ),
                    {"instance": self.vault.instance_id, "command": command_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return str(row["request_digest"]), KeySettingsView.model_validate(row["result"])

    async def require_selection(
        self, db: AsyncConnection, choice: ModelSelection
    ) -> ConnectionRevision:
        return await self.require_connection(db, choice.connection_id, choice.connection_revision)

    async def resolve_role(
        self,
        db: AsyncConnection,
        selection: SaveSelection | SaveSelectionV2 | SelectionView,
        role: ModelRole,
    ) -> ModelSelection:
        choice = {
            "default": selection.default,
            "brain": selection.brain,
            "recon": selection.recon
            if isinstance(selection, (SaveSelectionV2, SelectionViewV2))
            else None,
            "investigator": selection.investigator,
            "validator": selection.validator,
        }[role]
        if choice is None:
            choice = selection.default
        await self.require_selection(db, choice)
        await self.require_registered(db, choice)
        return choice

    async def require_connection(
        self, db: AsyncConnection, identity: str, revision: int
    ) -> ConnectionRevision:
        for row in await self.connections(db):
            if row.connection_id == identity and row.revision == revision and row.enabled:
                return row
        raise SettingsConflict("CONNECTION_UNAVAILABLE")

    async def require_registered(self, db: AsyncConnection, choice: ModelSelection) -> None:
        registered = (
            await db.execute(
                text(
                    "SELECT 1 FROM public.provider_model_entry e "
                    "JOIN public.provider_model_entry_revision r USING(instance_id,entry_id,connection_id) "
                    "WHERE e.instance_id=:instance AND e.connection_id=:connection AND e.model=:model "
                    "AND e.removed_registry_revision IS NULL "
                    "AND r.connection_revision=:connection_revision "
                    "AND r.revision=(SELECT max(h.revision) FROM public.provider_model_entry_revision h "
                    "WHERE h.instance_id=e.instance_id AND h.entry_id=e.entry_id) LIMIT 1"
                ),
                {
                    "instance": self.vault.instance_id,
                    "connection": choice.connection_id,
                    "connection_revision": choice.connection_revision,
                    "model": choice.model,
                },
            )
        ).scalar_one_or_none()
        if registered is None:
            raise SettingsConflict("MODEL_NOT_REGISTERED")

    @overload
    async def handle(self, command: KeySettingsControl) -> KeySettingsView: ...

    @overload
    async def handle(self, command: ModelRegistryControl) -> ModelRegistryView: ...

    async def handle(
        self, command: KeySettingsControl | ModelRegistryControl
    ) -> KeySettingsView | ModelRegistryView:
        # This same finite lock is also held across the final provider write, never its response.
        async with self.lock:
            if isinstance(command, ModelRegistryControl):
                from omnis.modules.settings.provider_model_service import handle_models

                return await handle_models(self, command)
            request = command.request
            if isinstance(request, ReadSettings):
                async with self.service.engine.connect() as db:
                    if request.command_id is not None:
                        previous = await self.receipt(db, request.command_id)
                        if previous is None:
                            raise SettingsConflict("NOT_FOUND")
                        return previous[1]
                    return await self.view(db, None)
            if any(not task.done() for task in self.writes):
                raise ValueError("Credential writer is not quiescent")
            digest = (
                sha256(command.wire_bytes()).hexdigest()
                if not isinstance(request, SaveConnection)
                else None
            )
            async with self.service.engine.connect() as db:
                previous = await self.receipt(db, request.command_id)
                if previous is not None:
                    if isinstance(request, SaveConnection):
                        digest = await asyncio.to_thread(
                            self.vault.command_digest, request.command_id, command.wire()
                        )
                    if previous[0] != digest:
                        raise SettingsConflict("COMMAND_CONFLICT")
                    return previous[1]
            status = await self.service.owned_status(self.owner, self.epoch)
            if str(status.instance_id) != self.vault.instance_id:
                raise SettingsConflict("CONNECTION_UNAVAILABLE")
            async with self.service.admission(status.generation, self.owner, self.epoch) as db:
                if isinstance(request, (SaveConnection, RevokeConnection)):
                    heads = await self.connections(db)
                    current = next(
                        (row for row in heads if row.connection_id == request.connection_id), None
                    )
                    if (
                        current.revision if current is not None else 0
                    ) != request.expected_revision:
                        raise SettingsConflict("REVISION_CONFLICT")
                    if isinstance(request, SaveConnection):
                        if any(
                            row.provider == request.provider
                            and row.connection_id != request.connection_id
                            for row in heads
                        ):
                            raise SettingsConflict("CONNECTION_UNAVAILABLE")
                        if current is not None and current.provider != request.provider:
                            raise SettingsConflict("CONNECTION_UNAVAILABLE")
                        # Revoked heads still retain credential refs; only empty DB history is initial.
                        if not heads:
                            await self._vault_write(self.vault.bootstrap)
                        digest = await asyncio.to_thread(
                            self.vault.command_digest, request.command_id, command.wire()
                        )
                        row = ConnectionRevision(
                            connection_id=request.connection_id,
                            provider=request.provider,
                            revision=request.expected_revision + 1,
                            enabled=True,
                            secret_id=str(uuid4()),
                            credential_revision=1,
                        )
                        # DB rollback may orphan this durable revision; it is never reused implicitly.
                        await self._vault_write(
                            lambda: self.vault.put(
                                row.credential(self.vault.instance_id),
                                request.secret.get_secret_value(),
                            )
                        )
                    else:
                        if current is None:
                            raise SettingsConflict("CONNECTION_UNAVAILABLE")
                        row = current.model_copy(
                            update={"revision": current.revision + 1, "enabled": False}
                        )
                    await db.execute(
                        text(
                            "INSERT INTO public.provider_connection_revision "
                            "(instance_id,connection_id,provider,revision,enabled,secret_id,credential_revision) "
                            "VALUES (:instance,:connection_id,:provider,:revision,:enabled,:secret_id,:credential_revision)"
                        ),
                        {"instance": self.vault.instance_id, **row.model_dump()},
                    )
                else:
                    current_selection = await self.selection(db)
                    if (
                        current_selection.revision if current_selection is not None else 0
                    ) != request.expected_revision:
                        raise SettingsConflict("REVISION_CONFLICT")
                    for role in MODEL_ROLES:
                        await self.resolve_role(db, request, role)
                    await db.execute(
                        text(
                            "INSERT INTO public.provider_selection_revision (instance_id,selection_id,revision,payload) "
                            "VALUES (:instance,:id,:revision,CAST(:payload AS jsonb))"
                        ),
                        {
                            "instance": self.vault.instance_id,
                            "id": request.command_id,
                            "revision": request.expected_revision + 1,
                            "payload": request.model_dump_json(),
                        },
                    )
                result = await self.view(db, request.command_id)
                await db.execute(
                    text(
                        "INSERT INTO public.provider_settings_command (instance_id,command_id,request_digest,result) "
                        "VALUES (:instance,:command,:digest,CAST(:result AS jsonb))"
                    ),
                    {
                        "instance": self.vault.instance_id,
                        "command": request.command_id,
                        "digest": digest,
                        "result": result.model_dump_json(),
                    },
                )
        if isinstance(request, (SaveConnection, RevokeConnection)) and self.model_drain is not None:
            if not await self.model_drain():
                raise ValueError("Model drain uncertain after committed connection change")
        return result
