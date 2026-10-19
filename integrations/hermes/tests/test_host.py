"""Real owned synthetic subprocesses; uncontained process groups stay UNCERTAIN."""

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase,reason,kind",
    [
        ("SPAWN", "os", "OS_ERROR"),
        ("HANDSHAKE", "Native ready deadline", "READY_TIMEOUT"),
        ("HANDSHAKE", "Native RPC deadline", "RPC_TIMEOUT"),
        ("HANDSHAKE", "Native transport unavailable", "TRANSPORT"),
        ("HANDSHAKE", "PRIVATE_EXCEPTION_TEXT", "OTHER"),
        ("HANDSHAKE", "unknown", "OTHER"),
        ("HANDSHAKE", "protocol_subclass", "OTHER"),
        ("HANDSHAKE", "string_subclass", "OTHER"),
        ("HANDSHAKE", "cancel", "CANCELLED"),
        ("HANDSHAKE", "timeout", "TIMEOUT"),
        ("POST_HANDSHAKE", "expired", "VALUE_ERROR"),
        (None, "positive", None),
    ],
)
@pytest.mark.parametrize("write_failure", [False, True])
async def test_launch_failure_diagnostic_precedes_stop(
    monkeypatch,
    capsys,
    phase,
    reason,
    kind,
    write_failure,
):
    from omnis_hermes import runtime_host as module
    from omnis_hermes.runtime_protocol import ProtocolError

    class PRIVATE_EXCEPTION_CLASS(Exception):
        pass

    errors = {
        "os": OSError("PRIVATE_EXCEPTION_TEXT"),
        "unknown": PRIVATE_EXCEPTION_CLASS("PRIVATE_EXCEPTION_TEXT"),
        "cancel": asyncio.CancelledError("PRIVATE_EXCEPTION_TEXT"),
        "timeout": TimeoutError("PRIVATE_EXCEPTION_TEXT"),
    }
    primary = errors.get(reason, ProtocolError(reason))
    if reason == "protocol_subclass":

        class PRIVATE_PROTOCOL_CLASS(ProtocolError):
            pass

        primary = PRIVATE_PROTOCOL_CLASS("Native ready deadline")
    elif reason == "string_subclass":

        class PRIVATE_STRING_CLASS(str):
            pass

        primary = ProtocolError(PRIVATE_STRING_CLASS("Native ready deadline"))
    host = module.RuntimeHost(Path("/nonexistent"))
    process = Mock()
    spawn = AsyncMock(return_value=process)
    peer = Mock(handshake=AsyncMock(return_value={}))
    captured = []

    async def stop():
        captured.append(capsys.readouterr().err)

    host.stop = AsyncMock(side_effect=stop)
    if phase == "SPAWN":
        spawn.side_effect = primary
    elif phase == "HANDSHAKE":
        peer.handshake.side_effect = primary
    elif phase == "POST_HANDSHAKE":

        async def expired(**kwargs):
            host.state = "STOPPING"
            return {}

        peer.handshake.side_effect = expired
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(module, "NativePeer", Mock(return_value=peer))
    with monkeypatch.context() as io:
        if write_failure:
            io.setattr(sys, "stderr", Mock(write=Mock(side_effect=OSError("PRIVATE_IO"))))
        body: dict[str, object] = {
            "generation": 0,
            "epoch": 1,
            "deadline_ns": time.monotonic_ns() + 4_000_000_000,
        }
        if phase is None:
            await host._launch(body)
            assert host.state == "READY"
            host.stop.assert_not_awaited()
        else:
            with pytest.raises(
                ValueError if phase == "POST_HANDSHAKE" else type(primary)
            ) as raised:
                await host._launch(body)
            if phase != "POST_HANDSHAKE":
                assert raised.value is primary
            host.stop.assert_awaited_once()
    expected = f"RUNTIME_LAUNCH_FAILURE phase={phase} error={kind}\n" if not write_failure else ""
    assert captured == ([] if phase is None else [expected])
    output = capsys.readouterr()
    assert output.err == "" and output.out == ""


@pytest.mark.parametrize(
    "field,value",
    [
        ("op", []),
        ("version", True),
        ("generation", True),
        ("epoch", 1.0),
        ("id", 1),
        ("capability", 3),
        ("boot", []),
        ("argv", []),
    ],
)
def test_ipc_invalid_types_are_sanitized_before_spawn(field, value):
    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(Path("/nonexistent"))
    body = {
        "version": 1,
        "id": str(uuid4()),
        "boot": host.boot,
        "capability": host.capability,
        "generation": 0,
        "epoch": 1,
        "op": "status",
    }
    with pytest.raises(ValueError):
        host._validate({**body, field: value})
    assert host.process is None


