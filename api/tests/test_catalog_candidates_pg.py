"""Independent real-PG ledger/readback controls on the bounded service interface.

No SQLite, expected-result repository doubles, provisioning, or release publish.
Availability assertion precedes the inherited attested/migrated fixture.
"""

import importlib
from pathlib import Path
from typing import Protocol, cast

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from fixtures.b06a.consumer import mapping, sequence
from fixtures.b06a_durable.consumer import (
    copy_seed,
    envelope,
    exact_ref,
    freeze,
    material_digest,
    readback,
    require_consumer,
    scratch_directory,
)
from omnis.core.db import database_engine


class Catalog(Protocol):
    async def dispatch(self, operation: str, request: object) -> dict[str, object]: ...


class CatalogFactory(Protocol):
    def __call__(self, engine: AsyncEngine, root: Path) -> Catalog: ...


def catalog_factory() -> CatalogFactory:
    require_consumer()
    module = importlib.import_module("omnis.modules.settings.candidate_catalog")
    return cast(CatalogFactory, module.CandidateCatalog)


@pytest.mark.asyncio
async def test_replay_rejected_reservations_never_rebind(request: pytest.FixtureRequest) -> None:
    factory = catalog_factory()
    url: URL = request.getfixturevalue("migrated_database_url")
    seed = copy_seed(scratch_directory() / "reservation-ledger")
    engine = database_engine(url.render_as_string(hide_password=False))
    service = factory(engine, seed.catalog_root)
    captured_request = seed.capture_request()
    try:
        captured = await service.dispatch("capture", captured_request)
        assert captured["material_digest"] == material_digest((seed.package,), seed.profile)
        assert await service.dispatch("capture", captured_request) == captured
        source_refs = {
            "draft_ref": captured["draft_ref"],
            "source_draft_refs": captured["source_draft_refs"],
        }
        review_request = seed.write_request(**source_refs)
        review = await service.dispatch("review", review_request)
        assert await service.dispatch("review", review_request) == review
        assert sequence(review["candidate_refs"])
        async with engine.connect() as connection:
            before = (
                await connection.execute(
                    text(
                        "SELECT id, revision, digest, draft_id FROM catalog_reservation ORDER BY id, revision"
                    )
                )
            ).all()
            records = (
                (await connection.execute(text("SELECT envelope FROM catalog_record")))
                .scalars()
                .all()
            )
        assert before
        for record in records:
            obj = mapping(record)
            envelope(obj, {key: obj[key] for key in ("kind", "id", "revision", "digest")})
        rejected_request = seed.write_request(**source_refs)
        rejected = await service.dispatch("reject", rejected_request)
        assert rejected["state"] == "REJECTED"
        assert await service.dispatch("reject", rejected_request) == rejected
        notice = seed.package / "NOTICE.md"
        notice.write_bytes(notice.read_bytes() + b"\nindependent reservation revision probe\n")
        changed_request = seed.capture_request()
        changed = await service.dispatch("capture", changed_request)
        assert changed["material_digest"] != captured["material_digest"]
        changed_review = await service.dispatch(
            "review",
            seed.write_request(
                draft_ref=changed["draft_ref"], source_draft_refs=changed["source_draft_refs"]
            ),
        )
        assert sequence(changed_review["candidate_refs"])
        async with engine.connect() as connection:
            after = (
                await connection.execute(
                    text(
                        "SELECT id, revision, digest, draft_id FROM catalog_reservation ORDER BY id, revision"
                    )
                )
            ).all()
        assert all(row in after for row in before), "rejected reservations were removed/rebound"
        for old in before:
            same_identity = [row for row in after if row.id == old.id]
            assert [row for row in same_identity if row.revision == old.revision] == [old]
        old_digests = {row.id: row.digest for row in before}
        revised = [
            row for row in after if row.id in old_digests and row.digest != old_digests[row.id]
        ]
        assert revised and all(row.revision > 1 for row in revised)
        # Readback in a fresh CLI process proves original replay ignores edited workspace.
        assert seed.success(
            "capture", captured_request, url.render_as_string(hide_password=False)
        ) == (captured)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "table", ["catalog_record", "catalog_identity", "catalog_reservation", "catalog_command"]
)
async def test_catalog_rows_immutable_under_real_sql(
    request: pytest.FixtureRequest, table: str
) -> None:
    require_consumer()
    url: URL = request.getfixturevalue("migrated_database_url")
    seed = copy_seed(scratch_directory() / "immutable-ledger")
    database_url = url.render_as_string(hide_password=False)
    frozen = freeze(seed, database_url)
    before = readback(seed, database_url, frozen)
    engine = database_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = (
                (await connection.execute(text(f"SELECT to_jsonb(t) FROM {table} t")))
                .scalars()
                .all()
            )
        assert rows, "immutable oracle requires a real persisted positive row"
        # No-op UPDATE is still forbidden. Every attempt gets its own rolled-back transaction.
        column = "owner_id" if table == "catalog_command" else "id"
        for sql in (f"UPDATE {table} SET {column}={column}", f"DELETE FROM {table}"):
            with pytest.raises(DBAPIError) as caught:
                async with engine.begin() as connection:
                    await connection.execute(text(sql))
            assert getattr(caught.value.orig, "sqlstate", None) == "P0001"
        async with engine.connect() as connection:
            after = (
                (await connection.execute(text(f"SELECT to_jsonb(t) FROM {table} t")))
                .scalars()
                .all()
            )
        assert sorted(map(str, after)) == sorted(map(str, rows))
        assert readback(seed, database_url, frozen) == before
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("attack", "reason"),
    [("writable", "FROZEN_MATERIAL_WRITABLE"), ("bytes", "FROZEN_MATERIAL_MISMATCH")],
)
def test_readback_refuses_actual_frozen_tamper(
    request: pytest.FixtureRequest, attack: str, reason: str
) -> None:
    require_consumer()
    url: URL = request.getfixturevalue("migrated_database_url")
    seed = copy_seed(scratch_directory() / "frozen-tamper")
    database_url = url.render_as_string(hide_password=False)
    frozen = freeze(seed, database_url)
    readback(seed, database_url, frozen)  # Same real consumer positive before the negative.
    ref = exact_ref(frozen["snapshot_ref"])
    # Inspect the concrete finalized namespace; do not infer layout from snapshot IDs.
    root = seed.catalog_root / "candidates"
    files = [path for path in root.rglob("SKILL.md") if path.is_file()]
    assert len(files) == 1 and not files[0].is_symlink()
    path = files[0]
    original = path.read_bytes()
    assert path.stat().st_mode & 0o222 == 0
    path.chmod(0o600)
    if attack == "bytes":
        path.write_bytes(original + b"\nfrozen byte tamper\n")
        path.chmod(0o400)  # Reach digest mismatch, not the preceding mode guard.
    seed.denied("readback", seed.request(snapshot_ref=ref), database_url, reason)
    # Keep tampered bytes: evidence, not automatic adoption/repair of material.


