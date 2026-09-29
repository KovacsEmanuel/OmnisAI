"""Real owner lifecycle through an isolated, per-case child subreaper."""

import errno
import http.client
import json
import os
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Buffer
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest

from owner_process_harness import (
    EvidenceError,
    Ref,
    _exited,
    _gone,
    _path_absent,
    _pin,
    _recv,
    _send,
    _signal,
)


class _DeadlineSocket(socket.socket):
    """One monotonic UDS budget even through HTTPResponse.makefile/recv_into."""

    def __init__(self, deadline: float) -> None:
        super().__init__(socket.AF_UNIX, socket.SOCK_STREAM)
        self._deadline = deadline

    def _budget(self) -> None:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Private liveness response exceeded total deadline")
        self.settimeout(min(1, remaining))

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        self._budget()
        return super().recv(bufsize, flags)

    def recv_into(self, buffer: Buffer, nbytes: int = 0, flags: int = 0) -> int:
        self._budget()
        return super().recv_into(memoryview(buffer), nbytes, flags)


def _uds_liveness(path: Path, *, pid: int, uid: int, deadline: float) -> tuple[int, bytes]:
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid:
        raise EvidenceError("untrusted private API socket")
    if stat.S_IMODE(info.st_mode) != 0o600:
        # The real listener binds, chmods, then listens. Refuse the socket
        # until chmod has completed; retry only within the total deadline.
        raise BlockingIOError(errno.EAGAIN, "private API socket permissions pending")
    with _DeadlineSocket(deadline) as peer:
        peer._budget()
        peer.connect(str(path))
        actual_pid, actual_uid, _gid = struct.unpack(
            "3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        )
        if (actual_pid, actual_uid) != (pid, uid):
            raise EvidenceError("private API peer differs from pinned worker")
        peer._budget()
        peer.sendall(
            b"GET /health/live HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n\r\n"
        )
        response = http.client.HTTPResponse(peer)
        response.begin()
        result = response.status, response.read(4097)
        response.close()
    if len(result[1]) > 4096:
        raise EvidenceError("private liveness response exceeds limit")
    return result


class OwnerProcessCase:
    """Parent-facing attested control, with teardown even when READY fails."""

    def __init__(self, directory: Path, evidence: str = "normal") -> None:
        if evidence not in {"normal", "missing", "invalid"}:
            raise ValueError("unknown evidence fault")
        self.directory, self.evidence = directory, evidence
        self.spawn_attested = self.clean = self.cleanup_gone = False
        self.owner_exit: int | None = None
        self.supervisor_exit: int | None = None
        self.refs: list[Ref] = []
        self.ready_seen: dict[str, object] | None = None
        self.control: socket.socket | None = None
        self.proc: subprocess.Popen[bytes] | None = None
        self.supervisor: Ref | None = None

    def __enter__(self) -> Self:
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.control = parent
        try:
            script = Path(__file__).with_name("owner_process_harness.py").resolve()
            cmd = [sys.executable, "-I", str(script), str(child.fileno())]
            cmd.extend((str(self.directory), self.evidence))
            self.proc = subprocess.Popen(
                cmd,
                pass_fds=(child.fileno(),),
                cwd=self.directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            child.close()
            self.supervisor = _pin(self.proc.pid, os.getpid(), None)
            parent.settimeout(12)
            if _recv(parent) != {"event": "SUPERVISOR", "pid": self.supervisor.pid}:
                raise EvidenceError("supervisor identity not attested")
            _send(parent, {"event": "START"})
            spawned = _recv(parent)
            if spawned.get("event") != "SPAWN":
                raise EvidenceError("missing SPAWN evidence")
            o, w = spawned.get("owner"), spawned.get("worker")
            if (
                not isinstance(o, list)
                or not isinstance(w, list)
                or len(o) != 2
                or len(w) != 2
                or any(type(n) is not int or n < 1 for n in o + w)
            ):
                raise EvidenceError("invalid SPAWN identities")
            owner = _pin(o[0], self.proc.pid, o[0])
            self.refs.append(owner)
            worker = _pin(w[0], owner.pid, owner.pid)
            self.refs.append(worker)
            if o != owner.token() or w != worker.token():
                raise EvidenceError("SPAWN identity readback mismatch")
            self.spawn_attested = True
            if self.live() != (200, b'{"status":"live"}'):
                raise EvidenceError("real UDS liveness mismatch")
            parent.settimeout(1 if self.evidence == "missing" else 12)
            try:
                ready = _recv(parent)
            except socket.timeout as exc:
                raise EvidenceError("missing READY evidence") from exc
            self.ready_seen = ready
            if ready != {"event": "READY", "owner": o, "worker": w}:
                raise EvidenceError("invalid READY evidence")
            self.clean = True  # Provisional; __exit__ requires final cleanup readback.
            return self
        except BaseException as exc:
            child.close()
            try:
                self.close()
            except Exception as cleanup_exc:
                raise EvidenceError(f"{exc}; cleanup UNCERTAIN: {cleanup_exc}") from exc
            raise

    def live(self) -> tuple[int, bytes]:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if any(_exited(ref) for ref in self.refs):
                raise EvidenceError("owner/worker exited before liveness")
            try:
                result = _uds_liveness(
                    self.directory / "api.sock",
                    pid=self.refs[1].pid,
                    uid=self.refs[1].uid,
                    deadline=deadline,
                )
                if any(_exited(ref) for ref in self.refs):
                    raise EvidenceError("owner/worker exited during liveness")
                return result
            except (OSError, http.client.HTTPException):
                time.sleep(0.05)
        raise EvidenceError("real UDS liveness timed out")

    def close(self) -> None:
        if self.control is None:
            return
        control, self.control = self.control, None
        try:
            control.settimeout(23)
            _send(control, {"event": "STOP"})
            report = _recv(control)
            assert self.proc is not None
            self.supervisor_exit = self.proc.wait(timeout=2)
            exit_code = report.get("owner_exit")
            if isinstance(exit_code, int) and not isinstance(exit_code, bool):
                self.owner_exit = exit_code
            reaped = report.get("reaped")
            self.cleanup_gone = bool(
                report.get("event") == "CLEAN"
                and self.supervisor_exit == 0
                and len(self.refs) == 2
                and sorted(ref.token() for ref in self.refs) == report.get("gone")
                and isinstance(reaped, list)
                and self.refs[0].token() in reaped
                and reaped == [self.refs[0].token()]
                and report.get("forced_kill") is False
                and report.get("descendant_reaped") is False
                and report.get("remaining") == []
                and all(_gone(ref) for ref in self.refs)
                and _path_absent(self.directory / "api.sock")
            )
            self.clean = bool(self.clean and self.cleanup_gone and self.owner_exit == 0)
            if not self.cleanup_gone:
                raise EvidenceError(f"cleanup UNCERTAIN: {report}")
        except BaseException as original:
            self.clean = False
            issues: list[str] = []
            # Rescue uses only previously pinned, revalidated handles; never marker PIDs.
            for ref in reversed(self.refs):
                try:
                    _signal(ref, signal.SIGKILL)
                except (OSError, EvidenceError):
                    issues.append("pinned process signal unavailable")
            try:
                control.close()  # EOF lets the supervisor clean rather than wait for STOP.
            except OSError:
                issues.append("control close unavailable")
            if self.proc is not None:
                try:
                    self.supervisor_exit = self.proc.wait(timeout=18)
                except subprocess.TimeoutExpired:
                    if self.supervisor is not None:
                        try:
                            _signal(self.supervisor, signal.SIGKILL)
                        except (OSError, EvidenceError):
                            issues.append("supervisor signal unavailable")
                    try:
                        self.supervisor_exit = self.proc.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        issues.append("supervisor reap unavailable")
                except OSError:
                    issues.append("supervisor wait unavailable")
            for ref in self.refs:
                try:
                    if not _gone(ref):
                        issues.append("owned process survived rescue")
                except (OSError, ValueError, EvidenceError):
                    issues.append("owned process readback unavailable")
            if self.supervisor is not None:
                try:
                    if not _gone(self.supervisor):
                        issues.append("supervisor survived rescue")
                except (OSError, ValueError, EvidenceError):
                    issues.append("supervisor readback unavailable")
            if not _path_absent(self.directory / "api.sock"):
                issues.append("private socket survived rescue")
            reason = ", ".join(issues) if issues else "initial verification failed"
            raise EvidenceError("cleanup UNCERTAIN: " + reason) from original
        finally:
            control.close()
            for ref in self.refs:
                os.close(ref.fd)
            if self.supervisor is not None:
                os.close(self.supervisor.fd)

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


def test_real_owner_liveness_and_graceful_stop_have_attested_cleanup() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        case = OwnerProcessCase(Path(name))
        with case:
            assert case.spawn_attested
            assert case.live() == (200, b'{"status":"live"}')
        assert case.clean
        assert case.owner_exit == 0
        assert not (Path(name) / "api.sock").exists()


def test_liveness_waits_for_socket_chmod_before_accepting_real_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        case = OwnerProcessCase(Path(name))
        with case:
            socket_path = case.directory / "api.sock"
            original_lstat = Path.lstat
            pending = [True]

            def before_chmod(path: Path) -> os.stat_result:
                info = original_lstat(path)
                if path == socket_path and pending[0]:
                    pending[0] = False
                    fields = list(info)
                    fields[0] = stat.S_IFSOCK | 0o755
                    return os.stat_result(fields)
                return info

            with monkeypatch.context() as scoped:
                scoped.setattr(Path, "lstat", before_chmod)
                assert case.live() == (200, b'{"status":"live"}')
            assert not pending[0]
        assert case.clean


def test_parent_readback_uses_pinned_identity_when_numeric_pid_is_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        case = OwnerProcessCase(Path(name))
        with monkeypatch.context() as scoped:
            with case:
                assert case.live() == (200, b'{"status":"live"}')
                original_exists = Path.exists
                owned = {f"/proc/{ref.pid}" for ref in case.refs}

                def reused_path(path: Path, *, follow_symlinks: bool = True) -> bool:
                    if str(path) in owned and all(_exited(ref) for ref in case.refs):
                        return True  # A new process now occupies an old numeric PID.
                    return original_exists(path, follow_symlinks=follow_symlinks)

                scoped.setattr(Path, "exists", reused_path)
        assert case.clean and case.cleanup_gone


def test_private_liveness_trickle_obeys_one_total_deadline() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        path = Path(name) / "api.sock"
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(path))
        path.chmod(0o600)
        listener.listen(1)
        listener.settimeout(2)
        finished = threading.Event()

        def slow_reply() -> None:
            try:
                peer, _address = listener.accept()
                with peer:
                    peer.settimeout(2)
                    peer.recv(4096)
                    body = b'{"status":"live"}'
                    peer.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: "
                        + str(len(body)).encode()
                        + b"\r\nConnection: close\r\n\r\n"
                    )
                    for byte in body:
                        try:
                            peer.sendall(bytes((byte,)))
                        except OSError:
                            break
                        time.sleep(0.06)
            except OSError:
                pass
            finally:
                finished.set()

        server = threading.Thread(target=slow_reply, daemon=True)
        server.start()
        started = time.monotonic()
        try:
            with pytest.raises(TimeoutError):
                _uds_liveness(path, pid=os.getpid(), uid=os.getuid(), deadline=started + 0.3)
            assert time.monotonic() - started < 0.8
        finally:
            listener.close()
            assert finished.wait(timeout=2)
            server.join(timeout=2)
            assert not server.is_alive()


