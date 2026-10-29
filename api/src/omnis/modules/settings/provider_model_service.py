"""Registry transactions run only under ProviderSettingsOwner's existing lock/admission."""

from hashlib import sha256
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.settings.provider_key_models import ModelSelection
from omnis.modules.settings.provider_key_service import SettingsConflict
from omnis.modules.settings.provider_model_models import (
    ModelEntry,
    ModelRegistryControl,
    ModelRegistryView,
    ReadModels,
    RegistryState,
    RemoveModel,
    SaveModels,
)

if TYPE_CHECKING:
    from omnis.modules.settings.provider_key_service import ProviderSettingsOwner


async def registry(db: AsyncConnection, instance: str) -> RegistryState:
    revision = (
        await db.execute(
            text(
                "SELECT revision FROM public.provider_model_registry_revision "
                "WHERE instance_id=:instance ORDER BY revision DESC LIMIT 1"
            ),
            {"instance": instance},
        )
    ).scalar_one_or_none()
    if revision is None:
        return RegistryState(revision=0, entries=[])
    rows = (
        (
            await db.execute(
                text(
                    "SELECT DISTINCT ON (r.entry_id) r.entry_id::text,r.revision,r.connection_id::text,"
                    "r.connection_revision,e.model,r.output_tokens FROM public.provider_model_entry_revision r "
                    "JOIN public.provider_model_entry e USING(instance_id,entry_id,connection_id) "
                    "WHERE r.instance_id=:instance AND r.registry_revision<=:revision "
                    "AND e.removed_registry_revision IS NULL "
                    "ORDER BY r.entry_id,r.revision DESC"
                ),
                {"instance": instance, "revision": revision},
            )
        )
        .mappings()
        .all()
    )
    return RegistryState(
        revision=revision, entries=[ModelEntry.model_validate(dict(row)) for row in rows]
    )


def merge_models(current: RegistryState, request: SaveModels) -> RegistryState:
    if (
        current.revision != request.expected_registry_revision
        or current.revision == 9223372036854775807
    ):
        raise SettingsConflict("REVISION_CONFLICT")
    entries = {item.entry_id: item for item in current.entries}
    identities = {(item.connection_id, item.model): item.entry_id for item in current.entries}
    for item in request.models:
        previous = entries.get(item.entry_id)
        if previous is not None and (previous.connection_id, previous.model) != (
            request.connection_id,
            item.model,
        ):
            raise SettingsConflict("COMMAND_CONFLICT")
        if (
            previous.revision if previous is not None else 0
        ) != item.expected_revision or item.expected_revision == 9223372036854775807:
            raise SettingsConflict("REVISION_CONFLICT")
        if identities.get((request.connection_id, item.model), item.entry_id) != item.entry_id:
            raise SettingsConflict("COMMAND_CONFLICT")
        entries[item.entry_id] = ModelEntry(
            entry_id=item.entry_id,
            revision=item.expected_revision + 1,
            connection_id=request.connection_id,
            connection_revision=request.connection_revision,
            model=item.model,
            output_tokens=item.output_tokens,
        )
    if len(entries) > 64:
        raise SettingsConflict("REGISTRY_FULL")
    return RegistryState(
        revision=current.revision + 1,
        entries=sorted(entries.values(), key=lambda item: item.entry_id),
    )


def remove_model(current: RegistryState, request: RemoveModel) -> RegistryState:
    if (
        current.revision != request.expected_registry_revision
        or current.revision == 9223372036854775807
    ):
        raise SettingsConflict("REVISION_CONFLICT")
    entry = next((item for item in current.entries if item.entry_id == request.entry_id), None)
    if entry is None:
        raise SettingsConflict("NOT_FOUND")
    if entry.revision != request.expected_revision:
        raise SettingsConflict("REVISION_CONFLICT")
    return RegistryState(
        revision=current.revision + 1,
        entries=[item for item in current.entries if item.entry_id != request.entry_id],
    )


async def require_removable(
    owner: "ProviderSettingsOwner", db: AsyncConnection, entry: ModelEntry
) -> None:
    selected = await owner.selection(db)
    if selected is not None and any(
        choice is not None
        and (choice.connection_id, choice.model) == (entry.connection_id, entry.model)
        for choice in (selected.default, selected.brain, selected.investigator, selected.validator)
    ):
        raise SettingsConflict("MODEL_IN_USE")
    if (
        await db.execute(
            text(
                "SELECT 1 FROM public.system_operation WHERE instance_id=:instance "
                "AND state <> 'FINISHED' LIMIT 1"
            ),
            {"instance": owner.vault.instance_id},
        )
    ).first() is not None:
        raise SettingsConflict("OPERATION_ACTIVE")


