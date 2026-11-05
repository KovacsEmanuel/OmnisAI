"""The future web client must see the API's actual error contract."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from omnis.api import create_app
from omnis.core.errors import ErrorEnvelope
from omnis.security.sessions import SessionStore


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/pairing", "post", (400, 401, 403, 413, 422, 429, 500, 503)),
        ("/api/session", "get", (400, 401, 403, 500, 503)),
        ("/api/logout", "post", (400, 401, 403, 413, 500, 503)),
        ("/api/instance", "get", (400, 401, 403, 500, 503)),
        (
            "/api/v1/engagements/{engagement_id}/run-preflight",
            "post",
            (401, 404, 409, 413, 422, 503),
        ),
        ("/api/v1/runs", "post", (401, 404, 409, 413, 422, 503)),
        ("/api/v1/runs/{run_id}/commands", "post", (401, 404, 409, 413, 422, 503)),
        ("/api/v1/runs/commands/{command_id}", "get", (401, 404, 422, 503)),
        ("/api/v1/runs/publications", "get", (401, 409, 503)),
        ("/api/v1/runs/active", "get", (401, 503)),
        ("/api/v1/engagements/{engagement_id}/run", "get", (401, 422, 503)),
        ("/api/v1/runs/{run_id}/summary", "get", (401, 404, 422, 503)),
        ("/api/v1/runs/{run_id}/events", "get", (401, 404, 422, 503)),
        ("/api/v1/runs/{run_id}/attempts/{attempt_id}", "get", (401, 404, 422, 503)),
    ],
)
def test_openapi_declares_real_error_envelopes(
    path: str, method: str, statuses: tuple[int, ...]
) -> None:
    schema = create_app().openapi()
    assert "ErrorEnvelope" in schema["components"]["schemas"]
    responses = schema["paths"][path][method]["responses"]
    for status in statuses:
        assert responses[str(status)]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorEnvelope"
        }
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_health_degradation_keeps_its_distinct_readiness_payload() -> None:
    responses = create_app().openapi()["paths"]["/health/ready"]["get"]["responses"]
    assert responses["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthReady"
    }


def test_engagement_declares_aggregate_payload_budget() -> None:
    schema = create_app().openapi()["components"]["schemas"]["EngagementDraft"]
    assert schema["x-max-canonical-payload-bytes"] == 1_000_000


@pytest.mark.asyncio
async def test_documented_validation_error_matches_the_real_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ready_without_db(engine: object) -> None:
        return None

    monkeypatch.setattr("omnis.security.host_origin.readiness_reason", ready_without_db)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.post(
            "/api/pairing",
            json={"code": {"synthetic-secret": "must-not-be-reflected"}},
            headers={"origin": "http://127.0.0.1:8765"},
        )
    assert response.status_code == 422
    parsed = ErrorEnvelope.model_validate(response.json())
    assert parsed.error.code == "INVALID_INPUT"
    assert "must-not-be-reflected" not in response.text
    documented = app.openapi()["paths"]["/api/pairing"]["post"]["responses"]["422"]
    assert documented["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorEnvelope")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/engagements/{engagement_id}/run-preflight", "post"),
        ("/api/v1/runs", "post"),
        ("/api/v1/runs/{run_id}/commands", "post"),
        ("/api/v1/runs/commands/{command_id}", "get"),
        ("/api/v1/engagements/{engagement_id}/run", "get"),
        ("/api/v1/runs/{run_id}/summary", "get"),
        ("/api/v1/runs/{run_id}/events", "get"),
        ("/api/v1/runs/{run_id}/attempts/{attempt_id}", "get"),
    ],
)
async def test_run_validation_envelope_matches_documented_source_route(
    monkeypatch: pytest.MonkeyPatch, path: str, method: str
) -> None:
    monkeypatch.setattr("omnis.security.host_origin.readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf="a" * 64))
    )
    app = create_app()
    # No lifespan/DB/control: validation must refuse before the real endpoint body.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.request(
            method,
            path.format(
                engagement_id="invalid",
                run_id="invalid",
                command_id="invalid",
                attempt_id="invalid",
            ),
            json={"synthetic-secret": "must-not-be-reflected"} if method == "post" else None,
            headers={
                "origin": "http://127.0.0.1:8765",
                "Cookie": "omnis_session=synthetic",
                "X-CSRF-Token": "a" * 64,
            },
        )
    assert response.status_code == 422
    assert ErrorEnvelope.model_validate(response.json()).error.code == "INVALID_INPUT"
    assert "must-not-be-reflected" not in response.text
    assert app.openapi()["paths"][path][method]["responses"]["422"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ErrorEnvelope"}
