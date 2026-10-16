"""SOURCE: actual request bytes over owned UDS; no native/PG/provider.

Only the loopback connect is redirected to a private UDS HTTP peer. The Host,
RuntimeClient, configure, parser and pre-write boundary remain product code.
"""

import asyncio
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from omnis_hermes import management_http, runtime_host
from omnis_hermes.management_contract import SELECTION

from omnis.modules.instance.service import RuntimeAuthority
from omnis.supervisor.runtime_client import RuntimeClient


@pytest.mark.asyncio
@pytest.mark.parametrize("cut", ["valid", "expired", "stop", "stopping", "fence", "health_expired"])
@pytest.mark.parametrize("action", ["save", "logout"])
async def test_settings_checks_authority_after_connect_before_bytes(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, cut: str, action: str
) -> None:
    home = ipc_directory / "m"
    home.mkdir(mode=0o700)
    fifo = home / "hold"
    os.mkfifo(fifo, 0o600)
    hold = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    script = (
        "import os; print('HERMES_BACKEND_READY port=1',flush=True); "
        "fd=os.open('hold',os.O_RDONLY); os.read(fd,1)"
    )
    host = runtime_host.RuntimeHost(
        ipc_directory,
        _test_management=runtime_host.TestLaunch((sys.executable, "-I", "-B", "-c", script), home),
    )
    methods: list[str] = []
    peers: set[asyncio.Task[None]] = set()
    connections = 0
    stop_task: asyncio.Task[None] | None = None

    async def endpoint(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        peers.add(task)
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            first = header.split(b"\r\n", 1)[0].decode()
            method, path, _ = first.split()
            methods.append(method)
            length = next(
                int(line.split(b":", 1)[1])
                for line in header.split(b"\r\n")
                if line.startswith(b"Content-Length:")
            )
            await reader.readexactly(length)
            value: object = (
                {"status": "ok", "mode": "management-only"}
                if path == "/api/health"
                else {"selection": dict(SELECTION), "authenticated": "ABSENT"}
                if path == "/api/auth/codex"
                else {"ok": True}
                if method == "PUT"
                else dict(SELECTION)
            )
            raw = json.dumps(value).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw
            )
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            peers.discard(task)

    socket_path = ipc_directory / "http.sock"
    server = await asyncio.start_unix_server(endpoint, path=socket_path)

    async def connect(
        address: str, port: int, *, limit: int
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        nonlocal connections, stop_task
        assert address == "127.0.0.1" and port == 1
        reader, writer = await asyncio.open_unix_connection(socket_path, limit=limit)
        connections += 1
        if connections == 2:  # After health, immediately before actual PUT write.
            if cut == "expired":
                while time.monotonic_ns() < host.deadline_ns:
                    pass  # Scheduling cut: no watchdog turn before request.write.
            elif cut == "stopping":
                host.state = "STOPPING"  # Trusted owner-state cut, not an IPC boolean.
            elif cut == "fence":
                host.epoch += 1
            elif cut == "stop":
                stop_task = asyncio.create_task(host.stop())
                try:
                    await asyncio.Event().wait()
                finally:
                    writer.close()
                    await writer.wait_closed()
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", connect)
    if cut == "health_expired":
        original = management_http.request

        async def health(
            port: int,
            token: str,
            method: str,
            path: str,
            *,
            dispatch_guard: Callable[[], None],
        ) -> object:
            result = await original(port, token, method, path, dispatch_guard=dispatch_guard)
            while time.monotonic_ns() < host.deadline_ns:
                pass
            return result

        monkeypatch.setattr(runtime_host, "request", health)
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 300_000_000)
    )
    try:
        async with host:
            client = RuntimeClient(ipc_directory, generation=0, epoch=1)
            await client.connect()
            try:
                identity = str(uuid4())
                assert (
                    await client.settings(
                        service,
                        uuid4(),
                        {
                            "operation_id": identity,
                            "action": action,
                            "selection": dict(SELECTION) if action == "save" else None,
                        },
                    )
                )["status"] == "PENDING"
                async with asyncio.timeout(2):
                    while host.settings_task is None or not host.settings_task.done():
                        await asyncio.sleep(0.001)
                assert host.settings_result is not None
                assert host.settings_result["status"] == (
                    "CONFIRMED" if cut == "valid" else "INDETERMINATE"
                )
                await asyncio.sleep(0.01)  # Let the real peer observe bytes or EOF.
                assert methods.count("PUT" if action == "save" else "DELETE") == int(cut == "valid")
                expected = ["GET", "PUT", "GET"] if action == "save" else ["GET", "DELETE"]
                assert methods == (expected if cut == "valid" else ["GET"])
                if stop_task is not None:
                    await asyncio.wait_for(stop_task, 1)
            finally:
                await client.close()
        assert host.process is not None and host.process.returncode is not None
        assert not host._owned_pids()
    finally:
        server.close()
        server.close_clients()
        await server.wait_closed()
        await asyncio.gather(*peers, return_exceptions=True)
        socket_path.unlink(missing_ok=True)
        os.close(hold)


