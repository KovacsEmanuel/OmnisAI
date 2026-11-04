"""Local private candidate consumer; no publication, runtime, provider or target IO."""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic_ns
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine

from . import candidate_store as store
from .candidate_index import (
    INDEX_FILE,
    bind_catalog,
    compile_material,
    index_source,
    resolved_index,
)
from .candidate_material import (
    MAX_SOURCE_PACKAGES,
    capture,
    digest,
    finalize,
    private_root,
    read_material,
)
from .candidate_resolution import load_dependencies
from .catalog_models import CatalogError, CompiledCatalog
from .catalog_schema import bounded, canonical, pairs
from .skill_catalog import evaluate_pure, read_file

# Conservative trusted behavior closure shared by STATIC compilation and PURE evaluation.
# Labels are package-relative; neither checkout paths nor Git metadata enter the preimage.
# Hash source bytes, not an embedded revision literal: there is no self-hash fixed point.
BEHAVIOR_FILES = (
    "settings/candidate_catalog.py",
    "settings/candidate_index.py",
    "settings/candidate_material.py",
    "settings/candidate_store.py",
    "settings/candidate_resolution.py",
    "settings/catalog_models.py",
    "settings/catalog_schema.py",
    "settings/skill_catalog.py",
    "settings/publication_models.py",  # requirement_conditions -> exact -> clean_text
    "tasks/module_registry.py",
    "tasks/contract_case_input.py",
    "tasks/managed_contract.py",  # Compiler applicability validator and its local helpers.
)


def behavior_revision(domain: str) -> str:
    root = Path(__file__).parent.parent
    manifest = {
        "domain": domain,
        "files": {name: digest(read_file(root / name)) for name in BEHAVIOR_FILES},
    }
    return "sha256:" + digest(canonical(manifest))


# Process-start identities assume installed trusted code is immutable while serving.
# Protocol/schema lineage remains in checker/protocol; it is not code identity.
COMPILER_REVISION = behavior_revision("omnis-candidate-compiler-v1")
EVALUATOR_REVISION = behavior_revision("omnis-candidate-evaluator-v1")

# Exact bf6d197 V1 reader compatibility, never stamped onto new artifacts.
LEGACY_COMPILER_REVISION = "sha256:7958c3676989ca829d80ceac99284118ad6b08af7994f0e43211a8b06ad8733b"
LEGACY_EVALUATOR_REVISION = (
    "sha256:47fddea827616d5fe1779e653c71e487d072b9c11ccde3d4598bc2ec8715b6d9"
)


_COMPILER_ONLY = object()


