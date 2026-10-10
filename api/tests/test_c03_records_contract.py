"""Records tracer: existing compiler/handlers, not a DTO-only acceptance."""

from pathlib import Path

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
