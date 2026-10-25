import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "profile",
        "owner",
        "epoch",
        "generation",
        "quiescence",
        "drain",
        "receipt",
        "fence",
        "already_commanded",
        "live_lease",
        "maximum",
        "overflow",
    ],
)
async def test_owner_loss_new_shutdown_source(case: str) -> None:
    """SOURCE SQL double, real acquire/quiesce/shutdown guards; PG proof below."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime, timedelta
    from unittest.mock import AsyncMock, Mock

    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    now = datetime.now(UTC)
    identity, old_owner, owner = uuid4(), uuid4(), uuid4()
    generation = 9223372036854775805 if case == "maximum" else 1
    instance: dict[str, object] = dict(
        id=1,
        instance_id=identity,
        admission_open=True,
        shutdown_command_id=None,
        generation=1,
        quiesced_generation=None,
        quiesced_at=None,
    )
    instance["generation"] = generation
    lease: dict[str, object] = dict(
        id=1, owner=old_owner, epoch=1, expires_at=now - timedelta(seconds=1)
    )
    receipts: dict[object, dict[str, object]] = {}
    fenced = False

    async def execute(statement: object, params: dict[str, object] | None = None) -> Mock:
        query, params = str(statement), params or {}
        result = Mock()
        if query == "SELECT * FROM instance_control WHERE id = 1 FOR UPDATE":
            result.mappings.return_value.one.return_value = dict(instance)
        elif query == "SELECT * FROM supervisor_lease WHERE id = 1 FOR UPDATE":
            result.mappings.return_value.one.return_value = dict(lease)
        elif query == "SELECT clock_timestamp()":
            result.scalar_one.return_value = now
        elif query == "SELECT 1 FROM instance_stop_fence WHERE id = 1":
            result.scalar_one_or_none.return_value = 1 if fenced else None
        elif query.startswith("SELECT * FROM instance_command"):
            result.mappings.return_value.one_or_none.return_value = receipts.get(params["command"])
        elif query.startswith("SELECT 1 FROM instance_command"):
            result.scalar_one_or_none.return_value = 1 if case == "receipt" else None
        elif query.startswith("UPDATE supervisor_lease SET owner"):
            lease.update(owner=params["owner"], epoch=2, expires_at=now + timedelta(seconds=5))
            result.scalar_one.return_value = 2
        elif query.startswith("UPDATE instance_control SET admission_open"):
            instance.update(
                admission_open=False,
                generation=params.get("generation", generation + 1),
                shutdown_command_id=params["command"],
                quiesced_generation=None,
                quiesced_at=None,
            )
        elif query.startswith("UPDATE instance_control SET quiesced_generation"):
            instance.update(quiesced_generation=instance["generation"], quiesced_at=now)
        elif query.startswith("INSERT INTO instance_command"):
            receipts[params["command"]] = dict(
                command_id=params["command"],
                kind=params["kind"],
                expected_generation=params["expected"],
                result_generation=params["result"],
                owner_epoch=params["epoch"],
            )
        else:
            raise AssertionError(query)
        return result

    connection = Mock(execute=AsyncMock(side_effect=execute))

    @asynccontextmanager
    async def begin() -> AsyncIterator[Mock]:
        yield connection

    service = InstanceService(Mock(begin=begin))
    # T1 opt-in is deliberately not a request payload or a public HTTP option.
    service.recover_owner_loss = True
    if case == "live_lease":
        lease["expires_at"] = now + timedelta(seconds=5)
        with pytest.raises(ControlConflict, match="SUPERVISOR_OWNED"):
            await service.acquire(owner)
        assert instance["admission_open"] is True and not receipts
        return
    epoch = await service.acquire(owner)
    implicit = instance["shutdown_command_id"]
    assert instance["admission_open"] is False
    await service.quiesce(owner, epoch)
    command = uuid4()
    expected = generation + 1
    if case == "profile":
        service.recover_owner_loss = False
    elif case == "owner":
        owner = uuid4()
    elif case == "epoch":
        epoch += 1
    elif case == "generation":
        expected -= 1
    elif case in {"quiescence", "drain"}:
        instance["quiesced_generation"] = None
        if case == "drain":
            service.runtime_drain = AsyncMock(return_value=False)
            with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
                await service.quiesce(owner, epoch)
    elif case == "fence":
        fenced = True
    elif case == "already_commanded":
        instance["shutdown_command_id"] = uuid4()
    elif case == "overflow":
        expected = 9223372036854775807
    if case not in {"valid", "maximum"}:
        before = dict(instance)
        with pytest.raises(ControlConflict):
            await service.shutdown(command, expected, owner, epoch)
        assert instance == before and command not in receipts
        return
    assert await service.shutdown(command, expected, owner, epoch) == expected + 1
    assert implicit not in receipts
    assert receipts[command] == dict(
        command_id=command,
        kind="SHUTDOWN",
        expected_generation=expected,
        result_generation=expected + 1,
        owner_epoch=epoch,
    )
    assert instance["admission_open"] is False
    assert await service.shutdown(command, expected, owner, epoch) == expected + 1
    with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
        await service.shutdown(command, expected - 1, owner, epoch)
    with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
        await service.shutdown(uuid4(), expected + 1, owner, epoch)


def test_shutdown_wire_maximum_and_rejected_inputs_source() -> None:
    import json

    from pydantic import ValidationError

    from omnis.modules.instance.schemas import ControlRequest, InstanceView, LifecycleCommand

    command = LifecycleCommand(
        op="shutdown",
        instance_id=uuid4(),
        command_id=uuid4(),
        expected_generation=9223372036854775806,
    )
    frame = ControlRequest.model_validate(
        dict(version=1, capability="f" * 64, command=command.model_dump(mode="json"))
    )
    encoded = json.dumps(frame.model_dump(mode="json")).encode() + b"\n"
    assert len(encoded) <= 4096
    assert ControlRequest.model_validate_json(encoded) == frame
    for invalid in (True, -1, 9223372036854775807, "2", 2.0):
        with pytest.raises(ValidationError):
            LifecycleCommand.model_validate(
                {**command.model_dump(mode="json"), "expected_generation": invalid}
            )
    view = InstanceView.model_validate(
        dict(
            instance_id=command.instance_id,
            generation=9223372036854775807,
            admission_open=False,
            shutdown_command_id=command.command_id,
            quiesced_generation=9223372036854775807,
            supervisor_epoch=9223372036854775807,
            supervisor_ready=True,
            shutdown_finalized=True,
            assessment_ready=False,
            dashboard_ready=False,
        )
    )
    reply = dict(
        ok=True,
        correlation_id=str(uuid4()),
        result_generation=view.generation,
        status=view.model_dump(mode="json"),
        command_id=str(command.command_id),
        expected_generation=command.expected_generation,
        owner_epoch=view.supervisor_epoch,
    )
    assert len(json.dumps(reply).encode()) + 1 <= 4096


@pytest.mark.asyncio
async def test_recovery_private_shutdown_pg(
    migrated_database_url: URL, ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real CLI frame, LocalControl and PG receipts; no Docker/provider effect."""
    import importlib
    import json
    import os
    from unittest.mock import Mock

    from psycopg import sql

    from conftest import connect_test_database
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService
    from omnis.transport.local_control import LocalControl
    from test_stop_fence import db_snapshot

    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "cli/src"))
    client = importlib.import_module("omnis_cli.control")
    recovery = importlib.import_module("omnis_cli.recover")
    assert recovery.__file__ is not None
    assert Path(recovery.__file__).resolve() == root / "cli/src/omnis_cli/recover.py"
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    old, owner, opened, command, finalized = (uuid4() for _ in range(5))
    try:
        epoch = await service.acquire(old)
        await service.open(opened, 0, old, epoch)
        identity = (await service.status()).instance_id
        record = dict(
            instance_id=str(identity),
            generation=1,
            supervisor_epoch=epoch,
            open_command=str(opened),
            containers={"db": "d" * 64, "api": "a" * 64, "supervisor": "b" * 64},
        )
        with connect_test_database(migrated_database_url, autocommit=True) as connection:
            connection.execute("SET default_transaction_read_only = on")

            def psql(cid: str, query: str) -> str:
                assert cid == "d" * 64 and query.startswith("SELECT ")
                row = connection.execute(sql.SQL(query)).fetchone()
                assert row is not None
                return json.dumps(row[0])

            runtime = Mock(psql=psql)
            with pytest.raises(recovery.StartError, match="RECOVERY_AUTHORITY_UNVERIFIED"):
                recovery._owner(runtime, record)
            with pytest.raises(ControlConflict, match="SUPERVISOR_OWNED"):
                await service.acquire(owner)
            async with engine.begin() as db:
                await db.execute(
                    text(
                        "UPDATE supervisor_lease SET expires_at=clock_timestamp()-interval '1 second' WHERE id=1"
                    )
                )
            assert recovery._owner(runtime, record) == str(old)
            replacement = InstanceService(engine)
            replacement.recover_owner_loss = True
            next_epoch = await replacement.acquire(owner)
            implicit = (await replacement.status()).shutdown_command_id
            assert next_epoch == epoch + 1 and implicit is not None
            with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
                await replacement.shutdown(command, 2, owner, next_epoch)

            async def refused_drain() -> bool:
                return False

            replacement.runtime_drain = refused_drain
            with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
                await replacement.quiesce(owner, next_epoch)
            replacement.runtime_drain = None
            await replacement.quiesce(owner, next_epoch)
            assert recovery._owner(runtime, record, {"shutdown_command_id": str(implicit)}) == str(
                owner
            )
            async with LocalControl(ipc_directory, replacement, owner, next_epoch):
                payload = dict(
                    op="shutdown",
                    instance_id=str(identity),
                    command_id=str(command),
                    expected_generation=2,
                )
                before = await db_snapshot(engine)
                for wrong in (
                    {**payload, "instance_id": str(uuid4())},
                    {**payload, "expected_generation": 1},
                ):
                    with pytest.raises(client.ControlUnavailable):
                        await asyncio.to_thread(
                            client.request, ipc_directory, wrong, peer_pid=os.getpid()
                        )
                    assert await db_snapshot(engine) == before
                closed = await asyncio.to_thread(
                    client.request, ipc_directory, payload, peer_pid=os.getpid()
                )
                assert closed["generation"] == 3 and closed["admission_open"] is False
                assert closed["shutdown_command_id"] == str(command)
                committed = await db_snapshot(engine)
                assert await asyncio.to_thread(client.request, ipc_directory, payload) == closed
                for wrong in (
                    {**payload, "expected_generation": 3},
                    {**payload, "command_id": str(uuid4()), "expected_generation": 3},
                ):
                    with pytest.raises(client.ControlUnavailable):
                        await asyncio.to_thread(client.request, ipc_directory, wrong)
                    assert await db_snapshot(engine) == committed
                await replacement.quiesce(owner, next_epoch)
                done = await asyncio.to_thread(
                    client.request,
                    ipc_directory,
                    dict(
                        op="finalize",
                        instance_id=str(identity),
                        command_id=str(finalized),
                        expected_generation=3,
                    ),
                )
                assert done["shutdown_finalized"] is True
                grant = await asyncio.to_thread(
                    client.request,
                    ipc_directory,
                    dict(
                        op="arm_stop",
                        instance_id=str(identity),
                        command_id=str(command),
                        finalize_command_id=str(finalized),
                        generation=3,
                        owner_epoch=next_epoch,
                        daemon_id="synthetic-pg-no-daemon",
                        inventory={"db": "d" * 64},
                    ),
                )
                assert grant["owner_uuid"] == str(owner) and grant["generation"] == 3
                before = await db_snapshot(engine)
                with pytest.raises(ControlConflict, match="STOP_IN_PROGRESS"):
                    await replacement.acquire(uuid4())
                assert await db_snapshot(engine) == before
            async with engine.connect() as db:
                receipts = (
                    await db.execute(
                        text(
                            "SELECT command_id,kind,expected_generation,result_generation,owner_epoch FROM instance_command ORDER BY result_generation,kind"
                        )
                    )
                ).all()
                assert [tuple(row) for row in receipts] == [
                    (opened, "OPEN", 0, 1, epoch),
                    (finalized, "FINALIZE", 3, 3, next_epoch),
                    (command, "SHUTDOWN", 2, 3, next_epoch),
                ]
                assert all(row[0] != implicit for row in receipts)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("renewal", ["startup", "heartbeat"])