@pytest.mark.parametrize(
    ("attack", "reason"),
    [
        ("missing_source", "SOURCE_DRAFT_MISMATCH"),
        ("duplicate_source", "SOURCE_DRAFT_MISMATCH"),
        ("foreign_owner", "REF_UNAVAILABLE"),
        ("digest", "REF_MISMATCH"),
        ("kind", "REF_MISMATCH"),
        ("revision", "REF_MISMATCH"),
        ("bool_revision", "INVALID_REQUEST"),
        ("float_revision", "INVALID_REQUEST"),
    ],
)
def test_review_exact_ref_denials_same_cli(
    request: pytest.FixtureRequest, attack: str, reason: str
) -> None:
    require_consumer()
    url: URL = request.getfixturevalue("migrated_database_url")
    seed = copy_seed(scratch_directory() / "ref-denials")
    database_url = url.render_as_string(hide_password=False)
    captured = seed.success("capture", seed.capture_request(), database_url)
    valid = seed.write_request(
        draft_ref=captured["draft_ref"], source_draft_refs=captured["source_draft_refs"]
    )
    positive = seed.success("review", valid, database_url)
    assert positive["status"] == "STATIC_PASS"
    import copy
    from uuid import uuid4

    invalid = copy.deepcopy(valid)
    invalid["command_id"] = str(uuid4())
    ref = mapping(invalid["draft_ref"])
    sources = sequence(invalid["source_draft_refs"])
    if attack == "missing_source":
        sources = [source for source in sources if source == ref]
    elif attack == "duplicate_source":
        sources.append(copy.deepcopy(sources[0]))
    elif attack == "foreign_owner":
        invalid["owner_id"] = str(uuid4())
    else:
        changed = {
            "digest": "0" * 64,
            "kind": "technical-review",
            "revision": 2,
            "bool_revision": True,
            "float_revision": 1.0,
        }
        field = "revision" if attack in {"bool_revision", "float_revision"} else attack
        ref[field] = changed[attack]
    invalid["draft_ref"] = ref
    invalid["source_draft_refs"] = sources
    seed.denied("review", invalid, database_url, reason)
    assert seed.success("review", valid, database_url) == positive


