"""Local private candidate consumer; no publication, runtime, provider or target IO."""

import argparse
import asyncio
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine

from . import candidate_store as store
from .candidate_material import capture, finalize, private_root, read_material
from .catalog_models import CatalogError
from .catalog_schema import bounded, canonical, load_json
from .skill_catalog import compile_catalog, read_file

COMPILER_REVISION = "6b38fc3806b365643abb65d1d6e94c2342d73608"


def uuid_string(value: object) -> str:
    if type(value) is not str:
        raise CatalogError("INVALID_REQUEST")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise CatalogError("INVALID_REQUEST") from None
    return value


def valid_ref(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "revision", "digest"}:
        raise CatalogError("INVALID_REQUEST")
    uuid_string(value["id"])
    if (
        type(value["revision"]) is not int
        or not 1 <= value["revision"] < 2147483647
        or type(value["kind"]) is not str
        or type(value["digest"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", value["digest"]) is None
    ):
        raise CatalogError("INVALID_REQUEST")
    return value


def validate_request(operation: str, value: object) -> dict[str, object]:
    fields = {
        "capture": {"author_kind", "packages", "profile"},
        "review": {"draft_ref", "source_draft_refs"},
        "reject": {"draft_ref", "source_draft_refs"},
    }
    if operation not in fields or not isinstance(value, dict):
        raise CatalogError("INVALID_REQUEST")
    if set(value) != {"schema_version", "owner_id", "command_id"} | fields[operation]:
        raise CatalogError("INVALID_REQUEST")
    bounded(value)
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise CatalogError("INVALID_REQUEST")
    uuid_string(value["owner_id"])
    uuid_string(value["command_id"])
    if operation == "capture":
        packages = value["packages"]
        if (
            value["author_kind"] not in ("OPERATOR", "AI", "IMPORT")
            or not isinstance(packages, list)
            or not 1 <= len(packages) <= 128
        ):
            raise CatalogError("INVALID_REQUEST")
        for path in [*packages, value["profile"]]:
            if type(path) is not str or not Path(path).is_absolute() or "\x00" in path:
                raise CatalogError("INVALID_REQUEST")
    else:
        valid_ref(value["draft_ref"])
        refs = value["source_draft_refs"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 128:
            raise CatalogError("INVALID_REQUEST")
        for ref in refs:
            valid_ref(ref)
    # Reject invalid Unicode before any PostgreSQL write or replay.
    raw = canonical(value)
    if b"\x00" in raw or len(raw) > 1048576 or "\u0000" in raw.decode():
        raise CatalogError("INVALID_REQUEST")
    return value


def payload(record: dict[str, object]) -> dict[str, object]:
    value = record["payload"]
    if not isinstance(value, dict):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return value


class CandidateCatalog:
    def __init__(self, engine: AsyncEngine, root: Path) -> None:
        self.engine = engine
        self.root = private_root(Path(root))

    async def dispatch(self, operation: str, request: object) -> dict[str, object]:
        value = validate_request(operation, request)
        async with asyncio.timeout(15):
            result = await self._dispatch(operation, value)
        if result.get("status") == "BLOCKED":
            reason = result["reason"]
            if not isinstance(reason, str):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            raise CatalogError(reason)
        return result

    async def sources(
        self, connection: AsyncConnection, owner: str, value: dict[str, object]
    ) -> tuple[str, list[dict[str, object]]]:
        primary = valid_ref(value["draft_ref"])
        group, record = await store.get(connection, owner, primary)
        if record["kind"] != "source-draft" or payload(record)["source_kind"] != "profile":
            raise CatalogError("SOURCE_DRAFT_MISMATCH")
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT envelope FROM catalog_record WHERE group_id=:group AND owner_id=:owner AND kind='source-draft' ORDER BY id"
                    ),
                    {"group": group, "owner": owner},
                )
            )
            .scalars()
            .all()
        )
        records = [store.checked(row) for row in rows]
        expected = sorted([store.reference(r) for r in records], key=lambda ref: str(ref["id"]))
        supplied = value["source_draft_refs"]
        if (
            not isinstance(supplied, list)
            or sorted(supplied, key=lambda ref: str(ref["id"])) != expected
        ):
            raise CatalogError("SOURCE_DRAFT_MISMATCH")
        return group, records

    async def _dispatch(self, operation: str, value: dict[str, object]) -> dict[str, object]:
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        result: dict[str, object]
        reservations: list[dict[str, object]] = []
        # Review reservations commit in their own transaction before semantic checker work.
        if operation == "review":
            async with self.engine.begin() as connection:
                await store.lock(connection, "owner:" + owner)
                prior = await store.replay(connection, owner, command, operation, value)
                if prior is not None:
                    return prior
                group, records = await self.sources(connection, owner, value)
                if await self.rejected(connection, owner, group):
                    raise CatalogError("CANDIDATE_REJECTED")
                sources = [payload(record) for record in records]
                read_material(self.root, "drafts", group, sources)
                identities: list[tuple[str, str, str, str]] = []
                for record in records:
                    source = payload(record)
                    namespace = source.get("package_key", "@profile")
                    sha = source.get("package_digest", record["digest"])
                    items = source["identities"]
                    if (
                        not isinstance(namespace, str)
                        or not isinstance(sha, str)
                        or not isinstance(items, list)
                    ):
                        raise CatalogError("STORAGE_INCOMPATIBLE")
                    for item in items:
                        if (
                            not isinstance(item, list)
                            or len(item) != 2
                            or not all(isinstance(x, str) for x in item)
                        ):
                            raise CatalogError("STORAGE_INCOMPATIBLE")
                        identities.append((namespace, item[0], item[1], sha))
                reservations = await store.reserve(
                    connection, owner, str(valid_ref(value["draft_ref"])["id"]), identities
                )
        async with self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            prior = await store.replay(connection, owner, command, operation, value)
            if prior is not None:
                return prior
            if operation == "capture":
                packages, profile = value["packages"], value["profile"]
                if (
                    not isinstance(packages, list)
                    or not all(isinstance(p, str) for p in packages)
                    or not isinstance(profile, str)
                ):
                    raise CatalogError("INVALID_REQUEST")
                material, sources, material_digest = capture(packages, profile)
                group = str(uuid4())
                finalized = finalize(self.root, "drafts", group, material)
                records = [
                    store.envelope(
                        "source-draft",
                        {
                            **source,
                            "created_by": owner,
                            "author_kind": value["author_kind"],
                            "material_digest": material_digest,
                        },
                    )
                    for source in sources
                ]
                read_material(self.root, "drafts", finalized.name, [payload(r) for r in records])
                for record in records:
                    await store.put(connection, owner, group, record)
                result = {
                    "draft_ref": store.reference(records[-1]),
                    "source_draft_refs": sorted(
                        [store.reference(r) for r in records], key=lambda r: str(r["id"])
                    ),
                    "material_digest": material_digest,
                }
            else:
                group, records = await self.sources(connection, owner, value)
                sources = [payload(r) for r in records]
                read_material(self.root, "drafts", group, sources)
                if operation == "reject":
                    record = store.envelope(
                        "candidate-rejection",
                        {
                            "draft_ref": value["draft_ref"],
                            "source_draft_refs": value["source_draft_refs"],
                            "created_by": owner,
                        },
                    )
                    await store.put(connection, owner, group, record)
                    result = {"state": "REJECTED", "rejection_ref": store.reference(record)}
                else:
                    if await self.rejected(connection, owner, group):
                        raise CatalogError("CANDIDATE_REJECTED")
                    try:
                        packages = tuple(
                            self.root / "drafts" / group / str(s["prefix"])
                            for s in sources
                            if s["source_kind"] == "package"
                        )
                        compiled = compile_catalog(
                            packages, self.root / "drafts" / group / "profile.yaml"
                        )
                        status, reason = "STATIC_PASS", None
                        index = {
                            "refs": [asdict(r) for r in compiled.refs],
                            "steps": [{"id": s.id, "handler": s.handler} for s in compiled.steps],
                        }
                        index_digest = compiled.resolved_index_digest
                    except CatalogError as error:
                        status, reason, index, index_digest = "BLOCKED", error.reason, None, None
                    record = store.envelope(
                        "technical-review",
                        {
                            "draft_ref": value["draft_ref"],
                            "source_draft_refs": value["source_draft_refs"],
                            "material_digest": sources[0]["material_digest"],
                            "resolved_index_digest": index_digest,
                            "resolved_index": index,
                            "candidate_refs": reservations,
                            "dependency_closure_refs": [],
                            "compiler_revision": COMPILER_REVISION,
                            "checker": "omnis-static-v1",
                            "protocol": "b06a-static-v1",
                            "author_kind": sources[0]["author_kind"],
                            "created_by": owner,
                            "status": status,
                            "reason": reason,
                        },
                    )
                    await store.put(connection, owner, group, record)
                    result = {
                        "technical_review_ref": store.reference(record),
                        "status": status,
                        "reason": reason,
                        "source_draft_refs": value["source_draft_refs"],
                        "material_digest": sources[0]["material_digest"],
                        "candidate_refs": reservations,
                        "resolved_index_digest": index_digest,
                    }
            await store.complete(connection, owner, command, operation, value, result)
        # Read back the exact committed command on a fresh connection.
        async with self.engine.connect() as connection:
            readback = await store.replay(connection, owner, command, operation, value)
        if readback is None:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        return readback

    async def rejected(self, connection: AsyncConnection, owner: str, group: str) -> bool:
        return (
            await connection.scalar(
                text(
                    "SELECT 1 FROM catalog_record WHERE owner_id=:owner AND group_id=:group AND kind='candidate-rejection' LIMIT 1"
                ),
                {"owner": owner, "group": group},
            )
            is not None
        )


def main(argv: list[str] | None = None) -> int:
    class SafeParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = SafeParser()
    parser.add_argument("operation", choices=("capture", "review", "reject"))
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog-root", required=True)
    try:
        args = parser.parse_args(argv)
        request = load_json(read_file(Path(args.request)))
        url = os.environ.get("OMNIS_DATABASE_URL")
        if not url:
            raise CatalogError("DATABASE_UNAVAILABLE")

        async def run() -> dict[str, object]:
            engine = database_engine(url)
            try:
                return await CandidateCatalog(engine, Path(args.catalog_root)).dispatch(
                    args.operation, request
                )
            finally:
                await engine.dispose()

        print(canonical(asyncio.run(run())).decode())
        return 0
    except CatalogError as error:
        reason = error.reason
    except (SQLAlchemyError, TimeoutError):
        reason = "DATABASE_UNAVAILABLE"
    except (OSError, UnicodeError, RecursionError, ValueError):
        reason = "INPUT_UNAVAILABLE"
    print(canonical({"status": "BLOCKED", "reason": reason}).decode(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
