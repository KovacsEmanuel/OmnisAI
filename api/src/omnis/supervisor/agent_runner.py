"""One public SDK step; the owner persists tools and admits every continuation."""

import json
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Literal

import httpx
from agents import (
    Agent,
    AgentOutputSchema,
    FunctionTool,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    set_tracing_disabled,
)
from agents.exceptions import AgentsException
from agents.items import TResponseInputItem
from agents.retry import ModelRetrySettings
from openai import APIError, APIStatusError, AsyncOpenAI, Omit
from pydantic import Field, field_validator

from omnis.modules.runs.model_test_contract import ENDPOINTS
from omnis.modules.runs.model_test_store import digest
from omnis.modules.runs.run_contract import BrainDecision, WorkerFinal
from omnis.modules.settings.provider_key_models import KeyDTO, Provider
from omnis.security.host_origin import reject_json_constant, unique_json_object
from omnis.supervisor.model_relay_protocol import Authority
from omnis.supervisor.model_sender import CURRENT, Permit, SendDenied, Transport, failure_code

READ_DESCRIPTION = "Read only the selected persisted synthetic inert context; no target effects."
READ_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}
ROUTING = {"allow_fallbacks": False, "require_parameters": True}


class Exchange(KeyDTO):
    call_id: str = Field(min_length=1, max_length=128)
    arguments: str = Field(min_length=2, max_length=128)
    result: str = Field(max_length=8192)

    @field_validator("arguments")
    @classmethod
    def empty_object(cls, value: str) -> str:
        if decode(value.encode()) != {}:
            raise ValueError("TOOL_ARGUMENTS_DENIED")
        return value


class StepInput(KeyDTO):
    role: Literal["BRAIN", "RECON"]
    model: str = Field(min_length=1, max_length=256)
    output_tokens: int = Field(ge=1, le=65536)
    provider: Provider
    instructions: str
    input_text: str
    history: list[Exchange] = Field(max_length=1)


class StepResult(KeyDTO):
    kind: Literal["tool", "final"]
    text: str
    call_id: str | None
    arguments: str | None


class ExplicitClient(AsyncOpenAI):
    @property
    def default_headers(self) -> dict[str, str | Omit]:
        # SDK 2.45 merges OPENAI_CUSTOM_HEADERS even with default_headers={}.
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
            "Accept-Encoding": "identity",
        }


def decode(raw: bytes) -> object:
    return json.loads(
        raw, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant
    )


def contains_secret(value: object, secret: str) -> bool:
    if isinstance(value, str):
        return secret in value
    if isinstance(value, list):
        return any(contains_secret(item, secret) for item in value)
    if isinstance(value, dict):
        return any(
            contains_secret(key, secret) or contains_secret(item, secret)
            for key, item in value.items()
        )
    return False


