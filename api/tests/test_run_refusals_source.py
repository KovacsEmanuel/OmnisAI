"""Actual private dispatcher/bridge/public route; synthetic streams, no sockets."""

import asyncio
import json
import os
import struct
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from starlette.responses import JSONResponse

from omnis.modules.runs import model_test_routes, run_routes
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.runs.run_contract import Question, RunControl
from omnis.transport import local_control
from omnis.transport.local_control import LocalControl
from test_run_controls_source import Owned, command
from test_run_controls_source import owned as owned
from test_run_routes_source import request_with_body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        "DATA_DENIED",
        "CONNECTION_UNAVAILABLE",
        "OPERATION_FINISHED",
        "MODEL_NOT_REGISTERED",
        "UNRECOGNIZED",
        "NETWORK",
    ],
)
async def test_definite_owner_refusal_survives_private_and_public_adapters(
    owned: Owned, monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    sentinel = "synthetic-unused-key"
    owned.question = Question(
        question_id=str(uuid4()),
        run_id=owned.run.run_id,
        task_id=str(uuid4()),
        revision=1,
        cause="Clarify",
        text="Which context?",
        refs=[],
        state="PENDING",
    )
    request = command(owned, "answer", question_id=owned.question.question_id, answer=sentinel)
    control = object.__new__(LocalControl)
    control.service = owned.owner.service
    control.agent_run = (
        owned.owner.handle if code == "DATA_DENIED" else AsyncMock(side_effect=ModelConflict(code))
    )
    if code == "DATA_DENIED":
        from omnis.modules.runs.run_contract import Setup
        from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
        from test_run_owner_source import fixture_setup_payload

        connection = Setup.model_validate(fixture_setup_payload()).brain.connection
        monkeypatch.setattr(
            ProviderSettingsOwner, "connections", AsyncMock(return_value=[connection])
        )
    monkeypatch.setattr(local_control, "readiness_reason", AsyncMock(return_value=None))
    private = await control._dispatch(request)
    assert private == {"ok": False, "error": code}
    assert owned.writes == []
    reader, writer, peer = Mock(), Mock(), Mock()
    reader.readuntil = AsyncMock(return_value=json.dumps(private).encode() + b"\n")
    writer.drain, writer.wait_closed = AsyncMock(), AsyncMock()
    peer.getsockopt.return_value = struct.pack("3i", 0, os.getuid(), os.getgid())
    writer.get_extra_info.return_value = peer
    connect = AsyncMock(return_value=(reader, writer))
    if code == "NETWORK":
        connect.side_effect = OSError("synthetic transport failure")
    monkeypatch.setenv("OMNIS_CONTROL_DIR", "/nonexistent-refusal-source")
    monkeypatch.setattr(model_test_routes, "_read_capability", lambda path: "a" * 64)
    monkeypatch.setattr(asyncio, "open_unix_connection", connect)
    assert isinstance(request, RunControl)
    response = await run_routes.mutate(
        request_with_body(request.request.model_dump_json().encode()), request.request
    )
    assert isinstance(response, JSONResponse)
    expected = "CONTROL_UNAVAILABLE" if code in {"NETWORK", "UNRECOGNIZED"} else code
    assert response.status_code == (503 if expected == "CONTROL_UNAVAILABLE" else 409)
    assert json.loads(bytes(response.body))["error"]["code"] == expected
    assert sentinel not in bytes(response.body).decode()
    assert owned.writes == []
