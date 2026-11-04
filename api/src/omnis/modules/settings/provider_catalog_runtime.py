"""Catalog operations use the existing ModelTest owner/tasks/store/relay authority."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as store
from omnis.modules.runs.model_test_contract import ENDPOINTS
from omnis.modules.settings.provider_catalog import CatalogIngest
from omnis.modules.settings.provider_catalog_models import (
    CancelCatalog,
    CatalogControl,
    CatalogModel,
    CatalogReason,
    CatalogView,
    RefreshCatalog,
    SearchCatalog,
)
from omnis.modules.settings.provider_key_models import Identity, KeyDTO, PositiveRevision
from omnis.modules.settings.provider_key_service import ConnectionRevision
from omnis.supervisor.model_relay import RelayFailure

if TYPE_CHECKING:
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest


class CatalogRequest(KeyDTO):
    command_id: Identity
    connection: ConnectionRevision
    generation: int = Field(strict=True, ge=0)
    owner_epoch: PositiveRevision
    execution_owner_id: Identity
    deadline: datetime


class CatalogResult(KeyDTO):
    command_id: Identity
    connection: ConnectionRevision
    state: Literal["READY", "PARTIAL", "FAILED"]
    reason: CatalogReason | None
    entries: list[CatalogModel] = Field(max_length=8192)


async def request_record(
    runtime: "ApiKeyModelTest", db: AsyncConnection, request: SearchCatalog
) -> CatalogRequest | None:
    if request.catalog_command_id is not None:
        raw = await runtime.latest(db, "catalog-request", request.catalog_command_id)
        if raw is None:
            raise store.ModelConflict("NOT_FOUND")
    else:
        raw = (
            await db.execute(
                text(
                    "SELECT payload FROM model_record_v2 WHERE instance_id=:instance AND kind='catalog-request' "
                    "AND payload->'connection'->>'connection_id'=:connection ORDER BY created_at DESC LIMIT 1"
                ),
                {"instance": runtime.instance, "connection": request.connection_id},
            )
        ).scalar_one_or_none()
    if raw is None:
        return None
    record = CatalogRequest.model_validate_json(json.dumps(raw))
    if (
        record.connection.connection_id != request.connection_id
        or record.connection.revision != request.connection_revision
    ):
        if request.catalog_command_id is not None:
            raise store.ModelConflict("REVISION_CONFLICT")
        return None
    return record


async def view(runtime: "ApiKeyModelTest", request: SearchCatalog) -> CatalogView:
    async with runtime.service.engine.connect() as db:
        connections = await runtime.settings.connections(db)
        current = next((x for x in connections if x.connection_id == request.connection_id), None)
        if current is None:
            raise store.ModelConflict("CONNECTION_UNAVAILABLE")
        record = await request_record(runtime, db, request)
        state: Literal["NOT_REQUESTED", "PENDING", "READY", "PARTIAL", "FAILED", "STALE"] = (
            "NOT_REQUESTED"
        )
        reason: CatalogReason | None = None
        entries: list[CatalogModel] = []
        if record is not None:
            raw = await runtime.latest(db, "catalog-result", record.command_id)
            if raw is not None:
                result = CatalogResult.model_validate(raw)
                if result.connection != record.connection:
                    raise store.ModelConflict("REF_UNAVAILABLE")
                state, reason, entries = result.state, result.reason, result.entries
            elif record.owner_epoch != runtime.settings.epoch or record.deadline <= datetime.now(
                UTC
            ):
                state, reason = "FAILED", "OWNER_LOST"
            else:
                state = "PENDING"
        if (
            not current.enabled
            or current.revision != request.connection_revision
            or (record is not None and record.connection != current)
        ):
            state, reason, entries = "STALE", "CONNECTION_STALE", []
        query = request.query.casefold()
        entries = sorted(
            (
                x
                for x in entries
                if query in x.model.casefold()
                or (x.name is not None and query in x.name.casefold())
            ),
            key=lambda x: x.model,
        )
        selected = entries[request.offset : request.offset + 16]
        return CatalogView(
            connection_id=request.connection_id,
            connection_revision=request.connection_revision,
            provider=current.provider,
            catalog_command_id=record.command_id if record else None,
            state=state,
            reason=reason,
            query=request.query,
            offset=request.offset,
            next_offset=request.offset + 16
            if request.offset + len(selected) < len(entries)
            else None,
            total=len(entries),
            entries=selected,
        )


async def handle(runtime: "ApiKeyModelTest", command: CatalogControl) -> dict[str, object]:
    request = command.request
    if isinstance(request, SearchCatalog):
        return (await view(runtime, request)).model_dump(mode="json")
    identity = request.command_id
    digest = store.digest(command.model_dump(mode="json"))
    search = SearchCatalog(
        action="search",
        connection_id=request.connection_id,
        connection_revision=request.connection_revision,
        catalog_command_id=identity
        if isinstance(request, RefreshCatalog)
        else request.catalog_command_id,
    )
    async with runtime.settings.lock:
        async with runtime.service.engine.connect() as db:
            repeated, _ = await store.replay(db, runtime.instance, identity, digest)
        if repeated:
            return (await view(runtime, search)).model_dump(mode="json")
        if runtime.closing or runtime.settlement_failed:
            raise store.ModelConflict("CONTROL_UNAVAILABLE")
        status = await runtime.service.owned_status(runtime.settings.owner, runtime.settings.epoch)
        async with runtime.service.admission(
            status.generation, runtime.settings.owner, runtime.settings.epoch
        ) as db:
            connection = await runtime.settings.require_connection(
                db, request.connection_id, request.connection_revision
            )
            if isinstance(request, CancelCatalog):
                record = await request_record(runtime, db, search)
                if (
                    record is None
                    or await runtime.latest(db, "catalog-result", record.command_id) is not None
                ):
                    raise store.ModelConflict("OPERATION_FINISHED")
                if record.owner_epoch != runtime.settings.epoch:
                    raise store.ModelConflict("OPERATION_FINISHED")
            else:
                await runtime.require_idle(db)
                record = CatalogRequest(
                    command_id=identity,
                    connection=connection,
                    generation=status.generation,
                    owner_epoch=runtime.settings.epoch,
                    execution_owner_id=str(runtime.settings.owner),
                    deadline=datetime.now(UTC) + timedelta(seconds=15),
                )
                await store.put(
                    db, runtime.instance, "catalog-request", record.model_dump(mode="json")
                )
                await store.relay_scope(
                    db,
                    {
                        "instance_id": runtime.instance,
                        "kind": "METADATA_COMMAND",
                        "id": identity,
                        "execution_owner_id": record.execution_owner_id,
                        "generation": record.generation,
                        "owner_epoch": record.owner_epoch,
                        "cancel_epoch": 1,
                        "deadline": record.deadline.isoformat(),
                        "provider": connection.provider,
                    },
                    allocate=True,
                )
            await store.command(
                db,
                runtime.instance,
                identity,
                digest,
                "cancel" if isinstance(request, CancelCatalog) else "refresh",
                None,
            )
        if isinstance(request, RefreshCatalog):
            runtime.spawn(refresh(runtime, record))
        else:
            for task in runtime.tasks:
                task.cancel()
    if isinstance(request, CancelCatalog) and not await runtime.drain_models():
        raise store.ModelConflict("CONTROL_UNAVAILABLE")
    return (await view(runtime, search)).model_dump(mode="json")


async def refresh(runtime: "ApiKeyModelTest", request: CatalogRequest) -> None:
    ingest = CatalogIngest(request.connection.provider)
    reason: CatalogReason | None = None
    try:
        async with asyncio.timeout(max(0, (request.deadline - datetime.now(UTC)).total_seconds())):
            secret = await asyncio.to_thread(
                runtime.settings.vault.get, request.connection.credential(runtime.instance)
            )
            offset: int | None = 0 if request.connection.provider == "openrouter" else None
            while True:
                remaining = 16777216 - ingest.bytes
                if remaining <= 0:
                    ingest.reason = "CATALOG_LIMIT"
                    break
                raw, size = await runtime.sender.metadata_page(
                    ENDPOINTS[request.connection.provider],
                    secret,
                    lambda: runtime.metadata_guard(
                        request.command_id,
                        request.connection,
                        request.generation,
                        "catalog-request",
                    ),
                    offset,
                    min(2097152, remaining),
                )
                ingest.bytes += size
                if ingest.bytes > 16777216:
                    ingest.reason = "CATALOG_LIMIT"
                    break
                offset = ingest.add(raw, secret)
                if offset is None:
                    break
    except asyncio.CancelledError:
        reason = "CANCELLED_OR_STOPPED"
        raise
    except (ValueError, OSError, TimeoutError):
        reason = "METADATA_UNAVAILABLE"
    finally:
        try:
            await runtime.retire_relay()
        except (RelayFailure, OSError, ValueError, TimeoutError):
            runtime.settlement_failed = True
        if runtime.sender.transport.backend.relay.failed or runtime.settlement_failed:
            runtime.settlement_failed = True
            raise RelayFailure("RELAY_CONTROL_UNCERTAIN")
        reason = reason or ingest.reason
        result = CatalogResult(
            command_id=request.command_id,
            connection=request.connection,
            state="READY"
            if ingest.complete and reason is None
            else "PARTIAL"
            if ingest.entries
            else "FAILED",
            reason=reason,
            entries=list(ingest.entries.values()),
        )
        async with runtime.service.engine.begin() as db:
            await store.put(db, runtime.instance, "catalog-result", result.model_dump(mode="json"))
