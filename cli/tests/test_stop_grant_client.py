"""Private Stop-grant client through real UDS; the DB peer is substituted."""

import contextlib
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from omnis_cli import control


class StopGrantClientTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sg-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        cap = self.directory / "control.cap"
        cap.write_text("a" * 64)
        cap.chmod(0o600)
        self.command = {
            "op": "arm_stop",
            "instance_id": str(uuid4()),
            "command_id": str(uuid4()),
            "finalize_command_id": str(uuid4()),
            "generation": 2,
            "owner_epoch": 1,
            "daemon_id": "synthetic-daemon",
            "inventory": {"version": 1, "pid": 7},
        }
        self.grant = {
            **{key: value for key, value in self.command.items() if key != "op"},
            "version": 1,
            "state": "STOP_PENDING",
            "owner_uuid": str(uuid4()),
        }
        self.valid = {"ok": True, "correlation_id": str(uuid4()), "grant": self.grant}

    @contextlib.contextmanager
    def peer(self, reply, delay: float = 0.0):
        path = self.directory / "control.sock"
        received, errors = [], []
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(path))
            path.chmod(0o600)
            listener.listen(1)
            listener.settimeout(2)

            def serve():
                try:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(2)
                        data = bytearray()
                        while not data.endswith(b"\n") and len(data) <= 4096:
                            part = connection.recv(4097 - len(data))
                            if not part:
                                break
                            data.extend(part)
                        received.append(json.loads(data))
                        if delay:
                            time.sleep(delay)
                        if reply is not None:
                            try:
                                connection.sendall(json.dumps(reply).encode() + b"\n")
                            except BrokenPipeError:
                                pass
                except BaseException as error:
                    errors.append(type(error).__name__)

            worker = threading.Thread(target=serve)
            worker.start()
            try:
                yield
            finally:
                worker.join(3)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(len(received), 1)
                self.assertEqual(received[0]["command"], self.command)
        path.unlink()

    def test_native_grant_and_each_binding_mutation_use_same_private_channel(self):
        with self.peer(self.valid):
            self.assertEqual(control.request(self.directory, self.command), self.grant)
        changes = [
            ("version", True),
            ("state", "STOP_UNCERTAIN"),
            ("state", []),
            ("instance_id", str(uuid4())),
            ("command_id", str(uuid4())),
            ("finalize_command_id", str(uuid4())),
            ("generation", 2.0),
            ("owner_epoch", True),
            ("owner_uuid", "invalid"),
            ("daemon_id", "foreign"),
            ("inventory", {"version": True, "pid": 7}),
            ("extra", 1),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                reply = {**self.valid, "grant": {**self.grant, key: value}}
                with self.peer(reply), self.assertRaises(control.ControlUnavailable):
                    control.request(self.directory, self.command)
        legacy = {key: value for key, value in self.grant.items() if key != "owner_uuid"}
        with (
            self.peer({**self.valid, "grant": legacy}),
            self.assertRaises(control.ControlUnavailable),
        ):
            control.request(self.directory, self.command)

    def test_invalid_outgoing_binding_is_refused_before_socket_contact(self):
        listener = socket.socket(socket.AF_UNIX)
        self.addCleanup(listener.close)
        path = self.directory / "control.sock"
        listener.bind(str(path))
        path.chmod(0o600)
        listener.listen(1)
        for key, value in (
            ("generation", True),
            ("generation", 0),
            ("generation", 2**63),
            ("owner_epoch", 1.0),
            ("command_id", "not-a-uuid"),
            ("daemon_id", "bad/daemon"),
            ("inventory", {"pid": 1.5}),
            ("inventory", {1: "coercible-key"}),
            ("extra", 1),
        ):
            with (
                self.subTest(key=key, value=value),
                patch.object(
                    control.socket,
                    "socket",
                    side_effect=AssertionError("control contact before validation"),
                ),
            ):
                with self.assertRaises(control.ControlUnavailable):
                    control.request(self.directory, {**self.command, key: value})

    def test_lost_ack_mixed_reply_and_timeout_never_return_a_grant(self):
        for reply in (None, {**self.valid, "status": {}}, {**self.valid, "ok": False}):
            with self.peer(reply), self.assertRaises(control.ControlUnavailable):
                control.request(self.directory, self.command)
        with self.peer(deepcopy(self.valid), delay=0.3):
            began = time.monotonic()
            with self.assertRaises(control.ControlUnavailable):
                control.request(self.directory, self.command, deadline=began + 0.05)
            self.assertLess(time.monotonic() - began, 0.5)
