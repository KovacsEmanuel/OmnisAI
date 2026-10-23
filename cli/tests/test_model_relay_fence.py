"""Actual finite host relay; DNS/connect are redirected only to owned loopback."""

import asyncio
import json
import os
import socket
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from omnis_cli import forwarder


class PhysicalFenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_fence_held_dns_denies_late_connect_and_drain_waits_for_resolver(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            root.chmod(0o700)
            entered, release = threading.Event(), threading.Event()
            connects = []
            scope = {
                "instance_id": str(uuid4()),
                "kind": "MODEL_DISPATCH",
                "id": str(uuid4()),
                "execution_owner_id": str(uuid4()),
                "generation": 1,
                "owner_epoch": 1,
                "cancel_epoch": 1,
                "deadline": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
                "provider": "openrouter",
            }
            connection = str(uuid4())

            def dns(host, port, **kwargs):
                self.assertEqual((host, port), ("openrouter.ai", 443))
                entered.set()
                if not release.wait(3):
                    raise OSError("fixture deadline")
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))
                ]

            original_connect = asyncio.get_running_loop().sock_connect

            async def denied_connect(sock, address):
                if sock.family == socket.AF_UNIX:
                    return await original_connect(sock, address)
                connects.append(address)
                raise AssertionError("FENCED_CONNECT")

            listener = None
            try:
                with (
                    patch.object(socket, "getaddrinfo", dns),
                    patch.object(asyncio.get_running_loop(), "sock_connect", denied_connect),
                ):
                    listener = await forwarder.start_auth_forwarder(root, model=True)
                    # The capability is local IPC authority, never a provider/API credential.
                    cap_path = root / "model-relay.cap"
                    cap = cap_path.read_text() if cap_path.exists() else "0" * 64

                    async def rpc(action, sequence=0):
                        reader, writer = await asyncio.open_unix_connection(
                            root / "model-egress.sock"
                        )
                        frame = {
                            "version": 1,
                            "action": action,
                            "request_id": str(uuid4()),
                            "connection_id": connection if action == "OPEN" else None,
                            "scope": scope,
                            "sequence": sequence,
                            "size": 0,
                            "timeout_ms": 1000,
                            "write_deadline": None,
                            "capability": cap,
                        }
                        try:
                            writer.write(json.dumps(frame).encode() + b"\n")
                            await writer.drain()
                            response = await asyncio.wait_for(reader.readline(), 2)
                            self.assertTrue(
                                response, "missing scoped physical relay acknowledgement"
                            )
                            return json.loads(response)
                        finally:
                            writer.close()
                            await writer.wait_closed()

                    opening = asyncio.create_task(rpc("OPEN"))
                    await asyncio.sleep(0.05)
                    if opening.done():
                        await (
                            opening
                        )  # Original relay refuses the framed protocol: intentional RED.
                    self.assertTrue(await asyncio.to_thread(entered.wait, 1))
                    self.assertEqual((await rpc("FENCE"))["status"], "OK")
                    self.assertEqual((await rpc("DRAIN"))["status"], "BUSY")
                    self.assertFalse(connects)
                    release.set()
                    self.assertEqual((await opening)["status"], "DENIED")
                    self.assertEqual((await rpc("DRAIN"))["status"], "OK")
                    self.assertFalse(connects)
            finally:
                release.set()
                if listener is not None:
                    listener.close()
                    await listener.wait_closed()
