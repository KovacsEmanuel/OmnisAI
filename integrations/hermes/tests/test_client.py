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
    expected_environment = {
        "HOME": "/state/os-home",
        "HERMES_HOME": "/state/active",
        "CODEX_HOME": "/state/codex",
        "XDG_CONFIG_HOME": "/state/xdg/config",
        "XDG_CACHE_HOME": "/state/xdg/cache",
        "XDG_STATE_HOME": "/state/xdg/state",
        "XDG_DATA_HOME": "/state/xdg/data",
        "TMPDIR": "/state/tmp",
        "HERMES_MANAGED_DIR": "/state/managed-empty",
        "HERMES_DISABLE_LAZY_INSTALLS": "1",
        "HERMES_SKIP_NODE_BOOTSTRAP": "1",
        "HERMES_OMNIS_INERT": "1",
        "PATH": "/opt/hermes/venv/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONNOUSERSITE": "1",
    }
    # Keep fixture creation in the original owned scratch, not hostile TMPDIR.
    scratch = os.environ["TMPDIR"]
    for key in expected_environment:
        monkeypatch.setenv(key, "synthetic_hostile_ambient_value")
    forbidden = {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_BASE_URL",
        "HERMES_PROFILE",
        "HERMES_CONFIG",
        "HERMES_AUTH_FILE",
        "PYTHONPATH",
        "PYTHONHOME",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "LD_PRELOAD",
        "B05_UNLISTED_AMBIENT",
    }
    for key in forbidden:
        monkeypatch.setenv(key, "synthetic_sensitive_marker")
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

    with tempfile.TemporaryDirectory(dir=scratch, prefix="b05-") as name:
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
                assert isinstance(environment, dict)
                observed = environment["env"]
                assert isinstance(observed, dict)
                assert forbidden.isdisjoint(observed)
                assert "synthetic_sensitive_marker" not in observed.values()
                assert "synthetic_hostile_ambient_value" not in observed.values()
                # Independent literal contract; never import NATIVE_ENV as oracle.
                assert observed == expected_environment
                process = host.process
                assert process is not None
                await client.renew(Authority(), uuid4())
            finally:
                await client.close()
            await asyncio.sleep(0.3)
            assert process.returncode is not None
            assert host.state == "UNCERTAIN"
            assert not Path(f"/proc/{process.pid}").exists()
