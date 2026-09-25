import pytest
from httpx import ASGITransport, AsyncClient

from omnis.api import create_app


@pytest.mark.asyncio
async def test_live_reports_the_process_without_a_database(monkeypatch):
    monkeypatch.delenv("OMNIS_DATABASE_URL", raising=False)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.parametrize(
    "host", ["attacker.invalid:8765", "127.0.0.1:9999", "127.0.0.1:8765.evil", "127.0.0.1"]
)
@pytest.mark.asyncio
async def test_live_rejects_a_foreign_host(host):
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.get(
            "/health/live", headers={"host": host, "x-forwarded-host": "127.0.0.1:8765"}
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_live_ignores_forwarded_host():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.get(
            "/health/live", headers={"x-forwarded-host": "attacker.invalid:8765"}
        )

    assert response.status_code == 200
