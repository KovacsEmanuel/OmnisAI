"""Cancellation must survive a transport failure during client teardown."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.transport.local_control import LocalControl


@pytest.mark.asyncio
async def test_client_teardown_does_not_suppress_cancellation(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL, ipc_directory: Path
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    control = LocalControl(ipc_directory, service, owner, epoch)
    captured: asyncio.Future[asyncio.Task[object]] = asyncio.get_running_loop().create_future()
    original_handle = control._handle

    async def failed_close() -> None:
        raise ConnectionResetError("synthetic transport close failure")

    async def capture(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        monkeypatch.setattr(writer, "wait_closed", failed_close)
        captured.set_result(task)
        await original_handle(reader, writer)

    monkeypatch.setattr(control, "_handle", capture)
    try:
        async with control:
            _, writer = await asyncio.open_unix_connection(str(ipc_directory / "control.sock"))
            try:
                handler = await asyncio.wait_for(captured, timeout=2)
                handler.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await handler
                assert not control.clients
            finally:
                writer.close()
                await writer.wait_closed()
    finally:
        await engine.dispose()
