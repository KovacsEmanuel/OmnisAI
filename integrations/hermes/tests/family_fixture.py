"""Disposable harness subreaper owns ONLY its own synthetic family."""

import asyncio
import ctypes
import json
import os
import select
import signal
import sys
import tempfile
import time
from pathlib import Path

from omnis_hermes.runtime_host import RuntimeHost, TestLaunch


async def run():
    assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-family-") as name:
        root = Path(name)
        root.chmod(0o700)
        async with RuntimeHost(
            root,
            _test_launch=TestLaunch(
                (sys.executable, str(Path(__file__).with_name("peer_fixture.py")), "detached"), root
            ),
        ) as host:
            await host._launch(
                {"generation": 0, "epoch": 1, "deadline_ns": time.monotonic_ns() + 1_000_000_000}
            )
            reply = await host.peer.call("ping", {})
            child = reply["child_pid"]
            fd = os.pidfd_open(child)
            try:
                await host.stop()
                killed = bool(select.select([fd], [], [], 1)[0])
                if not killed:
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                os.waitpid(child, 0)  # Exact adopted synthetic child, never waitpid(-1).
                assert killed, "Runtime failed to kill detached descendant"
                assert not Path(f"/proc/{child}").exists()
                assert host.state == "UNCERTAIN"  # Harness is not product OCI containment.
                print(json.dumps({"detached_reaped": True, "state": host.state}))
            finally:
                os.close(fd)


asyncio.run(run())
