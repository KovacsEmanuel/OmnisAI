"""Owned lifecycle storage. No catalog inserts or mutable record envelopes."""

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.settings import candidate_store as catalog
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping, record, ref


async def lock(connection: AsyncConnection, owner: str) -> None:
    await catalog.lock(connection, "managed-owner:" + owner)


async def put(connection: AsyncConnection, owner: str, run: str, value: object) -> None:
    item = record(value)
    await connection.execute(
        sql(
            "INSERT INTO managed_record(id,owner_id,run_id,envelope) VALUES (:id,:owner,:run,CAST(:body AS jsonb))"
        ),
        {"id": item["id"], "owner": owner, "run": run, "body": canonical(item).decode()},
    )


async def by_id(
    connection: AsyncConnection, owner: str, run: str, identity: object
) -> dict[str, object]:
    row = (
        (
            await connection.execute(
                sql("SELECT owner_id,run_id,envelope FROM managed_record WHERE id=:id"),
                {"id": identity},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or str(row["owner_id"]) != owner or str(row["run_id"]) != run:
        raise CatalogError("REF_UNAVAILABLE")
    result = record(row["envelope"])
    if result["id"] != str(identity):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return result


async def get(
    connection: AsyncConnection, owner: str, run: str, reference: object
) -> dict[str, object]:
    checked = ref(reference)
    item = await by_id(connection, owner, run, checked["id"])
    if canonical(catalog.reference(item)) != canonical(checked):
        raise CatalogError("REF_MISMATCH")
    return item


async def state(
    connection: AsyncConnection, owner: str, *, command: str | None = None, manifest: object = None
) -> dict[str, object]:
    args: dict[str, object]
    if command is not None:
        query, args = "command_id=:value", {"owner": owner, "value": command}
    else:
        query, args = (
            "manifest_id=:value",
            {"owner": owner, "value": ref(manifest, "launch-manifest")["id"]},
        )
    row = (
        (
            await connection.execute(
                sql("SELECT * FROM managed_run WHERE owner_id=:owner AND " + query), args
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise CatalogError("REF_UNAVAILABLE")
    # Driver UUIDs are normalized only for explicitly UUID-backed columns.
    result = mapping(dict(row))
    for field in (
        "run_id",
        "owner_id",
        "command_id",
        "manifest_id",
        "binding_id",
        "final_id",
        "runtime_boot",
        "ticket",
    ):
        if result[field] is not None:
            result[field] = str(result[field])
    if manifest is not None:
        await get(connection, owner, str(result["run_id"]), manifest)
    return result


async def owned(
    connection: AsyncConnection, owner: str, reference: object
) -> tuple[str, dict[str, object]]:
    from omnis.modules.settings.candidate_catalog import uuid_string

    checked = ref(reference)
    row = (
        await connection.execute(
            sql("SELECT run_id FROM managed_record WHERE owner_id=:owner AND id=:id"),
            {"owner": owner, "id": checked["id"]},
        )
    ).scalar_one_or_none()
    if row is None:
        raise CatalogError("REF_UNAVAILABLE")
    run = uuid_string(str(row))
    return run, await get(connection, owner, run, checked)


async def graph(connection: AsyncConnection, owner: str, run: str) -> list[dict[str, object]]:
    rows = (
        (
            await connection.execute(
                sql(
                    "SELECT envelope FROM managed_record WHERE owner_id=:owner AND run_id=:run ORDER BY id"
                ),
                {"owner": owner, "run": run},
            )
        )
        .scalars()
        .all()
    )
    return [record(r) for r in rows]


async def command_receipt(
    connection: AsyncConnection, owner: str, command: str
) -> dict[str, object]:
    rows = (
        (
            await connection.execute(
                sql(
                    "SELECT envelope FROM managed_record WHERE owner_id=:owner AND envelope->>'kind'='contract-input-command' AND envelope->'payload'->>'command_id'=:command"
                ),
                {"owner": owner, "command": command},
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise CatalogError("REF_UNAVAILABLE")
    if len(rows) != 1:
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return record(rows[0], "contract-input-command")


async def command_replay(
    connection: AsyncConnection, owner: str, command: str, operation: str, request: object
) -> dict[str, object] | None:
    from hashlib import sha256

    try:
        receipt = await command_receipt(connection, owner, command)
    except CatalogError as error:
        if error.reason == "REF_UNAVAILABLE":
            return None
        raise
    body = mapping(receipt["payload"])
    if (
        body["operation"] != operation
        or body["request_digest"] != sha256(canonical(request)).hexdigest()
    ):
        raise CatalogError("COMMAND_CONFLICT")
    result = mapping(body["result_refs"])
    for reference in result.values():
        await owned(connection, owner, reference)
    return result


async def command_complete(
    connection: AsyncConnection,
    owner: str,
    run: str,
    command: str,
    operation: str,
    request: object,
    result_refs: dict[str, object],
) -> None:
    from hashlib import sha256

    await put(
        connection,
        owner,
        run,
        catalog.envelope(
            "contract-input-command",
            {
                "version": 1,
                "owner_id": owner,
                "command_id": command,
                "operation": operation,
                "request_digest": sha256(canonical(request)).hexdigest(),
                "result_refs": result_refs,
            },
        ),
    )
