"""Real private-PG C01 controls; no acquisition before feature-positive assertion.

Each operation uses fresh CLI processes; concurrency requires observed blocking
backends, not a scheduling sleep. Crash probes are software-only, not power loss.
"""

import asyncio
import copy
import importlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from conftest import connect_test_database
from fixtures.b06b_publication.consumer import (
    Qualified,
    canonical,
    confirmed,
    envelope,
    mapping,
    new_seed,
    publish_request,
    qualify,
    require_consumer,
    sequence,
    sha,
    strict_json,
)


def setup(request: pytest.FixtureRequest, author: str = "OPERATOR") -> tuple[Qualified, URL, str]:
    require_consumer()
    url = cast(URL, request.getfixturevalue("migrated_database_url"))
    database_url = url.render_as_string(hide_password=False)
    return qualify(new_seed(), database_url, author), url, database_url


def ledger(url: URL, owner: str) -> bytes:
    with connect_test_database(url) as connection:
        state = {}
        for table in ("catalog_record", "catalog_command", "catalog_publication_head"):
            rows = connection.execute(
                f"SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text",
            ).fetchall()
            state[table] = [row[0] for row in rows]
    return canonical(state)


def assert_publication(q: Qualified, result: dict[str, object]) -> dict[str, object]:
    assert result["state"] == "PUBLISHED"
    assert result["generation"] == cast(int, q.selection["expected_head_generation"]) + 1
    body = envelope(result["publication"], result["publication_ref"])
    for key, value in q.selection.items():
        assert body[key] == value, f"publication changed selected {key}"
    return body


def test_tty_publish_readback_replay_restart_and_inert_snapshot(
    request: pytest.FixtureRequest,
) -> None:
    q, url, dsn = setup(request)
    confirmation = confirmed(q, dsn)
    command = publish_request(q, confirmation)
    published = q.seed.success("publish", command, dsn)
    body = assert_publication(q, published)
    assert body["confirmation_ref"] == confirmation["confirmation_ref"]
    before = ledger(url, q.seed.owner)
    assert q.seed.success("publish", command, dsn) == published
    assert ledger(url, q.seed.owner) == before
    back = q.seed.success(
        "readback", q.seed.request(publication_ref=published["publication_ref"]), dsn
    )
    assert (
        back["publication"] == published["publication"] and back["snapshot"] == q.frozen["snapshot"]
    )
    assert back["state"] == "PUBLISHED" and back["assessment_selectable"] is False
    assert sha(canonical(back["resolved_index"])) == q.selection["resolved_index_digest"]
    evaluation_refs: list[dict[str, object]] = []
    for record in sequence(back["evaluations"]):
        obj = mapping(record)
        ref = {key: obj[key] for key in ("kind", "id", "revision", "digest")}
        envelope(obj, ref)
        evaluation_refs.append(ref)
    assert (
        q.static["evaluation_ref"] in evaluation_refs
        and q.pure["evaluation_ref"] in evaluation_refs
    )
    # Every success() above starts/exits the owning CLI process on this same PG.
    assert (
        q.seed.success(
            "readback", q.seed.request(publication_ref=published["publication_ref"]), dsn
        )
        == back
    )
    snapshot_request = q.seed.write(publication_ref=published["publication_ref"])
    inert = q.seed.success("snapshot", snapshot_request, dsn)
    payload = envelope(inert["snapshot"], inert["snapshot_ref"])
    assert mapping(inert["snapshot_ref"])["kind"] == "run-snapshot"
    assert payload["execution_purpose"] == "CONTRACT_PROBE"
    assert payload["publication_ref"] == published["publication_ref"]
    frozen = envelope(q.frozen["snapshot"], q.frozen["snapshot_ref"])
    assert payload["profile_ref"] == frozen["profile_ref"]
    assert payload["candidate_refs"] == frozen["candidate_refs"]
    assert payload["package_refs"] == [
        ref for ref in sequence(frozen["candidate_refs"]) if mapping(ref)["kind"] == "package"
    ]
    assert payload["dependency_closure_refs"] == frozen["dependency_closure_refs"]
    assert payload["method_review_policy"] == "CHECK_ONLY"
    assert payload["resolution"] == "NO_MODEL" and payload["effective"] is None
    assert q.seed.success("snapshot", snapshot_request, dsn) == inert
    state = ledger(url, q.seed.owner)
    q.seed.denied(
        "snapshot",
        {
            **q.seed.write(publication_ref=published["publication_ref"]),
            "execution_purpose": "ASSESSMENT",
        },
        dsn,
        "INVALID_REQUEST",
    )
    assert ledger(url, q.seed.owner) == state


