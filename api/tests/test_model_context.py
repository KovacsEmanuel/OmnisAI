"""Behavior at the existing owner/RPC, not a standalone schema or native authority seed."""

import asyncio
import importlib
import json
import os
import struct
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import native_preparation
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping
from omnis.supervisor import native_tasks
from omnis.supervisor.runtime_client import RuntimeClient
from omnis.transport import control_probe
from test_model_admission import (
    test_qualified_projection_reaches_cold_admission_without_model_reservation as old_journey,
)


@pytest.mark.asyncio
async def test_existing_owner_sends_qualified_selection_and_derived_purpose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = RuntimeClient.managed
    seen: list[object] = []

    async def observed(
        self: RuntimeClient,
        service: InstanceService,
        owner: UUID,
        operation: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if operation == "task_model_preflight":
            assert "model_context" in payload, "real owner RPC omits qualified selection/purpose"
            context = mapping(payload["model_context"])
            assert context["purpose"] == "SUPPORT"
            selected = mapping(mapping(context["selection"])["payload"])
            assert selected["resolution"] == "NO_MODEL"
            assert selected["effective"] is None
            seen.append(context)
        return await original(self, service, owner, operation, payload)

    monkeypatch.setattr(RuntimeClient, "managed", observed)
    await old_journey(tmp_path, monkeypatch)
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_rpc_context_denies_purpose_and_effective_forgery_after_redigest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = RuntimeClient.managed
    seen: list[dict[str, object]] = []

    async def capture(
        self: RuntimeClient,
        service: InstanceService,
        owner: UUID,
        operation: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if operation == "task_model_preflight":
            seen.append(deepcopy(payload))
        return await original(self, service, owner, operation, payload)

    monkeypatch.setattr(RuntimeClient, "managed", capture)
    await old_journey(tmp_path, monkeypatch)
    adapter = importlib.import_module("omnis_hermes.model_admission")
    for key, value in (
        ("purpose", "VALIDATION"),
        ("effective", {"model": "UNTRUSTED"}),
        ("recipe_role", "VALIDATOR"),
        ("version", True),
    ):
        poisoned = deepcopy(seen[0])
        context = mapping(poisoned["model_context"])
        context[key] = value
        poisoned["model_context"] = context
        poisoned["model_context_digest"] = sha256(canonical(context)).hexdigest()
        with pytest.raises(ValueError):
            adapter.validate_preflight(poisoned)


@pytest.mark.asyncio
async def test_private_reader_accepts_actual_full_owner_echo_and_refuses_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[tuple[dict[str, object], dict[str, object]]] = []
    original = native_tasks.NativeTaskOwner.handle

    async def capture(self: native_tasks.NativeTaskOwner, command: object) -> dict[str, object]:
        from omnis.modules.instance.schemas import NativeTaskCommand

        assert isinstance(command, NativeTaskCommand)
        answer = await original(self, command)
        observed.append((command.model_dump(mode="json"), answer))
        return answer

    monkeypatch.setattr(native_tasks.NativeTaskOwner, "handle", capture)
    await old_journey(tmp_path, monkeypatch)
    command, answer = observed[0]
    response = {**answer, "correlation_id": str(uuid4())}
    frame = json.dumps(response).encode() + b"\n"  # actual LocalControl encoding
    socket_double = Mock()
    socket_double.getsockopt.return_value = struct.pack("3i", os.getpid(), os.getuid(), os.getgid())

    async def drain() -> None:
        pass

    writer = SimpleNamespace(
        get_extra_info=lambda key: socket_double,
        write=lambda data: None,
        drain=drain,
        close=lambda: None,
        wait_closed=drain,
    )

    async def connect(path: object, *, limit: int) -> tuple[asyncio.StreamReader, object]:
        reader = asyncio.StreamReader(limit=limit)
        reader.feed_data(frame)
        reader.feed_eof()
        return reader, writer

    monkeypatch.setattr(native_preparation, "existing_private_root", lambda path: None)
    monkeypatch.setattr(control_probe, "_read_capability", lambda path: "0" * 64)
    monkeypatch.setattr(asyncio, "open_unix_connection", connect)
    assert len(frame) > 4096
    assert await native_tasks.control_task(tmp_path, command) == response
    frame = b"x" * (native_tasks.NATIVE_TASK_REPLY_MAX_BYTES + 1) + b"\n"
    from omnis.modules.settings.catalog_models import CatalogError

    with pytest.raises(CatalogError, match="TASK_REJECTED"):
        await native_tasks.control_task(tmp_path, command)
