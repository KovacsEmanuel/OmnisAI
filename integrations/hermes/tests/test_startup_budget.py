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
async def test_installed_client_waits_for_startup_within_absolute_grant():
    class Authority:
        async def runtime_authority(self, owner, epoch, generation, *, inert_probe):
            assert inert_probe is True
            return RuntimeAuthority(generation, epoch, time.monotonic_ns() + 4_500_000_000)

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as raw:
        root = Path(raw)
        host = RuntimeHost(
            root,
            _test_launch=LaunchFixture(
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py")), "slow_ready"),
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
