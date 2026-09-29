"""Isolated subreaper probe for the owner's signal-wait failure path.

The worker waits on a supervisor-only guard as well as a private admission gate.
If the supervisor dies, its guard writer closes and the worker exits on EOF;
pytest neither becomes a subreaper nor rescues descendants by numeric PID.
"""

import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path

import pytest

import owner_process_harness as h

# -I omits the script/cwd from sys.path; the only inserted path is this test directory.
_PROBE = (
    "import sys; "
    "sys.path.insert(0, sys.argv[1]); "
    "import test_owner_watch_fault as probe; "
    "raise SystemExit(probe._dispatch(sys.argv[2:]))"
)


def _worker(gate: int, guard: int) -> None:
    """Do no work before admission; exit promptly if the supervisor disappears."""
    try:
        ready, _, _ = select.select([gate, guard], [], [])
        if guard in ready or gate not in ready or os.read(gate, 1) != b"1":
            os._exit(0)
        # The supervisor releases the gate only after the owner exits, so a
        # broken _kill_owned cannot borrow the owner's natural-exit reap.
        select.select([guard], [], [], 0.5)
    finally:
        os._exit(0)


def _owner_shim(args: list[str]) -> int:
    supervisor, fd, gate, guard = map(int, args[:4])
    mode = args[4]
    h._parent_guard(supervisor)
    with socket.socket(fileno=fd) as control:
        child = os.fork()
        if child == 0:
            control.close()
            _worker(gate, guard)
        os.close(gate)
        os.close(guard)
        pidfd = os.pidfd_open(child)
        try:
            h._send(control, {"event": "CHILD", "pid": child})
            control.settimeout(10)
            if h._recv(control) != {"event": "GO"}:
                raise h.EvidenceError("owner was not admitted by its supervisor")
            import omnis.owner as owner

            actual_wait = signal.sigtimedwait
            calls = 0

            def fault_once(signals: Iterable[int], timeout: float) -> signal.struct_siginfo | None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    h._send(control, {"event": "FAULT", "count": calls})
                    raise OSError("injected signal-wait failure")
                return actual_wait(signals, timeout)

            signal.sigtimedwait = fault_once
            if mode in {"kill_noop", "kill_noop_delayed"}:

                def no_op_kill(pid: int, pidfd: int) -> None:
                    pass

                owner._kill_owned = no_op_kill
            if mode == "kill_noop_delayed":
                # An owner delayed after admission must not borrow the
                # worker's natural timeout as evidence of its own cleanup.
                time.sleep(5.2)
            return owner._watch(child, pidfd)
        finally:
            # No test-side rescue: only the real _watch or the subreaper may reap.
            os.close(pidfd)


def _supervise(args: list[str]) -> int:
    fd = int(args[0])
    mode = args[1]
    directory = Path(args[2])
    h._prctl(36, 1)  # PR_SET_CHILD_SUBREAPER in this subprocess, never pytest.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    refs: dict[tuple[int, int], h.Ref] = {}
    owner: h.Ref | None = None
    failed = True
    fault_fired = False
    gate_read = gate_write = guard_read = guard_write = -1
    with socket.socket(fileno=fd) as control:
        peer, shim = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            control.settimeout(12)
            h._send(control, {"event": "SUPERVISOR", "pid": os.getpid()})
            if h._recv(control) != {"event": "START"}:
                raise h.EvidenceError("supervisor did not receive START")
            gate_read, gate_write = os.pipe()
            guard_read, guard_write = os.pipe()
            with peer, shim:
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        _PROBE,
                        str(Path(__file__).parent),
                        "owner",
                        str(os.getpid()),
                        str(shim.fileno()),
                        str(gate_read),
                        str(guard_read),
                        mode,
                    ],
                    cwd=directory,
                    env={"PATH": os.environ.get("PATH", "")},
                    pass_fds=(shim.fileno(), gate_read, guard_read),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                shim.close()
                os.close(gate_read)
                gate_read = -1
                os.close(guard_read)
                guard_read = -1
                owner = h._pin(proc.pid, os.getpid(), proc.pid)
                refs[owner.pid, owner.start] = owner
                peer.settimeout(10)
                spawned = h._recv(peer)
                child_pid = spawned.get("pid")
                if spawned.get("event") != "CHILD" or type(child_pid) is not int or child_pid < 1:
                    raise h.EvidenceError("missing direct-child attestation")
                if h._children(owner.pid) != [child_pid]:
                    raise h.EvidenceError("unexpected owner child set")
                worker = h._pin(child_pid, owner.pid, owner.pid)
                refs[worker.pid, worker.start] = worker
                if h._exited(worker):
                    raise h.EvidenceError("worker exited before admission")
                h._send(
                    control, {"event": "PINNED", "owner": owner.token(), "worker": worker.token()}
                )
                if h._recv(control) != {"event": "GO"}:
                    raise h.EvidenceError("parent did not admit pinned pair")
                if h._exited(worker):
                    raise h.EvidenceError("worker exited before fault")
                h._send(peer, {"event": "GO"})
                if h._recv(peer) != {"event": "FAULT", "count": 1}:
                    raise h.EvidenceError("missing single fault-fired marker")
                fault_fired = True
                h._send(control, {"event": "FAULT", "count": 1})
                deadline = time.monotonic() + 5
                while not h._exited(owner) and time.monotonic() < deadline:
                    time.sleep(0.025)
                if not h._exited(owner):
                    raise h.EvidenceError("owner did not finish bounded fault handling")
                try:
                    os.write(gate_write, b"1")
                except BrokenPipeError:
                    pass  # Real owner already killed and reaped its gated worker.
            failed = False
        except (OSError, ValueError, h.EvidenceError, subprocess.SubprocessError):
            # The supervisor still scans and reaps after an early owner exit.
            pass
        finally:
            peer.close()
            shim.close()
            if failed:
                # EOF lets even a not-yet-admitted worker leave without rescue.
                if guard_write >= 0:
                    os.close(guard_write)
                    guard_write = -1
            for descriptor in (gate_read, gate_write, guard_read):
                if descriptor >= 0:
                    os.close(descriptor)
            report = h._cleanup(refs, owner, directory)
            report["probe_error"] = failed
            report["fault_fired"] = fault_fired
            try:
                h._send(control, report)
            except OSError:
                pass
            for ref in refs.values():
                os.close(ref.fd)
            if guard_write >= 0:
                os.close(guard_write)
    return 4 if failed else 0


