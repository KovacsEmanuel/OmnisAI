"""SOURCE read-model checks; PostgreSQL/live acceptance belongs to the parent."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.engine import IteratorResult
from sqlalchemy.engine.result import SimpleResultMetaData
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs import projections
from omnis.modules.runs.model_test_store import ModelConflict
from test_run_owner_source import fixture_run


@pytest.mark.asyncio
async def test_agent_roster_groups_brain_and_pages_without_prompt_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = fixture_run()
    rows = [
        ("brain", "BRAIN", None, run.owner_id, "RUNNING", "Brain mission", 25),
        *[
            (
                f"00000000-0000-4000-8000-{index:012d}",
                "RECON",
                "brain",
                f"00000000-0000-4000-8001-{index:012d}",
                "SUCCEEDED",
                "Worker mission",
                1,
            )
            for index in range(1, 26)
        ],
    ]
    queries: list[str] = []

    async def execute(self: AsyncConnection, query: object, params: dict[str, object]) -> object:
        sql = str(query)
        queries.append(sql)
        after = params["after"]
        selected = (
            rows
            if after is None
            else rows[1:]
            if after == "brain"
            else [r for r in rows[1:] if r[0] > str(after)]
        )
        return IteratorResult(
            SimpleResultMetaData(
                ["agent_id", "role", "parent_agent_id", "attempt_id", "state", "brief", "attempts"]
            ),
            iter(selected[: int(str(params["limit"]))]),
        )

    monkeypatch.setattr(AsyncConnection, "execute", execute)
    anchor = AsyncMock(return_value=1)
    monkeypatch.setattr(AsyncConnection, "scalar", anchor)
    db = object.__new__(AsyncConnection)
    first = await projections.agent_page(db, run, None, 20)
    assert len(first.agents) == 20 and first.has_more and first.next_after
    assert first.agents[0].agent_id == "brain" and first.agents[0].attempts == 25
    second = await projections.agent_page(db, run, first.next_after, 20)
    again = await projections.agent_page(db, run, first.next_after, 20)
    ids = [item.agent_id for item in [*first.agents, *second.agents]]
    assert len(ids) == len(set(ids)) == 26 and not second.has_more
    assert [item.agent_id for item in again.agents] == [item.agent_id for item in second.agents]
    assert len(first.model_dump_json().encode()) < 65536
    assert all(
        "GROUP BY" in query and "instance_id=:instance" in query and "run_id=:run" in query
        for query in queries
    )
    with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
        await projections.agent_page(
            db, run.model_copy(update={"revision": run.revision + 1}), first.next_after, 20
        )
    with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
        await projections.agent_page(db, run, f"foreign:{run.revision}:brain", 20)
    anchor.return_value = None
    with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
        await projections.agent_page(db, run, f"{run.run_id}:{run.revision}:{str(uuid4())}", 20)


@pytest.mark.asyncio
async def test_agent_history_denies_foreign_cursor_before_database() -> None:
    with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
        await projections.agent_history(
            object.__new__(AsyncEngine), fixture_run().run_id, "brain", "foreign:brain:1", 20
        )


@pytest.mark.asyncio
async def test_agent_history_pairs_across_pages_and_exposes_gaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = fixture_run()
    db = object.__new__(AsyncConnection)
    engine = object.__new__(AsyncEngine)

    @asynccontextmanager
    async def connect(self: AsyncEngine) -> AsyncIterator[AsyncConnection]:
        yield db

    @asynccontextmanager
    async def begin(self: AsyncConnection) -> AsyncIterator[None]:
        yield None

    monkeypatch.setattr(AsyncEngine, "connect", connect)
    monkeypatch.setattr(AsyncConnection, "begin", begin)
    monkeypatch.setattr(AsyncConnection, "execution_options", AsyncMock(return_value=db))
    monkeypatch.setattr(projections, "read_run", AsyncMock(return_value=run))
    scalar = AsyncMock(return_value=1)
    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    events: list[dict[str, object]] = [
        {
            "event_id": str(uuid4()),
            "run_id": run.run_id,
            "task_id": run.owner_id,
            "attempt_id": run.owner_id,
            "sequence": index,
            "kind": "tool_called" if index != 21 else "tool_result",
            "summary": "Recorded inert call",
            "refs": [],
            "call_id": "call",
            "created_at": datetime.now(UTC).isoformat(),
        }
        for index in range(1, 24)
    ]
    queries: list[str] = []

    async def execute(self: AsyncConnection, query: object, params: dict[str, object]) -> object:
        queries.append(str(query))
        assert params["instance"] == run.instance_id and params["run"] == run.run_id
        after = int(str(params["after"]))
        rows = [
            (
                event,
                "RUNNING" if event["sequence"] == 22 else "FAILED",
                21 if event["sequence"] == 20 else 20 if event["sequence"] == 21 else None,
            )
            for event in events
            if int(str(event["sequence"])) > after
        ]
        return IteratorResult(
            SimpleResultMetaData(["payload", "state", "paired_sequence"]),
            iter(rows[: int(str(params["limit"]))]),
        )

    monkeypatch.setattr(AsyncConnection, "execute", execute)
    first = await projections.agent_history(engine, run.run_id, "brain", None, 20)
    second = await projections.agent_history(
        engine, run.run_id, "brain", f"{run.run_id}:brain:{first.through_cursor}", 20
    )
    replay = await projections.agent_history(
        engine, run.run_id, "brain", f"{run.run_id}:brain:{first.through_cursor}", 20
    )
    assert len(first.events) == 20 and first.has_more
    assert len(second.events) == 3 and not second.has_more
    assert [e.sequence for e in first.events + second.events] == list(range(1, 24))
    assert replay.events == second.events
    assert first.events[-1].pairing == "MATCHED" and first.events[-1].paired_sequence == 21
    assert [e.pairing for e in second.events] == ["MATCHED", "PENDING", "UNMATCHED"]
    assert all(
        "p.payload->>'task_id'=e.payload->>'task_id'" in query
        and "p.payload->>'attempt_id'=e.payload->>'attempt_id'" in query
        for query in queries
    )
    scalar.return_value = None
    with pytest.raises(ModelConflict, match="NOT_FOUND"):
        await projections.agent_history(engine, run.run_id, str(uuid4()), None, 20)
    assert len(queries) == 3


@pytest.mark.asyncio
async def test_activity_readers_require_authorization_without_database() -> None:
    from httpx import ASGITransport, AsyncClient

    from omnis.api import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://127.0.0.1:8765"
    ) as client:
        run = fixture_run()
        for suffix in ("agents", "agents/brain/events"):
            response = await client.get(f"/api/v1/runs/{run.run_id}/{suffix}")
            assert response.status_code == 401


@pytest.mark.asyncio
async def test_overview_metrics_are_unbounded_scoped_aggregates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = fixture_run()
    row = {
        "started_at": None,
        "finished_at": None,
        "agents": 26,
        "attempts": 50,
        "failed_attempts": 2,
        "sent": 45,
        "reserved": 1,
        "released": 4,
        "inflight": 1,
        "settled": 42,
        "unknown": 2,
    }
    execute = AsyncMock(
        return_value=IteratorResult(SimpleResultMetaData(list(row)), iter([tuple(row.values())]))
    )
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    result = await projections.overview_metrics(object.__new__(AsyncConnection), run)
    assert result.agents == 26 and result.attempts == 50
    assert result.sent == 45 and result.unknown == 2 and result.failed_attempts == 2
    assert result.started_at is None and result.finished_at is None
    sql = str(execute.call_args.args[0])
    assert "LIMIT" not in sql and "DISTINCT" in sql and "run_dispatch_event" in sql
    assert execute.call_args.args[1] == {
        "instance": run.instance_id,
        "run": run.run_id,
        "terminal": False,
    }
