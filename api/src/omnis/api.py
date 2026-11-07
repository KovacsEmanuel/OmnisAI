"""Local, inert API process."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from omnis.core.db import ReadinessReason, database_engine, readiness_reason
from omnis.core.errors import error_responses, validation_field_errors
from omnis.core.readiness import DashboardReason, dashboard_reason
from omnis.core.web_assets import CONTENT_TYPES, WEB_HEADERS, WebAssets
from omnis.modules.engagements.routes import dashboard_router
from omnis.modules.diagnostics.routes import router as diagnostics_router
from omnis.modules.diagnostics.service import DiagnosticSink
from omnis.modules.engagements.routes import router as engagement_router
from omnis.modules.instance.schemas import InstanceView
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.model_test_routes import router as model_test_router
from omnis.modules.runs.run_routes import router as run_router
from omnis.modules.settings.catalog_inspection_routes import router as catalog_inspection_router
from omnis.modules.settings.provider_catalog_routes import router as provider_catalog_router
from omnis.modules.settings.provider_key_routes import router as provider_key_router
from omnis.modules.settings.provider_model_routes import router as provider_model_router
from omnis.modules.settings.provider_routes import router as provider_router
from omnis.security.host_origin import LocalBoundary, error_response, local_origin
from omnis.security.routes import router as session_router


class HealthReady(BaseModel):
    api_ready: bool
    dashboard_ready: bool
    assessment_ready: bool
    reason: ReadinessReason | None
    dashboard_reason: ReadinessReason | DashboardReason | None


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database_url = os.environ.get("OMNIS_DATABASE_URL")
        engine = database_engine(database_url) if database_url else None
        app.state.db_engine = engine
        try:
            yield
        finally:
            app.state.db_engine = None
            if engine is not None:
                await engine.dispose()

    app = FastAPI(
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        responses=error_responses(400, 403, 500),
    )
    app.state.db_engine = None
    web_assets = WebAssets(os.environ.get("OMNIS_WEB_ROOT"))
    app.state.ui_diagnostics = DiagnosticSink()
    control_root = os.environ.get("OMNIS_CONTROL_DIR")
    control_directory = Path(control_root) if control_root else None

    app.add_middleware(LocalBoundary, origin=local_origin())
    app.include_router(session_router)
    app.include_router(diagnostics_router)
    app.include_router(engagement_router)
    app.include_router(dashboard_router)
    app.include_router(provider_router)
    app.include_router(provider_key_router)
    app.include_router(provider_model_router)
    app.include_router(provider_catalog_router)
    app.include_router(model_test_router)
    app.include_router(run_router)
    app.include_router(catalog_inspection_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.startswith("/api/v1/engagements"):
            return error_response(
                "INVALID_INPUT", 422, field_errors=validation_field_errors(exc.errors())
            )
        return error_response("INVALID_INPUT", 422)

    @app.exception_handler(HTTPException)
    async def http_failure(request: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        response = error_response(code, exc.status_code)
        if exc.status_code == 405 and exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_failure(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return error_response("CONTROL_UNAVAILABLE", 503)

    @app.exception_handler(TimeoutError)
    async def operation_timeout(request: Request, exc: TimeoutError) -> JSONResponse:
        return error_response("CONTROL_TIMEOUT", 503)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/api/instance", response_model=InstanceView, responses=error_responses(401, 503))
    async def instance() -> InstanceView:
        async with asyncio.timeout(3):
            status = await InstanceService(app.state.db_engine).status()
            view = InstanceView.model_validate(status)
            view.dashboard_ready = (
                await dashboard_reason(web_assets, control_directory, status) is None
            )
            return view

    @app.get(
        "/health/ready",
        response_model=HealthReady,
        responses={503: {"model": HealthReady, "description": "Database or schema unavailable"}},
    )
    async def ready(response: Response) -> HealthReady:
        reason = await readiness_reason(app.state.db_engine)
        dashboard_failure: ReadinessReason | DashboardReason | None = reason
        if reason is None:
            try:
                async with asyncio.timeout(3):
                    status = await InstanceService(app.state.db_engine).status()
                dashboard_failure = await dashboard_reason(web_assets, control_directory, status)
            except (SQLAlchemyError, TimeoutError):
                reason = ReadinessReason.DATABASE_UNAVAILABLE
                dashboard_failure = reason
        if reason is not None:
            response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return HealthReady(
            api_ready=reason is None,
            dashboard_ready=dashboard_failure is None,
            assessment_ready=False,
            reason=reason,
            dashboard_reason=dashboard_failure,
        )

    async def serve_asset(name: str) -> Response:
        files = await web_assets.read()
        if files is None:
            return error_response("WEB_UNAVAILABLE", 503)
        content = files.get(name)
        if content is None:
            return error_response("NOT_FOUND", 404)
        return Response(content, media_type=CONTENT_TYPES[Path(name).suffix], headers=WEB_HEADERS)

    @app.get("/", include_in_schema=False)
    @app.get("/pair", include_in_schema=False)
    @app.get("/engagements", include_in_schema=False)
    @app.get("/engagements/new", include_in_schema=False)
    @app.get("/settings/providers", include_in_schema=False)
    @app.get("/settings/skills", include_in_schema=False)
    @app.get("/settings/runtime", include_in_schema=False)
    @app.get("/settings/data", include_in_schema=False)
    async def web_index() -> Response:
        return await serve_asset("index.html")

    @app.get("/engagements/{engagement_id:uuid}/overview", include_in_schema=False)
    @app.get("/engagements/{engagement_id:uuid}/setup", include_in_schema=False)
    @app.get("/engagements/{engagement_id:uuid}/stream", include_in_schema=False)
    @app.get("/engagements/{engagement_id:uuid}/findings", include_in_schema=False)
    @app.get("/engagements/{engagement_id:uuid}/coverage", include_in_schema=False)
    @app.get("/engagements/{engagement_id:uuid}/reports", include_in_schema=False)
    async def web_engagement() -> Response:
        # Shell only; private engagement data still requires the API session.
        return await serve_asset("index.html")

    @app.get("/assets/{name}", include_in_schema=False)
    async def web_asset(name: str) -> Response:
        return await serve_asset(f"assets/{name}")

    return app
