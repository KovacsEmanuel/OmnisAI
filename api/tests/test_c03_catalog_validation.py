"""Strict shared material seam; records here are unit fixtures, not authority."""

import base64
from pathlib import Path
from uuid import uuid4

import pytest

from fixtures.b06a.consumer import mapping, sequence, write_yaml, yaml_object
from fixtures.c03_capture import CAPTURE_SLOT, capture_seed
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.settings.skill_catalog import compile_catalog
from omnis.modules.tasks.contract_case_input import (
    capture_schema,
    material_section,
    produce_input,
    require_capture_slots,
    slot_values,
    validate_material,
    validate_slot_values,
    validate_value,
)

RAW = b'{"$schema":"https://json-schema.org/draft/2020-12/schema", "type":"object", "properties":{"capture":{"type":"string","maxLength":65536}}, "required":["capture"], "additionalProperties":false}\n'


def material(namespace: str = "PACKAGE_EVAL", value: str = "[]") -> dict[str, object]:
    def ref(kind: str) -> dict[str, object]:
        return store.reference(store.envelope(kind, {}))

    context = store.envelope(
        "contract-input-context",
        {
            "version": 1,
            "namespace": namespace,
            "owner_id": str(uuid4()),
            "basis_ref": ref("managed-run" if namespace == "RUN" else "evaluation-admission"),
            "snapshot_ref": ref("run-snapshot" if namespace == "RUN" else "candidate-snapshot"),
            "procedure_ref": ref("procedure"),
            "schema_ref": ref("schema"),
            "selection_ref": ref("execution-selection") if namespace == "RUN" else None,
            "mission_ref": ref("mission") if namespace == "RUN" else None,
            "focus_ref": ref("focus") if namespace == "RUN" else None,
        },
    )
    return material_section(
        context,
        produce_input(context, {"capture": value}, RAW, str(uuid4())),
        mapping(context["payload"])["schema_ref"],
        RAW,
        schema_path="templates/schemas/capture.schema.json",
    )


@pytest.mark.parametrize("namespace", ["RUN", "PACKAGE_EVAL"])
def test_material_exact_bytes_namespace_and_copy(namespace: str) -> None:
    section = material(namespace, "é\n\t🦊")
    owner = mapping(mapping(section["context"])["payload"])["owner_id"]
    assert isinstance(owner, str)
    validated = validate_material(section, namespace=namespace, owner_id=owner)
    assert validated == section and validated is not section
    encoded = mapping(section["schema"])["source_b64"]
    assert isinstance(encoded, str)
    assert base64.b64decode(encoded) == RAW
    assert validate_slot_values(slot_values(section), section) == slot_values(section)
    with pytest.raises(CatalogError):
        validate_material(
            section,
            namespace="RUN" if namespace == "PACKAGE_EVAL" else "PACKAGE_EVAL",
            owner_id=owner,
        )
    with pytest.raises(CatalogError):
        validate_material(section, namespace=namespace, owner_id=str(uuid4()))


@pytest.mark.parametrize(
    "value",
    ["\ufeffx", "\r", "\x00", "\x7f", "\x85", "\ud800", "é" * 2049, "x" * 4097, "\t" * 4096],
)
def test_capture_text_controls_and_aggregate_byte_cap(value: str) -> None:
    with pytest.raises(CatalogError):
        validate_value({"capture": value}, RAW)


def test_capture_boundary_no_normalization() -> None:
    assert validate_value({"capture": "é" * 2048}, RAW) == {"capture": "é" * 2048}
    assert validate_value({"capture": ""}, RAW) == {"capture": ""}
    with pytest.raises(CatalogError):
        produce_input(material()["context"], {"capture": "\t" * 3800}, RAW, str(uuid4()))


@pytest.mark.parametrize(
    "mutation",
    [
        "schema-bool",
        "schema-pattern",
        "schema-extra",
        "schema-required",
        "schema-bom",
        "schema-size",
    ],
)
def test_schema_narrow_subset(mutation: str) -> None:
    document = capture_schema(RAW)
    definition = mapping(mapping(document["properties"])["capture"])
    if mutation == "schema-bool":
        definition["maxLength"] = True
    if mutation == "schema-pattern":
        definition["pattern"] = ".*"
    document["properties"] = {"capture": definition}
    if mutation == "schema-extra":
        document["title"] = "unsupported"
    if mutation == "schema-required":
        document["required"] = []
    raw = canonical(document)
    if mutation == "schema-bom":
        raw = b"\xef\xbb\xbf" + raw
    if mutation == "schema-size":
        raw += b" " * 8192
    with pytest.raises(CatalogError):
        capture_schema(raw)


