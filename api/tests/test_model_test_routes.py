"""ASGI caller/security controls, with session/DB/control doubles and no effects."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from omnis.api import create_app
from omnis.modules.engagements.service import EngagementService
from omnis.modules.runs.model_test_models import ModelTestView
from omnis.modules.runs.model_test_operation import OBJECTIVE, SYSTEM
from omnis.security.sessions import SessionStore


@pytest.mark.asyncio
async def test_instance_test_requires_no_saved_engagement(monkeypatch: pytest.MonkeyPatch) -> None:
    from omnis.modules.runs import model_test_routes as routes
    from omnis.security import host_origin

    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf="a" * 64))
    )
    engagement_read = AsyncMock(
        side_effect=AssertionError("Synthetic connectivity must not read a draft")
    )
    monkeypatch.setattr(EngagementService, "read", engagement_read)
    exchange = AsyncMock(
        return_value={
            "operation_id": None,
            "status": "AVAILABLE",
            "reason": None,
            "system_message": SYSTEM,
            "user_message": OBJECTIVE,
            "requested_provider": "openai-codex",
            "requested_model": "gpt-6.1-sol",
            "requested_effort": "xhigh",
            "observed_model": None,
            "observed_effort": None,
            "response_text": None,
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "duration_ms": None,
            "calls_limit": 1,
            "wall_seconds": 300,
        }
    )
    monkeypatch.setattr(routes, "control_exchange", exchange)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.get(
            "/api/v1/model-test", headers={"Cookie": "omnis_session=synthetic"}
        )
    assert response.status_code == 200
    engagement_read.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_test_route_security_input_and_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.runs import model_test_routes as routes
    from omnis.security import host_origin

    identity, operation = str(uuid4()), str(uuid4())
    csrf = "a" * 64
    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf=csrf))
    )
    monkeypatch.setattr(EngagementService, "read", AsyncMock())
    view = ModelTestView(
        operation_id=operation,
        status="PENDING",
        reason=None,
        system_message=SYSTEM,
        user_message=OBJECTIVE,
    )
    exchange = AsyncMock(return_value=view.model_dump(mode="json"))
    monkeypatch.setattr(routes, "control_exchange", exchange)
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        path = "/api/v1/model-test"
        body = {"operation_id": operation, "consent": True}
        headers = {
            "Origin": "http://127.0.0.1:8765",
            "X-CSRF-Token": csrf,
            "Cookie": "omnis_session=synthetic",
        }
        assert (
            await client.put(path, json=body, headers={"Origin": headers["Origin"]})
        ).status_code == 401
        assert (
            await client.put(path, json=body, headers={**headers, "X-CSRF-Token": "b" * 64})
        ).status_code == 403
        assert (
            await client.put(
                path, json=body, headers={**headers, "Origin": "https://foreign.invalid"}
            )
        ).status_code == 403
        for invalid in (
            {**body, "prompt": "raw"},
            {**body, "consent": 1},
            {**body, "operation_id": True},
            {**body, "engagement_id": identity},
        ):
            assert (await client.put(path, json=invalid, headers=headers)).status_code == 422
        duplicate = '{"operation_id":"' + operation + '","consent":true,"consent":true}'
        assert (
            await client.put(
                path, content=duplicate, headers={**headers, "Content-Type": "application/json"}
            )
        ).status_code == 422
        exchange.assert_not_awaited()
        response = await client.put(path, json=body, headers=headers)
        assert response.status_code == 200 and response.json()["status"] == "PENDING"
        assert response.headers["cache-control"] == "no-store"
        assert exchange.await_args is not None and exchange.await_args.args[0].action == "start"
        response = await client.get(path, headers=headers)
        assert response.status_code == 200
        assert exchange.await_args is not None and exchange.await_args.args[0].action == "read"
        assert "manifest_ref" not in response.text and "capability" not in response.text
