"""Real fresh-process durable consumer, not repeated in-memory calls.

DB allocation is deliberately behind the positive feature-availability assertion.
The parent runs this through the existing attested PostgreSQL gate after integration.
"""

import json
import shutil

import pytest
from sqlalchemy.engine import URL

from fixtures.b06a.consumer import mapping, sequence
from fixtures.b06a_durable.consumer import (
    canonical,
    copy_seed,
    envelope,
    freeze,
    readback,
    require_consumer,
    scratch_directory,
)


def test_capture_review_freeze_readback_positive(request: pytest.FixtureRequest) -> None:
    require_consumer()
    url: URL = request.getfixturevalue("migrated_database_url")
    directory = scratch_directory() / "durable-tracer"
    seed = copy_seed(directory)
    database_url = url.render_as_string(hide_password=False)
    frozen = freeze(seed, database_url)
    first = readback(seed, database_url, frozen)
    # Each success invokes -I -B -m in a new joined process on the same PG/root.
    assert readback(seed, database_url, frozen) == first


def test_workspace_removed_fresh_process_evaluation_uses_frozen_bytes(
    request: pytest.FixtureRequest,
) -> None:
    require_consumer()
    url: URL = request.getfixturevalue("migrated_database_url")
    seed = copy_seed(scratch_directory() / "durable-restart")
    database_url = url.render_as_string(hide_password=False)
    frozen = freeze(seed, database_url)
    before = readback(seed, database_url, frozen)
    golden = mapping(json.loads((seed.directory / "golden.json").read_bytes()))
    (seed.package / "SKILL.md").write_bytes(b"mutated workspace is not frozen material")
    shutil.rmtree(seed.package)
    seed.profile.unlink()
    assert readback(seed, database_url, frozen) == before
    static = seed.success(
        "evaluate",
        seed.write_request(
            snapshot_ref=frozen["snapshot_ref"], evaluation_kind="STATIC", input=None
        ),
        database_url,
    )
    static_payload = envelope(static["evaluation"], static["evaluation_ref"])
    pure = seed.success(
        "evaluate",
        seed.write_request(
            snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input=golden["input"]
        ),
        database_url,
    )
    pure_payload = envelope(pure["evaluation"], pure["evaluation_ref"])
    assert sequence(pure["outputs"]) == [
        canonical(item).decode() for item in sequence(golden["outputs"])
    ], "all three PURE outputs must match independently copied golden bytes"
    snapshot_payload = mapping(frozen["snapshot"])["payload"]
    for receipt in (static_payload, pure_payload):
        assert receipt["snapshot_ref"] == frozen["snapshot_ref"]
        assert receipt["material_digest"] == mapping(snapshot_payload)["material_digest"]
        assert (
            receipt["resolved_index_digest"] == mapping(snapshot_payload)["resolved_index_digest"]
        )
        assert receipt["resolution"] == "NO_MODEL" and receipt["effective"] is None
    after = readback(seed, database_url, frozen)
    assert after["snapshot"] == before["snapshot"]
    evaluations = [mapping(value) for value in sequence(after["evaluations"])]
    assert static["evaluation"] in evaluations and pure["evaluation"] in evaluations
