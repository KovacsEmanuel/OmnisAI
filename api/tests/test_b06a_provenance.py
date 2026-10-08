"""R1-N02 authoring evidence: source pin exists and contains the declared bytes."""

import hashlib
import subprocess

from fixtures.b06a.consumer import ROOT, CatalogSeed, mapping, sequence, yaml_object
from fixtures.b06a.consumer import seed as seed


def test_first_party_source_pin_contains_the_declared_bytes(seed: CatalogSeed) -> None:
    seed.compile()
    manifest = yaml_object(seed.manifest)
    sources = sequence(manifest["provenance"])
    assert sources
    for item in sources:
        source = mapping(item)
        revision, path = source["revision"], source["path"]
        assert type(revision) is str and type(path) is str
        result = subprocess.run(
            ["git", "show", f"{revision}:skills/recon-mapping-contract/{path}"],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, "Pinned first-party source does not exist at revision"
        assert hashlib.sha256(result.stdout).hexdigest() == source["source_digest"]
    # Git is a development oracle only; the installed PURE compiler never looks up Git.
