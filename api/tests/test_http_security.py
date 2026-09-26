import asyncio
import secrets
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from omnis.api import create_app
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import SessionStore, code_digest

ORIGIN = "http://127.0.0.1:8765"


@pytest.mark.asyncio
async def test_http_pairing_session_csrf_logout(monkeypatch, migrated_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        code = secrets.token_urlsafe(24)
        await SessionStore(app.state.db_engine).register(code_digest(code), issuance_id=uuid4())
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get("/api/session")).status_code == 401
            response = await client.post("/api/pairing", json={"code": code}, headers={"origin": ORIGIN})
            assert response.status_code == 200
            assert code not in response.text
            cookie = response.headers["set-cookie"]
            assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
            assert "Domain=" not in cookie
            assert response.headers["cache-control"] == "no-store"
            old_token = client.cookies["omnis_session"]
            csrf = response.json()["csrf_token"]
            session = await client.get("/api/session")
            assert session.status_code == 200 and session.json()["csrf_token"] == csrf
            instance = await client.get("/api/instance")
            assert instance.status_code == 200
            assert instance.json()["admission_open"] is False
            assert instance.json()["supervisor_ready"] is False
            assert instance.json()["assessment_ready"] is False
            assert instance.json()["dashboard_ready"] is False
            assert (await client.post("/api/logout", headers={"origin": ORIGIN})).status_code == 403
            assert (await client.post("/api/logout", headers={"origin": ORIGIN, "x-csrf-token": "wrong"})).status_code == 403
            assert (await client.post("/api/logout", headers={"origin": ORIGIN, "x-csrf-token": csrf})).status_code == 204
            assert (await client.get("/api/session", headers={"cookie": f"omnis_session={old_token}"})).status_code == 401
            assert (await client.post("/api/pairing", json={"code": code}, headers={"origin": ORIGIN})).status_code == 401


@pytest.mark.parametrize("headers", [
    {}, {"origin": "null"}, {"origin": "http://attacker.invalid"},
    {"origin": ORIGIN + "/"}, {"origin": "https://127.0.0.1:8765"},
    [("origin", ORIGIN), ("origin", ORIGIN)],
])
@pytest.mark.asyncio
async def test_mutations_require_exact_unambiguous_origin(headers):
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url=ORIGIN) as client:
        response = await client.post("/api/pairing", json={"code": "synthetic_marker_do_not_reflect"}, headers=headers)
    assert response.status_code == 403
    assert "synthetic_marker" not in response.text


@pytest.mark.asyncio
async def test_foreign_reads_duplicate_host_and_pairing_url_are_refused():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url=ORIGIN) as client:
        assert (await client.get("/health/live", headers={"origin": "http://attacker.invalid"})).status_code == 403
        assert (await client.get("/health/live", headers=[("host", "127.0.0.1:8765"), ("host", "127.0.0.1:8765")])).status_code == 400
        response = await client.post("/api/pairing?code=synthetic_marker", headers={"origin": ORIGIN})
        assert response.status_code == 400 and "synthetic_marker" not in response.text


@pytest.mark.asyncio
async def test_http_port_is_explicit_and_loopback_only(monkeypatch):
    monkeypatch.setenv("OMNIS_HTTP_PORT", "18765")
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://127.0.0.1:18765") as client:
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/health/live", headers={"host": "127.0.0.1:8765"})).status_code == 400
    monkeypatch.setenv("OMNIS_HTTP_PORT", "0")
    with pytest.raises(ValueError, match="port"):
        create_app()


@pytest.mark.asyncio
async def test_pairing_body_is_bounded_and_errors_do_not_reflect(monkeypatch, migrated_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
            invalid = await client.post("/api/pairing", json={"code": {"secret": "synthetic_marker"}})
            assert invalid.status_code == 422 and "synthetic_marker" not in invalid.text
            assert invalid.json()["error"]["correlation_id"] == invalid.headers["x-correlation-id"]
            async def chunks():
                yield b"x" * 3000
                yield b"synthetic_marker" * 300
            oversized = await client.post("/api/pairing", content=chunks())
            assert oversized.status_code == 413 and "synthetic_marker" not in oversized.text


@pytest.mark.parametrize("operation", ["pairing", "logout", "instance"])
@pytest.mark.asyncio
async def test_session_transaction_has_deadline_and_rolls_back(monkeypatch, migrated_database_url, operation):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        store = SessionStore(app.state.db_engine)
        code = secrets.token_urlsafe(24)
        await store.register(code_digest(code), issuance_id=uuid4())
        grant = await store.exchange(code)

        async def stalled_transaction(self, *args):
            # Fault-inject a stalled client operation after a real PostgreSQL write.
            async with self.engine.begin() as connection:
                await connection.execute(text("UPDATE pairing_challenge SET attempts = attempts + 10"))
                await asyncio.Event().wait()

        method = {"pairing": "exchange", "logout": "logout", "instance": "status"}[operation]
        owner = InstanceService if operation == "instance" else SessionStore
        monkeypatch.setattr(owner, method, stalled_transaction)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            try:
                response = await asyncio.wait_for(client.request(
                    "GET" if operation == "instance" else "POST", f"/api/{operation}",
                    json={"code": code} if operation == "pairing" else None,
                    headers={"origin": ORIGIN, "cookie": f"omnis_session={grant.token}", "x-csrf-token": grant.csrf}
                ), timeout=4)
            except TimeoutError:
                pytest.fail("Session transaction outlived the HTTP deadline")
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "CONTROL_TIMEOUT"
            assert response.json()["error"]["correlation_id"] == response.headers["x-correlation-id"]
            assert "set-cookie" not in response.headers and code not in response.text
        async with app.state.db_engine.connect() as connection:
            assert (await connection.execute(text("SELECT attempts FROM pairing_challenge"))).scalar_one() == 1


@pytest.mark.asyncio
async def test_error_correlations_are_generated_server_side_per_request():
    injected = "00000000-0000-4000-8000-000000000000"
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url=ORIGIN,
                           headers={"x-correlation-id": injected}) as client:
        responses = await asyncio.gather(
            client.get("/health/live", headers={"host": "attacker.invalid"}),
            client.post("/api/pairing", headers={"origin": "null"}),
            client.get("/api/session"),
            client.post("/api/pairing", json={"code": "synthetic_code_marker"}, headers={"origin": ORIGIN}),
            client.get("/unknown"),
            client.post("/health/live", headers={"origin": ORIGIN}),
        )
    assert [response.status_code for response in responses] == [400, 403, 401, 503, 404, 405]
    assert "GET" in responses[-1].headers.get("allow", "")
    correlations = []
    for response in responses:
        assert "x-correlation-id" in response.headers
        correlation = response.headers["x-correlation-id"]
        assert UUID(correlation).version == 4 and correlation != injected
        assert response.json()["error"]["correlation_id"] == correlation
        assert "synthetic_code_marker" not in response.text
        correlations.append(correlation)
    assert len(set(correlations)) == len(responses)
