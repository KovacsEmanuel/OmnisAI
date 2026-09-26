import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from omnis.api import create_app
from omnis.security.sessions import SessionStore, code_digest

ORIGIN = "http://127.0.0.1:8765"


@pytest.mark.asyncio
async def test_http_pairing_session_csrf_logout(monkeypatch, migrated_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        code = secrets.token_urlsafe(24)
        await SessionStore(app.state.db_engine).register(code_digest(code))
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
            async def chunks():
                yield b"x" * 3000
                yield b"synthetic_marker" * 300
            oversized = await client.post("/api/pairing", content=chunks())
            assert oversized.status_code == 413 and "synthetic_marker" not in oversized.text
