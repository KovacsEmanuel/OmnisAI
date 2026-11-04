"""Real SDK finish FunctionTool -> owner gate -> committed synthetic receipt."""

import json
import ssl
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpcore
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.run_contract import Attempt, Setup, WorkerFinal
from omnis.supervisor.agent_runner import AgentStep, Exchange, StepInput
from omnis.supervisor.model_relay_protocol import Authority, Scope
from omnis.supervisor.model_sender import CURRENT, SendDenied, Transport
from test_run_controls_source import Owned
from test_run_controls_source import owned as owned
from test_run_owner_source import fixture_setup_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["valid", "missing", "foreign", "gaps", "stopped"])
async def test_finish_sdk_waits_for_owner_receipt_and_settlement_never_duplicates(
    owned: Owned, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    ref = owned.run.setup_ref.model_copy(update={"kind": "run-tool-result-v1"})
    snapshot = Setup.model_validate(fixture_setup_payload())
    actor = Attempt(
        instance_id=owned.run.instance_id,
        run_id=owned.run.run_id,
        task_id=str(uuid4()),
        attempt_id=str(uuid4()),
        role="RECON",
        parent_task_id=None,
        state="RUNNING",
        brief="Inert",
        input_refs=[],
        input_text="Inert",
        instructions="Inert",
        configured_model="fixture/recon",
        skill_refs=[],
        read_receipt_ref=None if mode == "missing" else ref,
    )
    owned.run = owned.run.model_copy(update={"active_attempt_id": actor.attempt_id})
    scope = Scope(
        owned.run.instance_id,
        "MODEL_DISPATCH",
        str(uuid4()),
        owned.run.owner_id,
        0,
        1,
        owned.run.fence,
        (datetime.now(UTC) + timedelta(seconds=300)).isoformat(),
        "openrouter",
        1,
    )
    payloads: list[dict[str, object]] = []
    events: list[str] = []

    async def read_attempt(*args: object) -> Attempt:
        return actor

    async def save(db: AsyncConnection, value: Attempt, *, initial: bool = False) -> None:
        nonlocal actor
        actor = value

    async def put(
        db: AsyncConnection, instance: str, kind: str, payload: dict[str, object]
    ) -> object:
        assert kind == "run-result-v1"
        payloads.append(payload)
        return ref.model_copy(
            update={"kind": kind, "id": str(uuid4()), "digest": records.digest(payload)}
        )

    async def event(*args: object, **kwargs: object) -> int:
        assert kwargs["call_id"] == "finish-1"
        events.append(str(args[2]))
        return len(events)

    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(store, "attempt", read_attempt)
    monkeypatch.setattr(store, "save_attempt", save)
    monkeypatch.setattr(store, "event", event)
    inbox = AsyncMock()
    monkeypatch.setattr(store, "add_inbox", inbox)
    monkeypatch.setattr(records, "put", put)
    supplied = ref if mode != "foreign" else ref.model_copy(update={"id": str(uuid4())})
    final = WorkerFinal(
        summary="Read selected context",
        consumed_refs=[supplied],
        gaps=["not complete"] if mode == "gaps" else [],
    )
    transport = Transport(Path("/nonexistent-finish-source"), ssl.create_default_context())
    calls = 0

    class Body:
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield json.dumps(
                {
                    "id": "scripted",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "fixture/recon",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "tool_calls",
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "finish-1",
                                        "type": "function",
                                        "function": {
                                            "name": "finish",
                                            "arguments": final.model_dump_json(),
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            ).encode()

        async def aclose(self) -> None:
            return None

    async def sink(request: httpcore.Request) -> httpcore.Response:
        nonlocal calls
        calls += 1
        return httpcore.Response(
            200, headers=[(b"content-type", b"application/json")], content=Body()
        )

    async def callback(name: str, arguments: str, call_id: str) -> str:
        if mode == "stopped":
            owned.run = owned.run.model_copy(
                update={"state": "STOPPING", "fence": owned.run.fence + 1}
            )
        result = await owned.owner.execute_tool(
            owned.run.run_id, scope, actor.attempt_id, snapshot, name, arguments, call_id
        )
        assert owned.writes[-1] == "commit" and actor.result_ref is not None
        assert inbox.await_count == 1 and events == ["tool_called", "result"]
        return result

    def guard() -> AbstractAsyncContextManager[Authority]:
        raise AssertionError("No relay in SOURCE")

    step = StepInput(
        role="RECON",
        model="fixture/recon",
        provider="openrouter",
        output_tokens=128,
        input_text="Inert",
        instructions="Inert",
        history=[Exchange(call_id="read-1", arguments="{}", result="inert receipt")],
    )
    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    try:
        if mode == "stopped":
            with pytest.raises((SendDenied, records.ModelConflict)):
                await AgentStep(transport).run(
                    step, "synthetic-unused-key", guard, callback, AsyncMock(), AsyncMock()
                )
            assert not payloads and not inbox.called
        else:
            result = await AgentStep(transport).run(
                step, "synthetic-unused-key", guard, callback, AsyncMock(), AsyncMock()
            )
            assert result.kind == "finish"
            assert actor.state == ("SUCCEEDED" if mode == "valid" else "INCONCLUSIVE")
            assert len(payloads) == 1 and payloads[0]["completion_kind"] == "finish"
            monkeypatch.setattr(AsyncConnection, "scalar", AsyncMock(side_effect=["SETTLED", None]))
            dispatch = AsyncMock()
            monkeypatch.setattr(store, "dispatch_event", dispatch)
            for expected in (True, False):
                assert (
                    await owned.owner.finish_step(
                        object.__new__(AsyncConnection),
                        owned.run.run_id,
                        actor.attempt_id,
                        scope,
                        result,
                        None,
                        admitted=True,
                    )
                    is expected
                )
            assert len(payloads) == 1 and inbox.await_count == dispatch.await_count == 1
        assert calls == 1 and CURRENT.get(None) is None
    finally:
        await transport.aclose()
