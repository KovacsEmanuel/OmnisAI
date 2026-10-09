"""Supervisor orchestration order; domain/runtime doubles are not PG/native proof."""

import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings import candidate_store as records
from omnis.modules.tasks.managed_contract import mapping, sequence
from omnis.supervisor.runtime_client import RuntimeClient
from test_managed_contract import manifest as manifest_fixture
from test_managed_contract import stage


def module() -> ModuleType:
    try:
        return importlib.import_module("omnis.supervisor.native_tasks")
    except ModuleNotFoundError:
        pytest.fail("managed supervisor consumer absent")


@pytest.mark.asyncio
@pytest.mark.parametrize("composed", [False, True])
async def test_stage_commit_precedes_any_release(
    monkeypatch: pytest.MonkeyPatch, composed: bool
) -> None:
    consumer = module()
    manifest = manifest_fixture()
    if composed:
        # Domain double: native schema/material checks are separate real-consumer probes.
        body = mapping(manifest["payload"])
        body["entries"] = [
            {
                **mapping(entry),
                "composition_ref": records.reference(records.envelope("prompt-composition", {})),
            }
            for entry in sequence(body["entries"])
        ]
        manifest = records.envelope("launch-manifest", {**body, "composition_version": 1})
    owner, instance = uuid4(), str(uuid4())
    events: list[str] = []
    reference = records.reference(manifest)
    command = NativeTaskCommand(
        op="native_task",
        schema_version=1,
        owner_id=str(uuid4()),
        command_id=str(uuid4()),
        instance_id=instance,
        expected_generation=0,
        expected_epoch=1,
        action="stage",
        manifest_ref=reference,
    )
    domain = Mock()
    domain.readback = AsyncMock(
        return_value={
            "manifest_ref": reference,
            "manifest": manifest,
            "binding": None,
            "results": [],
            "stage_started": False,
            "release_started": False,
        }
    )
    domain.reserve_dispatch = AsyncMock(return_value=manifest)
    expected_payload: dict[str, object] = {
        "protocol": "omnis-managed-admission-v1",
        "manifest": manifest,
    }
    if composed:
        expected_payload = {
            "protocol": "omnis-managed-admission-v2",
            "manifest": manifest,
            "compositions": [records.envelope("prompt-composition", {})],
        }

    async def stage_payload(*args: object) -> dict[str, object]:
        assert domain.reserve_dispatch.await_count == 0
        return expected_payload

    domain.stage_payload = AsyncMock(side_effect=stage_payload)
    bound = records.envelope("runtime-binding", {})
    domain.commit_binding = AsyncMock(return_value=bound)
    connection = Mock(spec=AsyncConnection)
    identity = Mock()
    identity.scalar_one.return_value = instance
    connection.execute = AsyncMock(return_value=identity)
    service = Mock(spec=InstanceService)
    service.engine = Mock(spec=AsyncEngine)

    @asynccontextmanager
    async def fence(*args: object) -> AsyncIterator[AsyncConnection]:
        events.append("begin")
        yield connection
        events.append("commit")

    service.native_preparation_commit = fence
    runtime = RuntimeClient(Path("/unused"), generation=0, epoch=1)
    runtime.boot = str(uuid4())

    async def managed(*args: object) -> dict[str, object]:
        assert events == ["begin", "commit"]
        assert args[2] == "task_stage"
        assert args[3] == expected_payload
        events.append("native-stage")
        return stage(manifest)

    monkeypatch.setattr(runtime, "managed", managed)
    handler = consumer.NativeTaskOwner(domain, service, owner, 1, runtime)
    reply = await handler.handle(command)
    assert reply["ok"] is True
    assert reply["binding_ref"] == records.reference(bound)
    assert events == ["begin", "commit", "native-stage", "begin", "commit"]
    assert domain.reserve_dispatch.await_args.args[-1] == "stage"
    assert domain.stage_payload.await_count == int(composed)
    assert mapping(domain.commit_binding.await_args.args[3])["status"] == "STAGED"
