"""CONTRACT/PURE tracer: real deterministic transforms, no API imports."""

import importlib.util
import json
from datetime import datetime, timedelta, timezone

import pytest
from composition_fixture import ref, seal
from omnis_hermes.managed_admission_contract import canonical, validate_stage
from test_c03_case_input import capture_fixture
from test_c03_records import records_fixture
from test_prompt_bundle import reseal_graph

BASE = "CONTRACT_PROBE. Deterministic PURE method only; no provider, model, target or stock tools. Read only the bound assignment inputs."
ROLE = "SUPPORT-only native CONTRACT/PURE method; not an assessment."
PROTOCOL = "omnis-managed-admission-v4"


def method_fixture(records=False, value=None):
    stage = (
        records_fixture(value)
        if records
        else capture_fixture()
        if value is None
        else capture_fixture(value)
    )
    stage["protocol"] = PROTOCOL
    stage["manifest"]["payload"]["composition_version"] = 4
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    bundle = payload["prompt_bundle"]
    if records:
        from omnis_hermes.prompt_bundle import CRITERIA_COMPOSER_REVISION

        bundle["payload"]["composer_revision"] = CRITERIA_COMPOSER_REVISION
    for index, text in ((0, BASE), (1, ROLE)):
        sections[index]["record"]["payload"]["text"] = text
        seal(sections[index]["record"])
    bundle["payload"]["base_ref"] = ref(sections[0]["record"])
    bundle["payload"]["role_refs"][0]["content_ref"] = ref(sections[1]["record"])
    brief = sections[2]["record"]["payload"]
    brief["deadline"] = (
        (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    )
    brief["limits"]["max_output_bytes"] = 32768
    procedure = sections[3]["record"]["payload"]["resolved_procedure"]
    procedure["limits"]["max_output_bytes"] = 32768
    procedure["outcomes"] = ["SUCCEEDED", "BLOCKED"]
    # Fixtures originally share a synthetic output ref; assign distinct schemas.
    from composition_fixture import reference

    for step in procedure["probe"]:
        step["output_schema_ref"] = reference("schema")
    procedure["output_schema_ref"] = procedure["handoff_schema_ref"] = procedure["probe"][-1][
        "output_schema_ref"
    ]
    procedure["method_requirements"][0]["artifact_schema_refs"] = [procedure["output_schema_ref"]]
    reseal_graph(stage, sections, bundle)
    return stage


def test_contract_method_seam_exists_and_accepts_v4_assignment():
    assert importlib.util.find_spec("omnis_hermes.contract_method"), (
        "native CONTRACT/PURE method seam missing"
    )
    stage = method_fixture()
    assert validate_stage(stage) == stage["manifest"]


def test_native_artifact_schema_rejects_duplicate_statuses():
    from omnis_hermes.contract_method import OUTPUT_SCHEMAS, validate_value

    with pytest.raises(ValueError):
        validate_value(
            OUTPUT_SCHEMAS["normalize-operations"],
            {"operations": [{"method": "GET", "path": "/", "statuses": [200, 200]}]},
        )


def test_three_native_handlers_transform_actual_prior_output():
    from omnis_hermes import contract_method as method

    assert callable(getattr(method, "run_handler", None)), "deterministic handlers missing"
    rows = [
        {"method": "POST", "path": "/b", "status": 404},
        {"method": "GET", "path": "/a", "status": 200},
        {"method": "POST", "path": "/b", "status": 201},
        {"method": "POST", "path": "/b", "status": 404},
    ]
    parsed = method.run_handler("contract.parse-capture", {"capture": json.dumps(rows)})
    assert parsed == {"records": rows}
    normalized = method.run_handler("contract.normalize-operations", parsed)
    assert normalized == {
        "operations": [
            {"method": "GET", "path": "/a", "statuses": [200]},
            {"method": "POST", "path": "/b", "statuses": [201, 404]},
        ]
    }
    assert method.run_handler("contract.build-map", normalized) == {
        "surface_map": [
            {"path": "/a", "methods": ["GET"], "operation_count": 1},
            {"path": "/b", "methods": ["POST"], "operation_count": 1},
        ]
    }
    for bad in (
        {"records": [{"method": "GET", "path": "/", "status": True}]},
        {"records": [{"method": "GET", "path": "/bad path", "status": 200}]},
        {"records": [], "extra": 1},
    ):
        with pytest.raises(ValueError):
            method.run_handler("contract.normalize-operations", bad)
    with pytest.raises(ValueError):
        method.run_handler(
            "contract.parse-capture",
            {"capture": '[{"method":"GET","method":"POST","path":"/","status":200}]'},
        )
    with pytest.raises(ValueError):
        method.run_handler("from.goal.text", {})


def test_real_constructor_has_separate_contract_admission_before_client_seam():
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "upstream/managed-source/run_agent.py"
    cls = next(
        n
        for n in ast.parse(source.read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "AIAgent"
    )
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    assert "contract_admission" in [n.arg for n in init.args.args], (
        "native CONTRACT admission missing"
    )
    code = ast.unparse(init)
    assert code.index("initialize_contract") < code.index("from agent.agent_init import init_agent")


def test_v4_release_rejects_duplicate_brief_before_registry_lookup():
    from uuid import uuid4

    from composition_fixture import record
    from omnis_hermes.managed_admission_contract import validate_release

    stage = method_fixture()
    ticket = str(uuid4())
    entry = {k: v for k, v in stage["manifest"]["payload"]["entries"][0].items() if k != "goal"}
    entry.update(native_child_id=str(uuid4()), native_session_id=str(uuid4()))
    second = {
        **entry,
        "batch_index": 1,
        "task_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "native_child_id": str(uuid4()),
        "native_session_id": str(uuid4()),
    }
    binding = record(
        "runtime-binding",
        {
            "runtime_boot": str(uuid4()),
            "run_id": stage["manifest"]["payload"]["run_id"],
            "ticket": ticket,
            "native_root_id": str(uuid4()),
            "entries": [entry, second],
            "authority": {
                "instance_id": str(uuid4()),
                "owner": str(uuid4()),
                "epoch": 1,
                "generation": 0,
            },
        },
    )
    with pytest.raises(ValueError):
        validate_release(
            {
                "protocol": PROTOCOL,
                "ticket": ticket,
                "manifest_ref": ref(stage["manifest"]),
                "binding": binding,
            }
        )


@pytest.mark.parametrize("records", [False, True])
def test_v4_material_cannot_be_reinterpreted_as_cold_or_inverse(records):
    stage = method_fixture(records=records)
    assert validate_stage(stage)
    stage["protocol"] = "omnis-managed-admission-v3" if records else "omnis-managed-admission-v2"
    stage["manifest"]["payload"]["composition_version"] = 3 if records else 2
    seal(stage["manifest"])
    with pytest.raises(ValueError):
        validate_stage(stage)
    cold = records_fixture() if records else capture_fixture()
    cold["protocol"] = PROTOCOL
    cold["manifest"]["payload"]["composition_version"] = 4
    seal(cold["manifest"])
    with pytest.raises(ValueError):
        validate_stage(cold)


@pytest.mark.parametrize("records", [False, True])
def test_historical_records_composer_explicitly_remains_accepted_for_cold(records):
    stage = records_fixture() if records else capture_fixture()
    payload = stage["compositions"][0]["payload"]
    payload["prompt_bundle"]["payload"]["composer_revision"] = (
        "55963352e1b855f51f379bdfb0cf0ff49b0004dacb40aad32ef85ea9f3b5828c"
    )
    reseal_graph(stage, json.loads(payload["text"]), payload["prompt_bundle"])
    assert validate_stage(stage)


@pytest.mark.parametrize("records", [False, True])
@pytest.mark.parametrize(
    "field,value",
    [("id", "from-goal-text"), ("parameters", {"override": 1}), ("tool_ref", {"kind": "tool"})],
)
def test_contract_assignment_rejects_unknown_step_or_parameters(records, field, value):
    from omnis_hermes.contract_method import assignment

    stage = method_fixture(records=records)
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    sections[3]["record"]["payload"]["resolved_procedure"]["probe"][0][field] = value
    reseal_graph(stage, sections, payload["prompt_bundle"])
    with pytest.raises(ValueError):
        assignment(canonical(stage))


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"method": "GET", "path": "/", "status": 200}],
        [
            {"method": "POST", "path": "/é🦊", "status": 599},
            {"method": "GET", "path": "/é🦊", "status": 100},
        ],
        [{"method": "PUT", "path": "/sorted", "status": 300}] * 128,
    ],
)
def test_native_algorithms_equal_the_actual_api_handlers(rows):
    from omnis_hermes.contract_method import run_handler as native_handler

    from omnis.modules.tasks.module_registry import run_handler as api_handler

    actual, expected = {"capture": json.dumps(rows)}, {"capture": json.dumps(rows)}
    for name in ("contract.parse-capture", "contract.normalize-operations", "contract.build-map"):
        actual = native_handler(name, actual)
        expected = api_handler(name, expected)
        assert actual == expected