def test_non_tty_and_ai_json_cannot_create_confirmation(request: pytest.FixtureRequest) -> None:
    q, url, dsn = setup(request, "AI")
    before = ledger(url, q.seed.owner)
    confirmation_request = q.seed.write(**q.selection)
    q.seed.denied("confirm", confirmation_request, dsn, "OPERATOR_CONFIRMATION_REQUIRED")
    for grant in (
        {"approved": True},
        {"actor": f"local-operator:{os.getuid()}"},
        {"author_kind": "OPERATOR"},
    ):
        q.seed.denied("confirm", {**confirmation_request, **grant}, dsn)
        assert ledger(url, q.seed.owner) == before
    declined, _ = q.seed.confirm(confirmation_request, dsn, answer="no")
    assert declined.returncode == 2 and declined.stdout == ""
    assert ledger(url, q.seed.owner) == before
    # AI source is not categorically banned: the trusted operator can review it.
    confirmation = confirmed(q, dsn)
    assert_publication(q, q.seed.success("publish", publish_request(q, confirmation), dsn))


def test_new_capture_after_confirm_refuses_stale_publish_but_retains_readback(
    request: pytest.FixtureRequest,
) -> None:
    q, url, dsn = setup(request)
    confirmation = confirmed(q, dsn)
    notice = q.seed.package / "NOTICE.md"
    notice.write_bytes(notice.read_bytes() + b"\nC01 independently authored D2.\n")
    second_command = q.seed.capture()
    d2 = q.seed.success("capture", second_command, dsn, candidate=True)
    assert d2["material_digest"] != q.capture["material_digest"]
    before = ledger(url, q.seed.owner)
    q.seed.denied("publish", publish_request(q, confirmation), dsn)
    assert ledger(url, q.seed.owner) == before
    head = q.seed.success("head", q.seed.request(draft_ref=d2["draft_ref"]), dsn)
    assert head["generation"] == cast(int, q.selection["expected_head_generation"]) + 1
    # Replay of D1 must not move the head backwards.
    assert q.seed.success("capture", q.capture_command, dsn, candidate=True) == q.capture
    assert q.seed.success("capture", second_command, dsn, candidate=True) == d2
    assert q.seed.success("head", q.seed.request(draft_ref=d2["draft_ref"]), dsn) == head
    # The global package identity is owned by this original owner; do not
    # accidentally test foreign-owner shadow admission instead of D2 readback.
    q2 = qualify(q.seed, dsn)
    publication = q2.seed.success("publish", publish_request(q2, confirmed(q2, dsn)), dsn)
    q2.seed.success("capture", q2.seed.capture(), dsn, candidate=True)
    assert (
        q2.seed.success(
            "readback", q2.seed.request(publication_ref=publication["publication_ref"]), dsn
        )["publication"]
        == publication["publication"]
    )


