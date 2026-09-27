"""Test-only bounded teardown of owned Popen handles and their Linux descendants."""

import ctypes
import os
import signal
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _identity(pid: int) -> tuple[int, str, str] | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return int(fields[1]), fields[19], fields[0]  # ppid, kernel start time, state
    except (OSError, ValueError, IndexError):
        return None  # Process disappeared during observation.


def _descendants(root: int) -> dict[int, str]:
    records = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdecimal():
            identity = _identity(int(entry.name))
            if identity is not None:
                records[int(entry.name)] = identity
    owned = {root}
    while True:
        children = {pid for pid, record in records.items() if record[0] in owned}
        if children <= owned:
            break
        owned |= children
    return {pid: records[pid][1] for pid in owned if pid in records}


def _signal(members: dict[int, str], sig: signal.Signals) -> None:
    for pid, started in members.items():
        current = _identity(pid)
        if current is not None and current[1] == started and current[2] not in {"Z", "X"}:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass


def _stop(process: subprocess.Popen[str], tree: bool, grace: float) -> tuple[str, str]:
    # Snapshot descendants before timeout escalation can orphan detached Chromium children.
    members = _descendants(process.pid) if tree else {}
    _signal(members, signal.SIGTERM)
    if process.poll() is None:
        process.terminate()
    try:
        output = process.communicate(timeout=grace)
    except subprocess.TimeoutExpired:
        _signal(members, signal.SIGKILL)
        if process.poll() is None:
            process.kill()
        output = process.communicate(timeout=3)
    # The leader may exit before a detached child; do not confuse that with full cleanup.
    _signal(members, signal.SIGKILL)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if all(
            (current := _identity(pid)) is None or current[1] != started or current[2] in {"Z", "X"}
            for pid, started in members.items()
        ):
            return output
        time.sleep(0.01)
    raise RuntimeError("Owned E2E descendants failed to stop")


def subreaper_state() -> int:
    value = ctypes.c_int()
    if ctypes.CDLL(None, use_errno=True).prctl(37, ctypes.byref(value), 0, 0, 0) != 0:
        raise RuntimeError("Cannot inspect test-process subreaper state")
    return value.value


def _set_subreaper(value: int) -> None:
    if ctypes.CDLL(None, use_errno=True).prctl(36, ctypes.c_ulong(value), 0, 0, 0) != 0:
        raise RuntimeError("Cannot set test-process subreaper state")


class OwnedChildren:
    def __init__(self, baseline: dict[int, str]) -> None:
        self.baseline = baseline

    def cleanup(self, grace: float = 0.2) -> None:
        started = time.monotonic()
        while time.monotonic() - started < grace + 3:
            members = {
                pid: stamp
                for pid, stamp in _descendants(os.getpid()).items()
                if pid != os.getpid() and self.baseline.get(pid) != stamp
            }
            if not members:
                return
            _signal(
                members, signal.SIGTERM if time.monotonic() - started < grace else signal.SIGKILL
            )
            for pid in members:
                current = _identity(pid)
                if current is not None and current[0] == os.getpid():
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            time.sleep(0.01)
        raise RuntimeError("Owned/adopted E2E children failed to stop and reap")


@contextmanager
def owned_children() -> Iterator[OwnedChildren]:
    """Adopt orphaned descendants of this test process, never a foreign process tree."""
    previous = subreaper_state()
    family = OwnedChildren(_descendants(os.getpid()))
    _set_subreaper(1)
    try:
        yield family
    finally:
        try:
            family.cleanup()
        finally:
            _set_subreaper(previous)


def cleanup_all(
    processes: list[tuple[subprocess.Popen[str], bool]],
    *,
    grace: float = 3,
    ownership: OwnedChildren | None = None,
) -> list[tuple[str, str]]:
    outputs = []
    failures = []
    for process, tree in processes:
        try:
            outputs.append(_stop(process, tree, grace))
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            failures.append(type(exc).__name__)
    if ownership is not None:
        try:
            ownership.cleanup()
        except (OSError, RuntimeError) as exc:
            failures.append(type(exc).__name__)
    if failures:
        raise RuntimeError(
            "E2E cleanup failed after attempting all resources: " + ", ".join(failures)
        )
    return outputs
