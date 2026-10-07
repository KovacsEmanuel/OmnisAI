"""Supervisor-only bounded UDS client; no Hermes imports or arbitrary RPC API."""

import asyncio
import json
import os
import re
import socket
import stat
import struct
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from omnis.core.paths import check_private_file, private_directory

if TYPE_CHECKING:
    from omnis.modules.instance.service import InstanceService, RuntimeAuthority

MAX_FRAME = 64 * 1024


class RuntimeUnavailable(ValueError):
    """Sanitized runtime failure; never expose raw IPC or credentials."""


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeUnavailable("Invalid runtime message")
        result[key] = value
    return result


def _object(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_FRAME:
        raise RuntimeUnavailable("Runtime message limit")
    try:
        value: object = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, RecursionError, UnicodeError):
        raise RuntimeUnavailable("Invalid runtime message") from None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RuntimeUnavailable("Invalid runtime message")
    return {key: item for key, item in value.items()}


class RuntimeClient:
    def __init__(
        self, directory: Path, *, generation: int, epoch: int, peer_uid: int | None = None
    ) -> None:
        if type(generation) is not int or generation < 0 or type(epoch) is not int or epoch < 1:
            raise RuntimeUnavailable("Invalid runtime fence")
        self.directory = directory
        self.generation = generation
        self.epoch = epoch
        self.peer_uid = os.getuid() if peer_uid is None else peer_uid
        self.boot = ""
        self.capability = ""
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.lock = asyncio.Lock()

    async def connect(self) -> None:
        private_directory(self.directory)
        fd = os.open(self.directory / "runtime.boot", os.O_RDONLY | os.O_NOFOLLOW)
        try:
            check_private_file(os.fstat(fd))
            with os.fdopen(fd, "rb", closefd=False) as source:
                metadata = _object(source.read(4097))
            boot, capability = metadata.get("boot"), metadata.get("capability")
            if (
                set(metadata) != {"version", "boot", "capability"}
                or type(metadata["version"]) is not int
                or metadata["version"] != 1
                or not isinstance(boot, str)
                or str(UUID(boot)) != boot
                or not isinstance(capability, str)
                or re.fullmatch("[0-9a-f]{64}", capability) is None
            ):
                raise RuntimeUnavailable("Invalid runtime identity")
            self.boot, self.capability = boot, capability
        finally:
            os.close(fd)
        info = (self.directory / "runtime.sock").lstat()
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise RuntimeUnavailable("Invalid runtime socket")
        try:
            async with asyncio.timeout(1):
                self.reader, self.writer = await asyncio.open_unix_connection(
                    str(self.directory / "runtime.sock"), limit=MAX_FRAME
                )
                peer = self.writer.get_extra_info("socket").getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, 12
                )
                if struct.unpack("3i", peer)[1] != self.peer_uid:
                    raise RuntimeUnavailable("Runtime peer denied")
        except BaseException:
            await self.close()
            raise

    async def _exchange(
        self, op: str, authority: "RuntimeAuthority | None" = None
    ) -> dict[str, object]:
        if op not in {"launch", "status", "renew", "stop"}:
            raise RuntimeUnavailable("Runtime operation denied")
        if op in {"launch", "renew"} and authority is None:
            raise RuntimeUnavailable("Runtime authority missing")
        async with self.lock:
            if self.reader is None or self.writer is None:
                raise RuntimeUnavailable("Runtime disconnected")
            correlation = str(uuid4())
            request: dict[str, object] = {
                "version": 1,
                "id": correlation,
                "boot": self.boot,
                "capability": self.capability,
                "generation": self.generation,
                "epoch": self.epoch,
                "op": op,
            }
            if authority is not None:
                if (authority.generation, authority.epoch) != (self.generation, self.epoch):
                    raise RuntimeUnavailable("Runtime authority mismatch")
                request["deadline_ns"] = authority.deadline_ns
            timeout = 2.0
            if op == "launch" and authority is not None:
                remaining = (authority.deadline_ns - time.monotonic_ns()) / 1_000_000_000
                if remaining <= 0:
                    raise RuntimeUnavailable("Expired runtime authority")
                timeout = min(6.0, remaining + 1.0)  # Bounded refusal/drain after grant expiry.
            try:
                async with asyncio.timeout(timeout):
                    self.writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
                    await self.writer.drain()
                    response = _object(await self.reader.readuntil(b"\n"))
                    if response.get("id") != correlation or response.get("boot") != self.boot:
                        raise RuntimeUnavailable("Runtime correlation mismatch")
                    if response.get("ok") is not True:
                        raise RuntimeUnavailable("Runtime refused")
                    state = response.get("state")
                    if not isinstance(state, str) or state not in {
                        "IDLE",
                        "STARTING",
                        "READY",
                        "STOPPING",
                        "STOPPED",
                        "UNCERTAIN",
                    }:
                        raise RuntimeUnavailable("Invalid runtime state")
                    if (
                        response.get("assessment_ready") is not False
                        or type(response.get("drained")) is not bool
                    ):
                        raise RuntimeUnavailable("Invalid runtime readiness")
                    for key in ("generation", "epoch"):
                        if type(response.get(key)) is not int:
                            raise RuntimeUnavailable("Invalid runtime fence")
                    if state == "IDLE":
                        if (response["generation"], response["epoch"]) != (0, 0):
                            raise RuntimeUnavailable("Invalid idle runtime")
                    elif (response["generation"], response["epoch"]) != (
                        self.generation,
                        self.epoch,
                    ):
                        raise RuntimeUnavailable("Runtime stale fence")
                    if response["drained"] != (state in {"IDLE", "STOPPED"}):
                        raise RuntimeUnavailable("Invalid runtime drain")
                    return response
            except (
                OSError,
                ValueError,
                TimeoutError,
                asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,
            ):
                await self.close()
                raise RuntimeUnavailable("Runtime exchange unavailable") from None

    async def status(self) -> dict[str, object]:
        return await self._exchange("status")

    async def launch_inert(self, service: "InstanceService", owner: UUID) -> dict[str, object]:
        authority = await service.runtime_authority(
            owner, self.epoch, self.generation, inert_probe=True
        )
        return await self._exchange("launch", authority)

    async def renew(self, service: "InstanceService", owner: UUID) -> dict[str, object]:
        try:
            authority = await service.runtime_authority(
                owner, self.epoch, self.generation, inert_probe=True
            )
            return await self._exchange("renew", authority)
        except BaseException:
            await self.close()
            raise

    async def drain(self) -> bool:
        try:
            status = await self._exchange("stop")
            observed = await self.status()  # Exact target readback, not just ACK.
            return status["drained"] is True and observed["drained"] is True
        except (OSError, ValueError, TimeoutError):
            return False

    async def close(self) -> None:
        writer, self.writer = self.writer, None
        self.reader = None
        if writer is not None:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.5)
