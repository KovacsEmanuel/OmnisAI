"""C03 independent native wire controls; synthetic records, not DB evidence."""

import base64
import copy
import json
from uuid import uuid4

import pytest
from composition_fixture import fixture, record, ref, reference, seal
from omnis_hermes.managed_admission_contract import canonical, digest, validate_stage
from test_prompt_bundle import reseal_graph


def capture_fixture(capture='[{"method":"GET","path":"/c03","status":200}]'):
    stage = fixture()
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    bundle = payload["prompt_bundle"]
    brief, bound = sections[2]["record"], sections[3]["record"]
    p = bound["payload"]["resolved_procedure"]
    p["key"] = "map-capture"
    p["limits"]["max_actions"] = 3
    brief["payload"]["limits"]["max_actions"] = 3
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["capture"],
        "properties": {"capture": {"type": "string", "maxLength": 65536}},
    }
    raw_schema = json.dumps(schema, indent=2).encode()
    schema_path = "templates/capture.schema.json"
    skill = sections[4]
    skill["files"].append(
        {"path": schema_path, "sha256": digest(raw_schema), "size": len(raw_schema)}
    )
    skill["files"].sort(key=lambda f: f["path"].encode())
    old_package = copy.deepcopy(skill["package_ref"])
    skill["package_ref"]["digest"] = digest(canonical(skill["files"]))
    for packages in (bundle["payload"]["package_refs"], brief["payload"]["package_refs"]):
        packages[0] = copy.deepcopy(skill["package_ref"])
    schema_ref = {**reference("schema"), "digest": skill["package_ref"]["digest"]}
    p["input_schema_ref"] = schema_ref
    steps = []
    for i, name in enumerate(("parse-capture", "normalize-operations", "build-map")):
        step = copy.deepcopy(p["probe"][0])
        step["id"] = name
        step["input_bindings"] = (
            []
            if not i
            else [
                {
                    "name": ("records", "operations")[i - 1],
                    "selector": None,
                    "source_ref": {
                        "kind": "STEP_OUTPUT",
                        "step_id": steps[-1]["id"],
                        "output_name": ("records", "operations")[i - 1],
                    },
                }
            ]
        )
        steps.append(step)
    p["probe"] = steps
    p["method_requirements"][0]["step_ids"] = [s["id"] for s in steps]
    header = brief["payload"]["header"]
    owner = str(uuid4())
    context = record(
        "contract-input-context",
        {
            "version": 1,
            "namespace": "RUN",
            "owner_id": owner,
            "basis_ref": {**reference("managed-run"), "id": header["run_id"]},
            "snapshot_ref": header["snapshot_ref"],
            "procedure_ref": bound["payload"]["procedure_ref"],
            "schema_ref": schema_ref,
            "selection_ref": brief["payload"]["execution_selection_ref"],
            "mission_ref": header["mission_revision"],
            "focus_ref": header["focus_ref"],
        },
    )
    input_record = record(
        "contract-case-input",
        {
            "version": 1,
            "value": {"capture": capture},
            "schema_ref": schema_ref,
            "owner_id": owner,
            "context_ref": ref(context),
            "provenance": {
                "producer_key": "contract-case-input",
                "producer_revision": "contract-case-input-v1",
                "command_id": str(uuid4()),
                "source_kind": "SYNTHETIC",
            },
        },
    )
    material = {
        "section": "case-input",
        "version": 1,
        "context": context,
        "input": input_record,
        "schema": {
            "ref": schema_ref,
            "document": schema,
            "path": schema_path,
            "source_b64": base64.b64encode(raw_schema).decode(),
        },
    }
    sections.insert(4, material)
    stage["manifest"]["payload"]["composition_version"] = 2
    relink(stage, sections)
    assert old_package != skill["package_ref"]
    return stage


def relink(stage, sections):
    material = sections[4]
    context, input_record = material["context"], material["input"]
    seal(context)
    input_record["payload"]["context_ref"] = ref(context)
    seal(input_record)
    slots = [{"slot_name": "capture", "refs": [ref(input_record)]}]
    brief, bound = sections[2]["record"], sections[3]["record"]
    bound["payload"]["slot_values"] = copy.deepcopy(slots)
    bound["payload"]["resolved_procedure"]["probe"][0]["input_bindings"] = [
        {"name": "capture", "source_ref": ref(input_record), "selector": "capture"}
    ]
    brief["payload"]["procedure_bindings"][0]["slot_values"] = copy.deepcopy(slots)
    brief["payload"]["input_artifact_refs"] = [ref(input_record)]
    brief["payload"]["context"] = brief["payload"]["context"][:2] + [
        {
            "ref": ref(input_record),
            "epistemic_state": "OBSERVED",
            "summary": "Backend supplied synthetic capture; no method execution.",
            "mandatory": True,
        }
    ]
    reseal_graph(stage, sections, stage["compositions"][0]["payload"]["prompt_bundle"])


def test_native_accepts_versioned_capture_material_and_consumes_value():
    stage = capture_fixture()
    before = canonical(stage)
    assert validate_stage(stage) == stage["manifest"]
    sections = json.loads(stage["compositions"][0]["payload"]["text"])
    assert (
        sections[4]["input"]["payload"]["value"]["capture"]
        == '[{"method":"GET","path":"/c03","status":200}]'
    )
    assert canonical(stage) == before


def test_native_legacy_composition_remains_strict_readable():
    stage = fixture()
    assert validate_stage(stage) == stage["manifest"]
    stage["manifest"]["payload"]["composition_version"] = True
    seal(stage["manifest"])
    with pytest.raises(ValueError):
        validate_stage(stage)