@pytest.mark.parametrize(
    "attack", ["missing", "duplicate", "empty", "overflow", "unknown", "bool", "wrong-kind"]
)
def test_slot_values_strict(attack: str) -> None:
    section = material()
    values = slot_values(section)
    entry = mapping(values[0])
    refs = sequence(entry["refs"])
    ref = mapping(refs[0])
    if attack == "missing":
        values = []
    if attack == "duplicate":
        values *= 2
    if attack == "empty":
        values = [{"slot_name": "capture", "refs": []}]
    if attack == "overflow":
        values = [{"slot_name": "capture", "refs": refs * 2}]
    if attack == "unknown":
        values = [{"slot_name": "other", "refs": refs}]
    if attack in ("bool", "wrong-kind"):
        ref["revision" if attack == "bool" else "kind"] = (
            True if attack == "bool" else "evaluation-input"
        )
        values = [{"slot_name": "capture", "refs": [ref]}]
    with pytest.raises(CatalogError):
        validate_slot_values(values, section)


@pytest.mark.parametrize("field", ["basis_ref", "snapshot_ref", "procedure_ref", "schema_ref"])
def test_resealed_nested_ref_bool_refused(field: str) -> None:
    section = material()
    context = mapping(section["context"])
    body = mapping(context["payload"])
    altered_ref = mapping(body[field])
    altered_ref["revision"] = True
    body[field] = altered_ref
    context = store.envelope("contract-input-context", body)
    input_record = mapping(section["input"])
    input_body = mapping(input_record["payload"])
    input_body["context_ref"] = store.reference(context)
    section["context"] = context
    section["input"] = store.envelope("contract-case-input", input_body)
    with pytest.raises(CatalogError):
        validate_material(section, namespace="PACKAGE_EVAL", owner_id=str(body["owner_id"]))


@pytest.mark.parametrize(
    "value",
    [
        [],
        [CAPTURE_SLOT, CAPTURE_SLOT],
        [{**CAPTURE_SLOT, "min_items": True}],
        [{**CAPTURE_SLOT, "max_items": 2}],
    ],
)
def test_declaration_refuses_non_exact(value: object) -> None:
    with pytest.raises(CatalogError):
        require_capture_slots(value)


@pytest.mark.parametrize(
    "attack",
    ["document-bool", "path-parent", "input-version", "provenance", "context-schema-version"],
)
def test_material_rejects_resealed_or_substituted_fields(attack: str) -> None:
    section = material()
    context = mapping(section["context"])
    body = mapping(context["payload"])
    if attack == "document-bool":
        schema = mapping(section["schema"])
        document = mapping(schema["document"])
        document["additionalProperties"] = 0
        schema["document"] = document
        section["schema"] = schema
    elif attack == "path-parent":
        schema = mapping(section["schema"])
        schema["path"] = "../capture.json"
        section["schema"] = schema
    elif attack == "context-schema-version":
        context["schema_version"] = True
        from omnis.modules.settings.candidate_material import digest

        context["digest"] = digest(canonical({k: v for k, v in context.items() if k != "digest"}))
        section["context"] = context
    else:
        input_body = mapping(mapping(section["input"])["payload"])
        if attack == "input-version":
            input_body["version"] = True
        if attack == "provenance":
            input_body["provenance"] = {"source_kind": "RUN"}
        section["input"] = store.envelope("contract-case-input", input_body)
    with pytest.raises(CatalogError):
        validate_material(section, namespace="PACKAGE_EVAL", owner_id=str(body["owner_id"]))


@pytest.mark.parametrize(
    "prefix, suffix",
    [(b"\xef\xbb\xbf", b""), (b"", b" " * 8192)],
    ids=["utf8-bom", "raw-byte-limit"],
)
def test_capture_source_validates_original_schema_bytes(
    tmp_path: Path, prefix: bytes, suffix: bytes
) -> None:
    seed = capture_seed(tmp_path / "schema-raw")
    path = seed.package / "templates/schemas/capture.schema.json"
    path.write_bytes(prefix + path.read_bytes() + suffix)
    with pytest.raises(CatalogError):
        compile_catalog((seed.package,), seed.profile)


def test_capture_source_disallows_schema_extensions(tmp_path: Path) -> None:
    seed = capture_seed(tmp_path / "schema-extension")
    path = seed.package / "templates/schemas/capture.schema.json"
    document = capture_schema(path.read_bytes())
    document["title"] = "Not in C03 schema subset"
    path.write_bytes(canonical(document))
    with pytest.raises(CatalogError):
        compile_catalog((seed.package,), seed.profile)


def test_capture_declaration_requires_binding_and_strict_schema(tmp_path: Path) -> None:
    seed = capture_seed(tmp_path / "missing-binding")
    path = seed.package / "templates/procedures/map-capture.yaml"
    procedure = yaml_object(path)
    steps = sequence(procedure["probe"])
    first = mapping(steps[0])
    first["input_bindings"] = []
    procedure["probe"] = [first, *steps[1:]]
    write_yaml(path, procedure)
    with pytest.raises(CatalogError):
        compile_catalog((seed.package,), seed.profile)
