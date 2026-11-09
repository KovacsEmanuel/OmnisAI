"""SOURCE read-model checks; PostgreSQL/live acceptance belongs to the parent."""

import json
import sqlite3
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
    progressed = await projections.agent_page(
        db, run.model_copy(update={"revision": run.revision + 1}), first.next_after, 3
    )
    assert [a.agent_id for a in progressed.agents] == ids[20:23]
    assert progressed.next_after == f"{run.run_id}:{run.revision}:{ids[22]}"
    assert progressed.revision == run.revision + 1
    with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
        await projections.agent_page(db, run, f"foreign:{run.revision}:brain", 20)
    for cursor in (
        "",
        f"{run.run_id}:0:brain",
        f"{run.run_id}:01:brain",
        f"{run.run_id}:2:brain",
        f"{run.run_id}:1:invalid",
    ):
        with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
            await projections.agent_page(db, run, cursor, 20)
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
            "kind": "control",
            "summary": "Retained synthetic event",
            "refs": [],
            "call_id": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        for index in range(1, 37)
    ]
    for sequence, kind, call in [
        (20, "tool_called", "page"),
        (21, "tool_result", "page"),
        (22, "tool_called", "pending"),
        (23, "tool_called", "missing"),
        (24, "tool_called", "reused"),
        (25, "tool_result", "reused"),
        (26, "tool_called", "reused"),
        (27, "result", "reused"),
        (28, "tool_called", "extra-call"),
        (29, "tool_called", "extra-call"),
        (30, "tool_result", "extra-call"),
        (31, "tool_called", "extra-result"),
        (32, "tool_result", "extra-result"),
        (33, "result", "extra-result"),
        (34, "tool_result", None),
        (35, "result", None),
    ]:
        events[sequence - 1].update(kind=kind, call_id=call)
    pending = str(uuid4())
    events[21]["attempt_id"] = pending
    queries: list[str] = []

    async def execute(self: AsyncConnection, query: object, params: dict[str, object]) -> object:
        queries.append(str(query))
        assert params["instance"] == run.instance_id and params["run"] == run.run_id
        # Only PG text casts differ; execute the full projection, not invented pair columns.
        with sqlite3.connect(":memory:") as sql:
            sql.execute(
                "CREATE TABLE run_event(instance_id text, run_id text, sequence int, payload text)"
            )
            sql.execute(
                "CREATE TABLE run_attempt(instance_id text, run_id text, attempt_id text, task_id text, role text, state text)"
            )
            for attempt, state in [(run.owner_id, "FAILED"), (pending, "RUNNING")]:
                sql.execute(
                    "INSERT INTO run_attempt VALUES(?,?,?,?,?,?)",
                    (run.instance_id, run.run_id, attempt, run.owner_id, "BRAIN", state),
                )
            sql.executemany(
                "INSERT INTO run_event VALUES(?,?,?,?)",
                [(run.instance_id, run.run_id, e["sequence"], json.dumps(e)) for e in events],
            )
            rows = sql.execute(str(query).replace("::text", ""), params)
            names = [column[0] for column in rows.description]
            values = [(json.loads(row[0]), *row[1:]) for row in rows]
        return IteratorResult(SimpleResultMetaData(names), iter(values))

    monkeypatch.setattr(AsyncConnection, "execute", execute)
    first = await projections.agent_history(engine, run.run_id, "brain", None, 20)
    second = await projections.agent_history(
        engine, run.run_id, "brain", f"{run.run_id}:brain:20", 20
    )
    replay = await projections.agent_history(
        engine, run.run_id, "brain", f"{run.run_id}:brain:20", 20
    )
    assert len(first.events) == 20 and first.has_more
    assert len(second.events) == 16 and not second.has_more
    assert [e.sequence for e in first.events + second.events] == list(range(1, 37))
    assert replay.events == second.events
    assert first.events[-1].pairing == "MATCHED" and first.events[-1].paired_sequence == 21
    assert [e.pairing for e in second.events[:3]] == ["MATCHED", "PENDING", "UNMATCHED"]
    assert [(e.sequence, e.paired_sequence) for e in second.events[3:7]] == [
        (24, 25),
        (25, 24),
        (26, 27),
        (27, 26),
    ]
    assert all(e.pairing == "UNMATCHED" and e.paired_sequence is None for e in second.events[7:14])
    direct = second.events[14]
    assert direct.kind == "result" and direct.call_id is None
    assert direct.pairing == "NOT_APPLICABLE" and direct.paired_sequence is None
    assert second.events[-1].pairing == "NOT_APPLICABLE"
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
