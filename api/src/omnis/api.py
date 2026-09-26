"""Local, inert API process."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from omnis.core.db import ReadinessReason, database_engine, readiness_reason
from omnis.modules.instance.schemas import InstanceView
from omnis.modules.instance.service import InstanceService
from omnis.security.host_origin import LocalBoundary, error_response, local_origin
from omnis.security.routes import router as session_router


class HealthReady(BaseModel):
    api_ready: bool
    dashboard_ready: bool
    assessment_ready: bool
    reason: ReadinessReason | None


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database_url = os.environ.get("OMNIS_DATABASE_URL")
        engine = database_engine(database_url) if database_url else None
        app.state.db_engine = engine
        try:
            yield
        finally:
            app.state.db_engine = None
            if engine is not None:
                await engine.dispose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db_engine = None

    app.add_middleware(LocalBoundary, origin=local_origin())
    app.include_router(session_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        return error_response("INVALID_INPUT", 422)

    @app.exception_handler(SQLAlchemyError)
    async def database_failure(request: Request, exc: SQLAlchemyError):
        return error_response("CONTROL_UNAVAILABLE", 503)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/api/instance", response_model=InstanceView)
    async def instance() -> InstanceView:
        return InstanceView.model_validate(await InstanceService(app.state.db_engine).status())

    @app.get("/health/ready", response_model=HealthReady)
    async def ready(response: Response) -> HealthReady:
        reason = await readiness_reason(app.state.db_engine)
        if reason is not None:
            response.status_code = 503
        return HealthReady(
            api_ready=reason is None,
            dashboard_ready=False,
            assessment_ready=False,
            reason=reason,
        )

    return app
