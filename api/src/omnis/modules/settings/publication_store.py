"""Publication head updates in the owning catalog transaction and owner lock."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from . import candidate_store as store
from .candidate_catalog import payload, valid_ref
from .catalog_models import CatalogError


def profile_key(record: dict[str, object]) -> str:
    body = payload(record)
    key = body.get("key")
    if (
        record["kind"] != "source-draft"
        or body.get("source_kind") != "profile"
        or not isinstance(key, str)
    ):
        raise CatalogError("SOURCE_DRAFT_MISMATCH")
    return key


async def capture_head(connection: AsyncConnection, owner: str, draft: dict[str, object]) -> None:
    await connection.execute(
        text(
            "INSERT INTO catalog_publication_head (owner_id,profile_key,generation,draft_id,publication_id) "
            "VALUES (:owner,:key,1,:draft,NULL) ON CONFLICT (owner_id,profile_key) DO UPDATE SET "
            "generation=catalog_publication_head.generation+1,draft_id=EXCLUDED.draft_id,publication_id=NULL"
        ),
        {"owner": owner, "key": profile_key(draft), "draft": draft["id"]},
    )


async def head(
    connection: AsyncConnection, owner: str, draft: dict[str, object]
) -> dict[str, object]:
    key = profile_key(draft)
    row = (
        (
            await connection.execute(
                text(
                    "SELECT generation,draft_id,publication_id FROM catalog_publication_head "
                    "WHERE owner_id=:owner AND profile_key=:key"
                ),
                {"owner": owner, "key": key},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise CatalogError("HEAD_UNAVAILABLE")
    generation = row["generation"]
    if type(generation) is not int or not 1 <= generation < 2**63:
        raise CatalogError("STORAGE_INCOMPATIBLE")
    refs: dict[str, object] = {}
    for field, column, kind in (
        ("draft_ref", "draft_id", "source-draft"),
        ("publication_ref", "publication_id", "catalog-publication"),
    ):
        if row[column] is None:
            refs[field] = None
            continue
        record_row = (
            (
                await connection.execute(
                    text("SELECT owner_id,envelope FROM catalog_record WHERE id=:id"),
                    {"id": row[column]},
                )
            )
            .mappings()
            .one_or_none()
        )
        if record_row is None or str(record_row["owner_id"]) != owner:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        record = store.checked(record_row["envelope"])
        if record["kind"] != kind:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        refs[field] = valid_ref(store.reference(record))
    return {"generation": generation, "profile_key": key, **refs}


def check_head(current: dict[str, object], value: dict[str, object]) -> None:
    if (
        current["generation"] != value["expected_head_generation"]
        or current["draft_ref"] != value["draft_ref"]
    ):
        raise CatalogError("STALE_HEAD")


async def promote(
    connection: AsyncConnection,
    owner: str,
    key: str,
    value: dict[str, object],
    publication: dict[str, object],
) -> int:
    generation = await connection.scalar(
        text(
            "UPDATE catalog_publication_head SET generation=generation+1,publication_id=:publication "
            "WHERE owner_id=:owner AND profile_key=:key AND generation=:generation AND draft_id=:draft "
            "RETURNING generation"
        ),
        {
            "owner": owner,
            "key": key,
            "generation": value["expected_head_generation"],
            "draft": valid_ref(value["draft_ref"])["id"],
            "publication": publication["id"],
        },
    )
    if type(generation) is not int:
        raise CatalogError("STALE_HEAD")
    return generation
