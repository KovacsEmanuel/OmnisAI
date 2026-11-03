"""S0 SDK/serializer admission only: scripted replies, no inference or persistence."""

import asyncio
import json
import ssl
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AbstractAsyncContextManager, nullcontext
from pathlib import Path

import httpcore
import httpx
import pytest
from agents import Agent, FunctionTool, ModelSettings, OpenAIChatCompletionsModel, RunConfig, Runner
from agents.retry import ModelRetrySettings
from openai import APIConnectionError, AsyncOpenAI, InternalServerError
from pydantic import ValidationError

from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.runs.model_test_contract import ENDPOINTS
from omnis.modules.settings.provider_key_models import (
    KeySettingsControl,
    ModelSelection,
    SaveSelection,
)
from omnis.supervisor.model_relay_protocol import Authority
from omnis.supervisor.model_sender import CURRENT, Permit, SendDenied, Transport
from omnis.transport.local_control import decode_control_frame

FIXTURE = Path(__file__).with_name("fixtures") / "agent_sdk_admission.json"
MODEL = "fixture/selected-brain"
SECRET = "synthetic-not-a-credential"
REF = {
    "kind": "context",
    "id": "11111111-1111-4111-8111-111111111111",
    "revision": 1,
    "digest": "a" * 64,
}
SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "ref": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["context"]},
                "id": {"type": "string"},
                "revision": {"type": "integer"},
                "digest": {"type": "string"},
            },
            "required": ["kind", "id", "revision", "digest"],
            "additionalProperties": False,
        }
    },
    "required": ["ref"],
    "additionalProperties": False,
}
DESCRIPTION = "Read the selected inert context ref; no external effect or persistence."
PROVIDER = {"allow_fallbacks": False, "require_parameters": True}


def wire(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def composition() -> tuple[str, str, str]:
    value: object = json.loads(FIXTURE.read_bytes())
    assert isinstance(value, dict)
    instructions, user, history = value["instructions"], value["user"], value["history"]
    assert isinstance(instructions, str) and isinstance(user, str) and isinstance(history, str)
    user += "\n" + wire({"brief": value["brief"], "context": value["context"]}).decode()
    return instructions, user, history


def projection(instructions: str, user: str, history: str, result: str | None) -> dict[str, object]:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": "What is currently admitted?"},
        {"role": "assistant", "content": history},
        {"role": "user", "content": user},
    ]
    if result is not None:
        messages.extend(
            [
                {"role": "assistant", "content": None, "tool_calls": [tool_call()]},
                {"role": "tool", "tool_call_id": "s0-call", "content": result},
            ]
        )
    return {
        "model": MODEL,
        "messages": messages,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_context",
                    "description": DESCRIPTION,
                    "parameters": SCHEMA,
                    "strict": True,
                },
            }
        ],
        "max_tokens": 128,
        "parallel_tool_calls": False,
        "store": False,
        "provider": PROVIDER,
    }


def tool_call() -> dict[str, object]:
    return {
        "id": "s0-call",
        "type": "function",
        "function": {"name": "read_context", "arguments": wire({"ref": REF}).decode()},
    }


def scripted_reply(tool: bool) -> bytes:
    message: dict[str, object] = {
        "role": "assistant",
        "content": None if tool else "S0 fixture done",
    }
    if tool:
        message["tool_calls"] = [tool_call()]
    return wire(
        {
            "id": "s0-synthetic",
            "object": "chat.completion",
            "created": 0,
            "model": MODEL,
            "choices": [
                {"index": 0, "message": message, "finish_reason": "tool_calls" if tool else "stop"}
            ],
        }
    )