def test_private_liveness_refuses_a_different_peer_pid() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        path = Path(name) / "api.sock"
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(path))
        path.chmod(0o600)
        listener.listen(1)
        listener.settimeout(2)
        finished = threading.Event()

        def foreign_peer() -> None:
            try:
                peer, _address = listener.accept()
                with peer:
                    peer.settimeout(1)
                    try:
                        peer.recv(4096)
                    except OSError:
                        pass
            except OSError:
                pass
            finally:
                finished.set()

        server = threading.Thread(target=foreign_peer, daemon=True)
        server.start()
        try:
            with pytest.raises(EvidenceError, match="differs from pinned worker"):
                _uds_liveness(
                    path,
                    pid=os.getpid() + 1,
                    uid=os.getuid(),
                    deadline=time.monotonic() + 1,
                )
        finally:
            listener.close()
            assert finished.wait(timeout=2)
            server.join(timeout=2)
            assert not server.is_alive()


def test_private_liveness_refuses_worker_exit_during_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = OwnerProcessCase(Path(os.environ["TMPDIR"]))
    case.refs = [Ref(1, 1, os.getuid(), -1), Ref(2, 2, os.getuid(), -1)]
    worker_checks = [0]
    requests = [0]

    def exit_after_reply(ref: Ref) -> bool:
        if ref.pid == 2:
            worker_checks[0] += 1
            return worker_checks[0] > 1
        return False

    def reply(*_args: object, **_kwargs: object) -> tuple[int, bytes]:
        requests[0] += 1
        return 200, b'{"status":"live"}'

    with monkeypatch.context() as scoped:
        scoped.setattr(sys.modules[__name__], "_exited", exit_after_reply)
        scoped.setattr(sys.modules[__name__], "_uds_liveness", reply)
        with pytest.raises(EvidenceError, match="exited during liveness"):
            case.live()
    assert requests == [1] and worker_checks[0] >= 2


