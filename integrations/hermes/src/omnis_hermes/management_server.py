"""Opt-in native management-only serve path; native config remains the store.

This replaces only the broad dashboard boot for the exact private serve command.
No stock session/gateway/rooms/cron/discovery/auth bootstrap is imported here.
The narrowed native /api/config never exports the raw configuration.
"""

import asyncio
import hmac
import importlib
import json
import os
import socket
import sys
from collections.abc import Awaitable, Callable

from .management_contract import SELECTION, selection
from .native_preparation_contract import loads


def saved_selection(config: object) -> dict[str, object] | None:
    if type(config) is not dict:
        raise ValueError("Invalid native config")
    if not config:
        return None
    # Pinned config.py _canonicalize_config/save_config(strip_defaults=False)
    # adds no metadata/defaults to this exact sparse shape. In particular it
    # does not add _config_version; do not adopt arbitrary preexisting metadata.
    if set(config) != {"model", "agent", "auth"}:
        raise ValueError("Foreign native config fields")
    model = config["model"]
    agent, auth = config.get("agent"), config.get("auth")
    if (
        type(model) is not dict
        or set(model) != {"provider", "default"}
        or type(agent) is not dict
        or type(auth) is not dict
        or set(agent) != {"reasoning_effort", "reasoning_overrides"}
        or set(auth) != {"adopt_external_logins"}
        or auth.get("adopt_external_logins") is not False
        or type(agent.get("reasoning_overrides")) is not dict
        or any(type(value) is not str for value in model.values())
        or type(agent.get("reasoning_effort")) is not str
        or any(
            type(key) is not str or type(value) is not str
            for key, value in agent["reasoning_overrides"].items()
        )
        or agent.get("reasoning_overrides") != {"gpt-6.1-sol": "xhigh"}
    ):
        raise ValueError("Foreign or incomplete native config")
    return selection(
        {
            "provider": model["provider"],
            "model": model["default"],
            "effort": agent.get("reasoning_effort"),
        }
    )


def config_operation(method: str, payload: object) -> object:
    if method not in {"GET", "PUT"}:
        raise ValueError("Invalid config method")
    # Native import occurs only in the isolated native child, never in the API/Host.
    native = importlib.import_module("hermes_cli.config")
    read: object = getattr(native, "require_readable_config_before_write", None)
    save: object = getattr(native, "save_config", None)
    if not callable(read) or not callable(save):
        raise ValueError("Pinned native configuration API missing")
    existing: object = read()
    saved_selection(existing)
    if method == "PUT":
        expected = {
            "config": {
                "model": {"provider": "openai-codex", "default": "gpt-6.1-sol"},
                "agent": {
                    "reasoning_effort": "xhigh",
                    "reasoning_overrides": {"gpt-6.1-sol": "xhigh"},
                },
                "auth": {"adopt_external_logins": False},
            }
        }
        if json.dumps(payload, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError("Invalid config write")
        # The native writer owns locking/atomic replacement/cache invalidation.
        # Preserve explicit defaults so the exact requested effort is readable.
        save(expected["config"], strip_defaults=False, merge_existing=True)
        if saved_selection(read()) != SELECTION:
            raise ValueError("Native readback mismatch")
        return {"ok": True}
    return saved_selection(existing)


def main() -> int:
    if (
        sys.argv[1:] != ["serve", "--isolated", "--host", "127.0.0.1", "--port", "0"]
        or os.environ.get("HERMES_OMNIS_MANAGEMENT") != "1"
        or os.environ.get("HERMES_HOME") != "/state/provider"
    ):
        return 3
    token = os.environ.get("HERMES_DASHBOARD_SESSION_TOKEN", "")
    if len(token) != 64:
        return 3
    import uvicorn
    from fastapi import FastAPI, Request
    from starlette.responses import JSONResponse, Response

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    lock = asyncio.Lock()

    @app.middleware("http")
    async def boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Everything, including health, is private. No cookies, CORS, profiles or URLs.
        if (
            request.headers.get("host") != f"127.0.0.1:{port}"
            or request.headers.get("origin") is not None
            or len(request.headers.getlist("x-hermes-session-token")) != 1
        ):
            return JSONResponse({"error": "DENIED"}, status_code=403)
        if not hmac.compare_digest(request.headers["x-hermes-session-token"], token):
            return JSONResponse({"error": "DENIED"}, status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "management-only"}

    @app.api_route("/api/config", methods=["GET", "PUT"])
    async def config(request: Request) -> JSONResponse:
        if (request.method == "GET" and str(request.url.query) != "include_defaults=false") or (
            request.method == "PUT" and request.url.query
        ):
            return JSONResponse({"error": "DENIED"}, status_code=400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return JSONResponse({"error": "LIMIT"}, status_code=413)
        try:
            payload = loads(bytes(body), 4096) if body else None
            async with lock:
                value = await asyncio.to_thread(config_operation, request.method, payload)
            return JSONResponse(value)
        except (ValueError, OSError):
            return JSONResponse({"error": "CONFIG_UNAVAILABLE"}, status_code=409)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.listen(4)
        listener.setblocking(False)
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))

        async def serve() -> None:
            task = asyncio.create_task(server.serve(sockets=[listener]))
            while not server.started and not task.done():
                await asyncio.sleep(0.01)
            if not server.started:
                await task
                raise ValueError("Management startup failed")
            print(f"HERMES_BACKEND_READY port={port}", flush=True)
            await task

        asyncio.run(serve())
    return 0
