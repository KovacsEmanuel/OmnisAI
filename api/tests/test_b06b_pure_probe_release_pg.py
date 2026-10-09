"""R1-PURE-01: real dependency-bearing publication, not a forged snapshot.

External prequalification uses the existing labeled B06a fixture producer;
local capture/review/freeze/eval/TTY publication and snapshot use real C01 CLI.
"""

import asyncio
from typing import cast

import pytest
from sqlalchemy.engine import URL

from fixtures.b06a_durable.releases import binding, external, install_fixture, seed
from fixtures.b06b_publication.consumer import (
    canonical,
    confirmed,
    envelope,
    new_seed,
    publish_request,
    qualify,
    strict_json,
)
from fixtures.b06b_pure_probe.consumer import Probe, require_consumer
from omnis.modules.settings import skill_catalog
from omnis.modules.settings.candidate_material import private_root
from omnis.modules.settings.catalog_models import CatalogError, CompiledCatalog, PureEvaluation
from test_b06b_pure_probe_pg import Published, dispatch, ledger


def test_release_dependency_refused_before_qualification_executor(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    require_consumer()
    url = cast(URL, request.getfixturevalue("migrated_database_url"))
    dsn = url.render_as_string(hide_password=False)
    local = new_seed()
    root = private_root(local.root)
    package, profile = seed(local.directory / "external", "external-probe")
    dependency = external(root, package, profile)
    install_fixture(url, local.owner, (dependency,))
    manifest_path = local.package / "omnis.yaml"
    manifest = strict_json(manifest_path.read_text())
    manifest["input_schema_ref"] = {
        "kind": "RELEASE",
        "ref": binding(dependency, "schema", "capture"),
    }
    manifest_path.write_bytes(canonical(manifest))
    q = qualify(local, dsn)
    published = local.success("publish", publish_request(q, confirmed(q, dsn)), dsn)
    snapshot = local.success(
        "snapshot", local.write(publication_ref=published["publication_ref"]), dsn
    )
    snapshot_body = envelope(snapshot["snapshot"], snapshot["snapshot_ref"])
    assert len(cast(list[object], snapshot_body["dependency_artifact_refs"])) == 1
    p = Published(
        q, Probe(local.directory, local.package, local.profile, root, local.owner), url, snapshot
    )
    command = p.select_request()
    before = ledger(url)
    calls: list[object] = []
    original = skill_catalog.evaluate_pure

    def observed(compiled: CompiledCatalog, input_object: object) -> PureEvaluation:
        calls.append(input_object)
        return original(compiled, input_object)

    with monkeypatch.context() as patch:
        patch.setattr(skill_catalog, "evaluate_pure", observed)
        with pytest.raises(CatalogError, match="^RELEASE_DEPENDENCY_NOT_SUPPORTED$"):
            asyncio.run(dispatch(p, "select", command))
    assert calls == [], "unsupported release reached qualification PURE before denial"
    p.probe.denied("select", command, dsn, "RELEASE_DEPENDENCY_NOT_SUPPORTED")
    assert ledger(url) == before
