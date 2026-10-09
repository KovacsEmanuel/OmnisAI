"""Real PG/CLI PURE consumer contract, acquired only after feature availability.

Accepted C01 source/consumer is reused read-only. Faults are labeled software
seams, and concurrency requires observed pg_blocking_pids, never a timing guess.
"""

import asyncio
import copy
import importlib
import json
import subprocess
import time
from dataclasses import dataclass
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
    sequence,
    strict_json,
)
from fixtures.b06b_pure_probe.consumer import (
    ACTUAL_INPUT,
    MODULE,
    RECIPE,
    Probe,
    assert_readback,
    assert_receipt,
    assert_selection,
    probe_executor_revision,
    require_consumer,
)


@dataclass(frozen=True)
class Published:
    qualified: Qualified
    probe: Probe
    url: URL
    snapshot: dict[str, object]

    @property
    def dsn(self) -> str:
        return self.url.render_as_string(hide_password=False)

    @property
    def executor_revision(self) -> str:
        body = envelope(self.qualified.pure["evaluation"], self.qualified.pure["evaluation_ref"])
        revision = body["evaluator_revision"]
        assert type(revision) is str
        return probe_executor_revision(revision)

    def select_request(self) -> dict[str, object]:
        return self.probe.write(snapshot_ref=self.snapshot["snapshot_ref"], recipe_key=RECIPE)

    def selected(self) -> tuple[dict[str, object], dict[str, object]]:
        command = self.select_request()
        result = self.probe.success("select", command, self.dsn)
        assert_selection(result, self.snapshot)
        return command, result

    def execute_request(self, selection: dict[str, object]) -> dict[str, object]:
        return self.probe.write(selection_ref=selection["selection_ref"], input=ACTUAL_INPUT)


def setup(request: pytest.FixtureRequest) -> Published:
    require_consumer()
    url = cast(URL, request.getfixturevalue("migrated_database_url"))
    dsn = url.render_as_string(hide_password=False)
    seed = new_seed()
    q = qualify(seed, dsn)
    publication = seed.success("publish", publish_request(q, confirmed(q, dsn)), dsn)
    snapshot = seed.success(
        "snapshot", seed.write(publication_ref=publication["publication_ref"]), dsn
    )
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    return Published(q, probe, url, snapshot)


def ledger(url: URL) -> bytes:
    with connect_test_database(url) as connection:
        state = {}
        for table in (
            "catalog_record",
            "catalog_command",
            "catalog_publication_head",
            "catalog_identity",
            "catalog_reservation",
        ):
            rows = connection.execute(
                f"SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text"
            ).fetchall()
            state[table] = [row[0] for row in rows]
    return canonical(state)


def test_new_input_executes_real_pure_and_fresh_cli_replays_readback(
    request: pytest.FixtureRequest,
) -> None:
    p = setup(request)
    select_command, selected = p.selected()
    before_execute = ledger(p.url)
    assert p.probe.success("select", select_command, p.dsn) == selected
    assert ledger(p.url) == before_execute
    with connect_test_database(p.url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM catalog_record WHERE owner_id=%s AND kind='execution-selection'",
            (p.probe.owner,),
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM catalog_record WHERE owner_id=%s AND kind='pure-probe-receipt'",
            (p.probe.owner,),
        ).fetchone() == (0,)
    command = p.execute_request(selected)
    result = p.probe.success("execute", command, p.dsn)
    body = assert_receipt(result, selected, p.executor_revision)
    qualification = envelope(p.qualified.pure["evaluation"], p.qualified.pure["evaluation_ref"])
    old_outputs = [json.loads(str(raw)) for raw in sequence(qualification["outputs"])]
    assert [mapping(item)["output"] for item in sequence(body["outputs"])] != old_outputs
    committed = ledger(p.url)
    assert committed != before_execute
    assert p.probe.success("execute", command, p.dsn) == result
    read = p.probe.request(receipt_ref=result["receipt_ref"])
    back = p.probe.success("readback", read, p.dsn)
    assert_readback(back, result, selected)
    assert p.probe.success("readback", read, p.dsn) == back
    assert ledger(p.url) == committed


