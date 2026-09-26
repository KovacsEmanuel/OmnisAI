import asyncio
import json
import os
import secrets
import socket
import stat
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService


async def request(directory, capability, command, **extra):
    reader, writer = await asyncio.open_unix_connection(str(directory / "control.sock"))
    try:
        writer.write(json.dumps({"version": 1, "capability": capability, "command": command, **extra}).encode() + b"\n")
        await writer.drain()
        return json.loads(await asyncio.wait_for(reader.readline(), 5))
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.fixture
def ipc_directory():
    with tempfile.TemporaryDirectory(prefix="omnis-ipc-", dir=os.environ["TMPDIR"]) as name:
        yield Path(name)


@pytest.mark.asyncio
async def test_real_unix_control_peer_capability_and_allowlist(migrated_database_url, ipc_directory):
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
            assert (await request(ipc_directory, capability, {"op": "exec", "argv": ["id"]}))["error"] == "INVALID_REQUEST"
            assert (await request(ipc_directory, capability, {"op": "status"}, arbitrary="denied"))["error"] == "INVALID_REQUEST"
            instance_id = accepted["status"]["instance_id"]
            opened = await request(ipc_directory, capability, {"op": "open", "instance_id": instance_id, "command_id": str(uuid4()), "expected_generation": 0})
            assert opened["ok"] and opened["result_generation"] == 1
            stale = await request(ipc_directory, capability, {"op": "shutdown", "instance_id": instance_id, "command_id": str(uuid4()), "expected_generation": 0})
            assert stale["error"] == "GENERATION_CONFLICT"
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
async def test_control_refuses_unsafe_directory_and_foreign_files(migrated_database_url, ipc_directory):
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
async def test_control_frames_are_bounded_and_duplicate_keys_rejected(migrated_database_url, ipc_directory):
    from omnis.transport.local_control import LocalControl

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    try:
        async with LocalControl(ipc_directory, service, owner, epoch):
            for payload in (b"x" * 5000 + b"\n", b'{"version":1,"version":1}\n'):
                reader, writer = await asyncio.open_unix_connection(str(ipc_directory / "control.sock"))
                writer.write(payload)
                await writer.drain()
                response = json.loads(await asyncio.wait_for(reader.readline(), 4))
                assert response["error"] == "INVALID_REQUEST"
                writer.close()
                await writer.wait_closed()
    finally:
        await engine.dispose()


def test_private_directory_rejects_replaceable_ancestor(ipc_directory):
    from omnis.core.paths import private_directory

    parent = ipc_directory / "shared"
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    child = parent / "private"
    child.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="ancestor"):
        private_directory(child)


@pytest.mark.asyncio
async def test_cancelled_socket_startup_leaves_no_listener(migrated_database_url, ipc_directory):
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
