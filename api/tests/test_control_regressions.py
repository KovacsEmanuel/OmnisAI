"""Additional negative/recovery controls from the P0.2 acceptance matrix."""

import asyncio
import importlib
import os
import secrets
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection

from conftest import connect_test_database
from omnis.api import create_app
from omnis.core.db import ReadinessReason, database_engine, readiness_reason
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.records import CommandKind, LeaseRecord
from omnis.modules.instance.service import InstanceService
from omnis.security.sessions import PairingDenied, SessionStore, code_digest
from test_supervisor import start_supervisor, stop_process, wait_ready


@pytest.mark.asyncio
async def test_finalized_stop_readback_refuses_committed_current_lease_takeover(
    migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source-level Stop SQL must reject E+1 even if E's FINALIZE remains committed.

    This is a private PostgreSQL readback of the CLI source, not an installed Stop
    or a Docker teardown. The only runtime capability supplied is read-only psql.
    """
    cli_source = Path(__file__).resolve().parents[2] / "cli/src/omnis_cli/stop.py"
    monkeypatch.syspath_prepend(str(cli_source.parents[1]))
    stop_source = importlib.import_module("omnis_cli.stop")
    assert stop_source.__file__ is not None
    assert Path(stop_source.__file__).resolve() == cli_source

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner, successor = uuid4(), uuid4()
    shutdown_command, finalize_command = uuid4(), uuid4()
    db_alias = "attested-private-db"
    try:
        epoch = await service.acquire(owner)
        instance_id = str((await service.status()).instance_id)
        generation = await service.open(uuid4(), 0, owner, epoch)
        generation = await service.shutdown(shutdown_command, generation, owner, epoch)
        await service.quiesce(owner, epoch)
        assert await service.finalize(finalize_command, generation, owner, epoch) == generation

        with connect_test_database(migrated_database_url, autocommit=True) as connection:
            connection.execute("SET default_transaction_read_only = on")
            assert connection.execute("SHOW default_transaction_read_only").fetchone() == ("on",)
            system_id_row = connection.execute(
                "SELECT system_identifier FROM pg_control_system()"
            ).fetchone()
            assert system_id_row is not None
            record: dict[str, object] = {
                "system_id": str(system_id_row[0]),
                "finalized_generation": generation,
                "stop_command": str(shutdown_command),
                "finalize_command": str(finalize_command),
                "supervisor_epoch": epoch,
            }

            def state() -> tuple[object, ...]:
                row = connection.execute(
                    "SELECT c.generation, c.admission_open, c.shutdown_command_id::text, "
                    "c.quiesced_generation, f.kind, f.expected_generation, "
                    "f.result_generation, f.owner_epoch FROM instance_control c "
                    "JOIN instance_command f ON f.command_id = %s WHERE c.id = 1",
                    (finalize_command,),
                ).fetchone()
                assert row is not None
                return row

            committed = state()
            assert committed == (
                generation,
                False,
                str(shutdown_command),
                generation,
                "FINALIZE",
                generation,
                generation,
                epoch,
            )

            def psql(ident: str, query: str) -> str:
                assert ident == db_alias
                assert query.startswith("SELECT "), "Readback must never issue a Stop effect"
                # SQL is emitted by the trusted CLI source; all UUIDs came from this fixture.
                row = connection.execute(sql.SQL(query)).fetchone()  # pyright: ignore[reportArgumentType]
                assert row is not None and len(row) == 1
                return str(row[0])

            runtime = SimpleNamespace(psql=psql)
            stop_source._finalized_db_readback(runtime, record, db_alias, instance_id)

            await service.release(owner, epoch)
            next_epoch = await service.acquire(successor)
            assert next_epoch == epoch + 1
            assert connection.execute(
                "SELECT owner, epoch FROM supervisor_lease WHERE id = 1"
            ).fetchone() == (
                successor,
                next_epoch,
            )
            assert state() == committed  # No new shutdown generation or FINALIZE receipt.
            with pytest.raises(stop_source.StartError) as failure:
                stop_source._finalized_db_readback(runtime, record, db_alias, instance_id)
            assert failure.value.reason == "FINALIZE_READBACK_UNVERIFIED"
            assert failure.value.code == 4
            assert state() == committed  # Readback did not write or initiate Stop.
    finally:
        await engine.dispose()


@pytest.mark.parametrize("operation", ["open", "shutdown", "finalize"])
@pytest.mark.asyncio
async def test_lifecycle_owner_expiry_during_command_receipt_lock_wait_rolls_back(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL, operation: str
) -> None:
    """A pinned owner cannot publish OPEN/Stop after its DB lease expires.

    Hold the command table after acquiring the instance/lease row locks. Only
    this test extends PostgreSQL's statement budget beyond the five-second
    lease; the product's two-second statement budget is unchanged.
    """
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    entered = asyncio.Event()
    original = service._receipt
    task: asyncio.Task[int] | None = None

    async def blocked_receipt(
        connection: AsyncConnection, command_id: UUID, kind: CommandKind, expected: int
    ) -> int | None:
        await connection.execute(text("SET LOCAL statement_timeout = 10000"))
        entered.set()
        return await original(connection, command_id, kind, expected)

    try:
        epoch = await service.acquire(owner)
        generation = 0
        if operation != "open":
            generation = await service.open(uuid4(), generation, owner, epoch)
        if operation == "finalize":
            generation = await service.shutdown(uuid4(), generation, owner, epoch)
            await service.quiesce(owner, epoch)
        monkeypatch.setattr(service, "_receipt", blocked_receipt)
        command = uuid4()
        async with engine.begin() as blocker:
            await blocker.execute(text("LOCK TABLE instance_command IN ACCESS EXCLUSIVE MODE"))
            task = asyncio.create_task(
                getattr(service, operation)(command, generation, owner, epoch)
            )
            await asyncio.wait_for(entered.wait(), 5)
            assert not task.done(), "Command did not wait on the real PostgreSQL lock"
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
                pytest.fail("PostgreSQL lease did not expire during bounded lock wait")
            assert not task.done()
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await asyncio.wait_for(task, 5)
        async with engine.connect() as reader:
            assert (
                await reader.execute(
                    text("SELECT count(*) FROM instance_command WHERE command_id = :id"),
                    {"id": command},
                )
            ).scalar_one() == 0
        current = await service.status()
        assert current.admission_open is (operation == "shutdown")
        assert current.shutdown_finalized is False
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()


@pytest.mark.asyncio
async def test_quiesce_owner_expiry_during_update_lock_wait_rolls_back(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    """A real SHARE table lock delays only UPDATE, after the owner was checked."""
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    checked = asyncio.Event()
    original = service._require_owner
    task: asyncio.Task[None] | None = None

    async def observed(
        connection: AsyncConnection, lease: LeaseRecord, expected_owner: UUID, epoch: int
    ) -> None:
        await original(connection, lease, expected_owner, epoch)
        await connection.execute(text("SET LOCAL statement_timeout = 10000"))
        checked.set()

    try:
        epoch = await service.acquire(owner)
        generation = await service.open(uuid4(), 0, owner, epoch)
        await service.shutdown(uuid4(), generation, owner, epoch)
        monkeypatch.setattr(service, "_require_owner", observed)
        async with engine.begin() as blocker:
            await blocker.execute(text("LOCK TABLE instance_control IN SHARE MODE"))
            task = asyncio.create_task(service.quiesce(owner, epoch))
            await asyncio.wait_for(checked.wait(), 5)
            assert not task.done(), "quiesce did not wait on the real UPDATE table lock"
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
                pytest.fail("PostgreSQL lease did not expire during the bounded quiesce wait")
            assert not task.done()
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await asyncio.wait_for(task, 5)
        assert (await service.status()).quiesced_generation is None
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()


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
        await service.shutdown(uuid4(), generation, owner, epoch)
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
