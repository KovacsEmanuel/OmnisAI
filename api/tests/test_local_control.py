import asyncio
import json
import os
import secrets
import stat
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Required, TypedDict
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ConfigDict, TypeAdapter, ValidationError, with_config
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlCode, ControlConflict, InstanceStatus
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import SessionStore


@with_config(ConfigDict(extra="allow"))
class ControlStatus(TypedDict):
    instance_id: str
    generation: int
    admission_open: bool
    shutdown_command_id: str | None
    quiesced_generation: int | None
    supervisor_epoch: int
    supervisor_ready: bool
    shutdown_finalized: bool
    assessment_ready: bool
    dashboard_ready: bool


@with_config(ConfigDict(extra="allow"))
class ControlReply(TypedDict, total=False):
    ok: Required[bool]
    correlation_id: Required[str]
    error: str
    status: ControlStatus
    result_generation: int | None
    command_id: str
    expected_generation: int
    owner_epoch: int


CONTROL_REPLY = TypeAdapter(ControlReply)


@pytest.mark.parametrize("admission_open", [True, False])
@pytest.mark.asyncio
async def test_pairing_issuer_uses_instance_transaction_before_write(
    monkeypatch: pytest.MonkeyPatch, admission_open: bool
) -> None:
    """The DB integration test below proves the same ordering on PostgreSQL."""
    engine = Mock(spec=AsyncEngine)
    service = InstanceService(engine)
    identity, owner, issuance = uuid4(), uuid4(), uuid4()
    connection = object()

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[object, SimpleNamespace, object]]:
        yield (
            connection,
            SimpleNamespace(
                instance_id=identity, admission_open=admission_open, shutdown_command_id=None
            ),
            object(),
        )

    owner_check = AsyncMock()
    register = AsyncMock()
    monkeypatch.setattr(service, "_locked", locked)
    monkeypatch.setattr(service, "_require_owner", owner_check)
    monkeypatch.setattr(SessionStore, "register_on", register, raising=False)
    if admission_open:
        await service.register_pairing(identity, "a" * 64, issuance, owner, 1)
        register.assert_awaited_once_with(connection, "a" * 64, issuance_id=issuance)
    else:
        with pytest.raises(ControlConflict, match="INSTANCE_SHUTTING_DOWN"):
            await service.register_pairing(identity, "a" * 64, issuance, owner, 1)
        register.assert_not_awaited()
    assert owner_check.await_count == (2 if admission_open else 1)


@pytest.mark.asyncio
async def test_pairing_issuer_rechecks_lease_after_challenge_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = Mock(spec=AsyncEngine)
    service = InstanceService(engine)
    identity, owner, issuance = uuid4(), uuid4(), uuid4()
    connection = object()

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[object, SimpleNamespace, object]]:
        yield (
            connection,
            SimpleNamespace(instance_id=identity, admission_open=True, shutdown_command_id=None),
            object(),
        )

    owner_check = AsyncMock(side_effect=[None, ControlConflict(ControlCode.LEASE_LOST)])
    register = AsyncMock()
    monkeypatch.setattr(service, "_locked", locked)
    monkeypatch.setattr(service, "_require_owner", owner_check)
    monkeypatch.setattr(SessionStore, "register_on", register)
    with pytest.raises(ControlConflict, match="LEASE_LOST"):
        await service.register_pairing(identity, "a" * 64, issuance, owner, 1)
    register.assert_awaited_once_with(connection, "a" * 64, issuance_id=issuance)
    assert owner_check.await_count == 2


