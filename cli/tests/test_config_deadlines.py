"""Measured local child deadlines, not Docker-daemon deadline certification."""

import contextlib
import importlib
import os
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, process_identity, write_record
from test_stop import private_stop_fixture


@contextlib.contextmanager
def resistant_child():
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(60)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    fd = os.pidfd_open(child.pid)
    finished, rescued = threading.Event(), threading.Event()

    def rescue():
        if not finished.wait(0.8):
            rescued.set()
            signal.pidfd_send_signal(fd, signal.SIGKILL)

    observer = threading.Thread(target=rescue)
    try:
        assert select.select([child.stdout], [], [], 3)[0]
        assert child.stdout.readline() == b"ready\n"
        observer.start()
        yield child, fd, rescued
    finally:
        finished.set()
        if observer.ident is not None:
            observer.join(2)
        if child.poll() is None:
            signal.pidfd_send_signal(fd, signal.SIGKILL)
        child.wait(timeout=3)
        os.close(fd)
        child.stdout.close()


class ConfigDeadlineTest(unittest.TestCase):
    def test_runtime_timeout_reap_does_not_add_fixed_five_seconds(self):
        from omnis_cli.start_runtime import ControlRuntime

        with tempfile.TemporaryDirectory(prefix="m22-run-", dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            executable = root / "owned-child"
            executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(60)\n")
            executable.chmod(0o700)
            runtime = ControlRuntime.__new__(ControlRuntime)
            runtime.docker = executable
            runtime.release = root
            runtime.host = "unix:///unused-owned-fixture"
            runtime.deadline = time.monotonic() + 0.15
            runtime.uncertain = False
            runtime.family_drained = True
            observed, children = [], []
            original = subprocess.Popen.wait

            def wait(child, timeout=None):
                observed.append(timeout)
                children.append(child)
                return original(child, timeout=timeout)

            try:
                with patch.object(subprocess.Popen, "wait", wait), self.assertRaises(StartError):
                    runtime.run("fixture", effect=True)
                self.assertTrue(observed)
                self.assertLessEqual(max(observed), 0.15)
                self.assertTrue(runtime.uncertain)
                self.assertFalse(runtime.family_drained)
            finally:
                for child in children:
                    child.wait(timeout=3)  # Parent-owned readback, not product deadline credit.

    def test_stop_forwarder_waits_share_remaining_deadline_on_both_paths(self):
        stop = importlib.import_module("omnis_cli.stop")
        for path in ("normal", "emergency"):
            with (
                self.subTest(path=path),
                private_stop_fixture() as (_base, root, _foreign, control, record, runtime),
                resistant_child() as (child, _fd, rescued),
            ):
                record.update(
                    phase="STOPPING", teardown_completed=[], forwarder=process_identity(child.pid)
                )
                journal = root / "startup.json"
                write_record(journal, record)
                ids = record["containers"]
                runtime.ids = lambda: list(ids.values())
                runtime.inspect = lambda *args: {"State": {"Running": True}}
                runtime.attest = lambda *args: {"State": {"Running": True}}
                runtime.network = lambda *args: "test-network"

                def no_daemon(*args, **kwargs):
                    raise StartError("DAEMON_REACHED", 4)

                runtime.run = no_daemon
                runtime.deadline = time.monotonic() + 0.2
                began = time.monotonic()
                with (
                    patch.object(stop, "listener_owned"),
                    patch.object(stop, "_listener_absent"),
                    patch.object(stop, "_finalized_db_readback"),
                    self.assertRaises(StartError) as error,
                ):
                    if path == "normal":
                        stop._resume_owned(runtime, root, control, journal, record)
                    else:
                        stop._emergency_drain(runtime, root, control, record)
                elapsed = time.monotonic() - began
                self.assertEqual(error.exception.reason, "FORWARDER_STOP_UNCERTAIN")
                self.assertLess(elapsed, 0.65)
                self.assertFalse(rescued.is_set(), "test fuse, not product, killed the child")
                self.assertEqual(child.wait(timeout=2), -signal.SIGKILL)
                self.assertEqual(record["teardown_completed"], [])

    def test_cleanup_forwarder_wait_cannot_extend_cleanup_deadline(self):
        from omnis_cli.start import stop_forwarder

        with resistant_child() as (child, fd, rescued):
            began = time.monotonic()
            with self.assertRaises(StartError) as error:
                stop_forwarder(child, fd, deadline=began + 0.2)
            self.assertEqual(error.exception.reason, "FORWARDER_CLEANUP_UNCERTAIN")
            self.assertLess(time.monotonic() - began, 0.65)
            self.assertFalse(rescued.is_set())
            self.assertEqual(child.wait(timeout=2), -signal.SIGKILL)