def test_select_denies_owner_snapshot_recipe_and_model_overrides(
    request: pytest.FixtureRequest,
) -> None:
    p = setup(request)
    good = p.select_request()
    attacks = [
        {**good, "owner_id": str(uuid4())},
        {**good, "recipe_key": "unpublished-recipe"},
        {**good, "snapshot_ref": p.qualified.frozen["snapshot_ref"]},
    ]
    for field, value in (("id", str(uuid4())), ("digest", "0" * 64), ("revision", 2)):
        attacks.append({**good, "snapshot_ref": {**mapping(good["snapshot_ref"]), field: value}})
    for field, override in (
        ("model_key", "unauthorized-model"),
        ("effective", {"model_key": "unauthorized-model"}),
        ("requested", {"requirement": "REQUIRED"}),
        ("resolution", "MODEL"),
        ("execution_preference", {"on_unavailable": "USE_RUN_DEFAULT"}),
    ):
        attacks.append({**good, field: override})
    before = ledger(p.url)
    for bad in attacks:
        p.probe.denied("select", bad, p.dsn)
        assert ledger(p.url) == before
    assert_selection(p.probe.success("select", good, p.dsn), p.snapshot)


def test_execute_readback_denials_and_replay_conflict_leave_success_unchanged(
    request: pytest.FixtureRequest,
) -> None:
    p = setup(request)
    _, selected = p.selected()
    good = p.execute_request(selected)
    result = p.probe.success("execute", good, p.dsn)
    before = ledger(p.url)
    attacks = [
        {**good, "owner_id": str(uuid4())},
        {**good, "input": None},
        {**good, "input": []},
        {**good, "selection_ref": p.snapshot["snapshot_ref"]},
        {**good, "model_key": "unauthorized-model"},
        {**good, "effective": None},
        {**good, "requested": {}},
        {**good, "recipe_key": RECIPE},
    ]
    for field, value in (("id", str(uuid4())), ("digest", "0" * 64), ("revision", 2)):
        attacks.append({**good, "selection_ref": {**mapping(good["selection_ref"]), field: value}})
    for bad in attacks:
        for attempt in (bad, {**bad, "command_id": str(uuid4())}):
            p.probe.denied("execute", attempt, p.dsn)
            assert ledger(p.url) == before
    p.probe.denied("execute", {**good, "input": {"capture": "[]"}}, p.dsn, "COMMAND_CONFLICT")
    duplicate = canonical(good).replace(b'"input":{', b'"input":{"capture":"[]",', 1)
    p.probe.denied("execute", good, p.dsn, raw=duplicate)
    assert ledger(p.url) == before
    read = p.probe.request(receipt_ref=result["receipt_ref"])
    for bad in (
        {**read, "owner_id": str(uuid4())},
        {**read, "receipt_ref": selected["selection_ref"]},
        {**read, "receipt_ref": {**mapping(read["receipt_ref"]), "digest": "0" * 64}},
    ):
        p.probe.denied("readback", bad, p.dsn)
        assert ledger(p.url) == before
    assert p.probe.success("execute", good, p.dsn) == result
    assert_readback(p.probe.success("readback", read, p.dsn), result, selected)


def test_strict_schema_and_wire_validation_precedes_existing_replay(
    request: pytest.FixtureRequest,
) -> None:
    p = setup(request)
    select_command, selected = p.selected()
    execute_command = p.execute_request(selected)
    result = p.probe.success("execute", execute_command, p.dsn)
    before = ledger(p.url)
    for operation, good, ref_field in (
        ("select", select_command, "snapshot_ref"),
        ("execute", execute_command, "selection_ref"),
        ("readback", p.probe.request(receipt_ref=result["receipt_ref"]), "receipt_ref"),
    ):
        attacks: list[tuple[dict[str, object], str]] = []
        for value in (True, 1.0, "1", None, 0, 2):
            reason = "INVALID_JSON" if type(value) is float else "INVALID_REQUEST"
            attacks.append(({**good, "schema_version": value}, reason))
        for value in (True, 1.0, "1"):
            reason = "INVALID_JSON" if type(value) is float else "INVALID_REQUEST"
            attacks.append(
                ({**good, ref_field: {**mapping(good[ref_field]), "revision": value}}, reason)
            )
        for bad, reason in attacks:
            # COMMAND_CONFLICT would prove replay ran before strict validation.
            p.probe.denied(operation, bad, p.dsn, reason)
            assert ledger(p.url) == before
        duplicate = canonical(good)[:-1] + b',"schema_version":1}'
        p.probe.denied(operation, good, p.dsn, raw=duplicate)
        assert ledger(p.url) == before
    assert p.probe.success("select", select_command, p.dsn) == selected
    assert p.probe.success("execute", execute_command, p.dsn) == result


