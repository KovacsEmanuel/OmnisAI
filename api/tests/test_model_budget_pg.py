"""Real PostgreSQL accounting tests. NOT_RUN without the attested parent runner.

Metadata below is explicitly synthetic accounting-only metadata, NOT an admitted
ModelProjection/native binding. No provider, native runtime or send is exercised.
"""

import asyncio
import os
import sys
from uuid import uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.settings.candidate_store import envelope, reference
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import mapping, sequence
from omnis.policy import budgets
from test_model_budget import limits, request, usage

READBACK_SCRIPT = """import asyncio
import os
import sys

from omnis.core.db import database_engine
from omnis.policy.budgets import readback
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks.managed_contract import mapping

async def main():
    engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            result = await readback(conn, sys.argv[1], mapping(load_json(sys.argv[2].encode())))
            print(canonical(result).decode())
    finally:
        await engine.dispose()

asyncio.run(main())
"""


async def seed(engine: AsyncEngine) -> tuple[str, str, dict[str, object], dict[str, object]]:
    owner = str(uuid4())
    scope = envelope("managed-run", {"accounting_test_only": True})
    run = str(scope["id"])
    req = request()
    req["run_or_job_ref"] = reference(scope)
    async with engine.begin() as conn:
        await managed_store.put(conn, owner, run, scope)
        for field in (
            "native_turn_ref",
            "dispatch_owner_ref",
            "provider_config_ref",
            "execution_selection_ref",
            "projection_ref",
        ):
            payload: dict[str, object] = {"accounting_test_only": True}
            if field == "projection_ref":
                payload["projection_digest"] = req["projection_digest"]
            item = envelope(str(mapping(req[field])["kind"]), payload)
            await managed_store.put(conn, owner, run, item)
            req[field] = reference(item)

        budget = await budgets.create_budget(conn, owner, reference(scope), limits())
    return owner, run, req, budget