def no_network_guard() -> AbstractAsyncContextManager[Authority]:
    raise AssertionError("S0 must never enter the relay/network guard")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "exemplar",
        "exact_32768",
        "overflow_32769",
        "escaped_result",
        "extra_body",
        "unadmitted_field",
        "foreign_ref",
        "response_exact",
        "response_overflow",
        "network_failure",
        "status_503",
        "cancel",
    ],
)
async def test_agent_sdk_serializes_initial_and_tool_result(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    instructions, user, history = composition()
    prefix = wire({"ref": REF, "observation": 'SYNTHETIC ș漢🙂 \\"\n\t'}).decode()
    result_text = prefix + "x" * (8192 - len(prefix.encode()))
    if mode == "escaped_result":
        result_text = "\x00" * 8192
    assert len(result_text.encode()) == 8192
    if mode in {"exact_32768", "overflow_32769"}:
        remaining = 32768 - len(wire(projection(instructions, user, history, result_text)))
        assert remaining > 0
        user += "🙂" * (remaining // 4) + "x" * (remaining % 4)
        if mode == "overflow_32769":
            user += "x"
    expected = [
        projection(instructions, user, history, None),
        projection(instructions, user, history, result_text),
    ]
    attempts: list[bytes] = []
    accepted: list[bytes] = []
    invoked: list[str] = []
    closed: list[int] = []
    reset: list[bool] = []
    transport = Transport(Path("/nonexistent-s0-fixture"), ssl.create_default_context())
    original = transport.handle_async_request

    async def admitted_request(request: httpx.Request) -> httpx.Response:
        assert CURRENT.get(None) is None
        index = len(attempts)
        assert index < len(expected), "unexpected retry or third turn"
        token = CURRENT.set(
            Permit(
                ENDPOINTS["openrouter"] + "/chat/completions",
                expected[index],
                SECRET,
                no_network_guard,
                131072,
            )
        )
        try:
            attempts.append(await request.aread())
            return await original(request)
        finally:
            CURRENT.reset(token)
            reset.append(CURRENT.get(None) is None)

    class Body:
        def __init__(self, index: int) -> None:
            self.index = index

        async def __aiter__(self) -> AsyncIterator[bytes]:
            raw = scripted_reply(self.index == 0)
            if self.index == 1 and mode in {"response_exact", "response_overflow"}:
                raw += b" " * (131072 - len(raw))
                yield raw
                if mode == "response_overflow":
                    yield b" "
            else:
                yield raw

        async def aclose(self) -> None:
            closed.append(self.index)

    async def sink(request: httpcore.Request) -> httpcore.Response:
        assert isinstance(request.stream, AsyncIterable)
        raw = b"".join([part async for part in request.stream])
        assert request.method == b"POST" and request.url.target == b"/api/v1/chat/completions"
        assert httpx.Headers(request.headers)["accept-encoding"] == "identity"
        assert json.loads(raw) == expected[len(accepted)]
        accepted.append(raw)
        if mode == "network_failure":
            raise httpcore.ReadError("synthetic bounded connection failure")
        if mode == "cancel":
            raise asyncio.CancelledError("synthetic bounded cancellation")
        return httpcore.Response(
            503 if mode == "status_503" else 200,
            headers=[(b"content-type", b"application/json")],
            content=Body(len(accepted) - 1),
        )

    async def read_context(context: object, arguments: str) -> str:
        assert json.loads(arguments) == {"ref": REF}
        invoked.append(arguments)
        if mode == "foreign_ref":
            return result_text.replace(
                "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
            )
        return result_text

    extra: dict[str, object] = {"provider": PROVIDER}
    if mode == "extra_body":
        extra["model"] = "fixture/foreign-model"
    if mode == "unadmitted_field":
        extra["unadmitted"] = {"ref": REF}
    failure: type[BaseException] | None = None
    if mode in {
        "overflow_32769",
        "escaped_result",
        "extra_body",
        "unadmitted_field",
        "foreign_ref",
        "response_overflow",
        "network_failure",
    }:
        failure = APIConnectionError
    elif mode == "status_503":
        failure = InternalServerError
    elif mode == "cancel":
        failure = asyncio.CancelledError

    monkeypatch.setattr(transport, "handle_async_request", admitted_request)
    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    async with httpx.AsyncClient(
        transport=transport,
        trust_env=False,
        follow_redirects=False,
        timeout=300,
        headers={"Accept-Encoding": "identity"},
    ) as http:
        async with AsyncOpenAI(
            api_key=SECRET,
            organization="",
            project="",
            base_url=ENDPOINTS["openrouter"],
            max_retries=0,
            timeout=300,
            http_client=http,
            default_headers={},
        ) as client:
            agent = Agent[None](
                name="S0 inert Brain exemplar",
                instructions=instructions,
                model=OpenAIChatCompletionsModel(model=MODEL, openai_client=client),
                model_settings=ModelSettings(
                    max_tokens=128,
                    parallel_tool_calls=False,
                    store=False,
                    extra_body=extra,
                    retry=ModelRetrySettings(max_retries=0),
                    context_management=None,
                ),
                tools=[
                    FunctionTool(
                        name="read_context",
                        description=DESCRIPTION,
                        params_json_schema=SCHEMA,
                        on_invoke_tool=read_context,
                        strict_json_schema=True,
                    )
                ],
                handoffs=[],
                mcp_servers=[],
            )
            config = RunConfig(tracing_disabled=True, trace_include_sensitive_data=False)
            assert config.model is None and not agent.handoffs and not agent.mcp_servers
            with pytest.raises(failure) if failure else nullcontext() as caught:
                async with asyncio.timeout(10):
                    outcome = await Runner.run(
                        agent,
                        input=[
                            {"role": "user", "content": "What is currently admitted?"},
                            {"role": "assistant", "content": history},
                            {"role": "user", "content": user},
                        ],
                        run_config=config,
                        max_turns=2,
                        session=None,
                    )
                assert failure is None and outcome.final_output == "S0 fixture done"
            if caught is not None and mode not in {"network_failure", "status_503", "cancel"}:
                assert isinstance(caught.value.__cause__, SendDenied)
                reason = "RESPONSE_LIMIT" if mode == "response_overflow" else "FINAL_DATA_DENIED"
                assert str(caught.value.__cause__) == reason
    early = mode in {"extra_body", "unadmitted_field", "network_failure", "status_503", "cancel"}
    denied = mode in {
        "extra_body",
        "unadmitted_field",
        "overflow_32769",
        "escaped_result",
        "foreign_ref",
    }
    assert len(attempts) == (1 if early else 2)
    assert len(accepted) == len(attempts) - int(denied)
    assert len(invoked) == (0 if early else 1)
    assert closed == ([] if mode in {"network_failure", "cancel"} else list(range(len(accepted))))
    assert reset == [True] * len(attempts) and CURRENT.get(None) is None
    assert all(len(raw) <= 32768 for raw in accepted)
    if mode in {"exact_32768", "overflow_32769"}:
        assert len(attempts[1]) == (32768 if mode == "exact_32768" else 32769)
    if mode == "escaped_result":
        assert len(attempts[1]) > 32768
    print(
        "S0_SIZES",
        json.dumps(
            {
                "mode": mode,
                "instructions_utf8": len(instructions.encode()),
                "user_brief_context_utf8": len(user.encode()),
                "history_utf8": len(history.encode()),
                "tool_schema_json": len(wire(SCHEMA)),
                "tool_result_utf8": len(result_text.encode()),
                "wire_attempts": [len(raw) for raw in attempts],
                "sink_calls": len(accepted),
            },
            sort_keys=True,
        ),
    )


@pytest.mark.parametrize("unicode_query", [False, True])
def test_existing_command_http_and_control_envelopes(unicode_query: bool) -> None:
    """Measured existing DTOs, not admission of the absent S1 Needs-you schema."""
    from omnis.modules.settings.provider_catalog_models import CatalogControl, SearchCatalog

    identity = "11111111-1111-4111-8111-111111111111"
    command: KeySettingsControl | CatalogControl
    if unicode_query:
        command = CatalogControl(
            op="provider_catalog",
            request=SearchCatalog(
                action="search",
                connection_id=identity,
                connection_revision=1,
                catalog_command_id=identity,
                query=('ș漢🙂"\\\n' * 32),
            ),
        )
        command_raw = command.model_dump_json().encode()
    else:
        model = ModelSelection(
            connection_id=identity,
            connection_revision=9223372036854775807,
            model=('"\\' * 128),
            output_tokens=65536,
        )
        command = KeySettingsControl(
            op="provider_settings",
            request=SaveSelection(
                action="save_selection",
                command_id=identity,
                expected_revision=9223372036854775807,
                default=model,
                brain=model,
                investigator=model,
                validator=model,
            ),
        )
        command_raw = command.wire_bytes()
    request = ControlRequest(version=1, capability="c" * 64, command=command)
    frame = request.model_dump_json().encode() + b"\n"
    body = httpx.Request(
        "PUT", "http://s0.invalid/measurement-only", json=command.request.model_dump(mode="json")
    ).content
    assert len(command_raw) <= 3600 and len(body) <= 4096 and len(frame) <= 4096
    assert decode_control_frame(frame) == request
    assert json.loads(body) == command.request.model_dump(mode="json")
    with pytest.raises(ValidationError):
        ControlRequest.model_validate({**request.model_dump(mode="json"), "foreign": True})

    # Whitespace proves frame capacity, not a 3600-byte raw-input gate or a Needs-you contract.
    complete_command = command_raw + b" " * (3600 - len(command_raw))
    command_frame = (
        b'{"version":1,"capability":"' + b"c" * 64 + b'","command":' + complete_command + b"}\n"
    )
    assert len(complete_command) == 3600 and len(command_frame) <= 4096
    assert decode_control_frame(command_frame) == request
    exact_frame = frame[:-1] + b" " * (4096 - len(frame)) + b"\n"
    assert len(exact_frame) == 4096 and decode_control_frame(exact_frame) == request
    with pytest.raises(ValueError, match="^Oversized legacy frame$"):
        decode_control_frame(exact_frame[:-1] + b" \n")
    print(
        "S0_IPC_SIZES",
        json.dumps(
            {
                "unicode": unicode_query,
                "command": len(command_raw),
                "http_body": len(body),
                "frame": len(frame),
                "padded_command": len(complete_command),
                "padded_command_frame": len(command_frame),
                "exact_frame": len(exact_frame),
                "overflow_frame": len(exact_frame) + 1,
            },
            sort_keys=True,
        ),
    )
