"""Private inert owner; fixed native entrypoint, no model/task execution API."""

import asyncio
import hmac
import json
import os
import secrets
import signal
import socket
import struct
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Self
from uuid import UUID, uuid4

from . import private_paths
from .runtime_protocol import MAX_FRAME, NativePeer, encode, unique_object

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
OPS = frozenset({"launch", "status", "renew", "stop"})


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
    ):
        self.directory = directory
        self.peer_uid = os.getuid() if peer_uid is None else peer_uid
        self.launch_spec = _test_launch
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
        self.namespace_owned = os.getpid() == 1 and _test_launch is None
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
            if self.process is None or self.state in {"STOPPED", "UNCERTAIN"}:
                return
            self.state = "STOPPING"
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
                drained = self.process.returncode is not None and not self._owned_pids()
                self.state = "STOPPED" if drained and self.namespace_owned else "UNCERTAIN"
            finally:
                for fd in handles.values():
                    os.close(fd)

    def _validate(self, body: object) -> dict[str, object]:
        if type(body) is not dict:
            raise ValueError("Invalid IPC")
        if type(body.get("op")) is not str:
            raise ValueError("Invalid operation type")
        expected = {"version", "id", "boot", "capability", "generation", "epoch", "op"}
        if body.get("op") in {"launch", "renew"}:
            expected.add("deadline_ns")
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
                    body = json.loads(raw, object_pairs_hook=unique_object)
                    if type(body) is dict and type(body.get("id")) is str:
                        correlation = body["id"]
                    body = self._validate(body)
                    if self.owner_writer is not None and self.owner_writer is not writer:
                        raise ValueError("Runtime already owned")
                    self.owner_writer = writer
                    authenticated = True
                    async with self.command_lock:
                        if body["op"] == "launch":
                            await self._launch(body)
                        elif body["op"] == "renew":
                            if self.state != "READY" or time.monotonic_ns() >= self.deadline_ns:
                                raise ValueError("Expired authority")
                            self.deadline_ns = self._grant(body)
                        elif body["op"] == "stop":
                            await self.stop()
                        response = {"ok": True, "id": correlation, **self.snapshot()}
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
