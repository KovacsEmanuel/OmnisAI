"""Bounded Unix control protocol, authenticated by kernel peer and boot capability."""

import asyncio
import fcntl
import hmac
import json
import os
import secrets
import socket
import struct
from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from omnis.core.db import readiness_reason
from omnis.core.paths import (
    check_private_file,
    private_directory,
    remove_stale_socket,
    unlink_owned_inode,
)
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.schemas import (
    ControlRequest,
    InstanceView,
    LifecycleCommand,
    PairingCommand,
    StatusCommand,
)
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import PairingConflict


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class LocalControl:
    def __init__(
        self,
        directory: Path,
        service: InstanceService,
        owner: UUID,
        epoch: int,
        *,
        peer_uid: int | None = None,
    ) -> None:
        self.directory = directory
        self.service = service
        self.owner = owner
        self.epoch = epoch
        self.peer_uid = os.getuid() if peer_uid is None else peer_uid
        self.capability = secrets.token_hex(32)
        self.server: asyncio.AbstractServer | None = None
        self.lock_fd: int | None = None
        self.socket_inode: int | None = None
        self.cap_inode: int | None = None
        self.clients: set[asyncio.Task[object]] = set()

    async def __aenter__(self) -> Self:
        private_directory(self.directory)
        try:
            self.lock_fd = os.open(
                self.directory / "control.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            check_private_file(os.fstat(self.lock_fd))
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            remove_stale_socket(self.directory / "control.sock")
            cap_path = self.directory / "control.cap"
            if cap_path.exists() or cap_path.is_symlink():
                check_private_file(cap_path.lstat())
                cap_path.unlink()
            fd = os.open(cap_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as output:
                self.cap_inode = os.fstat(output.fileno()).st_ino
                output.write(self.capability)
                output.flush()
                os.fsync(output.fileno())
            self.server = await asyncio.start_unix_server(
                self._handle,
                path=str(self.directory / "control.sock"),
                limit=4096,
                backlog=16,
                cleanup_socket=False,
                start_serving=False,
            )
            self.socket_inode = (self.directory / "control.sock").stat().st_ino
            (self.directory / "control.sock").chmod(0o600)
            # Own cleanup and set mode before start_serving's cancellation point.
            await self.server.start_serving()
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        clients = list(self.clients)
        for client in clients:
            client.cancel()
        if clients:
            await asyncio.gather(*clients, return_exceptions=True)
        unlink_owned_inode(self.directory / "control.sock", self.socket_inode)
        unlink_owned_inode(self.directory / "control.cap", self.cap_inode)
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    async def _dispatch(
        self, command: StatusCommand | PairingCommand | LifecycleCommand
    ) -> dict[str, object]:
        if await readiness_reason(self.service.engine) is not None:
            return {"ok": False, "error": "CONTROL_UNAVAILABLE"}
        status = await self.service.owned_status(self.owner, self.epoch)
        result_generation: int | None = None
        if not isinstance(command, StatusCommand):
            if command.instance_id != status.instance_id:
                return {"ok": False, "error": "INSTANCE_MISMATCH"}
            if isinstance(command, PairingCommand):
                await self.service.register_pairing(
                    command.instance_id, command.digest, command.issuance_id, self.owner, self.epoch
                )
            elif command.op == "open":
                result_generation = await self.service.open(
                    command.command_id, command.expected_generation, self.owner, self.epoch
                )
            elif command.op == "shutdown":
                result_generation = await self.service.shutdown(
                    command.command_id, command.expected_generation, self.owner, self.epoch
                )
            elif command.op == "finalize":
                result_generation = await self.service.finalize(
                    command.command_id, command.expected_generation, self.owner, self.epoch
                )
            status = await self.service.status()
        return {
            "ok": True,
            "result_generation": result_generation,
            "status": InstanceView.model_validate(status).model_dump(mode="json"),
        }

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None  # start_unix_server runs each coroutine callback in a Task.
        if len(self.clients) >= 16:
            writer.close()
            return
        self.clients.add(task)
        try:
            try:
                async with asyncio.timeout(4):
                    peer = writer.get_extra_info("socket").getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                    )
                    _, uid, _ = struct.unpack("3i", peer)
                    if uid != self.peer_uid:
                        response = {"ok": False, "error": "CONTROL_DENIED"}
                    else:
                        frame = await reader.readuntil(b"\n")
                        if len(frame) > 4096:
                            raise ValueError("Oversized frame")
                        body = ControlRequest.model_validate(
                            json.loads(frame, object_pairs_hook=unique_object)
                        )
                        if not hmac.compare_digest(
                            body.capability.encode(), self.capability.encode()
                        ):
                            response = {"ok": False, "error": "CONTROL_DENIED"}
                        else:
                            response = await self._dispatch(body.command)
            except (
                ValueError,
                ValidationError,
                RecursionError,
                asyncio.LimitOverrunError,
                asyncio.IncompleteReadError,
            ):
                response = {"ok": False, "error": "INVALID_REQUEST"}
            except TimeoutError:
                response = {"ok": False, "error": "CONTROL_TIMEOUT"}
            except SQLAlchemyError:
                response = {"ok": False, "error": "CONTROL_UNAVAILABLE"}
            except ControlConflict as exc:
                response = {"ok": False, "error": exc.code.value}
            except PairingConflict:
                response = {"ok": False, "error": "PAIRING_CONFLICT"}
            response["correlation_id"] = str(uuid4())
            writer.write(json.dumps(response).encode() + b"\n")
            await asyncio.wait_for(writer.drain(), 1)
        except (ConnectionError, TimeoutError):
            # Disconnected clients cannot undo a committed command; retry via its receipt.
            return
        finally:
            self.clients.discard(task)
            writer.close()
            # A disconnected peer may fail to close, but must not erase a pending cancellation.
            with suppress(ConnectionError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 1)
