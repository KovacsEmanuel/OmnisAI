"""Independent native records grammar on resealed wire; not DB or installed QA."""

import base64
import copy
import json
from pathlib import Path

import pytest
from composition_fixture import ref, seal
from omnis_hermes.managed_admission_contract import canonical, digest, validate_stage
from omnis_hermes.prompt_bundle import CAPTURE_COMPOSER_REVISION
from test_c03_case_input import capture_fixture
from test_prompt_bundle import reseal_graph

SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "skills/recon-mapping-contract/templates/schemas/records.schema.json"
)
ROW = {"method": "GET", "path": "/records-é🦊", "status": 200}


def relink_records(stage, sections):
    material = sections[4]
    context, item = material["context"], material["input"]
    seal(context)
    item["payload"]["context_ref"] = ref(context)
    seal(item)
    slots = [{"slot_name": "records", "refs": [ref(item)]}]
    brief, bound = sections[2]["record"], sections[3]["record"]
    bound["payload"]["slot_values"] = copy.deepcopy(slots)
    bound["payload"]["resolved_procedure"]["probe"][0]["input_bindings"] = [
        {"name": "records", "source_ref": ref(item), "selector": "records"}
    ]
    brief["payload"]["procedure_bindings"][0]["slot_values"] = copy.deepcopy(slots)
    brief["payload"]["input_artifact_refs"] = [ref(item)]
    brief["payload"]["context"] = brief["payload"]["context"][:2] + [
        {
            "ref": ref(item),
            "epistemic_state": "OBSERVED",
            "summary": "Synthetic records; not method execution.",
            "mandatory": True,
        }
    ]
    reseal_graph(stage, sections, stage["compositions"][0]["payload"]["prompt_bundle"])


def records_fixture(value=None):
    stage = capture_fixture()
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    material, skill = sections[4], sections[5]
    schema = material["schema"]
    raw = SCHEMA.read_bytes()
    for file in skill["files"]:
        if file["path"] == schema["path"]:
            file.update(path="templates/records.schema.json", sha256=digest(raw), size=len(raw))
    skill["files"].sort(key=lambda f: f["path"].encode())
    skill["package_ref"]["digest"] = digest(canonical(skill["files"]))
    schema.update(
        path="templates/records.schema.json",
        document=json.loads(raw),
        source_b64=base64.b64encode(raw).decode(),
    )
    schema["ref"]["digest"] = skill["package_ref"]["digest"]
    for body in (material["context"]["payload"], material["input"]["payload"]):
        body["schema_ref"] = copy.deepcopy(schema["ref"])
    for b in (payload["prompt_bundle"]["payload"], sections[2]["record"]["payload"]):
        b["package_refs"][0] = copy.deepcopy(skill["package_ref"])
    material["version"] = material["context"]["payload"]["version"] = 2
    item = material["input"]
    item["kind"] = "contract-case-records"
    item["payload"]["value"] = (
        {"records": [copy.deepcopy(ROW)]} if value is None else copy.deepcopy(value)
    )
    item["payload"]["provenance"].update(
        producer_key="contract-case-records", producer_revision="contract-case-records-v1"
    )
    p = sections[3]["record"]["payload"]["resolved_procedure"]
    p["input_schema_ref"] = copy.deepcopy(schema["ref"])
    p["key"] = "map-records"
    p["probe"] = p["probe"][1:]
    p["method_requirements"][0]["step_ids"] = [s["id"] for s in p["probe"]]
    stage["protocol"] = "omnis-managed-admission-v3"
    stage["manifest"]["payload"]["composition_version"] = 3
    relink_records(stage, sections)
    return stage


@pytest.mark.parametrize(
    "value",
    [
        {"records": []},
        {"records": [ROW]},
        {"records": [{"method": "GET", "path": "/", "status": 100}] * 128},
        {"records": [{"method": "POST", "path": "/" + "é" * 239, "status": 599}]},
        {"records": [ROW, {**ROW, "status": 404}, ROW]},
    ],
)
def test_native_records_positive_value_is_structured_and_immutable(value):
    stage = records_fixture(value)
    before = canonical(stage)
    assert validate_stage(stage) == stage["manifest"]
    sections = json.loads(stage["compositions"][0]["payload"]["text"])
    assert sections[4]["input"]["payload"]["value"] == value
    assert canonical(stage) == before


