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
from .catalog_inspection_models import (
    CatalogBinding,
    CatalogEntry,
    CatalogInspection,
    CatalogPage,
    CatalogPin,
)
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
EVALUATION_PROTOCOLS = {
    "b06a-static-pure-v1": ("omnis-static-pure-v1", 0, "evaluation-input"),
    "c03-static-pure-capture-v2": ("omnis-static-pure-capture-v2", 1, "contract-case-input"),
    "c03-static-pure-records-v3": ("omnis-static-pure-records-v3", 2, "contract-case-records"),
}


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
    bounded(row["envelope"])
    if len(canonical(row["envelope"])) > 1048576:
        refuse()
    record = store.checked(row["envelope"])
    metadata_tree(record)
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


def metadata_tree(value: object) -> None:
    """Preserve JSON identity types before equality, even in retained subtrees."""
    if isinstance(value, dict):
        if {"kind", "id", "revision", "digest"} <= set(value) and "payload" not in value:
            pin(value)
        for key, child in value.items():
            if key == "files":
                if not isinstance(child, list) or not 1 <= len(child) <= 128:
                    refuse()
                names: set[str] = set()
                for item in child:
                    file = obj(item, {"path", "sha256", "size"})
                    name, digest = file["path"], file["sha256"]
                    if (
                        type(name) is not str
                        or len(name) > 4096
                        or name.startswith("/")
                        or "\\" in name
                        or any(part in ("", ".", "..") for part in name.split("/"))
                        or name in names
                        or type(digest) is not str
                        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    ):
                        refuse()
                    names.add(name)
                    integer(file["size"], 0, 1048576)
            if key == "limits":
                if not isinstance(child, dict) or set(child) not in (
                    {"max_material_bytes", "dispatch_timeout_seconds"},
                    {"max_input_bytes", "max_output_bytes", "dispatch_timeout_seconds"},
                ):
                    refuse()
            if key in ("refs", "steps", "catalog_bindings"):
                if not isinstance(child, list) or len(child) > 128:
                    refuse()
                fields = {
                    "refs": {"package_key", "entity_kind", "key", "digest"},
                    "steps": {"id", "handler", "input_schema_sha256", "output_schema_sha256"},
                    "catalog_bindings": {"package_key", "entity_kind", "key", "ref"},
                }[key]
                for item in child:
                    descriptor = obj(item, fields)
                    for field, scalar in descriptor.items():
                        if field == "ref":
                            pin(scalar)
                        elif field == "digest" or field.endswith("_sha256"):
                            if (
                                type(scalar) is not str
                                or re.fullmatch(r"[0-9a-f]{64}", scalar) is None
                            ):
                                refuse()
                        elif type(scalar) is not str or (
                            not (field == "package_key" and scalar == "@profile")
                            and re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", scalar) is None
                        ):
                            refuse()
            if key in (
                "size",
                "duration_ns",
                "max_input_bytes",
                "max_output_bytes",
                "max_material_bytes",
                "dispatch_timeout_seconds",
            ):
                integer(child, 0)
            if isinstance(child, str):
                if "\x00" in child:
                    refuse()
                child.encode("utf-8")
            metadata_tree(child)
    elif isinstance(value, list):
        for child in value:
            metadata_tree(child)


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
    capture = kind in (
        "contract-case-input",
        "contract-case-records",
        "contract-input-context",
        "evaluation-admission",
    )
    if (
        not isinstance(body, dict)
        or body.get("owner_id" if capture else "created_by") != owner
        or (capture and record["revision"] != 1)
        or (
            kind in ("contract-case-input", "contract-case-records")
            and len(canonical(record)) > 8192
        )
    ):
        refuse()
    return body


