"""Private inert owner; fixed native entrypoint, no model/task execution API."""

import asyncio
import hmac
import json
import os
import secrets
import shutil
import signal
import socket
import stat
import struct
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Self, cast
from uuid import UUID, uuid4

from . import managed_admission_contract as managed
from . import private_paths
from .native_preparation_contract import (
    LIMITS,
    canonical,
    digest,
    loads,
    validate_payload,
    validate_result,
)
from .native_preparation_worker import PATHS, regular_bytes
from .runtime_protocol import MAX_FRAME, NativePeer, encode

NATIVE_COMMAND = ("/opt/hermes/venv/bin/python", "-I", "-m", "tui_gateway.entry")
NATIVE_CWD = Path("/state/work")
NATIVE_ENV = {
    "HOME": "/state/os-home",
    "HERMES_HOME": "/state/active",
    "CODEX_HOME": "/state/codex",
    "XDG_CONFIG_HOME": "/state/xdg/config",
    "XDG_CACHE_HOME": "/state/xdg/cache",
    "XDG_STATE_HOME": "/state/xdg/state",
    "XDG_DATA_HOME": "/state/xdg/data",
    "TMPDIR": "/state/tmp",
    "PATH": "/opt/hermes/venv/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "PYTHONUNBUFFERED": "1",
    "PYTHONNOUSERSITE": "1",
    "HERMES_OMNIS_INERT": "1",
    "HERMES_MANAGED_DIR": "/state/managed-empty",
    "HERMES_DISABLE_LAZY_INSTALLS": "1",
    "HERMES_SKIP_NODE_BOOTSTRAP": "1",
}
OPS = frozenset({"launch", "status", "renew", "stop", "prepare"}) | managed.OPS
PREPARATION_COMMAND = (
    "/opt/hermes/venv/bin/python",
    "-I",
    "-B",
    "-m",
    "omnis_hermes.native_preparation_worker",
)
# Prepare-specific, measured cold-import budget. Existing native/RPC grants are unchanged.
PREPARATION_SECONDS = 2.5
PREPARATION_CLEANUP_SECONDS = 0.4


@dataclass(frozen=True)
class TestPreparation:
    """Trusted source-unit subprocess seam only; never accepted from env/argv/IPC."""

    command: tuple[str, ...]
    temporary_root: Path


@dataclass(frozen=True)
class TestLaunch:
    """Trusted Python constructor seam ONLY. Never decoded from IPC/env."""

    command: tuple[str, ...]
    cwd: Path


