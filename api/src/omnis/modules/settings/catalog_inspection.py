"""Bounded PostgreSQL metadata projection. Never compile, open material or evaluate.

The recorded compiler/evaluator pins are historical identities, not current-code
attestations. External release material has no installed mount at this seam.
"""

import hashlib
import re
from typing import NoReturn, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from . import candidate_store as store
from .catalog_inspection_models import CatalogEntry, CatalogInspection, CatalogPage, CatalogPin
from .catalog_models import CatalogError, Preference
from .catalog_schema import bounded, canonical

SELECTION = frozenset(
    (
        "expected_head_generation",
        "draft_ref",
        "source_draft_refs",
        "snapshot_ref",
        "technical_review_ref",
        "static_evaluation_ref",
        "pure_evaluation_ref",
        "material_digest",
        "resolved_index_digest",
        "dependency_closure_digest",
    )
)
PUBLICATION = SELECTION | {
    "confirmation_ref",
    "profile_key",
    "generation",
    "profile_ref",
    "candidate_refs",
    "dependency_closure_refs",
    "dependency_artifact_refs",
    "compiler_revision",
    "evaluator_revision",
    "created_by",
    "state",
    "resolution",
    "effective",
    "assessment_selectable",
}
SHARED = frozenset(
    (
        "draft_ref",
        "source_draft_refs",
        "material_digest",
        "resolved_index_digest",
        "candidate_refs",
        "dependency_closure_refs",
        "compiler_revision",
        "created_by",
    )
)
ROW_COLUMNS = "id,owner_id,group_id,kind,revision,digest,envelope"


