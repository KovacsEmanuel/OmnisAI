"""Real PG lock-wait evidence beyond Capture; no sequential concurrency claims."""

import json
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from conftest import connect_test_database
from fixtures.b06a.consumer import mapping, sequence
from fixtures.b06a_durable.consumer import (
    canonical,
    copy_seed,
    envelope,
    freeze,
    freeze_request,
    readback,
    reviewed,
    scratch_directory,
)
from fixtures.b06a_durable.overlap import ledger, overlap


@pytest.mark.parametrize("same_command", [True, False])
def test_candidate_tracer_overlapping_freeze_exactly_one_snapshot(
    migrated_database_url: URL,
    same_command: bool,
) -> None:
    seed = copy_seed(scratch_directory() / "overlap-freeze")
    url = migrated_database_url.render_as_string(hide_password=False)
    captured, review = reviewed(seed, url)
    command = freeze_request(seed, captured, review)
    other = command if same_command else {**command, "command_id": str(uuid4())}
    before = ledger(migrated_database_url)
    first, second = overlap(seed, migrated_database_url, ("freeze", command), ("freeze", other))
    assert first[1] is None and second == first
    assert first[0] is not None
    back = readback(seed, url, first[0])
    assert (
        mapping(mapping(back["snapshot"])["payload"])["candidate_refs"] == review["candidate_refs"]
    )
    after = ledger(migrated_database_url)
    assert len(after["catalog_record"]) == len(before["catalog_record"]) + 1
    assert len(after["catalog_command"]) == len(before["catalog_command"]) + (
        1 if same_command else 2
    )
    assert after["catalog_reservation"] == before["catalog_reservation"]
    assert len(list((seed.catalog_root / "candidates").iterdir())) == 1
    assert seed.success("freeze", command, url) == first[0]
    assert ledger(migrated_database_url) == after


@pytest.mark.parametrize("winner", ["freeze", "reject"])
def test_candidate_tracer_overlapping_freeze_reject_permitted_winner(
    migrated_database_url: URL,
    winner: str,
) -> None:
    seed = copy_seed(scratch_directory() / "overlap-reject")
    url = migrated_database_url.render_as_string(hide_password=False)
    captured, review = reviewed(seed, url)
    freeze_command = freeze_request(seed, captured, review)
    reject_command = seed.write_request(
        draft_ref=captured["draft_ref"],
        source_draft_refs=captured["source_draft_refs"],
    )
    commands = {"freeze": freeze_command, "reject": reject_command}
    loser = "reject" if winner == "freeze" else "freeze"
    before = ledger(migrated_database_url)
    first, second = overlap(
        seed,
        migrated_database_url,
        (winner, commands[winner]),
        (loser, commands[loser]),
    )
    assert first[1] is None and first[0] is not None
    assert second == (None, "CANDIDATE_FROZEN" if winner == "freeze" else "CANDIDATE_REJECTED")
    after = ledger(migrated_database_url)
    assert len(after["catalog_record"]) == len(before["catalog_record"]) + 1
    assert len(after["catalog_command"]) == len(before["catalog_command"]) + 1
    assert after["catalog_reservation"] == before["catalog_reservation"]
    if winner == "freeze":
        readback(seed, url, first[0])
    else:
        assert not list((seed.catalog_root / "candidates").iterdir())
        seed.denied("freeze", freeze_command, url, "CANDIDATE_REJECTED")
    seed.denied(
        "reject" if winner == "freeze" else "freeze",
        commands[loser],
        url,
        "CANDIDATE_FROZEN" if winner == "freeze" else "CANDIDATE_REJECTED",
    )
    assert ledger(migrated_database_url) == after