class RuntimeHost:
    def __init__(
        self,
        directory: Path,
        *,
        peer_uid: int | None = None,
        _test_launch: TestLaunch | None = None,
        _test_preparation: TestPreparation | None = None,
    ):
        self.directory = directory
        self.peer_uid = os.getuid() if peer_uid is None else peer_uid
        self.launch_spec = _test_launch
        self.preparation_spec = _test_preparation
        self.preparation_process: asyncio.subprocess.Process | None = None
        self.preparation_task: asyncio.Task[dict[str, object]] | None = None
        self.preparation_root: tuple[Path, tuple[int, int]] | None = None
        self.boot = str(uuid4())
        self.capability = secrets.token_hex(32)
        self.process: asyncio.subprocess.Process | None = None
        self.peer: NativePeer | None = None
        self.server: asyncio.AbstractServer | None = None
        self.lock_fd: int | None = None
        self.identities: dict[str, tuple[int, int]] = {}
        self.clients: set[asyncio.Task[None]] = set()
        self.owner_writer: asyncio.StreamWriter | None = None
        self.watchdog: asyncio.Task[None] | None = None
        self.deadline_ns = 0
        self.generation = 0
        self.epoch = 0
        self.state = "IDLE"
        # Only the fixed entrypoint as PID1 may certify whole-namespace drain.
        self.namespace_owned = (
            os.getpid() == 1 and _test_launch is None and _test_preparation is None
        )
        self.stop_lock = asyncio.Lock()
        self.command_lock = asyncio.Lock()
        self.capabilities: dict[str, object] = {}

    async def __aenter__(self) -> Self:
        private_paths.directory(self.directory)
        try:
            self.lock_fd = private_paths.lock(self.directory / "runtime.lock")
            # Refuse leftovers rather than adopt or remove another owner's state.
            for name in ("runtime.sock", "runtime.boot"):
                if os.path.lexists(self.directory / name):
                    raise ValueError("Runtime state already exists")
            fd = os.open(
                self.directory / "runtime.boot",
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w") as output:
                info = os.fstat(output.fileno())
                self.identities["runtime.boot"] = (info.st_dev, info.st_ino)
                json.dump({"version": 1, "boot": self.boot, "capability": self.capability}, output)
                output.flush()
                os.fsync(output.fileno())
            self.server = await asyncio.start_unix_server(
                self._handle,
                path=str(self.directory / "runtime.sock"),
                limit=MAX_FRAME,
                backlog=32,
                start_serving=False,
                cleanup_socket=False,
            )
            info = (self.directory / "runtime.sock").lstat()
            self.identities["runtime.sock"] = (info.st_dev, info.st_ino)
            (self.directory / "runtime.sock").chmod(0o600)
            self.watchdog = asyncio.create_task(self._watch())
            await self.server.start_serving()
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *_exc: object) -> None:
        if self.server is not None:
            self.server.close()
            # Python 3.13 wait_closed includes active transports. Close them
            # before waiting, including a live client on an exception path.
            self.server.close_clients()
            await self.server.wait_closed()
        if self.watchdog is not None:
            self.watchdog.cancel()
            await asyncio.gather(self.watchdog, return_exceptions=True)
        await self.stop()
        tasks = list(self.clients)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for name, identity in self.identities.items():
            private_paths.unlink(self.directory / name, identity)
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    def snapshot(self) -> dict[str, object]:
        return {
            "state": self.state,
            "generation": self.generation,
            "epoch": self.epoch,
            "boot": self.boot,
            "drained": self.state in {"IDLE", "STOPPED"},
            "assessment_ready": False,
            "capabilities": self.capabilities,
            "bootstrap_inventory": self.peer.bootstrap_inventory if self.peer is not None else None,
        }

    def _grant(self, body: dict[str, object]) -> int:
        deadline = body.get("deadline_ns")
        now = time.monotonic_ns()
        if type(deadline) is not int or not now < deadline <= now + 5_000_000_000:
            raise ValueError("Invalid authority deadline")
        return deadline

    async def _launch(self, body: dict[str, object]) -> None:
        if self.state != "IDLE":
            raise ValueError("Boot launch already used")
        self.deadline_ns = self._grant(body)
        generation, epoch = body["generation"], body["epoch"]
        assert isinstance(generation, int) and isinstance(epoch, int)
        self.generation, self.epoch = generation, epoch
        self.state = "STARTING"
        command = NATIVE_COMMAND if self.launch_spec is None else self.launch_spec.command
        cwd = NATIVE_CWD if self.launch_spec is None else self.launch_spec.cwd
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                env=dict(NATIVE_ENV),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                limit=MAX_FRAME,
            )
            self.peer = NativePeer(self.process, timeout=0.8)
            remaining = (self.deadline_ns - time.monotonic_ns()) / 1_000_000_000
            async with asyncio.timeout(remaining):
                self.capabilities = await self.peer.handshake(ready_timeout=remaining)
            if time.monotonic_ns() >= self.deadline_ns or self.state != "STARTING":
                raise ValueError("Authority expired during launch")
            self.state = "READY"
        except BaseException:
            await self.stop()
            raise

    def _preparation_ready(self) -> None:
        if (
            self.state != "READY"
            or time.monotonic_ns() >= self.deadline_ns
            or self.peer is None
            or self.peer.failure is not None
            or self.process is None
            or self.process.returncode is not None
        ):
            raise ValueError("Expired preparation authority")

    async def _managed(self, body: dict[str, object]) -> dict[str, object]:
        """Finite call on the existing owner/peer, never retry a lost native reply."""
        self._preparation_ready()
        operation = body["op"]
        assert isinstance(operation, str)
        payload = cast(dict[str, object], body["payload"])
        validators = {
            "task_stage": managed.validate_stage,
            "task_release": managed.validate_release,
            "task_status": managed.validate_status,
            "task_model_preflight": managed.validate_model_preflight,
            "task_model_initialize": managed.validate_initialization,
        }
        validators[operation](payload)
        if operation == "task_model_initialize":
            authority = cast(dict[str, object], payload["authority"])
            if payload["runtime_boot"] != self.boot or (
                authority["generation"],
                authority["epoch"],
            ) != (self.generation, self.epoch):
                raise ValueError("Stale initialization authority")
        if operation in ("task_release", "task_model_preflight"):
            binding = cast(
                dict[str, object], cast(dict[str, object], payload["binding"])["payload"]
            )
            authority = cast(dict[str, object], binding["authority"])
            if binding["runtime_boot"] != self.boot or (
                authority["generation"],
                authority["epoch"],
            ) != (self.generation, self.epoch):
                raise ValueError("Stale managed authority")
        deadline = self._grant(body)
        if deadline > time.monotonic_ns() + 4_500_000_000:
            raise ValueError("Invalid managed grant")
        self.deadline_ns = deadline
        remaining = min(3.2, (deadline - time.monotonic_ns()) / 1_000_000_000)
        assert self.peer is not None
        async with asyncio.timeout(remaining):
            if operation == "task_model_initialize":
                observed = await self.peer.call(managed.RPC[operation], payload, timeout=remaining)
                self._preparation_ready()
                return managed.validate_initialization_result(observed, payload)
            if operation == "task_model_preflight":
                from .model_admission import validate_preflight_result

                observed = await self.peer.call(managed.RPC[operation], payload, timeout=remaining)
                self._preparation_ready()
                return validate_preflight_result(observed, payload)
            result = managed.validate_response(
                await self.peer.call(managed.RPC[operation], payload, timeout=remaining)
            )
        self._preparation_ready()
        if result["protocol"] != payload["protocol"]:
            raise ValueError("Native managed protocol mismatch")
        composed = payload["protocol"] in (managed.PROTOCOL_V2, managed.PROTOCOL_V3)
        if operation == "task_stage":
            manifest = managed.validate_stage(payload)
            rows = managed.entries(
                cast(dict[str, object], manifest["payload"])["entries"],
                native=False,
                composed=composed,
            )
            expected = [{k: v for k, v in e.items() if k != "goal"} for e in rows]
            observed = [
                {k: v for k, v in e.items() if k not in {"native_child_id", "native_session_id"}}
                for e in managed.entries(result["entries"], native=True, composed=composed)
            ]
            if result["manifest_ref"] != managed.ref(manifest) or observed != expected:
                raise ValueError("Native stage mismatch")
        else:
            if any(result[k] != payload[k] for k in ("ticket", "manifest_ref")):
                raise ValueError("Native readback mismatch")
            if operation == "task_release" and (
                result["status"] != "BLOCKED"
                or result["binding_ref"] != managed.ref(cast(dict[str, object], payload["binding"]))
                or any(result[k] != binding[k] for k in ("native_root_id", "entries"))
            ):
                raise ValueError("Native binding mismatch")
        return result

    async def _managed_connected(
        self, body: dict[str, object], reader: asyncio.StreamReader
    ) -> dict[str, object]:
        operation = asyncio.create_task(self._managed(body))
        disconnected = asyncio.create_task(reader.read(1))
        try:
            await asyncio.wait((operation, disconnected), return_when=asyncio.FIRST_COMPLETED)
            if disconnected.done() or reader.at_eof():
                raise ValueError("Managed owner disconnected")
            return await operation
        finally:
            if not operation.done():
                operation.cancel()
            disconnected.cancel()
            await asyncio.gather(operation, disconnected, return_exceptions=True)

    async def _prepare(self, body: dict[str, object]) -> dict[str, object]:
        self._preparation_ready()
        validate_payload(body["payload"])
        if self.preparation_task is not None or self.preparation_root is not None:
            raise ValueError("Native preparation busy")
        deadline = self._grant(body)
        if deadline > time.monotonic_ns() + 4_500_000_000:
            raise ValueError("Invalid preparation authority")
        self._preparation_ready()
        self.deadline_ns = deadline
        task = asyncio.create_task(self._run_preparation(body["payload"]))
        self.preparation_task = task
        try:
            result = await asyncio.shield(task)
            self._preparation_ready()
            return result
        finally:
            if not task.done():
                task.cancel()
            await asyncio.shield(asyncio.gather(task, return_exceptions=True))
            self.preparation_task = None

    async def _prepare_connected(
        self, body: dict[str, object], reader: asyncio.StreamReader
    ) -> dict[str, object]:
        # The sole client is sequential. EOF or pipelining invalidates this effect.
        operation = asyncio.create_task(self._prepare(body))
        disconnected = asyncio.create_task(reader.read(1))
        try:
            await asyncio.wait((operation, disconnected), return_when=asyncio.FIRST_COMPLETED)
            if disconnected.done() or reader.at_eof():
                raise ValueError("Preparation owner disconnected")
            return await operation
        finally:
            if not operation.done():
                operation.cancel()
            disconnected.cancel()
            await asyncio.gather(operation, disconnected, return_exceptions=True)

    def _preparation_home(self) -> tuple[Path, dict[str, str]]:
        parent = (
            Path("/state/tmp")
            if self.preparation_spec is None
            else self.preparation_spec.temporary_root
        )
        private_paths.directory(parent)
        if any(entry.name.startswith("native-prep-") for entry in parent.iterdir()):
            raise ValueError("Preparation crash leftover")
        root = parent / f"native-prep-{uuid4()}"
        root.mkdir(mode=0o700)
        info = root.lstat()
        self.preparation_root = (root, (info.st_dev, info.st_ino))
        env = dict(NATIVE_ENV)
        for key, relative in PATHS.items():
            path = root / relative
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            env[key] = str(path)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return root, env

    async def _worker_output(self, process: asyncio.subprocess.Process, raw: bytes) -> bytes:
        assert (
            process.stdin is not None and process.stdout is not None and process.stderr is not None
        )

        async def bounded_read(stream: asyncio.StreamReader, maximum: int) -> bytes:
            output = bytearray()
            while chunk := await stream.read(4096):
                output.extend(chunk)
                if len(output) > maximum:
                    raise ValueError("Preparation output limit")
            return bytes(output)

        async def send() -> None:
            assert process.stdin is not None
            process.stdin.write(raw)
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()

        outputs = [
            asyncio.create_task(bounded_read(process.stdout, LIMITS["max_worker_result_bytes"])),
            asyncio.create_task(bounded_read(process.stderr, 8192)),
        ]
        sender = asyncio.create_task(send())
        try:
            await asyncio.gather(*outputs, sender, process.wait())
            if process.returncode != 0:
                raise ValueError("Native preparation rejected")
            return outputs[0].result()
        finally:
            for task in [*outputs, sender]:
                task.cancel()
            await asyncio.gather(*outputs, sender, return_exceptions=True)

    def _preparation_pids(self, baseline: set[int]) -> set[int]:
        if self.namespace_owned:
            return self._owned_pids() - baseline
        process = self.preparation_process
        if process is None:
            return set()
        # Source-unit seam only: track this fresh session, never host-wide ownership.
        result = set()
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                with suppress(FileNotFoundError, ProcessLookupError):
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    if int(fields[3]) == process.pid:
                        result.add(int(entry.name))
        return result

    def _remove_preparation_home(self) -> None:
        if self.preparation_root is None:
            return
        root, identity = self.preparation_root
        info = root.lstat()
        if (info.st_dev, info.st_ino) != identity or not stat.S_ISDIR(info.st_mode):
            raise ValueError("Preparation cleanup uncertain")

        # fd-based traversal: never chmod or follow a replaced symlink.
        def writable(fd: int) -> None:
            os.fchmod(fd, 0o700)
            for name in os.listdir(fd):
                child = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(child.st_mode):
                    nested = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        writable(nested)
                    finally:
                        os.close(nested)

        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            current = os.fstat(fd)
            if (current.st_dev, current.st_ino) != identity:
                raise ValueError("Preparation cleanup uncertain")
            writable(fd)
        finally:
            os.close(fd)
        current = root.lstat()
        if (current.st_dev, current.st_ino) != identity:
            raise ValueError("Preparation cleanup uncertain")
        shutil.rmtree(root)
        if os.path.lexists(root):
            raise ValueError("Preparation cleanup uncertain")
        self.preparation_root = None

    async def _clean_preparation(self, baseline: set[int]) -> None:
        started = time.monotonic()
        try:
            async with asyncio.timeout(PREPARATION_CLEANUP_SECONDS):
                process = self.preparation_process
                if process is not None:
                    for pid in self._preparation_pids(baseline):
                        with suppress(ProcessLookupError):
                            fd = os.pidfd_open(pid)
                            try:
                                signal.pidfd_send_signal(fd, signal.SIGKILL)
                            finally:
                                os.close(fd)
                    if process.returncode is None:
                        process.kill()
                    await process.wait()
                    # PID1 adopts detached descendants. Reap only this worker's set.
                    while pids := self._preparation_pids(baseline):
                        for pid in pids:
                            with suppress(ProcessLookupError):
                                fd = os.pidfd_open(pid)
                                try:
                                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                                finally:
                                    os.close(fd)
                            if self.namespace_owned:
                                with suppress(ChildProcessError):
                                    os.waitpid(pid, os.WNOHANG)
                        await asyncio.sleep(0.005)
                self._remove_preparation_home()
                self.preparation_process = None
                if time.monotonic() - started >= PREPARATION_CLEANUP_SECONDS:
                    raise ValueError("Preparation cleanup exceeded budget")
        except (OSError, ValueError, TimeoutError):
            self.state = "UNCERTAIN"
            raise ValueError("Preparation cleanup uncertain") from None

    async def _run_preparation(self, payload: object) -> dict[str, object]:
        baseline = self._owned_pids()
        result: dict[str, object]
        try:
            remaining = (self.deadline_ns - time.monotonic_ns()) / 1_000_000_000
            budget = min(PREPARATION_SECONDS, remaining - PREPARATION_CLEANUP_SECONDS)
            if budget <= 0:
                raise ValueError("Expired preparation authority")
            worker_deadline = time.monotonic() + budget
            async with asyncio.timeout(budget):
                root, env = self._preparation_home()
                command = (
                    PREPARATION_COMMAND
                    if self.preparation_spec is None
                    else self.preparation_spec.command
                )
                # Finish spawn acquisition even if cancellation lands during fork/exec.
                spawn = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        *command,
                        cwd=root / "work",
                        env=env,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=True,
                        limit=LIMITS["max_worker_result_bytes"],
                    )
                )
                try:
                    self.preparation_process = await asyncio.shield(spawn)
                except asyncio.CancelledError:
                    self.preparation_process = await spawn
                    raise
                output = await self._worker_output(
                    self.preparation_process, canonical(payload) + b"\n"
                )
                if not output.endswith(b"\n") or output.count(b"\n") != 1:
                    raise ValueError("Invalid preparation output")
                value = loads(output, LIMITS["max_worker_result_bytes"])
                worker_hash = digest(
                    regular_bytes(Path(__file__).with_name("native_preparation_worker.py"), 131072)
                )
                result = validate_result(value, payload, worker_hash)
                if self._preparation_pids(baseline):
                    raise ValueError("Preparation descendants remain")
                if time.monotonic() >= worker_deadline:
                    raise TimeoutError("Preparation exceeded budget")
        finally:
            # A separately owned cleanup task cannot be interrupted by owner cancellation.
            cleanup = asyncio.create_task(self._clean_preparation(baseline))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
        self._preparation_ready()
        if not self.namespace_owned:
            raise ValueError("Preparation containment unproved")
        return result

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(0.025)
            if self.state in {"STARTING", "READY"} and (
                time.monotonic_ns() >= self.deadline_ns
                or (self.peer is not None and self.peer.failure is not None)
            ):
                await self.stop()

    def _owned_pids(self) -> set[int]:
        if self.process is None:
            return set()
        # Namespace PID1 owns all runtime namespace processes, not host-wide PIDs.
        if self.namespace_owned:
            return {
                int(entry.name)
                for entry in Path("/proc").iterdir()
                if entry.name.isdigit() and int(entry.name) != os.getpid()
            }
        # Outside that boundary only the still-parented descendant tree is owned.
        parents: dict[int, int] = {}
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                with suppress(FileNotFoundError, ProcessLookupError):
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    parents[int(entry.name)] = int(fields[1])
        owned = {self.process.pid} if self.process.returncode is None else set()
        previous: set[int] = set()
        while previous != owned:
            previous = owned.copy()
            owned.update(pid for pid, parent in parents.items() if parent in owned)
        return owned

    async def stop(self) -> None:
        async with self.stop_lock:
            if self.process is None or self.state == "STOPPED":
                return
            uncertain = self.state == "UNCERTAIN"
            if uncertain and self.process.returncode is not None and self.preparation_task is None:
                return
            self.state = "STOPPING"
            if self.preparation_task is not None:
                self.preparation_task.cancel()
                await asyncio.gather(self.preparation_task, return_exceptions=True)
            handles: dict[int, int] = {}
            try:
                for pid in self._owned_pids():
                    with suppress(ProcessLookupError):
                        handles[pid] = os.pidfd_open(pid)
                # Leader is unreaped and pinned while its group receives TERM.
                if self.process.returncode is None:
                    with suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGTERM)
                for fd in handles.values():
                    with suppress(ProcessLookupError):
                        signal.pidfd_send_signal(fd, signal.SIGTERM)
                await asyncio.sleep(0.15)
                for pid in self._owned_pids():
                    if pid not in handles:
                        with suppress(ProcessLookupError):
                            handles[pid] = os.pidfd_open(pid)
                for fd in handles.values():
                    with suppress(ProcessLookupError):
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                if self.peer is not None:
                    await self.peer.close()
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.process.wait(), 0.5)
                # PID1 adopts orphans in its dedicated namespace; reap exact owned IDs.
                if self.namespace_owned:
                    for pid in handles:
                        if pid != self.process.pid:
                            with suppress(ChildProcessError):
                                os.waitpid(pid, os.WNOHANG)
                drained = (
                    self.process.returncode is not None
                    and not self._owned_pids()
                    and self.preparation_process is None
                    and self.preparation_root is None
                )
                self.state = (
                    "STOPPED" if drained and self.namespace_owned and not uncertain else "UNCERTAIN"
                )
            finally:
                for fd in handles.values():
                    os.close(fd)

    def _validate(self, body: object) -> dict[str, object]:
        if type(body) is not dict:
            raise ValueError("Invalid IPC")
        if type(body.get("op")) is not str:
            raise ValueError("Invalid operation type")
        expected = {"version", "id", "boot", "capability", "generation", "epoch", "op"}
        if body.get("op") in {"launch", "renew", "prepare"} | managed.OPS:
            expected.add("deadline_ns")
        if body.get("op") in {"prepare"} | managed.OPS:
            expected.add("payload")
        if set(body) != expected or type(body["version"]) is not int or body["version"] != 1:
            raise ValueError("Invalid IPC fields")
        if type(body["id"]) is not str or str(UUID(body["id"])) != body["id"]:
            raise ValueError("Invalid correlation")
        if body["op"] not in OPS or type(body["capability"]) is not str:
            raise ValueError("Invalid operation")
        if body["boot"] != self.boot or not hmac.compare_digest(
            body["capability"].encode(), self.capability.encode()
        ):
            raise ValueError("Runtime identity denied")
        if any(
            type(body[key]) is not int
            or not (0 if key == "generation" else 1) <= body[key] <= 2**63 - 1
            for key in ("generation", "epoch")
        ):
            raise ValueError("Invalid fence")
        if self.epoch and (body["generation"], body["epoch"]) != (self.generation, self.epoch):
            raise ValueError("Stale fence")
        if body["op"] == "prepare":
            validate_payload(body["payload"])
            if len(canonical(body)) + 1 > LIMITS["max_runtime_request_bytes"]:
                raise ValueError("Invalid native preparation")
        if body["op"] in managed.OPS:
            {
                "task_stage": managed.validate_stage,
                "task_release": managed.validate_release,
                "task_status": managed.validate_status,
                "task_model_preflight": managed.validate_model_preflight,
            }[body["op"]](body["payload"])
        return body

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is None or len(self.clients) >= 32:
            writer.close()
            return
        self.clients.add(task)
        authenticated = False
        try:
            peer = writer.get_extra_info("socket").getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
            )
            if struct.unpack("3i", peer)[1] != self.peer_uid:
                return
            while True:
                correlation = None
                try:
                    raw = await asyncio.wait_for(reader.readuntil(b"\n"), 2.5)
                    if len(raw) > MAX_FRAME:
                        raise ValueError("Frame limit")
                    body = loads(raw, MAX_FRAME)
                    if type(body) is dict and type(body.get("id")) is str:
                        correlation = body["id"]
                    body = self._validate(body)
                    if body["op"] == "prepare" and len(raw) > LIMITS["max_runtime_request_bytes"]:
                        raise ValueError("Preparation frame limit")
                    if self.owner_writer is not None and self.owner_writer is not writer:
                        raise ValueError("Runtime already owned")
                    self.owner_writer = writer
                    authenticated = True
                    async with self.command_lock:
                        preparation = None
                        managed_result = None
                        if body["op"] == "launch":
                            await self._launch(body)
                        elif body["op"] == "renew":
                            if self.state != "READY" or time.monotonic_ns() >= self.deadline_ns:
                                raise ValueError("Expired authority")
                            self.deadline_ns = self._grant(body)
                        elif body["op"] == "prepare":
                            preparation = await self._prepare_connected(body, reader)
                        elif body["op"] in managed.OPS:
                            managed_result = await self._managed_connected(body, reader)
                        elif body["op"] == "stop":
                            await self.stop()
                        response = {"ok": True, "id": correlation, **self.snapshot()}
                        if preparation is not None:
                            response["preparation"] = preparation
                        if managed_result is not None:
                            response["managed"] = managed_result
                except (ValueError, OSError, TimeoutError, asyncio.LimitOverrunError):
                    response = {
                        "ok": False,
                        "id": correlation,
                        "error": "RUNTIME_DENIED",
                        **self.snapshot(),
                    }
                writer.write(encode(response))
                await asyncio.wait_for(writer.drain(), 0.5)
        except (OSError, TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            if authenticated:
                await self.stop()
                self.owner_writer = None
            self.clients.discard(task)
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.5)


async def run() -> None:
    raw = os.environ.get("OMNIS_RUNTIME_DIR")
    if not raw or len(sys.argv) != 1:
        raise ValueError("Explicit private runtime directory required")
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    try:
        async with RuntimeHost(Path(raw)):
            print("RUNTIME_HOST_READY", flush=True)
            await stopped.wait()
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def main() -> int:
    try:
        asyncio.run(run())
    except (ValueError, OSError, TimeoutError):
        print("RUNTIME_HOST_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