def test_clean_report_cannot_hide_a_dangling_uds_name(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        directory = Path(name)
        actual_recv = _recv

        def inject_dangling_name(control: socket.socket) -> dict[str, object]:
            packet = actual_recv(control)
            if packet.get("event") == "CLEAN":
                (directory / "api.sock").symlink_to(directory / "missing")
            return packet

        monkeypatch.setattr(sys.modules[__name__], "_recv", inject_dangling_name)
        case = OwnerProcessCase(directory)
        with pytest.raises(EvidenceError, match="cleanup UNCERTAIN"):
            with case:
                assert case.live() == (200, b'{"status":"live"}')
        assert (directory / "api.sock").is_symlink()


def test_owner_exit_before_stop_cannot_be_reported_clean() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        case = OwnerProcessCase(Path(name))
        with pytest.raises(EvidenceError, match="cleanup UNCERTAIN"):
            with case:
                assert case.live() == (200, b'{"status":"live"}')
                owner = case.refs[0]
                _signal(owner, signal.SIGTERM)
                deadline = time.monotonic() + 5
                while not _exited(owner) and time.monotonic() < deadline:
                    time.sleep(0.05)
                assert _exited(owner), "Owner did not exit before STOP"
        assert not case.clean
        assert case.supervisor_exit == 4
        assert not (Path(name) / "api.sock").exists()


_ORPHAN_OWNER_PROBE = """\
import json, os, select, signal, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import owner_process_harness as h
h._prctl(36, 1)
signal.signal(signal.SIGCHLD, signal.SIG_DFL)
supervisor = os.getpid()
read_fd, write_fd = os.pipe()
guard_read, guard_write = os.pipe()
refs = {}
report = {"event": "UNCERTAIN"}
try:
    owner_pid = os.fork()
    if owner_pid == 0:
        actual_owner = os.getpid()
        os.close(read_fd)
        os.close(guard_write)
        h._prctl(1, signal.SIGKILL)
        if os.getppid() != supervisor: os._exit(4)
        worker_pid = os.fork()
        if worker_pid == 0:
            os.close(write_fd)
            if os.getppid() != actual_owner: os._exit(4)
            ready, _, _ = select.select([guard_read], [], [], float(sys.argv[2]))
            if ready and os.read(guard_read, 1): os._exit(5)
            os._exit(0)
        os.close(guard_read)
        signal.signal(signal.SIGTERM, lambda *_args: os._exit(0))
        os.write(write_fd, str(worker_pid).encode())
        os.close(write_fd)
        time.sleep(90)
        os._exit(3)
    os.close(write_fd)
    os.close(guard_read)
    if not select.select([read_fd], [], [], 2)[0]:
        raise h.EvidenceError("worker identity publication timed out")
    worker_pid = int(os.read(read_fd, 64))
    os.close(read_fd)
    owner = h._pin(owner_pid, supervisor, None)
    refs[owner.pid, owner.start] = owner
    worker = h._pin(worker_pid, owner_pid, None)
    refs[worker.pid, worker.start] = worker
    if h._exited(worker): raise h.EvidenceError("worker exited before STOP")
    if sys.argv[4] in ("no-op-kill", "deny-rescue", "ignored-chld"):
        real_signal = h._signal
        def no_op_kill(ref, signum):
            if signum == signal.SIGKILL: return True
            return real_signal(ref, signum)
        h._signal = no_op_kill
    report = h._cleanup(refs, owner, Path(sys.argv[3]))
    report.update(owner=owner.token(), worker=worker.token())
    if sys.argv[4] == "deny-rescue":
        real_pidfd_signal = signal.pidfd_send_signal
        def deny_pidfd_signal(fd, signum):
            if signum == signal.SIGKILL: raise PermissionError("rescue signal denied")
            return real_pidfd_signal(fd, signum)
        signal.pidfd_send_signal = deny_pidfd_signal
    if sys.argv[4] == "ignored-chld":
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
except Exception as exc:
    report = {"event": "UNCERTAIN", "error": type(exc).__name__}
finally:
    prior_reaped = report.get("reaped")
    if not isinstance(prior_reaped, list): prior_reaped = []
    rescue = h._rescue_adopted(refs, guard_write, time.monotonic() + 5, prior_reaped)
    report["rescue"] = rescue
    if not rescue["certified"]: report["event"] = "UNCERTAIN"
    print(json.dumps(report), flush=True)
    for ref in refs.values(): os.close(ref.fd)
sys.exit(0 if rescue["certified"] and "owner_exit" in report else 4)
"""


def _run_orphan_probe(directory: Path, delay: str, mode: str) -> tuple[int, dict[str, object]]:
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _ORPHAN_OWNER_PROBE,
            str(Path(__file__).parent.resolve()),
            delay,
            str(directory),
            mode,
        ],
        cwd=directory,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=28,
        check=False,
    )
    result = json.loads(process.stdout)
    if not isinstance(result, dict):
        raise EvidenceError("orphan probe returned non-object evidence")
    return process.returncode, result