def refuse() -> NoReturn:
    raise CatalogError("CATALOG_METADATA_UNAVAILABLE")


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def obj(value: object, fields: set[str] | frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        refuse()
    return cast(dict[str, object], value)


def integer(value: object, minimum: int = 1, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        refuse()
    return value


def uuid_text(value: object) -> str:
    if type(value) is UUID:
        return str(value)
    if type(value) is not str or str(UUID(value)) != value:
        refuse()
    return value


def pin(value: object, kind: str | None = None) -> dict[str, object]:
    try:
        parsed = CatalogPin.model_validate(value)
    except ValidationError:
        refuse()
    if kind is not None and parsed.kind != kind:
        refuse()
    return parsed.model_dump(mode="json")


def pins(value: object, kind: str | None = None, minimum: int = 0) -> list[dict[str, object]]:
    if not isinstance(value, list) or not minimum <= len(value) <= 128:
        refuse()
    result = [pin(item, kind) for item in cast(list[object], value)]
    if len({canonical(item) for item in result}) != len(result):
        refuse()
    return result


def checked(row: dict[str, object]) -> dict[str, object]:
    record = store.checked(row["envelope"])
    bounded(record)
    if len(canonical(record)) > 1048576:
        refuse()
    integer(record["schema_version"], 1, 1)
    ref = pin(store.reference(record))
    if (
        uuid_text(row["id"]) != ref["id"]
        or row["kind"] != ref["kind"]
        or integer(row["revision"], 1, 2147483646) != ref["revision"]
        or row["digest"] != ref["digest"]
    ):
        refuse()
    uuid_text(row["owner_id"])
    uuid_text(row["group_id"])
    return record


async def row_for(connection: AsyncConnection, identity: str) -> dict[str, object]:
    row = (
        (
            await connection.execute(
                text(f"SELECT {ROW_COLUMNS} FROM catalog_record WHERE id=:id"), {"id": identity}
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        refuse()
    return dict(cast(dict[str, object], row))


async def retained(
    connection: AsyncConnection, value: object, kind: str, owner: str, group: str
) -> dict[str, object]:
    ref = pin(value, kind)
    row = await row_for(connection, str(ref["id"]))
    record = checked(row)
    if (
        store.reference(record) != ref
        or uuid_text(row["owner_id"]) != owner
        or uuid_text(row["group_id"]) != group
    ):
        refuse()
    body = record["payload"]
    if not isinstance(body, dict) or body.get("created_by") != owner:
        refuse()
    return body


def publication(record: dict[str, object], owner: str) -> dict[str, object]:
    pin(store.reference(record), "catalog-publication")
    body = obj(record["payload"], PUBLICATION)
    if (
        body["created_by"] != owner
        or body["state"] != "PUBLISHED"
        or body["assessment_selectable"] is not False
        or body["resolution"] != "NO_MODEL"
        or body["effective"] is not None
    ):
        refuse()
    if integer(body["generation"]) != integer(body["expected_head_generation"]) + 1:
        refuse()
    for field, kind in (
        ("draft_ref", "source-draft"),
        ("snapshot_ref", "candidate-snapshot"),
        ("technical_review_ref", "technical-review"),
        ("static_evaluation_ref", "evaluation-receipt"),
        ("pure_evaluation_ref", "evaluation-receipt"),
        ("confirmation_ref", "operator-confirmation"),
        ("profile_ref", "profile"),
    ):
        pin(body[field], kind)
    sources = pins(body["source_draft_refs"], "source-draft", 1)
    candidates = pins(body["candidate_refs"], minimum=1)
    closure = pins(body["dependency_closure_refs"])
    pins(body["dependency_artifact_refs"], "qualified-release")
    if (
        body["draft_ref"] not in sources
        or body["profile_ref"] not in candidates
        or len([r for r in candidates if r["kind"] == "profile"]) != 1
        or body["dependency_closure_digest"] != sha(closure)
        or body["static_evaluation_ref"] == body["pure_evaluation_ref"]
    ):
        refuse()
    return body


async def published_page(connection: AsyncConnection, after: str | None) -> CatalogPage:
    """Only non-null current heads; UUID keyset and one real lookahead row."""
    if after is not None:
        uuid_text(after)
    rows = (
        (
            await connection.execute(
                text(
                    "SELECT owner_id,profile_key,generation,draft_id,publication_id "
                    "FROM catalog_publication_head WHERE publication_id IS NOT NULL "
                    "AND (:after IS NULL OR publication_id > CAST(:after AS uuid)) "
                    "ORDER BY publication_id LIMIT 21"
                ),
                {"after": after},
            )
        )
        .mappings()
        .all()
    )
    entries = []
    for head in rows[:20]:
        identity = uuid_text(head["publication_id"])
        row = await row_for(connection, identity)
        record = checked(row)
        owner = uuid_text(head["owner_id"])
        body = publication(record, owner)
        if (
            uuid_text(row["owner_id"]) != owner
            or body["profile_key"] != head["profile_key"]
            or body["generation"] != integer(head["generation"])
            or pin(body["draft_ref"])["id"] != uuid_text(head["draft_id"])
        ):
            refuse()
        entries.append(
            CatalogEntry.model_validate(
                {
                    "publication_ref": store.reference(record),
                    "profile_key": body["profile_key"],
                    "generation": body["generation"],
                }
            )
        )
    more = len(rows) > 20
    return CatalogPage(
        items=entries, has_more=more, next_after=entries[-1].publication_ref.id if more else None
    )


async def inspect_publication(
    connection: AsyncConnection, identity: str, digest: str
) -> CatalogInspection:
    """Exact immutable identity independent of subsequent head capture/promotion."""
    uuid_text(identity)
    row = await row_for(connection, identity)
    record = checked(row)
    if record["digest"] != digest:
        refuse()
    owner, group = uuid_text(row["owner_id"]), uuid_text(row["group_id"])
    body = publication(record, owner)
    snapshot = await retained(connection, body["snapshot_ref"], "candidate-snapshot", owner, group)
    obj(snapshot, SHARED | {"profile_ref", "technical_review_ref"})
    for field in snapshot:
        if canonical(snapshot[field]) != canonical(body[field]):
            refuse()
    review = await retained(
        connection, body["technical_review_ref"], "technical-review", owner, group
    )
    obj(
        review,
        SHARED
        | {
            "resolved_index",
            "dependency_closure_digest",
            "reviewed_at",
            "started_at",
            "duration_ns",
            "limits",
            "resolution",
            "effective",
            "checker",
            "protocol",
            "author_kind",
            "status",
            "reason",
        },
    )
    for field in SHARED | {"dependency_closure_digest"}:
        if canonical(review[field]) != canonical(body[field]):
            refuse()
    if (
        review["status"] != "STATIC_PASS"
        or review["reason"] is not None
        or review["protocol"] != "b06a-static-v1"
        or review["checker"] != "omnis-static-v1"
        or review["resolution"] != "NO_MODEL"
        or review["effective"] is not None
    ):
        refuse()
    integer(review["duration_ns"], 0)
    index = obj(
        review["resolved_index"],
        {
            "refs",
            "steps",
            "requested",
            "resolution",
            "dependency_closure_refs",
            "dependency_artifact_refs",
            "catalog_bindings",
        },
    )
    if (
        sha(index) != body["resolved_index_digest"]
        or index["resolution"] != "NO_MODEL"
        or index["dependency_closure_refs"] != body["dependency_closure_refs"]
        or index["dependency_artifact_refs"] != body["dependency_artifact_refs"]
    ):
        refuse()
    requested = Preference.model_validate(index["requested"])
    # Unknown retained index shapes are refused, not upgraded into current readiness.
    for field in ("refs", "steps", "catalog_bindings"):
        if not isinstance(index[field], list) or len(cast(list[object], index[field])) > 128:
            refuse()
    sources = pins(body["source_draft_refs"], "source-draft", 1)
    profile_seen = False
    for ref in sources:
        source = await retained(connection, ref, "source-draft", owner, group)
        source_kind = source.get("source_kind")
        fields = {
            "source_kind",
            "prefix",
            "files",
            "identities",
            "created_by",
            "author_kind",
            "material_digest",
        }
        obj(
            source,
            fields | ({"key"} if source_kind == "profile" else {"package_key", "package_digest"}),
        )
        if (
            source_kind not in ("profile", "package")
            or source["material_digest"] != body["material_digest"]
        ):
            refuse()
        if source["author_kind"] not in ("OPERATOR", "AI"):
            refuse()
        if source_kind == "profile":
            if profile_seen or ref != body["draft_ref"] or source["key"] != body["profile_key"]:
                refuse()
            profile_seen = True
    if not profile_seen:
        refuse()
    confirmation = await retained(
        connection, body["confirmation_ref"], "operator-confirmation", owner, group
    )
    obj(confirmation, {"selection", "actor", "author_kind", "created_by"})
    if (
        canonical(confirmation["selection"]) != canonical({key: body[key] for key in SELECTION})
        or confirmation["author_kind"] != "OPERATOR"
        or type(confirmation["actor"]) is not str
        or re.fullmatch(r"local-operator:(?:0|[1-9][0-9]*)", str(confirmation["actor"])) is None
    ):
        refuse()
    for kind in ("STATIC", "PURE"):
        receipt = await retained(
            connection, body[kind.lower() + "_evaluation_ref"], "evaluation-receipt", owner, group
        )
        obj(
            receipt,
            {
                "snapshot_ref",
                "material_digest",
                "resolved_index_digest",
                "dependency_closure_refs",
                "dependency_closure_digest",
                "compiler_revision",
                "evaluator_revision",
                "evaluator",
                "protocol",
                "tool_versions",
                "corpus_ref",
                "evaluation_kind",
                "input_ref",
                "requested",
                "resolution",
                "effective",
                "model_ref",
                "created_by",
                "status",
                "reason",
                "outputs",
                "evidence_refs",
                "target_evidence",
                "limits",
                "limitations",
                "started_at",
                "finished_at",
                "duration_ns",
            },
        )
        for field in (
            "snapshot_ref",
            "material_digest",
            "resolved_index_digest",
            "dependency_closure_refs",
            "dependency_closure_digest",
            "compiler_revision",
            "evaluator_revision",
            "resolution",
        ):
            if canonical(receipt[field]) != canonical(body[field]):
                refuse()
        if (
            receipt["status"] != kind + "_PASS"
            or receipt["evaluation_kind"] != kind
            or receipt["reason"] is not None
            or receipt["effective"] is not None
            or receipt["model_ref"] is not None
            or receipt["requested"] != index["requested"]
            or receipt["protocol"] != "b06a-static-pure-v1"
            or receipt["evaluator"] != "omnis-static-pure-v1"
            or receipt["target_evidence"] != "NOT_APPLICABLE"
            or receipt["evidence_refs"] != []
        ):
            refuse()
        integer(receipt["duration_ns"], 0)
        if kind == "PURE":
            input_body = await retained(
                connection, receipt["input_ref"], "evaluation-input", owner, group
            )
            obj(input_body, {"snapshot_ref", "input", "created_by"})
            if input_body["snapshot_ref"] != body["snapshot_ref"]:
                refuse()
        elif receipt["input_ref"] is not None:
            refuse()
    fields = {
        "profile_key",
        "generation",
        "profile_ref",
        "snapshot_ref",
        "technical_review_ref",
        "static_evaluation_ref",
        "pure_evaluation_ref",
        "confirmation_ref",
        "source_draft_refs",
        "candidate_refs",
        "dependency_closure_refs",
        "dependency_artifact_refs",
        "material_digest",
        "resolved_index_digest",
        "dependency_closure_digest",
        "compiler_revision",
        "evaluator_revision",
    }
    return CatalogInspection.model_validate(
        {
            **{key: body[key] for key in fields},
            "publication_ref": store.reference(record),
            "owner_id": owner,
            "requested": requested,
            "review": "RECORDED_STATIC_PASS",
            "static": "RECORDED_STATIC_PASS",
            "pure": "RECORDED_PURE_PASS",
            "dependency_metadata": "NOT_VERIFIED"
            if body["dependency_artifact_refs"]
            else "NO_EXTERNAL_DEPENDENCIES",
            "material": "NOT_VERIFIED",
            "runtime": "NOT_AVAILABLE",
            "benchmark": "NOT_VERIFIED",
            "fixture": "NOT_VERIFIED",
            "security": "NOT_VERIFIED",
            "assessment_selectable": False,
            "resolution": "NO_MODEL",
        }
    )


READ_FAILURES = (
    CatalogError,
    ValidationError,
    ValueError,
    TypeError,
    KeyError,
    UnicodeError,
    RecursionError,
)
