"""Real process controls for the test harness, without a DB or product traffic."""

import os
import signal
import subprocess
import sys

from e2e_processes import cleanup_all


def test_cleanup_reaps_every_owned_process_even_if_api_exits_unexpectedly() -> None:
    api = subprocess.Popen(
        [sys.executable, "-c", "raise SystemExit(1)"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    supervisor = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('READY'); time.sleep(60)",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert supervisor.stdout is not None and supervisor.stdout.readline().strip() == "READY"
        api.wait(timeout=3)
        outputs = cleanup_all([(api, False), (supervisor, False)], grace=0.1)
        assert len(outputs) == 2
        assert api.returncode == 1
        assert supervisor.returncode == -signal.SIGKILL
    finally:
        for process in (api, supervisor):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)


def test_cleanup_kills_an_owned_driver_descendant_in_a_separate_session() -> None:
    script = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
print(child.pid, flush=True)
time.sleep(60)
"""
    driver = subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        assert driver.stdout is not None
        child_pid = int(driver.stdout.readline().strip())
        cleanup_all([(driver, True)], grace=0.1)
        try:
            with open(f"/proc/{child_pid}/stat") as source:
                state = source.read().split(") ", 1)[1].split()[0]
            # proc_pid_stat(5): X is the transient dead state during reaping, not a live process.
            assert state in {"Z", "X"}, "Owned descendant is still running"
        except FileNotFoundError:
            pass
    finally:
        if driver.poll() is None:
            driver.kill()
        driver.wait(timeout=3)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
