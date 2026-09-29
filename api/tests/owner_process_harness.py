"""Per-case Linux subreaper; only this process produces/adopts children.

Normal-path probe only: a supervisor crash before SPAWN is UNCERTAIN, not CLEAN.
"""

import ctypes
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


class EvidenceError(RuntimeError):
    """Missing, inconsistent or unreconciled control evidence."""


@dataclass
class Ref:
    pid: int
    start: int
    uid: int
    fd: int

    def token(self) -> list[int]:
        return [self.pid, self.start]


def _state(pid: int) -> tuple[int, int, int, int, int]:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    if len(fields) < 20:
        raise EvidenceError("truncated proc identity")
    uid = Path(f"/proc/{pid}").stat().st_uid
    return uid, int(fields[1]), int(fields[2]), int(fields[3]), int(fields[19])


def _pin(pid: int, parent: int, session: int | None) -> Ref:
    before = _state(pid)
    if (
        before[0] != os.getuid()
        or before[1] != parent
        or (session is not None and (before[2], before[3]) != (session, session))
    ):
        raise EvidenceError("child lineage or session mismatch")
    fd = os.pidfd_open(pid)
    try:
        if _state(pid) != before:
            raise EvidenceError("identity changed across pidfd acquisition")
        return Ref(pid, before[4], before[0], fd)
    except BaseException:
        os.close(fd)
        raise


def _exited(ref: Ref) -> bool:
    poll = select.poll()
    poll.register(ref.fd, select.POLLIN)
    return bool(poll.poll(0))


def _gone(ref: Ref) -> bool:
    if not _exited(ref):
        return False
    try:
        return _state(ref.pid)[4] != ref.start  # Numeric PID may have been reused.
    except FileNotFoundError:
        return True


def _path_absent(path: Path) -> bool:
    try:
        path.lstat()  # A dangling symlink is still a retained pathname.
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def _signal(ref: Ref, signum: int) -> bool:
    if _exited(ref):
        return False
    try:
        state = _state(ref.pid)
    except FileNotFoundError:
        return False
    if (state[0], state[4]) != (ref.uid, ref.start):
        raise EvidenceError("refusing signal to changed identity")
    signal.pidfd_send_signal(ref.fd, signum)
    return True


def _send(sock: socket.socket, data: dict[str, object]) -> None:
    raw = json.dumps(data, separators=(",", ":")).encode()
    if len(raw) > 4096 or sock.send(raw) != len(raw):
        raise EvidenceError("control packet not delivered")


def _recv(sock: socket.socket) -> dict[str, object]:
    raw = sock.recv(4097)
    if not raw or len(raw) > 4096:
        raise EvidenceError("missing or oversized control packet")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise EvidenceError("invalid control packet")
    return result


