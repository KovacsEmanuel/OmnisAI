"""Authenticated public projection; only the existing supervisor can admit a test."""

import asyncio
import json
import os
import socket
import struct
from contextlib import suppress
from pathlib import Path

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.modules.instance.schemas import MODEL_TEST_PREPARE_WAIT_SECONDS, ControlRequest
from omnis.modules.runs.model_test_contract import ModelTestView
from omnis.modules.runs.model_test_models import (
    CancelTestRequest,
    ModelTestControl,
    ModelTestRequest,
    RefreshRequest,
)
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.settings.provider_key_models import Identity
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object
from omnis.transport.control_probe import _read_capability

router = APIRouter(prefix="/api/v1/model-test")


async def control_exchange(command: ModelTestControl) -> dict[str, object]:
    raw = os.environ.get("OMNIS_CONTROL_DIR")
    if not raw:
        raise ValueError("Control unavailable")
    directory = Path(raw)
    wait = MODEL_TEST_PREPARE_WAIT_SECONDS + 2 if command.action == "provision" else 4
    async with asyncio.timeout(wait):
        capability = await asyncio.to_thread(_read_capability, directory)
        reader, writer = await asyncio.open_unix_connection(directory / "control.sock", limit=65536)
        try:
            peer = writer.get_extra_info("socket").getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
            )
            if struct.unpack("3i", peer)[1] != os.getuid():
                raise ValueError("Control denied")
            envelope = ControlRequest(version=1, capability=capability, command=command)
            frame = envelope.model_dump_json().encode() + b"\n"
            if len(frame) > 4096:
                raise ValueError("Control limit")
            writer.write(frame)
            await writer.drain()
            response = json.loads(
                await reader.readuntil(b"\n"),
                object_pairs_hook=unique_json_object,
                parse_constant=reject_json_constant,
            )
            if not isinstance(response, dict):
                raise ValueError("Control unavailable")
            if response.get("ok") is not True:
                code = response.get("error")
                allowed = {
                    "COMMAND_CONFLICT",
                    "REVISION_CONFLICT",
                    "CAPABILITIES_REQUIRED",
                    "OPERATION_ACTIVE",
                    "NOT_FOUND",
                    "OPERATION_FINISHED",
                }
                if isinstance(code, str) and code in allowed:
                    raise ModelConflict(code)
                raise ValueError("Control unavailable")
            if command.action == "provision":
                if response.get("model_test") != {"status": "PREPARED_RESTART_REQUIRED"}:
                    raise ValueError("Invalid provisioning result")
                return {"status": "PREPARED_RESTART_REQUIRED"}
            result = ModelTestView.model_validate(response.get("model_test"))
            if command.operation_id is not None and result.operation_id != command.operation_id:
                raise ValueError("Operation mismatch")
            return result.model_dump(mode="json")
        finally:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)


async def result(command: ModelTestControl, request: Request) -> ModelTestView | JSONResponse:
    try:
        return ModelTestView.model_validate(await control_exchange(command))
    except ModelConflict as error:
        return error_response(error.code, 404 if error.code == "NOT_FOUND" else 409)
    except (
        OSError,
        ValueError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        # A missing mutation response never permits an automatic repeat.
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.get(
    "",
    response_model=ModelTestView,
    responses=error_responses(401, 404, 422, 503),
)
async def read_model_test(request: Request) -> ModelTestView | JSONResponse:
    return await result(ModelTestControl(op="model_test", action="read"), request)


@router.get(
    "/{operation_id}", response_model=ModelTestView, responses=error_responses(401, 404, 422, 503)
)
async def read_operation(operation_id: Identity, request: Request) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(op="model_test", action="read", operation_id=operation_id), request
    )


@router.post(
    "/capabilities",
    response_model=ModelTestView,
    status_code=202,
    responses=error_responses(401, 409, 422, 503),
)
async def refresh_capabilities(
    body: RefreshRequest, request: Request
) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(
            op="model_test",
            action="refresh",
            command_id=body.command_id,
            expected_selection_revision=body.expected_selection_revision,
        ),
        request,
    )


@router.post(
    "/{operation_id}/cancel",
    response_model=ModelTestView,
    status_code=202,
    responses=error_responses(401, 404, 409, 422, 503),
)
async def cancel_operation(
    operation_id: Identity, body: CancelTestRequest, request: Request
) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(
            op="model_test",
            action="cancel",
            operation_id=operation_id,
            command_id=body.command_id,
            expected_state_revision=body.expected_state_revision,
        ),
        request,
    )


@router.put(
    "",
    response_model=ModelTestView,
    status_code=202,
    responses=error_responses(401, 404, 409, 413, 422, 503),
)
async def start_model_test(
    body: ModelTestRequest,
    request: Request,
) -> ModelTestView | JSONResponse:
    try:
        json.loads(
            await request.body(),
            object_pairs_hook=unique_json_object,
            parse_constant=reject_json_constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        return error_response("INVALID_INPUT", 422)
    return await result(
        ModelTestControl(
            op="model_test",
            action="start",
            operation_id=body.operation_id,
            expected_selection_revision=body.expected_selection_revision,
            consent=body.consent,
        ),
        request,
    )
