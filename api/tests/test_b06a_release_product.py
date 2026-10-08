"""Source-only pure tests; private synthetic external artifacts, never Publish."""

import inspect
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
import yaml

from omnis.modules.settings import skill_catalog
from omnis.modules.settings.candidate_index import index_source, resolved_index
from omnis.modules.settings.candidate_material import capture, digest, finalize, private_root
from omnis.modules.settings.candidate_resolution import ReleasePackage
from omnis.modules.settings.candidate_store import envelope, reference
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical

ROOT = Path(__file__).resolve().parents[2]


def seed(directory: Path, key: str) -> tuple[Path, Path]:
    package = directory / key
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    profile = directory / f"{key}.yaml"
    raw = (ROOT / "profiles/recon-mapping-contract.yaml").read_text()
    profile.write_text(raw.replace("recon-mapping-contract", key))
    manifest = package / "omnis.yaml"
    manifest.write_text(manifest.read_text().replace("recon-mapping-contract", key))
    skill = package / "SKILL.md"
    skill.write_text(skill.read_text().replace("recon-mapping-contract", key))
    return package, profile


def external(
    root: Path, package: Path, profile: Path, dependencies: tuple[ReleasePackage, ...] = ()
) -> ReleasePackage:
    """Fixture producer only; immutable backend artifact distinct from CandidateSnapshot."""
    from omnis.modules.settings.candidate_catalog import COMPILER_REVISION, EVALUATOR_REVISION

    material, sources, _ = capture([str(package)], str(profile))
    compiled = skill_catalog.compile_catalog((package,), profile, dependencies=dependencies)
    output = skill_catalog.evaluate_pure(
        compiled, {"capture": '[{"method":"GET","path":"/synthetic","status":200}]'}
    )
    assert len(output.outputs_json) == 3
    index = resolved_index(compiled)
    material["resolved-index.json"] = canonical(index)
    sources.append(index_source(index))
    bindings = [
        {
            "package_key": sources[0]["package_key"],
            "entity_kind": kind,
            "key": key,
            "ref": {
                "kind": kind,
                "id": str(uuid4()),
                "revision": 1,
                "digest": sources[0]["package_digest"],
            },
        }
        for kind, key in cast(list[list[str]], sources[0]["identities"])
    ]
    qualification = envelope(
        "release-qualification",
        {
            "material_digest": compiled.material_digest,
            "resolved_index_digest": compiled.resolved_index_digest,
            "dependency_closure_refs": list(compiled.dependency_closure_refs),
            "dependency_closure_digest": digest(canonical(list(compiled.dependency_closure_refs))),
            "compiler_revision": COMPILER_REVISION,
            "evaluator_revision": EVALUATOR_REVISION,
            "static_status": "STATIC_PASS",
            "pure_status": "PURE_PASS",
            "resolution": "NO_MODEL",
            "effective": None,
            "outputs": [raw.decode() for raw in output.outputs_json],
            "pure_input": {"capture": '[{"method":"GET","path":"/synthetic","status":200}]'},
        },
    )
    artifact = envelope(
        "qualified-release",
        {
            "authority": "EXTERNAL_PREQUALIFIED",
            "package_key": sources[0]["package_key"],
            "package_digest": sources[0]["package_digest"],
            "sources": sources,
            "bindings": bindings,
            "qualification_ref": reference(qualification),
            "dependency_artifact_refs": [],
        },
    )
    requested: list[dict[str, object]] = []

    def selectors(value: object) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "RELEASE":
                requested.append(cast(dict[str, object], value["ref"]))
            for child in value.values():
                selectors(child)
        elif isinstance(value, list):
            for child in value:
                selectors(child)

    for name, raw in material.items():
        if name.endswith(".yaml"):
            selectors(yaml.safe_load(raw))
    cast(dict[str, object], artifact["payload"])["dependency_artifact_refs"] = [
        reference(json.loads(d.artifact_json))
        for d in dependencies
        if any(b["ref"] in requested for b in json.loads(d.artifact_json)["payload"]["bindings"])
    ]
    artifact["digest"] = digest(canonical({k: v for k, v in artifact.items() if k != "digest"}))
    finalize(root, "candidates", str(artifact["id"]), material)
    return ReleasePackage(root, canonical(artifact), canonical(qualification))


def binding(dependency: ReleasePackage, kind: str, key: str) -> dict[str, object]:
    artifact = json.loads(dependency.artifact_json)
    return cast(
        dict[str, object],
        next(
            b["ref"]
            for b in artifact["payload"]["bindings"]
            if b["entity_kind"] == kind and b["key"] == key
        ),
    )


