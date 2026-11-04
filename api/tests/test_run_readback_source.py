"""Real owner+SDK+record/read DTO journey; SQL/authority seams, no PostgreSQL proof."""

import json
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import httpcore
import pytest
from fastapi import FastAPI
from sqlalchemy.engine import CursorResult, IteratorResult
from sqlalchemy.engine.result import SimpleResultMetaData
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from starlette.requests import Request

from omnis.modules.instance.domain import InstanceStatus
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_routes
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.run_contract import Attempt, AttemptInspection, Setup, UsageMeasures
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.supervisor.agent_runner import AgentStep
from omnis.supervisor.model_relay_protocol import Scope
from omnis.supervisor.model_sender import Transport
from test_run_controls_source import Owned
from test_run_controls_source import owned as owned
from test_run_inspection_source import actor
from test_run_owner_source import fixture_setup_payload
from test_run_usage_source import reported


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_counts", [False, True])
async def test_original_sdk_usage_owner_checkpoint_then_normal_reload_without_effects(
    owned: Owned,
    monkeypatch: pytest.MonkeyPatch,
    invalid_counts: bool,
) -> None:
    snapshot = Setup.model_validate(fixture_setup_payload())
    item = actor().model_copy(
        update={
            "instance_id": owned.run.instance_id,
            "run_id": owned.run.run_id,
            "role": "BRAIN",
            "state": "RUNNING",
        }
    )
    owned.run = owned.run.model_copy(update={"active_attempt_id": item.attempt_id})
    db = object.__new__(AsyncConnection)
    retained: dict[str, object] = {}
    saved: dict[str, dict[str, object]] = {}
    dispatch_id = ""
    dispatch_state = "RESERVED"
    readonly = False
    calls = 0
    writes: list[str] = []
    now = datetime.now(UTC)
    usage = reported()
    if invalid_counts:
        usage.update(
            {
                "prompt_tokens": True,
                "input_tokens": "10",
                "completion_tokens": 4.0,
                "output_tokens": False,
                "total_tokens": "30",
            }
        )

    @asynccontextmanager
    async def begin(self: object) -> AsyncIterator[AsyncConnection]:
        yield db

    async def scalar(self: AsyncConnection, statement: object, parameters: object = None) -> object:
        nonlocal dispatch_state
        sql = str(statement)
        if sql.startswith("SELECT payload FROM run_dispatch"):
            assert not readonly and "FOR UPDATE" in sql
            return retained
        if sql.startswith("UPDATE run_dispatch"):
            assert not readonly
            dispatch_state = "SETTLED"
            writes.append("settle")
            return dispatch_state
        if "agent_run" in sql:
            return owned.run.model_dump()
        if "supervisor_lease" in sql:
            return None
        raise AssertionError(sql)

    async def execute(
        self: AsyncConnection, statement: object, parameters: dict[str, object]
    ) -> CursorResult[tuple[object, ...]] | IteratorResult[tuple[object, ...]]:
        nonlocal dispatch_id, dispatch_state
        sql = str(statement)
        if sql.startswith("INSERT") or sql.startswith("UPDATE"):
            assert not readonly, "Normal GET must never write"
            writes.append(sql.split()[0])
            if sql.startswith("INSERT INTO model_record_v2"):
                saved[str(parameters["id"])] = json.loads(str(parameters["payload"]))
            elif sql.startswith("INSERT INTO run_dispatch"):
                retained.update(json.loads(str(parameters["payload"])))
                dispatch_id = str(parameters["id"])
            elif sql.startswith("UPDATE run_dispatch SET state"):
                dispatch_state = "SENT"
            elif sql.startswith("UPDATE run_dispatch SET payload"):
                retained.update(json.loads(str(parameters["payload"])))
            else:
                raise AssertionError(sql)
            result: CursorResult[tuple[object, ...]] = object.__new__(CursorResult)
            result.rowcount = 1
            return result
        if sql.startswith("SELECT payload FROM model_record_v2"):
            return IteratorResult(
                SimpleResultMetaData(["payload"]), iter([(saved[str(parameters["id"])],)])
            )
        if "FROM run_inbox" in sql:
            return IteratorResult(SimpleResultMetaData(["payload"]), iter([]))
        if sql.startswith("SELECT payload FROM run_attempt"):
            return IteratorResult(SimpleResultMetaData(["payload"]), iter([(item.model_dump(),)]))
        assert readonly and sql.startswith("\nWITH")
        ref = Ref.model_validate(retained["usage_ref"])
        value = saved[ref.id]
        if "GROUPING SETS" in sql:
            columns = ["role", "dispatches", "unobserved", "invalid"]
            row: list[object] = [None, 1, 0, 0]
            measures = UsageMeasures.model_validate(value["measures"])
            for key, amount in measures.model_dump().items():
                columns.extend([key, key + "_observed"])
                row.extend([str(amount) if amount is not None else None, int(amount is not None)])
            return IteratorResult(SimpleResultMetaData(columns), iter([tuple(row)]))
        row_map = {
            "dispatch_id": dispatch_id,
            "state": dispatch_state,
            "invalid": False,
            "usage_id": ref.id,
            "usage_kind": ref.kind,
            "usage_digest": ref.digest,
            "reserved_at": now,
            "sent_at": now,
            "settled_at": now,
        }
        return IteratorResult(SimpleResultMetaData(list(row_map)), iter([tuple(row_map.values())]))

    async def save_attempt(db: AsyncConnection, value: Attempt, *, initial: bool = False) -> None:
        nonlocal item
        assert not readonly
        item = value
        writes.append("attempt")

    async def relay_scope(
        db: AsyncConnection, fields: dict[str, object], *, allocate: bool = False
    ) -> Scope:
        assert allocate
        return Scope.parse({**fields, "operation_serial": 1})

    async def status(self: InstanceService, owner: UUID, epoch: int) -> InstanceStatus:
        assert not readonly
        return InstanceStatus(UUID(owned.run.instance_id), 0, True, None, None, 1, True, False)

    monkeypatch.setattr(AsyncConnection, "execute", execute)
    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    monkeypatch.setattr(AsyncConnection, "begin", begin)
    monkeypatch.setattr(AsyncConnection, "begin_nested", begin)
    monkeypatch.setattr(AsyncEngine, "begin", begin)
    monkeypatch.setattr(AsyncConnection, "execution_options", AsyncMock(return_value=db))
    monkeypatch.setattr(InstanceService, "owned_status", status)
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(store, "attempt", AsyncMock(side_effect=lambda *args: item))
    monkeypatch.setattr(store, "save_attempt", save_attempt)
    monkeypatch.setattr(store, "event", AsyncMock(return_value=1))
    monkeypatch.setattr(store, "dispatch_event", AsyncMock())
    monkeypatch.setattr(records, "relay_scope", relay_scope)
    monkeypatch.setattr(AgentRunOwner, "dispatch_config", AsyncMock(return_value=snapshot.brain))
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest

    owned.owner.model_owner = object.__new__(ApiKeyModelTest)
    monkeypatch.setattr(ApiKeyModelTest, "retire_relay", AsyncMock())
    transport = Transport(Path("/nonexistent-run-readback-source"), ssl.create_default_context())
    owned.owner.runner = AgentStep(transport)

    class Body:
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield json.dumps(
                {
                    "id": "scripted",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "fixture/observed",
                    "usage": usage,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "action": "finish",
                                        "summary": "No assessment",
                                        "detail": "No target work",
                                        "consumed_refs": [],
                                    }
                                ),
                            },
                        }
                    ],
                }
            ).encode()

        async def aclose(self) -> None:
            return None

    async def sink(request: httpcore.Request) -> httpcore.Response:
        nonlocal calls
        assert not readonly and dispatch_state == "SENT"
        calls += 1
        return httpcore.Response(
            200, headers=[(b"content-type", b"application/json")], content=Body()
        )

    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    try:
        await owned.owner.work(owned.run.run_id)
        assert item.state == "SUCCEEDED" and owned.run.state == "LIMITED"
        assert calls == 1 and item.result_ref is not None
        assert item.result_ref.kind == "run-decision-v2"
        assert (
            len(saved) == 3
        )  # step, usage, decision; one scripted transport call, not paid inference.
        readonly = True
        before = list(writes)
        app = FastAPI()
        app.state.db_engine = owned.owner.service.engine
        request = Request({"type": "http", "method": "GET", "path": "/", "app": app})
        last: AttemptInspection | None = None
        for _ in range(2):
            result = await run_routes.attempt(owned.run.run_id, item.attempt_id, request)
            assert isinstance(result, AttemptInspection)
            last = result
            assert result.decision is not None and result.decision.detail == "No target work"
            assert result.usage is not None and result.usage.scope == "ATTEMPT"
            assert result.usage.totals.cost_observed.value == "0.12300"
            retained_usage = result.dispatches[0].usage
            assert retained_usage is not None and retained_usage.reported.cost == "0.12300"
            assert retained_usage.measures.input_tokens == (None if invalid_counts else 10)
            assert retained_usage.measures.reasoning_tokens == 5
            assert retained_usage.measures.cached_tokens == 4
            assert "NO_RETAIN" not in result.model_dump_json()
            assert len(result.model_dump_json().encode()) <= 65536
        summary = await run_routes.summary(owned.run.run_id, request, 20)
        from omnis.modules.runs.run_contract import RunSummary

        assert isinstance(summary, RunSummary)
        assert summary.usage.scope == "RUN" and summary.usage.totals.dispatches == 1
        assert len(summary.attempts) == 1 and summary.attempts[0].result_ref == item.result_ref
        # Keep exact completion/whole-attempt totals; truncate only dispatch detail with has_more.
        assert last is not None
        base_size = len(last.model_copy(update={"dispatches": []}).model_dump_json().encode())
        item = item.model_copy(update={"input_text": item.input_text + "x" * (65536 - base_size)})
        bounded = await run_routes.attempt(owned.run.run_id, item.attempt_id, request)
        assert isinstance(bounded, AttemptInspection)
        assert len(bounded.model_dump_json().encode()) <= 65536
        assert bounded.dispatches == [] and bounded.dispatches_has_more
        assert bounded.usage is not None and bounded.usage.totals.dispatches == 1
        assert writes == before and calls == 1
    finally:
        await transport.aclose()
