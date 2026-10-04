"""Cleanup faults with an owned ACK child held alive until pinned observer rescue."""

import json
import os
import select
import signal
import socket
import subprocess
import time
import unittest
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, read_record
from omnis_cli.stop_owner import prepare_stop_inventory, run_stop_owner, verify_stop_completion
from omnis_cli.stop_receipt import receipt_path
from stop_owner_fixture import Fixture


class StopOwnerCleanupTests(unittest.TestCase):
    def test_signal_failure_still_attempts_reap_and_closes_handles(self):
        self.cleanup_fault("signal")

    def test_second_wait_failure_preserves_timeout_and_closes_handles(self):
        self.cleanup_fault("second_wait")

    def test_first_wait_failure_still_attempts_signal_and_reap(self):
        self.cleanup_fault("first_wait")

    def cleanup_fault(self, fault):
        fixture = Fixture()
        real_popen, real_pin = subprocess.Popen, os.pidfd_open
        real_signal, real_pair = signal.pidfd_send_signal, socket.socketpair
        reader, writer = os.pipe()
        owned, pins, channels, waits, signals = {}, [], [], [], []
        outcome = None
        facts = {}

        def pin(pid):
            fd = real_pin(pid)
            pins.append(fd)
            return fd

        def pair(*args):
            result = real_pair(*args)
            channels.extend(result)
            return result

        def popen(argv, **kwargs):
            # The test's pipe is a death fuse; no natural expiry during cleanup.
            # Alarm is only a last-resort bound, never credited as signal success.
            code = (
                "import os,signal,socket,sys; signal.alarm(12); "
                "s=socket.socket(fileno=int(sys.argv[1])); s.recv(16384); "
                "s.send(b'READY'); assert s.recv(128)==b'ADMIT'; s.send(b'DONE'); "
                "os.read(int(sys.argv[4]),1)"
            )
            kwargs["pass_fds"] = (*kwargs["pass_fds"], reader)
            process = real_popen([argv[0], "-I", "-c", code, *argv[4:], str(reader)], **kwargs)
            owned["process"] = process
            owned["observer"] = real_pin(process.pid)
            owned["wait"] = process.wait

            def wait(timeout=None):
                waits.append(timeout)
                if (fault == "second_wait" and len(waits) == 2) or (
                    fault == "first_wait" and len(waits) == 1
                ):
                    raise OSError("injected wait failure")
                return owned["wait"](timeout=timeout)

            process.wait = wait
            return process

        def send(fd, sig):
            signals.append((fd, sig))
            if fault == "signal":
                raise OSError("injected signal failure")
            # No-op syscall seam keeps the child live for the wait-failure test.
            # The independent observer below must actually kill and reap it.

        try:
            with fixture.original_locks() as (locks, guards):
                inventory = prepare_stop_inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record
                )
                start = time.monotonic()
                with (
                    patch("omnis_cli.stop_owner.subprocess.Popen", side_effect=popen),
                    patch("omnis_cli.stop_owner.os.pidfd_open", side_effect=pin),
                    patch("omnis_cli.stop_owner.socket.socketpair", side_effect=pair),
                    patch("omnis_cli.stop_owner.signal.pidfd_send_signal", side_effect=send),
                    patch(
                        "omnis_cli.stop_owner.os.kill",
                        side_effect=AssertionError("numeric PID fallback"),
                    ) as numeric,
                ):
                    try:
                        run_stop_owner(
                            fixture.runtime,
                            fixture.root,
                            fixture.control,
                            fixture.record,
                            fixture.grant(inventory),
                            lock_fds=locks,
                            guard_fds=guards,
                            deadline=start + 0.3,
                        )
                    except Exception as exc:
                        outcome = exc
                facts["elapsed"] = time.monotonic() - start
                facts["numeric_calls"] = numeric.call_count
                facts["channels_closed"] = all(channel.fileno() == -1 for channel in channels)
                facts["leaked"] = []
                for fd in pins:
                    try:
                        os.fstat(fd)
                    except OSError:
                        pass
                    else:
                        facts["leaked"].append(fd)
                facts["child_live"] = not select.select([owned["observer"]], [], [], 0)[0]
                facts["receipt"] = read_record(receipt_path(fixture.root, fixture.record))["state"]
                facts["effects"] = [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                with self.assertRaisesRegex(StartError, "STOP_RECEIPT_UNVERIFIED"):
                    verify_stop_completion(
                        fixture.runtime, fixture.root, fixture.control, fixture.record
                    )
        finally:
            try:
                if owned:
                    fd = owned["observer"]
                    try:
                        real_signal(fd, signal.SIGKILL)
                        ready = bool(select.select([fd], [], [], 2)[0])
                        observed = os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                        reaped = owned["wait"](timeout=2)
                        facts["rescue"] = [
                            ready,
                            observed.si_code if observed else None,
                            observed.si_status if observed else None,
                            reaped,
                        ]
                        with self.assertRaises(ChildProcessError):
                            os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
                    finally:
                        os.close(fd)
                # Rescue old-code FD leaks too, but retain the failing observation.
                for fd in pins:
                    try:
                        os.fstat(fd)
                    except OSError:
                        continue
                    os.close(fd)
                for channel in channels:
                    channel.close()
            finally:
                os.close(reader)
                os.close(writer)
                fixture.close()
        print(
            json.dumps({"fault": fault, "outcome": str(outcome), "waits": waits, **facts}),
            flush=True,
        )
        self.assertTrue(facts["child_live"], "natural fuse exit must not counterfeit cleanup")
        self.assertEqual(facts["rescue"], [True, os.CLD_KILLED, signal.SIGKILL, -signal.SIGKILL])
        self.assertEqual(facts["effects"], [])
        self.assertEqual(facts["receipt"], "PREPARED")
        self.assertEqual(facts["numeric_calls"], 0)
        self.assertEqual(len(pins), 1)
        self.assertEqual(len(channels), 2)
        self.assertEqual(signals, [(pins[0], signal.SIGKILL)])
        self.assertEqual(len(waits), 2, "failed signal or first wait must not skip bounded reap")
        self.assertEqual(waits[1], 2)
        self.assertLess(facts["elapsed"], 5)
        self.assertEqual(facts["leaked"], [])
        self.assertTrue(facts["channels_closed"])
        self.assertIsInstance(outcome, StartError)
        assert isinstance(outcome, StartError)
        self.assertEqual(outcome.reason, "STOP_OWNER_TIMEOUT")
        self.assertEqual(outcome.code, 4)
        self.assertEqual(outcome.__notes__, ["STOP_OWNER_CLEANUP_UNCERTAIN"])
