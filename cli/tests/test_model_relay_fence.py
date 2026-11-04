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
from omnis_cli.model_relay_protocol import decode, encode


class RelayRetentionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root.chmod(0o700)
        self.scope = {
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
        self.connects = []
        self.scope["operation_serial"] = 1
        loop = asyncio.get_running_loop()
        original_connect = loop.sock_connect

        async def connect(sock, address):
            if sock.family == socket.AF_UNIX:
                return await original_connect(sock, address)
            self.assertEqual(address, ("8.8.8.8", 443))
            self.connects.append(address)  # Readiness double; no INET syscall.

        def dns(host, port, **kwargs):
            self.assertEqual((host, port), ("openrouter.ai", 443))
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))]

        for patcher in (
            patch.object(socket, "getaddrinfo", dns),
            patch.object(loop, "sock_connect", connect),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.listener = await forwarder.start_auth_forwarder(self.root, model=True)
        self.capability = (self.root / "model-relay.cap").read_text()

    async def asyncTearDown(self):
        self.listener.close()
        await self.listener.wait_closed()

    async def rpc(self, action, scope=None, *, retire_through=0):
        current = self.scope if scope is None else scope
        frame = {
            "version": 2,
            "action": action,
            "request_id": str(uuid4()),
            "connection_id": str(uuid4()) if action == "OPEN" else None,
            "scope": current,
            "sequence": 0,
            "size": 0,
            "timeout_ms": 1000,
            "write_deadline": (datetime.now(UTC) + timedelta(seconds=0.4)).isoformat()
            if action == "OPEN"
            else None,
            "capability": self.capability,
            "retire_through": retire_through,
        }
        reader, writer = await asyncio.open_unix_connection(self.root / "model-egress.sock")
        try:
            writer.write(encode(frame))
            await writer.drain()
            return decode(await asyncio.wait_for(reader.readline(), 2))["status"]
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_fence_and_drain_survive_request_saturation(self):
        for _ in range(16384):
            self.assertEqual(await self.rpc("FENCE"), "OK")
        self.assertEqual(await self.rpc("FENCE"), "OK")
        self.assertEqual(await self.rpc("DRAIN"), "OK")
        self.assertFalse(self.connects)

    async def test_fenced_identity_cannot_be_reopened_by_changing_deadline(self):
        self.assertEqual(await self.rpc("OPEN"), "OK")
        self.assertEqual(await self.rpc("FENCE"), "OK")
        self.assertEqual(await self.rpc("DRAIN"), "OK")
        self.assertEqual(await self.rpc("OPEN"), "DENIED")
        changed = {
            **self.scope,
            "deadline": (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
        }
        self.assertEqual(await self.rpc("OPEN", changed), "DENIED")
        self.assertEqual(self.connects, [("8.8.8.8", 443)])

    async def test_data_quota_does_not_prevent_retirement_or_later_operations(self):
        self.assertEqual(await self.rpc("OPEN"), "OK")
        for _ in range(16384):
            self.assertEqual(await self.rpc("OPEN"), "DENIED")
        self.assertEqual(await self.rpc("FENCE"), "OK")
        self.assertEqual(await self.rpc("DRAIN", retire_through=1), "OK")
        for serial in range(2, 34):
            newer = {
                **self.scope,
                "id": str(uuid4()),
                "operation_serial": serial,
                "deadline": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
            }
            self.assertEqual(await self.rpc("OPEN", newer, retire_through=serial - 1), "OK")
            self.assertEqual(await self.rpc("FENCE", newer, retire_through=serial - 1), "OK")
            self.assertEqual(await self.rpc("DRAIN", newer, retire_through=serial), "OK")
        self.assertEqual(len(self.connects), 33)

    async def test_broker_restart_rotates_capability_and_bootstraps_retired_prefix(self):
        self.assertEqual(await self.rpc("FENCE"), "OK")
        self.assertEqual(await self.rpc("DRAIN", retire_through=1), "OK")
        self.listener.close()
        await self.listener.wait_closed()
        self.listener = await forwarder.start_auth_forwarder(self.root, model=True)
        self.assertEqual(await self.rpc("OPEN"), "DENIED")
        self.capability = (self.root / "model-relay.cap").read_text()
        self.assertEqual(await self.rpc("OPEN", retire_through=1), "DENIED")
        newer = {**self.scope, "id": str(uuid4()), "operation_serial": 2}
        self.assertEqual(await self.rpc("OPEN", newer, retire_through=1), "OK")

    async def test_retirement_rejects_gaps_and_changed_stale_scope(self):
        self.assertEqual(await self.rpc("FENCE"), "OK")
        self.assertEqual(await self.rpc("DRAIN", retire_through=2), "DENIED")
        self.assertEqual(await self.rpc("DRAIN", retire_through=1), "OK")
        changed = {
            **self.scope,
            "deadline": (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
        }
        self.assertEqual(await self.rpc("OPEN", changed, retire_through=1), "DENIED")
        newer = {**self.scope, "id": str(uuid4()), "operation_serial": 2}
        self.assertEqual(await self.rpc("OPEN", newer, retire_through=1), "OK")
        self.assertEqual(await self.rpc("FENCE", newer, retire_through=1), "OK")
        self.assertEqual(await self.rpc("DRAIN", newer, retire_through=2), "OK")
        self.assertEqual(await self.rpc("DRAIN", retire_through=1), "OK")
        self.assertEqual(await self.rpc("OPEN", newer, retire_through=1), "DENIED")

    async def test_controls_have_capacity_with_eight_data_clients_waiting(self):
        clients = []
        try:
            for _ in range(8):
                clients.append(await asyncio.open_unix_connection(self.root / "model-egress.sock"))
            await asyncio.sleep(0.02)
            self.assertEqual(await self.rpc("FENCE"), "OK")
            self.assertEqual(await self.rpc("DRAIN", retire_through=1), "OK")
        finally:
            for _, writer in clients:
                writer.close()
                await writer.wait_closed()


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
            scope["operation_serial"] = 1

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
                            "version": 2,
                            "action": action,
                            "request_id": str(uuid4()),
                            "connection_id": connection if action == "OPEN" else None,
                            "scope": scope,
                            "sequence": sequence,
                            "size": 0,
                            "timeout_ms": 1000,
                            "write_deadline": (
                                datetime.now(UTC) + timedelta(seconds=0.4)
                            ).isoformat()
                            if action == "OPEN"
                            else None,
                            "capability": cap,
                            "retire_through": 0,
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
