"""Real sockets/processes for the startup observation and local lock boundaries."""

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from omnis_cli.health import http_probe
from omnis_cli.lifecycle import (
    StartError,
    lifecycle_lock,
    listener_owned,
    process_identity,
    read_record,
    write_record,
)
from omnis_cli.start import preflight_port


class StartBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="s2b-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_sigterm_enters_startup_failure_path_instead_of_abandoning_it(self):
        program = (
            "import importlib,os,signal\n"
            "s=importlib.import_module('omnis_cli.start')\n"
            "def interrupted(port):\n"
            " os.kill(os.getpid(),signal.SIGTERM)\n"
            " raise AssertionError('signal was ignored')\n"
            "s.start_instance=interrupted\n"
            "raise SystemExit(s.start(port=None,as_json=True))\n"
        )
        p = subprocess.run(
            [sys.executable, "-I", "-c", program], capture_output=True, text=True, timeout=3
        )
        self.assertEqual(p.returncode, 3)
        self.assertIn('"dashboard_ready": false', p.stdout)
        self.assertNotIn("Traceback", p.stderr)

    def test_same_image_project_serializes_different_state_roots(self):
        import importlib
        from concurrent.futures import ThreadPoolExecutor
        from types import SimpleNamespace
        from unittest.mock import patch

        start = importlib.import_module("omnis_cli.start")
        data = self.root / "data"
        (data / "omnis").mkdir(parents=True, mode=0o700)
        local = threading.local()
        active = peak = 0
        guard = threading.Lock()
        runtime = SimpleNamespace(
            receipt=SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_id="test-daemon",
            ),
            digest="c" * 64,
            host="unix:///run/docker.sock",
            ids=lambda: [],
            inspect=lambda *args: None,
        )

        def config(*args):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.15)
            with guard:
                active -= 1
            raise StartError("SYNTHETIC_BEFORE_DOCKER")

        def attempt(number):
            local.root = self.root / f"state-{number}"
            with self.assertRaisesRegex(StartError, "SYNTHETIC_BEFORE_DOCKER"):
                start.start_instance(48765)

        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": str(data)}),
            patch.object(start, "ControlRuntime", return_value=runtime),
            patch.object(start, "state_dir", side_effect=lambda: local.root),
            patch.object(start, "control_dir", side_effect=lambda root: root / "runtime-ipc"),
            patch.object(start, "preflight_port"),
            patch.object(start, "validate_config", side_effect=config),
            patch.object(start, "cleanup_attempt", return_value=[]),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            list(pool.map(attempt, (1, 2)))
        self.assertEqual(
            peak, 1, "One image project must have one lifecycle writer across XDG state roots"
        )

    def test_lock_serializes_processes_without_interpreting_stale_pid(self):
        lock = self.root / "lifecycle.lock"
        lock.write_text(str(os.getpid()))
        lock.chmod(0o600)
        with lifecycle_lock(self.root, time.monotonic() + 1):
            program = (
                "import sys,time; from pathlib import Path; "
                "from omnis_cli.lifecycle import lifecycle_lock,StartError\n"
                "try:\n"
                " with lifecycle_lock(Path(sys.argv[1]),time.monotonic()+0.15): print('bad')\n"
                "except StartError as e: print(e.reason)\n"
            )
            p = subprocess.run(
                [sys.executable, "-I", "-c", program, str(self.root)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stdout.strip(), "LIFECYCLE_BUSY")
        with lifecycle_lock(self.root, time.monotonic() + 1):
            self.assertEqual(lock.read_text(), str(os.getpid()))

    def test_lock_refuses_nonprivate_mode_and_symlink(self):
        path = self.root / "lifecycle.lock"
        path.write_text("synthetic")
        path.chmod(0o644)
        with self.assertRaises(StartError):
            with lifecycle_lock(self.root, time.monotonic() + 1):
                self.fail("unsafe lock acquired")
        path.unlink()
        path.symlink_to(self.root / "outside")
        with self.assertRaises(OSError):
            with lifecycle_lock(self.root, time.monotonic() + 1):
                self.fail("symlink acquired")
        self.assertFalse((self.root / "outside").exists())

    def test_start_record_is_atomic_private_and_no_replace_by_default(self):
        path = self.root / "startup.json"
        write_record(path, {"phase": "STARTING"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            write_record(path, {"phase": "READY"})
        self.assertEqual(read_record(path), {"phase": "STARTING"})
        write_record(path, {"phase": "FAILED_CLEANED"}, replace=True)
        self.assertEqual(read_record(path), {"phase": "FAILED_CLEANED"})

    def test_foreign_bound_socket_and_listener_refused_without_connection(self):
        for listening in (False, True):
            with self.subTest(listening=listening), socket.socket() as foreign:
                foreign.bind(("127.0.0.1", 0))
                if listening:
                    foreign.listen(1)
                with self.assertRaisesRegex(StartError, "PORT_CONFLICT"):
                    preflight_port(foreign.getsockname()[1])
                if listening:
                    foreign.settimeout(0.05)
                    with self.assertRaises(TimeoutError):
                        foreign.accept()

    def test_process_pid_alone_is_not_listener_ownership(self):
        identity = process_identity(os.getpid())
        with socket.socket() as owned:
            owned.bind(("127.0.0.1", 0))
            owned.listen(1)
            inode = os.fstat(owned.fileno()).st_ino
            port = owned.getsockname()[1]
            listener_owned(identity, port, inode)
            with self.assertRaisesRegex(StartError, "IDENTITY_MISMATCH"):
                listener_owned({**identity, "start_ticks": "0"}, port, inode)
            with self.assertRaisesRegex(StartError, "SOCKET_MISMATCH"):
                listener_owned(identity, port, inode + 1)

    def peer(self, payload, *, fragment=False, unix=False, followups=()):
        stop = threading.Event()
        path = self.root / "api.sock"
        listener = socket.socket(socket.AF_UNIX if unix else socket.AF_INET)
        listener.bind(str(path) if unix else ("127.0.0.1", 0))
        if unix:
            path.chmod(0o600)
        listener.listen(1)
        listener.settimeout(2)
        port = 8765 if unix else listener.getsockname()[1]

        def serve():
            try:
                for response in (payload, *followups):
                    channel, _ = listener.accept()
                    with channel:
                        channel.recv(4096)
                        for part in [bytes([b]) for b in response] if fragment else [response]:
                            channel.sendall(part)
                            if fragment and stop.wait(0.05):
                                break
            except OSError:
                pass
            finally:
                listener.close()

        worker = threading.Thread(target=serve)
        worker.start()

        def cleanup():
            stop.set()
            worker.join(timeout=3)
            listener.close()
            self.assertFalse(worker.is_alive())

        self.addCleanup(cleanup)
        return port

    def test_uds_peer_must_belong_to_the_attested_api_pid_namespace(self):
        from unittest.mock import patch

        port = self.peer(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok", unix=True)
        real = os.readlink
        expected = os.getpid() + 10000000

        def namespace(path):
            if str(path) == f"/proc/{expected}/ns/pid":
                return "pid:[synthetic-foreign-namespace]"
            return real(path)

        with patch("os.readlink", side_effect=namespace):
            with self.assertRaisesRegex(StartError, "API_PEER_MISMATCH"):
                http_probe(port, "/", time.monotonic() + 1, directory=self.root, api_pid=expected)

    def test_api_ready_200_does_not_promote_unavailable_dashboard(self):
        import json
        from unittest.mock import patch

        from omnis_cli.health import dashboard

        body = json.dumps(
            {
                "api_ready": True,
                "dashboard_ready": False,
                "assessment_ready": False,
                "reason": None,
                "dashboard_reason": "WEB_UNAVAILABLE",
            }
        ).encode()
        response = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body
        port = self.peer(response, unix=True)
        control = {"instance_id": "fixture", "assessment_ready": False, "shutdown_command_id": None}
        with patch("omnis_cli.health.request", return_value=control):
            with self.assertRaisesRegex(StartError, "DASHBOARD_NOT_READY"):
                dashboard(
                    self.root,
                    self.root,
                    port,
                    "fixture",
                    {},
                    time.monotonic() + 2,
                    forwarded=False,
                    api_pid=os.getpid(),
                )

    def test_healthy_projection_cannot_hide_corrupt_served_asset(self):
        import json
        from unittest.mock import patch

        from omnis_cli.health import dashboard

        body = json.dumps(
            {
                "api_ready": True,
                "dashboard_ready": True,
                "assessment_ready": False,
                "reason": None,
                "dashboard_reason": None,
            }
        ).encode()
        response = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body
        damaged = b"corrupt"
        asset = f"HTTP/1.1 200 OK\r\nContent-Length: {len(damaged)}\r\n\r\n".encode() + damaged
        port = self.peer(response, unix=True, followups=(asset,))
        control = {"instance_id": "fixture", "assessment_ready": False, "shutdown_command_id": None}
        with patch("omnis_cli.health.request", return_value=control):
            with self.assertRaisesRegex(StartError, "SERVED_ASSET_MISMATCH"):
                dashboard(
                    self.root,
                    self.root,
                    port,
                    "fixture",
                    {"web/index.html": b"trusted"},
                    time.monotonic() + 2,
                    forwarded=False,
                    api_pid=os.getpid(),
                )

    def test_actual_forwarder_bind_race_does_not_adopt_foreign_socket(self):
        from omnis_cli.start import ForwarderStartError, launch_forwarder, stop_forwarder

        http = self.root / "http"
        http.mkdir(mode=0o700)
        with socket.socket(socket.AF_UNIX) as api, socket.socket() as reservation:
            api.bind(str(http / "api.sock"))
            (http / "api.sock").chmod(0o600)
            api.listen(1)
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
            reservation.close()
            preflight_port(port)
            with socket.socket() as foreign:
                foreign.bind(("127.0.0.1", port))
                try:
                    launch_forwarder(self.root, port, time.monotonic() + 5)
                except ForwarderStartError as exc:
                    try:
                        stop_forwarder(exc.process, exc.pidfd)
                        self.assertEqual(exc.process.returncode, 3)
                    finally:
                        os.close(exc.pidfd)
                else:
                    self.fail("Foreign bind after preflight was adopted")
                self.assertEqual(foreign.getsockname()[1], port)

    def test_http_positive_and_declared_byte_limit(self):
        port = self.peer(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        self.assertEqual(http_probe(port, "/", time.monotonic() + 1, limit=2), b"ok")
        oversized = self.peer(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nbad")
        with self.assertRaisesRegex(StartError, "SIZE_LIMIT"):
            http_probe(oversized, "/", time.monotonic() + 1, limit=2)

    def test_trickled_headers_have_one_total_deadline_tcp_and_uds(self):
        for unix in (False, True):
            with self.subTest(unix=unix):
                port = self.peer(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok", fragment=True, unix=unix
                )
                begin = time.monotonic()
                with self.assertRaises((StartError, TimeoutError)):
                    http_probe(port, "/", begin + 0.25, directory=self.root if unix else None)
                self.assertLess(time.monotonic() - begin, 0.6)

    def test_http_redirect_is_refused_without_contacting_location(self):
        with socket.socket() as sink:
            sink.bind(("127.0.0.1", 0))
            sink.listen(1)
            port = self.peer(
                f"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:{sink.getsockname()[1]}/\r\nContent-Length: 0\r\n\r\n".encode()
            )
            with self.assertRaisesRegex(StartError, "HTTP_NOT_READY"):
                http_probe(port, "/", time.monotonic() + 1)
            sink.settimeout(0.05)
            with self.assertRaises(TimeoutError):
                sink.accept()
