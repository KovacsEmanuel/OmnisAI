"""Strict publication selections; caller data never grants operator authority."""

import re

from .candidate_catalog import uuid_string, valid_ref
from .catalog_models import CatalogError
from .catalog_schema import bounded, canonical, load_json

SELECTION_FIELDS = frozenset(
    {
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
    }
)
REF_KINDS = {
    "draft_ref": "source-draft",
    "snapshot_ref": "candidate-snapshot",
    "technical_review_ref": "technical-review",
    "static_evaluation_ref": "evaluation-receipt",
    "pure_evaluation_ref": "evaluation-receipt",
    "confirmation_ref": "operator-confirmation",
    "publication_ref": "catalog-publication",
}


def clean_text(value: object) -> None:
    if isinstance(value, str):
        if "\x00" in value:
            raise CatalogError("INVALID_REQUEST")
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise CatalogError("INVALID_REQUEST") from None
    elif isinstance(value, dict):
        for key, child in value.items():
            clean_text(key)
            clean_text(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            clean_text(child)


def validate_request(operation: str, value: object) -> dict[str, object]:
    fields: dict[str, set[str] | frozenset[str]] = {
        "head": {"draft_ref"},
        "confirm": SELECTION_FIELDS,
        "publish": SELECTION_FIELDS | {"confirmation_ref"},
        "readback": {"publication_ref"},
        "snapshot": {"publication_ref"},
    }
    if operation not in fields or not isinstance(value, dict):
        raise CatalogError("INVALID_REQUEST")
    common = {"schema_version", "owner_id"}
    if operation not in ("head", "readback"):
        common.add("command_id")
    if set(value) != common | fields[operation]:
        raise CatalogError("INVALID_REQUEST")
    try:
        bounded(value)
        clean_text(value)
        if len(canonical(value)) > 1048576:
            raise CatalogError("INVALID_REQUEST")
    except CatalogError:
        raise CatalogError("INVALID_REQUEST") from None
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise CatalogError("INVALID_REQUEST")
    uuid_string(value["owner_id"])
    if "command_id" in common:
        uuid_string(value["command_id"])
    for field, kind in REF_KINDS.items():
        if field in value and valid_ref(value[field])["kind"] != kind:
            raise CatalogError("INVALID_REQUEST")
    if operation in ("confirm", "publish"):
        generation = value["expected_head_generation"]
        if type(generation) is not int or not 1 <= generation < 2**63:
            raise CatalogError("INVALID_REQUEST")
        refs = value["source_draft_refs"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 128:
            raise CatalogError("INVALID_REQUEST")
        for ref in refs:
            if valid_ref(ref)["kind"] != "source-draft":
                raise CatalogError("INVALID_REQUEST")
        if len({canonical(ref) for ref in refs}) != len(refs) or value["draft_ref"] not in refs:
            raise CatalogError("INVALID_REQUEST")
        if value["static_evaluation_ref"] == value["pure_evaluation_ref"]:
            raise CatalogError("INVALID_REQUEST")
        for field in ("material_digest", "resolved_index_digest", "dependency_closure_digest"):
            sha = value[field]
            if type(sha) is not str or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
                raise CatalogError("INVALID_REQUEST")
    return value


def selection(value: dict[str, object]) -> dict[str, object]:
    return {key: value[key] for key in SELECTION_FIELDS}


def load_request(raw: bytes) -> object:
    value = load_json(raw)
    clean_text(value)
    return value