@pytest.mark.parametrize(
    "attack",
    [
        "foreign_owner",
        "material_digest",
        "index_digest",
        "closure_digest",
        "wrong_receipt",
        "wrong_confirmation",
        "missing_source",
        "source_digest",
    ],
)
def test_exact_selection_denials_leave_database_unchanged(
    request: pytest.FixtureRequest, attack: str
) -> None:
    q, url, dsn = setup(request)
    confirmation = confirmed(q, dsn)
    command = publish_request(q, confirmation)
    bad = copy.deepcopy(command)
    if attack == "foreign_owner":
        bad["owner_id"] = str(uuid4())
    elif attack in ("material_digest", "index_digest", "closure_digest"):
        bad[
            {
                "material_digest": "material_digest",
                "index_digest": "resolved_index_digest",
                "closure_digest": "dependency_closure_digest",
            }[attack]
        ] = "0" * 64
    elif attack == "wrong_receipt":
        bad["static_evaluation_ref"], bad["pure_evaluation_ref"] = (
            bad["pure_evaluation_ref"],
            bad["static_evaluation_ref"],
        )
    elif attack == "wrong_confirmation":
        mapping(bad["confirmation_ref"])["id"] = str(uuid4())
    elif attack == "missing_source":
        bad["source_draft_refs"] = [bad["draft_ref"]]
    else:
        mapping(sequence(bad["source_draft_refs"])[0])["digest"] = "0" * 64
    before = ledger(url, q.seed.owner)
    q.seed.denied("publish", bad, dsn)
    assert ledger(url, q.seed.owner) == before
    assert_publication(q, q.seed.success("publish", command, dsn))


@pytest.mark.parametrize("value", [True, 1.0, "1", None, 0, -1])
def test_invalid_generation_before_successful_command_replay(
    request: pytest.FixtureRequest, value: object
) -> None:
    q, url, dsn = setup(request)
    command = publish_request(q, confirmed(q, dsn))
    publication = q.seed.success("publish", command, dsn)
    before = ledger(url, q.seed.owner)
    # The wire parser normalizes floating-number refusal before the DTO.
    reason = "INVALID_JSON" if type(value) is float else "INVALID_REQUEST"
    q.seed.denied("publish", {**command, "expected_head_generation": value}, dsn, reason)
    assert ledger(url, q.seed.owner) == before
    assert q.seed.success("publish", command, dsn) == publication


@pytest.mark.parametrize(
    "attack",
    [
        "bool_revision",
        "float_revision",
        "uuid_uppercase",
        "duplicate",
        "nested_duplicate",
        "nul",
        "surrogate",
        "nan",
        "oversize",
    ],
)
def test_strict_wire_denials_before_existing_replay(
    request: pytest.FixtureRequest, attack: str
) -> None:
    q, url, dsn = setup(request)
    command = publish_request(q, confirmed(q, dsn))
    publication = q.seed.success("publish", command, dsn)
    bad = copy.deepcopy(command)
    raw = None
    if attack in ("bool_revision", "float_revision"):
        mapping(bad["snapshot_ref"])["revision"] = True if attack == "bool_revision" else 1.0
    elif attack == "uuid_uppercase":
        bad["owner_id"] = str(bad["owner_id"]).upper()
    elif attack == "duplicate":
        raw = canonical(command)[:-1] + b',"schema_version":1}'
    elif attack == "nested_duplicate":
        raw = canonical(command).replace(
            b'"kind":"candidate-snapshot"',
            b'"kind":"candidate-snapshot","kind":"candidate-snapshot"',
        )
        assert raw != canonical(command)
    elif attack in ("nul", "surrogate"):
        bad["owner_id"] = "\x00" if attack == "nul" else "\ud800"
        raw = json.dumps(bad, ensure_ascii=True).encode()
    elif attack == "nan":
        raw = canonical(command).replace(b'"schema_version":1', b'"schema_version":NaN')
    else:
        raw = b'{"padding":"' + b"x" * 1048577 + b'"}'
    before = ledger(url, q.seed.owner)
    q.seed.denied("publish", bad, dsn, raw=raw)
    assert ledger(url, q.seed.owner) == before
    assert q.seed.success("publish", command, dsn) == publication