async def request(
    directory: Path, capability: str, command: Mapping[str, object], **extra: object
) -> ControlReply:
    reader, writer = await asyncio.open_unix_connection(str(directory / "control.sock"))
    try:
        writer.write(
            json.dumps(
                {"version": 1, "capability": capability, "command": command, **extra}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        return CONTROL_REPLY.validate_json(
            await asyncio.wait_for(reader.readline(), 5), strict=True
        )
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.parametrize("case", ["valid", "not_object", "missing_id", "boolean", "generation"])
@pytest.mark.asyncio
async def test_request_validates_reply_without_discarding_evidence(
    ipc_directory: Path, case: str
) -> None:
    status: dict[str, object] = {
        "instance_id": str(uuid4()),
        "generation": 1,
        "admission_open": False,
        "shutdown_command_id": None,
        "quiesced_generation": None,
        "supervisor_epoch": 1,
        "supervisor_ready": True,
        "shutdown_finalized": False,
        "assessment_ready": False,
        "dashboard_ready": False,
        "unexpected_status_evidence": "synthetic-secret-marker",
    }
    payload: dict[str, object] = {
        "ok": True,
        "correlation_id": str(uuid4()),
        "result_generation": 1,
        "status": status,
        "unexpected_evidence": "synthetic-secret-marker",
    }
    if case == "missing_id":
        del payload["correlation_id"]
    elif case == "boolean":
        payload["ok"] = 1
    elif case == "generation":
        status["generation"] = "1"
    frame = json.dumps([] if case == "not_object" else payload).encode() + b"\n"

    async def respond(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await asyncio.wait_for(reader.readline(), 5)
            writer.write(frame)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async with await asyncio.start_unix_server(respond, path=str(ipc_directory / "control.sock")):
        if case == "valid":
            # Unknown keys must survive decoding: filtering could hide leaked secrets.
            assert await request(ipc_directory, "synthetic-capability", {"op": "status"}) == payload
        else:
            with pytest.raises(ValidationError):
                await request(ipc_directory, "synthetic-capability", {"op": "status"})


@pytest.mark.asyncio
async def test_lifecycle_reply_cannot_mix_an_open_receipt_with_a_later_shutdown(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL, ipc_directory: Path
) -> None:
    """A separate status transaction can report another command's generation."""
    from omnis.transport.local_control import LocalControl

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        async with LocalControl(ipc_directory, service, owner, epoch):
            capability = (ipc_directory / "control.cap").read_text()
            identity = (await service.owned_status(owner, epoch)).instance_id
            original = service.status

            async def interleaved_status() -> InstanceStatus:
                await service.shutdown(uuid4(), 1, owner, epoch)
                return await original()

            monkeypatch.setattr(service, "status", interleaved_status)
            command_id = uuid4()
            reply = await request(
                ipc_directory,
                capability,
                {
                    "op": "open",
                    "instance_id": str(identity),
                    "command_id": str(command_id),
                    "expected_generation": 0,
                },
            )
            assert reply["ok"] is True
            status = reply.get("status")
            assert status is not None
            assert reply.get("command_id") == str(command_id)
            assert reply.get("expected_generation") == 0
            assert reply.get("result_generation") == status["generation"] == 1
            assert reply.get("owner_epoch") == status["supervisor_epoch"] == epoch
            assert status["admission_open"] is True
            current = await original()
            assert current.generation == 1 and current.admission_open is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_unix_control_peer_capability_and_allowlist(
    migrated_database_url: URL, ipc_directory: Path
) -> None:
    from omnis.transport.local_control import LocalControl

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    try:
        async with LocalControl(ipc_directory, service, owner, epoch):
            capability = (ipc_directory / "control.cap").read_text()
            for name in ("control.sock", "control.cap", "control.lock"):
                assert stat.S_IMODE((ipc_directory / name).stat().st_mode) == 0o600
            denied = await request(ipc_directory, secrets.token_hex(32), {"op": "status"})
            assert denied["ok"] is False and denied["error"] == "CONTROL_DENIED"
            assert UUID(denied["correlation_id"]).version == 4
            accepted = await request(ipc_directory, capability, {"op": "status"})
            assert accepted["ok"] and accepted["status"]["admission_open"] is False
            assert capability not in json.dumps(accepted)
            assert (await request(ipc_directory, capability, {"op": "exec", "argv": ["id"]}))[
                "error"
            ] == "INVALID_REQUEST"
            assert (await request(ipc_directory, capability, {"op": "status"}, arbitrary="denied"))[
                "error"
            ] == "INVALID_REQUEST"
            instance_id = accepted["status"]["instance_id"]
            opened = await request(
                ipc_directory,
                capability,
                {
                    "op": "open",
                    "instance_id": instance_id,
                    "command_id": str(uuid4()),
                    "expected_generation": 0,
                },
            )
            assert opened["ok"] and opened["result_generation"] == 1
            stale = await request(
                ipc_directory,
                capability,
                {
                    "op": "shutdown",
                    "instance_id": instance_id,
                    "command_id": str(uuid4()),
                    "expected_generation": 0,
                },
            )
            assert stale["error"] == "GENERATION_CONFLICT"
            first_stop = str(uuid4())
            closed = await request(
                ipc_directory,
                capability,
                {
                    "op": "shutdown",
                    "instance_id": instance_id,
                    "command_id": first_stop,
                    "expected_generation": 1,
                },
            )
            assert closed["ok"] and closed.get("result_generation") == 2
            closed_status = closed.get("status")
            assert closed_status is not None and closed_status["shutdown_command_id"] == first_stop
            second_stop = str(uuid4())
            mixed = await request(
                ipc_directory,
                capability,
                {
                    "op": "shutdown",
                    "instance_id": instance_id,
                    "command_id": second_stop,
                    "expected_generation": 2,
                },
            )
            assert mixed.get("error") == "COMMAND_CONFLICT", (
                "Second stop must not attest first intent"
            )
            async with engine.connect() as connection:
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM instance_command WHERE command_id = :id"),
                        {"id": second_stop},
                    )
                ).scalar_one() == 0
        assert not (ipc_directory / "control.sock").exists()
        assert not (ipc_directory / "control.cap").exists()
        # Exercise SO_PEERCRED denial on the same real socket/positive channel.
        async with LocalControl(ipc_directory, service, owner, epoch, peer_uid=os.getuid() + 1):
            capability = (ipc_directory / "control.cap").read_text()
            denied = await request(ipc_directory, capability, {"op": "status"})
            assert denied["error"] == "CONTROL_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_refuses_unsafe_directory_and_foreign_files(
    migrated_database_url: URL, ipc_directory: Path
) -> None:
    from omnis.transport.local_control import LocalControl

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    try:
        ipc_directory.chmod(0o755)
        with pytest.raises(ValueError, match="private"):
            async with LocalControl(ipc_directory, service, owner, epoch):
                pytest.fail("unsafe directory accepted")
        ipc_directory.chmod(0o700)
        other = ipc_directory / "untouched"
        other.write_text("not-a-socket")
        (ipc_directory / "control.sock").symlink_to(other)
        with pytest.raises(ValueError, match="socket"):
            async with LocalControl(ipc_directory, service, owner, epoch):
                pytest.fail("symlink socket adopted")
        assert other.read_text() == "not-a-socket"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_frames_are_bounded_and_duplicate_keys_rejected(
    migrated_database_url: URL, ipc_directory: Path
) -> None:
    from omnis.transport.local_control import LocalControl

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    try:
        async with LocalControl(ipc_directory, service, owner, epoch):
            for payload in (b"x" * 5000 + b"\n", b'{"version":1,"version":1}\n'):
                reader, writer = await asyncio.open_unix_connection(
                    str(ipc_directory / "control.sock")
                )
                writer.write(payload)
                await writer.drain()
                response = CONTROL_REPLY.validate_json(
                    await asyncio.wait_for(reader.readline(), 4), strict=True
                )
                assert response["error"] == "INVALID_REQUEST"
                writer.close()
                await writer.wait_closed()
    finally:
        await engine.dispose()


def test_private_directory_rejects_replaceable_ancestor(ipc_directory: Path) -> None:
    from omnis.core.paths import private_directory

    parent = ipc_directory / "shared"
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    child = parent / "private"
    child.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="ancestor"):
        private_directory(child)


@pytest.mark.asyncio
async def test_cancelled_socket_startup_leaves_no_listener(
    migrated_database_url: URL, ipc_directory: Path
) -> None:
    from omnis.transport.local_control import LocalControl

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    control = LocalControl(ipc_directory, service, owner, epoch)
    try:
        startup = asyncio.create_task(control.__aenter__())
        await asyncio.sleep(0)
        startup.cancel()
        with pytest.raises(asyncio.CancelledError):
            await startup
        assert not (ipc_directory / "control.sock").exists()
        assert not (ipc_directory / "control.cap").exists()
        async with LocalControl(ipc_directory, service, owner, epoch):
            capability = (ipc_directory / "control.cap").read_text()
            assert (await request(ipc_directory, capability, {"op": "status"}))["ok"]
    finally:
        await control.__aexit__(None, None, None)
        await engine.dispose()