async def test_startup_lease_is_bounded_preserved_and_cannot_resurrect_pg(
    migrated_database_url: URL,
    renewal: str,
) -> None:
    import time

    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        ordinary = await service.runtime_authority(owner, epoch, 0, inert_probe=True)
        assert 0 < ordinary.deadline_ns - time.monotonic_ns() <= 4_500_000_000
        for startup in (True, "renew"):
            with pytest.raises(ControlConflict):
                await service.runtime_authority(owner, epoch, 0, inert_probe=True, startup=startup)
        with pytest.raises(ControlConflict):
            await service.runtime_authority(uuid4(), epoch, 0, inert_probe=True, startup="launch")
        grant = await service.runtime_authority(owner, epoch, 0, inert_probe=True, startup="launch")
        assert 9_000_000_000 < grant.deadline_ns - time.monotonic_ns() <= 10_000_000_000
        async with engine.connect() as conn:
            expiry = (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one()
            remaining = (
                await conn.execute(
                    text(
                        "SELECT EXTRACT(EPOCH FROM expires_at-clock_timestamp()) FROM supervisor_lease WHERE id=1"
                    )
                )
            ).scalar_one()
            assert 10 < remaining <= 11
        await service.heartbeat(owner, epoch)
        async with engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one() == expiry
        ordinary = await service.runtime_authority(owner, epoch, 0, inert_probe=True)
        assert 0 < ordinary.deadline_ns - time.monotonic_ns() <= 4_500_000_000
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at=clock_timestamp()+interval '5 seconds' WHERE id=1"
                )
            )
        await service.heartbeat(owner, epoch)
        async with engine.connect() as conn:
            assert (
                await conn.execute(
                    text(
                        "SELECT EXTRACT(EPOCH FROM expires_at-clock_timestamp()) FROM supervisor_lease WHERE id=1"
                    )
                )
            ).scalar_one() <= 5
        # Actual blocking UPDATE crosses the original expiry; the extension must roll back.
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SEQUENCE lease_update_entries"))
            await conn.execute(
                text(
                    "CREATE FUNCTION delay_lease_update() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN PERFORM nextval('lease_update_entries'); PERFORM pg_sleep(0.3); RETURN NEW; END $$"
                )
            )
            await conn.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at=clock_timestamp()+interval '0.2 seconds' WHERE id=1"
                )
            )
            await conn.execute(
                text(
                    "CREATE TRIGGER delay_lease BEFORE UPDATE ON supervisor_lease FOR EACH ROW EXECUTE FUNCTION delay_lease_update()"
                )
            )
            original = (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one()
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            if renewal == "startup":
                await service.runtime_authority(owner, epoch, 0, inert_probe=True, startup="launch")
            else:
                await service.heartbeat(owner, epoch)
        async with engine.connect() as conn:
            # nextval survives rollback; elapsed time could be a pre-UPDATE wait.
            assert (
                await conn.execute(text("SELECT last_value, is_called FROM lease_update_entries"))
            ).one() == (1, True)
            assert (
                await conn.execute(text("SELECT expires_at FROM supervisor_lease WHERE id=1"))
            ).scalar_one() == original
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_shutdown_serializes_with_real_admission_and_requires_explicit_restart(
    migrated_database_url: URL,
) -> None:
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        startup = uuid4()
        generation = await service.open(startup, 0, owner, epoch)
        assert generation == 1
        assert await service.open(startup, 0, owner, epoch) == generation
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE inert_marker (generation bigint NOT NULL)"))
        # This is only a fully transactional inert marker, never an external effect.
        entered = asyncio.Event()
        finish = asyncio.Event()

        async def admitted() -> None:
            async with service.admission(generation, owner, epoch) as connection:
                entered.set()
                await finish.wait()
                await connection.execute(
                    text("INSERT INTO inert_marker VALUES (:generation)"),
                    {"generation": generation},
                )

        work = asyncio.create_task(admitted())
        await entered.wait()
        stop_id = uuid4()
        stopping = asyncio.create_task(service.shutdown(stop_id, generation, owner, epoch))
        await asyncio.sleep(0.05)
        assert not stopping.done()
        finish.set()
        await work
        closed_generation = await stopping
        assert closed_generation == 2
        assert await service.shutdown(stop_id, generation, owner, epoch) == closed_generation
        with pytest.raises(ControlConflict, match="INSTANCE_SHUTTING_DOWN"):
            async with service.admission(closed_generation, owner, epoch):
                pytest.fail("closed instance admitted work")
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.open(uuid4(), closed_generation, owner, epoch)
        await service.quiesce(owner, epoch)
        await service.finalize(uuid4(), closed_generation, owner, epoch)
        with pytest.raises(ControlConflict, match="RESTART_REQUIRED"):
            await service.open(uuid4(), closed_generation, owner, epoch)
        await service.release(owner, epoch)
        new_owner = uuid4()
        new_epoch = await service.acquire(new_owner)
        assert new_epoch > epoch
        assert (await service.status()).admission_open is False
        reopened = await service.open(uuid4(), closed_generation, new_owner, new_epoch)
        assert reopened == 3
        # A historical retry never reopens, shuts down or changes a new generation.
        assert (
            await service.shutdown(stop_id, generation, new_owner, new_epoch) == closed_generation
        )
        assert (await service.status()).generation == reopened
        with pytest.raises(ControlConflict, match="COMMAND_CONFLICT"):
            await service.shutdown(stop_id, reopened, new_owner, new_epoch)
        with pytest.raises(ControlConflict, match="GENERATION_CONFLICT"):
            await service.shutdown(uuid4(), generation, new_owner, new_epoch)
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT generation FROM inert_marker"))
            ).scalars().all() == [generation]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("cut", ["settlement", "refusal", "takeover", "generation", "expired"])