def readable_revisions(
    compiler: object, evaluator: object = _COMPILER_ONLY, *, legacy: bool = False
) -> bool:
    return (
        compiler == COMPILER_REVISION
        and (evaluator is _COMPILER_ONLY or evaluator == EVALUATOR_REVISION)
    ) or (
        legacy
        and compiler == LEGACY_COMPILER_REVISION
        and (evaluator is _COMPILER_ONLY or evaluator == LEGACY_EVALUATOR_REVISION)
    )


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
        "freeze": {"draft_ref", "source_draft_refs", "technical_review_ref"},
        "evaluate": {"snapshot_ref", "evaluation_kind", "input"},
        "readback": {"snapshot_ref"},
        "admit-evaluation-capture": {"snapshot_ref", "value"},
        "admit-evaluation-records": {"snapshot_ref", "value"},
    }
    capture_v2 = (
        isinstance(value, dict)
        and type(value.get("schema_version")) is int
        and value.get("schema_version") == 2
        and operation in ("admit-evaluation-capture", "evaluate")
    )
    records_v3 = (
        isinstance(value, dict)
        and type(value.get("schema_version")) is int
        and value.get("schema_version") == 3
        and operation in ("admit-evaluation-records", "evaluate")
    )
    if (capture_v2 or records_v3) and operation == "evaluate":
        fields["evaluate"] = {"snapshot_ref", "evaluation_kind", "input_ref"}
    if operation not in fields or not isinstance(value, dict):
        raise CatalogError("INVALID_REQUEST")
    common = {"schema_version", "owner_id"}
    if operation != "readback":
        common.add("command_id")
    if set(value) != common | fields[operation]:
        raise CatalogError("INVALID_REQUEST")
    try:
        bounded(value)
    except CatalogError as error:
        if error.reason == "INVALID_TYPE":
            raise CatalogError("INVALID_REQUEST") from None
        raise

    def check_text(item: object) -> None:
        if isinstance(item, str):
            if "\x00" in item:
                raise CatalogError("INVALID_REQUEST")
            try:
                item.encode("utf-8")
            except UnicodeError:
                raise CatalogError("INVALID_REQUEST") from None
        elif isinstance(item, dict):
            for key, child in item.items():
                check_text(key)
                check_text(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check_text(child)

    check_text(value)
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != (3 if records_v3 else 2 if capture_v2 else 1)
        or (operation == "admit-evaluation-capture" and not capture_v2)
        or (operation == "admit-evaluation-records" and not records_v3)
    ):
        raise CatalogError("INVALID_REQUEST")
    uuid_string(value["owner_id"])
    if operation != "readback":
        uuid_string(value["command_id"])
    if operation == "capture":
        packages = value["packages"]
        if (
            value["author_kind"] not in ("OPERATOR", "AI", "IMPORT")
            or not isinstance(packages, list)
            or not 1 <= len(packages) <= 128
        ):
            raise CatalogError("INVALID_REQUEST")
        if len(packages) > MAX_SOURCE_PACKAGES:
            raise CatalogError("COUNT_LIMIT")
        for path in [*packages, value["profile"]]:
            if type(path) is not str or not Path(path).is_absolute() or "\x00" in path:
                raise CatalogError("INVALID_REQUEST")
    elif capture_v2 or records_v3:
        if valid_ref(value["snapshot_ref"])["kind"] != "candidate-snapshot":
            raise CatalogError("INVALID_REQUEST")
        if operation == "evaluate":
            if value["evaluation_kind"] not in ("STATIC", "PURE") or valid_ref(value["input_ref"])[
                "kind"
            ] != ("contract-case-records" if records_v3 else "contract-case-input"):
                raise CatalogError("INVALID_REQUEST")
        elif not isinstance(value["value"], dict):
            raise CatalogError("INVALID_REQUEST")
    elif operation in ("evaluate", "readback"):
        valid_ref(value["snapshot_ref"])
        if operation == "evaluate" and (
            value["evaluation_kind"] not in ("STATIC", "PURE")
            or (value["evaluation_kind"] == "STATIC" and value["input"] is not None)
            or (value["evaluation_kind"] == "PURE" and not isinstance(value["input"], dict))
        ):
            raise CatalogError("INVALID_REQUEST")
    else:
        if operation == "freeze":
            valid_ref(value["technical_review_ref"])
        valid_ref(value["draft_ref"])
        refs = value["source_draft_refs"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 128:
            raise CatalogError("INVALID_REQUEST")
        for ref in refs:
            valid_ref(ref)
    raw = canonical(value)
    if len(raw) > 1048576:
        raise CatalogError("INVALID_REQUEST")
    return value


def payload(record: dict[str, object]) -> dict[str, object]:
    value = record["payload"]
    if not isinstance(value, dict):
        raise CatalogError("STORAGE_INCOMPATIBLE")
    return value


def check_capture_admission(record: object, expected: dict[str, object]) -> None:
    """Pure shape/pin validation; the caller still owns ledger/group authority."""
    checked = store.checked(record)
    ref = valid_ref(store.reference(checked))
    body = payload(checked)
    for field, kind in (
        ("snapshot_ref", "candidate-snapshot"),
        ("procedure_ref", "procedure"),
        ("schema_ref", "schema"),
    ):
        if valid_ref(body.get(field))["kind"] != kind:
            raise CatalogError("EVALUATION_ADMISSION_MISMATCH")
    uuid_string(body.get("owner_id"))
    if (
        ref["kind"] != "evaluation-admission"
        or type(checked["schema_version"]) is not int
        or checked["schema_version"] != 1
        or ref["revision"] != 1
        or type(body.get("version")) is not int
        or body != expected
    ):
        raise CatalogError("EVALUATION_ADMISSION_MISMATCH")


def case_version(compiled: CompiledCatalog) -> int:
    from omnis.modules.tasks.contract_case_input import slot_contract

    return slot_contract([s.model_dump(mode="json") for s in compiled.slots])


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
        owner = uuid_string(value["owner_id"])
        if operation == "readback":
            async with self.engine.connect() as connection:
                return await self.snapshot_readback(
                    connection, owner, valid_ref(value["snapshot_ref"])
                )
        command = uuid_string(value["command_id"])
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
                if operation in ("admit-evaluation-capture", "admit-evaluation-records"):
                    await self.capture_readback(connection, owner, value, prior)
                if operation in ("freeze", "evaluate"):
                    ref = prior.get("snapshot_ref", value.get("snapshot_ref"))
                    await self.snapshot_readback(connection, owner, valid_ref(ref))
                return prior
            if operation in ("admit-evaluation-capture", "admit-evaluation-records"):
                result = await self.admit_evaluation_capture(connection, owner, value)
            elif operation == "evaluate":
                result = await self.evaluate(connection, owner, value)
            elif operation == "freeze":
                result = await self.freeze(connection, owner, value)
            elif operation == "capture":
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
                # Import at the capture seam: the consumer reuses this producer.
                from .publication_store import capture_head

                await capture_head(connection, owner, records[-1])
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
                    if await self.frozen_record(connection, owner, group) is not None:
                        raise CatalogError("CANDIDATE_FROZEN")
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
                    review_started = datetime.now(UTC).isoformat()
                    review_clock = monotonic_ns()
                    closure: list[dict[str, object]] = []
                    try:
                        compiled = await self.compile_pinned(
                            connection, owner, self.root / "drafts" / group, records, reservations
                        )
                        closure = list(compiled.dependency_closure_refs)
                        status, reason = "STATIC_PASS", None
                        index = resolved_index(compiled)
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
                            "dependency_closure_refs": closure,
                            "dependency_closure_digest": digest(canonical(closure)),
                            "reviewed_at": datetime.now(UTC).isoformat(),
                            "started_at": review_started,
                            "duration_ns": monotonic_ns() - review_clock,
                            "limits": {
                                "max_material_bytes": 8 * 1048576,
                                "dispatch_timeout_seconds": 15,
                            },
                            "resolution": "NO_MODEL",
                            "effective": None,
                            "compiler_revision": COMPILER_REVISION,
                            "checker": "omnis-api-key-core-v2"
                            if index is not None and index.get("catalog_schema_version") == 2
                            else "omnis-static-v1",
                            "protocol": "s1-api-key-core-static-v2"
                            if index is not None and index.get("catalog_schema_version") == 2
                            else "b06a-static-v1",
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
                        "reservations": reservations,
                        "resolved_index_digest": index_digest,
                    }
            await store.complete(connection, owner, command, operation, value, result)
        # Read back the exact committed command on a fresh connection.
        async with self.engine.connect() as connection:
            readback = await store.replay(connection, owner, command, operation, value)
            if readback is not None and operation in (
                "admit-evaluation-capture",
                "admit-evaluation-records",
            ):
                await self.capture_readback(connection, owner, value, readback)
            elif readback is not None and operation == "evaluate":
                await self.snapshot_readback(connection, owner, valid_ref(value["snapshot_ref"]))
        if readback is None:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        return readback

    async def frozen_record(
        self, connection: AsyncConnection, owner: str, group: str
    ) -> dict[str, object] | None:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT envelope FROM catalog_record WHERE owner_id=:owner AND group_id=:group AND kind='candidate-snapshot'"
                    ),
                    {"owner": owner, "group": group},
                )
            )
            .scalars()
            .all()
        )
        if len(rows) > 1:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        return store.checked(rows[0]) if rows else None

    async def review_record(
        self,
        connection: AsyncConnection,
        owner: str,
        group: str,
        value: dict[str, object],
        sources: list[dict[str, object]],
        *,
        read_only: bool = False,
    ) -> dict[str, object]:
        review_group, review = await store.get(
            connection, owner, valid_ref(value["technical_review_ref"])
        )
        body = payload(review)
        index = body.get("resolved_index")
        core = isinstance(index, dict) and index.get("catalog_schema_version") == 2
        if (
            review_group != group
            or review["kind"] != "technical-review"
            or body.get("created_by") != owner
            or body.get("status") != "STATIC_PASS"
            or body.get("draft_ref") != value["draft_ref"]
            or body.get("source_draft_refs") != value["source_draft_refs"]
            or body.get("material_digest") != sources[0]["material_digest"]
            or not readable_revisions(body.get("compiler_revision"), legacy=read_only and not core)
            or body.get("protocol") != ("s1-api-key-core-static-v2" if core else "b06a-static-v1")
            or body.get("checker") != ("omnis-api-key-core-v2" if core else "omnis-static-v1")
            or not isinstance(body.get("dependency_closure_refs"), list)
            or body.get("dependency_closure_digest")
            != digest(canonical(body.get("dependency_closure_refs")))
        ):
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        refs = body.get("candidate_refs")
        if not isinstance(refs, list) or not refs:
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        _, records = await self.sources(connection, owner, value)
        await store.reservation_bindings(
            connection, owner, [valid_ref(ref) for ref in refs], records
        )
        return review

    async def compile_pinned(
        self,
        connection: AsyncConnection,
        owner: str,
        directory: Path,
        records: list[dict[str, object]],
        refs: list[dict[str, object]],
        index: dict[str, object] | None = None,
    ) -> CompiledCatalog:
        sources = [payload(record) for record in records]
        pins = None if index is None else index.get("dependency_artifact_refs")
        if index is not None and pins is None:
            raise CatalogError("RELEASE_MISMATCH")
        if pins is not None and (
            not isinstance(pins, list) or not all(isinstance(p, dict) for p in pins)
        ):
            raise CatalogError("RELEASE_MISMATCH")
        dependencies = await load_dependencies(
            connection,
            owner,
            self.root,
            directory,
            sources,
            None if pins is None else [valid_ref(p) for p in pins],
        )
        bindings = await store.reservation_bindings(connection, owner, refs, records)
        return bind_catalog(
            compile_material(directory, sources, dependencies=dependencies), bindings
        )

    async def freeze(
        self, connection: AsyncConnection, owner: str, value: dict[str, object]
    ) -> dict[str, object]:
        group, records = await self.sources(connection, owner, value)
        if await self.rejected(connection, owner, group):
            raise CatalogError("CANDIDATE_REJECTED")
        sources = [payload(r) for r in records]
        review = await self.review_record(connection, owner, group, value, sources)
        body = payload(review)
        prior = await self.frozen_record(connection, owner, group)
        if prior is not None:
            if payload(prior)["technical_review_ref"] != value["technical_review_ref"]:
                raise CatalogError("CANDIDATE_FROZEN")
            await self.snapshot_readback(connection, owner, store.reference(prior))
            return {"snapshot_ref": store.reference(prior), "snapshot": prior}
        material = read_material(self.root, "drafts", group, sources)
        reviewed_index = body.get("resolved_index")
        if not isinstance(reviewed_index, dict):
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        reviewed_refs = body.get("candidate_refs")
        if not isinstance(reviewed_refs, list):
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        compiled = await self.compile_pinned(
            connection,
            owner,
            self.root / "drafts" / group,
            records,
            [valid_ref(r) for r in reviewed_refs],
            reviewed_index,
        )
        index = resolved_index(compiled)
        if (
            body.get("resolved_index") != index
            or body.get("resolved_index_digest") != compiled.resolved_index_digest
            or body.get("dependency_closure_refs") != list(compiled.dependency_closure_refs)
        ):
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        refs = body["candidate_refs"]
        if not isinstance(refs, list):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        profiles = [valid_ref(ref) for ref in refs if valid_ref(ref)["kind"] == "profile"]
        if len(profiles) != 1:
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        snapshot = store.envelope(
            "candidate-snapshot",
            {
                "draft_ref": value["draft_ref"],
                "source_draft_refs": value["source_draft_refs"],
                "material_digest": compiled.material_digest,
                "resolved_index_digest": compiled.resolved_index_digest,
                "candidate_refs": refs,
                "dependency_closure_refs": list(compiled.dependency_closure_refs),
                "profile_ref": profiles[0],
                "compiler_revision": COMPILER_REVISION,
                "technical_review_ref": value["technical_review_ref"],
                "created_by": owner,
            },
        )
        material[INDEX_FILE] = canonical(index)
        finalize(self.root, "candidates", str(snapshot["id"]), material)
        read_material(self.root, "candidates", str(snapshot["id"]), [*sources, index_source(index)])
        await store.put(connection, owner, group, snapshot)
        return {"snapshot_ref": store.reference(snapshot), "snapshot": snapshot}

    async def snapshot_readback(
        self, connection: AsyncConnection, owner: str, ref: dict[str, object]
    ) -> dict[str, object]:
        group, snapshot = await store.get(connection, owner, ref)
        if snapshot["kind"] != "candidate-snapshot":
            raise CatalogError("SNAPSHOT_MISMATCH")
        body = payload(snapshot)
        if set(body) != {
            "draft_ref",
            "source_draft_refs",
            "material_digest",
            "resolved_index_digest",
            "candidate_refs",
            "dependency_closure_refs",
            "profile_ref",
            "compiler_revision",
            "technical_review_ref",
            "created_by",
        }:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        source_group, records = await self.sources(connection, owner, body)
        if (
            source_group != group
            or body["created_by"] != owner
            or not readable_revisions(body["compiler_revision"], legacy=True)
        ):
            raise CatalogError("SNAPSHOT_MISMATCH")
        sources = [payload(r) for r in records]
        review = await self.review_record(connection, owner, group, body, sources, read_only=True)
        index = payload(review).get("resolved_index")
        if not isinstance(index, dict):
            raise CatalogError("RESOLVED_INDEX_MISMATCH")
        read_material(self.root, "candidates", str(snapshot["id"]), [*sources, index_source(index)])
        candidate_refs = body["candidate_refs"]
        if not isinstance(candidate_refs, list):
            raise CatalogError("SNAPSHOT_MISMATCH")
        compiled = await self.compile_pinned(
            connection,
            owner,
            self.root / "candidates" / str(snapshot["id"]),
            records,
            [valid_ref(r) for r in candidate_refs],
            index,
        )
        if (
            resolved_index(compiled) != index
            or body["material_digest"] != compiled.material_digest
            or body["resolved_index_digest"] != compiled.resolved_index_digest
            or body["compiler_revision"] != payload(review)["compiler_revision"]
            or body["candidate_refs"] != payload(review)["candidate_refs"]
            or body["profile_ref"] not in candidate_refs
            or body["dependency_closure_refs"] != payload(review)["dependency_closure_refs"]
        ):
            raise CatalogError("SNAPSHOT_MISMATCH")
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT envelope FROM catalog_record WHERE owner_id=:owner AND group_id=:group AND kind='evaluation-receipt' ORDER BY id"
                    ),
                    {"owner": owner, "group": group},
                )
            )
            .scalars()
            .all()
        )
        evaluations = []
        for row in rows:
            record = store.checked(row)
            receipt = payload(record)
            if receipt["snapshot_ref"] != ref or not readable_revisions(
                body["compiler_revision"],
                receipt.get("evaluator_revision"),
                legacy=not compiled.core_text,
            ):
                raise CatalogError("SNAPSHOT_MISMATCH")
            files = {"receipt.json": canonical(record)}
            input_ref = receipt["input_ref"]
            capture_v2 = receipt.get("protocol") == "c03-static-pure-capture-v2"
            records_v3 = receipt.get("protocol") == "c03-static-pure-records-v3"
            if capture_v2 or records_v3:
                if receipt.get("evaluator") != (
                    "omnis-static-pure-records-v3" if records_v3 else "omnis-static-pure-capture-v2"
                ) or case_version(compiled) != (2 if records_v3 else 1):
                    raise CatalogError("EVALUATION_MISMATCH")
                material = await self.capture_material(
                    connection, owner, group, snapshot, compiled, records, input_ref
                )
                files["input.json"] = canonical(material["input"])
            elif (
                receipt.get("protocol")
                != ("s1-api-key-core-v2" if compiled.core_text else "b06a-static-pure-v1")
                or receipt.get("evaluator")
                != ("omnis-api-key-core-v2" if compiled.core_text else "omnis-static-pure-v1")
                or (compiled.slots and receipt.get("status") == "PURE_PASS")
            ):
                raise CatalogError("EVALUATION_MISMATCH")
            elif input_ref is not None:
                input_group, input_record = await store.get(connection, owner, valid_ref(input_ref))
                if (
                    input_group != group
                    or input_record["kind"] != "evaluation-input"
                    or payload(input_record)["snapshot_ref"] != ref
                ):
                    raise CatalogError("SNAPSHOT_MISMATCH")
                files["input.json"] = canonical(input_record)
            outputs = receipt["outputs"]
            if outputs:
                files["outputs.json"] = canonical(outputs)
            file_source: dict[str, object] = {
                "prefix": "",
                "files": [
                    {"path": name, "sha256": digest(raw), "size": len(raw)}
                    for name, raw in files.items()
                ],
            }
            read_material(self.root, "receipts", str(record["id"]), [file_source])
            for key in ("material_digest", "resolved_index_digest", "compiler_revision"):
                if receipt[key] != body[key]:
                    raise CatalogError("SNAPSHOT_MISMATCH")
            if receipt["dependency_closure_digest"] != digest(
                canonical(body["dependency_closure_refs"])
            ):
                raise CatalogError("SNAPSHOT_MISMATCH")
            evaluations.append(record)
        return {
            "snapshot_ref": ref,
            "snapshot": snapshot,
            "resolved_index": index,
            "technical_review": review,
            "evaluations": evaluations,
            "publication": "UNPUBLISHED",
            "assessment_selectable": False,
        }

    def capture_spec(
        self,
        snapshot: dict[str, object],
        compiled: CompiledCatalog,
        records: list[dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, object], bytes, str]:
        """Resolve schema bytes through the selected frozen procedure, never caller refs."""
        from omnis.modules.tasks.contract_case_input import (
            first_binding,
            input_schema,
        )

        from .catalog_models import CandidateRef, LocalRef, Manifest, Procedure, Profile
        from .catalog_schema import dto

        version = case_version(compiled)
        if (
            compiled.verification_kind != "CONTRACT"
            or not compiled.steps
            or [b.model_dump(mode="json") for b in compiled.steps[0].bindings]
            != [first_binding(version)]
        ):
            raise CatalogError("UNSUPPORTED_CAPTURE_SLOT")
        directory = self.root / "candidates" / str(snapshot["id"])
        profile = dto(read_file(directory / "profile.yaml", 262144), Profile)
        if len(profile.agent_recipes) != 1 or len(profile.agent_recipes[0].procedure_refs) != 1:
            raise CatalogError("UNSUPPORTED_RECIPE")
        selected = profile.agent_recipes[0].procedure_refs[0]
        if not isinstance(selected, CandidateRef) or selected.entity_kind != "procedure":
            raise CatalogError("UNSUPPORTED_CAPTURE_SLOT")
        sources = [
            payload(r)
            for r in records
            if payload(r).get("source_kind") == "package"
            and payload(r).get("package_key") == selected.package_key
        ]
        if len(sources) != 1:
            raise CatalogError("REF_MISMATCH")
        package_dir = directory / str(sources[0]["prefix"])
        manifest = dto(read_file(package_dir / "omnis.yaml", 262144), Manifest)
        procedures = [
            dto(read_file(package_dir / path, 262144), Procedure) for path in manifest.procedures
        ]
        matches = [p for p in procedures if p.key == selected.key]
        if len(matches) != 1 or not isinstance(matches[0].input_schema_ref, LocalRef):
            raise CatalogError("UNSUPPORTED_CAPTURE_SLOT")
        schema_key = matches[0].input_schema_ref.key
        paths = [
            b.path
            for b in manifest.file_bindings
            if b.entity_kind == "schema" and b.key == schema_key
        ]
        if len(paths) != 1:
            raise CatalogError("REF_MISMATCH")
        raw = read_file(package_dir / paths[0], 8192)
        if canonical(input_schema(raw, version=version)) != compiled.input_schema:
            raise CatalogError("REF_MISMATCH")

        def selected_ref(kind: str, key: str) -> dict[str, object]:
            bindings = [
                b
                for b in compiled.catalog_bindings
                if b["package_key"] == selected.package_key
                and b["entity_kind"] == kind
                and b["key"] == key
            ]
            if len(bindings) != 1:
                raise CatalogError("REF_MISMATCH")
            ref = valid_ref(bindings[0]["ref"])
            if ref["kind"] != kind:
                raise CatalogError("REF_MISMATCH")
            return ref

        return (
            selected_ref("procedure", selected.key),
            selected_ref("schema", schema_key),
            raw,
            paths[0],
        )

    def admission_payload(
        self,
        owner: str,
        snapshot: dict[str, object],
        procedure_ref: dict[str, object],
        schema_ref: dict[str, object],
        version: int = 1,
    ) -> dict[str, object]:
        body = payload(snapshot)
        return {
            "version": version,
            "namespace": "PACKAGE_EVAL",
            "owner_id": owner,
            "snapshot_ref": store.reference(snapshot),
            "procedure_ref": procedure_ref,
            "schema_ref": schema_ref,
            "material_digest": body["material_digest"],
            "resolved_index_digest": body["resolved_index_digest"],
            "compiler_revision": body["compiler_revision"],
        }

    async def capture_material(
        self,
        connection: AsyncConnection,
        owner: str,
        group: str,
        snapshot: dict[str, object],
        compiled: CompiledCatalog,
        records: list[dict[str, object]],
        input_ref: object,
    ) -> dict[str, object]:
        from omnis.modules.tasks.contract_case_input import material_section

        procedure_ref, schema_ref, raw, path = self.capture_spec(snapshot, compiled, records)
        version = case_version(compiled)
        input_group, input_record = await store.get(connection, owner, valid_ref(input_ref))
        context_group, context = await store.get(
            connection, owner, valid_ref(payload(input_record).get("context_ref"))
        )
        context_body = payload(context)
        admission_group, admission = await store.get(
            connection, owner, valid_ref(context_body.get("basis_ref"))
        )
        check_capture_admission(
            admission, self.admission_payload(owner, snapshot, procedure_ref, schema_ref, version)
        )
        expected_context = {
            "version": version,
            "namespace": "PACKAGE_EVAL",
            "owner_id": owner,
            "basis_ref": store.reference(admission),
            "snapshot_ref": store.reference(snapshot),
            "procedure_ref": procedure_ref,
            "schema_ref": schema_ref,
            "selection_ref": None,
            "mission_ref": None,
            "focus_ref": None,
        }
        if (
            input_group != group
            or context_group != group
            or admission_group != group
            or context_body != expected_context
        ):
            raise CatalogError("EVALUATION_ADMISSION_MISMATCH")
        return material_section(context, input_record, schema_ref, raw, schema_path=path)

    async def admit_evaluation_capture(
        self, connection: AsyncConnection, owner: str, value: dict[str, object]
    ) -> dict[str, object]:
        from omnis.modules.tasks.contract_case_input import material_section, produce_input

        ref = valid_ref(value["snapshot_ref"])
        back = await self.snapshot_readback(connection, owner, ref)
        group, snapshot = await store.get(connection, owner, ref)
        if await self.rejected(connection, owner, group):
            raise CatalogError("CANDIDATE_REJECTED")
        if await self.frozen_record(connection, owner, group) != snapshot:
            raise CatalogError("SNAPSHOT_MISMATCH")
        body = payload(snapshot)
        _, records = await self.sources(connection, owner, body)
        refs, index = body["candidate_refs"], back["resolved_index"]
        if not isinstance(refs, list) or not isinstance(index, dict):
            raise CatalogError("SNAPSHOT_MISMATCH")
        compiled = await self.compile_pinned(
            connection,
            owner,
            self.root / "candidates" / str(snapshot["id"]),
            records,
            [valid_ref(r) for r in refs],
            index,
        )
        procedure_ref, schema_ref, raw, path = self.capture_spec(snapshot, compiled, records)
        version = case_version(compiled)
        if value["schema_version"] != version + 1:
            raise CatalogError("EVALUATION_ADMISSION_MISMATCH")
        admission = store.envelope(
            "evaluation-admission",
            self.admission_payload(owner, snapshot, procedure_ref, schema_ref, version),
        )
        context = store.envelope(
            "contract-input-context",
            {
                "version": version,
                "namespace": "PACKAGE_EVAL",
                "owner_id": owner,
                "basis_ref": store.reference(admission),
                "snapshot_ref": ref,
                "procedure_ref": procedure_ref,
                "schema_ref": schema_ref,
                "selection_ref": None,
                "mission_ref": None,
                "focus_ref": None,
            },
        )
        input_record = produce_input(context, value["value"], raw, uuid_string(value["command_id"]))
        material = material_section(context, input_record, schema_ref, raw, schema_path=path)
        for record in (admission, context, input_record):
            await store.put(connection, owner, group, record)
        return {
            "admission_ref": store.reference(admission),
            "admission": admission,
            "context_ref": store.reference(context),
            "context": context,
            "input_ref": store.reference(input_record),
            "input": input_record,
            "material": material,
        }

    async def capture_readback(
        self,
        connection: AsyncConnection,
        owner: str,
        value: dict[str, object],
        result: dict[str, object],
    ) -> None:
        ref = valid_ref(value["snapshot_ref"])
        back = await self.snapshot_readback(connection, owner, ref)
        group, snapshot = await store.get(connection, owner, ref)
        body = payload(snapshot)
        _, records = await self.sources(connection, owner, body)
        refs, index = body["candidate_refs"], back["resolved_index"]
        if not isinstance(refs, list) or not isinstance(index, dict):
            raise CatalogError("SNAPSHOT_MISMATCH")
        compiled = await self.compile_pinned(
            connection,
            owner,
            self.root / "candidates" / str(snapshot["id"]),
            records,
            [valid_ref(r) for r in refs],
            index,
        )
        material = await self.capture_material(
            connection, owner, group, snapshot, compiled, records, result.get("input_ref")
        )
        context, input_record = material["context"], material["input"]
        if not isinstance(context, dict) or not isinstance(input_record, dict):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        _, admission = await store.get(connection, owner, valid_ref(payload(context)["basis_ref"]))
        expected = {
            "admission_ref": store.reference(admission),
            "admission": admission,
            "context_ref": store.reference(context),
            "context": context,
            "input_ref": store.reference(input_record),
            "input": input_record,
            "material": material,
        }
        provenance = payload(input_record).get("provenance")
        if (
            result != expected
            or material["version"] != (2 if value["schema_version"] == 3 else 1)
            or payload(input_record)["value"] != value["value"]
            or not isinstance(provenance, dict)
            or provenance.get("command_id") != value["command_id"]
        ):
            raise CatalogError("EVALUATION_ADMISSION_MISMATCH")

    async def evaluate(
        self, connection: AsyncConnection, owner: str, value: dict[str, object]
    ) -> dict[str, object]:
        ref = valid_ref(value["snapshot_ref"])
        back = await self.snapshot_readback(connection, owner, ref)
        group, snapshot = await store.get(connection, owner, ref)
        body = payload(snapshot)
        if body["compiler_revision"] != COMPILER_REVISION:
            raise CatalogError("LEGACY_READ_ONLY")
        _, records = await self.sources(connection, owner, body)
        started = datetime.now(UTC).isoformat()
        clock = monotonic_ns()
        pinned_index = back["resolved_index"]
        if not isinstance(pinned_index, dict) or not isinstance(body["candidate_refs"], list):
            raise CatalogError("SNAPSHOT_MISMATCH")
        compiled = await self.compile_pinned(
            connection,
            owner,
            self.root / "candidates" / str(snapshot["id"]),
            records,
            [valid_ref(r) for r in body["candidate_refs"]],
            pinned_index,
        )
        capture_v2 = value["schema_version"] in (2, 3)
        records_v3 = value["schema_version"] == 3
        capture_material = None
        input_record = None
        if capture_v2:
            if case_version(compiled) != (2 if records_v3 else 1):
                raise CatalogError("EVALUATION_ADMISSION_MISMATCH")
            capture_material = await self.capture_material(
                connection, owner, group, snapshot, compiled, records, value["input_ref"]
            )
            checked_input = capture_material["input"]
            if not isinstance(checked_input, dict):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            input_record = checked_input
        elif value["evaluation_kind"] == "PURE":
            input_record = store.envelope(
                "evaluation-input",
                {"snapshot_ref": ref, "input": value["input"], "created_by": owner},
            )
        outputs: list[str] = []
        try:
            if value["evaluation_kind"] == "PURE":
                outputs = [
                    raw.decode("utf-8")
                    for raw in evaluate_pure(
                        compiled,
                        None if capture_v2 else value["input"],
                        capture_material=capture_material,
                    ).outputs_json
                ]
            status, reason = str(value["evaluation_kind"]) + "_PASS", None
        except CatalogError as error:
            status, reason = "BLOCKED", error.reason
        receipt = store.envelope(
            "evaluation-receipt",
            {
                "snapshot_ref": ref,
                "material_digest": body["material_digest"],
                "resolved_index_digest": body["resolved_index_digest"],
                "dependency_closure_refs": body["dependency_closure_refs"],
                "dependency_closure_digest": digest(canonical(body["dependency_closure_refs"])),
                "compiler_revision": COMPILER_REVISION,
                "evaluator": "omnis-api-key-core-v2"
                if compiled.core_text
                else "omnis-static-pure-records-v3"
                if records_v3
                else "omnis-static-pure-capture-v2"
                if capture_v2
                else "omnis-static-pure-v1",
                "evaluator_revision": EVALUATOR_REVISION,
                "protocol": "s1-api-key-core-v2"
                if compiled.core_text
                else "c03-static-pure-records-v3"
                if records_v3
                else "c03-static-pure-capture-v2"
                if capture_v2
                else "b06a-static-pure-v1",
                "tool_versions": {
                    "trusted_handlers": "core-read-context-v2"
                    if compiled.core_text
                    else "contract-v1"
                },
                "corpus_ref": None,
                "evaluation_kind": value["evaluation_kind"],
                "input_ref": store.reference(input_record) if input_record is not None else None,
                "requested": back["resolved_index"]["requested"]
                if isinstance(back["resolved_index"], dict)
                else None,
                "resolution": "NO_MODEL",
                "effective": None,
                "model_ref": None,
                "created_by": owner,
                "status": status,
                "reason": reason,
                "outputs": outputs,
                "evidence_refs": [],
                "target_evidence": "NOT_APPLICABLE",
                "limits": {
                    "max_input_bytes": 8192 if capture_v2 else 1048576,
                    "max_output_bytes": compiled.max_output_bytes,
                    "dispatch_timeout_seconds": 15,
                },
                "limitations": [
                    "STATIC/PURE synthetic only",
                    "Publish/runtime binding/plan pending",
                    "no provider or target effects",
                ],
                "started_at": started,
                "finished_at": datetime.now(UTC).isoformat(),
                "duration_ns": monotonic_ns() - clock,
            },
        )
        files = {"receipt.json": canonical(receipt)}
        if input_record is not None:
            files["input.json"] = canonical(input_record)
        if outputs:
            files["outputs.json"] = canonical(outputs)
        finalize(self.root, "receipts", str(receipt["id"]), files)
        file_source: dict[str, object] = {
            "prefix": "",
            "files": [
                {"path": name, "sha256": digest(raw), "size": len(raw)}
                for name, raw in files.items()
            ],
        }
        read_material(self.root, "receipts", str(receipt["id"]), [file_source])
        if input_record is not None and not capture_v2:
            await store.put(connection, owner, group, input_record)
        await store.put(connection, owner, group, receipt)
        return {
            "status": status,
            "reason": reason,
            "snapshot_ref": ref,
            "evaluation_ref": store.reference(receipt),
            "evaluation": receipt,
            "outputs": outputs,
        }

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


def load_request(raw: bytes) -> object:
    from omnis.modules.tasks.contract_case_input import utf8_json_text

    source = utf8_json_text(raw)

    def reject_number(value: str) -> NoReturn:
        raise CatalogError("INVALID_REQUEST")

    try:
        return json.loads(
            source, object_pairs_hook=pairs, parse_float=reject_number, parse_constant=reject_number
        )
    except CatalogError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise CatalogError("INVALID_REQUEST") from None


def main(argv: list[str] | None = None) -> int:
    class SafeParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = SafeParser()
    parser.add_argument(
        "operation",
        choices=(
            "capture",
            "review",
            "reject",
            "freeze",
            "evaluate",
            "readback",
            "admit-evaluation-capture",
            "admit-evaluation-records",
        ),
    )
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog-root", required=True)
    try:
        args = parser.parse_args(argv)
        request = load_request(read_file(Path(args.request)))
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