def test_qualified_external_schema_is_pure_and_exact(ipc_directory: Path) -> None:
    assert Path(skill_catalog.__file__).resolve().is_relative_to(ROOT / "api/src")
    assert "dependencies" in inspect.signature(skill_catalog.compile_catalog).parameters, (
        "nonempty qualified RELEASE inventory is not implemented"
    )
    root = private_root(ipc_directory / "catalog")
    package, profile = seed(ipc_directory, "external")
    dependency = external(root, package, profile)
    local, local_profile = seed(ipc_directory, "local")
    path = local / "omnis.yaml"
    manifest = yaml.safe_load(path.read_bytes())
    exact = binding(dependency, "schema", "capture")
    manifest["input_schema_ref"] = {"kind": "RELEASE", "ref": exact}
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    with pytest.raises(CatalogError, match="DEPENDENCY_UNAVAILABLE"):
        skill_catalog.compile_catalog((local,), local_profile)
    compiled = skill_catalog.compile_catalog((local,), local_profile, dependencies=(dependency,))
    assert exact in compiled.dependency_closure_refs
    assert compiled.resolution == "NO_MODEL"
    assert (
        len(
            skill_catalog.evaluate_pure(
                compiled, {"capture": '[{"method":"GET","path":"/synthetic","status":200}]'}
            ).outputs_json
        )
        == 3
    )
    index = resolved_index(compiled)
    assert index["dependency_artifact_refs"] == [reference(json.loads(dependency.artifact_json))]
    assert all(ref["digest"] == exact["digest"] for ref in compiled.dependency_closure_refs)
    manifest["input_schema_ref"]["ref"]["digest"] = "0" * 64
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    with pytest.raises(CatalogError, match="DEPENDENCY_UNAVAILABLE"):
        skill_catalog.compile_catalog((local,), local_profile, dependencies=(dependency,))


def test_candidate_bindings_are_exact_nonrecursive_inventory(ipc_directory: Path) -> None:
    from omnis.modules.settings import candidate_index

    assert hasattr(candidate_index, "bind_catalog"), "durable reservation binding is missing"
    package, profile = seed(ipc_directory, "candidate")
    compiled = skill_catalog.compile_catalog((package,), profile)
    _, sources, _ = capture([str(package)], str(profile))
    bindings = [
        {
            "package_key": source.get("package_key", "@profile"),
            "entity_kind": kind,
            "key": key,
            "ref": {
                "kind": kind,
                "id": str(uuid4()),
                "revision": 1,
                "digest": source.get("package_digest", "a" * 64),
            },
        }
        for source in sources
        for kind, key in cast(list[list[str]], source["identities"])
    ]
    bound = candidate_index.bind_catalog(compiled, bindings)
    index = resolved_index(bound)
    assert index["catalog_bindings"] == sorted(bindings, key=canonical)
    assert bound.material_digest == compiled.material_digest
    assert bound.resolved_index_digest != compiled.resolved_index_digest
    wrong = [dict(binding) for binding in bindings]
    wrong[0] = {**wrong[0], "ref": {**cast(dict[str, object], wrong[0]["ref"]), "digest": "0" * 64}}
    with pytest.raises(CatalogError, match="REF_MISMATCH"):
        candidate_index.bind_catalog(compiled, wrong)


