"""Real forwarder, private UDS and live client; no Docker/PG."""

import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from omnis_cli.lifecycle import process_identity, read_record, write_record


class StopForwarderDrainTests(unittest.TestCase):
    def test_bound_drain_receipt_follows_live_transport_close(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            http = root / "http"
            http.mkdir(mode=0o700)
            upstream = socket.socket(socket.AF_UNIX)
            upstream.bind(str(http / "api.sock"))
            (http / "api.sock").chmod(0o600)
            upstream.listen()
            upstream.settimeout(2)
            reservation = socket.socket()
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
            reservation.close()
            attempt, command = str(uuid4()), str(uuid4())
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "omnis_cli.forwarder",
                    "--socket-dir",
                    str(http),
                    "--port",
                    str(port),
                    "--stop-attempt",
                    attempt,
                ],
                env={"PATH": "/usr/bin:/bin"},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            pidfd = os.pidfd_open(process.pid)
            try:
                assert process.stdout is not None
                self.assertTrue(select.select([process.stdout], [], [], 3)[0])
                self.assertEqual(os.read(process.stdout.fileno(), 128), b"FORWARDER_READY\n")
                identity = process_identity(process.pid)
                with socket.create_connection(("127.0.0.1", port), timeout=2) as browser:
                    browser.sendall(b"hello")
                    api, _ = upstream.accept()
                    with api:
                        api.settimeout(2)
                        self.assertEqual(api.recv(5), b"hello")
                        api.sendall(b"world")
                        self.assertEqual(browser.recv(5), b"world")
                        rows = Path("/proc/net/tcp").read_text().splitlines()[1:]
                        inode = next(
                            int(row.split()[9])
                            for row in rows
                            if row.split()[1] == f"0100007F:{port:04X}" and row.split()[3] == "0A"
                        )
                        intent = {
                            "version": 1,
                            "attempt": attempt,
                            "command_id": command,
                            "forwarder": identity,
                            "listener_inode": inode,
                        }
                        write_record(root / f"stop-forwarder-{attempt}.json", intent)
                        signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                        self.assertEqual(process.wait(timeout=5), 0)
                        self.assertEqual(browser.recv(1), b"")
                        self.assertEqual(api.recv(1), b"")
                        self.assertEqual(
                            read_record(root / f"stop-forwarder-{attempt}-drained.json"),
                            {**intent, "drained": True},
                        )
            finally:
                if process.poll() is None:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                process.wait(timeout=3)
                os.close(pidfd)
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                upstream.close()