def _orphan_owner_report(
    directory: Path, delay: str, *, no_op_kill: bool = False
) -> dict[str, object]:
    code, result = _run_orphan_probe(directory, delay, "no-op-kill" if no_op_kill else "normal")
    if code != 0:
        raise EvidenceError(f"orphan probe UNCERTAIN (exit={code}): {result!r}")
    rescue = result.get("rescue")
    if not isinstance(rescue, dict) or rescue.get("certified") is not True:
        raise EvidenceError(f"orphan rescue UNCERTAIN: {result!r}")
    assert result.get("owner_exit") == 0
    return result


def test_owner_exit_zero_without_reaping_worker_is_not_clean() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        report = _orphan_owner_report(Path(name), "0.3")
        assert report.get("event") == "UNCERTAIN"
        reaped = report.get("reaped")
        assert isinstance(reaped, list) and len(reaped) == 2
        assert report.get("descendant_reaped") is True
        assert report.get("forced_kill") is False


def _assert_forced_cleanup(report: dict[str, object]) -> None:
    assert report.get("event") == "UNCERTAIN"
    assert report.get("owner_exit") == 0
    owner, worker = report.get("owner"), report.get("worker")
    assert isinstance(owner, list) and isinstance(worker, list)
    assert report.get("forced_kill") is True
    assert report.get("reap_status") == [
        {"token": owner, "code": os.CLD_EXITED, "status": 0},
        {"token": worker, "code": os.CLD_KILLED, "status": signal.SIGKILL},
    ], "the worker must be waitid-confirmed killed by SIGKILL, not exit voluntarily"
    assert report.get("reaped") == [owner, worker]
    assert report.get("descendant_reaped") is True
    assert report.get("gone") == sorted([owner, worker])
    assert report.get("remaining") == []
    rescue = report.get("rescue")
    assert isinstance(rescue, dict) and rescue.get("certified") is True
    assert rescue.get("refs") == rescue.get("gone") == sorted([owner, worker])
    assert rescue.get("remaining") == []