def test_ipc_accepts_initial_zero_generation_but_not_stale_boot_or_fence():
    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(Path("/nonexistent"))
    body = {
        "version": 1,
        "id": str(uuid4()),
        "boot": host.boot,
        "capability": host.capability,
        "generation": 0,
        "epoch": 1,
        "op": "status",
    }
    assert host._validate(body) == body
    host.generation, host.epoch = 0, 1
    with pytest.raises(ValueError):
        host._validate({**body, "epoch": 2})
    with pytest.raises(ValueError):
        host._validate({**body, "boot": str(uuid4())})


def test_real_detached_family_is_killed_and_exactly_reaped_in_owned_harness():
    adapter = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("family_fixture.py"))],
        env={"PYTHONPATH": adapter, "TMPDIR": os.environ["TMPDIR"]},
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout) == {"detached_reaped": True, "state": "UNCERTAIN"}


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [False, True])
async def test_host_exit_closes_a_live_idle_uds_client_before_waiting_for_server(authenticated):
    """Real local IPC/asyncio consumer; no native/provider subprocess."""
    from omnis_hermes.runtime_host import RuntimeHost

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        host = await RuntimeHost(root).__aenter__()
        if authenticated:
            from omnis.supervisor.runtime_client import RuntimeClient

            client = RuntimeClient(root, generation=0, epoch=1)
            await client.connect()
            assert (await client.status())["state"] == "IDLE"
            reader, writer = client.reader, client.writer
            assert reader is not None and writer is not None
        else:
            reader, writer = await asyncio.open_unix_connection(str(root / "runtime.sock"))
        exiting = None
        try:
            async with asyncio.timeout(0.5):
                while not host.clients:
                    await asyncio.sleep(0)
            exiting = asyncio.create_task(host.__aexit__(None, None, None))
            await asyncio.wait_for(asyncio.shield(exiting), 0.5)
            assert await asyncio.wait_for(reader.read(), 0.5) == b""
            assert not host.clients and host.lock_fd is None
            assert not (root / "runtime.sock").exists()
            assert not (root / "runtime.boot").exists()
        finally:
            writer.close()
            await writer.wait_closed()
            if exiting is not None:
                if not exiting.done():
                    exiting.cancel()
                await asyncio.gather(exiting, return_exceptions=True)
            await host.__aexit__(None, None, None)
        # The exact own endpoint/lock is reusable, not merely disconnected.
        async with RuntimeHost(root):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize("observe_wire", [False, True])
async def test_authenticated_idle_uds_has_no_unsolicited_frame(observe_wire):
    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.supervisor.runtime_client import RuntimeClient

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="idle-") as name:
        root = Path(name)
        async with RuntimeHost(root) as host:
            client = RuntimeClient(root, generation=0, epoch=1)
            await client.connect()
            try:
                assert (await client.status())["state"] == "IDLE"
                assert (await client.status())["state"] == "IDLE"
                owner, deadline = host.owner_writer, host.deadline_ns
                assert owner is not None and client.reader is not None
                if observe_wire:
                    with pytest.raises(TimeoutError):
                        await asyncio.wait_for(client.reader.read(1), 2.8)
                else:
                    await asyncio.sleep(2.8)
                assert (await client.status())["state"] == "IDLE"
                assert host.owner_writer is owner and host.deadline_ns == deadline == 0
                assert host.process is None and host.preparation_process is None
                assert not host.managed_finals and host.settings_task is None
            finally:
                await client.close()
            async with asyncio.timeout(0.5):
                while host.clients:
                    await asyncio.sleep(0)
            assert host.owner_writer is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        "unknown",
        "type",
        "auth",
        "newline",
        "oversize",
        "overflow",
        "eof",
        "partial-eof",
        "max-frame",
        "oversize-valid",
    ],
)
async def test_owned_uds_frame_validation_and_eof(invalid):
    from omnis_hermes.runtime_host import MAX_FRAME, RuntimeHost

    from omnis.supervisor.runtime_client import RuntimeClient

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="idle-") as name:
        root = Path(name)
        async with RuntimeHost(root) as host:
            client = RuntimeClient(root, generation=0, epoch=1)
            await client.connect()
            try:
                assert (await client.status())["state"] == "IDLE"
                reader, writer = client.reader, client.writer
                assert reader is not None and writer is not None
                body = {
                    "version": 1,
                    "id": str(uuid4()),
                    "boot": host.boot,
                    "capability": host.capability,
                    "generation": 0,
                    "epoch": 1,
                    "op": "status",
                }
                if invalid == "unknown":
                    body["op"] = "unknown"
                elif invalid == "type":
                    body["op"] = []
                elif invalid == "auth":
                    body["capability"] = "wrong"
                raw = json.dumps(body).encode() + b"\n"
                if invalid in {"max-frame", "oversize-valid"}:
                    size = MAX_FRAME + (invalid == "oversize-valid")
                    raw = raw[:-1].ljust(size - 1, b" ") + b"\n"
                if invalid == "newline":
                    raw = b"\n"
                elif invalid in {"oversize", "overflow"}:
                    raw = b" " * (MAX_FRAME + 1) + (b"\n" if invalid == "oversize" else b"")
                elif invalid in {"eof", "partial-eof"}:
                    raw = b"" if invalid == "eof" else b"{"
                writer.write(raw)
                await writer.drain()
                if invalid in {"eof", "partial-eof"}:
                    writer.write_eof()
                    assert await asyncio.wait_for(reader.read(), 0.5) == b""
                    async with asyncio.timeout(0.5):
                        while host.clients:
                            await asyncio.sleep(0)
                    assert host.owner_writer is None
                elif invalid == "max-frame":
                    accepted = json.loads(await asyncio.wait_for(reader.readline(), 0.5))
                    assert accepted["ok"] is True and accepted["id"] == body["id"]
                else:
                    denied = json.loads(await asyncio.wait_for(reader.readline(), 3.1))
                    assert denied["ok"] is False and denied["error"] == "RUNTIME_DENIED"
                    assert denied["id"] == (
                        body["id"] if invalid in {"unknown", "type", "auth"} else None
                    )
                    if invalid not in {"oversize", "overflow"}:
                        assert (await client.status())["state"] == "IDLE"
                assert host.process is None and host.deadline_ns == 0
            finally:
                await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unauth-idle", "unauth-partial", "owned-partial"])