@pytest.mark.asyncio
@pytest.mark.parametrize("cut", ["stop", "expiry"])
@pytest.mark.parametrize("action", ["save", "logout"])
async def test_sent_save_stays_indeterminate_until_owned_process_drains(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, cut: str, action: str
) -> None:
    home = ipc_directory / "m"
    home.mkdir(mode=0o700)
    fifo = home / "hold"
    os.mkfifo(fifo, 0o600)
    hold = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    # Ignore TERM so Stop must exercise the existing bounded KILL/reap path.
    script = (
        "import os,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "print('HERMES_BACKEND_READY port=1',flush=True); "
        "fd=os.open('hold',os.O_RDONLY); os.read(fd,1)"
    )
    host = runtime_host.RuntimeHost(
        ipc_directory,
        _test_management=runtime_host.TestLaunch((sys.executable, "-I", "-B", "-c", script), home),
    )
    sent = asyncio.Event()
    writes = 0

    async def endpoint(*args: object, **kwargs: object) -> object:
        nonlocal writes
        guard = kwargs.get("dispatch_guard")
        if callable(guard):
            guard()
        writes += 1
        sent.set()
        await asyncio.Event().wait()  # Native response/writer outcome unknown.
        return None

    monkeypatch.setattr(
        runtime_host, "request", AsyncMock(return_value={"status": "ok", "mode": "management-only"})
    )
    monkeypatch.setattr(management_http, "request", endpoint)
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 300_000_000)
    )
    try:
        async with host:
            client = RuntimeClient(ipc_directory, generation=0, epoch=1)
            await client.connect()
            try:
                identity = str(uuid4())
                await client.settings(
                    service,
                    uuid4(),
                    {
                        "operation_id": identity,
                        "action": action,
                        "selection": dict(SELECTION) if action == "save" else None,
                    },
                )
                await asyncio.wait_for(sent.wait(), 1)
                process = host.process
                assert process is not None
                before_stop = process.returncode
                assert before_stop is None
                if cut == "stop":
                    stopping = asyncio.create_task(client.drain())
                else:
                    stopping = None
                async with asyncio.timeout(2):
                    while host.state != "STOPPING":
                        await asyncio.sleep(0.001)
                    assert host.snapshot()["drained"] is False
                    during_stop = process.returncode
                    assert during_stop is None
                    while process.returncode is None or host.state == "STOPPING":
                        await asyncio.sleep(0.001)
                if stopping is not None:
                    assert await stopping is False  # Non-PID1 remains UNCERTAIN.
                assert process.returncode is not None
                assert host.state == "UNCERTAIN"
                assert (await client.settings_status(identity))["status"] == "INDETERMINATE"
                assert (await client.settings_status(identity))["status"] == "INDETERMINATE"
                assert writes == 1 and not host._owned_pids()
            finally:
                await client.close()
    finally:
        os.close(hold)
