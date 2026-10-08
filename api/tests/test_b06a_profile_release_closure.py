"""Regression for both snapshot1 reviews: retained qualification profile edges."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from omnis.modules.settings.candidate_material import digest, private_root
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.settings.skill_catalog import compile_catalog, evaluate_pure
from test_b06a_release_product import binding, external, seed


def test_qualified_profile_only_transitive_release_round_trip(ipc_directory: Path) -> None:
    root = private_root(ipc_directory / "catalog")
    pb, fb = seed(ipc_directory, "qualified-b")
    b = external(root, pb, fb)
    pa, fa = seed(ipc_directory, "qualified-a")
    document = yaml.safe_load(fa.read_bytes())
    recipe = document["agent_recipes"][0]
    recipe["package_refs"].append({"kind": "RELEASE", "ref": binding(b, "package", "qualified-b")})
    for kind, key in (("technique", "capture-mapping"), ("procedure", "map-capture")):
        recipe[kind + "_refs"] = [{"kind": "RELEASE", "ref": binding(b, kind, key)}]
    fa.write_text(yaml.safe_dump(document, sort_keys=False))
    a = external(root, pa, fa, (b,))
    local, profile = seed(ipc_directory, "profile-closure-consumer")
    path = local / "omnis.yaml"
    manifest = yaml.safe_load(path.read_bytes())
    manifest["input_schema_ref"] = {"kind": "RELEASE", "ref": binding(a, "schema", "capture")}
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))

    compiled = compile_catalog((local,), profile, dependencies=(a, b))
    expected = [
        binding(a, "package", "qualified-a"),
        binding(a, "schema", "capture"),
        binding(b, "package", "qualified-b"),
        binding(b, "technique", "capture-mapping"),
        binding(b, "procedure", "map-capture"),
    ]
    assert list(compiled.dependency_closure_refs) == sorted(expected, key=canonical)
    reversed_inventory = compile_catalog((local,), profile, dependencies=(b, a))
    assert compiled.resolved_index_digest == reversed_inventory.resolved_index_digest
    assert len(evaluate_pure(compiled, {"capture": "[]"}).outputs_json) == 3
    with pytest.raises(CatalogError, match="^DEPENDENCY_UNAVAILABLE$"):
        compile_catalog((local,), profile, dependencies=(a,))

    record = json.loads(a.artifact_json)
    record["payload"]["dependency_artifact_refs"] = []
    record["digest"] = digest(canonical({k: v for k, v in record.items() if k != "digest"}))
    undeclared = replace(a, artifact_json=canonical(record))
    with pytest.raises(CatalogError, match="^RELEASE_MISMATCH$"):
        compile_catalog((local,), profile, dependencies=(undeclared, b))
    assert compile_catalog((local,), profile, dependencies=(a, b)) == compiled