def test_bad_input_fails_without_partial_input_or_receipt(request: pytest.FixtureRequest) -> None:
    p = setup(request)
    _, selected = p.selected()
    good = p.execute_request(selected)
    before = ledger(p.url)
    invalid_inputs: tuple[object, ...] = (
        None,
        [],
        {},
        {"capture": 7},
        {"capture": "not-json"},
        {"capture": "{}"},
        {"capture": "[]", "extra": True},
        {"capture": "\x00"},
    )
    for value in invalid_inputs:
        p.probe.denied("execute", {**good, "input": value}, p.dsn)
        assert ledger(p.url) == before
    duplicate = canonical(good).replace(b'"input":{', b'"input":{"capture":"[]",', 1)
    assert duplicate != canonical(good)
    p.probe.denied("execute", good, p.dsn, raw=duplicate)
    assert ledger(p.url) == before
    assert_receipt(p.probe.success("execute", good, p.dsn), selected, p.executor_revision)


@pytest.mark.parametrize("attack", ["writable", "bytes"])
def test_mutated_retained_material_refuses_selection_execution_replay_and_readback(
    request: pytest.FixtureRequest,
    attack: str,
) -> None:
    p = setup(request)
    select_command, selected = p.selected()
    execute_command = p.execute_request(selected)
    result = p.probe.success("execute", execute_command, p.dsn)
    before = ledger(p.url)
    paths = list((p.probe.root / "candidates").rglob("SKILL.md"))
    assert len(paths) == 1 and not paths[0].is_symlink()
    path = paths[0]
    assert path.stat().st_mode & 0o222 == 0
    path.chmod(0o600)
    if attack == "bytes":
        path.write_bytes(path.read_bytes() + b"\nB06b PURE retained material tamper.\n")
        path.chmod(0o400)
    for operation, command in (
        ("select", select_command),
        ("select", p.select_request()),
        ("execute", execute_command),
        ("execute", p.execute_request(selected)),
        ("readback", p.probe.request(receipt_ref=result["receipt_ref"])),
    ):
        p.probe.denied(operation, command, p.dsn)
        assert ledger(p.url) == before


