"""Authenticated bounded Settings caller of the existing local supervisor owner."""

import asyncio
import json
import os
import socket
import struct
from contextlib import suppress
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.settings.provider_models import ProviderCommand, ProviderView, SettingsControl
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object
from omnis.transport.control_probe import _read_capability

router = APIRouter(prefix="/api/v1/settings/provider")


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ok: Literal[True]
    settings: ProviderView
    correlation_id: UUID


async def settings_exchange(command: SettingsControl) -> ProviderView:
    raw_directory = os.environ.get("OMNIS_CONTROL_DIR")
    if not raw_directory:
        raise ValueError("Settings control unavailable")
    directory = Path(raw_directory)
    async with asyncio.timeout(2):
        capability = await asyncio.to_thread(_read_capability, directory)
        reader, writer = await asyncio.open_unix_connection(directory / "control.sock", limit=4096)
        try:
            peer = writer.get_extra_info("socket").getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
            )
            if struct.unpack("3i", peer)[1] != os.getuid():
                raise ValueError("Settings control denied")
            envelope = ControlRequest(version=1, capability=capability, command=command)
            frame = envelope.model_dump_json().encode() + b"\n"
            if len(frame) > 4096:
                raise ValueError("Settings control limit")
            writer.write(frame)
            await writer.drain()
            raw = await reader.readuntil(b"\n")
            if len(raw) > 4096:
                raise ValueError("Settings response limit")
            result = _Reply.model_validate_json(raw).settings
            if result.operation_id != command.operation_id:
                raise ValueError("Settings response mismatch")
            return result
        finally:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)


async def _result(command: SettingsControl) -> ProviderView | JSONResponse:
    try:
        return await settings_exchange(command)
    except (
        ValueError,
        OSError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        # A lost mutation response is indeterminate; never reconnect/resend.
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.put("", response_model=ProviderView, responses=error_responses(401, 413, 422, 503))
async def configure(body: ProviderCommand, request: Request) -> ProviderView | JSONResponse:
    try:
        raw = (await request.body()).decode("utf-8")
        if raw.startswith("\ufeff"):
            raise ValueError("Invalid encoding")
        json.loads(raw, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
    except (ValueError, UnicodeError, RecursionError):
        return error_response("INVALID_INPUT", 422)
    return await _result(
        SettingsControl(op="settings", command=body, operation_id=body.operation_id)
    )


@router.get(
    "/operations/{operation_id}",
    response_model=ProviderView,
    responses=error_responses(401, 422, 503),
)
async def operation(operation_id: str) -> ProviderView | JSONResponse:
    try:
        command = SettingsControl(op="settings", command=None, operation_id=operation_id)
    except ValueError:
        return error_response("INVALID_INPUT", 422)
    return await _result(command)
