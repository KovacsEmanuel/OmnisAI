"""Fresh-exec SIGCHLD regression, real children and intercepted numeric signals.

Only the Docker argv is substituted. No daemon or database is contacted.
"""

import errno
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from omnis_cli import start_runtime
from omnis_cli.lifecycle import StartError
from omnis_cli.start_runtime import ControlRuntime


def main():
    mode = sys.argv[1]
    original_spawn = subprocess.Popen
    handler_reaped = []

    def reaper(signum, frame):
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if not pid:
                return
            handler_reaped.append(pid)

    if mode == "handler":
        signal.signal(signal.SIGCHLD, reaper)
    policy = signal.getsignal(signal.SIGCHLD)
    if mode == "ignored" and policy != signal.SIG_IGN:
        raise AssertionError("SIG_IGN must arrive through exec, not fixture injection")
    if mode == "default" and policy != signal.SIG_DFL:
        raise AssertionError("Default control must start with SIG_DFL")

    # Prove the kernel/handler boundary independently of the product preflight.
    probe = original_spawn([sys.executable, "-I", "-c", "pass"])
    until = time.monotonic() + 2
    kernel_echild = False
    while time.monotonic() < until:
        try:
            state = os.waitid(os.P_PID, probe.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError as exc:
            kernel_echild = exc.errno == errno.ECHILD
            break
        if state is not None and mode == "default":
            break
        time.sleep(0.01)
    probe.wait(timeout=2)
    if mode != "default" and not kernel_echild:
        raise AssertionError("Real child did not reach ECHILD")

    runtime = ControlRuntime.__new__(ControlRuntime)
    runtime.deadline = time.monotonic() + 3
    runtime.uncertain = False
    runtime.family_drained = True
    runtime.docker = Path("/usr/bin/docker")
    runtime.release = Path(os.environ["TMPDIR"])
    runtime.host = "unix:///run/docker.sock"
    children, pins, attempts = [], [], []

    def launch(argv, **kwargs):
        child = original_spawn(
            [sys.executable, "-I", "-c", "import time; time.sleep(0.05); print('ack')"],
            **kwargs,
        )
        children.append(child)
        pins.append(os.pidfd_open(child.pid))  # Observer-owned rescue, never numeric.
        return child

    def numeric_signal(pid, sig):
        attempts.append([pid, int(sig)])  # Record before returning; never execute killpg.

    report = {"module": start_runtime.__file__, "kernel_echild": kernel_echild}
    try:
        with (
            patch("subprocess.Popen", side_effect=launch),
            patch("os.killpg", numeric_signal),
            patch("os.kill", numeric_signal),
        ):
            try:
                result = runtime.run("create", "synthetic", effect=True)
                report.update(outcome="completed", returncode=result.returncode)
            except (StartError, OSError) as exc:
                report.update(
                    outcome=type(exc).__name__, reason=str(exc), errno=getattr(exc, "errno", None)
                )
        report.update(
            spawned=len(children),
            attempts=attempts,
            uncertain=runtime.uncertain,
            drained=runtime.family_drained,
            policy_unchanged=signal.getsignal(signal.SIGCHLD) is policy,
            handler_reaped=bool(handler_reaped),
        )
    finally:
        for child, fd in zip(children, pins, strict=True):
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=2)
            for pipe in (child.stdout, child.stderr):
                if pipe is not None:
                    pipe.close()
            os.close(fd)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
