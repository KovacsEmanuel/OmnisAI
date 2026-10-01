"""RT-F01: real owned forwarder, independent pidfd/listener, no Docker/DB."""

import importlib
import os
import select
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

start = importlib.import_module("omnis_cli.start")


class ForwarderHandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fh-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "http").mkdir(mode=0o700)
        self.api = socket.socket(socket.AF_UNIX)
        self.api.bind(str(self.root / "http/api.sock"))
        (self.root / "http/api.sock").chmod(0o600)
        self.api.listen(1)
        self.addCleanup(self.api.close)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.port = reservation.getsockname()[1]
        self.children = []
        self.listeners = []
        self.addCleanup(self.rescue)

    def rescue(self):
        for child, pin in self.children:
            try:
                if not select.select([pin], [], [], 0)[0]:
                    signal.pidfd_send_signal(pin, signal.SIGKILL)
                child.wait(timeout=3)
            finally:
                os.close(pin)
                for stream in (child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
        self.assertFalse(self.listener_rows())

    def listener_rows(self):
        return [
            row.split()
            for table in ("tcp", "tcp6")
            for row in Path(f"/proc/net/{table}").read_text().splitlines()[1:]
            if row.split()[3] == "0A" and int(row.split()[1].split(":")[1], 16) == self.port
        ]

    def attempt(self, boundary):
        spawn, pin, fdopen = subprocess.Popen, os.pidfd_open, os.fdopen
        fired = False

        def interrupt():
            nonlocal fired
            if not fired:
                fired = True
                os.kill(os.getpid(), signal.SIGTERM)

        def observed_spawn(argv, **kwargs):
            child = spawn(argv, **kwargs)
            self.children.append((child, pin(child.pid)))
            close = child.stdout.close

            def observed_close():
                # Capture identity BEFORE the fault, independently of product journal.
                rows = self.listener_rows()
                if rows:
                    self.listeners.extend(int(row[9]) for row in rows)
                close()
                child.stdout.close = close
                if boundary == "stdout-close":
                    interrupt()
                elif boundary == "stdout-error":
                    raise OSError("synthetic close failure")

            child.stdout.close = observed_close
            if boundary == "spawn":
                interrupt()
            return child

        class Log:
            def __init__(self, fd, mode):
                self.file = fdopen(fd, mode)

            def __enter__(self):
                return self.file

            def __exit__(self, *args):
                self.file.close()
                if boundary == "log-close":
                    interrupt()

        def observed_pin(pid):
            if boundary == "pidfd-missing":
                raise OSError("synthetic pidfd failure")
            result = pin(pid)
            if boundary == "pidfd":
                interrupt()
            return result

        original_listener = start.listener_owned

        def observed_listener(*args):
            original_listener(*args)
            if boundary == "listener":
                interrupt()

        previous = signal.signal(signal.SIGTERM, start._interrupt)
        owned_process = None
        owned_pin = -1
        try:
            try:
                with (
                    patch.object(start.subprocess, "Popen", side_effect=observed_spawn),
                    patch.object(start.os, "pidfd_open", side_effect=observed_pin),
                    patch.object(start.os, "fdopen", side_effect=Log),
                    patch.object(start, "listener_owned", side_effect=observed_listener),
                ):
                    owned_process, owned_pin, _, _ = start.launch_forwarder(
                        self.root, self.port, time.monotonic() + 5
                    )
                if boundary == "handoff":
                    interrupt()
            except start.ForwarderStartError as exc:
                owned_process, owned_pin = exc.process, exc.pidfd
            except (KeyboardInterrupt, OSError):
                pass
            self.assertIsNotNone(owned_process, "Post-spawn failure lost cleanup ownership")
            self.assertIs(owned_process, self.children[0][0])
            runtime = SimpleNamespace(
                uncertain=False,
                family_drained=True,
                ids=lambda: [],
                network=lambda _: None,
            )

            def fixture_ipc_cleanup(*args):
                self.api.close()
                (self.root / "http/api.sock").unlink()
                return []

            with patch.object(start, "cleanup_startup_ipc", side_effect=fixture_ipc_cleanup):
                problems = start.cleanup_attempt(
                    runtime, self.root, self.root / "control", self.port, owned_process, owned_pin
                )
            if boundary == "pidfd-missing":
                self.assertIn("forwarder", problems)
                self.assertIsNone(owned_process.poll(), "Do not signal an unpinned numeric PID")
            else:
                if owned_process.returncode == -signal.SIGTERM:
                    # Stop before the child's handlers exist is conservatively
                    # uncertain, not a CLEANED certificate; IPC stays retained.
                    self.assertEqual(problems, ["forwarder", "IPC retained"])
                else:
                    self.assertEqual(problems, [])
                self.assertIsNotNone(owned_process.returncode)
                self.assertTrue(select.select([self.children[0][1]], [], [], 0)[0])
                self.assertFalse(
                    self.listener_rows(), "CLEANED cannot coexist with a live listener"
                )
        finally:
            signal.signal(signal.SIGTERM, previous)
            if owned_pin >= 0:
                os.close(owned_pin)

    def test_signal_during_spawn_preserves_child(self):
        self.attempt("spawn")

    def test_signal_during_log_close_preserves_child(self):
        self.attempt("log-close")

    def test_signal_after_pidfd_open_preserves_child(self):
        self.attempt("pidfd")

    def test_signal_after_listener_attestation_preserves_child(self):
        self.attempt("listener")

    def test_signal_during_stdout_finally_preserves_child(self):
        self.attempt("stdout-close")

    def test_stdout_close_error_preserves_child(self):
        self.attempt("stdout-error")

    def test_missing_pidfd_preserves_child_and_uncertainty(self):
        self.attempt("pidfd-missing")

    def test_failure_immediately_after_handoff_cleans_child(self):
        self.attempt("handoff")

    def test_positive_launch_and_cleanup_same_channel(self):
        self.attempt("positive")
