"""Observe two real product transactions at their acquired advisory lock.

No replacement locks, DB provisioning or production timeout changes. The second
owner lock in Review is after its immutable reservation transaction committed.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait

from sqlalchemy import event, text
from sqlalchemy.engine import URL, Connection

from conftest import connect_test_database
from fixtures.b06a_durable.consumer import DurableSeed, canonical, exact_ref
from omnis.core.db import database_engine
from omnis.modules.settings.candidate_catalog import CandidateCatalog
from omnis.modules.settings.catalog_models import CatalogError

Outcome = tuple[dict[str, object] | None, str | None]


def ledger(url: URL) -> dict[str, list[bytes]]:
    """Exact immutable rows, preserving unknown fields; never emit the DSN."""
    with connect_test_database(url, autocommit=True) as observer:
        return {
            table: sorted(
                canonical(row[0])
                for row in observer.execute(f"SELECT to_jsonb(t) FROM {table} t").fetchall()
            )
            for table in (
                "catalog_record",
                "catalog_command",
                "catalog_identity",
                "catalog_reservation",
            )
        }


def overlap(
    seed: DurableSeed,
    url: URL,
    first: tuple[str, dict[str, object]],
    second: tuple[str, dict[str, object]],
    *,
    owner_lock_number: int = 1,
) -> tuple[Outcome, Outcome]:
    locked = threading.Event()
    release = threading.Event()
    backend: list[int] = []
    database_url = url.render_as_string(hide_password=False)

    def worker(command: tuple[str, dict[str, object]], pause: bool) -> Outcome:
        async def run() -> Outcome:
            engine = database_engine(database_url)
            acquired = 0

            def after_lock(
                connection: Connection,
                cursor: object,
                statement: str,
                parameters: object,
                context: object,
                executemany: bool,
            ) -> None:
                nonlocal acquired
                if "pg_advisory_xact_lock" not in statement:
                    return
                # Ignore identity locks: we pause only a real owner-lock acquisition.
                if not isinstance(parameters, dict) or parameters.get("key") != (
                    "owner:" + seed.owner_id
                ):
                    return
                acquired += 1
                if acquired != owner_lock_number:
                    return
                pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
                assert type(pid) is int
                backend.append(pid)
                locked.set()
                assert release.wait(5), "bounded observer failed to release writer"

            if pause:
                event.listen(engine.sync_engine, "after_cursor_execute", after_lock)
            try:
                try:
                    return await CandidateCatalog(engine, seed.catalog_root).dispatch(
                        *command
                    ), None
                except CatalogError as error:
                    return None, error.reason
            finally:
                async with asyncio.timeout(5):
                    await engine.dispose()

        return asyncio.run(run())

    # Attestation must finish before the holder starts its bounded pause.
    with (
        connect_test_database(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [pool.submit(worker, first, True)]
        try:
            assert locked.wait(5), "product never acquired the expected advisory lock"
            if owner_lock_number == 2:
                reservation = observer.execute(
                    "SELECT count(*) FROM catalog_reservation r JOIN catalog_identity i ON i.id=r.id "
                    "WHERE i.owner_id=%s AND r.draft_id=%s",
                    (seed.owner_id, exact_ref(first[1]["draft_ref"])["id"]),
                ).fetchone()
                assert reservation is not None
                count = reservation[0]
                assert type(count) is int and count > 0, (
                    "Review reached checker transaction without committed immutable reservations"
                )
            futures.append(pool.submit(worker, second, False))
            until = time.monotonic() + 1.5
            observed = False
            while time.monotonic() < until:
                row = observer.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                    "WHERE datname=current_database() AND pid<>%s "
                    "AND %s=ANY(pg_blocking_pids(pid)))",
                    (backend[0], backend[0]),
                ).fetchone()
                assert row is not None
                if row[0] is True:
                    observed = True
                    break
                time.sleep(0.01)
            assert observed, "no real overlapping advisory-lock waiter observed"
        finally:
            release.set()
            # Settle BOTH engines even if the observer or first result fails.
            _, pending = wait(futures, timeout=20)
            assert not pending, "product worker did not settle within the deadline"
        assert len(futures) == 2
        return futures[0].result(), futures[1].result()
