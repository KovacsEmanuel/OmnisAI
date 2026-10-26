"""Paired local registry save, exact-command receive-only readback, bounded pages."""

import asyncio
import json

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.modules.settings.provider_key_routes import settings_exchange
from omnis.modules.settings.provider_key_service import SettingsConflict
from omnis.modules.settings.provider_model_models import (
    ModelRegistryControl,
    ModelRegistryView,
    ReadModels,
    SaveModels,
)
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object

router = APIRouter(prefix="/api/v1/settings/models")


async def result(request: SaveModels | ReadModels) -> ModelRegistryView | JSONResponse:
    try:
        view = await settings_exchange(ModelRegistryControl(op="provider_models", request=request))
        if (
            isinstance(request, ReadModels)
            and request.command_id is None
            and (
                view.after != request.after
                or (
                    request.registry_revision is not None
                    and view.registry_revision != request.registry_revision
                )
            )
        ):
            raise ValueError("Registry context mismatch")
        return view
    except SettingsConflict as conflict:
        return error_response(conflict.code, 404 if conflict.code == "NOT_FOUND" else 409)
    except (
        OSError,
        ValueError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        # Lost replies require the exact command GET, never an automatic resend.
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.get("", response_model=ModelRegistryView, responses=error_responses(401, 503))
async def read_models() -> ModelRegistryView | JSONResponse:
    return await result(ReadModels(action="read"))


@router.get(
    "/pages/{registry_revision}/{after}",
    response_model=ModelRegistryView,
    responses=error_responses(401, 404, 409, 422, 503),
)
async def read_page(registry_revision: str, after: str) -> ModelRegistryView | JSONResponse:
    try:
        if (
            not registry_revision.isascii()
            or not registry_revision.isdecimal()
            or str(int(registry_revision)) != registry_revision
        ):
            raise ValueError("Invalid revision")
        request = ReadModels(action="read", registry_revision=int(registry_revision), after=after)
    except ValueError:
        return error_response("INVALID_INPUT", 422)
    return await result(request)


@router.get(
    "/commands/{command_id}",
    response_model=ModelRegistryView,
    responses=error_responses(401, 404, 422, 503),
)
async def read_command(command_id: str) -> ModelRegistryView | JSONResponse:
    try:
        request = ReadModels(action="read", command_id=command_id)
    except ValueError:
        return error_response("INVALID_INPUT", 422)
    return await result(request)


@router.put(
    "", response_model=ModelRegistryView, responses=error_responses(401, 404, 409, 413, 422, 503)
)
async def save_models(body: SaveModels, request: Request) -> ModelRegistryView | JSONResponse:
    try:
        raw = await request.body()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Invalid JSON")
        json.loads(raw, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
    except (ValueError, UnicodeError, RecursionError):
        return error_response("INVALID_INPUT", 422)
    return await result(body)
