"""Black-box STATIC contract and hostile controls on the same CLI channel."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from fixtures.b06a.consumer import (
    MARKER,
    CatalogSeed,
    declared_paths,
    invoke,
    mapping,
    procedure,
    release_digest,
    schema_path,
    sequence,
    source_bytes,
    stable_block,
    write_yaml,
    yaml_object,
)
from fixtures.b06a.consumer import (
    seed as seed,
)


def test_cli_consumer_exists_before_seed_integration() -> None:
    """The initial RED must reach the absent real module, not fabricated receipts."""
    with tempfile.TemporaryDirectory(prefix="b06a-cli-red-", dir=os.environ["TMPDIR"]) as name:
        result = invoke(Path(name), "--help")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "compile" in result.stdout and "evaluate" in result.stdout


def test_compile_is_deterministic_read_only_and_no_model(seed: CatalogSeed) -> None:
    before = source_bytes(seed)
    actual_files = sorted(
        path.relative_to(seed.package).as_posix()
        for path in seed.package.rglob("*")
        if path.is_file()
    )
    assert actual_files == sorted(declared_paths(seed))
    first = seed.compile()
    second = seed.compile()
    assert first == second
    assert source_bytes(seed) == before
    assert all(not path.is_symlink() for path in seed.package.rglob("*"))


def test_complete_original_file_bytes_bind_both_digests(seed: CatalogSeed) -> None:
    first = seed.compile()
    independent_before = release_digest(seed)
    package_refs = sequence(first["resolved_refs"])
    assert package_refs
    assert all(mapping(ref)["digest"] == independent_before for ref in package_refs)
    with (seed.package / "SKILL.md").open("ab") as stream:
        stream.write(b"\nB06a evaluator-only benign material edit.\n")
    independent_after = release_digest(seed)
    assert independent_after != independent_before
    second = seed.compile()
    assert second["material_digest"] != first["material_digest"]
    assert second["resolved_index_digest"] != first["resolved_index_digest"]
    assert seed.compile() == second


def test_two_candidate_roots_with_the_same_package_key_are_refused(seed: CatalogSeed) -> None:
    seed.compile()
    duplicate = seed.directory / "duplicate-package"
    shutil.copytree(seed.package, duplicate)
    stable_block(seed, packages=(seed.package, duplicate))


def test_distinct_package_keys_cannot_shadow_a_native_name(seed: CatalogSeed) -> None:
    seed.compile()
    duplicate = seed.directory / "shadow-package"
    shutil.copytree(seed.package, duplicate)
    manifest_path = duplicate / "omnis.yaml"
    manifest = yaml_object(manifest_path)
    manifest["package_key"] = "b06a-native-shadow"
    write_yaml(manifest_path, manifest)
    stable_block(seed, packages=(seed.package, duplicate))


def test_an_undeclared_regular_file_is_refused(seed: CatalogSeed) -> None:
    seed.compile()
    (seed.package / "undeclared.txt").write_text(MARKER, encoding="utf-8")
    stable_block(seed)


@pytest.mark.parametrize("path", ["../outside.txt", "/outside.txt", "references\\outside.txt"])
def test_hostile_declared_paths_are_not_normalized(seed: CatalogSeed, path: str) -> None:
    seed.compile()
    manifest = yaml_object(seed.manifest)
    manifest["support_files"] = [*sequence(manifest["support_files"]), path]
    write_yaml(seed.manifest, manifest)
    stable_block(seed)


def test_a_declared_file_symlink_cannot_escape_the_package(seed: CatalogSeed) -> None:
    seed.compile()
    outside = seed.directory / "private-outside.txt"
    outside.write_text(MARKER, encoding="utf-8")
    original = seed.package / "SKILL.md"
    original.unlink()
    original.symlink_to(outside)
    stable_block(seed)
    assert outside.read_text(encoding="utf-8") == MARKER


@pytest.mark.parametrize("attack", ["duplicate", "tag", "alias"])
def test_safe_yaml_requires_no_duplicates_tags_or_aliases(seed: CatalogSeed, attack: str) -> None:
    seed.compile()
    original = seed.manifest.read_text(encoding="utf-8")
    if attack == "duplicate":
        seed.manifest.write_text(original + "\nschema_version: 1\n", encoding="utf-8")
    elif attack == "tag":
        assert "schema_version: 1" in original
        seed.manifest.write_text(
            original.replace("schema_version: 1", "schema_version: !!int 1", 1),
            encoding="utf-8",
        )
    else:
        manifest = yaml_object(seed.manifest)
        compatibility = mapping(manifest["compatibility"])
        assert compatibility["adapter_refs"] == compatibility["tool_refs"] == []
        compatibility["tool_refs"] = compatibility["adapter_refs"]
        manifest["compatibility"] = compatibility
        write_yaml(seed.manifest, manifest)
        assert "&id" in seed.manifest.read_text(encoding="utf-8")
        assert "*id" in seed.manifest.read_text(encoding="utf-8")
    stable_block(seed)


def test_manifest_above_256_kib_is_refused(seed: CatalogSeed) -> None:
    seed.compile()
    with seed.manifest.open("ab") as stream:
        stream.write(b"\n#" + b"x" * (256 * 1024))
    stable_block(seed)


@pytest.mark.parametrize(
    "reference",
    [
        "https://invalid.example/" + MARKER,
        "file:///" + MARKER,
    ],
)
def test_json_schema_never_resolves_remote_or_file_refs(seed: CatalogSeed, reference: str) -> None:
    seed.compile()
    path = schema_path(seed)
    value: object = json.loads(path.read_text(encoding="utf-8"))
    schema = mapping(value)
    schema["$ref"] = reference
    path.write_text(json.dumps(schema), encoding="utf-8")
    stable_block(seed)


def test_author_supplied_backend_authority_is_refused(seed: CatalogSeed) -> None:
    seed.compile()
    manifest = yaml_object(seed.manifest)
    manifest["publication"] = "PUBLISHED"
    manifest["validated"] = True
    write_yaml(seed.manifest, manifest)
    stable_block(seed)


def test_unknown_action_handler_is_not_a_dynamic_import(seed: CatalogSeed) -> None:
    seed.compile()
    path, value = procedure(seed)
    steps = sequence(value["probe"])
    assert len(steps) == 3
    step = mapping(steps[0])
    reference = mapping(step["action_definition_ref"])
    reference["key"] = "unknown-b06a-handler"
    step["action_definition_ref"] = reference
    steps[0] = step
    value["probe"] = steps
    write_yaml(path, value)
    stable_block(seed)


def test_step_output_forward_reference_is_refused(seed: CatalogSeed) -> None:
    seed.compile()
    path, value = procedure(seed)
    steps = sequence(value["probe"])
    assert len(steps) == 3
    consumer = mapping(steps[1])
    future = mapping(steps[2])
    bindings = sequence(consumer["input_bindings"])
    assert bindings
    binding = mapping(bindings[0])
    source = mapping(binding["source_ref"])
    assert source["kind"] == "STEP_OUTPUT"
    source["step_id"] = future["id"]
    binding["source_ref"] = source
    bindings[0] = binding
    consumer["input_bindings"] = bindings
    steps[1] = consumer
    value["probe"] = steps
    write_yaml(path, value)
    stable_block(seed)


def test_profile_local_ref_has_no_implicit_package(seed: CatalogSeed) -> None:
    seed.compile()
    profile = yaml_object(seed.profile)
    # This increment exposes a source Profile, not a durable WorkflowProfileRevision.config.
    recipes = sequence(profile["agent_recipes"])
    assert recipes
    recipe = mapping(recipes[0])
    references = sequence(recipe["package_refs"])
    assert references
    original = mapping(references[0])
    references[0] = {"kind": "LOCAL", "entity_kind": "package", "key": original["key"]}
    recipe["package_refs"] = references
    recipes[0] = recipe
    profile["agent_recipes"] = recipes
    write_yaml(seed.profile, profile)
    stable_block(seed)


def test_seed_compatibility_names_the_native_hermes_pin(seed: CatalogSeed) -> None:
    from fixtures.b06a.consumer import ROOT

    native_pin = mapping(json.loads((ROOT / "integrations/hermes/pin.json").read_text()))
    manifest = yaml_object(seed.manifest)
    assert mapping(manifest["compatibility"])["hermes_revision"] == native_pin["commit"]
    seed.compile()


def test_wrong_native_hermes_revision_is_static_blocked(seed: CatalogSeed) -> None:
    seed.compile()
    manifest = yaml_object(seed.manifest)
    compatibility = mapping(manifest["compatibility"])
    compatibility["hermes_revision"] = "0" * 40
    manifest["compatibility"] = compatibility
    write_yaml(seed.manifest, manifest)
    stable_block(seed)
