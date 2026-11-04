"""Known synthetic credentials at the real SDK DATA boundary; no external IO."""

import json
import ssl
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import httpcore
import pytest

from omnis.modules.runs.run_contract import BrainDecision
from omnis.supervisor.agent_runner import AgentStep, StepInput
from omnis.supervisor.model_relay_protocol import Authority
from omnis.supervisor.model_sender import CURRENT, SendDenied, Transport


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["plain", "escaped", "request", "peer", "peer_request", "metadata", "safe"]
)
async def test_sdk_denies_parsed_known_credentials_before_observation(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    secret = "SYNTHETIC-BRAIN-CREDENTIAL-NOT-A-REAL-KEY"
    peer = "SYNTHETIC-RECON-CREDENTIAL-NOT-A-REAL-KEY"

    async def check_data(value: object) -> None:
        from omnis.supervisor.agent_runner import contains_secret

        if contains_secret(value, peer):
            raise SendDenied("SECRET_ECHO_DENIED")

    transport = Transport(Path("/nonexistent-data-source"), ssl.create_default_context())
    wires: list[bytes] = []
    observations: list[bytes] = []
    sent_calls: list[bool] = []
    closed: list[bool] = []
    output = BrainDecision(
        action="delegate",
        summary="Synthetic safe context",
        consumed_refs=[],
        detail=secret
        if mode in {"plain", "escaped"}
        else peer
        if mode == "peer"
        else "No credential here",
    ).model_dump_json()
    if mode == "escaped":
        output = output.replace(secret, "".join(f"\\u{ord(c):04x}" for c in secret))

    class Body:
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield json.dumps(
                {
                    "id": "scripted",
                    "object": "chat.completion",
                    "created": 0,
                    "model": peer if mode == "metadata" else "fixture/brain",
                    "usage": {"prompt_tokens": "uncoerced"},
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": output,
                            },
                        }
                    ],
                }
            ).encode()

        async def aclose(self) -> None:
            closed.append(True)

    async def sink(request: httpcore.Request) -> httpcore.Response:
        assert isinstance(request.stream, AsyncIterable)
        wires.append(b"".join([part async for part in request.stream]))
        return httpcore.Response(
            200, headers=[(b"content-type", b"application/json")], content=Body()
        )

    async def observe(raw: bytes) -> None:
        observations.append(raw)
        assert json.loads(raw)["usage"]["prompt_tokens"] == "uncoerced"

    async def sent() -> None:
        sent_calls.append(True)

    async def tool(name: str, arguments: str, call_id: str) -> str:
        raise AssertionError("No tools in Brain")

    def guard() -> AbstractAsyncContextManager[Authority]:
        raise AssertionError("No physical relay in SOURCE")

    step = StepInput(
        role="BRAIN",
        model="fixture/brain",
        output_tokens=128,
        provider="openrouter",
        instructions="Synthetic inert",
        input_text=secret if mode == "request" else peer if mode == "peer_request" else "Inert",
        history=[],
    )
    monkeypatch.setattr(transport.pool, "handle_async_request", sink)
    try:
        if mode == "safe":
            result = await AgentStep(transport).run(
                step, secret, guard, tool, observe, sent, check_data=check_data
            )
            assert (
                BrainDecision.model_validate_json(result.text).summary == "Synthetic safe context"
            )
            assert len(observations) == 1
        else:
            with pytest.raises(SendDenied, match="SECRET_ECHO_DENIED|FINAL_DATA_DENIED"):
                await AgentStep(transport).run(
                    step, secret, guard, tool, observe, sent, check_data=check_data
                )
            assert observations == []
        assert len(wires) == (0 if mode in {"request", "peer_request"} else 1)
        assert len(sent_calls) == len(wires) == len(closed)
        assert CURRENT.get(None) is None
    finally:
        await transport.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["BRAIN", "RECON"])
async def test_owner_rejects_peer_credential_before_result_event_or_worker(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import AsyncConnection

    from omnis.modules.runs import model_test_store as records
    from omnis.modules.runs import run_store as store
    from omnis.modules.runs.run_contract import Attempt, Setup, WorkerFinal
    from omnis.modules.runs.run_runtime import AgentRunOwner
    from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
    from omnis.modules.settings.provider_vault import ProviderVault
    from test_run_owner_source import fixture_run, fixture_setup_payload

    run = fixture_run()
    snapshot = Setup.model_validate(fixture_setup_payload())
    peer = snapshot.recon.connection.model_copy(
        update={
            "provider": "orcarouter",
            "connection_id": str(uuid4()),
            "secret_id": str(uuid4()),
        }
    )
    snapshot = snapshot.model_copy(
        update={
            "recon": snapshot.recon.model_copy(update={"connection": peer}),
        }
    )
    secret = "SYNTHETIC-PEER-KEY-NOT-A-REAL-CREDENTIAL"
    owner = object.__new__(AgentRunOwner)
    owner.instance = run.instance_id
    owner.settings = object.__new__(ProviderSettingsOwner)
    owner.settings.vault = object.__new__(ProviderVault)
    monkeypatch.setattr(ProviderSettingsOwner, "connections", AsyncMock(return_value=[peer]))
    monkeypatch.setattr(ProviderVault, "get", lambda self, ref: secret)
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    put, event, child = (
        AsyncMock(return_value=run.setup_ref),
        AsyncMock(return_value=1),
        AsyncMock(return_value=run),
    )
    monkeypatch.setattr(records, "put", put)
    monkeypatch.setattr(store, "event", event)
    monkeypatch.setattr(AgentRunOwner, "new_attempt", child)
    monkeypatch.setattr(store, "consume", AsyncMock())
    monkeypatch.setattr(store, "question", AsyncMock(return_value=None))
    monkeypatch.setattr(store, "save_run", AsyncMock())
    monkeypatch.setattr(store, "save_attempt", AsyncMock())
    monkeypatch.setattr(store, "add_inbox", AsyncMock())
    actor = Attempt.model_validate(
        {
            "instance_id": run.instance_id,
            "run_id": run.run_id,
            "task_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "role": role,
            "parent_task_id": None,
            "state": "RUNNING",
            "brief": "Inert",
            "input_refs": [],
            "input_text": "Inert",
            "instructions": "Inert",
            "configured_model": "fixture/brain",
            "skill_refs": [],
            "correction_count": 1,
        }
    )
    output = (
        BrainDecision(action="delegate", summary=secret, detail=secret, consumed_refs=[])
        if role == "BRAIN"
        else WorkerFinal(summary=secret, consumed_refs=[], gaps=[])
    ).model_dump_json()
    with pytest.raises(SendDenied, match="SECRET_ECHO_DENIED"):
        await owner.complete(object.__new__(AsyncConnection), run, actor, output, None)
    assert not put.called and not event.called and not child.called
