"""Synthetic Engine UDS only: these are not physical Docker tests."""

import importlib
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from omnis_cli.lifecycle import StartError


class EnginePeer:
    def __init__(self, path: Path, status: int = 204, *, trickle: bool = False) -> None:
        self.path, self.status, self.trickle = path, status, trickle
        self.requests: list[str] = []
        self.raw_reply: bytes | None = None
        self.mutation_reply: bytes | None = None
        self.fragment_size = 0
        self.done = threading.Event()
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(path))
        self.sock.listen()
        self.sock.settimeout(0.1)
        self.thread = threading.Thread(target=self.serve)
        self.thread.start()

    def serve(self) -> None:
        while not self.done.is_set():
            try:
                peer, _ = self.sock.accept()
            except TimeoutError:
                continue
            with peer:
                raw = bytearray()
                peer.settimeout(1)
                while b"\r\n\r\n" not in raw:
                    part = peer.recv(4096)
                    if not part:
                        break
                    raw.extend(part)
                line = raw.decode().split("\r\n")[0]
                self.requests.append(line)
                code = 200 if line.startswith("GET /info ") else self.status
                body = json.dumps({"ID": "synthetic-stop-daemon"}).encode() if code == 200 else b""
                response = (
                    f"HTTP/1.1 {code} Synthetic\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
                if self.raw_reply is not None:
                    response = self.raw_reply
                elif self.mutation_reply is not None and not line.startswith("GET /info "):
                    response = self.mutation_reply
                try:
                    if self.trickle:
                        for byte in response:
                            peer.sendall(bytes([byte]))
                            if self.done.wait(0.03):
                                break
                    elif self.fragment_size:
                        for offset in range(0, len(response), self.fragment_size):
                            peer.sendall(response[offset : offset + self.fragment_size])
                            if self.done.wait(0.001):
                                break
                    else:
                        peer.sendall(response)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    def close(self) -> None:
        self.done.set()
        self.thread.join(2)
        self.sock.close()
        self.path.unlink()
        assert not self.thread.is_alive()


class StopEngineTests(unittest.TestCase):
    def test_wire_response_cap_still_includes_headers(self):
        from omnis_cli.stop_engine import MAX_RESPONSE, StopEngine

        for size in (MAX_RESPONSE, MAX_RESPONSE + 1):
            with (
                self.subTest(size=size),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name,
            ):
                body = b'{"ID":"synthetic-stop-daemon"}'
                length = size
                for _ in range(3):
                    header = f"HTTP/1.1 200 OK\r\nContent-Length: {length}\r\n\r\n".encode()
                    length = size - len(header)
                response = header + body + b" " * (length - len(body))
                self.assertEqual(len(response), size)
                peer = EnginePeer(Path(name) / "e")
                peer.raw_reply = response
                try:
                    engine = StopEngine(
                        "unix://" + str(peer.path), "synthetic-stop-daemon", time.monotonic() + 3
                    )
                    if size == MAX_RESPONSE:
                        engine.check_daemon()
                    else:
                        with self.assertRaisesRegex(StartError, "STOP_ENGINE_RESPONSE_INVALID"):
                            engine.check_daemon()
                finally:
                    peer.close()

    def test_entire_status_header_block_cap_exact_and_fragmented(self):
        from omnis_cli.stop_engine import StopEngine

        for fragment_size in (0, 137):
            for shape in ("status", "field", "many"):
                for size in (16383, 16384, 16385, 20500):
                    with (
                        self.subTest(fragment_size=fragment_size, shape=shape, size=size),
                        tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name,
                    ):
                        prefix = b"HTTP/1.1 204 "
                        if shape != "status":
                            prefix += b"OK\r\n"
                            if shape == "many":
                                prefix += b"".join(f"x-{i}:\r\n".encode() for i in range(1200))
                            prefix += b"X-Pad: "
                        reply = prefix + b"A" * (size - len(prefix) - 4) + b"\r\n\r\n"
                        self.assertEqual(len(reply), size)
                        peer = EnginePeer(Path(name) / "e")
                        peer.mutation_reply, peer.fragment_size = reply, fragment_size
                        try:
                            engine = StopEngine(
                                "unix://" + str(peer.path),
                                "synthetic-stop-daemon",
                                time.monotonic() + 3,
                            )
                            if size <= 16384:
                                self.assertEqual(engine.stop_container("a" * 64), 204)
                            else:
                                with self.assertRaisesRegex(
                                    StartError, "STOP_ENGINE_RESPONSE_INVALID"
                                ):
                                    engine.stop_container("a" * 64)
                            self.assertEqual(
                                peer.requests,
                                [
                                    "GET /info HTTP/1.1",
                                    f"POST /containers/{'a' * 64}/stop?t=15 HTTP/1.1",
                                ],
                            )
                        finally:
                            peer.close()

    def test_caps_deep_json_and_chunked_reply_on_same_socket(self):
        from omnis_cli.stop_engine import StopEngine

        body = b'{"ID":"synthetic-stop-daemon"}'
        chunked = (
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            + f"{len(body):x}\r\n".encode()
            + body
            + b"\r\n0\r\n\r\n"
        )
        deep = b'{"ID":"synthetic-stop-daemon","extra":' + b"[" * 1100 + b"0" + b"]" * 1100 + b"}"
        deep_response = f"HTTP/1.1 200 OK\r\nContent-Length: {len(deep)}\r\n\r\n".encode() + deep
        for response in (
            chunked,
            b"HTTP/1.1 200 OK\r\nContent-Length: 1048577\r\n\r\n",
            deep_response,
        ):
            with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
                peer = EnginePeer(Path(name) / "e")
                peer.raw_reply = response
                try:
                    engine = StopEngine(
                        "unix://" + str(peer.path), "synthetic-stop-daemon", time.monotonic() + 1
                    )
                    if response == chunked:
                        engine.check_daemon()
                    else:
                        with self.assertRaises(StartError):
                            engine.check_daemon()
                    self.assertEqual(len(peer.requests), 1)
                finally:
                    peer.close()

    def test_typed_mutation_requires_204_and_never_retries(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("omnis_cli.stop_engine"), "missing typed Engine"
        )
        from omnis_cli.stop_engine import StopEngine

        for status in (204, 304, 404, 500):
            with (
                self.subTest(status=status),
                tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name,
            ):
                peer = EnginePeer(Path(name) / "e", status)
                try:
                    engine = StopEngine(
                        "unix://" + str(peer.path), "synthetic-stop-daemon", time.monotonic() + 2
                    )
                    engine.check_daemon()
                    if status == 204:
                        self.assertEqual(engine.stop_container("a" * 64), 204)
                    else:
                        with self.assertRaises(StartError):
                            engine.stop_container("a" * 64)
                    effects = [x for x in peer.requests if x.startswith("POST")]
                    self.assertEqual(effects, [f"POST /containers/{'a' * 64}/stop?t=15 HTTP/1.1"])
                    with self.assertRaises(StartError):
                        engine.remove_container("../../foreign")
                finally:
                    peer.close()

    def test_trickling_headers_obey_one_total_deadline(self) -> None:
        from omnis_cli.stop_engine import StopEngine

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            peer = EnginePeer(Path(name) / "e", trickle=True)
            try:
                start = time.monotonic()
                engine = StopEngine(
                    "unix://" + str(peer.path), "synthetic-stop-daemon", start + 0.2
                )
                with self.assertRaises((StartError, TimeoutError)):
                    engine.check_daemon()
                self.assertLess(time.monotonic() - start, 0.8)
            finally:
                peer.close()
