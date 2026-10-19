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
from omnis.supervisor.runtime_client import RuntimeClient


@pytest.mark.asyncio
async def test_installed_client_waits_for_startup_within_absolute_grant(capsys):
    class Authority:
        async def runtime_authority(self, owner, epoch, generation, *, inert_probe):
            assert inert_probe is True
            return RuntimeAuthority(generation, epoch, time.monotonic_ns() + 4_500_000_000)

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
                    "slow_ready",
                ),
                root,
            ),
        )
        async with host:
            client = RuntimeClient(root, generation=0, epoch=1)
            await client.connect()
            try:
                before = time.monotonic()
                ready = await client.launch_inert(Authority(), uuid4())
                assert time.monotonic() - before > 2
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
        assert capsys.readouterr().err == ""


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
