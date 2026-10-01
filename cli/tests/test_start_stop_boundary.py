"""F-REV-02: first stop during the real recoverable readiness retry."""

import importlib
import os
import signal
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

start = importlib.import_module("omnis_cli.start")


class FirstStopBoundaryTest(unittest.TestCase):
    def test_first_stop_in_recoverable_retry_never_attempts_second_peer(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=sig):
                calls = []
                valid = {"admission_open": False, "generation": 0, "shutdown_command_id": None}

                def peer(*args, calls=calls, valid=valid, **kwargs):
                    calls.append(True)
                    if len(calls) == 1:
                        raise start.ControlUnavailable("synthetic transient peer")
                    return valid

                def stop_in_retry(duration, sig=sig):
                    os.kill(os.getpid(), sig)

                previous = signal.signal(sig, start._interrupt)
                try:
                    with (
                        patch.object(start, "dashboard", side_effect=peer),
                        patch.object(start.time, "sleep", side_effect=stop_in_retry),
                    ):
                        with self.assertRaises(KeyboardInterrupt):
                            start.wait_dashboard(
                                SimpleNamespace(deadline=time.monotonic() + 3, files={}),
                                Path("/unused"),
                                Path("/unused"),
                                23456,
                                "fixture",
                                os.getpid(),
                            )
                    self.assertEqual(len(calls), 1)
                finally:
                    signal.signal(sig, previous)

    def test_no_stop_retry_control_uses_the_same_channel(self):
        calls = []
        valid = {"admission_open": False, "generation": 0, "shutdown_command_id": None}

        def peer(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise start.ControlUnavailable("synthetic transient peer")
            return valid

        with patch.object(start, "dashboard", side_effect=peer), patch.object(start.time, "sleep"):
            result = start.wait_dashboard(
                SimpleNamespace(deadline=time.monotonic() + 3, files={}),
                Path("/unused"),
                Path("/unused"),
                23456,
                "fixture",
                os.getpid(),
            )
        self.assertEqual(result, valid)
        self.assertEqual(len(calls), 2)
