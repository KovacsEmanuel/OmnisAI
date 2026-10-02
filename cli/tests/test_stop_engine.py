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
                try:
                    if self.trickle:
                        for byte in response:
                            peer.sendall(bytes([byte]))
                            if self.done.wait(0.03):
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