def test_qualification_cannot_claim_fabricated_pure_outputs(ipc_directory: Path) -> None:
    root = private_root(ipc_directory / "catalog")
    package, profile = seed(ipc_directory, "qualified")
    dependency = external(root, package, profile)
    local, local_profile = seed(ipc_directory, "consumer")
    path = local / "omnis.yaml"
    document = yaml.safe_load(path.read_bytes())
    document["input_schema_ref"] = {
        "kind": "RELEASE",
        "ref": binding(dependency, "schema", "capture"),
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    skill_catalog.compile_catalog((local,), local_profile, dependencies=(dependency,))
    qualification = json.loads(dependency.qualification_json)
    qualification["payload"]["outputs"] = ["{}", "{}", "{}"]
    qualification["digest"] = digest(
        canonical({k: v for k, v in qualification.items() if k != "digest"})
    )
    artifact = json.loads(dependency.artifact_json)
    artifact["payload"]["qualification_ref"] = reference(qualification)
    artifact["digest"] = digest(canonical({k: v for k, v in artifact.items() if k != "digest"}))
    forged = replace(
        dependency, artifact_json=canonical(artifact), qualification_json=canonical(qualification)
    )
    with pytest.raises(CatalogError, match="RELEASE_UNQUALIFIED"):
        skill_catalog.compile_catalog((local,), local_profile, dependencies=(forged,))


def test_profile_can_select_exact_external_procedure(ipc_directory: Path) -> None:
    root = private_root(ipc_directory / "catalog")
    package, profile = seed(ipc_directory, "external-profile")
    dependency = external(root, package, profile)
    local, local_profile = seed(ipc_directory, "profile-consumer")
    document = yaml.safe_load(local_profile.read_bytes())
    recipe = document["agent_recipes"][0]
    recipe["package_refs"].append(
        {"kind": "RELEASE", "ref": binding(dependency, "package", "external-profile")}
    )
    recipe["technique_refs"] = [
        {"kind": "RELEASE", "ref": binding(dependency, "technique", "capture-mapping")}
    ]
    recipe["procedure_refs"] = [
        {"kind": "RELEASE", "ref": binding(dependency, "procedure", "map-capture")}
    ]
    local_profile.write_text(yaml.safe_dump(document, sort_keys=False))
    compiled = skill_catalog.compile_catalog((local,), local_profile, dependencies=(dependency,))
    assert binding(dependency, "procedure", "map-capture") in compiled.dependency_closure_refs
    recipe["package_refs"] = recipe["package_refs"][:1]
    local_profile.write_text(yaml.safe_dump(document, sort_keys=False))
    with pytest.raises(CatalogError, match="PROFILE_PACKAGE_MISMATCH"):
        skill_catalog.compile_catalog((local,), local_profile, dependencies=(dependency,))


def test_declared_external_cycle_is_denied(ipc_directory: Path) -> None:
    root = private_root(ipc_directory / "catalog")
    package, profile = seed(ipc_directory, "cycle")
    dependency = external(root, package, profile)
    local, local_profile = seed(ipc_directory, "cycle-consumer")
    path = local / "omnis.yaml"
    document = yaml.safe_load(path.read_bytes())
    document["input_schema_ref"] = {
        "kind": "RELEASE",
        "ref": binding(dependency, "schema", "capture"),
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    record = json.loads(dependency.artifact_json)
    # The graph token is an exact immutable artifact ref, not a mutable source selector.
    record["payload"]["dependency_artifact_refs"] = [reference(record)]
    record["digest"] = digest(canonical({k: v for k, v in record.items() if k != "digest"}))
    cyclic = replace(dependency, artifact_json=canonical(record))
    with pytest.raises(CatalogError, match="DEPENDENCY_CYCLE"):
        skill_catalog.compile_catalog((local,), local_profile, dependencies=(cyclic,))


def test_diamond_closure_is_transitive_deduplicated_and_deterministic(ipc_directory: Path) -> None:
    root = private_root(ipc_directory / "catalog")
    package_d, profile_d = seed(ipc_directory, "diamond-d")
    d = external(root, package_d, profile_d)

    def with_schema(key: str, dependency: ReleasePackage) -> tuple[Path, Path]:
        package, profile = seed(ipc_directory, key)
        path = package / "omnis.yaml"
        document = yaml.safe_load(path.read_bytes())
        document["input_schema_ref"] = {
            "kind": "RELEASE",
            "ref": binding(dependency, "schema", "capture"),
        }
        path.write_text(yaml.safe_dump(document, sort_keys=False))
        return package, profile

    package_b, profile_b = with_schema("diamond-b", d)
    b = external(root, package_b, profile_b, (d,))
    package_c, profile_c = with_schema("diamond-c", d)
    c = external(root, package_c, profile_c, (d,))
    package_a, profile_a = with_schema("diamond-a", b)
    path = package_a / "omnis.yaml"
    document = yaml.safe_load(path.read_bytes())
    document["output_schema_ref"] = {"kind": "RELEASE", "ref": binding(c, "schema", "surface_map")}
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    a = external(root, package_a, profile_a, (b, c, d))
    local, local_profile = with_schema("diamond-consumer", a)
    inventory = (a, b, c, d)
    compiled = skill_catalog.compile_catalog((local,), local_profile, dependencies=inventory)
    reverse = skill_catalog.compile_catalog(
        (local,), local_profile, dependencies=tuple(reversed(inventory))
    )
    assert compiled.resolved_index_digest == reverse.resolved_index_digest
    assert len(compiled.dependency_artifact_refs) == 4
    tokens = [canonical(ref) for ref in compiled.dependency_closure_refs]
    assert len(tokens) == len(set(tokens))
    assert binding(d, "schema", "capture") in compiled.dependency_closure_refs
