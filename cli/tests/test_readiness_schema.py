"""AR01: exact readiness scalars through the real JSON/UDS HTTP boundary.

Only the control IPC channel is substituted; HTTP, parser, peer checks and
asset verification run unchanged. These are not live API/Docker startup tests.
"""

import contextlib
import importlib
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.health import dashboard
from omnis_cli.lifecycle import StartError


class ReadinessSchemaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ar1-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.valid = {
            "api_ready": True,
            "dashboard_ready": True,
            "assessment_ready": False,
            "reason": None,
            "dashboard_reason": None,
        }
        self.control = {
            "instance_id": "ar01-fixture",
            "assessment_ready": False,
            "shutdown_command_id": None,
        }
        self.files = {"web/index.html": b"owned index", "web/assets/app-1.js": b"owned asset"}

    @contextlib.contextmanager
    def peer(self, body):
        path = self.root / "api.sock"
        routes = []
        errors = []
        stop = threading.Event()
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(path))
        path.chmod(0o600)
        listener.listen(4)
        listener.settimeout(0.05)
        responses = {
            "/health/ready": body,
            "/": self.files["web/index.html"],
            "/assets/app-1.js": self.files["web/assets/app-1.js"],
        }

        def serve():
            try:
                while not stop.is_set():
                    try:
                        channel, _ = listener.accept()
                    except TimeoutError:
                        continue
                    with channel:
                        channel.settimeout(2)
                        request = b""
                        while b"\r\n\r\n" not in request:
                            part = channel.recv(4096)
                            if not part or len(request) + len(part) > 4096:
                                raise AssertionError("Missing or oversized HTTP request")
                            request += part
                        route = request.split(b" ")[1].decode("ascii")
                        if b"\r\nHost: 127.0.0.1:8765\r\n" not in request:
                            raise AssertionError("Unexpected Host")
                        routes.append(route)
                        content = responses[route]
                        channel.sendall(
                            f"HTTP/1.1 200 OK\r\nContent-Length: {len(content)}\r\n\r\n".encode()
                            + content
                        )
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=serve)
        worker.start()
        try:
            yield routes
        finally:
            stop.set()
            worker.join(timeout=3)
            listener.close()
            path.unlink()
            self.assertFalse(worker.is_alive(), "Owned UDS peer did not stop")
            self.assertFalse(os.path.lexists(path))
            self.assertEqual(errors, [])

    def probe(self):
        return dashboard(
            self.root,
            self.root,
            8765,
            "ar01-fixture",
            self.files,
            time.monotonic() + 3,
            forwarded=False,
            api_pid=os.getpid(),
        )

    def assert_refused(self, value):
        with (
            self.peer(json.dumps(value).encode()) as routes,
            patch("omnis_cli.health.request", return_value=self.control) as control,
        ):
            with self.assertRaises(StartError) as failure:
                self.probe()
            self.assertEqual(failure.exception.reason, "DASHBOARD_NOT_READY")
            self.assertEqual(failure.exception.code, 3)
            self.assertEqual(routes, ["/health/ready"])
            self.assertEqual(control.call_count, 1, "Invalid readiness reached post-health control")

    def test_exact_bool_control_verifies_assets_on_same_real_uds_channel(self):
        with (
            self.peer(json.dumps(self.valid).encode()) as routes,
            patch("omnis_cli.health.request", return_value=self.control) as control,
        ):
            self.assertEqual(self.probe(), self.control)
            self.assertEqual(routes, ["/health/ready", "/", "/assets/app-1.js"])
            self.assertEqual(control.call_count, 2)

    def test_each_readiness_flag_refuses_numeric_and_noncontractual_values(self):
        for field in ("api_ready", "dashboard_ready", "assessment_ready"):
            for value in (1, 1.0, 0, not self.valid[field], "ar01-secret-marker", None):
                with self.subTest(field=field, value=value, scalar_type=type(value).__name__):
                    self.assert_refused({**self.valid, field: value})

    def test_exact_fields_and_null_reasons_are_required(self):
        for field in self.valid:
            with self.subTest(missing=field):
                self.assert_refused(
                    {key: value for key, value in self.valid.items() if key != field}
                )
        with self.subTest(extra=True):
            self.assert_refused({**self.valid, "unexpected": "ar01-secret-marker"})
        for field in ("reason", "dashboard_reason"):
            for value in (True, False, 1, 1.0, 0, "", "ar01-secret-marker", [], {}):
                with self.subTest(field=field, value=value):
                    self.assert_refused({**self.valid, field: value})
        for value in ([], None, True, 1, "ar01-secret-marker"):
            with self.subTest(top_level=value):
                self.assert_refused(value)

    def test_duplicate_field_is_refused_by_real_json_parser(self):
        body = json.dumps(self.valid).removesuffix("}") + ',"api_ready":true}'
        with (
            self.peer(body.encode()) as routes,
            patch("omnis_cli.health.request", return_value=self.control) as control,
        ):
            with self.assertRaises(ValueError):
                self.probe()
            self.assertEqual(routes, ["/health/ready"])
            self.assertEqual(control.call_count, 1)

    def test_start_consumer_sanitizes_real_dashboard_refusal_without_ready_promotion(self):
        start = importlib.import_module("omnis_cli.start")
        # Substitute only startup preparation: the actual dashboard and start
        # refusal consumer remain real, without provisioning Docker or a DB.
        for value in (
            {**self.valid, "api_ready": 1},
            {**self.valid, "dashboard_ready": 1.0},
            {**self.valid, "assessment_ready": 0},
            {**self.valid, "reason": "ar01-secret-marker"},
            {**self.valid, "dashboard_reason": "ar01-secret-marker"},
        ):
            with (
                self.subTest(value=value),
                self.peer(json.dumps(value).encode()) as routes,
                patch("omnis_cli.health.request", return_value=self.control),
                patch.object(start, "start_instance", side_effect=lambda port: self.probe()),
                contextlib.redirect_stdout(io.StringIO()) as output,
                contextlib.redirect_stderr(io.StringIO()) as errors,
            ):
                self.assertEqual(start.start(port=None, as_json=True), 3)
                self.assertEqual(
                    json.loads(output.getvalue()),
                    {
                        "state": "FAILED",
                        "reason": "DASHBOARD_NOT_READY",
                        "dashboard_ready": False,
                        "assessment_ready": False,
                        "browser_opened": False,
                    },
                )
                self.assertEqual(errors.getvalue(), "")
                self.assertNotIn("ar01-secret-marker", output.getvalue())
                self.assertNotIn("Traceback", output.getvalue())
                self.assertEqual(routes, ["/health/ready"])
