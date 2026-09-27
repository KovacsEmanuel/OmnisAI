"""Narrow browser bootstrap routes; pairing issuance is never an HTTP operation."""

import asyncio

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from omnis.security.host_origin import COOKIE, error_response
from omnis.security.sessions import PairingDenied, PairingLimited, SessionStore

router = APIRouter(prefix="/api")


class PairingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$", repr=False)


class SessionView(BaseModel):
    authenticated: bool = True
    csrf_token: str


@router.post("/pairing", response_model=SessionView)
async def pair(body: PairingBody, request: Request, response: Response):
    store = SessionStore(request.app.state.db_engine)
    try:
        async with asyncio.timeout(3):
            grant = await store.exchange(body.code)
    except PairingDenied:
        return error_response("PAIRING_DENIED", 401)
    except PairingLimited:
        result = error_response("PAIRING_RATE_LIMITED", 429)
        result.headers["Retry-After"] = "60"
        return result
    response.set_cookie(
        COOKIE, grant.token, httponly=True, samesite="strict", path="/", secure=False, max_age=43200
    )
    return SessionView(csrf_token=grant.csrf)


@router.get("/session", response_model=SessionView)
async def session(request: Request):
    return SessionView(csrf_token=request.state.session_grant.csrf)


@router.post("/logout", status_code=204)
async def logout(request: Request):
    async with asyncio.timeout(3):
        await SessionStore(request.app.state.db_engine).logout(request.state.session_grant.token)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict", secure=False)
    return response
