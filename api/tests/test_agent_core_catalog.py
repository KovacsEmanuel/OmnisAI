"""S1 core source probes; no model, target or PostgreSQL effects."""

from pathlib import Path

import pytest

from omnis.modules.settings.candidate_index import compile_material, resolved_index
from omnis.modules.settings.candidate_material import capture, finalize, private_root, read_material
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.skill_catalog import compile_catalog, evaluate_pure

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "skills/omnis-agent-core"
PROFILE = ROOT / "profiles/omnis-agent-core.yaml"


def test_api_key_core_capture_compile_evaluate_without_hermes(tmp_path: Path) -> None:
    assert PACKAGE.is_dir(), "S1 requires the versioned API-key core package"
    material, sources, sha = capture([str(PACKAGE)], str(PROFILE))
    for source in sources:
        source["material_digest"] = sha
    root = private_root(tmp_path / "catalog")
    directory = finalize(root, "drafts", "synthetic", material)
    assert read_material(root, "drafts", "synthetic", sources) == material
    compiled = compile_material(directory, sources)
    assert compiled.material_digest == sha
    assert resolved_index(compiled)["catalog_schema_version"] == 2
    assert compiled.resolution == "NO_MODEL"
    assert compiled.verification_kind == "CONTRACT"
    assert not compiled.dependency_artifact_refs
    assert evaluate_pure(compiled, {"context": "owner-selected synthetic context"}).outputs == (
        {"context": "owner-selected synthetic context"},
    )
    with pytest.raises(CatalogError, match="SCHEMA_VALIDATION"):
        evaluate_pure(compiled, {"context": "synthetic", "grant": "shell"})


def test_core_duplicate_package_is_not_a_search_path() -> None:
    with pytest.raises(CatalogError, match="PACKAGE_SHADOW"):
        compile_catalog((PACKAGE, PACKAGE), PROFILE)
