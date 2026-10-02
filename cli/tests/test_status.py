"""CLI status must not adopt a port or report an unverified dashboard as ready."""

import contextlib
import io
import json
import os
import socket
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.control import ControlUnavailable, request
from omnis_cli.lifecycle import write_record
from omnis_cli.main import main
from omnis_cli.start import READY_FIELDS
from omnis_cli.stop import STOP_FIELDS


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.original = os.environ.get("XDG_STATE_HOME")
        self.original_runtime = os.environ.pop("XDG_RUNTIME_DIR", None)
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        os.environ["XDG_STATE_HOME"] = self.temp.name
        self.addCleanup(self.restore_env)
        self.state = Path(self.temp.name) / "omnis"
        self.state.mkdir(mode=0o700)
        self.control = self.state / "runtime-ipc"
        self.control.mkdir(mode=0o700)
        self.identity = str(uuid4())

    def restore_env(self):
        if self.original is None:
            os.environ.pop("XDG_STATE_HOME", None)
        else:
            os.environ["XDG_STATE_HOME"] = self.original
        if self.original_runtime is not None:
            os.environ["XDG_RUNTIME_DIR"] = self.original_runtime

    def run_status(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["status", "--json"])
        return code, json.loads(out.getvalue()), err.getvalue()

    def write_instance(self, origin="http://127.0.0.1:8765"):
        record = {
            "version": 1,
            "instance_id": self.identity,
            "release": "0.1.0",
            "schema": "0004_pairing_receipts",
            "project": "omnis-local-1",
            "origin": origin,
        }
        path = self.state / "instance.json"
        path.write_text(json.dumps(record))
        path.chmod(0o600)
        return path

    def test_missing_instance_is_not_installed_without_creating_files(self):
        code, status, err = self.run_status()
        self.assertEqual(code, 3)
        self.assertEqual(status["state"], "NOT_INSTALLED")
        self.assertFalse(status["dashboard_ready"])
        self.assertEqual(err, "")
        self.assertFalse((self.state / "instance.json").exists())

    def test_stop_requested_does_not_claim_a_committed_database_barrier(self):
        self.write_instance()
        record: dict[str, object] = {key: None for key in READY_FIELDS}
        record.update(
            phase="STOPPING",
            attempt=str(uuid4()),
            port=8765,
            containers={"db": "d" * 64, "api": "a" * 64, "supervisor": "s" * 64},
            generation=1,
            supervisor_epoch=1,
            stop_command=str(uuid4()),
            stop_expected=1,
            stop_generation=None,
            finalize_command=str(uuid4()),
            finalized_generation=None,
            teardown_completed=[],
        )
        self.assertEqual(set(record), STOP_FIELDS)
        journal = self.state / "startup.json"
        write_record(journal, record)
        with patch("omnis_cli.status.ControlRuntime"):
            code, status, _ = self.run_status()
        self.assertEqual(code, 4)
        self.assertEqual(status["state"], "STOP_REQUESTED")
        self.assertEqual(status["reason"], "STOP_BARRIER_UNCONFIRMED")
        self.assertNotIn("admission_open", status)
        self.assertFalse(status["dashboard_ready"])
        record["stop_generation"] = 2
        write_record(journal, record, replace=True)
        with patch("omnis_cli.status.ControlRuntime"):
            code, status, _ = self.run_status()
        self.assertEqual(code, 4)
        self.assertEqual(status["state"], "STOPPING")
        self.assertEqual(status["reason"], "INSTANCE_SHUTTING_DOWN")

    def test_live_private_status_does_not_claim_unverified_http(self):
        self.write_instance()
        (self.control / "control.cap").write_text("a" * 64)
        (self.control / "control.cap").chmod(0o600)
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(self.control / "control.sock"))
        (self.control / "control.sock").chmod(0o600)
        listener.listen(1)
        self.addCleanup(listener.close)
        reply = {
            "ok": True,
            "correlation_id": str(uuid4()),
            "result_generation": None,
            "status": {
                "instance_id": self.identity,
                "generation": 2,
                "admission_open": False,
                "shutdown_command_id": None,
                "quiesced_generation": 2,
                "supervisor_epoch": 1,
                "supervisor_ready": True,
                "shutdown_finalized": False,
                "assessment_ready": False,
                "dashboard_ready": False,
            },
        }
        received = []

        def serve():
            conn, _ = listener.accept()
            with conn:
                received.append(json.loads(conn.recv(4096)))
                conn.sendall(json.dumps(reply).encode() + b"\n")

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        code, status, err = self.run_status()
        worker.join(timeout=2)
        self.assertEqual(code, 0)
        self.assertEqual(received[0]["command"], {"op": "status"})
        self.assertEqual(received[0]["capability"], "a" * 64)
        self.assertEqual(status["instance_id"], self.identity)
        self.assertTrue(status["control_ready"])
        self.assertFalse(status["dashboard_ready"])
        self.assertEqual(status["reason"], "HTTP_UNVERIFIED")
        self.assertNotIn("a" * 64, json.dumps(status) + err)

    def test_private_control_reply_missing_shutdown_field_is_not_accepted(self):
        (self.control / "control.cap").write_text("a" * 64)
        (self.control / "control.cap").chmod(0o600)
        status = {
            "instance_id": self.identity,
            "generation": 1,
            "admission_open": True,
            "quiesced_generation": None,
            "supervisor_epoch": 1,
            "supervisor_ready": True,
            "shutdown_finalized": False,
            "assessment_ready": False,
            "dashboard_ready": False,
        }
        reply = {"ok": True, "correlation_id": str(uuid4()), "status": status}
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(self.control / "control.sock"))
            (self.control / "control.sock").chmod(0o600)
            listener.listen(1)

            def serve():
                connection, _ = listener.accept()
                with connection:
                    connection.recv(4096)
                    connection.sendall(json.dumps(reply).encode() + b"\n")

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            with self.assertRaises(ControlUnavailable):
                request(self.control, {"op": "status"})
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())

    def test_command_reply_is_bound_to_id_generation_and_epoch(self):
        (self.control / "control.cap").write_text("a" * 64)
        (self.control / "control.cap").chmod(0o600)
        command = str(uuid4())
        sent = {
            "op": "shutdown",
            "instance_id": self.identity,
            "command_id": command,
            "expected_generation": 1,
        }
        valid = {
            "ok": True,
            "correlation_id": str(uuid4()),
            "command_id": command,
            "expected_generation": 1,
            "result_generation": 2,
            "owner_epoch": 3,
            "status": {
                "instance_id": self.identity,
                "generation": 2,
                "admission_open": False,
                "shutdown_command_id": command,
                "quiesced_generation": None,
                "supervisor_epoch": 3,
                "supervisor_ready": True,
                "shutdown_finalized": False,
                "assessment_ready": False,
                "dashboard_ready": False,
            },
        }
        for change in (
            {},
            {"command_id": str(uuid4())},
            {"expected_generation": 0},
            {"result_generation": 1},
            {"owner_epoch": 2},
            {"status": {**valid["status"], "generation": 3}},
            {"status": {**valid["status"], "admission_open": True}},
        ):
            reply = {**valid, **change}
            with socket.socket(socket.AF_UNIX) as listener:
                path = self.control / "control.sock"
                listener.bind(str(path))
                path.chmod(0o600)
                listener.listen(1)

                def serve(reply=reply):
                    connection, _ = listener.accept()
                    with connection:
                        connection.recv(4096)
                        connection.sendall(json.dumps(reply).encode() + b"\n")

                worker = threading.Thread(target=serve, daemon=True)
                worker.start()
                try:
                    if not change:
                        self.assertEqual(request(self.control, sent), valid["status"])
                    else:
                        with self.assertRaises(ControlUnavailable):
                            request(self.control, sent)
                finally:
                    worker.join(timeout=2)
                    self.assertFalse(worker.is_alive())
            path.unlink()

    def test_wrong_instance_identity_is_not_adopted(self):
        self.write_instance()
        # A foreign/non-socket path or capability must not be used as a live control plane.
        (self.control / "control.sock").write_text("foreign")
        code, status, _ = self.run_status()
        self.assertEqual(code, 3)
        self.assertFalse(status["control_ready"])
        self.assertEqual(status["reason"], "CONTROL_UNAVAILABLE")
        self.assertEqual((self.control / "control.sock").read_text(), "foreign")

    def test_non_private_metadata_is_refused_without_reflection(self):
        path = self.write_instance()
        path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        code, status, err = self.run_status()
        self.assertEqual(code, 2)
        self.assertEqual(status["state"], "CONFIG_INVALID")
        self.assertNotIn(self.identity, json.dumps(status) + err)

    def test_invalid_metadata_encoding_fails_closed_without_traceback(self):
        path = self.write_instance()
        path.write_bytes(b"\xff")
        code, status, err = self.run_status()
        self.assertEqual(code, 2)
        self.assertEqual(status["state"], "CONFIG_INVALID")
        self.assertEqual(err, "")

    def test_relative_state_root_is_invalid_even_if_missing(self):
        os.environ["XDG_STATE_HOME"] = "relative-location"
        code, status, err = self.run_status()
        self.assertEqual(code, 2)
        self.assertEqual(status["state"], "CONFIG_INVALID")
        self.assertEqual(err, "")

    def test_fragmented_control_reply_has_one_total_deadline(self):
        self.write_instance()
        (self.control / "control.cap").write_text("a" * 64)
        (self.control / "control.cap").chmod(0o600)
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(self.control / "control.sock"))
        (self.control / "control.sock").chmod(0o600)
        listener.listen(1)
        self.addCleanup(listener.close)

        def trickle():
            conn, _ = listener.accept()
            with conn:
                conn.recv(4096)
                try:
                    for fragment in (b"{", b" ", b" "):
                        conn.sendall(fragment)
                        time.sleep(1.35)
                except OSError:
                    return

        worker = threading.Thread(target=trickle, daemon=True)
        worker.start()
        start = time.monotonic()
        code, status, _ = self.run_status()
        elapsed = time.monotonic() - start
        self.assertEqual(code, 3)
        self.assertEqual(status["reason"], "CONTROL_UNAVAILABLE")
        self.assertLess(elapsed, 2.4, "Each fragment must not renew the IPC deadline")
        worker.join(timeout=5)

    def test_foreign_http_listener_is_not_adopted_by_private_status(self):
        with socket.socket() as foreign:
            foreign.bind(("127.0.0.1", 0))
            foreign.listen(1)
            foreign.settimeout(0.2)
            self.write_instance(f"http://127.0.0.1:{foreign.getsockname()[1]}")
            code, status, _ = self.run_status()
            self.assertEqual(code, 3)
            self.assertFalse(status["dashboard_ready"])
            with self.assertRaises(TimeoutError):
                foreign.accept()
