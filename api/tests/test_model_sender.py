import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from omnis.modules.runs.model_test_contract import ACK, ENDPOINTS, Projection
from omnis.supervisor.model_sender import ModelSender


@asynccontextmanager
async def guard() -> AsyncIterator[None]:
    yield


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