@pytest.mark.parametrize("conflicting_input", [False, True])
def test_real_pg_writers_overlap_then_one_atomic_receipt(
    request: pytest.FixtureRequest,
    conflicting_input: bool,
) -> None:
    p = setup(request)
    _, selected = p.selected()
    first = p.execute_request(selected)
    second = copy.deepcopy(first)
    if conflicting_input:
        second["input"] = {"capture": "[]"}
    children: list[subprocess.Popen[str]] = []
    before = ledger(p.url)
    try:
        with connect_test_database(p.url) as blocker:
            row = blocker.execute("SELECT pg_backend_pid()").fetchone()
            assert row is not None
            blocker.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"owner:{p.probe.owner}",)
            )
            for command in (first, second):
                children.append(
                    subprocess.Popen(
                        p.probe.command("execute", command),
                        cwd=p.probe.directory,
                        env=p.probe.environment(p.dsn),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                )
            deadline = time.monotonic() + 10
            observed = False
            with connect_test_database(p.url, autocommit=True) as observer:
                while time.monotonic() < deadline:
                    rows = observer.execute(
                        "SELECT pid FROM pg_stat_activity WHERE datname=current_database() "
                        "AND %s = ANY(pg_blocking_pids(pid))",
                        (row[0],),
                    ).fetchall()
                    if len(rows) == 2:
                        observed = True
                        break
                    assert all(child.poll() is None for child in children), "early writer exit"
                    time.sleep(0.02)  # Poll interval only; observed PG blocking is the oracle.
            assert observed, "two actual execute transactions never overlapped at owner lock"
            assert ledger(p.url) == before
            blocker.commit()
        outputs = []
        for child in children:
            out, err = child.communicate(timeout=25)
            outputs.append((child.returncode, out, err))
        assert sorted(code for code, _, _ in outputs) == ([0, 2] if conflicting_input else [0, 0])
        winner_index = next(i for i, (code, _, _) in enumerate(outputs) if code == 0)
        winner = strict_json(outputs[winner_index][1])
        for code, out, err in outputs:
            if code == 0:
                assert err == "" and strict_json(out) == winner
            else:
                assert out == ""
                assert strict_json(err) == {"status": "BLOCKED", "reason": "COMMAND_CONFLICT"}
        command = (first, second)[winner_index]
        assert p.probe.success("execute", command, p.dsn) == winner
        back = p.probe.success(
            "readback", p.probe.request(receipt_ref=winner["receipt_ref"]), p.dsn
        )
        assert back["receipt"] == winner["receipt"]
        assert envelope(back["input"], back["input_ref"])["input"] == command["input"]
        with connect_test_database(p.url) as connection:
            assert connection.execute(
                "SELECT count(*) FROM catalog_record WHERE owner_id=%s AND kind='pure-probe-receipt'",
                (p.probe.owner,),
            ).fetchone() == (1,)
            assert connection.execute(
                "SELECT count(*) FROM catalog_command WHERE owner_id=%s AND command_id=%s",
                (p.probe.owner, first["command_id"]),
            ).fetchone() == (1,)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


class Catalog(Protocol):
    async def dispatch(self, operation: str, request: object) -> dict[str, object]: ...


class Factory(Protocol):
    def __call__(self, engine: AsyncEngine, root: Path) -> Catalog: ...


async def dispatch(p: Published, operation: str, command: dict[str, object]) -> dict[str, object]:
    module = importlib.import_module(MODULE)
    db = importlib.import_module("omnis.core.db")
    factory = cast(Factory, module.PureProbe)
    engine = cast(AsyncEngine, db.database_engine(p.dsn))
    try:
        return await factory(engine, p.probe.root).dispatch(operation, command)
    finally:
        await engine.dispose()


def test_successful_replay_and_readback_never_rerun_executor(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = setup(request)
    _, selected = p.selected()
    command = p.execute_request(selected)
    result = p.probe.success("execute", command, p.dsn)  # Real positive: no patched evaluator.
    assert_receipt(result, selected, p.executor_revision)
    before = ledger(p.url)
    module = importlib.import_module(MODULE)
    attempts: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        attempts.append("evaluate_pure")
        raise AssertionError("successful execution must not be evaluated again")

    with monkeypatch.context() as patch:
        patch.setattr(module, "evaluate_pure", forbidden)
        assert asyncio.run(dispatch(p, "execute", command)) == result
        back = asyncio.run(
            dispatch(p, "readback", p.probe.request(receipt_ref=result["receipt_ref"]))
        )
        assert_readback(back, result, selected)
    assert attempts == []
    assert ledger(p.url) == before
    assert p.probe.success("execute", command, p.dsn) == result


def test_software_failure_after_actual_writes_rolls_back_input_receipt_and_command(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = setup(request)
    _, selected = p.selected()  # This committed selection must survive the execution rollback.
    command = p.execute_request(selected)
    store = importlib.import_module("omnis.modules.settings.candidate_store")
    errors = importlib.import_module("omnis.modules.settings.catalog_models")
    original = store.complete
    before = ledger(p.url)
    observed = False

    async def cut(*args: object, **kwargs: object) -> None:
        nonlocal observed
        await original(*args, **kwargs)
        connection = cast(AsyncConnection, args[0])
        result = mapping(args[5])
        receipt = envelope(result["receipt"], result["receipt_ref"])
        for ref in (result["receipt_ref"], receipt["input_ref"]):
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM catalog_record WHERE owner_id=:owner AND id=:id"),
                    {"owner": p.probe.owner, "id": mapping(ref)["id"]},
                )
                == 1
            )
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM catalog_command WHERE owner_id=:owner AND command_id=:id"
                ),
                {"owner": p.probe.owner, "id": command["command_id"]},
            )
            == 1
        )
        observed = True
        raise errors.CatalogError("INJECTED_TEST_PRECOMMIT")

    with monkeypatch.context() as patch:
        patch.setattr(store, "complete", cut)
        with pytest.raises(errors.CatalogError, match="^INJECTED_TEST_PRECOMMIT$"):
            asyncio.run(dispatch(p, "execute", command))
    assert observed, "software fault did not reach actual input+receipt+command writes"
    assert ledger(p.url) == before
    result = p.probe.success("execute", command, p.dsn)
    assert_receipt(result, selected, p.executor_revision)
    assert_readback(
        p.probe.success("readback", p.probe.request(receipt_ref=result["receipt_ref"]), p.dsn),
        result,
        selected,
    )
