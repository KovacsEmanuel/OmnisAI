"""Minimal API process owner: no application imports or event loop in PID1."""

import fcntl
import os
import signal
import sys
import time

_STOP_SIGNALS = {signal.SIGTERM, signal.SIGINT}
_WORKER_MODULE = "omnis.worker"


def _sole_thread() -> bool:
    """Refuse wrappers that break blocked-signal and FD-snapshot ownership."""
    try:
        tids = os.listdir("/proc/self/task")
    except OSError:
        return False
    return tids == [str(os.getpid())]


def _exit_code(status: int, *, stopping: bool) -> int:
    code = os.waitstatus_to_exitcode(status)
    if stopping:
        return 0 if code == 0 else 4
    return code if code in {0, 2, 3, 4} else 3


def _reap_after_kill(pid: int) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            reaped, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        if reaped == pid:
            return
        time.sleep(0.05)


def _kill_owned(pid: int, pidfd: int) -> None:
    try:
        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        # Only the sole, still-unreaped direct child can be signaled numerically.
        try:
            reaped, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        if reaped == 0:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass  # Exit 4 reports that termination could not be reconciled.


def _worker_file_actions(gate_read: int) -> list[tuple[int, int]]:
    """Do not export ambient inherited FDs to the exec'd worker."""
    actions: list[tuple[int, int]] = []
    for raw in os.listdir("/proc/self/fd"):
        if not raw.isdecimal():
            continue
        fd = int(raw)
        if fd < 3 or fd == gate_read:
            continue
        try:
            os.fstat(fd)
        except OSError:
            continue  # /proc's own enumeration FD was already closed.
        actions.append((os.POSIX_SPAWN_CLOSE, fd))
    return actions


def _watch(pid: int, pidfd: int) -> int:
    stop_at: float | None = None
    while True:
        try:
            reaped, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return 4 if stop_at is not None else 3
        if reaped == pid:
            return _exit_code(status, stopping=stop_at is not None)
        try:
            requested = signal.sigtimedwait(_STOP_SIGNALS, 0.05)
        except InterruptedError:
            continue
        except OSError:
            _kill_owned(pid, pidfd)
            _reap_after_kill(pid)
            return 4
        if requested is not None:
            # An already-waitable child wins over a concurrently pending stop.
            reaped, status = os.waitpid(pid, os.WNOHANG)
            if reaped == pid:
                return _exit_code(status, stopping=stop_at is not None)
            if stop_at is None:
                stop_at = time.monotonic()
                try:
                    signal.pidfd_send_signal(pidfd, requested.si_signo)
                except ProcessLookupError:
                    pass
                except OSError:
                    _kill_owned(pid, pidfd)
                    _reap_after_kill(pid)
                    return 4
        if stop_at is not None and time.monotonic() - stop_at >= 10:
            _kill_owned(pid, pidfd)
            _reap_after_kill(pid)
            return 4


def main() -> int:
    """Spawn only one gated worker and preserve its exact exit/stop outcome."""
    # The supported direct `python -I -m omnis.owner` exec starts one thread;
    # a wrapper with native threads cannot safely own signals or spawn FDs.
    if not _sole_thread():
        return 4
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_BLOCK, _STOP_SIGNALS)
    for signum in _STOP_SIGNALS:
        signal.signal(signum, lambda _signum, _frame: None)

    gate_read, gate_write = os.pipe()
    if gate_read < 3:
        private_read = fcntl.fcntl(gate_read, fcntl.F_DUPFD_CLOEXEC, 3)
        os.close(gate_read)
        gate_read = private_read
    os.set_inheritable(gate_read, True)
    child_pid: int | None = None
    child_pidfd: int | None = None
    try:
        argv = [
            sys.executable,
            "-I",
            "-m",
            _WORKER_MODULE,
            "--gate-fd",
            str(gate_read),
            "--owner-pid",
            str(os.getpid()),
        ]
        try:
            file_actions = _worker_file_actions(gate_read)
            child_pid = os.posix_spawn(
                sys.executable,
                argv,
                dict(os.environ),
                file_actions=file_actions,
                setsigmask=(),
                setsigdef=tuple(_STOP_SIGNALS | {signal.SIGCHLD}),
            )
        except OSError:
            return 3
        os.close(gate_read)
        gate_read = -1
        try:
            child_pidfd = os.pidfd_open(child_pid)
        except OSError:
            os.close(gate_write)  # Never release an unpinned worker.
            gate_write = -1
            reaped, status = os.waitpid(child_pid, os.WNOHANG)
            if reaped == child_pid:
                return _exit_code(status, stopping=False)
            try:
                os.kill(child_pid, signal.SIGKILL)  # Direct, still-unreaped child only.
            except OSError:
                pass  # The unreconciled worker still has its private gate closed.
            _reap_after_kill(child_pid)
            return 4
        try:
            stop_before_release = signal.sigtimedwait(_STOP_SIGNALS, 0) is not None
        except OSError:
            stop_before_release = True  # Cannot safely admit work without observing stops.
        if stop_before_release:
            os.close(gate_write)
            gate_write = -1
            _kill_owned(child_pid, child_pidfd)
            _reap_after_kill(child_pid)
            return 4
        try:
            os.write(gate_write, b"1")
        except BrokenPipeError:
            pass  # The worker rejected its gate before application import.
        os.close(gate_write)
        gate_write = -1
        return _watch(child_pid, child_pidfd)
    finally:
        if gate_read >= 0:
            os.close(gate_read)
        if gate_write >= 0:
            os.close(gate_write)
        if child_pidfd is not None:
            os.close(child_pidfd)


if __name__ == "__main__":
    raise SystemExit(main())
