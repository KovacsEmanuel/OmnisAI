"""Bounded C03 inert case input. Validation is not persistence/admission authority."""

import base64
import binascii
from copy import deepcopy
from typing import TypeAlias

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import bounded, canonical, load_json

RecordEnvelope: TypeAlias = dict[str, object]
CAPTURE_SLOT = {
    "name": "capture",
    "expected_kind": "contract-case-input",
    "min_items": 1,
    "max_items": 1,
}
CAPTURE_BINDING = {
    "name": "capture",
    "source_ref": {"kind": "CASE_SLOT_REF", "name": "capture"},
    "selector": "capture",
}
PRODUCER_REVISION = "contract-case-input-v1"


def utf8_json_text(raw: bytes) -> str:
    """Decode authored request bytes exactly; JSON must not auto-detect encodings."""
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise CatalogError("INVALID_JSON") from None
    if value.startswith("\ufeff"):
        raise CatalogError("INVALID_JSON")
    return value


def _object(value: object, fields: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or any(type(k) is not str for k in value):
        raise CatalogError("INVALID_CASE_INPUT")
    if fields is not None and set(value) != fields:
        raise CatalogError("INVALID_CASE_INPUT")
    return value


def _text(value: object) -> str:
    if type(value) is not str or value.startswith("\ufeff"):
        raise CatalogError("INVALID_CASE_INPUT")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise CatalogError("INVALID_CASE_INPUT") from None
    if any((ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) <= 159 for c in value):
        raise CatalogError("INVALID_CASE_INPUT")
    return value


def _ref(value: object, kind: str) -> dict[str, object]:
    from omnis.modules.settings.candidate_catalog import valid_ref

    ref = valid_ref(value)
    if ref["kind"] != kind:
        raise CatalogError("INVALID_CASE_INPUT")
    return ref


def _record(value: object, kind: str) -> RecordEnvelope:
    record = records.checked(value)
    _ref(records.reference(record), kind)
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or record["revision"] != 1
    ):
        raise CatalogError("INVALID_CASE_INPUT")
    _object(record["payload"])
    return record


def capture_schema(raw_schema: bytes) -> dict[str, object]:
    if type(raw_schema) is not bytes or len(raw_schema) > 8192:
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    try:
        raw_text = raw_schema.decode("utf-8", errors="strict")
    except UnicodeError:
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA") from None
    if raw_text.startswith("\ufeff"):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    document = _object(
        load_json(raw_text), {"$schema", "type", "properties", "required", "additionalProperties"}
    )
    if (
        document["$schema"] != "https://json-schema.org/draft/2020-12/schema"
        or document["type"] != "object"
        or document["additionalProperties"] is not False
        or document["required"] != ["capture"]
    ):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    definition = _object(_object(document["properties"], {"capture"})["capture"])
    if set(definition) not in ({"type", "maxLength"}, {"type", "maxLength", "minLength"}):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    maximum, minimum = definition["maxLength"], definition.get("minLength", 0)
    if (
        definition["type"] != "string"
        or type(maximum) is not int
        or not 1 <= maximum <= 65536
        or type(minimum) is not int
        or not 0 <= minimum <= maximum
    ):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    return deepcopy(document)


def validate_value(value: object, raw_schema: bytes) -> dict[str, object]:
    document = capture_schema(raw_schema)
    obj = _object(value, {"capture"})
    text = _text(obj["capture"])
    definition = _object(_object(document["properties"])["capture"])
    maximum, minimum = definition["maxLength"], definition.get("minLength", 0)
    if not isinstance(maximum, int) or not isinstance(minimum, int):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    if (
        not minimum <= len(text) <= maximum
        or len(text.encode("utf-8")) > 4096
        or len(canonical(obj)) > 8192
    ):
        raise CatalogError("CASE_INPUT_LIMIT")
    return deepcopy(obj)


def _context(value: object, *, namespace: str, owner_id: str) -> RecordEnvelope:
    from omnis.modules.settings.candidate_catalog import uuid_string

    uuid_string(owner_id)
    if namespace not in ("RUN", "PACKAGE_EVAL"):
        raise CatalogError("INVALID_CASE_INPUT")
    record = _record(value, "contract-input-context")
    body = _object(
        record["payload"],
        set(
            "version namespace owner_id basis_ref snapshot_ref procedure_ref schema_ref selection_ref mission_ref focus_ref".split()
        ),
    )
    if (
        type(body["version"]) is not int
        or body["version"] != 1
        or body["namespace"] != namespace
        or body["owner_id"] != owner_id
    ):
        raise CatalogError("INVALID_CASE_INPUT")
    _ref(body["basis_ref"], "managed-run" if namespace == "RUN" else "evaluation-admission")
    _ref(body["snapshot_ref"], "run-snapshot" if namespace == "RUN" else "candidate-snapshot")
    _ref(body["procedure_ref"], "procedure")
    _ref(body["schema_ref"], "schema")
    for field, kind in (
        ("selection_ref", "execution-selection"),
        ("mission_ref", "mission"),
        ("focus_ref", "focus"),
    ):
        if namespace == "RUN":
            _ref(body[field], kind)
        elif body[field] is not None:
            raise CatalogError("INVALID_CASE_INPUT")
    return record


