"""SOURCE fixed relay: controlled DNS only, never public name resolution."""

import asyncio
import os
import socket
import ssl
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli import forwarder


def hello(host="auth.openai.com"):
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    connection = ssl.create_default_context().wrap_bio(
        incoming, outgoing, server_side=False, server_hostname=host
    )
    try:
        connection.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.read()


class AuthRelayTest(unittest.IsolatedAsyncioTestCase):
    async def test_numeric_connect_once_and_mixed_answer_never_connects(self):
        good = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))
        bad = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))
        from unittest.mock import AsyncMock

        for rows in ([good], [good, bad]):
            with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
                root = Path(name)
                with (
                    patch.object(socket, "getaddrinfo", return_value=rows) as dns,
                    patch.object(
                        asyncio.get_running_loop(),
                        "sock_connect",
                        new=AsyncMock(side_effect=ConnectionRefusedError),
                    ) as connect,
                ):
                    listener = await forwarder.start_auth_forwarder(root)
                    local = socket.socket(socket.AF_UNIX)
                    local.connect(str(root / "auth-egress.sock"))
                    reader, writer = await asyncio.open_unix_connection(sock=local)
                    writer.write(hello())
                    await writer.drain()
                    try:
                        self.assertEqual(await asyncio.wait_for(reader.read(), 3), b"")
                        self.assertEqual(dns.call_count, 1)
                        self.assertEqual(connect.call_count, 1 if len(rows) == 1 else 0)
                        if len(rows) == 1:
                            self.assertEqual(connect.call_args.args[1], ("8.8.8.8", 443))
                    finally:
                        writer.close()
                        await writer.wait_closed()
                        listener.close()
                        await listener.wait_closed()
                        (root / "auth-egress.sock").unlink()

    async def test_full_dns_set_is_validated_before_any_connect(self):
        validate = getattr(forwarder, "auth_addresses", None)
        self.assertTrue(callable(validate), "auth address validator missing")
        good = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))
        self.assertEqual(validate([good]), [good])
        for address in (
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "224.0.0.1",
            "0.0.0.0",
            "192.0.2.1",
            "240.0.0.1",
        ):
            bad = (*good[:4], (address, 443))
            with self.subTest(address=address), self.assertRaises(ValueError):
                validate([good, bad])
        for address in (
            "::1",
            "::ffff:8.8.8.8",
            "fe80::1",
            "ff02::1",
            "2001:db8::1",
            "fec0::1",
            "2606:4700:4700::1111%eth0",
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                validate(
                    [
                        good,
                        (
                            socket.AF_INET6,
                            socket.SOCK_STREAM,
                            socket.IPPROTO_TCP,
                            "",
                            (address, 443, 0, 0),
                        ),
                    ]
                )
        with self.assertRaises(ValueError):
            validate([])

    async def test_start_is_inert_and_resolver_cancellation_stays_uncertain(self):
        start = getattr(forwarder, "start_auth_forwarder", None)
        self.assertTrue(callable(start), "auth listener missing")
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            entered, release = threading.Event(), threading.Event()
            calls = []

            def resolve(*args, **kwargs):
                calls.append((args, kwargs))
                entered.set()
                release.wait(3)
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))
                ]

            with patch.object(socket, "getaddrinfo", side_effect=resolve):
                listener = await start(root)
                self.assertEqual(calls, [])
                path = root / "auth-egress.sock"
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(
                    listener.auth_identity["socket"], [path.stat().st_dev, path.stat().st_ino]
                )
                reader, writer = await asyncio.open_unix_connection(str(path))
                writer.write(hello())
                await writer.drain()
                try:
                    for _ in range(100):
                        if entered.is_set():
                            break
                        await asyncio.sleep(0.005)
                    self.assertTrue(entered.is_set())
                    listener.close()
                    with self.assertRaisesRegex(ValueError, "resolver"):
                        await listener.wait_closed()
                    self.assertEqual(await reader.read(), b"")
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0][0], ("auth.openai.com", 443))
                finally:
                    release.set()
                    writer.close()
                    await writer.wait_closed()
                    for _ in range(100):
                        if not listener.resolver_alive:
                            break
                        await asyncio.sleep(0.005)
                    listener.close()
                    await listener.wait_closed()
                    path.unlink()

    async def test_stale_socket_never_adopted_or_removed(self):
        start = getattr(forwarder, "start_auth_forwarder", None)
        self.assertTrue(callable(start), "auth listener missing")
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            path = root / "auth-egress.sock"
            with socket.socket(socket.AF_UNIX) as stale:
                stale.bind(str(path))
            before = path.stat().st_ino
            with self.assertRaises((ValueError, OSError)):
                await start(root)
            self.assertEqual(path.stat().st_ino, before)


class FiniteTlsTest(unittest.TestCase):
    def test_product_destinations_and_unknown_sni(self):
        for host in ("auth.openai.com", "chatgpt.com"):
            self.assertEqual(forwarder.tls_destination(hello(host)), host)
        for host in ("example.com", "localhost", "chatgpt.com.example.com"):
            with self.assertRaises(ValueError):
                forwarder.tls_destination(hello(host))
        for raw in (b"", b"CONNECT chatgpt.com:443\r\n", hello()[:-1]):
            with self.assertRaises(ValueError):
                forwarder.tls_destination(raw)
