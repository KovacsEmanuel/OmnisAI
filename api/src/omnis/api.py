"""Local, inert API process."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from starlette.responses import PlainTextResponse

from omnis.core.db import ReadinessReason, database_engine, readiness_reason


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

    @app.middleware("http")
    async def require_local_host(request: Request, call_next):
        if request.headers.getlist("host") != ["127.0.0.1:8765"]:
            return PlainTextResponse("Invalid host", status_code=400)
        return await call_next(request)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

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