def _dispatch(args: list[str]) -> int:
    if args[0] == "owner":
        return _owner_shim(args[1:])
    if args[0] == "supervisor":
        return _supervise(args[1:])
    raise h.EvidenceError("unknown isolated probe role")


def _probe(directory: Path, mode: str) -> tuple[dict[str, object], list[int], list[int]]:
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    supervisor: h.Ref | None = None
    refs: list[h.Ref] = []
    proc: subprocess.Popen[bytes] | None = None
    completed = False
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                _PROBE,
                str(Path(__file__).parent.resolve()),
                "supervisor",
                str(child.fileno()),
                mode,
                str(directory),
            ],
            cwd=directory,
            env={"PATH": os.environ.get("PATH", "")},
            pass_fds=(child.fileno(),),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        child.close()
        supervisor = h._pin(proc.pid, os.getpid(), None)
        parent.settimeout(12)
        assert h._recv(parent) == {"event": "SUPERVISOR", "pid": supervisor.pid}
        h._send(parent, {"event": "START"})
        spawned = h._recv(parent)
        owner_token, worker_token = spawned.get("owner"), spawned.get("worker")
        assert spawned.get("event") == "PINNED"
        assert isinstance(owner_token, list) and isinstance(worker_token, list)
        assert all(type(x) is int and x > 0 for x in owner_token + worker_token)
        assert len(owner_token) == len(worker_token) == 2
        owner = h._pin(owner_token[0], supervisor.pid, owner_token[0])
        refs.append(owner)
        worker = h._pin(worker_token[0], owner.pid, owner.pid)
        refs.append(worker)
        assert owner.token() == owner_token and worker.token() == worker_token
        assert not h._exited(worker)
        h._send(parent, {"event": "GO"})
        assert h._recv(parent) == {"event": "FAULT", "count": 1}
        parent.settimeout(22)  # Existing _cleanup: 12 s grace + 4 s bound.
        report = h._recv(parent)
        assert proc.wait(timeout=2) == 0
        assert report.get("probe_error") is False and report.get("fault_fired") is True
        assert report.get("gone") == sorted([owner.token(), worker.token()])
        assert report.get("remaining") == []
        assert h._gone(owner) and h._gone(worker)
        completed = True
        return report, owner.token(), worker.token()
    finally:
        child.close()
        parent.close()  # EOF prompts supervisor cleanup even before STOP/admission.
        issues: list[str] = []
        try:
            if proc is not None and not completed:
                try:
                    proc.wait(timeout=22)
                except subprocess.TimeoutExpired:
                    if supervisor is not None:
                        try:
                            h._signal(supervisor, signal.SIGKILL)  # Pinned pidfd only.
                        except (OSError, h.EvidenceError):
                            issues.append("supervisor pidfd signal unavailable")
                    try:
                        proc.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        issues.append("supervisor not reaped")
                except OSError:
                    issues.append("supervisor wait unavailable")
                # Even if supervisor rescue fails, attempt every pinned readback.
                for ref in refs:
                    deadline = time.monotonic() + 2
                    try:
                        while not h._exited(ref) and time.monotonic() < deadline:
                            time.sleep(0.025)
                        if not h._exited(ref):
                            issues.append("guarded child remained live after supervisor failure")
                    except OSError:
                        issues.append("guarded child readback unavailable")
        finally:
            for ref in refs:
                os.close(ref.fd)
            if supervisor is not None:
                os.close(supervisor.fd)
        if issues:
            raise h.EvidenceError("probe teardown UNCERTAIN: " + ", ".join(issues))


def _assert_owner_reaped_worker(report: dict[str, object], owner: list[int]) -> None:
    assert report.get("owner_exit") == 4
    assert report.get("reaped") == [owner], (
        "owner-owned worker reap required (no supervisor rescue)"
    )
    assert report.get("descendant_reaped") is False
    assert report.get("forced_kill") is False
    assert report.get("event") == "UNCERTAIN"  # Early exit is not a clean STOP proof.


def test_signal_wait_fault_is_reconciled_by_owner_not_supervisor() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        # Explicit RED switch mutates only the *positive* case's real owner shim.
        mode = "kill_noop" if os.environ.get("OMNIS_TEST_WATCH_KILL_NOOP") == "1" else "normal"
        positive, owner, _worker_token = _probe(directory, mode)
        _assert_owner_reaped_worker(positive, owner)
        negative, owner, _worker_token = _probe(directory, "kill_noop")
        assert negative.get("owner_exit") == 4
        assert negative.get("descendant_reaped") is True
        assert negative.get("forced_kill") is False
        with pytest.raises(AssertionError, match="owner-owned worker reap required"):
            _assert_owner_reaped_worker(negative, owner)
        delayed, owner, _worker_token = _probe(directory, "kill_noop_delayed")
        assert delayed.get("fault_fired") is True and delayed.get("owner_exit") == 4
        with pytest.raises(AssertionError, match="owner-owned worker reap required"):
            _assert_owner_reaped_worker(delayed, owner)
