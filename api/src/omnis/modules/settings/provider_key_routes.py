"""Paired API-key Settings forwards bounded commands to its private supervisor."""

import asyncio
import json
import os
import socket
import struct
from contextlib import suppress
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Request
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.modules.settings.provider_key_models import (
    KeySettingsControl,
    KeySettingsView,
    ReadSettings,
    RevokeConnection,
    SaveConnection,
    SaveSelection,
)
from omnis.modules.settings.provider_key_service import SettingsConflict
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object
from omnis.transport.control_probe import _read_capability

router = APIRouter(prefix="/api/v1/settings/providers")


async def settings_exchange(command: KeySettingsControl) -> KeySettingsView:
    directory_raw = os.environ.get("OMNIS_CONTROL_DIR")
    if not directory_raw:
        raise ValueError("Control unavailable")
    directory = Path(directory_raw)
    async with asyncio.timeout(2):
        capability = await asyncio.to_thread(_read_capability, directory)
        reader, writer = await asyncio.open_unix_connection(directory / "control.sock", limit=8192)
        try:
            peer = writer.get_extra_info("socket").getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
            )
            if struct.unpack("3i", peer)[1] != os.getuid():
                raise ValueError("Private peer denied")
            frame = (
                json.dumps(
                    {"version": 1, "capability": capability, "command": command.wire()},
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
                + b"\n"
            )
            if len(frame) > 4096:
                raise ValueError("Control frame limit")
            writer.write(frame)
            await writer.drain()
            raw = await reader.readuntil(b"\n")
            if len(raw) > 8192:
                raise ValueError("Control response limit")
            reply = json.loads(
                raw, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant
            )
            if type(reply) is not dict:
                raise ValueError("Invalid control reply")
            if reply.get("ok") is not True:
                reason = reply.get("error")
                if reason in {
                    "COMMAND_CONFLICT",
                    "REVISION_CONFLICT",
                    "CONNECTION_UNAVAILABLE",
                    "NOT_FOUND",
                }:
                    raise SettingsConflict(str(reason))
                raise ValueError("Control unavailable")
            result = KeySettingsView.model_validate(reply.get("provider_settings"))
            expected = command.request.command_id
            if result.command_id != expected:
                raise ValueError("Command mismatch")
            return result
        finally:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)


async def result(command: KeySettingsControl) -> KeySettingsView | JSONResponse:
    try:
        return await settings_exchange(command)
    except SettingsConflict as conflict:
        return error_response(conflict.code, 404 if conflict.code == "NOT_FOUND" else 409)
    except (
        OSError,
        ValueError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        # A lost response never permits reconnection/resend; GET the exact command receipt.
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.get("", response_model=KeySettingsView, responses=error_responses(401, 503))
async def read_settings() -> KeySettingsView | JSONResponse:
    return await result(
        KeySettingsControl(op="provider_settings", request=ReadSettings(action="read"))
    )


@router.get(
    "/commands/{command_id}",
    response_model=KeySettingsView,
    responses=error_responses(401, 404, 422, 503),
)
async def read_command(command_id: str) -> KeySettingsView | JSONResponse:
    try:
        request = ReadSettings(action="read", command_id=command_id)
    except ValueError:
        return error_response("INVALID_INPUT", 422)
    return await result(KeySettingsControl(op="provider_settings", request=request))


@router.put(
    "", response_model=KeySettingsView, responses=error_responses(401, 404, 409, 413, 422, 503)
)
async def save_settings(
    body: Annotated[
        SaveConnection | RevokeConnection | SaveSelection, Body(discriminator="action")
    ],
    request: Request,
) -> KeySettingsView | JSONResponse:
    try:
        raw = await request.body()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Invalid JSON")
        json.loads(raw, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
        control = KeySettingsControl(op="provider_settings", request=body)
    except (ValueError, UnicodeError, RecursionError):
        return error_response("INVALID_INPUT", 422)
    return await result(control)
