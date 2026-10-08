"""R1-N01: validation and digest must consume the same captured manifest bytes."""

import json
from pathlib import Path

import pytest

from fixtures.b06a.consumer import CatalogSeed, mapping, release_digest, sequence
from fixtures.b06a.consumer import seed as seed
from omnis.modules.settings import skill_catalog


def test_manifest_digest_uses_the_exact_validated_capture(
    seed: CatalogSeed, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seed.compile()
    expected_digest = release_digest(seed)
    original = skill_catalog.read_file
    reads = 0

    def replace_after_first_read(path: Path, maximum: int = 1048576) -> bytes:
        nonlocal reads
        data = original(path, maximum)
        if path == seed.manifest:
            reads += 1
            if reads == 1:
                seed.manifest.write_bytes(
                    data.replace(skill_catalog.NATIVE_HERMES_REVISION.encode(), b"0" * 40)
                    + b"\npublication: PUBLISHED\n"
                )
        return data

    monkeypatch.setattr(skill_catalog, "read_file", replace_after_first_read)
    code = skill_catalog.main(
        ["compile", "--package", str(seed.package), "--profile", str(seed.profile)]
    )
    output = capsys.readouterr()
    assert code == 0 and output.err == ""
    report = mapping(json.loads(output.out))
    assert report["status"] == "STATIC_PASS"
    refs = sequence(report["resolved_refs"])
    assert refs and all(mapping(ref)["digest"] == expected_digest for ref in refs)
    assert reads == 1
    monkeypatch.setattr(skill_catalog, "read_file", original)
    fresh = seed.cli("compile")
    assert fresh.returncode == 2 and fresh.stdout == ""
    assert mapping(json.loads(fresh.stderr))["reason"] == "INVALID_DTO"
