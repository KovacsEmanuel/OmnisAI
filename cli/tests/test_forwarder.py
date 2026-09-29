"""The host-only forwarder has one loopback listener and one private UDS peer."""

import asyncio
import os
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from omnis_cli.forwarder import start_forwarder


async def observe_bidirectional_progress(
    browser: socket.socket, body_seen: asyncio.Event, *, timeout: float
) -> None:
    """Require private request bytes and browser response bytes on the real sockets."""
    await asyncio.wait_for(body_seen.wait(), timeout)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            prefix = browser.recv(4, socket.MSG_PEEK)
        except BlockingIOError:
            prefix = b""
        if prefix == b"HTTP":
            return
        if prefix and not b"HTTP".startswith(prefix):
            raise AssertionError("unexpected browser response")
        await asyncio.sleep(0.02)
    raise TimeoutError("forwarded browser response not observed")


class ForwarderTest(unittest.IsolatedAsyncioTestCase):
    async def test_installed_style_process_stops_without_claiming_a_foreign_port(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                await reader.readuntil(b"\r\n\r\n")
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
                await writer.drain()
                writer.close()
                await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "omnis_cli.forwarder",
                    "--socket-dir",
                    str(directory),
                    "--port",
                    str(port),
                ],
                cwd=directory,
                env={"PATH": os.environ.get("PATH", "")},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                assert process.stdout is not None
                line = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), timeout=5)
                self.assertEqual(line.strip(), "FORWARDER_READY")
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(
                    b"GET /health/live HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
                )
                await writer.drain()
                self.assertIn(b"200 OK", await asyncio.wait_for(reader.read(4096), 3))
                writer.close()
                await writer.wait_closed()
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate(timeout=5)
                unix.close()
                await unix.wait_closed()
            self.assertEqual(process.returncode, 0)

    async def test_loopback_request_reaches_only_its_private_unix_peer(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            received: list[bytes] = []

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                received.append(await reader.readuntil(b"\r\n\r\n"))
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
                await writer.drain()
                writer.close()
                await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            try:
                forward = await start_forwarder(directory, port=0)
                try:
                    address = forward.sockets[0].getsockname()
                    self.assertEqual(address[0], "127.0.0.1")
                    client, peer = await asyncio.open_connection("127.0.0.1", address[1])
                    peer.write(
                        b"GET /health/live HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
                    )
                    await peer.drain()
                    response = await asyncio.wait_for(client.read(4096), 3)
                    self.assertEqual(
                        response,
                        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK",
                    )
                    self.assertEqual(
                        received,
                        [
                            b"GET /health/live HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
                        ],
                    )
                    peer.close()
                    await peer.wait_closed()
                finally:
                    forward.close()
                    await forward.wait_closed()
            finally:
                unix.close()
                await unix.wait_closed()

    async def test_foreign_loopback_port_is_never_adopted(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            upstream = await asyncio.start_unix_server(
                lambda _reader, writer: writer.close(), path=str(directory / "api.sock")
            )
            (directory / "api.sock").chmod(0o600)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as foreign:
                    foreign.bind(("127.0.0.1", 0))
                    foreign.listen(1)
                    port = foreign.getsockname()[1]
                    with self.assertRaises(OSError):
                        await start_forwarder(directory, port=port)
                    self.assertEqual(foreign.getsockname()[1], port)
            finally:
                upstream.close()
                await upstream.wait_closed()

    async def test_bound_but_not_listening_foreign_port_is_not_adopted(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            upstream = await asyncio.start_unix_server(
                lambda _reader, writer: writer.close(), path=str(directory / "api.sock")
            )
            (directory / "api.sock").chmod(0o600)
            forward = None
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as foreign:
                    foreign.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    foreign.bind(("127.0.0.1", 0))
                    port = foreign.getsockname()[1]
                    with self.assertRaises(OSError):
                        forward = await start_forwarder(directory, port=port)
                    foreign.listen(1)
                    self.assertEqual(foreign.getsockname()[1], port)
            finally:
                if forward is not None:
                    forward.close()
                    await forward.wait_closed()
                upstream.close()
                await upstream.wait_closed()

    async def test_full_sized_asset_and_next_keepalive_response_are_not_cut(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            asset = b"A" * (2 * 1024 * 1024)
            first = (
                b"HTTP/1.1 200 OK\r\nContent-Length: 2097152\r\nConnection: keep-alive\r\n\r\n"
                + asset
            )
            second = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    await reader.readuntil(b"\r\n\r\n")
                    writer.write(first)
                    await writer.drain()
                    await reader.readuntil(b"\r\n\r\n")
                    writer.write(second)
                    await writer.drain()
                except (asyncio.IncompleteReadError, ConnectionError):
                    pass
                finally:
                    writer.close()
                    await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            forward = await start_forwarder(directory, port=0)
            client, peer = await asyncio.open_connection(
                "127.0.0.1", forward.sockets[0].getsockname()[1]
            )
            try:
                peer.write(b"GET /assets/large HTTP/1.1\r\nHost: localhost\r\n\r\n")
                await peer.drain()
                self.assertEqual(await asyncio.wait_for(client.readexactly(len(first)), 5), first)
                peer.write(b"GET /assets/next HTTP/1.1\r\nHost: localhost\r\n\r\n")
                await peer.drain()
                self.assertEqual(await asyncio.wait_for(client.readexactly(len(second)), 5), second)
            finally:
                peer.close()
                await peer.wait_closed()
                forward.close()
                await forward.wait_closed()
                unix.close()
                await unix.wait_closed()

    async def test_excess_idle_clients_never_open_extra_private_peers(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            accepted = 0
            admitted = asyncio.Event()
            release = asyncio.Event()

            async def upstream(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                nonlocal accepted
                accepted += 1
                if accepted >= 16:
                    admitted.set()
                try:
                    await release.wait()
                finally:
                    writer.close()
                    await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            forward = await start_forwarder(directory, port=0)
            clients: list[asyncio.StreamWriter] = []
            try:
                address = forward.sockets[0].getsockname()
                for _ in range(20):
                    _reader, writer = await asyncio.open_connection("127.0.0.1", address[1])
                    clients.append(writer)
                await asyncio.wait_for(admitted.wait(), 3)
                await asyncio.sleep(0.1)
                self.assertEqual(accepted, 16)
            finally:
                release.set()
                for writer in clients:
                    writer.close()
                    await writer.wait_closed()
                forward.close()
                await asyncio.wait_for(forward.wait_closed(), 4)
                unix.close()
                await unix.wait_closed()

    async def test_close_drains_an_accepted_idle_client_within_deadline(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            accepted = asyncio.Event()

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                accepted.set()
                try:
                    await reader.read(1)
                finally:
                    writer.close()
                    await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            forward = await start_forwarder(directory, port=0)
            reader, peer = await asyncio.open_connection(
                "127.0.0.1", forward.sockets[0].getsockname()[1]
            )
            try:
                await asyncio.wait_for(accepted.wait(), 2)
                forward.close()
                await asyncio.wait_for(forward.wait_closed(), 1)
                self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
            finally:
                peer.close()
                await peer.wait_closed()
                forward.close()
                await asyncio.wait_for(forward.wait_closed(), 3)
                unix.close()
                await unix.wait_closed()

    async def test_process_sigterm_drains_idle_client_without_hanging(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            accepted = asyncio.Event()

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                accepted.set()
                await reader.read(1)
                writer.close()
                await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "omnis_cli.forwarder",
                    "--socket-dir",
                    str(directory),
                    "--port",
                    str(port),
                ],
                cwd=directory,
                env={"PATH": os.environ.get("PATH", "")},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            peer: asyncio.StreamWriter | None = None
            try:
                assert process.stdout is not None
                line = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 5)
                self.assertEqual(line.strip(), "FORWARDER_READY")
                reader, peer = await asyncio.open_connection("127.0.0.1", port)
                await asyncio.wait_for(accepted.wait(), 2)
                os.killpg(process.pid, signal.SIGTERM)
                await asyncio.wait_for(asyncio.to_thread(process.communicate, timeout=5), 6)
                self.assertEqual(process.returncode, 0)
                self.assertEqual(await asyncio.wait_for(reader.read(), 2), b"")
            finally:
                if peer is not None:
                    peer.close()
                    await peer.wait_closed()
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await asyncio.to_thread(process.communicate, timeout=5)
                unix.close()
                await unix.wait_closed()

    async def test_process_sigterm_aborts_nonreading_browser_after_large_asset(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            upstream_ready = asyncio.Event()
            body_seen = asyncio.Event()
            draining: asyncio.Task[None] | None = None

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                nonlocal draining
                try:
                    await reader.readuntil(b"\r\n\r\n")
                    response = (
                        b"HTTP/1.1 200 OK\r\nContent-Length: 8388608\r\nConnection: close\r\n\r\n"
                        + b"A" * (8 * 1024 * 1024)
                    )
                    writer.write(response)
                    draining = asyncio.create_task(writer.drain())
                    upstream_ready.set()
                    if await reader.readexactly(1) == b"B":
                        body_seen.set()
                    await draining
                    await reader.read()
                except (OSError, asyncio.IncompleteReadError):
                    pass
                finally:
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), 2)
                    except (OSError, TimeoutError):
                        writer.transport.abort()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "omnis_cli.forwarder",
                    "--socket-dir",
                    str(directory),
                    "--port",
                    str(port),
                ],
                cwd=directory,
                env={"PATH": os.environ.get("PATH", "")},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            browser = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            browser.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            browser.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            browser.setblocking(False)
            send_body: asyncio.Task[None] | None = None
            try:
                assert process.stdout is not None
                line = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 5)
                self.assertEqual(line.strip(), "FORWARDER_READY")
                loop = asyncio.get_running_loop()
                await loop.sock_connect(browser, ("127.0.0.1", port))
                await loop.sock_sendall(
                    browser,
                    b"POST /upload HTTP/1.1\r\nHost: 127.0.0.1:8765\r\n"
                    b"Content-Length: 1945600\r\n\r\n",
                )
                await asyncio.wait_for(upstream_ready.wait(), 2)
                send_body = asyncio.create_task(loop.sock_sendall(browser, b"B" * (1900 * 1024)))
                await observe_bidirectional_progress(browser, body_seen, timeout=2)
                # Neither the UDS peer nor the browser drains the opposite stream.
                await asyncio.sleep(0.3)
                self.assertFalse(send_body.done(), "request did not reach backpressure")
                self.assertIsNotNone(draining)
                assert draining is not None
                self.assertFalse(draining.done(), "response did not reach backpressure")
                os.killpg(process.pid, signal.SIGTERM)
                await asyncio.wait_for(asyncio.to_thread(process.communicate, timeout=6), 7)
                self.assertEqual(process.returncode, 0)
            finally:
                if send_body is not None:
                    send_body.cancel()
                    await asyncio.gather(send_body, return_exceptions=True)
                browser.close()
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await asyncio.to_thread(process.communicate, timeout=5)
                unix.close()
                await asyncio.wait_for(unix.wait_closed(), 3)

    async def test_progress_observer_rejects_header_only_or_bodyless_peer(self) -> None:
        browser, peer = socket.socketpair()
        browser.setblocking(False)
        try:
            peer.sendall(b"HTTP")
            with self.assertRaises(TimeoutError):
                await observe_bidirectional_progress(browser, asyncio.Event(), timeout=0.05)
            browser.recv(4)
            seen = asyncio.Event()
            seen.set()
            with self.assertRaises(TimeoutError):
                await observe_bidirectional_progress(browser, seen, timeout=0.05)
        finally:
            browser.close()
            peer.close()

    async def test_shutdown_closes_attached_handler_that_has_not_started(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            directory = Path(name)
            opened = 0

            async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                nonlocal opened
                opened += 1
                try:
                    await reader.read()
                finally:
                    writer.close()
                    await writer.wait_closed()

            unix = await asyncio.start_unix_server(upstream, path=str(directory / "api.sock"))
            (directory / "api.sock").chmod(0o600)
            forward = await start_forwarder(directory, port=0)
            loop = asyncio.get_running_loop()
            previous = loop.get_task_factory()
            self.assertIsNone(previous)
            attached = asyncio.Event()
            resume = asyncio.Event()

            def factory(
                event_loop: asyncio.AbstractEventLoop,
                coroutine: Coroutine[Any, Any, Any],
                **kwargs: Any,
            ) -> asyncio.Task[Any]:
                if getattr(getattr(coroutine, "cr_code", None), "co_name", None) == "handle":

                    async def pending_handler() -> None:
                        try:
                            await resume.wait()
                            await coroutine
                        finally:
                            coroutine.close()

                    task = asyncio.Task(pending_handler(), loop=event_loop, **kwargs)
                    attached.set()
                    return task
                return asyncio.Task(coroutine, loop=event_loop, **kwargs)

            browser = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            browser.setblocking(False)
            loop.set_task_factory(factory)
            try:
                await loop.sock_connect(browser, forward.sockets[0].getsockname())
                await asyncio.wait_for(attached.wait(), 2)
                forward.close()
                waiter = asyncio.create_task(forward.wait_closed())
                await asyncio.sleep(0.05)
                self.assertFalse(waiter.done(), "attached transport was not held by server")
                resume.set()
                await asyncio.wait_for(waiter, 3)
                self.assertEqual(opened, 0, "late handler opened a private API peer")
            finally:
                resume.set()
                loop.set_task_factory(previous)
                browser.close()
                forward.close()
                await asyncio.wait_for(forward.wait_closed(), 4)
                unix.close()
                await unix.wait_closed()