async def capture_input(
    connection: AsyncConnection,
    input_ref: object,
    kind: str,
    version: int,
    body: dict[str, object],
    index: dict[str, object],
    owner: str,
    group: str,
) -> None:
    """Join retained producer metadata only, without opening schema/material bytes."""
    value = await retained(connection, input_ref, kind, owner, group)
    obj(value, {"version", "value", "schema_ref", "owner_id", "context_ref", "provenance"})
    integer(value["version"], 1, 1)
    if not isinstance(value["value"], dict):
        refuse()
    schema = pin(value["schema_ref"], "schema")
    provenance = obj(
        value["provenance"], {"producer_key", "producer_revision", "command_id", "source_kind"}
    )
    if provenance != {
        "producer_key": kind,
        "producer_revision": kind + "-v1",
        "command_id": uuid_text(provenance["command_id"]),
        "source_kind": "SYNTHETIC",
    }:
        refuse()
    context = await retained(
        connection, value["context_ref"], "contract-input-context", owner, group
    )
    obj(
        context,
        {
            "version",
            "namespace",
            "owner_id",
            "basis_ref",
            "snapshot_ref",
            "procedure_ref",
            "schema_ref",
            "selection_ref",
            "mission_ref",
            "focus_ref",
        },
    )
    integer(context["version"], version, version)
    procedure = pin(context["procedure_ref"], "procedure")
    basis = pin(context["basis_ref"], "evaluation-admission")
    if canonical(context) != canonical(
        {
            "version": version,
            "namespace": "PACKAGE_EVAL",
            "owner_id": owner,
            "basis_ref": basis,
            "snapshot_ref": body["snapshot_ref"],
            "procedure_ref": procedure,
            "schema_ref": schema,
            "selection_ref": None,
            "mission_ref": None,
            "focus_ref": None,
        }
    ):
        refuse()
    admission = await retained(connection, basis, "evaluation-admission", owner, group)
    integer(admission.get("version"), version, version)
    if canonical(admission) != canonical(
        {
            "version": version,
            "namespace": "PACKAGE_EVAL",
            "owner_id": owner,
            "snapshot_ref": body["snapshot_ref"],
            "procedure_ref": procedure,
            "schema_ref": schema,
            "material_digest": body["material_digest"],
            "resolved_index_digest": body["resolved_index_digest"],
            "compiler_revision": body["compiler_revision"],
        }
    ):
        refuse()
    # The admission records the producer's procedure/schema association. Check
    # both exact pins against this snapshot's index, not a current compiler.
    bindings = cast(list[dict[str, object]], index["catalog_bindings"])
    procedures = [b for b in bindings if b["ref"] == procedure and b["entity_kind"] == "procedure"]
    schemas = [b for b in bindings if b["ref"] == schema and b["entity_kind"] == "schema"]
    if (
        len(procedures) != 1
        or len(schemas) != 1
        or procedures[0]["package_key"] != schemas[0]["package_key"]
        or procedure not in pins(body["candidate_refs"])
        or schema not in pins(body["candidate_refs"])
        or not any(
            canonical(ref)
            == canonical(
                {
                    "package_key": procedures[0]["package_key"],
                    "entity_kind": "procedure",
                    "key": procedures[0]["key"],
                    "digest": procedure["digest"],
                }
            )
            for ref in cast(list[object], index["refs"])
        )
    ):
        refuse()


