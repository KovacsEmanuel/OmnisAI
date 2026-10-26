"""Exact saved-entry admission without a selection write or invented SelectionView."""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as store
from omnis.modules.runs.model_test_contract import ENDPOINTS, EntryCapabilities, EntrySnapshot, Ref
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.settings.provider_catalog_runtime import CatalogResult
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_model_service import registry

if TYPE_CHECKING:
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest


async def current(
    owner: ProviderSettingsOwner, db: AsyncConnection, snapshot: EntrySnapshot
) -> bool:
    entries = await registry(db, owner.vault.instance_id)
    connections = await owner.connections(db)
    return (
        snapshot.entry in entries.entries
        and snapshot.connection.enabled
        and snapshot.connection in connections
    )


async def prepare(
    runtime: "ApiKeyModelTest", db: AsyncConnection, command: ModelTestControl
) -> EntrySnapshot:
    state = await registry(db, runtime.instance)
    entry = next((x for x in state.entries if x.entry_id == command.entry_id), None)
    if entry is None:
        raise store.ModelConflict("NOT_FOUND")
    if (
        entry.revision != command.expected_entry_revision
        or entry.connection_revision != command.expected_connection_revision
    ):
        raise store.ModelConflict("REVISION_CONFLICT")
    connection = await runtime.settings.require_selection(db, entry)
    row = (
        await db.execute(
            text(
                "SELECT id::text,digest,payload FROM model_record_v2 WHERE instance_id=:instance "
                "AND kind='catalog-result' AND payload->>'command_id'=:command ORDER BY created_at DESC LIMIT 1"
            ),
            {"instance": runtime.instance, "command": command.catalog_command_id},
        )
    ).one_or_none()
    if row is None:
        raise store.ModelConflict("CAPABILITIES_REQUIRED")
    reference = Ref(instance_id=runtime.instance, kind="catalog-result", id=row[0], digest=row[1])
    result = CatalogResult.model_validate(
        await store.resolve(db, runtime.instance, reference, "catalog-result")
    )
    metadata = next((x for x in result.entries if x.model == entry.model), None)
    if (
        result.connection != connection
        or result.state not in {"READY", "PARTIAL"}
        or metadata is None
        or metadata.reason is not None
        or metadata.supports_max_tokens is not True
        or metadata.max_output_tokens is None
        or entry.output_tokens > metadata.max_output_tokens
    ):
        raise store.ModelConflict("CAPABILITIES_REQUIRED")
    capability = EntryCapabilities(
        entry=entry,
        connection=connection,
        catalog_ref=reference,
        max_output_tokens=metadata.max_output_tokens,
    )
    cap_ref = await store.put(
        db, runtime.instance, "model-entry-capabilities-v1", capability.model_dump(mode="json")
    )
    return EntrySnapshot(
        entry=entry,
        connection=connection,
        capabilities_ref=cap_ref,
        endpoint=ENDPOINTS[connection.provider],
    )
