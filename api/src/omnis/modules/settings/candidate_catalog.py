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
from .candidate_index import INDEX_FILE, compile_material, index_source, resolved_index
from .candidate_material import (
    MAX_SOURCE_PACKAGES,
    capture,
    digest,
    finalize,
    private_root,
    read_material,
)
from .catalog_models import CatalogError
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
    "settings/catalog_models.py",
    "settings/catalog_schema.py",
    "settings/skill_catalog.py",
    "tasks/module_registry.py",
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
    }
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
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
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
                if operation in ("freeze", "evaluate"):
                    ref = prior.get("snapshot_ref", value.get("snapshot_ref"))
                    await self.snapshot_readback(connection, owner, valid_ref(ref))
                return prior
            if operation == "evaluate":
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
                    try:
                        compiled = compile_material(self.root / "drafts" / group, sources)
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
                            "dependency_closure_refs": [],
                            "dependency_closure_digest": digest(canonical([])),
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
                        "reservations": reservations,
                        "resolved_index_digest": index_digest,
                    }
            await store.complete(connection, owner, command, operation, value, result)
        # Read back the exact committed command on a fresh connection.
        async with self.engine.connect() as connection:
            readback = await store.replay(connection, owner, command, operation, value)
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
    ) -> dict[str, object]:
        review_group, review = await store.get(
            connection, owner, valid_ref(value["technical_review_ref"])
        )
        body = payload(review)
        if (
            review_group != group
            or review["kind"] != "technical-review"
            or body.get("created_by") != owner
            or body.get("status") != "STATIC_PASS"
            or body.get("draft_ref") != value["draft_ref"]
            or body.get("source_draft_refs") != value["source_draft_refs"]
            or body.get("material_digest") != sources[0]["material_digest"]
            or body.get("compiler_revision") != COMPILER_REVISION
            or body.get("protocol") != "b06a-static-v1"
            or body.get("checker") != "omnis-static-v1"
            or body.get("dependency_closure_refs") != []
            or body.get("dependency_closure_digest") != digest(canonical([]))
        ):
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        refs = body.get("candidate_refs")
        if not isinstance(refs, list) or not refs:
            raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        for ref in refs:
            exact = valid_ref(ref)
            reserved = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM catalog_reservation r JOIN catalog_identity i ON i.id=r.id "
                    "WHERE r.id=:id AND r.revision=:revision AND r.digest=:digest AND i.owner_id=:owner AND i.entity_kind=:kind)"
                ),
                {**exact, "owner": owner},
            )
            if reserved is not True:
                raise CatalogError("TECHNICAL_REVIEW_MISMATCH")
        return review

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
        compiled = compile_material(self.root / "drafts" / group, sources)
        index = resolved_index(compiled)
        if (
            body.get("resolved_index") != index
            or body.get("resolved_index_digest") != compiled.resolved_index_digest
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
                "dependency_closure_refs": [],
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
            or body["compiler_revision"] != COMPILER_REVISION
        ):
            raise CatalogError("SNAPSHOT_MISMATCH")
        sources = [payload(r) for r in records]
        review = await self.review_record(connection, owner, group, body, sources)
        index = payload(review).get("resolved_index")
        if not isinstance(index, dict):
            raise CatalogError("RESOLVED_INDEX_MISMATCH")
        read_material(self.root, "candidates", str(snapshot["id"]), [*sources, index_source(index)])
        compiled = compile_material(self.root / "candidates" / str(snapshot["id"]), sources)
        candidate_refs = body["candidate_refs"]
        if not isinstance(candidate_refs, list):
            raise CatalogError("SNAPSHOT_MISMATCH")
        if (
            resolved_index(compiled) != index
            or body["material_digest"] != compiled.material_digest
            or body["resolved_index_digest"] != compiled.resolved_index_digest
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
            if (
                receipt["snapshot_ref"] != ref
                or receipt.get("evaluator_revision") != EVALUATOR_REVISION
            ):
                raise CatalogError("SNAPSHOT_MISMATCH")
            files = {"receipt.json": canonical(record)}
            input_ref = receipt["input_ref"]
            if input_ref is not None:
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

    async def evaluate(
        self, connection: AsyncConnection, owner: str, value: dict[str, object]
    ) -> dict[str, object]:
        ref = valid_ref(value["snapshot_ref"])
        back = await self.snapshot_readback(connection, owner, ref)
        group, snapshot = await store.get(connection, owner, ref)
        body = payload(snapshot)
        _, records = await self.sources(connection, owner, body)
        sources = [payload(r) for r in records]
        started = datetime.now(UTC).isoformat()
        clock = monotonic_ns()
        compiled = compile_material(self.root / "candidates" / str(snapshot["id"]), sources)
        input_record = None
        if value["evaluation_kind"] == "PURE":
            input_record = store.envelope(
                "evaluation-input",
                {"snapshot_ref": ref, "input": value["input"], "created_by": owner},
            )
        outputs: list[str] = []
        try:
            if value["evaluation_kind"] == "PURE":
                outputs = [
                    raw.decode("utf-8")
                    for raw in evaluate_pure(compiled, value["input"]).outputs_json
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
                "evaluator": "omnis-static-pure-v1",
                "evaluator_revision": EVALUATOR_REVISION,
                "protocol": "b06a-static-pure-v1",
                "tool_versions": {"trusted_handlers": "contract-v1"},
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
                    "max_input_bytes": 1048576,
                    "max_output_bytes": compiled.max_output_bytes,
                    "dispatch_timeout_seconds": 15,
                },
                "limitations": [
                    "STATIC/PURE synthetic only",
                    "full closure/RELEASE/plan pending",
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
        if input_record is not None:
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
    def reject_number(value: str) -> NoReturn:
        raise CatalogError("INVALID_REQUEST")

    try:
        return json.loads(
            raw, object_pairs_hook=pairs, parse_float=reject_number, parse_constant=reject_number
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
        "operation", choices=("capture", "review", "reject", "freeze", "evaluate", "readback")
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
