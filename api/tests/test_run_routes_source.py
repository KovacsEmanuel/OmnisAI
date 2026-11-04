"""S1 normal caller contract. SOURCE only; the PG journey is separately admitted."""

import json
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from omnis.api import create_app
from omnis.modules.runs import run_routes
from omnis.modules.runs.run_contract import CommandReceipt, RunCommand, RunControl


def test_run_routes_are_normal_authenticated_api_callers() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/v1/instance/stop" not in paths
    for path in (
        "/api/v1/engagements/{engagement_id}/run-preflight",
        "/api/v1/runs",
        "/api/v1/runs/{run_id}/commands",
        "/api/v1/runs/{run_id}/summary",
        "/api/v1/runs/{run_id}/events",
        "/api/v1/runs/{run_id}/attempts/{attempt_id}",
        "/api/v1/runs/commands/{command_id}",
    ):
        assert path in paths, path


def request_with_body(raw: bytes) -> Request:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/"}, receive)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["exact_body", "body_over", "envelope_over", "duplicate_json"])
async def test_run_command_wire_limits_fail_before_control(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    body = RunCommand(
        action="answer",
        command_id=str(uuid4()),
        run_id=str(uuid4()),
        question_id=str(uuid4()),
        expected_generation=0,
        expected_revision=1,
        answer="inert",
    )
    if mode == "envelope_over":
        for size in range(1000, 1800):
            candidate = body.model_copy(update={"answer": "\t" * size})
            length = len(candidate.model_dump_json().encode())
            if 3580 <= length <= 3600:
                body = RunCommand.model_validate(candidate.model_dump())
                break
        assert 3580 <= len(body.model_dump_json().encode()) <= 3600
    raw = body.model_dump_json().encode()
    if mode in {"exact_body", "body_over"}:
        raw += b" " * (4096 - len(raw) + int(mode == "body_over"))
    if mode == "duplicate_json":
        raw = raw[:-1] + b',"expected_revision":1}'
    sent: list[RunControl] = []

    async def exchange(control: RunControl) -> dict[str, object]:
        sent.append(control)
        return CommandReceipt(
            command_id=body.command_id, run_id=body.run_id, revision=2, state="ADMITTED"
        ).model_dump(mode="json")

    monkeypatch.setattr(run_routes, "control_exchange", exchange)
    result = await run_routes.command(body.run_id, body, request_with_body(raw))
    if mode == "exact_body":
        assert isinstance(result, CommandReceipt) and len(sent) == 1
    else:
        assert isinstance(result, JSONResponse) and result.status_code == 422
        assert sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize("more", [False, True])
async def test_publication_list_refuses_truncation(
    monkeypatch: pytest.MonkeyPatch, more: bool
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

    from omnis.modules.settings.catalog_inspection_models import CatalogPage

    engine = object.__new__(AsyncEngine)
    db = object.__new__(AsyncConnection)

    @asynccontextmanager
    async def connect(self: AsyncEngine) -> AsyncIterator[AsyncConnection]:
        yield db

    async def published_page(connection: AsyncConnection, after: str | None) -> CatalogPage:
        assert connection is db and after is None
        return CatalogPage(items=[], has_more=more, next_after=str(uuid4()) if more else None)

    from omnis.modules.settings import catalog_inspection

    monkeypatch.setattr(catalog_inspection, "published_page", published_page)
    monkeypatch.setattr(AsyncEngine, "connect", connect)
    app = FastAPI()
    app.state.db_engine = engine
    request = Request({"type": "http", "method": "GET", "path": "/", "app": app})
    result = await run_routes.publications(request)
    if more:
        assert isinstance(result, JSONResponse) and result.status_code == 409
        assert json.loads(bytes(result.body))["error"]["code"] == "CATALOG_LIST_LIMIT"
    else:
        assert result == []


@pytest.mark.parametrize(
    "code",
    [
        "AUTHORITY_DENIED",
        "ANSWER_DENIED",
        "REF_UNAVAILABLE",
        "GENERATION_CONFLICT",
        "CURSOR_DENIED",
        "PROJECTION_LIMIT",
        "CATALOG_LIST_LIMIT",
    ],
)
def test_run_denial_has_serializable_public_error(code: str) -> None:
    from omnis.security.host_origin import error_response

    response = error_response(code, 409)
    assert response.status_code == 409 and json.loads(bytes(response.body))["error"]["code"] == code
