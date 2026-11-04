"""S1 SOURCE: actual installed SDK, scripted transport only; no PG/provider proof."""

import json
import ssl
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import httpcore
import pytest
from openai import Omit
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.modules.runs.run_contract import BrainDecision, RunCommand, completion_status
from omnis.supervisor.agent_runner import AgentStep, ExplicitClient, StepInput
from omnis.supervisor.model_relay_protocol import Authority
from omnis.supervisor.model_sender import CURRENT, Transport
from test_agent_core_publication import publish_core
from test_agent_core_publication import storage_seam as storage_seam


@pytest.mark.parametrize(
    "exit_kind,read,expected",
    [
        ("direct", True, "SUCCEEDED"),
        ("direct", False, "INCONCLUSIVE"),
        ("finish", True, "SUCCEEDED"),
        ("finish", False, "INCONCLUSIVE"),
        ("error", True, "FAILED"),
        ("cancel", True, "CANCELLED"),
    ],
)
def test_all_finalizations_use_the_same_completion_gate(
    exit_kind: str, read: bool, expected: str
) -> None:
    assert completion_status(exit_kind, read) == expected


@pytest.mark.parametrize("action", ["delegate", "ask", "finish"])
def test_brain_decision_is_a_proposal_not_authority(action: str) -> None:
    proposal = dict(
        action=action, summary="Inert next step", consumed_refs=[], detail="Read context"
    )
    assert BrainDecision.model_validate(proposal).action == action
    with pytest.raises(ValidationError):
        BrainDecision.model_validate({**proposal, "task_id": "model-minted"})
    with pytest.raises(ValidationError):
        BrainDecision.model_validate({**proposal, "summary": "x" * 257})


