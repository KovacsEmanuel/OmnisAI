"""R2: malformed declared filenames must refuse without leaking a traceback."""

import pytest

from fixtures.b06a.consumer import MARKER, CatalogSeed, blocked, sequence, write_yaml, yaml_object
from fixtures.b06a.consumer import seed as seed


@pytest.mark.parametrize("field", ["procedures", "support_files"])
def test_nul_declared_path_is_sanitized(seed: CatalogSeed, field: str) -> None:
    seed.compile()
    manifest = yaml_object(seed.manifest)
    paths = sequence(manifest[field])
    paths.append(f"nul\x00{MARKER}.yaml")
    manifest[field] = paths
    write_yaml(seed.manifest, manifest)
    assert blocked(seed.cli("compile")) == "INVALID_PATH"
