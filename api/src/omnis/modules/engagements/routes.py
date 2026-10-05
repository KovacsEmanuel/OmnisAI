"""Same-origin authenticated engagement draft routes; no assessment effects."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Query, Request
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses
from omnis.modules.engagements.schemas import EngagementDraft, EngagementPage, EngagementView
from omnis.modules.engagements.service import EngagementNotFound, EngagementService
from omnis.security.host_origin import error_response

router = APIRouter(prefix="/api/v1/engagements")


@router.post(
    "",
    status_code=201,
    response_model=EngagementView,
    responses=error_responses(401, 413, 422, 503),
)
async def create_engagement(body: EngagementDraft, request: Request) -> EngagementView:
    async with asyncio.timeout(3):
        return await EngagementService(request.app.state.db_engine).create(body)


@router.get("", response_model=EngagementPage, responses=error_responses(401, 422, 503))
async def list_engagements(
    request: Request, limit: int = Query(default=20, ge=1, le=50), after: UUID | None = None
) -> EngagementPage:
    async with asyncio.timeout(3):
        return await EngagementService(request.app.state.db_engine).list_page(limit, after)


@router.get(
    "/{engagement_id}", response_model=EngagementView, responses=error_responses(401, 404, 422, 503)
)
async def read_engagement(engagement_id: UUID, request: Request) -> EngagementView | JSONResponse:
    try:
        async with asyncio.timeout(3):
            return await EngagementService(request.app.state.db_engine).read(engagement_id)
    except EngagementNotFound:
        return error_response("NOT_FOUND", 404)