BAD_VALUES = [
    {},
    {"records": [], "extra": 1},
    {"records": "[]"},
    {"records": [None]},
    {"records": [1]},
    {"records": [{"method": "GET", "path": "/"}]},
    {"records": [{**ROW, "extra": False}]},
    {"records": [{**ROW, "method": "get"}]},
    {"records": [{**ROW, "method": "TRACE"}]},
    {"records": [{**ROW, "path": "no-slash"}]},
    {"records": [{**ROW, "path": "/a b"}]},
    {"records": [{**ROW, "path": "/a\\b"}]},
    {"records": [{**ROW, "path": "/a\n"}]},
    {"records": [{**ROW, "path": "/\x00"}]},
    {"records": [{**ROW, "path": "/\x7f"}]},
    {"records": [{**ROW, "path": "/\x85"}]},
    {"records": [{**ROW, "path": "\ufeff/"}]},
    {"records": [{**ROW, "path": "/" + "x" * 240}]},
    *[{"records": [{**ROW, "status": status}]} for status in (True, "200", 99, 600, None)],
    {"records": [ROW] * 129},
    {"capture": "[]"},
]


@pytest.mark.parametrize("value", BAD_VALUES)
def test_native_records_invalid_values_on_positive_channel(value):
    assert validate_stage(records_fixture())
    with pytest.raises(ValueError):
        validate_stage(records_fixture(value))


@pytest.mark.parametrize(
    "attack",
    [
        "owner",
        "namespace",
        "context-version",
        "input-version",
        "kind",
        "provenance",
        "bool-ref",
        "foreign-run",
        "schema-extra",
        "schema-bool",
        "schema-weak",
        "schema-path",
        "schema-source",
        "schema-bom",
        "schema-utf8",
        "schema-size",
        "schema-base64",
        "file-hash",
        "file-size",
        "old-composer",
        "old-wire",
        "old-composition",
        "old-material",
    ],
)
def test_native_records_resealed_material_denials(attack):
    stage = records_fixture()
    assert validate_stage(stage)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    m, p = sections[4], payload["prompt_bundle"]
    c, v, s = m["context"]["payload"], m["input"]["payload"], m["schema"]
    if attack == "owner":
        v["owner_id"] = "00000000-0000-4000-8000-000000000001"
    elif attack == "namespace":
        c["namespace"] = "PACKAGE_EVAL"
    elif attack == "context-version":
        c["version"] = 1
    elif attack == "input-version":
        v["version"] = 2
    elif attack == "kind":
        m["input"]["kind"] = "contract-case-input"
    elif attack == "provenance":
        v["provenance"]["producer_revision"] = "contract-case-input-v1"
    elif attack == "bool-ref":
        s["ref"]["revision"] = True
    elif attack == "foreign-run":
        c["basis_ref"]["id"] = "00000000-0000-4000-8000-000000000001"
    elif attack == "schema-extra":
        s["document"]["title"] = "not admitted"
    elif attack == "schema-bool":
        s["document"]["properties"]["records"]["maxItems"] = True
    elif attack == "schema-weak":
        del s["document"]["properties"]["records"]["items"]["properties"]["method"]["enum"]
    elif attack == "schema-path":
        s["path"] = "templates/absent.schema.json"
    elif attack == "schema-source":
        s["source_b64"] = base64.b64encode(b"{}").decode()
    elif attack == "schema-bom":
        s["source_b64"] = base64.b64encode(b"\xef\xbb\xbf" + SCHEMA.read_bytes()).decode()
    elif attack == "schema-utf8":
        s["source_b64"] = base64.b64encode(b"\xff").decode()
    elif attack == "schema-size":
        s["source_b64"] = base64.b64encode(SCHEMA.read_bytes() + b" " * 8192).decode()
    elif attack == "schema-base64":
        s["source_b64"] += "="
    elif attack in ("file-hash", "file-size"):
        file = next(f for f in sections[5]["files"] if f["path"] == s["path"])
        file["sha256" if attack == "file-hash" else "size"] = (
            "0" * 64 if attack == "file-hash" else len(SCHEMA.read_bytes()) + 1
        )
    elif attack == "old-composer":
        p["payload"]["composer_revision"] = CAPTURE_COMPOSER_REVISION
    elif attack == "old-wire":
        stage["protocol"] = "omnis-managed-admission-v2"
    elif attack == "old-composition":
        stage["manifest"]["payload"]["composition_version"] = 2
    elif attack == "old-material":
        m["version"] = 1
    else:
        raise AssertionError(attack)
    if attack in ("schema-extra", "schema-bool", "schema-weak"):
        s["source_b64"] = base64.b64encode(canonical(s["document"])).decode()
    relink_records(stage, sections)
    with pytest.raises(ValueError):
        validate_stage(stage)