async def test_uds_frame_deadline_is_not_reset_by_partial_bytes(mode):
    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.supervisor.runtime_client import RuntimeClient

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="idle-") as name:
        root = Path(name)
        async with RuntimeHost(root) as host:
            client = RuntimeClient(root, generation=0, epoch=1)
            await client.connect()
            try:
                if mode == "owned-partial":
                    assert (await client.status())["state"] == "IDLE"
                reader, writer = client.reader, client.writer
                assert reader is not None and writer is not None
                started = time.monotonic()
                if mode == "owned-partial":
                    writer.write(b"{")
                    await writer.drain()
                if mode != "unauth-idle":
                    await asyncio.sleep(1.4)
                    writer.write(b" ")
                    await writer.drain()
                async with asyncio.timeout_at(started + 3.1):
                    denied = json.loads(await reader.readline())
                assert time.monotonic() - started >= 2.3
                assert denied["ok"] is False and denied["error"] == "RUNTIME_DENIED"
                assert denied["id"] is None
                assert host.deadline_ns == 0 and host.process is None
                if mode != "owned-partial":
                    assert host.owner_writer is None
            finally:
                await client.close()


@pytest.mark.asyncio
async def test_fixed_native_argv_does_not_import_a_writable_cwd_package():
    from omnis_hermes.runtime_host import NATIVE_COMMAND, RuntimeHost, TestLaunch

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        work, ipc = root / "work", root / "ipc"
        work.mkdir(mode=0o700)
        ipc.mkdir(mode=0o700)
        package = work / "tui_gateway"
        package.mkdir()
        (package / "__init__.py").write_text("")
        marker = work / "shadow-executed"
        fixture = Path(__file__).with_name("peer_fixture.py").read_text()
        (package / "entry.py").write_text(
            "from pathlib import Path\nPath('shadow-executed').write_text('synthetic')\n" + fixture
        )
        # Replace only the unavailable OCI interpreter, preserving product flags.
        argv = (sys.executable, "-B", *NATIVE_COMMAND[1:])
        async with RuntimeHost(ipc, _test_launch=TestLaunch(argv, work)) as host:
            try:
                await host._launch(
                    {
                        "generation": 0,
                        "epoch": 1,
                        "deadline_ns": time.monotonic_ns() + 1_000_000_000,
                    }
                )
            except ValueError:
                pass  # Installed Hermes is deliberately absent in the API environment.
            finally:
                await host.stop()
            assert host.process is not None and host.process.returncode is not None
            assert not Path(f"/proc/{host.process.pid}").exists()
            assert not marker.exists(), "fixed native launch selected the writable cwd package"


