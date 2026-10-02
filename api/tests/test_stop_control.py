"""Stop-only IPC contract tests; service IO is substituted, not a PostgreSQL proof."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.instance.service import InstanceService
from omnis.transport.local_control import LocalControl
from test_local_control import request


def arm_command() -> dict[str, object]:
    return {
        "op": "arm_stop",
        "instance_id": str(uuid4()),
        "command_id": str(uuid4()),
        "finalize_command_id": str(uuid4()),
        "generation": 2,
        "owner_epoch": 1,
        "daemon_id": "daemon-a",
        "inventory": {"db": "a" * 64},
    }


@pytest.mark.asyncio
async def test_arm_stop_private_reply_is_a_separate_exact_grant(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = arm_command()
    owner = uuid4()
    service = InstanceService(Mock(spec=AsyncEngine))
    grant = {"version": 1, "state": "STOP_PENDING", "owner_uuid": str(owner), **command}
    del grant["op"]
    arm = AsyncMock(return_value="STOP_PENDING")
    readback = AsyncMock(return_value=grant)
    monkeypatch.setattr(service, "arm_stop", arm)
    monkeypatch.setattr(service, "stop_grant_readback", readback, raising=False)
    monkeypatch.setattr(
        "omnis.transport.local_control.readiness_reason", AsyncMock(return_value=None)
    )
    async with LocalControl(ipc_directory, service, owner, 1) as control:
        reply = await request(ipc_directory, control.capability, command)
    assert reply["ok"] is True
    assert set(reply) == {"ok", "correlation_id", "grant"}
    assert reply.get("grant") == grant
    assert isinstance(command["instance_id"], str)
    assert isinstance(command["command_id"], str)
    assert isinstance(command["finalize_command_id"], str)
    arm.assert_awaited_once_with(
        UUID(command["command_id"]),
        UUID(command["finalize_command_id"]),
        2,
        UUID(command["instance_id"]),
        owner,
        1,
        "daemon-a",
        {"db": "a" * 64},
    )
    assert readback.await_count == 1


@pytest.mark.asyncio
async def test_arm_stop_refuses_epoch_and_capability_before_service(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = InstanceService(Mock(spec=AsyncEngine))
    arm = AsyncMock()
    monkeypatch.setattr(service, "arm_stop", arm)
    monkeypatch.setattr(
        "omnis.transport.local_control.readiness_reason", AsyncMock(return_value=None)
    )
    async with LocalControl(ipc_directory, service, uuid4(), 1) as control:
        bad_epoch = await request(
            ipc_directory, control.capability, {**arm_command(), "owner_epoch": 2}
        )
        bad_cap = await request(ipc_directory, "b" * 64, arm_command())
    assert bad_epoch.get("error") == "LEASE_LOST"
    assert bad_cap.get("error") == "CONTROL_DENIED"
    arm.assert_not_awaited()


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", True),
        ("generation", 2.0),
        ("owner_epoch", False),
        ("owner_epoch", "1"),
        ("owner_uuid", str(uuid4())),
        ("inventory", {}),
        ("inventory", {"inode": 1.0}),
        ("instance_id", "not-a-uuid"),
    ],
)
def test_arm_stop_rejects_invalid_authority(field: str, value: object) -> None:
    valid = arm_command()
    ControlRequest.model_validate({"version": 1, "capability": "a" * 64, "command": valid})
    with pytest.raises(ValidationError):
        ControlRequest.model_validate(
            {
                "version": 1,
                "capability": "a" * 64,
                "command": {**valid, field: value},
            }
        )
