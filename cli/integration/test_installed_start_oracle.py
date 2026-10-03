"""RT-PG01: real forwarder missing from journal must fail absence oracle."""

import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import installed_start


class IndependentForwarderOracleTest(unittest.TestCase):
    def test_invalid_attempt_is_not_observer_authority(self):
        for attempt in (
            None,
            True,
            1,
            {},
            [],
            "test-only",
            uuid4().hex,
            "ABCDEFAB-1234-4567-89ab-ABCDEFABCDEF",
        ):
            with self.subTest(attempt=attempt), self.assertRaises((AssertionError, ValueError)):
                installed_start.ForwarderObservation(Path("/unused"), 8765, os.getpid(), attempt)

    def test_missing_journal_identity_does_not_hide_live_forwarder(self):
        with tempfile.TemporaryDirectory(prefix="fo-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            attempt = str(uuid4())
            http = root / "http"
            http.mkdir(mode=0o700)
            with socket.socket(socket.AF_UNIX) as peer, socket.socket() as reservation:
                peer.bind(str(http / "api.sock"))
                (http / "api.sock").chmod(0o600)
                peer.listen(1)
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
                reservation.close()
                child = subprocess.Popen(
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
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                pin = os.pidfd_open(child.pid)
                observer = None
                try:
                    self.assertTrue(select.select([child.stdout], [], [], 5)[0])
                    self.assertEqual(child.stdout.readline(), b"FORWARDER_READY\n")
                    # The new flag is exact identity, not an arbitrary argv suffix.
                    for observed_root, observed_port, parent, nonce, reason in (
                        (root, port, os.getpid(), str(uuid4()), "argv"),
                        (root / "foreign", port, os.getpid(), attempt, "argv"),
                        (root, port + 1, os.getpid(), attempt, "argv"),
                        (root, port, os.getpid() + 1, attempt, "parent"),
                    ):
                        with self.subTest(boundary=reason, root=observed_root, nonce=nonce):
                            denied = installed_start.ForwarderObservation(
                                observed_root, observed_port, parent, nonce
                            )
                            before = set(Path("/proc/self/fd").iterdir())
                            try:
                                with self.assertRaisesRegex(
                                    AssertionError, "Unowned forwarder " + reason
                                ):
                                    denied.pin(child.pid)
                                self.assertEqual(denied.pins, {})
                                self.assertEqual(set(Path("/proc/self/fd").iterdir()), before)
                                self.assertIsNone(child.poll())
                            finally:
                                denied.close()
                    # Snapshot is observer-owned, not taken from a product journal.
                    observer = installed_start.ForwarderObservation(
                        root, port, os.getpid(), attempt
                    )
                    if observer is not None:
                        observer.pin(child.pid)
                        observer.snapshot_listener()
                    peer.close()
                    (http / "api.sock").unlink()
                    runtime = SimpleNamespace(ids=lambda: [], network=lambda _: None)
                    record = {"containers": {}, "phase": "FAILED_CLEANED"}
                    kwargs = {"observer": observer} if observer is not None else {}
                    with self.assertRaisesRegex(AssertionError, "forwarder|listener"):
                        installed_start.assert_resources_absent(
                            runtime, root, root / "control", record, **kwargs
                        )
                    signal.pidfd_send_signal(pin, signal.SIGTERM)
                    child.wait(timeout=25)
                    self.assertEqual(child.returncode, 0)
                    self.assertTrue(select.select([pin], [], [], 0)[0])
                    installed_start.assert_resources_absent(
                        runtime, root, root / "control", record, **kwargs
                    )
                finally:
                    if not select.select([pin], [], [], 0)[0]:
                        signal.pidfd_send_signal(pin, signal.SIGKILL)
                    child.wait(timeout=3)
                    os.close(pin)
                    if observer is not None:
                        observer.close()
                    for stream in (child.stdout, child.stderr):
                        stream.close()
