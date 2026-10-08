"""Immutable PostgreSQL ledger. All record reads verify the canonical envelope."""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .candidate_material import digest
from .catalog_models import CatalogError
from .catalog_schema import canonical


def envelope(kind: str, payload: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": 1,
        "kind": kind,
        "id": str(uuid4()),
        "revision": 1,
        "payload": payload,
    }
    result["digest"] = digest(canonical(result))
    return result


def reference(record: dict[str, object]) -> dict[str, object]:
    return {key: record[key] for key in ("kind", "id", "revision", "digest")}


async def lock(connection: AsyncConnection, key: str) -> None:
    await connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
    )


async def put(
    connection: AsyncConnection, owner: str, group: str, record: dict[str, object]
) -> None:
    await connection.execute(
        text(
            "INSERT INTO catalog_record "
            "(id, owner_id, group_id, kind, revision, digest, envelope) "
            "VALUES (:id,:owner,:group,:kind,:revision,:digest,CAST(:envelope AS jsonb))"
        ),
        {
            "id": record["id"],
            "owner": owner,
            "group": group,
            "kind": record["kind"],
            "revision": record["revision"],
            "digest": record["digest"],
            "envelope": canonical(record).decode(),
        },
    )


async def get(
    connection: AsyncConnection, owner: str, ref: dict[str, object]
) -> tuple[str, dict[str, object]]:
    row = (
        (
            await connection.execute(
                text("SELECT group_id, owner_id, envelope FROM catalog_record WHERE id=:id"),
                {"id": ref["id"]},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or str(row["owner_id"]) != owner:
        raise CatalogError("REF_UNAVAILABLE")
    record = checked(row["envelope"])
    if reference(record) != ref:
        raise CatalogError("REF_MISMATCH")
    return str(row["group_id"]), record


def checked(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "kind",
        "id",
        "revision",
        "payload",
        "digest",
    }:
        raise CatalogError("STORAGE_INCOMPATIBLE")
    if value["digest"] != digest(canonical({k: v for k, v in value.items() if k != "digest"})):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return value


async def replay(
    connection: AsyncConnection, owner: str, command: str, operation: str, request: object
) -> dict[str, object] | None:
    row = (
        (
            await connection.execute(
                text(
                    "SELECT operation, request_digest, result FROM catalog_command "
                    "WHERE owner_id=:owner AND command_id=:command"
                ),
                {"owner": owner, "command": command},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if row["operation"] != operation or row["request_digest"] != digest(canonical(request)):
        raise CatalogError("COMMAND_CONFLICT")
    result = row["result"]
    if not isinstance(result, dict):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return result


async def complete(
    connection: AsyncConnection,
    owner: str,
    command: str,
    operation: str,
    request: object,
    result: dict[str, object],
) -> None:
    await connection.execute(
        text(
            "INSERT INTO catalog_command VALUES "
            "(:owner,:command,:operation,:digest,CAST(:result AS jsonb))"
        ),
        {
            "owner": owner,
            "command": command,
            "operation": operation,
            "digest": digest(canonical(request)),
            "result": canonical(result).decode(),
        },
    )


async def reserve(
    connection: AsyncConnection, owner: str, draft: str, identities: list[tuple[str, str, str, str]]
) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    for package, kind, key, sha in sorted(identities):
        await lock(connection, "identity:" + canonical([package, kind, key]).decode())
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT id, owner_id FROM catalog_identity "
                        "WHERE package_key=:package AND entity_kind=:kind AND entity_key=:key"
                    ),
                    {"package": package, "kind": kind, "key": key},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            identity = uuid4()
            await connection.execute(
                text("INSERT INTO catalog_identity VALUES (:id,:owner,:package,:kind,:key)"),
                {"id": identity, "owner": owner, "package": package, "kind": kind, "key": key},
            )
        else:
            if str(row["owner_id"]) != owner or type(row["id"]) is not UUID:
                raise CatalogError("IDENTITY_OWNERSHIP")
            identity = row["id"]
        revision = await connection.scalar(
            text("SELECT revision FROM catalog_reservation WHERE id=:id AND digest=:digest"),
            {"id": identity, "digest": sha},
        )
        if revision is None:
            maximum = await connection.scalar(
                text("SELECT COALESCE(max(revision),0) FROM catalog_reservation WHERE id=:id"),
                {"id": identity},
            )
            if type(maximum) is not int:
                raise CatalogError("STORAGE_INCOMPATIBLE")
            revision = maximum + 1
            await connection.execute(
                text("INSERT INTO catalog_reservation VALUES (:id,:revision,:digest,:draft)"),
                {"id": identity, "revision": revision, "digest": sha, "draft": draft},
            )
        if type(revision) is not int:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        refs.append({"kind": kind, "id": str(identity), "revision": revision, "digest": sha})
    return refs
