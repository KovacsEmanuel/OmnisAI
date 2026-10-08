"""R1-N03: preserve valid SemVer text and refuse malformed identifiers."""

import pytest

from fixtures.b06a.consumer import CatalogSeed, blocked, write_yaml, yaml_object
from fixtures.b06a.consumer import seed as seed


def replace_version(seed: CatalogSeed, version: str) -> None:
    manifest = yaml_object(seed.manifest)
    manifest["version"] = version
    write_yaml(seed.manifest, manifest)
    text = (seed.package / "SKILL.md").read_text(encoding="utf-8")
    (seed.package / "SKILL.md").write_text(
        text.replace("version: 0.1.0", f"version: {version}"), encoding="utf-8"
    )


@pytest.mark.parametrize("version", ["1.2.3-a..b", "1.2.3-01", "1.2.3+foo..bar"])
def test_invalid_semver_is_blocked_by_real_consumer(seed: CatalogSeed, version: str) -> None:
    seed.compile()
    replace_version(seed, version)
    assert blocked(seed.cli("compile")) == "INVALID_DTO"


@pytest.mark.parametrize(
    "version", ["1.2.3-alpha.1+build.7", "1.2.3+001", "1.2.3-0.01alpha.--+build-01"]
)
def test_valid_semver_is_preserved(seed: CatalogSeed, version: str) -> None:
    replace_version(seed, version)
    seed.compile()
    assert yaml_object(seed.manifest)["version"] == version