def page(
    state: RegistryState, request: ReadModels, command_id: str | None = None
) -> ModelRegistryView:
    if request.registry_revision is not None and request.registry_revision != state.revision:
        raise SettingsConflict("REVISION_CONFLICT")
    entries = sorted(state.entries, key=lambda item: item.entry_id)
    start = 0
    if request.after is not None:
        ids = [item.entry_id for item in entries]
        if request.after not in ids:
            raise SettingsConflict("NOT_FOUND")
        start = ids.index(request.after) + 1
        if start >= len(entries):
            raise SettingsConflict("NOT_FOUND")
    selected = entries[start : start + 16]
    return ModelRegistryView(
        command_id=command_id,
        registry_revision=state.revision,
        after=request.after,
        next_after=selected[-1].entry_id if start + len(selected) < len(entries) else None,
        total=len(entries),
        entries=selected,
    )


async def receipt(
    db: AsyncConnection, instance: str, command: str
) -> tuple[str, ModelRegistryView] | None:
    row = (
        (
            await db.execute(
                text(
                    "SELECT request_digest,result FROM public.provider_model_command "
                    "WHERE instance_id=:instance AND command_id=:command"
                ),
                {"instance": instance, "command": command},
            )
        )
        .mappings()
        .one_or_none()
    )
    return (
        None
        if row is None
        else (str(row["request_digest"]), ModelRegistryView.model_validate(row["result"]))
    )


async def handle_models(
    owner: "ProviderSettingsOwner", command: ModelRegistryControl
) -> ModelRegistryView:
    request, instance = command.request, owner.vault.instance_id
    async with owner.service.engine.connect() as db:
        if isinstance(request, ReadModels):
            if request.command_id is not None:
                previous = await receipt(db, instance, request.command_id)
                if previous is None:
                    raise SettingsConflict("NOT_FOUND")
                return previous[1]
            return page(await registry(db, instance), request)
        digest = sha256(command.wire_bytes()).hexdigest()
        previous = await receipt(db, instance, request.command_id)
        if previous is not None:
            if previous[0] != digest:
                raise SettingsConflict("COMMAND_CONFLICT")
            return previous[1]
    status = await owner.service.owned_status(owner.owner, owner.epoch)
    if str(status.instance_id) != instance:
        raise SettingsConflict("CONNECTION_UNAVAILABLE")
    async with owner.service.admission(status.generation, owner.owner, owner.epoch) as db:
        current = await registry(db, instance)
        if isinstance(request, RemoveModel):
            updated = remove_model(current, request)
            entry = next(item for item in current.entries if item.entry_id == request.entry_id)
            await require_removable(owner, db, entry)
        else:
            await owner.require_selection(
                db,
                ModelSelection(
                    connection_id=request.connection_id,
                    connection_revision=request.connection_revision,
                    model=request.models[0].model,
                    output_tokens=request.models[0].output_tokens,
                ),
            )
            updated = merge_models(current, request)
            # An archived identity is never reused, even with a fresh registry revision.
            for requested in request.models:
                retired = (
                    await db.execute(
                        text(
                            "SELECT 1 FROM public.provider_model_entry WHERE instance_id=:instance "
                            "AND entry_id=:entry AND removed_registry_revision IS NOT NULL"
                        ),
                        {"instance": instance, "entry": requested.entry_id},
                    )
                ).first()
                if retired is not None:
                    raise SettingsConflict("REVISION_CONFLICT")
        result = page(updated, ReadModels(action="read"), request.command_id)
        await db.execute(
            text(
                "INSERT INTO public.provider_model_registry_revision (instance_id,revision) "
                "VALUES (:instance,:revision)"
            ),
            {"instance": instance, "revision": updated.revision},
        )
        previous_ids = {item.entry_id for item in current.entries}
        if isinstance(request, RemoveModel):
            await db.execute(
                text(
                    "UPDATE public.provider_model_entry SET removed_registry_revision=:revision "
                    "WHERE instance_id=:instance AND entry_id=:entry"
                ),
                {"instance": instance, "entry": request.entry_id, "revision": updated.revision},
            )
        changed_ids = (
            {item.entry_id for item in request.models} if isinstance(request, SaveModels) else set()
        )
        for item in updated.entries:
            if item.entry_id not in changed_ids:
                continue
            values = {
                **item.model_dump(),
                "instance": instance,
                "registry_revision": updated.revision,
            }
            if item.entry_id not in previous_ids:
                await db.execute(
                    text(
                        "INSERT INTO public.provider_model_entry (instance_id,entry_id,connection_id,model) "
                        "VALUES (:instance,:entry_id,:connection_id,:model)"
                    ),
                    values,
                )
            await db.execute(
                text(
                    "INSERT INTO public.provider_model_entry_revision (instance_id,entry_id,revision,"
                    "connection_id,connection_revision,registry_revision,output_tokens) "
                    "VALUES (:instance,:entry_id,:revision,:connection_id,:connection_revision,"
                    ":registry_revision,:output_tokens)"
                ),
                values,
            )
        await db.execute(
            text(
                "INSERT INTO public.provider_model_command (instance_id,command_id,request_digest,result) "
                "VALUES (:instance,:command,:digest,CAST(:result AS jsonb))"
            ),
            {
                "instance": instance,
                "command": request.command_id,
                "digest": digest,
                "result": result.model_dump_json(),
            },
        )
        return result
