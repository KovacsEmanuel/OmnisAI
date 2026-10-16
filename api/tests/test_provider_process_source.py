"""Real owned inert subprocess; HTTP/native config are explicitly simulated."""

import asyncio
import inspect
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from omnis.modules.instance.service import RuntimeAuthority
from omnis.supervisor.runtime_client import RuntimeClient


@pytest.mark.asyncio
async def test_management_process_is_owned_by_existing_stop_and_environment(
    ipc_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes import runtime_host

    assert "_test_management" in inspect.signature(runtime_host.RuntimeHost).parameters
    root = ipc_directory / "m"
    root.mkdir(mode=0o700)
    script = (
        "import os,time; "
        "assert 'OPENAI_API_KEY' not in os.environ; "
        "assert 'HERMES_OMNIS_INERT' not in os.environ; "
        "assert os.environ['HERMES_OMNIS_MANAGEMENT']=='1'; "
        "assert os.environ['HOME'] != '/synthetic-personal'; "
        "print('HERMES_BACKEND_READY port=12345',flush=True); time.sleep(20)"
    )
    host = runtime_host.RuntimeHost(
        ipc_directory,
        _test_management=runtime_host.TestLaunch((sys.executable, "-I", "-B", "-c", script), root),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-do-not-adopt")
    monkeypatch.setenv("HOME", "/synthetic-personal")
    monkeypatch.setattr(
        runtime_host, "request", AsyncMock(return_value={"status": "ok", "mode": "management-only"})
    )
    monkeypatch.setattr(runtime_host, "configure", AsyncMock(return_value=None))
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
    )
    async with host:
        client = RuntimeClient(ipc_directory, generation=0, epoch=1)
        await client.connect()
        try:
            operation_id = str(uuid4())
            assert (
                await client.settings(
                    service,
                    uuid4(),
                    {"operation_id": operation_id, "action": "read", "selection": None},
                )
            )["status"] == "PENDING"
            for _ in range(50):
                result = await client.settings_status(operation_id)
                if result["status"] != "PENDING":
                    break
                await asyncio.sleep(0.01)
            assert result["status"] == "CONFIRMED"
            process = host.process
            assert process is not None
            before_stop = process.returncode
            assert before_stop is None
            assert await client.drain() is False  # Host source is not PID1; preserve UNCERTAIN.
            assert process.returncode is not None
            assert host.state == "UNCERTAIN"
            assert all(task.done() for task in host.management_output)
            assert not host._owned_pids()
        finally:
            await client.close()