def _prctl(option: int, value: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(option, value, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl failed")


def _parent_guard(expected: int) -> None:
    _prctl(1, signal.SIGKILL)  # Owner dies if its dedicated supervisor dies.
    if os.getppid() != expected:
        os._exit(4)


def _children(pid: int) -> list[int]:
    return [int(value) for value in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]


def _cleanup(
    refs: dict[tuple[int, int], Ref], owner: Ref | None, directory: Path
) -> dict[str, object]:
    """Pin each newly adopted direct child; scan again after every reap."""
    uncertain = False
    forced_kill = False
    reaped: list[list[int]] = []
    reap_status: list[dict[str, object]] = []
    owner_exit: int | None = None
    if owner is not None:
        try:
            if not _signal(owner, signal.SIGTERM):
                uncertain = True  # A clean exit before STOP is not a stop proof.
        except (OSError, EvidenceError):
            uncertain = True
    grace = time.monotonic() + 12
    deadline = grace + 4
    empty = 0
    children: list[int] = [-1]
    while time.monotonic() < deadline:
        try:
            children = _children(os.getpid())
            for pid in children:
                key = pid, _state(pid)[4]
                if key not in refs:
                    refs[key] = _pin(pid, os.getpid(), None)
        except (OSError, ValueError, EvidenceError):
            uncertain = True
            children = [-1]  # Never infer zero children from a failed scan.
        for ref in list(refs.values()):
            try:
                result = os.waitid(os.P_PIDFD, ref.fd, os.WEXITED | os.WNOHANG)
            except ChildProcessError:
                continue  # Worker still belongs to owner, or already reaped by it.
            except OSError:
                uncertain = True
                continue
            if result is not None:
                token = ref.token()
                reaped.append(token)
                reap_status.append(
                    {"token": token, "code": result.si_code, "status": result.si_status}
                )
                if owner is not None and ref.pid == owner.pid:
                    owner_exit = (
                        result.si_status if result.si_code == os.CLD_EXITED else -result.si_status
                    )
        if time.monotonic() >= grace:
            for ref in refs.values():
                try:
                    if _signal(ref, signal.SIGKILL):
                        forced_kill = True
                except (OSError, EvidenceError):
                    uncertain = True
        gone = True
        for ref in refs.values():
            try:
                if not _gone(ref):
                    gone = False
            except (OSError, ValueError, EvidenceError):
                uncertain = True
                gone = False
        empty = empty + 1 if not children and gone else 0
        if empty >= 3:
            break
        time.sleep(0.05)
    gone_tokens: list[list[int]] = []
    for ref in refs.values():
        try:
            if _gone(ref):
                gone_tokens.append(ref.token())
            else:
                uncertain = True
        except (OSError, ValueError, EvidenceError):
            uncertain = True
    gone_tokens.sort()
    # The owner, not the supervisor's rescue, must reap its worker. An adopted
    # descendant means the 0 exit code did not establish shutdown ownership.
    descendant_reaped = any(owner is None or token != owner.token() for token in reaped)
    clean = not uncertain and not forced_kill and not descendant_reaped and empty >= 3
    clean = clean and owner_exit == 0
    clean = bool(
        clean and owner and owner.token() in reaped and _path_absent(directory / "api.sock")
    )
    verdict = "CLEAN" if clean else "UNCERTAIN"
    return dict(
        event=verdict,
        owner_exit=owner_exit,
        gone=gone_tokens,
        reaped=reaped,
        reap_status=reap_status,
        remaining=children,
        forced_kill=forced_kill,
        descendant_reaped=descendant_reaped,
    )


def _rescue_adopted(
    refs: dict[tuple[int, int], Ref],
    guard_fd: int,
    deadline: float,
    prior_reaped: list[list[int]],
) -> dict[str, object]:
    """Synthetic probe only: pidfd rescue, adoption/reap and bounded final readback.

    Do not use the possibly mutated _signal. Release the worker's guard before
    the deadline if pidfd rescue cannot finish; never infer absence from a
    failed /proc scan or discard a pinned identity on uncertainty.
    """
    uncertain = False
    confirmed: set[tuple[int, int]] = set()
    for token in prior_reaped:
        if len(token) == 2 and all(type(value) is int and value > 0 for value in token):
            confirmed.add((token[0], token[1]))
        else:
            uncertain = True
    # SIG_IGN auto-reaps descendants: disappearance alone cannot certify reap.
    # Restore waitability for rescue, but preserve the lost-evidence verdict.
    try:
        if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            uncertain = True
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    except (OSError, ValueError):
        uncertain = True
    released = False
    empty = 0
    reaped: list[list[int]] = []
    reap_status: list[dict[str, object]] = []
    remaining: list[int] = [-1]
    try:
        while time.monotonic() < deadline:
            try:
                remaining = _children(os.getpid())
                for pid in remaining:
                    key = pid, _state(pid)[4]
                    if key not in refs:
                        refs[key] = _pin(pid, os.getpid(), None)
            except (OSError, ValueError, EvidenceError):
                uncertain = True
                remaining = [-1]
            for ref in list(refs.values()):
                try:
                    result = os.waitid(os.P_PIDFD, ref.fd, os.WEXITED | os.WNOHANG)
                except ChildProcessError:
                    continue  # Already reaped, or not yet adopted from the owner.
                except OSError:
                    uncertain = True
                    continue
                if result is not None:
                    if result.si_pid != ref.pid:
                        uncertain = True
                    confirmed.add((ref.pid, ref.start))
                    reaped.append(ref.token())
                    reap_status.append(
                        {"token": ref.token(), "code": result.si_code, "status": result.si_status}
                    )
            for ref in list(refs.values()):
                try:
                    if _exited(ref):
                        continue
                    state = _state(ref.pid)
                    if (state[0], state[4]) != (ref.uid, ref.start):
                        raise EvidenceError("rescue identity changed")
                    signal.pidfd_send_signal(ref.fd, signal.SIGKILL)
                except ProcessLookupError:
                    if not _exited(ref):
                        uncertain = True
                except (OSError, ValueError, EvidenceError):
                    uncertain = True
            gone = True
            for ref in refs.values():
                try:
                    if not _gone(ref):
                        gone = False
                except (OSError, ValueError, EvidenceError):
                    uncertain = True
                    gone = False
            empty = empty + 1 if not remaining and gone else 0
            if empty >= 3:
                break
            if not released and time.monotonic() >= deadline - 2:
                try:
                    os.close(guard_fd)
                    released = True
                except OSError:
                    uncertain = True
            time.sleep(0.05)
    finally:
        if not released:
            try:
                os.close(guard_fd)
            except OSError:
                uncertain = True

    # Read again after releasing the guard, before reporting or closing pidfds.
    try:
        remaining = _children(os.getpid())
    except (OSError, ValueError):
        uncertain = True
        remaining = [-1]
    gone_tokens: list[list[int]] = []
    for ref in refs.values():
        try:
            if _gone(ref):
                gone_tokens.append(ref.token())
            else:
                uncertain = True
        except (OSError, ValueError, EvidenceError):
            uncertain = True
    tokens = sorted(ref.token() for ref in refs.values())
    gone_tokens.sort()
    certified = (
        not uncertain
        and empty >= 3
        and remaining == []
        and gone_tokens == tokens
        and confirmed == set(refs)
    )
    return dict(
        certified=certified,
        refs=tokens,
        gone=gone_tokens,
        remaining=remaining,
        reaped=reaped,
        reap_status=reap_status,
    )


def _supervise(fd: int, directory: Path, evidence: str) -> int:
    with socket.socket(fileno=fd) as control:
        refs: dict[tuple[int, int], Ref] = {}
        owner: Ref | None = None
        failed = False
        try:
            if len(os.listdir("/proc/self/task")) != 1:
                raise EvidenceError("supervisor is not single-threaded")
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)  # Keep direct children waitable.
            _prctl(36, 1)  # PR_SET_CHILD_SUBREAPER, only in this subprocess.
            expected = os.getpid()
            control.settimeout(12)
            _send(control, {"event": "SUPERVISOR", "pid": expected})
            if _recv(control) != {"event": "START"}:
                raise EvidenceError("unattested supervisor cannot launch owner")
            env = dict(PATH=os.environ.get("PATH", ""), OMNIS_HTTP_DIR=str(directory))
            env["OMNIS_HTTP_PORT"] = "8765"
            proc = subprocess.Popen(
                [sys.executable, "-I", "-m", "omnis.owner"],
                cwd=directory,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                preexec_fn=lambda: _parent_guard(expected),
            )
            owner = _pin(proc.pid, expected, proc.pid)
            refs[owner.pid, owner.start] = owner
            worker: Ref | None = None
            until = time.monotonic() + 10
            while time.monotonic() < until:
                children = _children(owner.pid)
                if len(children) == 1:
                    worker = _pin(children[0], owner.pid, owner.pid)
                    refs[worker.pid, worker.start] = worker
                    break
                if children or _exited(owner):
                    raise EvidenceError("owner did not retain one worker")
                time.sleep(0.05)
            if worker is None:
                raise EvidenceError("worker admission timed out")
            _send(control, {"event": "SPAWN", "owner": owner.token(), "worker": worker.token()})
            if evidence != "missing":
                token = owner.token()
                if evidence == "invalid":
                    # Live, foreign test-runner PID: READY must not authorize a signal.
                    token = [os.getppid(), _state(os.getppid())[4]]
                _send(control, {"event": "READY", "owner": token, "worker": worker.token()})
            control.settimeout(15)
            if _recv(control) != {"event": "STOP"}:
                raise EvidenceError("unexpected control command")
        except Exception:
            # No exception before teardown may turn an unobserved child into CLEAN.
            failed = True
        report = _cleanup(refs, owner, directory)
        if failed:
            report["event"] = "UNCERTAIN"
        try:
            _send(control, report)
        except OSError:
            pass
        for ref in refs.values():
            os.close(ref.fd)
        return 0 if report["event"] == "CLEAN" else 4


if __name__ == "__main__":
    raise SystemExit(_supervise(int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]))
