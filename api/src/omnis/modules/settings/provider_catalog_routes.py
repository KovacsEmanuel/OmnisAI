"""POST search is local-only and inherits the unchanged session/CSRF boundary."""

import asyncio
import json

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.modules.runs.model_test_routes import control_exchange
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.settings.provider_catalog_models import (
    CancelCatalog,
    CatalogControl,
    CatalogView,
    RefreshCatalog,
    SearchCatalog,
)
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object

router = APIRouter(prefix="/api/v1/settings/provider-catalog")


async def result(
    body: RefreshCatalog | SearchCatalog | CancelCatalog, request: Request
) -> CatalogView | JSONResponse:
    try:
        json.loads(
            await request.body(),
            object_pairs_hook=unique_json_object,
            parse_constant=reject_json_constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        return error_response("INVALID_INPUT", 422)
    try:
        view = CatalogView.model_validate(
            await control_exchange(CatalogControl(op="provider_catalog", request=body))
        )
        expected = body.command_id if isinstance(body, RefreshCatalog) else body.catalog_command_id
        if (
            view.connection_id != body.connection_id
            or view.connection_revision != body.connection_revision
            or (expected is not None and view.catalog_command_id != expected)
        ):
            raise ValueError("Catalog context mismatch")
        if isinstance(body, SearchCatalog) and (
            view.query != body.query or view.offset != body.offset
        ):
            raise ValueError("Search context mismatch")
        return view
    except ModelConflict as error:
        return error_response(error.code, 404 if error.code == "NOT_FOUND" else 409)
    except (
        OSError,
        ValueError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.post(
    "/search", response_model=CatalogView, responses=error_responses(401, 404, 409, 422, 503)
)
async def search_catalog(body: SearchCatalog, request: Request) -> CatalogView | JSONResponse:
    return await result(body, request)


@router.post(
    "/refresh",
    response_model=CatalogView,
    status_code=202,
    responses=error_responses(401, 409, 422, 503),
)
async def refresh_catalog(body: RefreshCatalog, request: Request) -> CatalogView | JSONResponse:
    return await result(body, request)


@router.post(
    "/cancel",
    response_model=CatalogView,
    status_code=202,
    responses=error_responses(401, 404, 409, 422, 503),
)
async def cancel_catalog(body: CancelCatalog, request: Request) -> CatalogView | JSONResponse:
    return await result(body, request)
