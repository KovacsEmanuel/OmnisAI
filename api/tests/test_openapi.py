"""The future web client must see the API's actual error contract."""

import pytest
from httpx import ASGITransport, AsyncClient

from omnis.api import create_app
from omnis.core.errors import ErrorEnvelope


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/pairing", "post", (400, 401, 403, 413, 422, 429, 500, 503)),
        ("/api/session", "get", (400, 401, 403, 500, 503)),
        ("/api/logout", "post", (400, 401, 403, 413, 500, 503)),
        ("/api/instance", "get", (400, 401, 403, 500, 503)),
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