@pytest.mark.parametrize(
    "attack",
    [
        "missing",
        "duplicate",
        "zero",
        "two",
        "unknown",
        "forward",
        "global",
        "cross-attempt",
        "undeclared",
        "selector",
        "omit-requirement",
        "without-slot",
    ],
)
def test_native_records_assignment_denials(attack):
    stage = records_fixture()
    assert validate_stage(stage)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    brief, bound = sections[2]["record"]["payload"], sections[3]["record"]["payload"]
    p = bound["resolved_procedure"]
    slots = bound["slot_values"]
    if attack == "missing":
        slots.clear()
    elif attack == "duplicate":
        slots.append(copy.deepcopy(slots[0]))
    elif attack == "zero":
        slots[0]["refs"] = []
    elif attack == "two":
        slots[0]["refs"] *= 2
    elif attack == "unknown":
        slots[0]["slot_name"] = "capture"
    elif attack in ("forward", "global", "cross-attempt", "undeclared"):
        source = p["probe"][1]["input_bindings"][0]["source_ref"]
        if attack == "forward":
            source["step_id"] = "build-map"
        elif attack == "global":
            source["step_id"] = "other-procedure.normalize"
        elif attack == "cross-attempt":
            source["attempt_id"] = brief["header"]["attempt_id"]
        else:
            source["output_name"] = "surface_map"
    elif attack == "selector":
        p["probe"][0]["input_bindings"][0]["selector"] = "capture"
    elif attack == "omit-requirement":
        brief["method_plan"]["requirements"] = []
    elif attack == "without-slot":
        slots.clear()
        brief["input_artifact_refs"] = []
        brief["context"] = brief["context"][:2]
        sections.pop(4)
        stage["manifest"]["payload"]["composition_version"] = 1
        stage["protocol"] = "omnis-managed-admission-v2"
    else:
        raise AssertionError(attack)
    brief["procedure_bindings"][0]["slot_values"] = copy.deepcopy(slots)
    reseal_graph(stage, sections, payload["prompt_bundle"])
    with pytest.raises(ValueError):
        validate_stage(stage)


def test_records_schema_resealed_wrong_bytes_and_frame_overflow():
    stage = records_fixture()
    assert validate_stage(stage)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    schema = sections[4]["schema"]
    raw = SCHEMA.read_bytes() + b" "
    schema["source_b64"] = base64.b64encode(raw).decode()
    relink_records(stage, sections)
    with pytest.raises(ValueError):
        validate_stage(stage)
    # Individually valid 128 long records exceed the existing aggregate caps.
    with pytest.raises(ValueError):
        validate_stage(records_fixture({"records": [{**ROW, "path": "/" + "x" * 239}] * 128}))


@pytest.mark.parametrize(
    "value",
    [
        {"records": []},
        {"records": [ROW]},
        {"records": [{"method": "GET", "path": "/", "status": 100}] * 128},
        *BAD_VALUES,
    ],
)
def test_api_native_records_value_parity(value):
    from omnis.modules.tasks import managed_composition

    stage = records_fixture(value)
    outcomes = []
    try:
        validate_stage(stage)
        outcomes.append(True)
    except ValueError:
        outcomes.append(False)
    try:
        managed_composition.validate(
            stage["compositions"][0], stage["manifest"]["payload"]["entries"][0], stage["manifest"]
        )
        outcomes.append(True)
    except ValueError:
        outcomes.append(False)
    assert outcomes[0] == outcomes[1]
    assert outcomes[0] == (value not in BAD_VALUES)
