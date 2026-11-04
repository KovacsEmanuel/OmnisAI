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
from omnis.modules.instance.schemas import (
    MODEL_TEST_PREPARE_WAIT_SECONDS,
    ControlRequest,
)
from omnis.modules.runs.model_test_contract import EntryTestView, ModelTestView
from omnis.modules.runs.model_test_models import (
    CancelTestRequest,
    EntryTestRequest,
    ModelTestControl,
    ModelTestRequest,
    RefreshRequest,
)
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.runs.run_contract import CommandReceipt, RunControl
from omnis.modules.settings.provider_catalog_models import CatalogControl, CatalogView
from omnis.modules.settings.provider_key_models import Identity
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object
from omnis.transport.control_probe import _read_capability

router = APIRouter(prefix="/api/v1/model-test")


async def control_exchange(
    command: ModelTestControl | CatalogControl | RunControl,
) -> dict[str, object]:
    raw = os.environ.get("OMNIS_CONTROL_DIR")
    if not raw:
        raise ValueError("Control unavailable")
    directory = Path(raw)
    wait = (
        MODEL_TEST_PREPARE_WAIT_SECONDS + 2
        if isinstance(command, ModelTestControl) and command.action == "provision"
        else 4
    )
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
                if (
                    code == "GENERATION_CONFLICT"
                    and isinstance(command, ModelTestControl)
                    and command.op == "entry_model_test"
                    and command.action == "start"
                ):
                    raise ModelConflict("REVISION_CONFLICT")
                allowed = {
                    "COMMAND_CONFLICT",
                    "REVISION_CONFLICT",
                    "CAPABILITIES_REQUIRED",
                    "OPERATION_ACTIVE",
                    "NOT_FOUND",
                    "OPERATION_FINISHED",
                    "CONNECTION_UNAVAILABLE",
                    "AUTHORITY_DENIED",
                    "ANSWER_DENIED",
                    "REF_UNAVAILABLE",
                    "GENERATION_CONFLICT",
                }
                if isinstance(command, RunControl):
                    allowed.update({"MODEL_NOT_REGISTERED", "DATA_DENIED"})
                if isinstance(code, str) and code in allowed:
                    raise ModelConflict(code)
                raise ValueError("Control unavailable")
            if isinstance(command, RunControl):
                run_receipt = CommandReceipt.model_validate(response.get("agent_run"))
                if run_receipt.command_id != command.request.command_id:
                    raise ValueError("Command mismatch")
                return run_receipt.model_dump(mode="json")
            if isinstance(command, CatalogControl):
                return CatalogView.model_validate(response.get("provider_catalog")).model_dump(
                    mode="json"
                )
            if command.action == "provision":
                if response.get("model_test") != {"status": "PREPARED_RESTART_REQUIRED"}:
                    raise ValueError("Invalid provisioning result")
                return {"status": "PREPARED_RESTART_REQUIRED"}
            if command.op == "entry_model_test":
                exact = EntryTestView.model_validate(response.get("entry_model_test"))
                if (
                    command.operation_id is not None and exact.operation_id != command.operation_id
                ) or (command.entry_id is not None and exact.entry_id != command.entry_id):
                    raise ValueError("Entry or operation mismatch")
                return exact.model_dump(mode="json")
            result = ModelTestView.model_validate(response.get("model_test"))
            if (
                command.action in {"read", "refresh"}
                and command.command_id is not None
                and result.metadata_command_id != command.command_id
            ):
                raise ValueError("Metadata command mismatch")
            if command.operation_id is not None and result.operation_id != command.operation_id:
                raise ValueError("Operation mismatch")
            return result.model_dump(mode="json")
        finally:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)


async def result(command: ModelTestControl, request: Request) -> ModelTestView | JSONResponse:
    if command.action in {"start", "refresh", "cancel"}:
        try:
            json.loads(
                await request.body(),
                object_pairs_hook=unique_json_object,
                parse_constant=reject_json_constant,
            )
        except (ValueError, UnicodeError, RecursionError):
            return error_response("INVALID_INPUT", 422)
    try:
        raw = await control_exchange(command)
        if command.op == "entry_model_test":
            exact = EntryTestView.model_validate(raw)
            if (
                (command.operation_id is not None and exact.operation_id != command.operation_id)
                or (command.entry_id is not None and exact.entry_id != command.entry_id)
                or (
                    command.action == "start"
                    and (
                        exact.entry_id != command.entry_id
                        or exact.entry_revision != command.expected_entry_revision
                        or exact.connection_revision != command.expected_connection_revision
                    )
                )
            ):
                raise ValueError("Exact test context mismatch")
            return exact
        return ModelTestView.model_validate(raw)
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
    "/capabilities/{command_id}",
    response_model=ModelTestView,
    responses=error_responses(401, 404, 422, 503),
)
async def read_capabilities(command_id: Identity, request: Request) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(op="model_test", action="read", command_id=command_id), request
    )


@router.put(
    "/entries",
    response_model=EntryTestView,
    status_code=202,
    responses=error_responses(401, 404, 409, 422, 503),
)
async def start_entry_test(
    body: EntryTestRequest, request: Request
) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl.model_validate(
            {"op": "entry_model_test", "action": "start", **body.model_dump()}
        ),
        request,
    )


@router.get(
    "/entries/latest/{entry_id}",
    response_model=EntryTestView,
    responses=error_responses(401, 404, 422, 503),
)
async def read_latest_entry_test(
    entry_id: Identity, request: Request
) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(op="entry_model_test", action="read", entry_id=entry_id), request
    )


@router.get(
    "/entries/{operation_id}",
    response_model=EntryTestView,
    responses=error_responses(401, 404, 422, 503),
)
async def read_entry_test(operation_id: Identity, request: Request) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(op="entry_model_test", action="read", operation_id=operation_id), request
    )


@router.post(
    "/entries/{operation_id}/cancel",
    response_model=EntryTestView,
    status_code=202,
    responses=error_responses(401, 404, 409, 422, 503),
)
async def cancel_entry_test(
    operation_id: Identity, body: CancelTestRequest, request: Request
) -> ModelTestView | JSONResponse:
    return await result(
        ModelTestControl(
            op="entry_model_test",
            action="cancel",
            operation_id=operation_id,
            command_id=body.command_id,
            expected_state_revision=body.expected_state_revision,
        ),
        request,
    )


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