def test_answer_bounds_the_complete_command() -> None:
    payload = dict(
        action="answer",
        command_id="11111111-1111-4111-8111-111111111111",
        expected_generation=0,
        expected_revision=1,
        run_id="22222222-2222-4222-8222-222222222222",
        question_id="33333333-3333-4333-8333-333333333333",
        answer="clarification",
    )
    assert RunCommand.model_validate(payload).answer == "clarification"
    with pytest.raises(ValidationError):
        RunCommand.model_validate({**payload, "answer": "\t" * 1800})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "read",
        "finish",
        "multiple",
        "foreign_tool",
        "overflow",
        "altered",
        "ambient",
        "foreign_header",
        "truncated",
        "secret_echo",
        "whitespace_arguments",
        "exact_32768",
        "overflow_32769",
        "exact_response",
        "response_over",
        "provider_error",
    ],
)
async def test_owned_sdk_step_stops_after_persisted_tool(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    transport = Transport(Path("/nonexistent-s1-source"), ssl.create_default_context())
    calls: list[bytes] = []
    receipts: list[str] = []
    closed: list[bool] = []
    sent_calls: list[bool] = []
    if mode == "foreign_header":
        original_headers = ExplicitClient.default_headers

        def foreign_headers(client: ExplicitClient) -> dict[str, str | Omit]:
            return {**original_headers.__get__(client), "OpenAI-Organization": "foreign"}

        monkeypatch.setattr(ExplicitClient, "default_headers", property(foreign_headers))
    if mode == "ambient":
        monkeypatch.setenv("OPENAI_ORG_ID", "not-admitted-org")
        monkeypatch.setenv("OPENAI_PROJECT_ID", "not-admitted-project")
        monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "X-Unadmitted: sentinel")

    async def persist(name: str, arguments: str, call_id: str) -> str:
        if mode == "finish":
            assert name == "finish" and json.loads(arguments) == {
                "summary": "Inert complete",
                "consumed_refs": [],
                "gaps": [],
            }
        else:
            assert name == "read_context" and json.loads(arguments) == {}
        assert call_id == "read-1"
        receipts.append(call_id)
        return '{"context":"selected synthetic inert input","receipt":"persisted"}'

    def guard() -> AbstractAsyncContextManager[Authority]:
        raise AssertionError("SOURCE must not access relay")

    async def sent() -> None:
        sent_calls.append(True)

    async def observed(raw: bytes) -> None:
        assert raw

    class Body:
        async def __aiter__(self) -> AsyncIterator[bytes]:
            tool = {
                "id": "read-1",
                "type": "function",
                "function": {"name": "read_context", "arguments": "{}"},
            }
            if mode == "finish":
                tool["function"] = {
                    "name": "finish",
                    "arguments": json.dumps(
                        {
                            "summary": "Inert complete",
                            "consumed_refs": [],
                            "gaps": [],
                        }
                    ),
                }
            if mode == "foreign_tool":
                tool["function"] = {"name": "shell", "arguments": "{}"}
            if mode == "whitespace_arguments":
                tool["function"] = {"name": "read_context", "arguments": " { } "}
            raw = json.dumps(
                {
                    "id": "scripted",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "fixture/recon",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "length" if mode == "truncated" else "tool_calls",
                            "message": {
                                "role": "assistant",
                                "content": "synthetic-not-a-key" if mode == "secret_echo" else None,
                                "tool_calls": [tool, tool] if mode == "multiple" else [tool],
                            },
                        }
                    ],
                }
            ).encode()
            if mode in {"exact_response", "response_over"}:
                raw += b" " * (131072 - len(raw) + int(mode == "response_over"))
            yield raw

        async def aclose(self) -> None:
            closed.append(True)

    async def sink(request: httpcore.Request) -> httpcore.Response:
        assert isinstance(request.stream, AsyncIterable)
        calls.append(b"".join([part async for part in request.stream]))
        assert not any(
            k.lower() in {b"openai-organization", b"openai-project", b"x-unadmitted"}
            for k, _ in request.headers
        )
        return httpcore.Response(
            503 if mode == "provider_error" else 200,
            headers=[(b"content-type", b"application/json")],
            content=Body(),
        )

    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    step = StepInput(
        role="RECON",
        model="fixture/recon",
        output_tokens=128,
        instructions="Only read the selected inert context.",
        input_text="Selected context ref",
        provider="openrouter",
        history=[],
    )
    if mode == "overflow":
        step = step.model_copy(update={"input_text": "\t" * 20000})
    bridge = AgentStep(transport)
    if mode == "altered":
        original = bridge.projection

        def altered(value: StepInput) -> dict[str, object]:
            return {**original(value), "model": "fixture/other"}

        monkeypatch.setattr(bridge, "projection", altered)
    if mode in {"exact_32768", "overflow_32769"}:
        remaining = 32768 - len(
            json.dumps(bridge.projection(step), ensure_ascii=False, separators=(",", ":")).encode()
        )
        assert remaining > 0
        step = step.model_copy(
            update={
                "input_text": step.input_text
                + "x" * remaining
                + ("x" if mode == "overflow_32769" else "")
            }
        )
    try:
        if mode in {
            "multiple",
            "foreign_tool",
            "overflow",
            "altered",
            "foreign_header",
            "truncated",
            "secret_echo",
            "overflow_32769",
            "response_over",
            "provider_error",
        }:
            with pytest.raises(ValueError):
                await bridge.run(step, "synthetic-not-a-key", guard, persist, observed, sent)
            assert receipts == []
            assert len(calls) == (
                0 if mode in {"overflow", "altered", "foreign_header", "overflow_32769"} else 1
            )
            assert len(sent_calls) == len(calls)
        else:
            result = await bridge.run(step, "synthetic-not-a-key", guard, persist, observed, sent)
            assert (
                result.kind == ("finish" if mode == "finish" else "tool")
                and result.call_id == "read-1"
            )
            assert receipts == ["read-1"] and len(calls) == 1
        assert CURRENT.get(None) is None
        if mode == "exact_32768":
            assert len(calls[0]) == 32768
        assert len(closed) == len(calls)
    finally:
        await transport.aclose()


