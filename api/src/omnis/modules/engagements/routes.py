"""Same-origin authenticated engagement draft routes; no assessment effects."""

import asyncio
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from starlette.responses import JSONResponse

from omnis.core.errors import FieldError, error_responses
from omnis.modules.engagements.schemas import (
    EngagementDraft,
    EngagementPage,
    EngagementView,
    RevisionPage,
)
from omnis.modules.engagements.service import (
    EngagementConflict,
    EngagementNotFound,
    EngagementService,
)
from omnis.security.host_origin import error_response

router = APIRouter(prefix="/api/v1/engagements")
ETAG_PATTERN = r'^"rev-([1-9][0-9]*)-([0-9a-f]{64})"$'
COMMAND_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def etag(view: EngagementView) -> str:
    return f'"rev-{view.revision}-{view.digest}"'


@router.post(
    "",
    status_code=201,
    response_model=EngagementView,
    responses=error_responses(401, 413, 422, 503),
)
async def create_engagement(
    body: EngagementDraft, request: Request, response: Response
) -> EngagementView:
    async with asyncio.timeout(3):
        view = await EngagementService(request.app.state.db_engine).create(body)
    response.headers["ETag"] = etag(view)
    return view


@router.get("", response_model=EngagementPage, responses=error_responses(401, 422, 503))
async def list_engagements(
    request: Request, limit: int = Query(default=20, ge=1, le=50), after: UUID | None = None
) -> EngagementPage:
    async with asyncio.timeout(3):
        return await EngagementService(request.app.state.db_engine).list_page(limit, after)


@router.get(
    "/{engagement_id}", response_model=EngagementView, responses=error_responses(401, 404, 422, 503)
)
async def read_engagement(
    engagement_id: UUID, request: Request, response: Response
) -> EngagementView | JSONResponse:
    try:
        async with asyncio.timeout(3):
            view = await EngagementService(request.app.state.db_engine).read(engagement_id)
        response.headers["ETag"] = etag(view)
        return view
    except EngagementNotFound:
        return error_response("NOT_FOUND", 404)


@router.get(
    "/{engagement_id}/revisions",
    response_model=RevisionPage,
    responses=error_responses(401, 404, 422, 503),
)
async def list_revisions(
    engagement_id: UUID,
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    after: int | None = Query(default=None, ge=1, le=2147483647),
) -> RevisionPage | JSONResponse:
    try:
        async with asyncio.timeout(3):
            return await EngagementService(request.app.state.db_engine).revision_page(
                engagement_id, limit, after
            )
    except EngagementNotFound:
        return error_response("NOT_FOUND", 404)


@router.put(
    "/{engagement_id}",
    response_model=EngagementView,
    responses=error_responses(401, 404, 409, 413, 422, 503),
)
async def edit_engagement(
    engagement_id: UUID,
    body: EngagementDraft,
    request: Request,
    response: Response,
    if_match: Annotated[
        str,
        Header(
            pattern=ETAG_PATTERN,
            max_length=83,
            description='Exact strong ETag: "rev-<positive decimal revision>-<64 lowercase hex digest>"',
        ),
    ],
    x_command_id: Annotated[
        str,
        Header(
            pattern=COMMAND_PATTERN,
            max_length=36,
            description="Explicit canonical lowercase UUID, unique per engagement edit command",
        ),
    ],
) -> EngagementView | JSONResponse:
    if (
        len(request.headers.getlist("if-match")) != 1
        or len(request.headers.getlist("x-command-id")) != 1
    ):
        return error_response(
            "INVALID_INPUT",
            422,
            field_errors=[
                FieldError(field="if-match", code="INVALID_VALUE"),
                FieldError(field="x-command-id", code="INVALID_VALUE"),
            ],
        )
    match = re.fullmatch(ETAG_PATTERN, if_match)
    if match is None or int(match[1]) >= 2147483647 or str(UUID(x_command_id)) != x_command_id:
        return error_response("INVALID_INPUT", 422)
    try:
        async with asyncio.timeout(3):
            view = await EngagementService(request.app.state.db_engine).edit(
                engagement_id, int(match[1]), match[2], UUID(x_command_id), body
            )
        response.headers["ETag"] = etag(view)
        return view
    except EngagementNotFound:
        return error_response("NOT_FOUND", 404)
    except EngagementConflict:
        return error_response("ENGAGEMENT_CONFLICT", 409)
