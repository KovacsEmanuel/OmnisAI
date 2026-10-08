"""Real bounded compiler consumer tests, no database/model/target fixtures."""

import importlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_cli_compile_returns_strict_report() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            f"import sys,runpy;sys.path.insert(0,{str(ROOT / 'api/src')!r});runpy.run_module('omnis.modules.settings.skill_catalog',run_name='__main__')",
            "compile",
            "--package",
            str(ROOT / "skills/recon-mapping-contract"),
            "--profile",
            str(ROOT / "profiles/recon-mapping-contract.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip(), "CLI does not emit a report"
    report = json.loads(completed.stdout)
    assert report["status"] == "STATIC_PASS"
    assert report["resolution"] == "NO_MODEL"
    assert completed.stderr == ""


def consumer() -> ModuleType:
    try:
        return importlib.import_module("omnis.modules.settings.skill_catalog")
    except ModuleNotFoundError:
        pytest.fail("B06a compiler consumer is not implemented")


def test_seed_compiles_no_model() -> None:
    module = consumer()
    compile_catalog = module.compile_catalog
    result = compile_catalog(
        (ROOT / "skills/recon-mapping-contract",), ROOT / "profiles/recon-mapping-contract.yaml"
    )
    assert result.resolution == "NO_MODEL"
    assert len(result.material_digest) == 64
    assert len(result.resolved_index_digest) == 64
    assert len(result.steps) == 3


def test_declared_case_slot_cannot_evaluate_unbound(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    procedure = package / "templates/procedures/map-capture.yaml"
    procedure.write_text(
        procedure.read_text()
        .replace(
            "slots: []",
            "slots:\n- name: rule\n  expected_kind: business_rule\n  min_items: 1\n  max_items: 1",
        )
        .replace(
            "business_rule_refs: []", "business_rule_refs:\n- kind: CASE_SLOT_REF\n  name: rule"
        )
    )
    module = consumer()
    candidate = module.compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")
    assert candidate.slots[0].name == "rule"
    with pytest.raises(ValueError, match="UNBOUND_SLOT"):
        module.evaluate_pure(candidate, {"capture": "[]"})


def test_schema_output_field_type_mismatch_is_static_blocked(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    output = package / "templates/schemas/records.schema.json"
    raw = json.loads(output.read_text())
    raw["properties"]["records"]["type"] = "string"
    output.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="SCHEMA_TYPE"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_unknown_case_slot_is_static_blocked(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    procedure = package / "templates/procedures/map-capture.yaml"
    procedure.write_text(
        procedure.read_text().replace(
            "business_rule_refs: []", "business_rule_refs:\n- kind: CASE_SLOT_REF\n  name: missing"
        )
    )
    with pytest.raises(ValueError, match="SLOT_DECLARATION"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_unknown_schema_keyword_is_not_silently_accepted(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    output = package / "templates/schemas/records.schema.json"
    raw = json.loads(output.read_text())
    raw["trust-me"] = True
    output.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="SCHEMA_UNSUPPORTED"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_hardlinked_material_is_rejected(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    notice = package / "NOTICE.md"
    moved = tmp_path / "notice-copy"
    notice.rename(moved)
    os.link(moved, notice)
    with pytest.raises(ValueError, match="UNSAFE_FILE"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


@pytest.mark.parametrize(
    "capture",
    [
        '[{"method":"get","path":"/a","status":200}]',
        '[{"method":"GET","path":"https://example.invalid","status":200}]',
        '[{"method":"GET","path":"/a","status":true}]',
        '[{"method":"GET","path":"/a","status":99}]',
        '[{"method":"GET","path":"/a","status":600}]',
        '[{"method":"GET","path":"/a","status":200,"token":"private"}]',
        '[{"method":"GET","path":"/a","status":200.0}]',
        '[{"method":"GET","method":"POST","path":"/a","status":200}]',
        "{}",
        "null",
        "[null]",
    ],
)
def test_hostile_capture_is_blocked(capture: str) -> None:
    module = consumer()
    candidate = module.compile_catalog(
        (ROOT / "skills/recon-mapping-contract",), ROOT / "profiles/recon-mapping-contract.yaml"
    )
    with pytest.raises(ValueError):
        module.evaluate_pure(candidate, {"capture": capture})


@pytest.mark.parametrize(
    "before,after",
    [
        ("schema_version: 1", "schema_version: 1\nunknown_authority: true"),
        ("schema_version: 1", "schema_version: 1\nschema_version: 1"),
        ("package_key: recon-mapping-contract", "package_key: !!str recon-mapping-contract"),
        ("package_key: recon-mapping-contract", "package_key: &alias recon-mapping-contract"),
        ("skill_path: SKILL.md", "skill_path: ../SKILL.md"),
    ],
)
def test_hostile_manifest_is_blocked(tmp_path: Path, before: str, after: str) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    manifest = package / "omnis.yaml"
    manifest.write_text(manifest.read_text().replace(before, after))
    with pytest.raises(ValueError):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


@pytest.mark.parametrize(
    "before,after",
    [
        ("contract.parse-capture", "evil.import-script"),
        ("step_id: parse-capture", "step_id: build-map"),
        ("output_name: records", "output_name: nonexistent"),
        ("key: empty", "key: missing-schema"),
        ("key: capture-mapping", "key: missing-technique"),
        ("entity_kind: schema", "entity_kind: overlay"),
        ("parameters: {}", "parameters: {slot: {kind: CASE_SLOT_REF, name: illegal}}"),
        ("verification_kind: CONTRACT", "verification_kind: SECURITY"),
    ],
)
def test_hostile_procedure_is_blocked(tmp_path: Path, before: str, after: str) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    procedure = package / "templates/procedures/map-capture.yaml"
    procedure.write_text(procedure.read_text().replace(before, after))
    module = consumer()
    with pytest.raises(ValueError):
        candidate = module.compile_catalog(
            (package,), ROOT / "profiles/recon-mapping-contract.yaml"
        )
        module.evaluate_pure(candidate, {"capture": "[]"})


def test_undeclared_symlink_directory_is_rejected(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    outside = tmp_path / "outside"
    outside.mkdir()
    (package / "hidden-link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="UNSAFE_FILE"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_unselected_procedure_unknown_handler_is_static_blocked(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    manifest = package / "omnis.yaml"
    manifest.write_text(
        manifest.read_text().replace(
            "- templates/procedures/map-capture.yaml",
            "- templates/procedures/map-capture.yaml\n- templates/procedures/other.yaml",
        )
    )
    source = package / "templates/procedures/map-capture.yaml"
    (package / "templates/procedures/other.yaml").write_text(
        source.read_text()
        .replace("key: map-capture", "key: other")
        .replace("contract.parse-capture", "evil.uninstalled")
    )
    with pytest.raises(ValueError, match="UNKNOWN_HANDLER"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_native_skill_frontmatter_mismatch_is_blocked(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    skill = package / "SKILL.md"
    skill.write_text(
        skill.read_text().replace("name: recon-mapping-contract", "name: misleading-native")
    )
    with pytest.raises(ValueError, match="NATIVE_SKILL_MISMATCH"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


@pytest.mark.parametrize(
    "mutation",
    [
        "unqualified",
        "model",
        "release",
        "duplicate",
        "remote-schema",
        "undeclared",
        "too-many-inputs",
        "oversized-input",
    ],
)
def test_remaining_bounded_denials(tmp_path: Path, mutation: str) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    profile = tmp_path / "profile.yaml"
    profile.write_text((ROOT / "profiles/recon-mapping-contract.yaml").read_text())
    packages: tuple[Path, ...] = (package,)
    if mutation == "unqualified":
        profile.write_text(
            profile.read_text()
            .replace("kind: CANDIDATE", "kind: LOCAL")
            .replace("    package_key: recon-mapping-contract\n", "")
        )
    elif mutation == "model":
        profile.write_text(
            profile.read_text().replace(
                "execution_preference: null",
                "execution_preference: {model_key: forbidden, effort: null, requirement: REQUIRED, on_unavailable: BLOCK}",
            )
        )
    elif mutation == "release":
        profile.write_text(
            profile.read_text().replace(
                "kind: CANDIDATE\n    package_key: recon-mapping-contract\n    entity_kind: procedure\n    key: map-capture",
                "kind: RELEASE\n    ref: {kind: procedure, id: 00000000-0000-0000-0000-000000000001, revision: 1, digest: '"
                + "a" * 64
                + "'}",
            )
        )
    elif mutation == "duplicate":
        packages = (package, package)
    elif mutation == "remote-schema":
        output = package / "templates/schemas/records.schema.json"
        raw = json.loads(output.read_text())
        raw["$ref"] = "file:///private/secret"
        output.write_text(json.dumps(raw))
    elif mutation == "undeclared":
        (package / "undeclared.txt").write_text("not declared")
    module = consumer()
    if mutation not in ("too-many-inputs", "oversized-input"):
        with pytest.raises(ValueError):
            module.compile_catalog(packages, profile)
        return
    candidate = module.compile_catalog(packages, profile)
    with pytest.raises(ValueError):
        capture = (
            "[" + ",".join('{"method":"GET","path":"/a","status":200}' for _ in range(129)) + "]"
            if mutation == "too-many-inputs"
            else " " * 65537
        )
        module.evaluate_pure(candidate, {"capture": capture})


def test_boolean_schema_version_is_not_integer_one(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    manifest = package / "omnis.yaml"
    manifest.write_text(manifest.read_text().replace("schema_version: 1", "schema_version: true"))
    with pytest.raises(ValueError):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_executable_seed_has_typed_method_requirement() -> None:
    from omnis.modules.settings.catalog_models import Procedure
    from omnis.modules.settings.catalog_schema import dto

    source = ROOT / "skills/recon-mapping-contract/templates/procedures/map-capture.yaml"
    procedure = dto(source.read_bytes(), Procedure)
    assert len(procedure.method_requirements) >= 1, "Executable seed lacks a method requirement"
    candidate = consumer().compile_catalog(
        (ROOT / "skills/recon-mapping-contract",), ROOT / "profiles/recon-mapping-contract.yaml"
    )
    assert len(candidate.steps) == 3


def test_two_packages_same_procedure_key_remain_qualified(tmp_path: Path) -> None:
    beta = tmp_path / "beta"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", beta)
    for relative in ("omnis.yaml", "SKILL.md"):
        source = beta / relative
        source.write_text(source.read_text().replace("recon-mapping-contract", "beta-contract"))
    candidate = consumer().compile_catalog(
        (ROOT / "skills/recon-mapping-contract", beta),
        ROOT / "profiles/recon-mapping-contract.yaml",
    )
    references = [
        reference
        for reference in candidate.refs
        if reference.entity_kind == "procedure" and reference.key == "map-capture"
    ]
    assert {reference.package_key for reference in references} == {
        "recon-mapping-contract",
        "beta-contract",
    }
    assert len({reference.digest for reference in references}) == 2


def test_nested_output_schema_type_mismatch_is_static_blocked(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    output = package / "templates/schemas/records.schema.json"
    raw = json.loads(output.read_text())
    raw["properties"]["records"]["items"]["properties"]["status"]["type"] = "string"
    output.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="SCHEMA_TYPE"):
        consumer().compile_catalog((package,), ROOT / "profiles/recon-mapping-contract.yaml")


def test_security_never_pure_pass() -> None:
    module = consumer()
    candidate = module.compile_catalog(
        (ROOT / "skills/recon-mapping-contract",), ROOT / "profiles/recon-mapping-contract.yaml"
    )
    with pytest.raises(ValueError, match="SECURITY_REQUIRES_FIXTURE"):
        module.evaluate_pure(replace(candidate, verification_kind="SECURITY"), {"capture": "[]"})


def test_three_pure_transform_outputs() -> None:
    module = consumer()
    evaluate_pure = getattr(module, "evaluate_pure", None)
    assert evaluate_pure is not None, "PURE evaluator missing"
    candidate = module.compile_catalog(
        (ROOT / "skills/recon-mapping-contract",), ROOT / "profiles/recon-mapping-contract.yaml"
    )
    capture = '[{"method":"GET","path":"/b","status":404},{"method":"POST","path":"/a","status":201},{"method":"GET","path":"/b","status":200}]'
    result = evaluate_pure(candidate, {"capture": capture})
    assert result.outputs == (
        {
            "records": [
                {"method": "GET", "path": "/b", "status": 404},
                {"method": "POST", "path": "/a", "status": 201},
                {"method": "GET", "path": "/b", "status": 200},
            ]
        },
        {
            "operations": [
                {"method": "POST", "path": "/a", "statuses": [201]},
                {"method": "GET", "path": "/b", "statuses": [200, 404]},
            ]
        },
        {
            "surface_map": [
                {"path": "/a", "methods": ["POST"], "operation_count": 1},
                {"path": "/b", "methods": ["GET"], "operation_count": 1},
            ]
        },
    )
