"""Private API client against an owned real UDS/synthetic peer."""

import asyncio
import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_api_client_checks_grant_and_channel_loss_stops_owned_peer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic_sensitive_marker")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic_sensitive_marker")
    assert importlib.util.find_spec("omnis.supervisor.runtime_client") is not None, (
        "private client missing"
    )
    from omnis_hermes.runtime_host import RuntimeHost, TestLaunch

    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.supervisor.runtime_client import RuntimeClient

    class Authority:
        async def runtime_authority(self, owner, epoch, generation, *, inert_probe):
            assert inert_probe is True
            return RuntimeAuthority(generation, epoch, time.monotonic_ns() + 1_000_000_000)

    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-") as name:
        root = Path(name)
        root.chmod(0o700)
        host = RuntimeHost(
            root,
            _test_launch=TestLaunch(
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py")), "environment"),
                root,
            ),
        )
        async with host:
            client = RuntimeClient(root, generation=2, epoch=3)
            await client.connect()
            try:
                status = await client.status()
                assert status["state"] == "IDLE"
                await client.launch_inert(Authority(), uuid4())
                assert (await client.status())["state"] == "READY"
                assert host.peer is not None
                next_id = host.peer.next_id
                with pytest.raises(ValueError):
                    await client._exchange("session.create")
                assert host.peer.next_id == next_id
                environment = await host.peer.call("ping", {})
                assert environment["env"]["HERMES_OMNIS_INERT"] == "1"
                assert environment["env"]["HOME"] == "/state/os-home"
                assert environment["env"]["HERMES_HOME"] == "/state/active"
                assert environment["env"]["CODEX_HOME"] == "/state/codex"
                assert "OPENAI_API_KEY" not in environment["env"]
                assert "ANTHROPIC_API_KEY" not in environment["env"]
                assert "PYTHONPATH" not in environment["env"]
                process = host.process
                assert process is not None
                await client.renew(Authority(), uuid4())
            finally:
                await client.close()
            await asyncio.sleep(0.3)
            assert process.returncode is not None
            assert host.state == "UNCERTAIN"
            assert not Path(f"/proc/{process.pid}").exists()
