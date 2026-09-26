"""Additional negative/recovery controls from the P0.2 acceptance matrix."""

import asyncio
import os
import secrets
import subprocess
import sys
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from conftest import connect_test_database
from omnis.api import create_app
from omnis.core.db import ReadinessReason, database_engine, readiness_reason
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import PairingDenied, SessionStore, code_digest
from test_local_control import ipc_directory, request
from test_supervisor import start_supervisor, stop_process, wait_ready


@pytest.mark.asyncio
async def test_pairing_rechecks_expiry_after_waiting_for_the_row(migrated_database_url):
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    store = SessionStore(engine)
    code = secrets.token_urlsafe(24)
    try:
        await store.register(code_digest(code), issuance_id=uuid4())
        async with engine.begin() as blocker:
            await blocker.execute(text("SELECT id FROM pairing_challenge WHERE id = 1 FOR UPDATE"))
            attempt = asyncio.create_task(store.exchange(code))
            await asyncio.sleep(0.05)
            assert not attempt.done()
            await blocker.execute(text("UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second'"))
        with pytest.raises(PairingDenied):
            await attempt
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT count(*) FROM ui_session"))).scalar_one() == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_csrf_is_not_transferable_and_ambiguous_cookies_are_refused(monkeypatch, migrated_database_url):
    monkeypatch.setenv("OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False))
    app = create_app()
    origin = "http://127.0.0.1:8765"
    async with app.router.lifespan_context(app):
        store = SessionStore(app.state.db_engine)
        tokens = []
        for _ in range(2):
            code = secrets.token_urlsafe(24)
            await store.register(code_digest(code), issuance_id=uuid4())
            tokens.append(await store.exchange(code))
        first, second = tokens
        async with AsyncClient(transport=ASGITransport(app=app), base_url=origin) as client:
            response = await client.post("/api/logout", headers={"origin": origin,
                "cookie": f"omnis_session={second.token}", "x-csrf-token": first.csrf})
            assert response.status_code == 403
            assert await store.authenticate(second.token) is not None
            response = await client.get("/api/session", headers={"cookie":
                f"omnis_session={first.token}; omnis_session={second.token}"})
            assert response.status_code == 401


@pytest.mark.parametrize("mutation", [
    "ALTER TABLE ui_session ALTER COLUMN expires_at DROP NOT NULL",
    "ALTER TABLE pairing_challenge ALTER COLUMN attempts SET DEFAULT 1",
    "ALTER TABLE instance_command DROP CONSTRAINT instance_command_pkey",
    "DELETE FROM supervisor_lease",
])
@pytest.mark.asyncio
async def test_new_authority_schema_drift_is_not_ready(migrated_database_url, mutation):
    with connect_test_database(migrated_database_url) as connection:
        connection.execute(mutation)
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        assert await readiness_reason(engine) == ReadinessReason.SCHEMA_INCOMPATIBLE
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_admission_rolls_back_its_inert_write(migrated_database_url):
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        generation = await service.open(uuid4(), 0, owner, epoch)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE inert_marker (id integer)"))
            await connection.execute(text("UPDATE supervisor_lease SET expires_at = clock_timestamp() + interval '1 second'"))
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            async with service.admission(generation, owner, epoch) as connection:
                await connection.execute(text("INSERT INTO inert_marker VALUES (1)"))
                await asyncio.sleep(1.1)
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT count(*) FROM inert_marker"))).scalar_one() == 0
    finally:
        await engine.dispose()


def test_supervisor_exits_bounded_when_db_authority_is_blocked(migrated_database_url, ipc_directory):
    process = start_supervisor(migrated_database_url, ipc_directory)
    try:
        wait_ready(process)
        with connect_test_database(migrated_database_url) as blocker:
            blocker.execute("LOCK TABLE instance_control IN ACCESS EXCLUSIVE MODE")
            stdout, stderr = process.communicate(timeout=8)
        assert process.returncode != 0
        assert "SUPERVISOR_UNAVAILABLE" in stderr
        assert not (ipc_directory / "control.sock").exists()
    finally:
        stop_process(process)


def test_domain_import_is_independent_of_frameworks_and_runtime(ipc_directory):
    result = subprocess.run([sys.executable, "-I", "-c",
        "import sys; import omnis.modules.instance.domain; "
        "assert not {'fastapi','sqlalchemy','hermes','playwright'} & set(sys.modules); print('DOMAIN_IMPORT_OK')"],
        cwd=ipc_directory, env={"PATH": os.environ.get("PATH", "")},
        capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and result.stdout.strip() == "DOMAIN_IMPORT_OK"
