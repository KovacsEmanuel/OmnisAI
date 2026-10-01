"""Additional negative/recovery controls from the P0.2 acceptance matrix."""

import asyncio
import os
import secrets
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection

from conftest import connect_test_database
from omnis.api import create_app
from omnis.core.db import ReadinessReason, database_engine, readiness_reason
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.records import LeaseRecord
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import PairingDenied, SessionStore, code_digest
from test_supervisor import start_supervisor, stop_process, wait_ready


@pytest.mark.asyncio
async def test_private_pairing_waits_for_challenge_then_refuses_expired_lease(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    """The first owner check must not authorize a later DB commit after expiry.

    The transaction-local statement timeout is lengthened only in this
    adversarial fixture so PostgreSQL does not abort the blocked read before
    the real DB lease expires; production keeps its 2s statement budget.
    """
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    first_check = asyncio.Event()
    original = service._require_owner

    async def observed(
        connection: AsyncConnection, lease: LeaseRecord, expected_owner: UUID, epoch: int
    ) -> None:
        await original(connection, lease, expected_owner, epoch)
        await connection.execute(text("SET LOCAL statement_timeout = 10000"))
        first_check.set()

    task: asyncio.Task[None] | None = None
    try:
        epoch = await service.acquire(owner)
        identity = (await service.status()).instance_id
        await service.open(uuid4(), 0, owner, epoch)
        monkeypatch.setattr(service, "_require_owner", observed)
        async with engine.begin() as blocker:
            await blocker.execute(text("SELECT id FROM pairing_challenge WHERE id = 1 FOR UPDATE"))
            task = asyncio.create_task(
                service.register_pairing(
                    identity,
                    code_digest("synthetic-pairing-waiting-for-expired-lease"),
                    uuid4(),
                    owner,
                    epoch,
                )
            )
            await asyncio.wait_for(first_check.wait(), 5)
            assert not task.done(), "Issuance did not wait on the challenge lock"
            deadline = asyncio.get_running_loop().time() + 8
            while asyncio.get_running_loop().time() < deadline:
                async with engine.connect() as reader:
                    expired = (
                        await reader.execute(
                            text(
                                "SELECT expires_at <= clock_timestamp() FROM supervisor_lease WHERE id = 1"
                            )
                        )
                    ).scalar_one()
                if expired is True:
                    break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("Real PostgreSQL lease did not expire within bounded wait")
            assert not task.done()
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await asyncio.wait_for(task, 5)
        async with engine.connect() as reader:
            assert (
                await reader.execute(text("SELECT digest FROM pairing_challenge WHERE id = 1"))
            ).scalar_one() is None
            assert (
                await reader.execute(text("SELECT count(*) FROM pairing_issuance"))
            ).scalar_one() == 0
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()


@pytest.mark.asyncio
async def test_private_pairing_issuance_is_serialized_with_shutdown(
    migrated_database_url: URL,
) -> None:
    """A closed instance cannot register a digest through the owner control plane."""
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner, issuance = uuid4(), uuid4()
    try:
        epoch = await service.acquire(owner)
        identity = (await service.status()).instance_id
        generation = await service.open(uuid4(), 0, owner, epoch)
        digest = code_digest("synthetic-before-shutdown-code")
        await service.register_pairing(identity, digest, issuance, owner, epoch)
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT digest FROM pairing_challenge WHERE id = 1"))
            ).scalar_one() == digest
        await service.shutdown(uuid4(), generation)
        with pytest.raises(ControlConflict, match="INSTANCE_SHUTTING_DOWN"):
            await service.register_pairing(
                identity, code_digest("synthetic-after-shutdown-code"), uuid4(), owner, epoch
            )
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT digest FROM pairing_challenge WHERE id = 1"))
            ).scalar_one() == digest
            assert (
                await connection.execute(text("SELECT count(*) FROM pairing_issuance"))
            ).scalar_one() == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pairing_rechecks_expiry_after_waiting_for_the_row(
    migrated_database_url: URL,
) -> None:
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
            await blocker.execute(
                text(
                    "UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        with pytest.raises(PairingDenied):
            await attempt
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM ui_session"))
            ).scalar_one() == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_csrf_is_not_transferable_and_ambiguous_cookies_are_refused(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
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
            response = await client.post(
                "/api/logout",
                headers={
                    "origin": origin,
                    "cookie": f"omnis_session={second.token}",
                    "x-csrf-token": first.csrf,
                },
            )
            assert response.status_code == 403
            assert await store.authenticate(second.token) is not None
            response = await client.get(
                "/api/session",
                headers={"cookie": f"omnis_session={first.token}; omnis_session={second.token}"},
            )
            assert response.status_code == 401


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER TABLE ui_session ALTER COLUMN expires_at DROP NOT NULL",
        "ALTER TABLE pairing_challenge ALTER COLUMN attempts SET DEFAULT 1",
        "ALTER TABLE instance_command DROP CONSTRAINT instance_command_pkey",
        "DELETE FROM supervisor_lease",
        "DROP TABLE ui_session",
        "ALTER TABLE pairing_challenge DROP CONSTRAINT pairing_challenge_id_check; "
        "ALTER TABLE pairing_challenge ADD CONSTRAINT pairing_challenge_id_check CHECK (true)",
        "ALTER TABLE ui_session ALTER COLUMN expires_at DROP NOT NULL; "
        "INSERT INTO ui_session VALUES ('synthetic-null-expiry', NULL); "
        "ALTER TABLE ui_session ADD CONSTRAINT expires_required NOT NULL expires_at NOT VALID",
        "ALTER TABLE pairing_issuance DROP CONSTRAINT pairing_issuance_digest_key",
    ],
)
@pytest.mark.asyncio
async def test_new_authority_schema_drift_is_not_ready(
    migrated_database_url: URL, mutation: str
) -> None:
    with connect_test_database(migrated_database_url) as connection:
        connection.execute(mutation)
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        assert await readiness_reason(engine) == ReadinessReason.SCHEMA_INCOMPATIBLE
        app = create_app()
        app.state.db_engine = engine
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            response = await client.post(
                "/api/pairing",
                json={"code": "synthetic-denied-code"},
                headers={"origin": "http://127.0.0.1:8765"},
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "CONTROL_UNAVAILABLE"
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT digest, attempts FROM pairing_challenge"))
            ).one() == (None, 0)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_admission_rolls_back_its_inert_write(migrated_database_url: URL) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        generation = await service.open(uuid4(), 0, owner, epoch)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE inert_marker (id integer)"))
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() + interval '1 second'"
                )
            )
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            async with service.admission(generation, owner, epoch) as connection:
                await connection.execute(text("INSERT INTO inert_marker VALUES (1)"))
                await asyncio.sleep(1.1)
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM inert_marker"))
            ).scalar_one() == 0
    finally:
        await engine.dispose()


def test_supervisor_exits_bounded_when_db_authority_is_blocked(
    migrated_database_url: URL, ipc_directory: Path
) -> None:
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


def test_domain_import_is_independent_of_frameworks_and_runtime(ipc_directory: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import omnis.modules.instance.domain; "
            "assert not {'fastapi','sqlalchemy','hermes','playwright'} & set(sys.modules); print('DOMAIN_IMPORT_OK')",
        ],
        cwd=ipc_directory,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0 and result.stdout.strip() == "DOMAIN_IMPORT_OK"
