"""Records tracer: existing compiler/handlers, not a DTO-only acceptance."""

from pathlib import Path

import pytest

from fixtures.b06a.consumer import mapping, sequence, write_yaml, yaml_object
from fixtures.b06a_durable.consumer import copy_seed
from omnis.modules.settings.skill_catalog import compile_catalog


def test_records_two_step_compiler_tracer(tmp_path: Path) -> None:
    seed = copy_seed(tmp_path / "records-red")
    path = seed.package / "templates/procedures/map-capture.yaml"
    procedure = yaml_object(path)
    procedure["key"] = "map-records"
    procedure["input_schema_ref"] = {"kind": "LOCAL", "entity_kind": "schema", "key": "records"}
    procedure["slots"] = [
        {
            "name": "records",
            "expected_kind": "contract-case-records",
            "min_items": 1,
            "max_items": 1,
        }
    ]
    steps = sequence(procedure["probe"])[1:]
    first = mapping(steps[0])
    first["input_bindings"] = [
        {
            "name": "records",
            "source_ref": {"kind": "CASE_SLOT_REF", "name": "records"},
            "selector": "records",
        }
    ]
    procedure["probe"] = [first, steps[1]]
    requirement = mapping(sequence(procedure["method_requirements"])[0])
    requirement["step_ids"] = ["normalize-operations", "build-map"]
    procedure["method_requirements"] = [requirement]
    write_yaml(path, procedure)
    manifest_path = seed.package / "omnis.yaml"
    manifest = yaml_object(manifest_path)
    technique = mapping(sequence(manifest["techniques"])[0])
    technique["procedure_refs"] = [
        {"kind": "LOCAL", "entity_kind": "procedure", "key": "map-records"}
    ]
    manifest["techniques"] = [technique]
    manifest["input_schema_ref"] = procedure["input_schema_ref"]
    write_yaml(manifest_path, manifest)
    profile = yaml_object(seed.profile)
    recipe = mapping(sequence(profile["agent_recipes"])[0])
    selected = mapping(sequence(recipe["procedure_refs"])[0])
    selected["key"] = "map-records"
    recipe["procedure_refs"] = [selected]
    profile["agent_recipes"] = [recipe]
    write_yaml(seed.profile, profile)
    compiled = compile_catalog((seed.package,), seed.profile)
    assert [step.handler for step in compiled.steps] == [
        "contract.normalize-operations",
        "contract.build-map",
    ]
    assert [slot.model_dump(mode="json") for slot in compiled.slots] == procedure["slots"]


def test_first_party_records_package_and_strict_value_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fixtures.c03_records import EVALUATION_VALUE, records_seed
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.modules.tasks.contract_case_input import validate_value

    seed = records_seed(tmp_path / "first-party")
    compiled = compile_catalog((seed.package,), seed.profile)
    assert [s.handler for s in compiled.steps] == [
        "contract.normalize-operations",
        "contract.build-map",
    ]
    raw = (seed.package / "templates/schemas/records.schema.json").read_bytes()

    def no_execution(*args: object, **kwargs: object) -> object:
        raise AssertionError("Input producer executed a method")

    monkeypatch.setattr("omnis.modules.tasks.module_registry.run_handler", no_execution)
    assert validate_value(EVALUATION_VALUE, raw, version=2) == EVALUATION_VALUE
    assert validate_value({"records": []}, raw, version=2) == {"records": []}
    maximum = {"records": [{"method": "GET", "path": "/", "status": 200}] * 128}
    assert validate_value(maximum, raw, version=2) == maximum
    with pytest.raises(CatalogError):
        validate_value({"records": []}, raw)


@pytest.mark.parametrize(
    "attack",
    [
        "forward",
        "global",
        "cross-attempt",
        "undeclared",
        "selector",
        "wrong-first",
        "missing-slot",
        "two-refs",
        "optional-slot",
        "kind",
        "duplicate-slot",
        "parse-step",
    ],
)
def test_records_compiler_rejects_unsupported_templates(tmp_path: Path, attack: str) -> None:
    from fixtures.c03_records import records_seed
    from omnis.modules.settings.catalog_models import CatalogError

    seed = records_seed(tmp_path / attack)
    assert len(compile_catalog((seed.package,), seed.profile).steps) == 2
    path = seed.package / "templates/procedures/map-records.yaml"
    procedure = yaml_object(path)
    steps = [mapping(s) for s in sequence(procedure["probe"])]
    bindings = [mapping(b) for b in sequence(steps[1]["input_bindings"])]
    output = mapping(bindings[0]["source_ref"])
    slots = [mapping(s) for s in sequence(procedure["slots"])]
    if attack == "forward":
        output["step_id"] = "build-map"
    elif attack == "global":
        output["step_id"] = "another-procedure.normalize"
    elif attack == "cross-attempt":
        output["attempt_id"] = "00000000-0000-4000-8000-000000000001"
    elif attack == "undeclared":
        output["output_name"] = "absent"
    elif attack == "selector":
        bindings[0]["selector"] = "operations"
    elif attack == "wrong-first":
        steps[0]["input_bindings"] = [
            {
                "name": "records",
                "source_ref": {
                    "kind": "STEP_OUTPUT",
                    "step_id": "build-map",
                    "output_name": "surface_map",
                },
                "selector": None,
            }
        ]
    elif attack == "missing-slot":
        slots.clear()
    elif attack == "two-refs":
        slots[0]["max_items"] = 2
    elif attack == "optional-slot":
        slots[0]["min_items"] = 0
    elif attack == "kind":
        slots[0]["expected_kind"] = "contract-case-input"
    elif attack == "duplicate-slot":
        slots.append(slots[0].copy())
    elif attack == "parse-step":
        steps[0]["action_definition_ref"] = {
            "kind": "LOCAL",
            "entity_kind": "action_definition",
            "key": "contract.parse-capture",
        }
    else:
        raise AssertionError(attack)
    bindings[0]["source_ref"] = output
    steps[1]["input_bindings"] = bindings
    procedure["probe"], procedure["slots"] = steps, slots
    write_yaml(path, procedure)
    with pytest.raises(CatalogError):
        compile_catalog((seed.package,), seed.profile)