def produce_input(
    context_record: object, value: object, raw_schema: bytes, command_id: str
) -> RecordEnvelope:
    from omnis.modules.settings.candidate_catalog import uuid_string

    body = _object(_object(context_record).get("payload"))
    context = _context(
        context_record,
        namespace=_text(body.get("namespace")),
        owner_id=uuid_string(body.get("owner_id")),
    )
    record = records.envelope(
        "contract-case-input",
        {
            "version": 1,
            "value": validate_value(value, raw_schema),
            "schema_ref": deepcopy(body["schema_ref"]),
            "owner_id": body["owner_id"],
            "context_ref": records.reference(context),
            "provenance": {
                "producer_key": "contract-case-input",
                "producer_revision": PRODUCER_REVISION,
                "command_id": uuid_string(command_id),
                "source_kind": "SYNTHETIC",
            },
        },
    )
    if len(canonical(record)) > 8192:
        raise CatalogError("CASE_INPUT_LIMIT")
    return record


def validate_material(material: object, *, namespace: str, owner_id: str) -> dict[str, object]:
    from omnis.modules.settings.candidate_catalog import uuid_string
    from omnis.modules.settings.skill_catalog import safe_path

    bounded(material)
    section = _object(material, {"section", "version", "context", "input", "schema"})
    if (
        section["section"] != "case-input"
        or type(section["version"]) is not int
        or section["version"] != 1
    ):
        raise CatalogError("INVALID_CASE_INPUT")
    context = _context(section["context"], namespace=namespace, owner_id=owner_id)
    context_body = _object(context["payload"])
    schema = _object(section["schema"], {"ref", "document", "path", "source_b64"})
    if _ref(schema["ref"], "schema") != context_body["schema_ref"]:
        raise CatalogError("INVALID_CASE_INPUT")
    path = _text(schema["path"])
    safe_path(path)
    encoded = _text(schema["source_b64"])
    if len(encoded) > 10924:
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA") from None
    if base64.b64encode(raw).decode("ascii") != encoded or canonical(
        schema["document"]
    ) != canonical(capture_schema(raw)):
        raise CatalogError("INVALID_CASE_INPUT_SCHEMA")
    record = _record(section["input"], "contract-case-input")
    body = _object(
        record["payload"],
        {"version", "value", "schema_ref", "owner_id", "context_ref", "provenance"},
    )
    if (
        type(body["version"]) is not int
        or body["version"] != 1
        or body["owner_id"] != owner_id
        or _ref(body["schema_ref"], "schema") != schema["ref"]
        or _ref(body["context_ref"], "contract-input-context") != records.reference(context)
    ):
        raise CatalogError("INVALID_CASE_INPUT")
    provenance = _object(
        body["provenance"], {"producer_key", "producer_revision", "command_id", "source_kind"}
    )
    if provenance != {
        "producer_key": "contract-case-input",
        "producer_revision": PRODUCER_REVISION,
        "command_id": uuid_string(provenance["command_id"]),
        "source_kind": "SYNTHETIC",
    }:
        raise CatalogError("INVALID_CASE_INPUT")
    validate_value(body["value"], raw)
    if len(canonical(record)) > 8192:
        raise CatalogError("CASE_INPUT_LIMIT")
    return deepcopy(section)


def material_section(
    context_record: object,
    input_record: object,
    schema_ref: object,
    raw_schema: bytes,
    *,
    schema_path: str,
) -> dict[str, object]:
    body = _object(_object(context_record).get("payload"))
    return validate_material(
        {
            "section": "case-input",
            "version": 1,
            "context": context_record,
            "input": input_record,
            "schema": {
                "ref": schema_ref,
                "document": capture_schema(raw_schema),
                "path": schema_path,
                "source_b64": base64.b64encode(raw_schema).decode("ascii"),
            },
        },
        namespace=_text(body.get("namespace")),
        owner_id=_text(body.get("owner_id")),
    )


def require_capture_slots(slots: object) -> None:
    if type(slots) is not list or len(slots) != 1:
        raise CatalogError("UNSUPPORTED_CAPTURE_SLOT")
    slot = _object(slots[0], set(CAPTURE_SLOT))
    if (
        type(slot["min_items"]) is not int
        or type(slot["max_items"]) is not int
        or slot != CAPTURE_SLOT
    ):
        raise CatalogError("UNSUPPORTED_CAPTURE_SLOT")


def slot_values(material: object) -> list[dict[str, object]]:
    section = _object(material)
    body = _object(_object(section.get("context")).get("payload"))
    checked = validate_material(
        material, namespace=_text(body.get("namespace")), owner_id=_text(body.get("owner_id"))
    )
    return [{"slot_name": "capture", "refs": [records.reference(_object(checked["input"]))]}]


def validate_slot_values(value: object, material: object) -> list[dict[str, object]]:
    if type(value) is not list or len(value) != 1:
        raise CatalogError("INVALID_SLOT_VALUES")
    entry = _object(value[0], {"slot_name", "refs"})
    refs = entry["refs"]
    if entry["slot_name"] != "capture" or type(refs) is not list or len(refs) != 1:
        raise CatalogError("INVALID_SLOT_VALUES")
    _ref(refs[0], "contract-case-input")
    expected = slot_values(material)
    if value != expected:
        raise CatalogError("INVALID_SLOT_VALUES")
    return deepcopy(expected)