def test_owner_exit_zero_needing_supervisor_kill_is_not_clean() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        report = _orphan_owner_report(Path(name), "60")
        _assert_forced_cleanup(report)


def test_no_op_kill_cannot_pass_the_same_forced_cleanup_assertion() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        report = _orphan_owner_report(Path(name), "60", no_op_kill=True)
        owner, worker = report["owner"], report["worker"]
        assert isinstance(owner, list) and isinstance(worker, list)
        assert report["forced_kill"] is True  # The mutant lies about sending SIGKILL.
        assert report["reap_status"] == [{"token": owner, "code": os.CLD_EXITED, "status": 0}]
        assert report["gone"] == [owner]
        assert report["remaining"] == [worker[0]]
        rescue = report["rescue"]
        assert isinstance(rescue, dict) and rescue["certified"] is True
        assert rescue["reap_status"] == [
            {"token": worker, "code": os.CLD_KILLED, "status": signal.SIGKILL}
        ]
        assert rescue["refs"] == rescue["gone"] == sorted([owner, worker])
        assert rescue["remaining"] == []
        with pytest.raises(AssertionError, match="worker must be waitid-confirmed killed"):
            _assert_forced_cleanup(report)


def test_failed_rescue_releases_guard_but_keeps_pinned_uncertain_evidence() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        code, report = _run_orphan_probe(Path(name), "60", "deny-rescue")
        assert code == 4 and report["event"] == "UNCERTAIN"
        owner, worker = report["owner"], report["worker"]
        assert isinstance(owner, list) and isinstance(worker, list)
        rescue = report["rescue"]
        assert isinstance(rescue, dict) and rescue["certified"] is False
        # The SIGKILL denial did not turn the worker into a falsely killed child:
        # closing the guard instead gave it a bounded voluntary exit and a reap.
        assert rescue["reap_status"] == [{"token": worker, "code": os.CLD_EXITED, "status": 0}]
        assert rescue["refs"] == rescue["gone"] == sorted([owner, worker])
        assert rescue["remaining"] == []


