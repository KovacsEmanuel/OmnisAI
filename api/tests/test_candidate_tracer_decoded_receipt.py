"""Admitted inner-JSON Unicode failures retain exact input/receipt and replay."""

import json

from sqlalchemy.engine import URL

from conftest import connect_test_database
from fixtures.b06a_durable.consumer import copy_seed, freeze, readback, scratch_directory


def test_candidate_tracer_decoded_receipt_same_cli(migrated_database_url: URL) -> None:
    seed = copy_seed(scratch_directory() / "decoded-receipt")
    url = migrated_database_url.render_as_string(hide_password=False)
    frozen = freeze(seed, url)
    control = seed.write_request(
        snapshot_ref=frozen["snapshot_ref"],
        evaluation_kind="PURE",
        input={"capture": json.dumps([{"method": "GET", "path": "/ok", "status": 200}])},
    )
    assert seed.success("evaluate", control, url)["status"] == "PURE_PASS"
    input_object = {"capture": json.dumps([{"method": "GET", "path": "/\ud800", "status": 200}])}
    admitted = seed.write_request(
        snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input=input_object
    )
    seed.denied("evaluate", admitted, url, "INVALID_PURE_INPUT")
    back = readback(seed, url, frozen)
    evaluations = back["evaluations"]
    assert isinstance(evaluations, list) and len(evaluations) == 2
    receipts = [
        item
        for item in evaluations
        if isinstance(item, dict)
        and isinstance(item["payload"], dict)
        and item["payload"]["status"] == "BLOCKED"
    ]
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["payload"]["reason"] == "INVALID_PURE_INPUT"
    assert receipt["payload"]["outputs"] == []
    input_ref = receipt["payload"]["input_ref"]
    assert isinstance(input_ref, dict)
    with connect_test_database(migrated_database_url, autocommit=True) as connection:
        row = connection.execute(
            "SELECT envelope FROM catalog_record WHERE id=%s::uuid AND owner_id=%s::uuid",
            (input_ref["id"], admitted["owner_id"]),
        ).fetchone()
        assert row is not None
        stored = row[0]
        assert isinstance(stored, dict)
        body = stored["payload"]
        assert isinstance(body, dict) and body["input"] == input_object
    # The denial is delivered after commit; each invocation is a fresh real process.
    seed.denied("evaluate", admitted, url, "INVALID_PURE_INPUT")
    assert readback(seed, url, frozen) == back
