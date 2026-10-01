"""Disposable reviewer-negative control; exclusive test subreaper, no Docker."""

import ctypes
import json
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import installed_start as probe


class NoDocker:
    uncertain = False
    family_drained = True

    def __init__(self, *args):
        pass

    def ids(self):
        return []

    def network(self, allowed):
        return None

    def inspect(self, *args):
        return None

    def run(self, *args, **kwargs):
        raise AssertionError("Uncertain oracle must not tear down DB")


def leaking_cli():
    root = Path(os.environ["XDG_STATE_HOME"]) / "omnis"
    (root / "http").mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    with socket.socket(socket.AF_UNIX) as peer:
        peer.bind(str(root / "http/api.sock"))
        (root / "http/api.sock").chmod(0o600)
        peer.listen(1)
        port = sys.argv[sys.argv.index("--port") + 1]
        subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-m",
                "omnis_cli.forwarder",
                "--socket-dir",
                str(root / "http"),
                "--port",
                port,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        record = {"phase": "FORWARDING", "containers": {}, "attempt": "test-only"}
        (root / "startup.json").write_text(json.dumps(record))
        stopped = False

        def stop(*args):
            nonlocal stopped
            stopped = True

        signal.signal(signal.SIGTERM, stop)
        while not stopped:
            select.select([], [], [], 0.005)
        record.update(phase="FAILED_CLEANED", cleanup=[], failed_phase="FORWARDING")
        (root / "startup.json").write_text(json.dumps(record))
        print(json.dumps({"dashboard_ready": False}))
    raise SystemExit(3)


def assert_failure_rescued():
    libc = ctypes.CDLL(None, use_errno=True)
    old = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(old), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    pins, observations, states = [], [], []

    class Observation(probe.ForwarderObservation):
        def __init__(self, *args):
            super().__init__(*args)
            observations.append(self)
            states.append(self.root.parent.parent)

        def pin(self, pid):
            prior = pid in self.pins
            super().pin(pid)
            if not prior:
                pins.append((pid, os.dup(self.pins[pid])))

    try:
        with tempfile.TemporaryDirectory(prefix="op-", dir=os.environ["TMPDIR"]) as name:
            fixture = Path(name) / "cli"
            fixture.write_text(
                f'#!/bin/sh\nexec {sys.executable} -I {Path(__file__).resolve()} --leaking-cli "$@"\n'
            )
            fixture.chmod(0o700)
            with (
                patch.object(probe, "ControlRuntime", NoDocker),
                patch.object(probe, "ForwarderObservation", Observation),
            ):
                try:
                    probe.run_interrupted_start(
                        Path(name) / "data",
                        {"project": "test-only"},
                        str(fixture),
                        phase="FORWARDING",
                    )
                except AssertionError as failure:
                    assert "forwarder" in str(failure) and "alive" in str(failure), str(failure)
                else:
                    raise AssertionError("Live unjournaled listener must FAIL product oracle")
            assert len(pins) == 1
            for pid, pin in pins:
                assert select.select([pin], [], [], 0)[0], "Harness lost rescue of pinned forwarder"
                os.waitpid(pid, 0)
            for observer in observations:
                observer.assert_absent()
            for state in states:
                receipt = json.loads((state / "probe-receipt.json").read_text())
                assert receipt["probe"] == "FAIL" and receipt["cleanup"] == "UNCERTAIN"
            print(
                "PRE_RESCUE_FAIL_PRESERVED; OBSERVER_RESCUE_EXITED_LISTENER_ABSENT; NO_DB_EFFECTS"
            )
    finally:
        for pid, pin in pins:
            if not select.select([pin], [], [], 0)[0]:
                signal.pidfd_send_signal(pin, signal.SIGKILL)
            assert select.select([pin], [], [], 5)[0]
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass  # The assertion path already reaped this exact child.
            os.close(pin)
        assert libc.prctl(36, old.value, 0, 0, 0) == 0


if __name__ == "__main__":
    if "--leaking-cli" in sys.argv:
        leaking_cli()
    else:
        assert_failure_rescued()