@pytest.mark.parametrize("same_command", [False, True])
def test_real_pg_observed_overlap_atomic_cas(
    request: pytest.FixtureRequest, same_command: bool
) -> None:
    q, url, dsn = setup(request)
    confirmation = confirmed(q, dsn)
    first = publish_request(q, confirmation)
    second = first if same_command else publish_request(q, confirmation)
    children: list[subprocess.Popen[str]] = []
    before = ledger(url, q.seed.owner)
    try:
        with connect_test_database(url) as blocker:
            pid_row = blocker.execute("SELECT pg_backend_pid()").fetchone()
            assert pid_row is not None
            pid = pid_row[0]
            blocker.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"owner:{q.seed.owner}",)
            )
            for command in (first, second):
                children.append(
                    subprocess.Popen(
                        q.seed.command("publish", command),
                        cwd=q.seed.directory,
                        env=q.seed.environment(dsn),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                )
            deadline = time.monotonic() + 10
            observed = False
            with connect_test_database(url, autocommit=True) as observer:
                while time.monotonic() < deadline:
                    rows = observer.execute(
                        "SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND %s = ANY(pg_blocking_pids(pid))",
                        (pid,),
                    ).fetchall()
                    if len(rows) == 2:
                        observed = True
                        break
                    assert all(child.poll() is None for child in children), (
                        "writer exited before observed overlap"
                    )
                    time.sleep(0.02)
            assert observed, "two real PostgreSQL writers never overlapped at the owner lock"
            assert ledger(url, q.seed.owner) == before
            blocker.commit()
        outputs = []
        for child in children:
            out, err = child.communicate(timeout=25)
            outputs.append((child.returncode, out, err))
        if same_command:
            assert [code for code, _, _ in outputs] == [0, 0]
            assert strict_json(outputs[0][1]) == strict_json(outputs[1][1])
        else:
            assert sorted(code for code, _, _ in outputs) == [0, 2]
            loser = next(err for code, _, err in outputs if code == 2)
            assert strict_json(loser)["status"] == "BLOCKED"
        winner = strict_json(next(out for code, out, _ in outputs if code == 0))
        assert_publication(q, winner)
        with connect_test_database(url) as connection:
            assert connection.execute(
                "SELECT count(*) FROM catalog_record WHERE owner_id=%s AND kind='catalog-publication'",
                (q.seed.owner,),
            ).fetchone() == (1,)
            assert connection.execute(
                "SELECT generation FROM catalog_publication_head WHERE owner_id=%s", (q.seed.owner,)
            ).fetchone() == (cast(int, q.selection["expected_head_generation"]) + 1,)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


@pytest.mark.parametrize("attack", ["writable", "bytes"])
def test_replay_and_readback_revalidate_real_material(
    request: pytest.FixtureRequest, attack: str
) -> None:
    q, url, dsn = setup(request)
    command = publish_request(q, confirmed(q, dsn))
    published = q.seed.success("publish", command, dsn)
    before = ledger(url, q.seed.owner)
    files = list((q.seed.root / "candidates").rglob("SKILL.md"))
    assert len(files) == 1 and not files[0].is_symlink()
    path = files[0]
    assert path.stat().st_mode & 0o222 == 0
    path.chmod(0o600)
    if attack == "bytes":
        path.write_bytes(path.read_bytes() + b"\nB06b actual retained material tamper.\n")
        path.chmod(0o400)
    q.seed.denied("publish", command, dsn)
    q.seed.denied("readback", q.seed.request(publication_ref=published["publication_ref"]), dsn)
    assert ledger(url, q.seed.owner) == before


class Catalog(Protocol):
    async def dispatch(self, operation: str, request: object) -> dict[str, object]: ...


class Factory(Protocol):
    def __call__(self, engine: AsyncEngine, root: Path) -> Catalog: ...


def test_software_precommit_failure_rolls_back_and_lost_response_replays(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, url, dsn = setup(request)
    command = publish_request(q, confirmed(q, dsn))
    module = importlib.import_module("omnis.modules.settings.catalog_publication")
    store = importlib.import_module("omnis.modules.settings.candidate_store")
    db = importlib.import_module("omnis.core.db")
    errors = importlib.import_module("omnis.modules.settings.catalog_models")
    factory = cast(Factory, module.PublicationCatalog)
    before = ledger(url, q.seed.owner)
    writes_observed = False
    original = store.complete

    async def cut(*args: object, **kwargs: object) -> None:
        nonlocal writes_observed
        await original(*args, **kwargs)
        connection = cast(AsyncConnection, args[0])
        count = await connection.scalar(
            text(
                "SELECT count(*) FROM catalog_record WHERE owner_id=:owner AND kind='catalog-publication'"
            ),
            {"owner": q.seed.owner},
        )
        assert count == 1, "fault fired without actual publication insertion"
        generation = await connection.scalar(
            text("SELECT generation FROM catalog_publication_head WHERE owner_id=:owner"),
            {"owner": q.seed.owner},
        )
        assert generation == cast(int, q.selection["expected_head_generation"]) + 1
        writes_observed = True
        raise errors.CatalogError("INJECTED_TEST_PRECOMMIT")

    async def execute(discard_response: bool = False) -> dict[str, object]:
        engine = cast(AsyncEngine, db.database_engine(dsn))
        try:
            result = await factory(engine, q.seed.root).dispatch("publish", command)
            if discard_response:
                raise RuntimeError("INJECTED_SOFTWARE_RESPONSE_DISCARD_AFTER_COMMIT")
            return result
        finally:
            await engine.dispose()

    with monkeypatch.context() as patch:
        patch.setattr(store, "complete", cut)
        with pytest.raises(errors.CatalogError, match="INJECTED_TEST_PRECOMMIT"):
            asyncio.run(execute())
    assert writes_observed, "fault did not reach real post-write/precommit boundary"
    assert ledger(url, q.seed.owner) == before

    # Software consumer response discard AFTER dispatch returned/committed, not
    # a physical server ACK loss or power-cut claim.
    with pytest.raises(RuntimeError, match="INJECTED_SOFTWARE_RESPONSE_DISCARD_AFTER_COMMIT"):
        asyncio.run(execute(discard_response=True))
    state_after_discard = ledger(url, q.seed.owner)
    assert state_after_discard != before
    committed = q.seed.success("publish", command, dsn)
    assert_publication(q, committed)
    assert ledger(url, q.seed.owner) == state_after_discard
    assert q.seed.success("publish", command, dsn) == committed
    back = q.seed.success(
        "readback", q.seed.request(publication_ref=committed["publication_ref"]), dsn
    )
    assert back["publication"] == committed["publication"]


def test_service_dispatch_cannot_mint_operator_confirmation(request: pytest.FixtureRequest) -> None:
    q, url, dsn = setup(request)
    module = importlib.import_module("omnis.modules.settings.catalog_publication")
    db = importlib.import_module("omnis.core.db")
    errors = importlib.import_module("omnis.modules.settings.catalog_models")
    factory = cast(Factory, module.PublicationCatalog)
    before = ledger(url, q.seed.owner)

    async def attempt() -> None:
        engine = cast(AsyncEngine, db.database_engine(dsn))
        try:
            with pytest.raises(errors.CatalogError, match="^OPERATOR_CONFIRMATION_REQUIRED$"):
                await factory(engine, q.seed.root).dispatch("confirm", q.seed.write(**q.selection))
        finally:
            await engine.dispose()

    asyncio.run(attempt())
    assert ledger(url, q.seed.owner) == before


def test_reviewer_profile_refused_before_confirmation_and_publication(
    request: pytest.FixtureRequest,
) -> None:
    require_consumer()
    url = cast(URL, request.getfixturevalue("migrated_database_url"))
    dsn = url.render_as_string(hide_password=False)
    seed = new_seed()
    profile = strict_json(seed.profile.read_text())
    mapping(sequence(profile["agent_recipes"])[0])["role"] = "REVIEWER"
    seed.profile.write_bytes(canonical(profile))
    q = qualify(seed, dsn)
    before = ledger(url, seed.owner)
    result, transcript = seed.confirm(seed.write(**q.selection), dsn)
    assert result.returncode == 2 and result.stdout == ""
    assert strict_json(transcript.strip()) == {
        "status": "BLOCKED",
        "reason": "REVIEWER_NOT_SUPPORTED",
    }
    # Invalid role is refused before even resolving a confirmation receipt.
    seed.denied(
        "publish",
        seed.write(
            **q.selection,
            confirmation_ref={
                "kind": "operator-confirmation",
                "id": str(uuid4()),
                "revision": 1,
                "digest": "0" * 64,
            },
        ),
        dsn,
        "REVIEWER_NOT_SUPPORTED",
    )
    assert ledger(url, seed.owner) == before
