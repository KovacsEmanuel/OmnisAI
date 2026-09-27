"""Real process controls for the test harness, without a DB or product traffic."""

import os
import signal
import subprocess
import sys
from collections.abc import Iterator

import pytest

from e2e_processes import OwnedChildren, cleanup_all, owned_children, subreaper_state


@pytest.fixture
def family() -> Iterator[OwnedChildren]:
    previous = subreaper_state()
    with owned_children() as owner:
        yield owner
    assert subreaper_state() == previous


def test_cleanup_reaps_every_owned_process_even_if_api_exits_unexpectedly(
    family: OwnedChildren,
) -> None:
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
        outputs = cleanup_all([(api, False), (supervisor, False)], grace=0.1, ownership=family)
        assert len(outputs) == 2
        assert api.returncode == 1
        assert supervisor.returncode == -signal.SIGKILL
    finally:
        for process in (api, supervisor):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)


def test_cleanup_kills_an_owned_driver_descendant_in_a_separate_session(
    family: OwnedChildren,
) -> None:
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
        cleanup_all([(driver, True)], grace=0.1, ownership=family)
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


def test_adoption_cleanup_preserves_preexisting_children_and_restores_attribute() -> None:
    before = subreaper_state()
    existing = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        with owned_children() as owner:
            spawned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            owner.cleanup(grace=0.1)
            assert spawned.poll() is not None
            assert existing.poll() is None
        assert subreaper_state() == before
    finally:
        existing.terminate()
        existing.wait(timeout=3)


@pytest.mark.parametrize("driver_kind", ["python", "node"])
def test_cleanup_tracks_detached_child_after_driver_already_exited(
    family: OwnedChildren,
    driver_kind: str,
) -> None:
    script = """
import subprocess, sys
child = subprocess.Popen([sys.executable, '-u', '-c',
    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('READY'); time.sleep(60)"],
    start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
assert child.stdout.readline().strip() == b'READY'
print(child.pid, flush=True)
raise SystemExit(1)
"""
    command = [sys.executable, "-u", "-c", script]
    if driver_kind == "node":
        command = [
            "node",
            "-e",
            """
const { spawn } = require('node:child_process');
const child = spawn(process.argv[1], ['-u', '-c',
    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('READY'); time.sleep(60)"],
    { detached: true, stdio: ['ignore', 'pipe', 'ignore'] });
child.stdout.once('data', () => { console.log(child.pid); process.exit(1); });
""",
            sys.executable,
        ]
    driver = subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        stdout, _ = driver.communicate(timeout=3)
        child_pid = int(stdout.strip())
        assert driver.returncode == 1
        cleanup_all([(driver, True)], grace=0.1, ownership=family)
        try:
            with open(f"/proc/{child_pid}/stat") as source:
                state = source.read().split(") ", 1)[1].split()[0]
            assert state in {"Z", "X"}, "Early-exit driver lost its detached child"
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
