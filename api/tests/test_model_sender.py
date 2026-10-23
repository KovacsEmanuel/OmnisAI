import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpcore
import httpx
import pytest

from omnis.modules.runs.model_test_contract import ACK, ENDPOINTS, Projection
from omnis.supervisor.model_sender import ModelSender, ResponseStream, SendDenied


@asynccontextmanager
async def guard() -> AsyncIterator[None]:
    yield


@pytest.mark.asyncio
async def test_refused_owned_socket_is_a_normal_metadata_outage(tmp_path: Path) -> None:
    sender = ModelSender(tmp_path / "missing")
    try:
        with pytest.raises(SendDenied, match="^METADATA_UNAVAILABLE$"):
            await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            "fixture-secret",
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        assert reply.result_state == "UNKNOWN" and reply.reason == "RESULT_UNKNOWN"
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [httpcore.ReadError, httpcore.RemoteProtocolError, httpcore.ReadTimeout]
)
async def test_streaming_outage_is_sanitized(error: type[Exception]) -> None:
    async def broken() -> AsyncIterator[bytes]:
        yield b"{"
        raise error("private diagnostic must not escape")

    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, stream=ResponseStream(httpcore.Response(200, content=broken()), 131072)
            )
        )
    )
    try:
        with pytest.raises(SendDenied, match="^METADATA_UNAVAILABLE$"):
            await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            "fixture-secret",
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        assert reply.result_state == "UNKNOWN" and reply.reason == "RESULT_UNKNOWN"
    finally:
        await sender.close()


@pytest.mark.asyncio
async def test_metadata_does_not_swallow_control_failures_or_cancellation() -> None:
    sender = ModelSender(Path("/nonexistent-owned-fixture"))

    async def fail(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("control failure")

    await sender.http.aclose()
    sender.http = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    try:
        with pytest.raises(RuntimeError, match="control failure"):
            await sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        task = asyncio.create_task(
            sender.metadata(ENDPOINTS["openrouter"], "fixture-secret", guard)
        )
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("length,offset", [(512, 0), (31, 250)])
async def test_redacts_before_bounding_response_identifiers(length: int, offset: int) -> None:
    secret = "canary-" + "Z" * (length - 7)
    echoed = "x" * offset + secret
    payload = {
        "id": echoed,
        "model": echoed,
        "object": "chat.completion",
        "created": 0,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": ACK}, "finish_reason": "stop"}
        ],
    }
    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(payload))
        )
    )
    try:
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            secret,
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        leaked = any(secret[:6] in (value or "") for value in (reply.model, reply.response_id))
        assert not leaked
        assert reply.result_state == "COMPLETED"
    finally:
        await sender.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("component", ["prompt_tokens", "completion_tokens", "reasoning_tokens"])
@pytest.mark.parametrize("value", [-1, 9007199254740992, True, "9", 1.5])
async def test_original_usage_is_not_coerced(component: str, value: object) -> None:
    usage = {
        "prompt_tokens": 9,
        "completion_tokens": 7,
        "total_tokens": 16,
        "completion_tokens_details": {"reasoning_tokens": 2},
    }
    if component == "reasoning_tokens":
        usage["completion_tokens_details"] = {"reasoning_tokens": value}
    else:
        usage[component] = value
    payload = {
        "id": "fixture",
        "model": "fixture/model",
        "object": "chat.completion",
        "created": 0,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": ACK}, "finish_reason": "stop"}
        ],
        "usage": usage,
    }
    sender = ModelSender(Path("/nonexistent-owned-fixture"))
    await sender.http.aclose()
    sender.http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(payload))
        )
    )
    try:
        reply = await sender.send(
            ENDPOINTS["openrouter"],
            "fixture-secret",
            Projection(model="fixture/model", output_tokens=64),
            guard,
        )
        assert reply.result_state == "COMPLETED"
        assert (
            getattr(
                reply,
                {
                    "prompt_tokens": "input_tokens",
                    "completion_tokens": "output_tokens",
                    "reasoning_tokens": "reasoning_tokens",
                }[component],
            )
            is None
        )
        assert reply.reason == "USAGE_INVALID"
    finally:
        await sender.close()