def named_index(
    body: dict[str, object],
    index: dict[str, object],
    sources: list[tuple[dict[str, object], dict[str, object]]],
) -> list[CatalogBinding]:
    """Project names only after joining the retained index to source identities."""
    bindings = [
        CatalogBinding.model_validate(item)
        for item in cast(list[object], index["catalog_bindings"])
    ]
    candidates = pins(body["candidate_refs"])
    closure = pins(body["dependency_closure_refs"])
    if not bindings:
        # Legacy empty index: do not invent names from current source/compiler.
        if any(ref["kind"] != "profile" for ref in candidates) or any(
            s["source_kind"] != "profile" for _, s in sources
        ):
            refuse()
        return []
    by_identity: dict[tuple[str, str, str], CatalogBinding] = {}
    identities: set[str] = set()
    for binding in bindings:
        identity: tuple[str, str, str] = (binding.package_key, binding.entity_kind, binding.key)
        if (
            identity in by_identity
            or binding.ref.id in identities
            or binding.entity_kind != binding.ref.kind
            or (binding.package_key == "@profile") != (binding.entity_kind == "profile")
            or (binding.entity_kind == "package" and binding.key != binding.package_key)
        ):
            refuse()
        by_identity[identity] = binding
        identities.add(binding.ref.id)
    for binding in bindings:
        if (
            binding.package_key != "@profile"
            and (binding.package_key, "package", binding.package_key) not in by_identity
        ):
            refuse()
    expected_local: set[bytes] = set()
    namespaces: set[str] = set()
    for source_ref, source in sources:
        namespace = source.get("package_key", "@profile")
        if type(namespace) is not str or namespace in namespaces:
            refuse()
        namespaces.add(namespace)
        digest = source.get("package_digest", source_ref["digest"])
        if source["source_kind"] == "package" and digest != sha(source["files"]):
            refuse()
        source_identities = source["identities"]
        if not isinstance(source_identities, list) or not 1 <= len(source_identities) <= 128:
            refuse()
        seen: set[tuple[str, str, str]] = set()
        for identity_value in source_identities:
            if (
                not isinstance(identity_value, list)
                or len(identity_value) != 2
                or not all(type(v) is str for v in identity_value)
            ):
                refuse()
            identity = (namespace, identity_value[0], identity_value[1])
            local_binding = by_identity.get(identity)
            if local_binding is None or identity in seen:
                refuse()
            seen.add(identity)
            ref = local_binding.ref.model_dump(mode="json")
            if ref not in candidates or ref["digest"] != digest:
                refuse()
            expected_local.add(canonical(ref))
    if expected_local != {canonical(ref) for ref in candidates}:
        refuse()
    for binding in bindings:
        ref = binding.ref.model_dump(mode="json")
        if binding.package_key in namespaces:
            if canonical(ref) not in expected_local:
                refuse()
        else:
            package = by_identity[(binding.package_key, "package", binding.package_key)]
            if (
                package.ref.model_dump(mode="json") not in closure
                or binding.ref.digest != package.ref.digest
            ):
                refuse()
    seen_refs: set[tuple[str, str, str]] = set()
    for qualified in cast(list[dict[str, object]], index["refs"]):
        identity = (
            str(qualified["package_key"]),
            str(qualified["entity_kind"]),
            str(qualified["key"]),
        )
        selected_binding = by_identity.get(identity)
        if (
            identity in seen_refs
            or selected_binding is None
            or selected_binding.ref.digest != qualified["digest"]
        ):
            refuse()
        seen_refs.add(identity)
    # The producer retains ALL external release bindings, including unselected
    # ones. Only exact candidate/closure pins are named in this projection; the
    # remaining release material is unavailable, not implicitly verified.
    return [
        binding
        for binding in bindings
        if binding.ref.model_dump(mode="json") in candidates + closure
    ]


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
                    "AND (CAST(:after AS uuid) IS NULL OR publication_id > CAST(:after AS uuid)) "
                    "ORDER BY publication_id LIMIT 21"
                ),
                {"after": after},
            )
        )
        .mappings()
        .all()
    )
    entries = []
    for head in rows:
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
        items=entries[:20],
        has_more=more,
        next_after=entries[19].publication_ref.id if more else None,
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
    source_bodies: list[tuple[dict[str, object], dict[str, object]]] = []
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
        if source["author_kind"] not in ("OPERATOR", "AI", "IMPORT"):
            refuse()
        if source_kind == "profile":
            if profile_seen or ref != body["draft_ref"] or source["key"] != body["profile_key"]:
                refuse()
            profile_seen = True
        source_bodies.append((ref, source))
    if not profile_seen:
        refuse()
    bindings = named_index(body, index, source_bodies)
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
    protocol: object = None
    shared_input: dict[str, object] | None = None
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
        if kind == "STATIC":
            protocol = receipt["protocol"]
        if type(protocol) is not str or protocol not in EVALUATION_PROTOCOLS:
            refuse()
        evaluator, version, input_kind = EVALUATION_PROTOCOLS[protocol]
        if (
            receipt["status"] != kind + "_PASS"
            or receipt["evaluation_kind"] != kind
            or receipt["reason"] is not None
            or receipt["effective"] is not None
            or receipt["model_ref"] is not None
            or receipt["requested"] != index["requested"]
            or receipt["protocol"] != protocol
            or receipt["evaluator"] != evaluator
            or receipt["target_evidence"] != "NOT_APPLICABLE"
            or receipt["evidence_refs"] != []
        ):
            refuse()
        integer(receipt["duration_ns"], 0)
        if version:
            ref = pin(receipt["input_ref"], input_kind)
            if kind == "STATIC":
                shared_input = ref
                await capture_input(connection, ref, input_kind, version, body, index, owner, group)
            elif ref != shared_input:
                refuse()
        elif kind == "PURE":
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
            "catalog_bindings": bindings,
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
