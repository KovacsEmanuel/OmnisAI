"""Exact normal-reader payloads through SQL seams; not PostgreSQL proof."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.engine import IteratorResult
from sqlalchemy.engine.result import SimpleResultMetaData
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.run_contract import Attempt
from test_run_owner_source import fixture_run


def actor() -> Attempt:
    run = fixture_run()
    return Attempt(
        instance_id=run.instance_id,
        run_id=run.run_id,
        task_id=str(uuid4()),
        attempt_id=str(uuid4()),
        role="RECON",
        parent_task_id=None,
        state="INCONCLUSIVE",
        brief="Inert",
        input_refs=[],
        input_text="Inert",
        instructions="Inert",
        configured_model="fixture/recon",
        skill_refs=[],
        result_summary="Incomplete",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["direct", "finish", "error", "cancel", None])
async def test_exact_result_readback_preserves_gaps_and_unknown_history(
    monkeypatch: pytest.MonkeyPatch,
    kind: str | None,
) -> None:
    item = actor()
    payload: dict[str, object] = {
        "run_id": item.run_id,
        "task_id": item.task_id,
        "attempt_id": item.attempt_id,
        "state": item.state,
        "summary": "Incomplete",
        "consumed_refs": [],
        "gaps": ["not observed", "INERT_READ_PROOF_INCOMPLETE"],
    }
    if kind is not None:
        payload["completion_kind"] = kind
    reference = Ref(
        instance_id=item.instance_id,
        kind="run-result-v1",
        id=str(uuid4()),
        digest=records.digest(payload),
    )
    item = item.model_copy(update={"result_ref": reference})
    db = object.__new__(AsyncConnection)
    execute = AsyncMock(
        side_effect=[
            IteratorResult(SimpleResultMetaData(["payload"]), iter([(payload,)])),
            IteratorResult(
                SimpleResultMetaData(["held", "consumed_decision_id"]), iter([(True, None)])
            ),
        ]
    )
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    result = await store.inspect_completion(db, item)
    assert result.result is not None
    assert result.result.gaps == payload["gaps"]
    assert result.result.completion_kind == kind
    assert result.result.state == item.state
    assert result.decision is None and result.consumption is not None
    assert result.consumption.held and result.consumption.decision_ref is None
    assert result.result_ref == reference and result.as_of <= datetime.now(UTC)
    assert all(str(call.args[0]).startswith("SELECT") for call in execute.call_args_list)
    assert json.loads(result.model_dump_json())["result"]["completion_kind"] == kind


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field", ["instance_id", "run_id", "task_id", "attempt_id", "kind", "revision", "digest"]
)
async def test_result_reference_and_ownership_are_independent_denials(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    item = actor()
    payload: dict[str, object] = {
        "run_id": item.run_id,
        "task_id": item.task_id,
        "attempt_id": item.attempt_id,
        "state": item.state,
        "summary": "Incomplete",
        "consumed_refs": [],
        "gaps": [],
    }
    if field in {"run_id", "task_id", "attempt_id"}:
        payload[field] = str(uuid4())
    reference = Ref(
        instance_id=item.instance_id,
        kind="run-result-v1",
        id=str(uuid4()),
        digest=records.digest(payload),
    )
    if field in {"instance_id", "kind", "revision", "digest"}:
        reference = reference.model_copy(
            update={
                field: {
                    "instance_id": str(uuid4()),
                    "kind": "run-context-v1",
                    "revision": 2,
                    "digest": "0" * 64,
                }[field]
            }
        )
    item = item.model_copy(update={"result_ref": reference})
    execute = AsyncMock(
        return_value=IteratorResult(SimpleResultMetaData(["payload"]), iter([(payload,)]))
    )
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    with pytest.raises(ValueError, match="REF_UNAVAILABLE"):
        await store.inspect_completion(object.__new__(AsyncConnection), item)
    assert execute.await_count <= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("wrong", [None, "run_id", "task_id", "attempt_id", "consumption", "event"])
async def test_last_brain_exact_decision_and_consumption(
    monkeypatch: pytest.MonkeyPatch,
    legacy: bool,
    wrong: str | None,
) -> None:
    item = actor().model_copy(update={"role": "BRAIN", "state": "SUCCEEDED"})
    consumed = Ref(
        instance_id=item.instance_id, kind="run-result-v1", id=str(uuid4()), digest="b" * 64
    )
    decision = {
        "action": "finish",
        "summary": "Stopped",
        "detail": "No assessment",
        "consumed_refs": [consumed.model_dump()],
    }
    envelope = {
        "run_id": item.run_id,
        "task_id": item.task_id,
        "attempt_id": item.attempt_id,
        "completion_kind": "direct",
        "decision": decision,
    }
    if wrong in {"run_id", "task_id", "attempt_id"}:
        envelope[wrong] = str(uuid4())
    payload = decision if legacy else envelope
    ref = Ref(
        instance_id=item.instance_id,
        kind="run-decision-v1" if legacy else "run-decision-v2",
        id=str(uuid4()),
        digest=records.digest(payload),
    )
    item = item.model_copy(update={"result_ref": ref})
    execute = AsyncMock(
        side_effect=[
            IteratorResult(SimpleResultMetaData(["payload"]), iter([(payload,)])),
            IteratorResult(
                SimpleResultMetaData(list(consumed.model_dump())),
                iter([] if wrong == "consumption" else [tuple(consumed.model_dump().values())]),
            ),
        ]
    )
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    scalar = AsyncMock(return_value=None if wrong else 1)
    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    if wrong and (legacy or wrong != "event"):
        with pytest.raises(ValueError, match="REF_UNAVAILABLE"):
            await store.inspect_completion(object.__new__(AsyncConnection), item)
    else:
        result = await store.inspect_completion(object.__new__(AsyncConnection), item)
        assert result.decision is not None and result.decision.model_dump() == decision
        assert result.decision_completion_kind == (None if legacy else "direct")
        assert result.result_ref == ref and result.result is None


@pytest.mark.asyncio
async def test_normal_attempt_route_reload_is_readonly_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from omnis.modules.runs import run_routes
    from omnis.modules.runs.run_contract import AttemptInspection

    item = actor()
    run = fixture_run().model_copy(update={"instance_id": item.instance_id, "run_id": item.run_id})
    engine, db = object.__new__(AsyncEngine), object.__new__(AsyncConnection)

    @asynccontextmanager
    async def connect(self: AsyncEngine) -> AsyncIterator[AsyncConnection]:
        yield db

    @asynccontextmanager
    async def begin(self: AsyncConnection) -> AsyncIterator[None]:
        yield

    options = AsyncMock(return_value=db)
    monkeypatch.setattr(AsyncEngine, "connect", connect)
    monkeypatch.setattr(AsyncConnection, "begin", begin)
    monkeypatch.setattr(AsyncConnection, "execution_options", options)
    scalar = AsyncMock(
        side_effect=lambda *args: (
            run.model_dump() if "agent_run" in str(args[0]) else item.model_dump()
        )
    )
    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    monkeypatch.setattr(
        AsyncConnection, "execute", AsyncMock(side_effect=AssertionError("No writes"))
    )
    app = FastAPI()
    app.state.db_engine = engine
    request = Request({"type": "http", "method": "GET", "path": "/", "app": app})
    for _ in range(2):
        result = await run_routes.attempt(item.run_id, item.attempt_id, request)
        assert isinstance(result, AttemptInspection) and result.result is None
        assert result.result_ref is None
    assert options.call_args.kwargs == {
        "isolation_level": "REPEATABLE READ",
        "postgresql_readonly": True,
    }
    item = item.model_copy(update={"input_text": "x" * 65536})
    denied = await run_routes.attempt(item.run_id, item.attempt_id, request)
    assert isinstance(denied, JSONResponse) and denied.status_code == 422
    assert b"PROJECTION_LIMIT" in bytes(denied.body)
