"""Normal authenticated run commands and receive-only readback."""

import asyncio
import json

from fastapi import APIRouter, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from omnis.modules.runs import projections
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_routes import control_exchange
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.runs.run_contract import (
    Attempt,
    CommandReceipt,
    EventPage,
    Preflight,
    RunCommand,
    RunControl,
    RunSummary,
    RunView,
    StartRun,
)
from omnis.modules.settings import catalog_inspection
from omnis.modules.settings.catalog_models import ExactRef
from omnis.modules.settings.provider_key_models import Identity
from omnis.security.host_origin import error_response, reject_json_constant, unique_json_object

router = APIRouter(prefix="/api/v1")


async def mutate(
    request: Request, body: Preflight | StartRun | RunCommand
) -> CommandReceipt | JSONResponse:
    try:
        raw = await request.body()
        if len(raw) > 4096:
            return error_response("INVALID_INPUT", 422)
        json.loads(raw, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
        command = RunControl(op="agent_run", request=body)
    except ValueError:
        return error_response("INVALID_INPUT", 422)
    try:
        return CommandReceipt.model_validate(await control_exchange(command))
    except ModelConflict as error:
        return error_response(error.code, 404 if error.code == "NOT_FOUND" else 409)
    except (
        ValueError,
        OSError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.post("/engagements/{engagement_id}/run-preflight", response_model=CommandReceipt)
async def preflight(
    engagement_id: Identity, body: Preflight, request: Request
) -> CommandReceipt | JSONResponse:
    if body.engagement_id != engagement_id:
        return error_response("INVALID_INPUT", 422)
    return await mutate(request, body)


@router.post("/runs", response_model=CommandReceipt, status_code=202)
async def start(body: StartRun, request: Request) -> CommandReceipt | JSONResponse:
    return await mutate(request, body)


@router.post("/runs/{run_id}/commands", response_model=CommandReceipt, status_code=202)
async def command(
    run_id: Identity, body: RunCommand, request: Request
) -> CommandReceipt | JSONResponse:
    if body.run_id != run_id:
        return error_response("INVALID_INPUT", 422)
    return await mutate(request, body)


@router.get("/runs/commands/{command_id}", response_model=CommandReceipt)
async def command_read(command_id: Identity, request: Request) -> CommandReceipt | JSONResponse:
    async with request.app.state.db_engine.connect() as db:
        instance = str(await db.scalar(text("SELECT instance_id FROM instance_control WHERE id=1")))
        receipt = await store.replay(db, instance, command_id)
    return receipt if receipt else error_response("NOT_FOUND", 404)


@router.get("/runs/publications", response_model=list[ExactRef])
async def publications(request: Request) -> list[ExactRef] | JSONResponse:
    try:
        async with asyncio.timeout(3), request.app.state.db_engine.connect() as db:
            page = await catalog_inspection.published_page(db, None)
            # This compact selector has no cursor; do not present a partial list as complete.
            if page.has_more:
                return error_response("CATALOG_LIST_LIMIT", 409)
            result = []
            for entry in page.items:
                reference = entry.publication_ref
                core = await db.scalar(
                    text(
                        "SELECT 1 FROM catalog_record p JOIN catalog_record r ON r.owner_id=p.owner_id AND r.id::text=p.envelope#>>'{payload,technical_review_ref,id}' AND r.digest=p.envelope#>>'{payload,technical_review_ref,digest}' WHERE p.id=:id AND p.digest=:digest AND p.kind='catalog-publication' AND r.kind='technical-review' AND r.envelope#>>'{payload,resolved_index,catalog_schema_version}'='2'"
                    ),
                    {"id": reference.id, "digest": reference.digest},
                )
                if core:
                    result.append(ExactRef.model_validate(reference.model_dump()))
            return result
    except (*catalog_inspection.READ_FAILURES, SQLAlchemyError, TimeoutError):
        return error_response("CONTROL_UNAVAILABLE", 503)


@router.get("/runs/active", response_model=RunView | None)
async def active(request: Request) -> RunView | None:
    async with request.app.state.db_engine.connect() as db:
        row = await db.scalar(
            text(
                "SELECT payload FROM agent_run WHERE instance_id=(SELECT instance_id FROM instance_control WHERE id=1) AND state NOT IN ('STOPPED','COMPLETED','LIMITED')"
            )
        )
        return RunView.model_validate_json(json.dumps(row)) if row is not None else None


@router.get("/engagements/{engagement_id}/run", response_model=RunView | None)
async def engagement_run(engagement_id: Identity, request: Request) -> RunView | None:
    async with request.app.state.db_engine.connect() as db:
        row = await db.scalar(
            text(
                "SELECT r.payload FROM agent_run r JOIN run_event e ON e.instance_id=r.instance_id AND e.run_id=r.run_id WHERE r.instance_id=(SELECT instance_id FROM instance_control WHERE id=1) AND r.engagement_id=:id ORDER BY e.sequence DESC LIMIT 1"
            ),
            {"id": engagement_id},
        )
        return RunView.model_validate_json(json.dumps(row)) if row is not None else None


@router.get("/runs/{run_id}/summary", response_model=RunSummary)
async def summary(
    run_id: Identity, request: Request, limit: int = Query(default=20, ge=1, le=50)
) -> RunSummary | JSONResponse:
    try:
        return await projections.summary(request.app.state.db_engine, run_id, limit)
    except ModelConflict as error:
        return error_response(error.code, 404)


@router.get("/runs/{run_id}/events", response_model=EventPage)
async def events(
    run_id: Identity,
    request: Request,
    after: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=50),
) -> EventPage | JSONResponse:
    try:
        return await projections.events(request.app.state.db_engine, run_id, after, limit)
    except ModelConflict as error:
        return error_response(error.code, 404 if error.code == "NOT_FOUND" else 422)


@router.get("/runs/{run_id}/attempts/{attempt_id}", response_model=Attempt)
async def attempt(
    run_id: Identity, attempt_id: Identity, request: Request
) -> Attempt | JSONResponse:
    try:
        async with request.app.state.db_engine.connect() as connection:
            db = await connection.execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            )
            async with db.begin():
                run = await projections.read_run(db, run_id)
                result = await store.attempt(db, run, attempt_id)
                if len(result.model_dump_json().encode()) > 65536:
                    raise ModelConflict("PROJECTION_LIMIT")
                return result
    except ModelConflict as error:
        return error_response(error.code, 404 if error.code == "NOT_FOUND" else 422)
