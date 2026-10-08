"""Literal Unicode request denials before JSONB/replay, with same-CLI PG control."""

import json
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from fixtures.b06a_durable.consumer import copy_seed, freeze, readback, scratch_directory
from omnis.modules.settings.candidate_catalog import validate_request
from omnis.modules.settings.catalog_models import CatalogError


def request_with(input_object: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "snapshot_ref": {
            "kind": "candidate-snapshot",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "0" * 64,
        },
        "evaluation_kind": "PURE",
        "input": input_object,
    }


@pytest.mark.parametrize(
    "input_object",
    [
        {"capture": "\x00"},
        {"capt\x00ure": "[]"},
        {"capture": "[]", "extra": [{"nested": "\x00"}]},
        {"capture": "\ud800"},
    ],
)
def test_candidate_tracer_request_invalid_unicode(input_object: dict[str, object]) -> None:
    control = request_with({"capture": "[]"})
    assert validate_request("evaluate", control) == control
    with pytest.raises(CatalogError, match="^INVALID_REQUEST$"):
        validate_request("evaluate", request_with(input_object))


def test_candidate_tracer_request_literal_escape_is_not_nul() -> None:
    control = request_with({"capture": "[]", "literal": r"\u0000"})
    assert validate_request("evaluate", control) == control


def test_candidate_tracer_request_nul_same_cli(migrated_database_url: URL) -> None:
    seed = copy_seed(scratch_directory() / "parent-unicode")
    url = migrated_database_url.render_as_string(hide_password=False)
    frozen = freeze(seed, url)
    input_object = json.loads((seed.directory / "golden.json").read_bytes())["input"]
    positive = seed.write_request(
        snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input=input_object
    )
    seed.success("evaluate", positive, url)
    before = readback(seed, url, frozen)
    for value in ({"capture": "\x00"}, {"capt\x00ure": "[]"}, {"capture": "[]", "extra": ["\x00"]}):
        bad = seed.write_request(
            snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input=value
        )
        seed.denied("evaluate", bad, url, "INVALID_REQUEST")
    assert readback(seed, url, frozen) == before
