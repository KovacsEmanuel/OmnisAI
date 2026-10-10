"""New C03 synthetic source; historical seed bytes stay unchanged."""

from copy import deepcopy
from pathlib import Path

from fixtures.b06a.consumer import mapping, sequence, write_yaml, yaml_object
from fixtures.b06a_durable.consumer import DurableSeed, copy_seed

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


def capture_seed(directory: Path, *, extra_requirement: bool = False) -> DurableSeed:
    seed = copy_seed(directory)
    path = seed.package / "templates/procedures/map-capture.yaml"
    procedure = yaml_object(path)
    procedure["slots"] = [CAPTURE_SLOT.copy()]
    mapping(sequence(procedure["probe"])[0])  # check fixture shape before mutating
    steps = sequence(procedure["probe"])
    first = mapping(steps[0])
    first["input_bindings"] = [CAPTURE_BINDING.copy()]
    procedure["probe"] = [first, *steps[1:]]
    if extra_requirement:
        requirements = sequence(procedure["method_requirements"])
        additional = deepcopy(mapping(requirements[0]))
        additional.update(
            key="capture-context-retained",
            description="Retain the supplied capture context independently of the steps.",
            step_ids=["parse-capture"],
        )
        procedure["method_requirements"] = [*requirements, additional]
    write_yaml(path, procedure)
    return seed
