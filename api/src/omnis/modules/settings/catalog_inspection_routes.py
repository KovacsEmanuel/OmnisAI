"""Authenticated read-only catalog inspection; no caller-supplied owner authority."""

import asyncio

from fastapi import APIRouter, Path, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.security.host_origin import error_response

from .catalog_inspection import READ_FAILURES, inspect_publication, published_page
from .catalog_inspection_models import CatalogInspection, CatalogPage

router = APIRouter(prefix="/api/v1/settings/catalog")
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


async def page(request: Request, after: str | None) -> CatalogPage | JSONResponse:
    try:
        async with asyncio.timeout(3), request.app.state.db_engine.connect() as connection:
            return await published_page(connection, after)
    except (*READ_FAILURES, SQLAlchemyError, TimeoutError, AttributeError):
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.get("", response_model=CatalogPage, responses=error_responses(401, 503))
async def current(request: Request) -> CatalogPage | JSONResponse:
    return await page(request, None)


@router.get("/page/{after}", response_model=CatalogPage, responses=error_responses(401, 422, 503))
async def next_page(
    request: Request, after: str = Path(pattern=UUID_PATTERN)
) -> CatalogPage | JSONResponse:
    return await page(request, after)


@router.get(
    "/publications/{publication_id}/{digest}",
    response_model=CatalogInspection,
    responses=error_responses(401, 422, 503),
)
async def detail(
    request: Request,
    publication_id: str = Path(pattern=UUID_PATTERN),
    digest: str = Path(pattern=r"^[0-9a-f]{64}$"),
) -> CatalogInspection | JSONResponse:
    try:
        async with asyncio.timeout(3), request.app.state.db_engine.connect() as connection:
            return await inspect_publication(connection, publication_id, digest)
    except (*READ_FAILURES, SQLAlchemyError, TimeoutError, AttributeError):
        return error_response("CONTROL_UNAVAILABLE", 503)