@pytest.mark.asyncio
async def test_pg_immutable_history_replay_restart_and_ownership(
    migrated_database_url: URL,
) -> None:
    dsn = migrated_database_url.render_as_string(hide_password=False)
    engine = database_engine(dsn)
    try:
        owner, run, req, budget = await seed(engine)
        async with engine.begin() as conn:
            assert (
                await budgets.create_budget(conn, owner, req["run_or_job_ref"], limits()) == budget
            )
            with pytest.raises(CatalogError, match="MODEL_BUDGET_CONFLICT"):
                await budgets.create_budget(
                    conn, owner, req["run_or_job_ref"], {**limits(), "calls": 4}
                )
            dispatch = await budgets.reserve(
                conn, owner, reference(budget), req, trusted_purpose="RECON"
            )
            assert (
                await budgets.reserve(conn, owner, reference(budget), req, trusted_purpose="RECON")
                == dispatch
            )
            with pytest.raises(CatalogError, match="MODEL_ATTEMPT_CONFLICT"):
                await budgets.reserve(
                    conn,
                    owner,
                    reference(budget),
                    {**req, "model_id": "different"},
                    trusted_purpose="RECON",
                )
            before = await budgets.readback(conn, owner, reference(dispatch))
        async with engine.begin() as conn:
            await budgets.mark_sent(conn, owner, reference(dispatch))
        async with engine.begin() as conn:
            with pytest.raises(CatalogError):
                await budgets.mark_sent(conn, owner, reference(dispatch))
            with pytest.raises(CatalogError):
                await budgets.release(conn, owner, reference(dispatch))
            unknown = usage("UNKNOWN", None)
            saved = await budgets.settle(conn, owner, reference(dispatch), unknown)
            assert await budgets.settle(conn, owner, reference(dispatch), unknown) == saved
            with pytest.raises(CatalogError, match="MODEL_RECEIPT_CONFLICT"):
                await budgets.settle(
                    conn,
                    owner,
                    reference(dispatch),
                    {**unknown, "usage_state": "KNOWN", "output_tokens": 1},
                )
        await engine.dispose()
        # New interpreter, not a cached ledger or merely a new connection.
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            READBACK_SCRIPT,
            owner,
            canonical(reference(dispatch)).decode(),
            env={
                **os.environ,
                "OMNIS_DATABASE_URL": dsn,
                "PYTHONPATH": os.pathsep.join(str(p) for p in sys.path),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(child.communicate(), 10)
        finally:
            if child.returncode is None:
                child.kill()
                await child.communicate()
        assert child.returncode == 0, "Fresh accounting readback process failed"
        restarted = mapping(load_json(stdout))
        engine = database_engine(dsn)
        async with engine.begin() as conn:
            resumed = await budgets.readback(conn, owner, reference(dispatch))
            assert restarted == resumed
            assert resumed["state"] == "SENT" and resumed["usage_state"] == "UNKNOWN"
            assert resumed["charged_output_tokens"] == 10
            assert resumed["reservation"] == before["reservation"]
            await budgets.settle(conn, owner, reference(dispatch), usage("PARTIAL", 1))
            await budgets.settle(conn, owner, reference(dispatch), usage("KNOWN", 2))
            final = await budgets.readback(conn, owner, reference(dispatch))
            assert final["state"] == "SETTLED" and final["charged_calls"] == 1
            assert final["charged_output_tokens"] == 2 and len(sequence(final["history"])) == 4
            with pytest.raises(CatalogError):
                await budgets.readback(conn, str(uuid4()), reference(dispatch))
            bad = {**reference(dispatch), "digest": "0" * 64}
            with pytest.raises(CatalogError):
                await budgets.readback(conn, owner, bad)
            req2 = {**req, "dispatch_attempt_id": str(uuid4())}
            second = await budgets.reserve(
                conn, owner, reference(budget), req2, trusted_purpose="RECON"
            )
            await budgets.release(conn, owner, reference(second))
            released = await budgets.readback(conn, owner, reference(second))
            assert released["charged_calls"] == released["charged_output_tokens"] == 0
            with pytest.raises(CatalogError):
                await budgets.mark_sent(conn, owner, reference(second))
        for target in (budget, dispatch, mapping(before["reservation"]), saved):
            for statement in (
                "UPDATE managed_record SET envelope=envelope WHERE id=:id",
                "DELETE FROM managed_record WHERE id=:id",
            ):
                with pytest.raises(DBAPIError):
                    async with engine.begin() as conn:
                        await conn.execute(sql(statement), {"id": target["id"]})
        async with engine.begin() as conn:
            assert await budgets.readback(conn, owner, reference(dispatch)) == final
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["capacity", "duplicate", "conflict", "release-send"])
async def test_pg_overlapping_transactions_are_serialized(
    migrated_database_url: URL, mode: str
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    task = None
    try:
        owner, _, req, budget = await seed(engine)
        ready = asyncio.Event()
        pid = 0

        async def competing() -> dict[str, object]:
            nonlocal pid
            async with engine.begin() as second:
                pid = int((await second.execute(sql("SELECT pg_backend_pid()"))).scalar_one())
                ready.set()
                if mode == "release-send":
                    return await budgets.mark_sent(second, owner, reference(first_dispatch))
                other = {**req}
                if mode == "capacity":
                    other["dispatch_attempt_id"] = str(uuid4())
                elif mode == "conflict":
                    other["model_id"] = "conflicting-attempt"
                return await budgets.reserve(
                    second, owner, reference(budget), other, trusted_purpose="RECON"
                )

        async with engine.begin() as first:
            first_dispatch = await budgets.reserve(
                first, owner, reference(budget), req, trusted_purpose="RECON"
            )
            if mode == "capacity":
                await budgets.reserve(
                    first,
                    owner,
                    reference(budget),
                    {**req, "dispatch_attempt_id": str(uuid4())},
                    trusted_purpose="RECON",
                )
            elif mode == "release-send":
                await budgets.release(first, owner, reference(first_dispatch))
            task = asyncio.create_task(competing())
            await asyncio.wait_for(ready.wait(), 3)
            # Observe a real waiting advisory lock, not a scheduling-only timeout.
            async with asyncio.timeout(3):
                async with engine.begin() as observer:
                    while not (
                        await observer.execute(
                            sql(
                                "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid=:pid AND locktype='advisory' AND NOT granted)"
                            ),
                            {"pid": pid},
                        )
                    ).scalar_one():
                        await asyncio.sleep(0.01)
            assert not task.done()
        if mode == "duplicate":
            assert await asyncio.wait_for(task, 3) == first_dispatch
        else:
            reason = {
                "capacity": "MODEL_BUDGET_EXHAUSTED",
                "conflict": "MODEL_ATTEMPT_CONFLICT",
                "release-send": "MODEL_TRANSITION_DENIED",
            }[mode]
            with pytest.raises(CatalogError, match=reason):
                await asyncio.wait_for(task, 3)
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("isolation", ["AUTOCOMMIT", "REPEATABLE READ", "SERIALIZABLE"])
async def test_pg_unsafe_isolation_is_refused(migrated_database_url: URL, isolation: str) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        owner, run, req, _ = await seed(engine)
        async with engine.connect() as connection:
            await connection.execution_options(isolation_level=isolation)
            async with connection.begin():
                with pytest.raises(CatalogError, match="MODEL_ISOLATION_REQUIRED"):
                    await budgets.create_budget(connection, owner, req["run_or_job_ref"], limits())
        async with engine.begin() as connection:
            graph = await managed_store.graph(connection, owner, run)
            assert sum(item["kind"] == "model-budget" for item in graph) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg_absent_foreign_scope_and_reference_pins_deny(migrated_database_url: URL) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        owner, _, req, budget = await seed(engine)
        other_owner, _, other, _ = await seed(engine)
        async with engine.begin() as conn:
            for who, scope in [
                (other_owner, req["run_or_job_ref"]),
                (owner, reference(envelope("managed-run", {}))),
            ]:
                with pytest.raises(CatalogError):
                    await budgets.create_budget(conn, who, scope, limits())
            for change in [
                {"run_or_job_ref": other["run_or_job_ref"]},
                {"native_turn_ref": other["native_turn_ref"]},
                {"projection_digest": "b" * 64},
                {
                    "projection_ref": {**mapping(req["projection_ref"]), "digest": "a" * 64},
                    "projection_digest": "a" * 64,
                },
            ]:
                with pytest.raises(CatalogError):
                    await budgets.reserve(
                        conn,
                        owner,
                        reference(budget),
                        {**req, **mapping(change)},
                        trusted_purpose="RECON",
                    )
            graph = await managed_store.graph(
                conn, owner, str(mapping(req["run_or_job_ref"])["id"])
            )
            assert not any(r["kind"] in {"model-dispatch", "model-reservation"} for r in graph)
    finally:
        await engine.dispose()