class AgentStep:
    def __init__(self, transport: Transport) -> None:
        set_tracing_disabled(True)
        self.transport = transport

    def projection(self, step: StepInput) -> dict[str, object]:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": step.instructions},
            {"role": "user", "content": step.input_text},
        ]
        for exchange in step.history:
            messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": exchange.call_id,
                                "type": "function",
                                "function": {
                                    "name": "read_context",
                                    "arguments": exchange.arguments,
                                },
                            }
                        ],
                    },
                    {"role": "tool", "tool_call_id": exchange.call_id, "content": exchange.result},
                ]
            )
        body: dict[str, object] = {
            "model": step.model,
            "messages": messages,
            "max_tokens": step.output_tokens,
            "parallel_tool_calls": False,
            "store": False,
            "provider": ROUTING,
        }
        if step.role == "RECON":
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "read_context",
                        "description": READ_DESCRIPTION,
                        "parameters": READ_SCHEMA,
                        "strict": True,
                    },
                }
            ]
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "final_output",
                "strict": True,
                "schema": AgentOutputSchema(
                    BrainDecision if step.role == "BRAIN" else WorkerFinal
                ).json_schema(),
            },
        }
        return body

    async def run(
        self,
        step: StepInput,
        secret: str,
        guard: Callable[[], AbstractAsyncContextManager[Authority]],
        tool: Callable[[str, str, str], Awaitable[str]],
        observe: Callable[[bytes], Awaitable[None]],
        sent: Callable[[], Awaitable[None]],
        *,
        check_data: Callable[[object], Awaitable[None]] | None = None,
    ) -> StepResult:
        async def checked(value: object) -> None:
            if contains_secret(value, secret):
                raise SendDenied("SECRET_ECHO_DENIED")
            if check_data is not None:
                await check_data(value)

        async def checked_text(value: str) -> None:
            await checked(value)
            try:
                parsed = decode(value.encode())
            except ValueError:
                return
            await checked(parsed)

        expected = self.projection(step)
        # Check before SDK input logging, then independently check the final wire body.
        await checked(expected)
        await checked_text(step.input_text)
        for exchange in step.history:
            await checked_text(exchange.result)
        parent = self
        call: Exchange | None = None
        tool_result: str | None = None
        requests = 0

        class Bridge(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                nonlocal call, requests
                requests += 1
                raw = await request.aread()
                if requests != 1 or len(raw) > 32768 or digest(decode(raw)) != digest(expected):
                    raise SendDenied("FINAL_DATA_DENIED")
                await checked(decode(raw))
                token = CURRENT.set(
                    Permit(
                        ENDPOINTS[step.provider] + "/chat/completions",
                        expected,
                        secret,
                        guard,
                        131072,
                    )
                )
                try:
                    await parent.transport.validate_request(request)
                    await sent()
                    response = await parent.transport.handle_async_request(request)
                    try:
                        data = await response.aread()
                        parsed = decode(data)
                        await checked(parsed)
                        choices_data = parsed.get("choices") if isinstance(parsed, dict) else None
                        if isinstance(choices_data, list):
                            for choice in choices_data:
                                message_data = (
                                    choice.get("message") if isinstance(choice, dict) else None
                                )
                                if isinstance(message_data, dict):
                                    content = message_data.get("content")
                                    if isinstance(content, str):
                                        await checked_text(content)
                                    tools = message_data.get("tool_calls")
                                    if isinstance(tools, list):
                                        for item_data in tools:
                                            function_data = (
                                                item_data.get("function")
                                                if isinstance(item_data, dict)
                                                else None
                                            )
                                            if isinstance(function_data, dict):
                                                arguments_data = function_data.get("arguments")
                                                if isinstance(arguments_data, str):
                                                    await checked_text(arguments_data)
                        # Capture safe original usage even when output shape later fails.
                        await observe(data)
                        if response.is_success:
                            if isinstance(parsed, dict) and "error" in parsed:
                                raise SendDenied(failure_code(200, parsed))
                            if not isinstance(parsed, dict) or not isinstance(
                                parsed.get("choices"), list
                            ):
                                raise SendDenied("RESPONSE_SHAPE_DENIED")
                            choices = parsed["choices"]
                            if len(choices) != 1 or not isinstance(choices[0], dict):
                                raise SendDenied("RESPONSE_SHAPE_DENIED")
                            message = choices[0].get("message")
                            if not isinstance(message, dict):
                                raise SendDenied("RESPONSE_SHAPE_DENIED")
                            calls = message.get("tool_calls", [])
                            if (
                                not isinstance(calls, list)
                                or len(calls) > 1
                                or (calls and step.role != "RECON")
                            ):
                                raise SendDenied("TOOL_LIST_DENIED")
                            if choices[0].get("finish_reason") != (
                                "tool_calls" if calls else "stop"
                            ):
                                raise SendDenied("RESPONSE_INCOMPLETE")
                            if calls:
                                item = calls[0]
                                if not isinstance(item, dict) or not isinstance(
                                    item.get("function"), dict
                                ):
                                    raise SendDenied("TOOL_LIST_DENIED")
                                function = item["function"]
                                if (
                                    item.get("type") != "function"
                                    or function.get("name") != "read_context"
                                    or step.history
                                ):
                                    raise SendDenied("TOOL_LIST_DENIED")
                                call_id = item.get("id")
                                if not isinstance(call_id, str):
                                    raise SendDenied("TOOL_LIST_DENIED")
                                arguments = function.get("arguments")
                                if not isinstance(arguments, str):
                                    raise SendDenied("TOOL_LIST_DENIED")
                                call = Exchange(call_id=call_id, arguments=arguments, result="")
                            parsed = {
                                key: parsed[key]
                                for key in ("id", "object", "created", "model")
                                if key in parsed
                            }
                            parsed["choices"] = [
                                {
                                    key: choices[0][key]
                                    for key in ("index", "finish_reason")
                                    if key in choices[0]
                                }
                                | {
                                    "message": {
                                        key: message[key]
                                        for key in ("role", "content", "tool_calls", "refusal")
                                        if key in message
                                    }
                                }
                            ]
                            data = json.dumps(parsed, ensure_ascii=False, allow_nan=False).encode()
                        return httpx.Response(
                            response.status_code, headers=response.headers, content=data
                        )
                    finally:
                        await response.aclose()
                finally:
                    CURRENT.reset(token)

            async def aclose(self) -> None:
                # The supervisor owns the shared transport, not this one-step SDK client.
                return None

        async def invoke(context: object, arguments: str) -> str:
            nonlocal tool_result
            if call is None or arguments != call.arguments or tool_result is not None:
                raise SendDenied("TOOL_AUTHORITY_DENIED")
            tool_result = await tool("read_context", arguments, call.call_id)
            await checked_text(tool_result)
            return tool_result

        inputs: list[TResponseInputItem] = [{"role": "user", "content": step.input_text}]
        for exchange in step.history:
            inputs.extend(
                [
                    {
                        "type": "function_call",
                        "call_id": exchange.call_id,
                        "name": "read_context",
                        "arguments": exchange.arguments,
                    },
                    {
                        "type": "function_call_output",
                        "call_id": exchange.call_id,
                        "output": exchange.result,
                    },
                ]
            )
        set_tracing_disabled(True)
        try:
            async with httpx.AsyncClient(
                transport=Bridge(),
                trust_env=False,
                follow_redirects=False,
                timeout=300,
                headers={"Accept-Encoding": "identity"},
            ) as http:
                async with ExplicitClient(
                    api_key=secret,
                    admin_api_key="",
                    organization="",
                    project="",
                    webhook_secret="",
                    base_url=ENDPOINTS[step.provider],
                    max_retries=0,
                    timeout=300,
                    http_client=http,
                    default_query={},
                    default_headers={},
                ) as client:
                    agent = Agent[None](
                        name=step.role,
                        instructions=step.instructions,
                        model=OpenAIChatCompletionsModel(model=step.model, openai_client=client),
                        model_settings=ModelSettings(
                            max_tokens=step.output_tokens,
                            parallel_tool_calls=False,
                            store=False,
                            extra_body={"provider": ROUTING},
                            retry=ModelRetrySettings(max_retries=0),
                        ),
                        tools=[
                            FunctionTool(
                                name="read_context",
                                description=READ_DESCRIPTION,
                                params_json_schema=READ_SCHEMA,
                                on_invoke_tool=invoke,
                            )
                        ]
                        if step.role == "RECON"
                        else [],
                        output_type=BrainDecision if step.role == "BRAIN" else WorkerFinal,
                        tool_use_behavior="stop_on_first_tool",
                        handoffs=[],
                        mcp_servers=[],
                    )
                    result = await Runner.run(
                        agent,
                        input=inputs,
                        max_turns=1,
                        session=None,
                        run_config=RunConfig(
                            tracing_disabled=True, trace_include_sensitive_data=False
                        ),
                    )
            if call is not None and tool_result is not None:
                return StepResult(
                    kind="tool", text=tool_result, call_id=call.call_id, arguments=call.arguments
                )
            output: object = result.final_output
            if isinstance(output, (BrainDecision, WorkerFinal)):
                output = output.model_dump_json()
            if not isinstance(output, str) or len(output.encode()) > 8192:
                raise SendDenied("FINAL_OUTPUT_DENIED")
            await checked_text(output)
            return StepResult(kind="final", text=output, call_id=None, arguments=None)
        except APIStatusError as error:
            raise SendDenied(failure_code(error.status_code, error.body)) from None
        except APIError as error:
            if isinstance(error.__cause__, SendDenied):
                raise SendDenied(str(error.__cause__)) from None
            raise SendDenied("MODEL_RESPONSE_UNAVAILABLE") from None
        except AgentsException:
            raise SendDenied("MODEL_OUTPUT_DENIED") from None
