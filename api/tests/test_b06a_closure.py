"""Concrete existing-compiler closure controls; no mock resolver/repository.

These source controls do not certify the new durable consumer. Every negative
first compiles valid material on the same CLI and requires an exact reason.
"""

import json
from pathlib import Path

import pytest

from fixtures.b06a.consumer import (
    CatalogSeed,
    blocked,
    mapping,
    procedure,
    sequence,
    write_yaml,
    yaml_object,
)
from fixtures.b06a_durable.consumer import copy_seed, package_digest


@pytest.fixture
def closure_seed(ipc_directory: Path) -> CatalogSeed:
    copied = copy_seed(ipc_directory / "closure")
    return CatalogSeed(copied.directory, copied.package, copied.profile)


def rename_refs(value: object, package: str) -> object:
    if isinstance(value, list):
        return [rename_refs(item, package) for item in value]
    if isinstance(value, dict):
        result = {key: rename_refs(item, package) for key, item in mapping(value).items()}
        if result.get("package_key") == "recon-mapping-contract":
            result["package_key"] = package
        if result.get("key") == "recon-mapping-contract":
            result["key"] = package
        if result.get("entity_kind") == "schema" and result.get("key") == "empty":
            result["key"] = "inspect"
        return result
    return value


def qualify_package(seed: CatalogSeed, key: str) -> None:
    manifest = mapping(rename_refs(yaml_object(seed.manifest), key))
    manifest["native_name"] = key
    write_yaml(seed.manifest, manifest)
    path, document = procedure(seed)
    write_yaml(path, mapping(rename_refs(document, key)))
    skill = seed.package / "SKILL.md"
    text = skill.read_text()
    assert "name: recon-mapping-contract" in text
    skill.write_text(text.replace("name: recon-mapping-contract", f"name: {key}", 1))
    write_yaml(seed.profile, mapping(rename_refs(yaml_object(seed.profile), key)))


def test_alpha_beta_local_inspect_are_distinct_qualified_refs(closure_seed: CatalogSeed) -> None:
    seed = closure_seed
    seed.compile()  # Same-channel positive before the two-package control.
    second = copy_seed(seed.directory / "beta-source")
    beta = CatalogSeed(second.directory, second.package, second.profile)
    qualify_package(seed, "alpha")
    qualify_package(beta, "beta")
    profile = yaml_object(seed.profile)
    recipe = mapping(sequence(profile["agent_recipes"])[0])
    recipe["package_refs"] = [
        *sequence(recipe["package_refs"]),
        {"kind": "CANDIDATE", "package_key": "beta", "entity_kind": "package", "key": "beta"},
    ]
    profile["agent_recipes"] = [recipe]
    write_yaml(seed.profile, profile)
    from fixtures.b06a.consumer import success

    result = success(seed.cli("compile", packages=(seed.package, beta.package)), "STATIC_PASS")
    refs = [mapping(item) for item in sequence(result["resolved_refs"])]
    inspect = [ref for ref in refs if ref["entity_kind"] == "schema" and ref["key"] == "inspect"]
    assert len(inspect) == 2
    assert {ref["package_key"]: ref["digest"] for ref in inspect} == {
        "alpha": package_digest(seed.package),
        "beta": package_digest(beta.package),
    }


def test_static_slot_is_preserved_and_pure_is_exactly_unbound(closure_seed: CatalogSeed) -> None:
    seed = closure_seed
    seed.compile()
    path, value = procedure(seed)
    value["slots"] = [
        {"name": "rules", "expected_kind": "business_rule", "min_items": 1, "max_items": 1}
    ]
    value["business_rule_refs"] = [{"kind": "CASE_SLOT_REF", "name": "rules"}]
    write_yaml(path, value)
    seed.compile()
    golden = mapping(json.loads((seed.directory / "golden.json").read_bytes()))
    input_path = seed.input(golden["input"])
    assert blocked(seed.cli("evaluate", "--input", str(input_path))) == "UNBOUND_SLOT"


@pytest.mark.parametrize(
    ("attack", "reason"),
    [
        ("forward", "FORWARD_OUTPUT_REF"),
        ("cycle", "FORWARD_OUTPUT_REF"),
        ("wrong_output", "OUTPUT_REF"),
        ("selector", "BINDING_TYPE"),
        ("duplicate_step", "DUPLICATE_STEP"),
        ("missing_schema", "MISSING_REF"),
        ("wrong_kind", "REF_TYPE"),
        ("unknown_handler", "UNKNOWN_HANDLER"),
        ("slot_cardinality", "SLOT_DECLARATION"),
    ],
)
def test_exact_step_and_ref_denials(closure_seed: CatalogSeed, attack: str, reason: str) -> None:
    seed = closure_seed
    seed.compile()
    path, value = procedure(seed)
    steps = [mapping(item) for item in sequence(value["probe"])]
    bindings = [mapping(item) for item in sequence(steps[1]["input_bindings"])]
    source = mapping(bindings[0]["source_ref"])
    if attack == "forward":
        source["step_id"] = steps[2]["id"]
    elif attack == "cycle":
        source["step_id"] = steps[1]["id"]
    elif attack == "wrong_output":
        source["output_name"] = "not_published"
    elif attack == "selector":
        bindings[0]["selector"] = "records"
    elif attack == "duplicate_step":
        removed = steps[1]["id"]
        steps[1]["id"] = steps[0]["id"]
        # Keep method requirements valid so this reaches the duplicate-step guard.
        requirements = [mapping(item) for item in sequence(value["method_requirements"])]
        for requirement in requirements:
            requirement["step_ids"] = [
                steps[0]["id"] if identifier == removed else identifier
                for identifier in sequence(requirement["step_ids"])
            ]
        value["method_requirements"] = requirements
    elif attack in {"missing_schema", "wrong_kind"}:
        reference = mapping(value["input_schema_ref"])
        reference["key" if attack == "missing_schema" else "entity_kind"] = (
            "missing" if attack == "missing_schema" else "procedure"
        )
        value["input_schema_ref"] = reference
    elif attack == "unknown_handler":
        reference = mapping(steps[0]["action_definition_ref"])
        reference["key"] = "not_registered"
        steps[0]["action_definition_ref"] = reference
    else:
        value["slots"] = [
            {"name": "rules", "expected_kind": "business_rule", "min_items": 2, "max_items": 1}
        ]
        value["business_rule_refs"] = [{"kind": "CASE_SLOT_REF", "name": "rules"}]
    bindings[0]["source_ref"] = source
    steps[1]["input_bindings"] = bindings
    value["probe"] = steps
    write_yaml(path, value)
    assert blocked(seed.cli("compile")) == reason
    assert blocked(seed.cli("compile")) == reason


def test_literal_numeric_pin_reaches_compatibility_guard(closure_seed: CatalogSeed) -> None:
    seed = closure_seed
    seed.compile()
    manifest = yaml_object(seed.manifest)
    compatibility = mapping(manifest["compatibility"])
    compatibility["hermes_revision"] = "0" * 40
    manifest["compatibility"] = compatibility
    write_yaml(seed.manifest, manifest)
    assert mapping(yaml_object(seed.manifest)["compatibility"])["hermes_revision"] == "0" * 40
    assert blocked(seed.cli("compile")) == "INCOMPATIBLE_HERMES"