@pytest.mark.parametrize(
    "case",
    [
        "owner",
        "eval_namespace",
        "foreign_run",
        "foreign_mission",
        "schema_ref",
        "bool_schema_revision",
        "bool_context_revision",
        "bad_provenance",
        "unknown_value",
        "not_string",
        "bom",
        "nul",
        "control",
        "unicode_overflow",
        "max_length",
        "schema_source_mismatch",
        "schema_path",
        "raw_schema_bom",
        "unknown_material",
    ],
)
def test_native_capture_denials_on_same_fully_resealed_channel(case):
    stage = capture_fixture()
    assert validate_stage(stage)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    material = sections[4]
    c, v, s = material["context"]["payload"], material["input"]["payload"], material["schema"]
    if case == "owner":
        v["owner_id"] = str(uuid4())
    elif case == "eval_namespace":
        c["namespace"] = "PACKAGE_EVAL"
    elif case == "foreign_run":
        c["basis_ref"]["id"] = str(uuid4())
    elif case == "foreign_mission":
        c["mission_ref"]["id"] = str(uuid4())
    elif case == "schema_ref":
        v["schema_ref"]["digest"] = "a" * 64
    elif case == "bool_schema_revision":
        v["schema_ref"]["revision"] = True
    elif case == "bool_context_revision":
        material["context"]["revision"] = True
    elif case == "bad_provenance":
        v["provenance"]["source_kind"] = "MODEL"
    elif case == "unknown_value":
        v["value"]["unknown"] = "not admitted"
    elif case == "not_string":
        v["value"]["capture"] = True
    elif case in {"bom", "nul", "control", "unicode_overflow", "max_length"}:
        v["value"]["capture"] = {
            "bom": "\ufeff[]",
            "nul": "\x00",
            "control": "\x85",
            "unicode_overflow": "é" * 2049,
            "max_length": "x" * 4097,
        }[case]
    elif case == "schema_source_mismatch":
        s["document"]["properties"]["capture"]["maxLength"] = 1
    elif case == "schema_path":
        s["path"] = "../capture.schema.json"
    elif case == "raw_schema_bom":
        s["source_b64"] = base64.b64encode(
            b"\xef\xbb\xbf" + base64.b64decode(s["source_b64"])
        ).decode()
    else:
        material["unknown"] = "not admitted"
    relink(stage, sections)
    with pytest.raises(ValueError):
        validate_stage(stage)


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "zero",
        "overflow",
        "unknown",
        "foreign_ref",
        "bool_revision",
        "selector",
        "forward",
        "global",
        "cross_attempt",
        "omit_requirement",
        "downgrade",
    ],
)
def test_native_slot_and_step_output_binding_denials(case):
    stage = capture_fixture()
    assert validate_stage(stage)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    brief, bound = sections[2]["record"]["payload"], sections[3]["record"]["payload"]
    slot = bound["slot_values"][0]
    if case == "missing":
        bound["slot_values"] = []
    elif case == "duplicate":
        bound["slot_values"].append(copy.deepcopy(slot))
    elif case == "zero":
        slot["refs"] = []
    elif case == "overflow":
        slot["refs"] *= 2
    elif case == "unknown":
        slot["slot_name"] = "other"
    elif case == "foreign_ref":
        slot["refs"][0]["id"] = str(uuid4())
    elif case == "bool_revision":
        slot["refs"][0]["revision"] = True
    elif case == "selector":
        bound["resolved_procedure"]["probe"][0]["input_bindings"][0]["selector"] = "capture.path"
    elif case in {"forward", "global", "cross_attempt"}:
        source = bound["resolved_procedure"]["probe"][1]["input_bindings"][0]["source_ref"]
        if case == "cross_attempt":
            source["attempt_id"] = str(uuid4())
        else:
            source["step_id"] = (
                "build-map" if case == "forward" else "another-procedure.parse-capture"
            )
    elif case == "omit_requirement":
        brief["method_plan"]["requirements"] = []
    else:
        stage["manifest"]["payload"]["composition_version"] = 1
    reseal_graph(stage, sections, payload["prompt_bundle"])
    with pytest.raises(ValueError):
        validate_stage(stage)


def test_different_value_changes_suffix_not_invariant_prefix_or_old_assignment():
    from omnis_hermes.prompt_bundle import compose

    first = capture_fixture("é")
    before = canonical(first)
    payload = first["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    prefix = canonical(sections[:2])[:-1]
    sections[4]["input"]["payload"]["value"]["capture"] = "nou"
    new_stage = copy.deepcopy(first)
    relink(new_stage, sections)
    assert validate_stage(new_stage)
    second = compose(payload["prompt_bundle"], payload["preparation_receipt_ref"], sections)
    assert second["text"].encode().startswith(prefix)
    assert second["text"] != payload["text"]
    assert json.loads(second["text"])[4]["input"]["payload"]["value"] == {"capture": "nou"}
    assert canonical(first) == before


def test_capture_exact_unicode_byte_boundary_and_aggregate_frame_denial():
    stage = capture_fixture("é" * 2048)
    assert validate_stage(stage)
    stage["compositions"][0]["payload"]["text"] += " " * 32768
    with pytest.raises(ValueError):
        validate_stage(stage)


def test_legacy_no_slot_cannot_substitute_a_contract_case_input_ref():
    stage = fixture()
    assert validate_stage(stage)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    sections[3]["record"]["payload"]["resolved_procedure"]["probe"][0]["input_bindings"] = [
        {"name": "capture", "selector": "capture", "source_ref": reference("contract-case-input")}
    ]
    reseal_graph(stage, sections, payload["prompt_bundle"])
    with pytest.raises(ValueError):
        validate_stage(stage)
