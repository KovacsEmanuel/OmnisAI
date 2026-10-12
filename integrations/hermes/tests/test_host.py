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
from uuid import uuid4

import pytest


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
async def test_host_exit_closes_a_live_idle_uds_client_before_waiting_for_server():
    """Real local IPC/asyncio consumer; no native/provider subprocess."""
    from omnis_hermes.runtime_host import RuntimeHost

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        host = await RuntimeHost(root).__aenter__()
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
        argv = (sys.executable, *NATIVE_COMMAND[1:])
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
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py")), "stall"), root
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
async def test_private_host_launch_watchdog_stop_and_environment():
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
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py")), "normal"), root
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
                launched = await request("launch", deadline_ns=time.monotonic_ns() + 400_000_000)
                assert launched["ok"] is True and launched["state"] == "READY"
                assert launched["generation"] == 1 and launched["epoch"] == 1
                process = host.process
                assert process is not None
                pid = process.pid
                await asyncio.sleep(0.7)
                status = await request("status")
                assert status["state"] == "UNCERTAIN"  # no OCI namespace containment proof
                assert process.returncode is not None
                assert not Path(f"/proc/{pid}").exists()
                renewed = await request("renew", deadline_ns=time.monotonic_ns() + 1_000_000_000)
                assert renewed["ok"] is False  # never resurrect expired authority
                stopped = await request("stop")
                assert stopped["drained"] is False
            finally:
                writer.close()
                await writer.wait_closed()
        assert not (root / "runtime.sock").exists()
        assert not (root / "runtime.boot").exists()