@pytest.mark.asyncio
async def test_sdk_initial_post_tool_and_brain_consume_are_separate_steps(
    monkeypatch: pytest.MonkeyPatch,
    storage_seam: AsyncEngine,
    tmp_path: Path,
) -> None:
    from uuid import uuid4

    from omnis.modules.runs.model_test_contract import Ref
    from omnis.modules.runs.run_contract import WorkerFinal
    from omnis.modules.settings.catalog_models import ExactRef
    from omnis.modules.tasks.agent_composition import compose_publication
    from omnis.supervisor.agent_runner import Exchange

    catalog, owner, publication = await publish_core(storage_seam, tmp_path / "catalog")
    async with storage_seam.begin() as db:
        recon_composition = await compose_publication(
            catalog,
            db,
            owner,
            ExactRef.model_validate(publication),
            role="RECON",
            brief="Read the selected synthetic context; report gaps.",
        )
        brain_composition = await compose_publication(
            catalog,
            db,
            owner,
            ExactRef.model_validate(publication),
            role="BRAIN",
            brief="Consume the exact stored result refs and decide the next step.",
        )

    transport = Transport(Path("/nonexistent-s1-sequence"), ssl.create_default_context())
    bridge = AgentStep(transport)
    reference = Ref(
        instance_id=str(uuid4()), id=str(uuid4()), kind="run-tool-result-v1", digest="a" * 64
    )
    memory: dict[str, str] = {}
    sizes: list[int] = []
    steps: list[StepInput] = []

    async def sent() -> None:
        assert CURRENT.get(None) is not None

    def guard() -> AbstractAsyncContextManager[Authority]:
        raise AssertionError("SOURCE never connects relay")

    async def tool(name: str, arguments: str, call_id: str) -> str:
        memory[reference.id] = json.dumps(
            {"ref": reference.model_dump(mode="json"), "text": "selected inert context"}
        )
        return memory[reference.id]

    async def observed(raw: bytes) -> None:
        assert json.loads(raw)["usage"]["prompt_tokens"] == "uncoerced"

    class Body:
        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield self.raw

        async def aclose(self) -> None:
            return None

    async def sink(request: httpcore.Request) -> httpcore.Response:
        assert isinstance(request.stream, AsyncIterable)
        raw = b"".join([part async for part in request.stream])
        sizes.append(len(raw))
        body = json.loads(raw)
        assert body == bridge.projection(steps[-1])
        index = len(sizes)
        message: dict[str, object] = {"role": "assistant"}
        if index == 1:
            message.update(
                content=None,
                tool_calls=[
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "read_context", "arguments": "{}"},
                    }
                ],
            )
        elif index == 2:
            assert body["response_format"]["json_schema"]["schema"]["title"] == "WorkerFinal"
            assert body["messages"][-1]["content"] == memory[reference.id]
            message["content"] = WorkerFinal(
                summary="Read selected context", consumed_refs=[reference], gaps=[]
            ).model_dump_json()
        else:
            assert reference.id in body["messages"][-1]["content"]
            message["content"] = BrainDecision(
                action="finish",
                summary="Consumed the stored result",
                consumed_refs=[reference],
                detail="S1 inert only",
            ).model_dump_json()
        return httpcore.Response(
            200,
            headers=[(b"content-type", b"application/json")],
            content=Body(
                json.dumps(
                    {
                        "id": "scripted",
                        "object": "chat.completion",
                        "created": 0,
                        "model": steps[-1].model,
                        "usage": {"prompt_tokens": "uncoerced"},
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "tool_calls" if index == 1 else "stop",
                                "message": message,
                            }
                        ],
                    }
                ).encode()
            ),
        )

    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    initial = StepInput(
        role="RECON",
        model="fixture/recon",
        output_tokens=256,
        provider="openrouter",
        instructions=recon_composition.text,
        input_text="Selected context",
        history=[],
    )
    try:
        steps.append(initial)
        first = await bridge.run(initial, "synthetic-not-a-key", guard, tool, observed, sent)
        assert first.kind == "tool"
        second = initial.model_copy(
            update={
                "history": [Exchange(call_id="call-1", arguments="{}", result=memory[reference.id])]
            }
        )
        steps.append(second)
        result = await bridge.run(second, "synthetic-not-a-key", guard, tool, observed, sent)
        assert WorkerFinal.model_validate_json(result.text).consumed_refs == [reference]
        brain = StepInput(
            role="BRAIN",
            model="fixture/brain",
            output_tokens=256,
            provider="openrouter",
            instructions=brain_composition.text,
            input_text=result.text,
            history=[],
        )
        steps.append(brain)
        decision = await bridge.run(brain, "synthetic-not-a-key", guard, tool, observed, sent)
        assert BrainDecision.model_validate_json(decision.text).consumed_refs == [reference]
        assert len(sizes) == 3 and CURRENT.get(None) is None
        print("S1_SCRIPTED_SDK_BYTES", sizes)
    finally:
        await transport.aclose()


@pytest.mark.asyncio
async def test_sdk_cancellation_has_no_retry_and_releases_private_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    transport = Transport(Path("/nonexistent-s1-cancel"), ssl.create_default_context())
    requests: list[bool] = []
    step = StepInput(
        role="BRAIN",
        model="fixture/brain",
        output_tokens=128,
        provider="openrouter",
        instructions="Inert",
        input_text="Inert",
        history=[],
    )

    async def sink(request: httpcore.Request) -> httpcore.Response:
        requests.append(True)
        assert CURRENT.get(None) is not None
        raise asyncio.CancelledError()

    def guard() -> AbstractAsyncContextManager[Authority]:
        raise AssertionError("No relay in SOURCE")

    async def tool(name: str, arguments: str, call_id: str) -> str:
        raise AssertionError("No tool after cancellation")

    async def observe(raw: bytes) -> None:
        raise AssertionError("No response after cancellation")

    async def sent() -> None:
        assert CURRENT.get(None) is not None

    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    try:
        with pytest.raises(asyncio.CancelledError):
            await AgentStep(transport).run(step, "synthetic-not-a-key", guard, tool, observe, sent)
        assert requests == [True] and CURRENT.get(None) is None
    finally:
        await transport.aclose()
