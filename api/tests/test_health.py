import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql

from omnis.api import create_app
from conftest import connect_test_database


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


@pytest.mark.asyncio
async def test_ready_requires_real_migrated_postgresql(monkeypatch, migrated_database_url):
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "api_ready": True,
        "dashboard_ready": False,
        "assessment_ready": False,
        "reason": None,
    }


@pytest.mark.asyncio
async def test_ready_denies_an_unmigrated_postgresql(monkeypatch, empty_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", empty_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "api_ready": False,
        "dashboard_ready": False,
        "assessment_ready": False,
        "reason": "SCHEMA_INCOMPATIBLE",
    }


@pytest.mark.asyncio
async def test_ready_denies_a_newer_schema_revision(monkeypatch, migrated_database_url):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute("UPDATE alembic_version SET version_num = 'unsupported_future'")
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "SCHEMA_INCOMPATIBLE"


@pytest.mark.asyncio
async def test_ready_denies_a_missing_instance_row(monkeypatch, migrated_database_url):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute("DELETE FROM instance_control WHERE id = 1")
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "SCHEMA_INCOMPATIBLE"


@pytest.mark.parametrize("column", ["shutdown_command_id", "quiesced_at"])
@pytest.mark.asyncio
async def test_ready_denies_missing_instance_column(monkeypatch, migrated_database_url, column):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute(
            sql.SQL("ALTER TABLE instance_control DROP COLUMN {}").format(sql.Identifier(column))
        )
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "SCHEMA_INCOMPATIBLE"


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER TABLE instance_control DROP CONSTRAINT ck_instance_control_singleton",
        "ALTER TABLE instance_control DROP CONSTRAINT instance_control_instance_id_key",
        "ALTER TABLE instance_control ALTER COLUMN admission_open SET DEFAULT true",
        "ALTER TABLE instance_control ALTER COLUMN quiesced_generation TYPE text",
    ],
)
@pytest.mark.asyncio
async def test_ready_denies_constraint_default_or_type_drift(monkeypatch, migrated_database_url, mutation):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute(mutation)
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "SCHEMA_INCOMPATIBLE"


@pytest.mark.asyncio
async def test_ready_denies_a_same_named_weakened_constraint(monkeypatch, migrated_database_url):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute("ALTER TABLE instance_control DROP CONSTRAINT ck_instance_control_singleton")
        connection.execute(
            "ALTER TABLE instance_control ADD CONSTRAINT ck_instance_control_singleton CHECK (true)"
        )
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "SCHEMA_INCOMPATIBLE"


@pytest.mark.asyncio
async def test_ready_denies_an_extra_constraint_blocking_future_admission(monkeypatch, migrated_database_url):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute(
            "ALTER TABLE instance_control ADD CONSTRAINT ck_never_open CHECK (NOT admission_open)"
        )
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "SCHEMA_INCOMPATIBLE"


@pytest.mark.asyncio
async def test_ready_times_out_while_postgres_is_connected_but_locked(monkeypatch, migrated_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    with connect_test_database(migrated_database_url) as blocker:
        blocker.execute("LOCK TABLE instance_control IN ACCESS EXCLUSIVE MODE")
        app = create_app()
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
            ) as client:
                response = await asyncio.wait_for(client.get("/health/ready"), timeout=4)

    assert response.status_code == 503
    assert response.json()["reason"] == "DATABASE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_ready_reports_disconnected_database_without_exposing_url(monkeypatch, empty_database_url):
    unavailable = empty_database_url.set(port=1, password="synthetic_do_not_echo")
    monkeypatch.setenv("OMNIS_DATABASE_URL", unavailable.render_as_string(hide_password=False))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.get("/health/ready")
            live = await client.get("/health/live")

    assert response.status_code == 503
    assert response.json()["reason"] == "DATABASE_UNAVAILABLE"
    assert "synthetic_do_not_echo" not in response.text
    assert live.status_code == 200


@pytest.mark.asyncio
async def test_api_rejects_ambient_libpq_routing_at_startup(monkeypatch):
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL",
        "postgresql+psycopg://omnis_test:synthetic@127.0.0.1:1/omnis_test",
    )
    monkeypatch.setenv("PGHOSTADDR", "127.0.0.2")
    app = create_app()
    with pytest.raises(ValueError, match="Ambient libpq"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
async def test_api_rejects_database_url_query_overrides_at_startup(monkeypatch):
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL",
        "postgresql+psycopg://omnis_test:synthetic@127.0.0.1:1/omnis_test?host=127.0.0.2",
    )
    app = create_app()
    with pytest.raises(ValueError, match="query parameters are forbidden"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
async def test_api_restart_closes_pool_and_keeps_instance_identity(monkeypatch, migrated_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    with connect_test_database(migrated_database_url) as connection:
        identity = connection.execute("SELECT instance_id FROM instance_control WHERE id = 1").fetchone()
        assert identity is not None

    for _ in range(2):
        app = create_app()
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
            ) as client:
                assert (await client.get("/health/ready")).status_code == 200
            with connect_test_database(migrated_database_url) as connection:
                count_row = connection.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid()"
                ).fetchone()
                assert count_row is not None and count_row[0] >= 1
        with connect_test_database(migrated_database_url) as connection:
            assert connection.execute("SELECT instance_id FROM instance_control WHERE id = 1").fetchone() == identity
            count_row = connection.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid()"
            ).fetchone()
            assert count_row == (0,)
