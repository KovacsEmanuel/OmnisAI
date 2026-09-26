"""Fail-closed same-origin HTTP boundary; no CORS or proxy-header trust."""

import asyncio
import hmac
import os
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import Headers

from starlette.responses import JSONResponse

from omnis.core.db import readiness_reason
from omnis.core.errors import ErrorCode, ErrorDetail, ErrorEnvelope, request_correlation
from omnis.security.sessions import SessionStore

COOKIE = "omnis_session"


def local_origin() -> str:
    raw = os.environ.get("OMNIS_HTTP_PORT", "8765")
    if not raw.isascii() or not raw.isdecimal() or not 1 <= int(raw) <= 65535:
        raise ValueError("Invalid local HTTP port")
    return f"http://127.0.0.1:{int(raw)}"


def error_response(code: str, status: int) -> JSONResponse:
    error = ErrorEnvelope(error=ErrorDetail(code=ErrorCode(code), correlation_id=request_correlation.get() or uuid4()))
    return JSONResponse(error.model_dump(mode="json"), status_code=status,
                        headers={"Cache-Control": "no-store"})


class LocalBoundary:
    def __init__(self, app, origin: str):
        self.app = app
        self.origin = origin
        self.host = origin.removeprefix("http://")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation = uuid4()
        token = request_correlation.set(correlation)
        async def correlated_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", []) if key.lower() != b"x-correlation-id"
                ] + [(b"x-correlation-id", str(correlation).encode())]
            await send(message)
        try:
            await self._http(scope, receive, correlated_send)
        finally:
            request_correlation.reset(token)

    async def _http(self, scope, receive, send):
        headers = Headers(scope=scope)
        mutation = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        origins = headers.getlist("origin")
        denied = None
        if headers.getlist("host") != [self.host]:
            denied = error_response("INVALID_HOST", 400)
        elif (origins and origins != [self.origin]) or (mutation and origins != [self.origin]):
            denied = error_response("INVALID_ORIGIN", 403)
        is_api = scope["path"] == "/api" or scope["path"].startswith("/api/")
        if denied is None and is_api and scope.get("query_string"):
            denied = error_response("QUERY_NOT_ALLOWED", 400)
        if denied is not None:
            await denied(scope, receive, send)
            return

        if is_api:
            try:
                if mutation:
                    body = bytearray()
                    async with asyncio.timeout(3):
                        while True:
                            message = await receive()
                            if message["type"] == "http.disconnect":
                                return
                            body.extend(message.get("body", b""))
                            if len(body) > 4096:
                                await error_response("BODY_TOO_LARGE", 413)(scope, receive, send)
                                return
                            if not message.get("more_body", False):
                                break
                    async def buffered_receive():
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    receive = buffered_receive

                engine = scope["app"].state.db_engine
                # Missing session must be denied even while the DB is unavailable.
                public_pairing = scope["path"] == "/api/pairing" and scope["method"] == "POST"
                tokens = []
                if not public_pairing:
                    cookies = [part.strip().partition("=") for header in headers.getlist("cookie") for part in header.split(";")]
                    tokens = [value for name, _, value in cookies if name == COOKIE]
                    if len(tokens) != 1:
                        await error_response("UNAUTHENTICATED", 401)(scope, receive, send)
                        return
                if await readiness_reason(engine) is not None:
                    await error_response("CONTROL_UNAVAILABLE", 503)(scope, receive, send)
                    return
                if not public_pairing:
                    async with asyncio.timeout(3):
                        grant = await SessionStore(engine).authenticate(tokens[0])
                    if grant is None:
                        await error_response("UNAUTHENTICATED", 401)(scope, receive, send)
                        return
                    csrf = headers.getlist("x-csrf-token")
                    if mutation and (len(csrf) != 1 or not hmac.compare_digest(csrf[0].encode(), grant.csrf.encode())):
                        await error_response("INVALID_CSRF", 403)(scope, receive, send)
                        return
                    scope.setdefault("state", {})["session_grant"] = grant
            except TimeoutError:
                await error_response("CONTROL_TIMEOUT", 503)(scope, receive, send)
                return
            except SQLAlchemyError:
                await error_response("CONTROL_UNAVAILABLE", 503)(scope, receive, send)
                return

        async def private_send(message):
            if message["type"] == "http.response.start" and is_api:
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", []) if key.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                     (b"x-frame-options", b"DENY")]
            await send(message)
        await self.app(scope, receive, private_send)
