"""Private managed-task command transport; no native result/DB proof from doubles."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.instance.service import InstanceService


def task_command(action: str = "stage") -> dict[str, object]:
    return {
        "op": "native_task",
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "instance_id": str(uuid4()),
        "expected_generation": 0,
        "expected_epoch": 1,
        "action": action,
        "manifest_ref": {
            "kind": "launch-manifest",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "a" * 64,
        },
    }


@pytest.mark.parametrize("action", ["stage", "release", "receive"])
def test_explicit_managed_task_control_command(action: str) -> None:
    command = task_command(action)
    parsed = ControlRequest.model_validate(
        {"version": 1, "capability": "a" * 64, "command": command}
    )
    assert parsed.command.model_dump(mode="json") == command


@pytest.mark.asyncio
async def test_task_control_dispatch_is_opt_in(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import omnis.transport.local_control as control
    from test_local_control import request

    monkeypatch.setattr(control, "readiness_reason", AsyncMock(return_value=None))
    service = InstanceService(Mock(spec=AsyncEngine))
    async with control.LocalControl(ipc_directory, service, uuid4(), 1) as local:
        reply = await request(ipc_directory, local.capability, task_command())
        assert reply["ok"] is False
        assert reply.get("error") == "TASK_UNAVAILABLE"


@pytest.mark.parametrize("reason", [None, "COMMAND_CONFLICT", "PRIVATE_DETAIL"])
@pytest.mark.asyncio
async def test_task_control_uses_authenticated_existing_socket(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, reason: str | None
) -> None:
    import omnis.transport.local_control as control
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.settings.catalog_models import CatalogError
    from test_local_control import request

    monkeypatch.setattr(control, "readiness_reason", AsyncMock(return_value=None))
    service = InstanceService(Mock(spec=AsyncEngine))
    command = task_command()
    seen: list[dict[str, object]] = []

    async def handle(value: NativeTaskCommand) -> dict[str, object]:
        seen.append(value.model_dump(mode="json"))
        if reason is not None:
            raise CatalogError(reason)
        return {"ok": True}

    async with control.LocalControl(
        ipc_directory, service, uuid4(), 1, native_task=handle
    ) as local:
        denied = await request(ipc_directory, "b" * 64, command)
        assert denied["ok"] is False and not seen
        reply = await request(ipc_directory, local.capability, command)
        assert seen == [command]
        assert reply["ok"] is (reason is None)
        if reason is not None:
            assert reply.get("error") == (
                reason if reason == "COMMAND_CONFLICT" else "TASK_REJECTED"
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("expected_generation", True),
        ("expected_epoch", 1.0),
        ("owner_id", "not-a-uuid"),
        ("action", "launch"),
        ("provider", "ambient"),
        ("manifest_ref", {"kind": "launch-manifest"}),
    ],
)
def test_task_control_refuses_invalid_payload(field: str, value: object) -> None:
    command = {**task_command(), field: value}
    with pytest.raises(ValidationError):
        ControlRequest.model_validate({"version": 1, "capability": "a" * 64, "command": command})


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["release", "receive"])
@pytest.mark.parametrize("status", ["SUCCEEDED", "BLOCKED"])
async def test_method_terminal_reply_reaches_public_reader(
    monkeypatch: pytest.MonkeyPatch, action: str, status: str
) -> None:
    """Real owner reply and reader; stream/private-root doubles, not method proof."""
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.settings import candidate_store as records
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from test_model_preflight_control import consume

    command = NativeTaskCommand.model_validate(task_command(action))
    binding = records.envelope("runtime-binding", {"source_test_only": True})
    owner = NativeTaskOwner(Mock(), Mock(), uuid4(), 1, Mock())
    response = {**owner._reply(command, binding, status), "correlation_id": str(uuid4())}
    assert await consume(monkeypatch, command.model_dump(mode="json"), response) == response


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["SUCCEEDED", "UNKNOWN", None, [], {}])
async def test_stage_reader_does_not_acquire_method_terminal_success(
    monkeypatch: pytest.MonkeyPatch, status: object
) -> None:
    from omnis.modules.instance.schemas import NativeTaskCommand
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.native_tasks import NativeTaskOwner
    from test_model_preflight_control import consume

    command = NativeTaskCommand.model_validate(task_command("stage"))
    binding = records.envelope("runtime-binding", {"source_test_only": True})
    owner = NativeTaskOwner(Mock(), Mock(), uuid4(), 1, Mock())
    response = {**owner._reply(command, binding, "BOUND"), "correlation_id": str(uuid4())}
    response["task_status"] = status
    with pytest.raises(CatalogError, match="^TASK_REJECTED$"):
        await consume(monkeypatch, command.model_dump(mode="json"), response)