def test_rescue_cannot_certify_auto_reaped_child_without_waitid() -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        code, report = _run_orphan_probe(Path(name), "60", "ignored-chld")
        assert code == 4 and report["event"] == "UNCERTAIN"
        rescue = report.get("rescue")
        assert isinstance(rescue, dict) and rescue.get("certified") is False
        owner, worker = report["owner"], report["worker"]
        assert isinstance(owner, list) and isinstance(worker, list)
        assert rescue.get("refs") == sorted([owner, worker])


def test_cleanup_readback_error_is_uncertain_without_abandoning_reap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        ref = Ref(os.getpid(), 1, os.getuid(), -1)

        def case(inject: bool) -> tuple[dict[str, object], int]:
            waited = [False]
            inspections = [0]

            def wait_once(*_args: object) -> SimpleNamespace | None:
                if waited[0]:
                    return None
                waited[0] = True
                return SimpleNamespace(si_status=0, si_code=os.CLD_EXITED)

            def inspect(_ref: Ref) -> bool:
                inspections[0] += 1
                if inject and inspections[0] == 1:
                    raise PermissionError("injected pinned readback failure")
                return True

            with monkeypatch.context() as scoped:
                # This is bookkeeping injection only; no pytest child is adopted
                # or signaled. Real owner/worker cleanup has separate controls.
                scoped.setattr(sys.modules["owner_process_harness"], "_children", lambda _pid: [])
                scoped.setattr(
                    sys.modules["owner_process_harness"], "_signal", lambda _ref, _sig: True
                )
                scoped.setattr(sys.modules["owner_process_harness"], "_gone", inspect)
                scoped.setattr(os, "waitid", wait_once)
                from owner_process_harness import _cleanup

                report = _cleanup({(ref.pid, ref.start): ref}, ref, Path(name))
            return report, inspections[0]

        for inject, expected in ((False, "CLEAN"), (True, "UNCERTAIN")):
            report, inspections = case(inject)
            assert report["event"] == expected
            assert report["reaped"] == [ref.token()]
            assert inspections >= 3


