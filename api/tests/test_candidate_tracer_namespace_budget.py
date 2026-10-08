"""A finalized declared aggregate must remain readable beyond one-package limits."""

import shutil
from pathlib import Path
from uuid import uuid4

from omnis.modules.settings import candidate_material as material
from omnis.modules.settings.catalog_schema import canonical, load_yaml


def test_candidate_tracer_namespace_declared_257_files_read_back(tmp_path: Path) -> None:
    root = material.private_root(tmp_path / "catalog")
    files = {f"source-{number}.txt": b"bounded" for number in range(257)}
    identity = str(uuid4())
    material.finalize(root, "drafts", identity, files)
    source: dict[str, object] = {
        "prefix": "",
        "files": [
            {"path": name, "sha256": material.digest(raw), "size": len(raw)}
            for name, raw in files.items()
        ],
    }
    assert material.read_material(root, "drafts", identity, [source]) == files


def test_candidate_tracer_namespace_maximum_package_capture_read_back(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    packages: list[str] = []
    for number in range(material.MAX_SOURCE_PACKAGES):
        package = tmp_path / f"package-{number}"
        shutil.copytree(repository / "skills/recon-mapping-contract", package)
        manifest = load_yaml((package / "omnis.yaml").read_bytes())
        assert isinstance(manifest, dict)
        manifest["package_key"] = f"synthetic-{number}"
        (package / "omnis.yaml").write_bytes(canonical(manifest))
        packages.append(str(package))
    files, sources, _ = material.capture(
        packages, str(repository / "profiles/recon-mapping-contract.yaml")
    )
    root = material.private_root(tmp_path / "catalog")
    identity = str(uuid4())
    material.finalize(root, "drafts", identity, files)
    assert len(sources) == 128
    assert material.read_material(root, "drafts", identity, sources) == files