def test_observed_overlapping_capture_transactions(request: pytest.FixtureRequest) -> None:
    """Observe product advisory-xact lock ownership/waiter, not sequential replay.

    The current product uses advisory locks, not row locks. This test proves that
    concrete boundary only; row-lock/CAS/crash coverage remains separate NOT_RUN.
    """
    import asyncio
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import event
    from sqlalchemy.engine import Connection

    from conftest import connect_test_database

    factory = catalog_factory()
    url: URL = request.getfixturevalue("migrated_database_url")
    seed = copy_seed(scratch_directory() / "concurrent-capture")
    database_url = url.render_as_string(hide_password=False)
    seed.success("capture", seed.capture_request(), database_url)  # Real same-consumer positive.
    command = seed.capture_request()
    locked = threading.Event()
    release = threading.Event()
    backend: list[int] = []

    def worker(pause: bool) -> dict[str, object]:
        async def run() -> dict[str, object]:
            engine = database_engine(database_url)

            def after_lock(
                connection: Connection,
                cursor: object,
                statement: str,
                parameters: object,
                context: object,
                executemany: bool,
            ) -> None:
                if "pg_advisory_xact_lock" not in statement or locked.is_set():
                    return
                backend.append(
                    cast(int, connection.execute(text("SELECT pg_backend_pid()")).scalar_one())
                )
                locked.set()  # Actual product transaction has acquired its DB lock.
                assert release.wait(5), "bounded observer did not release product writer"

            if pause:
                event.listen(engine.sync_engine, "after_cursor_execute", after_lock)
            try:
                return await factory(engine, seed.catalog_root).dispatch("capture", command)
            finally:
                await engine.dispose()

        return asyncio.run(run())

    # Attest/connect before pausing writers: attestation must not consume their lock timeout.
    with (
        connect_test_database(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        first = pool.submit(worker, True)
        second = None
        try:
            assert locked.wait(5), "product did not reach the known advisory lock boundary"
            second = pool.submit(worker, False)
            until = time.monotonic() + 1
            observed = False
            while time.monotonic() < until:
                row = observer.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>%s AND %s=ANY(pg_blocking_pids(pid)))",
                    (backend[0], backend[0]),
                ).fetchone()
                assert row is not None
                if row[0] is True:
                    observed = True
                    break
                time.sleep(0.01)
            assert observed, "no real overlapping product lock waiter was observed"
        finally:
            release.set()
            # Both actual worker engines settle even when the observer assertion fails.
            first_result = first.result(timeout=20)
            second_result = None if second is None else second.result(timeout=20)
        assert second_result == first_result
    with connect_test_database(url, autocommit=True) as observer:
        row = observer.execute(
            "SELECT count(*) FROM catalog_command WHERE owner_id=%s AND command_id=%s",
            (seed.owner_id, command["command_id"]),
        ).fetchone()
        assert row == (1,), "concurrent command replay created duplicate durable commands"
    assert seed.success("capture", command, database_url) == first_result