@pytest.mark.asyncio
async def test_watchdog_stops_while_all_native_pending_slots_are_saturated():
    from omnis_hermes.runtime_host import RuntimeHost, TestLaunch
    from omnis_hermes.runtime_protocol import ProtocolError

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        root.chmod(0o700)
        async with RuntimeHost(
            root,
            _test_launch=TestLaunch(
                (
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(__file__).with_name("peer_fixture.py")),
                    "stall",
                ),
                root,
            ),
        ) as host:
            await host._launch(
                {"generation": 0, "epoch": 1, "deadline_ns": time.monotonic_ns() + 200_000_000}
            )
            peer, process = host.peer, host.process
            assert peer is not None and process is not None
            calls = [asyncio.create_task(peer.call("ping", {})) for _ in range(32)]
            await asyncio.sleep(0.02)
            assert len(peer.pending) == 32
            results = await asyncio.wait_for(asyncio.gather(*calls, return_exceptions=True), 1.5)
            assert all(isinstance(result, ProtocolError) for result in results)
            await asyncio.wait_for(process.wait(), 1)
            assert not Path(f"/proc/{process.pid}").exists()


@pytest.mark.asyncio
async def test_host_refuses_unsafe_paths_exclusive_owner_and_wrong_peer():
    from omnis_hermes.runtime_host import RuntimeHost

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        root.chmod(0o755)
        with pytest.raises(ValueError):
            async with RuntimeHost(root):
                pass
        root.chmod(0o700)
        (root / "runtime.lock").symlink_to(root / "foreign")
        with pytest.raises(OSError):
            async with RuntimeHost(root):
                pass
        assert not (root / "foreign").exists()
        (root / "runtime.lock").unlink()
        async with RuntimeHost(root, peer_uid=os.getuid() + 1):
            with pytest.raises(OSError):
                async with RuntimeHost(root):
                    pass
            reader, writer = await asyncio.open_unix_connection(str(root / "runtime.sock"))
            assert await asyncio.wait_for(reader.read(), 1) == b""
            writer.close()
            await writer.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("termination", ["expiry", "stop", "disconnect"])
async def test_private_host_launch_watchdog_stop_and_environment(termination):
    assert importlib.util.find_spec("omnis_hermes.runtime_host") is not None, (
        "runtime owner missing"
    )
    import sys

    from omnis_hermes.runtime_host import RuntimeHost, TestLaunch

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        root.chmod(0o700)
        host = RuntimeHost(
            root,
            _test_launch=TestLaunch(
                (
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(__file__).with_name("peer_fixture.py")),
                    "normal",
                ),
                root,
            ),
        )
        async with host:
            boot = json.loads((root / "runtime.boot").read_text())
            assert (root / "runtime.sock").stat().st_mode & 0o777 == 0o600
            reader, writer = await asyncio.open_unix_connection(str(root / "runtime.sock"))

            async def request(op, **extra):
                body = {
                    "version": 1,
                    "id": str(uuid4()),
                    "boot": boot["boot"],
                    "capability": boot["capability"],
                    "generation": 1,
                    "epoch": 1,
                    "op": op,
                    **extra,
                }
                writer.write(json.dumps(body).encode() + b"\n")
                await writer.drain()
                return json.loads(await asyncio.wait_for(reader.readline(), 3))

            try:
                denied = await request("session.create")
                assert denied["ok"] is False and host.process is None
                grant = time.monotonic_ns() + (
                    400_000_000 if termination == "expiry" else 4_500_000_000
                )
                launched = await request("launch", deadline_ns=grant)
                assert launched["ok"] is True and launched["state"] == "READY"
                assert launched["generation"] == 1 and launched["epoch"] == 1
                process = host.process
                assert process is not None
                pid = process.pid
                if termination == "expiry":
                    await asyncio.wait_for(process.wait(), 1)
                await asyncio.sleep(2.8)
                assert host.deadline_ns == grant
                if termination != "expiry":
                    assert process.returncode is None and host.state == "READY"
                    if termination == "stop":
                        assert (await request("stop"))["ok"] is True
                    else:
                        writer.write_eof()
                        assert await asyncio.wait_for(reader.read(), 1) == b""
                    await asyncio.wait_for(process.wait(), 1)
                if termination != "disconnect":
                    status = await request("status")
                    assert status["ok"] is True
                    assert status["state"] == "UNCERTAIN"  # no OCI namespace containment proof
                    renewed = await request(
                        "renew", deadline_ns=time.monotonic_ns() + 1_000_000_000
                    )
                    assert renewed["ok"] is False  # never resurrect expired authority
                    stopped = await request("stop")
                    assert stopped["drained"] is False
                assert process.returncode is not None
                assert not Path(f"/proc/{pid}").exists()
                assert host.state == "UNCERTAIN" and not host._owned_pids()
            finally:
                writer.close()
                await writer.wait_closed()
        assert not (root / "runtime.sock").exists()
        assert not (root / "runtime.boot").exists()
