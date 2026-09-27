"""Read-only readiness probe over the existing authenticated private status protocol."""

import asyncio
import os
import re
import socket
import stat
import struct
from contextlib import suppress
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from omnis.core.paths import check_private_file, private_directory
from omnis.modules.instance.domain import InstanceStatus
from omnis.modules.instance.schemas import ControlRequest, InstanceView, StatusCommand


class _StatusReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ok: Literal[True]
    correlation_id: UUID
    result_generation: None
    status: InstanceView


def _read_capability(directory: Path) -> str:
    private_directory(directory)
    info = (directory / "control.sock").lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise ValueError("Unavailable private control socket")
    fd = os.open(directory / "control.cap", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as source:
        check_private_file(os.fstat(source.fileno()))
        capability = source.read(65)
    if not re.fullmatch(r"[0-9a-f]{64}", capability):
        raise ValueError("Invalid capability")
    return capability


async def control_available(directory: Path | None, expected: InstanceStatus) -> bool:
    if directory is None or not expected.supervisor_ready:
        return False
    try:
        async with asyncio.timeout(2):
            capability = await asyncio.to_thread(_read_capability, directory)
            reader, writer = await asyncio.open_unix_connection(
                directory / "control.sock", limit=4096
            )
            try:
                peer = writer.get_extra_info("socket").getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                )
                if struct.unpack("3i", peer)[1] != os.getuid():
                    return False
                request = ControlRequest(
                    version=1, capability=capability, command=StatusCommand(op="status")
                )
                writer.write(request.model_dump_json().encode() + b"\n")
                await writer.drain()
                frame = await reader.readuntil(b"\n")
                if len(frame) > 4096:
                    return False
                reply = _StatusReply.model_validate_json(frame, strict=True)
                return (
                    reply.status.instance_id == expected.instance_id
                    and reply.status.generation == expected.generation
                    and reply.status.supervisor_epoch == expected.supervisor_epoch
                    and reply.status.supervisor_ready
                )
            finally:
                writer.close()
                with suppress(OSError, TimeoutError):
                    await asyncio.wait_for(writer.wait_closed(), 0.2)
    except (
        OSError,
        ValueError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        return False