def test_supervisor_signal_failure_still_attempts_final_wait_and_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        case = OwnerProcessCase(Path(name))
        original_wait = subprocess.Popen.wait
        original_signal = _signal
        original_gone = _gone
        waits = [0]
        denied = [False]
        read_back: set[tuple[int, int]] = set()

        def timeout_then_wait(
            process: subprocess.Popen[bytes], timeout: float | None = None
        ) -> int:
            if process is case.proc:
                waits[0] += 1
                if waits[0] < 3:
                    assert timeout is not None
                    raise subprocess.TimeoutExpired(process.args, timeout)
            return original_wait(process, timeout=timeout)

        def reject_supervisor_signal(ref: Ref, signum: int) -> bool:
            if case.supervisor is not None and ref.pid == case.supervisor.pid:
                denied[0] = True
                raise PermissionError("injected supervisor signal denial")
            return original_signal(ref, signum)

        def record_readback(ref: Ref) -> bool:
            read_back.add((ref.pid, ref.start))
            if ref.pid == case.refs[0].pid:
                raise PermissionError("injected owner readback denial")
            return original_gone(ref)

        try:
            with monkeypatch.context() as scoped:
                with pytest.raises(EvidenceError, match="cleanup UNCERTAIN"):
                    with case:
                        scoped.setattr(subprocess.Popen, "wait", timeout_then_wait)
                        scoped.setattr(sys.modules[__name__], "_signal", reject_supervisor_signal)
                        scoped.setattr(sys.modules[__name__], "_gone", record_readback)
                        assert case.live() == (200, b'{"status":"live"}')
            assert denied[0] and waits[0] >= 3
            assert case.supervisor is not None
            assert {(ref.pid, ref.start) for ref in [*case.refs, case.supervisor]} <= read_back
            assert not (Path(name) / "api.sock").exists()
        finally:
            if case.proc is not None:
                try:
                    original_wait(case.proc, timeout=5)
                except subprocess.TimeoutExpired:
                    assert case.supervisor is not None
                    original_signal(case.supervisor, signal.SIGKILL)
                    original_wait(case.proc, timeout=2)


@pytest.mark.parametrize("fault", ["missing", "invalid"])
def test_missing_or_invalid_ready_evidence_fails_closed_after_real_spawn(fault: str) -> None:
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
        case = OwnerProcessCase(Path(name), evidence=fault)
        with pytest.raises(EvidenceError, match="READY"):
            with case:
                pytest.fail("A missing or mismatched READY must never admit the owner")
        assert case.spawn_attested  # Independent, attested SPAWN over the same channel.
        if fault == "missing":
            assert case.ready_seen is None
        else:
            assert case.ready_seen is not None
            foreign = case.ready_seen.get("owner")
            assert isinstance(foreign, list) and foreign[0] == os.getpid()
            assert foreign != case.refs[0].token()
        assert not case.clean
        assert case.cleanup_gone
        assert not (Path(name) / "api.sock").exists()
