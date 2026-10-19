"""A startup slower than ordinary RPC still uses a bounded lease, no native Hermes."""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest
from omnis_hermes.runtime_host import RuntimeHost
from omnis_hermes.runtime_host import TestLaunch as LaunchFixture

from omnis.modules.instance.service import RuntimeAuthority
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["slow_ready", "startup_eight", "startup_over", "stop", "cancel"])
async def test_installed_client_waits_for_startup_within_absolute_grant(capsys, mode):
    class Authority:
        async def runtime_authority(self, owner, epoch, generation, *, inert_probe, startup=None):
            assert inert_probe is True
            return RuntimeAuthority(generation, epoch, time.monotonic_ns() + 10_000_000_000)

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as raw:
        root = Path(raw)
        host = RuntimeHost(
            root,
            _test_launch=LaunchFixture(
                (
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(__file__).with_name("peer_fixture.py")),
                    "startup_eight" if mode in {"stop", "cancel"} else mode,
                ),
                root,
            ),
        )
        async with host:
            client = RuntimeClient(root, generation=0, epoch=1)
            await client.connect()
            try:
                before = time.monotonic()
                pending = asyncio.create_task(client.launch_inert(Authority(), uuid4()))
                if mode in {"stop", "cancel"}:
                    async with asyncio.timeout(2):
                        while host.peer is None:
                            await asyncio.sleep(0.01)
                    if mode == "stop":
                        assert await client.drain() is False
                    else:
                        pending.cancel()
                    with pytest.raises((RuntimeUnavailable, asyncio.CancelledError)):
                        await pending
                    assert time.monotonic() - before < 3
                elif mode == "startup_over":
                    with pytest.raises(RuntimeUnavailable):
                        await pending
                    assert 9 < time.monotonic() - before < 12
                else:
                    ready = await pending
                    assert time.monotonic() - before > (7.5 if mode == "startup_eight" else 2)
                    assert ready["state"] == "READY"
                    assert ready["drained"] is False
            finally:
                await client.close()
            deadline = time.monotonic() + 2
            while host.state == "STOPPING" or (
                host.process is not None and host.process.returncode is None
            ):
                assert time.monotonic() < deadline
                await asyncio.sleep(0.02)
            assert host.state == "UNCERTAIN"  # This test does not own a PID1 namespace.
        output = capsys.readouterr().err
        assert ("RUNTIME_LAUNCH_FAILURE" in output) == (mode in {"startup_over", "stop", "cancel"})


@pytest.mark.parametrize(
    "operation",
    [
        "renew",
        "settings",
        "prepare",
        "task_stage",
        "task_release",
        "task_status",
        "task_model_preflight",
        "task_model_initialize",
    ],
)
def test_ten_second_grant_is_not_ordinary_authority(tmp_path, operation):
    host = RuntimeHost(tmp_path)
    body = {"op": operation, "deadline_ns": time.monotonic_ns() + 9_000_000_000}
    for payload in (
        None,
        {"protocol": "omnis-managed-admission-v6", "mode": "STATUS"},
        {"protocol": "omnis-managed-admission-v6", "mode": "SEND"},
        {"protocol": "omnis-managed-admission-v6", "mode": "CREATE"},
    ):
        with pytest.raises(ValueError):
            host._grant({**body, "payload": payload})
    for deadline in (True, False, time.monotonic_ns() - 1, time.monotonic_ns() + 11_000_000_000):
        with pytest.raises(ValueError):
            host._grant({"op": "launch", "deadline_ns": deadline})


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,kind", [("ready_stall", "TIMEOUT"), ("eof", "TRANSPORT")])
async def test_real_launch_failure_marker_without_raw_native_stderr(mode, kind, capsys):
    from omnis_hermes.runtime_protocol import ProtocolError

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as raw:
        root = Path(raw)
        argv = (
            sys.executable,
            "-I",
            "-B",
            str(Path(__file__).with_name("peer_fixture.py")),
            "ready_stall",
        )
        if mode == "eof":
            argv = (
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import sys; sys.stderr.write('PRIVATE_NATIVE_STDERR')",
            )
        async with RuntimeHost(root, _test_launch=LaunchFixture(argv, root)) as host:
            with pytest.raises((TimeoutError, ProtocolError)):
                await host._launch(
                    {"generation": 0, "epoch": 1, "deadline_ns": time.monotonic_ns() + 500_000_000}
                )
            assert host.process is not None and host.process.returncode is not None
            assert not Path(f"/proc/{host.process.pid}").exists()
            assert host.state == "UNCERTAIN"
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err == f"RUNTIME_LAUNCH_FAILURE phase=HANDSHAKE error={kind}\n"