async def test_quiescence_drains_without_sql_locks_and_revalidates_pg(
    migrated_database_url: URL, cut: str
) -> None:
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    replacement = uuid4()
    epoch = await service.acquire(owner)
    generation = await service.open(uuid4(), 0, owner, epoch)
    closed = await service.shutdown(uuid4(), generation, owner, epoch)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE drain_settlement (generation bigint NOT NULL)"))

    async def drain() -> bool:
        # The real settlement transaction uses the same authority rows as the sender.
        async with service._locked() as (connection, instance, lease):
            await service._require_owner(connection, lease, owner, epoch)
            assert instance.generation == closed
            await connection.execute(
                text("INSERT INTO drain_settlement VALUES (:generation)"),
                {"generation": closed},
            )
            if cut == "expired":
                await connection.execute(
                    text(
                        "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second' WHERE id = 1"
                    )
                )
            if cut == "generation":
                await connection.execute(
                    text("UPDATE instance_control SET generation = generation + 1 WHERE id = 1")
                )
        if cut == "takeover":
            await service.release(owner, epoch)
            await service.acquire(replacement)
        return cut != "refusal"

    service.runtime_drain = drain
    try:
        if cut == "settlement":
            await service.quiesce(owner, epoch)
        else:
            reason = (
                "LEASE_LOST"
                if cut in {"takeover", "expired"}
                else ("GENERATION_CONFLICT" if cut == "generation" else "SHUTDOWN_INCOMPLETE")
            )
            with pytest.raises(ControlConflict, match=reason):
                await service.quiesce(owner, epoch)
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM drain_settlement"))
            ).scalar_one() == 1
            quiesced = (
                await connection.execute(text("SELECT quiesced_generation FROM instance_control"))
            ).scalar_one()
            assert quiesced == (closed if cut == "settlement" else None)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_owner_is_fenced_and_takeover_never_reopens(
    migrated_database_url: URL,
) -> None:
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    try:
        epoch = await service.acquire(owner)
        with pytest.raises(ControlConflict, match="SUPERVISOR_OWNED"):
            await service.acquire(uuid4())
        generation = await service.open(uuid4(), 0, owner, epoch)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at = clock_timestamp() - interval '1 second'"
                )
            )
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            async with service.admission(generation, owner, epoch):
                pytest.fail("expired owner admitted work")
        replacement = uuid4()
        next_epoch = await service.acquire(replacement)
        status = await service.status()
        assert status.admission_open is False and status.shutdown_command_id is not None
        assert status.generation > generation and next_epoch > epoch
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.heartbeat(owner, epoch)
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await service.quiesce(owner, epoch)
        await service.quiesce(replacement, next_epoch)
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.open(uuid4(), status.generation, replacement, next_epoch)
    finally:
        await engine.dispose()
