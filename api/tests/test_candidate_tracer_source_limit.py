"""Source budget controls at actual capture/request seams, not persisted DB refs."""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.settings import candidate_material as material
from omnis.modules.settings.candidate_catalog import validate_request
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_yaml

ROOT = Path(__file__).resolve().parents[2]


def command(**fields: object) -> dict[str, object]:
    return {"schema_version": 1, "owner_id": str(uuid4()), "command_id": str(uuid4()), **fields}


def test_candidate_tracer_maximum_capture_sources_fit_exact_request_budget(tmp_path: Path) -> None:
    packages: list[str] = []
    for number in range(127):
        path = tmp_path / f"package-{number}"
        shutil.copytree(ROOT / "skills/recon-mapping-contract", path)
        manifest = load_yaml((path / "omnis.yaml").read_bytes())
        assert isinstance(manifest, dict)
        manifest["package_key"] = f"synthetic-{number}"
        (path / "omnis.yaml").write_bytes(canonical(manifest))
        packages.append(str(path))
    profile = str(ROOT / "profiles/recon-mapping-contract.yaml")
    validate_request("capture", command(author_kind="IMPORT", packages=packages, profile=profile))
    _, sources, _ = material.capture(packages, profile)
    assert len(sources) == 128
    # Synthetic IDs only at the strict request-validation seam, never DB/receipt evidence.
    refs = [
        {"kind": "source-draft", "id": str(uuid4()), "revision": 1, "digest": "a" * 64}
        for _ in sources
    ]
    for operation in ("review", "reject"):
        validate_request(operation, command(draft_ref=refs[-1], source_draft_refs=refs))
    with pytest.raises(CatalogError, match="^COUNT_LIMIT$"):
        validate_request(
            "capture", command(author_kind="IMPORT", packages=[*packages, profile], profile=profile)
        )


def test_candidate_tracer_capture_helper_rejects_first_over_limit_before_reads(
    tmp_path: Path,
) -> None:
    with pytest.raises(CatalogError, match="^COUNT_LIMIT$"):
        material.capture([str(tmp_path / f"absent-{number}") for number in range(128)], "absent")
