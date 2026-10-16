"""Real owned inert subprocess; HTTP/native config are explicitly simulated."""

import asyncio
import inspect
import re
import stat
import sys
import time
from pathlib import Path
from types import SimpleNamespace
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


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["read", "save"])
@pytest.mark.parametrize("parent", ["image", "current", "foreign"])
async def test_image_provider_ancestor_through_settings(
    monkeypatch: pytest.MonkeyPatch, action: str, parent: str
) -> None:
    """Image metadata seam, actual guard/coroutine; no OCI/native execution."""
    from omnis_hermes import runtime_host

    dockerfile = (Path(__file__).resolve().parents[2] / "ops/Dockerfile.hermes").read_text()
    default = re.search(r"ARG RUNTIME_UID=(\d+)", dockerfile)
    assert default is not None
    # Follow the shipped /state chowns in order, not an assumed fixture owner.
    owners = re.findall(r'chown (?:-R )?"?([^\s"]+)"? (?:/runtime )?/state(?:\s|$)', dockerfile)
    assert owners
    image_uid = int(owners[-1].split(":")[0].replace("${RUNTIME_UID}", default[1]))
    uid = 1000
    parent_uid = image_uid if parent == "image" else uid if parent == "current" else 65532
    selected = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}
    host = runtime_host.RuntimeHost(Path("/unopened-source-fixture"))
    host.state, host.generation, host.epoch = "MANAGEMENT", 1, 1
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000

    def lstat(path: Path) -> SimpleNamespace:
        private = path == Path("/state/provider") or Path("/state/provider") in path.parents
        return SimpleNamespace(
            st_mode=stat.S_IFDIR | (0o700 if private else 0o755),
            st_uid=uid if private else parent_uid if path == Path("/state") else 0,
        )

    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    stdout.feed_data(b"HERMES_BACKEND_READY port=12345\n")
    stdout.feed_eof()
    stderr.feed_eof()
    spawn = AsyncMock(return_value=SimpleNamespace(stdout=stdout, stderr=stderr, returncode=None))
    configure = AsyncMock(return_value=selected if action == "save" else None)
    monkeypatch.setattr(Path, "resolve", lambda self: self)
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(runtime_host.os, "getuid", lambda: uid)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(runtime_host, "configure", configure)
    monkeypatch.setattr(
        runtime_host, "request", AsyncMock(return_value={"status": "ok", "mode": "management-only"})
    )
    try:
        await host._settings_run(
            {
                "operation_id": str(uuid4()),
                "action": action,
                "selection": selected if action == "save" else None,
            }
        )
        assert host.settings_result is not None
        assert host.settings_result["status"] == (
            "INDETERMINATE" if parent == "foreign" else "CONFIRMED"
        )
        assert host.management_failed is (parent == "foreign")
        assert spawn.await_count == configure.await_count == (0 if parent == "foreign" else 1)
        if parent == "image":
            assert image_uid == 0
            assert "&& chmod 0755 /state" in dockerfile
            assert 'chown -R "${RUNTIME_UID}:${RUNTIME_GID}" /runtime /state' in dockerfile
            assert "USER ${RUNTIME_UID}:${RUNTIME_GID}" in dockerfile
    finally:
        await asyncio.gather(*host.management_output)
