"""Bounded client for the existing private supervisor protocol (not a public HTTP admin)."""

import json
import os
import re
import socket
import stat
import struct
import time
from pathlib import Path
from uuid import UUID

from .instance import private_dir, private_file, unique_pairs


class ControlUnavailable(Exception):
    """The private peer or its authenticated response could not be verified."""


def _uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _discrete_json(value: object, depth: int = 0) -> bool:
    if depth > 16:
        return False
    if type(value) is dict:
        return all(
            type(key) is str and _discrete_json(item, depth + 1) for key, item in value.items()
        )
    if type(value) is list:
        return all(_discrete_json(item, depth + 1) for item in value)
    return type(value) in (str, int, bool, type(None))


def _stop_binding(command: dict[str, object]) -> dict[str, object]:
    fields = {
        "instance_id",
        "command_id",
        "finalize_command_id",
        "generation",
        "owner_epoch",
        "daemon_id",
        "inventory",
    }
    if set(command) != fields | {"op"} or command.get("op") != "arm_stop":
        raise ControlUnavailable()
    for key in ("instance_id", "command_id", "finalize_command_id"):
        if not _uuid(command[key]):
            raise ControlUnavailable()
    for key in ("generation", "owner_epoch"):
        value = command[key]
        if type(value) is not int or not 1 <= value <= 9223372036854775807:
            raise ControlUnavailable()
    daemon = command["daemon_id"]
    inventory = command["inventory"]
    if (
        type(daemon) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", daemon) is None
        or type(inventory) is not dict
        or not inventory
        or not _discrete_json(inventory)
    ):
        raise ControlUnavailable()
    # The real capability has the same fixed ASCII length. Bound the full frame
    # before opening a socket, not after sending an unbounded inventory.
    frame = {"version": 1, "capability": "0" * 64, "command": command}
    if len(json.dumps(frame).encode()) + 1 > 4096:
        raise ControlUnavailable()
    return {key: command[key] for key in fields}


def _stop_grant(reply: dict[str, object], command: dict[str, object]) -> dict[str, object]:
    grant = reply.get("grant")
    if (
        set(reply) != {"ok", "correlation_id", "grant"}
        or reply.get("ok") is not True
        or type(grant) is not dict
        or not _discrete_json(grant)
        or not _uuid(grant.get("owner_uuid"))
    ):
        raise ControlUnavailable()
    expected = {
        **_stop_binding(command),
        "version": 1,
        "state": "STOP_PENDING",
        "owner_uuid": grant["owner_uuid"],
    }
    actual = json.dumps(grant, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(actual.encode()) > 3600 or actual != json.dumps(
        expected, sort_keys=True, separators=(",", ":"), allow_nan=False
    ):
        raise ControlUnavailable()
    return expected


def request(
    directory: Path, command: dict[str, object], *, deadline: float | None = None
) -> dict[str, object]:
    try:
        if command.get("op") == "arm_stop":
            _stop_binding(command)
        private_dir(directory)
        info = (directory / "control.sock").lstat()
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ControlUnavailable()
        cap = private_file(directory / "control.cap", limit=64)
        if not re.fullmatch(r"[0-9a-f]{64}", cap):
            raise ControlUnavailable()
        deadline = (
            min(deadline, time.monotonic() + 2) if deadline is not None else time.monotonic() + 2
        )

        def remaining() -> float:
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise ControlUnavailable()
            return budget

        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(remaining())
            connection.connect(str(directory / "control.sock"))
            peer = connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            if struct.unpack("3i", peer)[1] != os.getuid():
                raise ControlUnavailable()
            payload = json.dumps({"version": 1, "capability": cap, "command": command}).encode()
            if len(payload) + 1 > 4096:
                raise ControlUnavailable()
            connection.settimeout(remaining())
            connection.sendall(payload + b"\n")
            data = bytearray()
            while not data.endswith(b"\n") and len(data) <= 4096:
                connection.settimeout(remaining())
                part = connection.recv(4097 - len(data))
                if not part:
                    raise ControlUnavailable()
                data.extend(part)
            if len(data) > 4096 or not data.endswith(b"\n"):
                raise ControlUnavailable()
        raw: object = json.loads(data, object_pairs_hook=unique_pairs)
        reply = raw
        if not isinstance(reply, dict) or not _uuid(reply.get("correlation_id")):
            raise ControlUnavailable()
        if command.get("op") == "arm_stop":
            return _stop_grant(reply, command)
        raw_status: object = reply.get("status")
        if reply.get("ok") is not True or not isinstance(raw_status, dict):
            raise ControlUnavailable()
        status: dict[str, object] = {}
        for key, value in raw_status.items():
            if not isinstance(key, str):
                raise ControlUnavailable()
            status[key] = value
        if set(status) != {
            "instance_id",
            "generation",
            "admission_open",
            "shutdown_command_id",
            "quiesced_generation",
            "supervisor_epoch",
            "supervisor_ready",
            "shutdown_finalized",
            "assessment_ready",
            "dashboard_ready",
        }:
            raise ControlUnavailable()
        generation = status.get("generation")
        epoch = status.get("supervisor_epoch")
        if (
            not _uuid(status.get("instance_id"))
            or not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation < 0
            or not isinstance(epoch, int)
            or isinstance(epoch, bool)
            or epoch < 1
            or status.get("supervisor_ready") is not True
            or type(status.get("admission_open")) is not bool
            or type(status.get("shutdown_finalized")) is not bool
            or type(status.get("assessment_ready")) is not bool
            or type(status.get("dashboard_ready")) is not bool
            or (
                status.get("shutdown_command_id") is not None
                and not _uuid(status["shutdown_command_id"])
            )
            or (
                status.get("quiesced_generation") is not None
                and type(status["quiesced_generation"]) is not int
            )
        ):
            raise ControlUnavailable()
        op = command.get("op")
        if op in {"open", "shutdown", "finalize"}:
            expected = command.get("expected_generation")
            result = reply.get("result_generation")
            owner_epoch = reply.get("owner_epoch")
            if (
                set(reply)
                != {
                    "ok",
                    "correlation_id",
                    "status",
                    "result_generation",
                    "command_id",
                    "expected_generation",
                    "owner_epoch",
                }
                or not _uuid(command.get("command_id"))
                or reply.get("command_id") != command["command_id"]
                or status["instance_id"] != command.get("instance_id")
                or type(expected) is not int
                or reply.get("expected_generation") != expected
                or type(reply.get("expected_generation")) is not int
                or type(result) is not int
                or result != generation
                or type(owner_epoch) is not int
                or owner_epoch != epoch
            ):
                raise ControlUnavailable()
            if op == "open":
                valid = (
                    result == expected + 1
                    and status["admission_open"] is True
                    and status["shutdown_command_id"] is None
                )
            elif op == "shutdown":
                valid = (
                    result == expected + 1
                    and status["admission_open"] is False
                    and status["shutdown_command_id"] is not None
                )
            else:
                valid = (
                    result == expected
                    and status["admission_open"] is False
                    and status["quiesced_generation"] == result
                    and status["shutdown_finalized"] is True
                )
            if not valid:
                raise ControlUnavailable()
        return status
    except (OSError, TimeoutError, ValueError, UnicodeError, RecursionError) as exc:
        raise ControlUnavailable() from exc
