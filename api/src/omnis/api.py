"""Local, inert API process."""

from fastapi import FastAPI, Request
from starlette.responses import PlainTextResponse


def create_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def require_local_host(request: Request, call_next):
        if request.headers.getlist("host") != ["127.0.0.1:8765"]:
            return PlainTextResponse("Invalid host", status_code=400)
        return await call_next(request)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    return app