def test_candidate_tracer_overlapping_review_reservation_reject(migrated_database_url: URL) -> None:
    seed = copy_seed(scratch_directory() / "overlap-reservation")
    url = migrated_database_url.render_as_string(hide_password=False)
    captured = seed.success("capture", seed.capture_request(), url)
    fields = {key: captured[key] for key in ("draft_ref", "source_draft_refs")}
    review_command = seed.write_request(**fields)
    rejection = seed.write_request(**fields)
    # Review's SECOND owner lock: reservations are already committed, checker has not run.
    first, second = overlap(
        seed,
        migrated_database_url,
        ("review", review_command),
        ("reject", rejection),
        owner_lock_number=2,
    )
    assert first[1] is None and first[0] is not None
    assert second[1] is None and second[0] is not None and second[0]["state"] == "REJECTED"
    review = first[0]
    reserved_before = ledger(migrated_database_url)["catalog_reservation"]
    assert reserved_before and review["reservations"] == review["candidate_refs"]
    seed.denied("freeze", freeze_request(seed, captured, review), url, "CANDIDATE_REJECTED")
    # New bytes keep each identity but allocate a NEW revision; no rejected revision rebind.
    path = seed.package / "NOTICE.md"
    path.write_bytes(path.read_bytes() + b"\nnew independent material\n")
    newer, new_review = reviewed(seed, url)
    assert newer["draft_ref"] != captured["draft_ref"]
    old_refs = [mapping(item) for item in sequence(review["candidate_refs"])]
    new_refs = [mapping(item) for item in sequence(new_review["candidate_refs"])]
    old_package = {item["id"]: item for item in old_refs if item["kind"] != "profile"}
    new_package = {item["id"]: item for item in new_refs if item["kind"] != "profile"}
    assert old_package.keys() == new_package.keys()
    for identity, ref in old_package.items():
        revision = ref["revision"]
        assert type(revision) is int
        assert new_package[identity]["revision"] == revision + 1
        assert new_package[identity]["digest"] != ref["digest"]
    assert set(reserved_before) <= set(ledger(migrated_database_url)["catalog_reservation"])
    seed.denied("freeze", freeze_request(seed, newer, review), url, "TECHNICAL_REVIEW_MISMATCH")
    seed.success("freeze", freeze_request(seed, newer, new_review), url)


@pytest.mark.parametrize("case", ["duplicate", "conflict", "blocked_duplicate", "pass_blocked"])
def test_candidate_tracer_overlapping_evaluation_idempotency(
    migrated_database_url: URL,
    case: str,
) -> None:
    seed = copy_seed(scratch_directory() / "overlap-evaluate")
    url = migrated_database_url.render_as_string(hide_password=False)
    frozen = freeze(seed, url)
    golden = mapping(json.loads((seed.directory / "golden.json").read_bytes()))
    command = seed.write_request(
        snapshot_ref=frozen["snapshot_ref"],
        evaluation_kind="PURE",
        input={"invalid": "synthetic"} if case == "blocked_duplicate" else golden["input"],
    )
    other = dict(command)
    if case in {"conflict", "pass_blocked"}:
        other["input"] = {"invalid": "synthetic"}
    if case == "pass_blocked":
        other["command_id"] = str(uuid4())
    before = ledger(migrated_database_url)
    first, second = overlap(seed, migrated_database_url, ("evaluate", command), ("evaluate", other))
    if case == "blocked_duplicate":
        assert first == second == (None, "SCHEMA_VALIDATION")
    else:
        assert first[1] is None and first[0] is not None and first[0]["status"] == "PURE_PASS"
        assert first[0]["outputs"] == [
            canonical(item).decode() for item in sequence(golden["outputs"])
        ]
        if case == "duplicate":
            assert second == first
        else:
            assert second == (
                None,
                "COMMAND_CONFLICT" if case == "conflict" else "SCHEMA_VALIDATION",
            )
    after = ledger(migrated_database_url)
    count = 2 if case == "pass_blocked" else 1
    assert len(after["catalog_record"]) == len(before["catalog_record"]) + count * 2
    assert len(after["catalog_command"]) == len(before["catalog_command"]) + count
    assert len(list((seed.catalog_root / "receipts").iterdir())) == count
    back = readback(seed, url, frozen)
    evaluations = back["evaluations"]
    assert isinstance(evaluations, list) and len(evaluations) == count
    statuses = []
    for record in evaluations:
        record = mapping(record)
        receipt = envelope(
            record, {key: record[key] for key in ("kind", "id", "revision", "digest")}
        )
        status = receipt["status"]
        assert type(status) is str
        statuses.append(status)
        assert receipt["input_ref"] and receipt["resolution"] == "NO_MODEL"
        assert receipt["effective"] is None
        if receipt["status"] == "BLOCKED":
            assert receipt["reason"] == "SCHEMA_VALIDATION" and receipt["outputs"] == []
    assert sorted(statuses) == (
        ["BLOCKED", "PURE_PASS"]
        if count == 2
        else ["BLOCKED" if case == "blocked_duplicate" else "PURE_PASS"]
    )
    with connect_test_database(migrated_database_url, autocommit=True) as observer:
        row = observer.execute(
            "SELECT count(*) FROM catalog_record WHERE kind='evaluation-input' AND owner_id=%s",
            (seed.owner_id,),
        ).fetchone()
        assert row == (count,)
    if case == "blocked_duplicate":
        seed.denied("evaluate", command, url, "SCHEMA_VALIDATION")
    else:
        assert seed.success("evaluate", command, url) == first[0]
    assert ledger(migrated_database_url) == after
