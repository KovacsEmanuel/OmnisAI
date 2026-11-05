"""Finite migration preconditions; synthetic stopped history, no provider IO."""

import asyncio
import json
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core import db, schema
from omnis.core.db import database_engine, schema_reason_on
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import StopReconciliation
from test_mission_revision_schema import SOURCE_OIDS, source_catalog_connection
from test_stop_reconcile import reconciliation_payload


def test_upgrade_job_sanitizes_unsafe_configuration(tmp_path: Path) -> None:
    body = reconciliation_payload()
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "omnis.migrate", "--upgrade-t1"],
        cwd=tmp_path,
        env={"OMNIS_DATABASE_URL": "synthetic-secret-marker"},
        input=json.dumps(body).encode(),
        capture_output=True,
        timeout=8,
    )
    assert result.returncode == 4
    assert result.stderr == b""
    assert b"synthetic-secret-marker" not in result.stdout
    assert json.loads(result.stdout)["ok"] is False


def migrate_to(revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(files("omnis.migrations")))
    command.upgrade(config, revision)


def test_previous_physical_schema_is_not_api_readiness(
    empty_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", empty_database_url.render_as_string(hide_password=False)
    )
    migrate_to("0016_provider_models")

    async def probe() -> None:
        engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
        try:
            async with engine.begin() as connection:
                assert await schema_reason_on(connection) is not None
                previous = getattr(schema, "schema0016_matches", None)
                assert callable(previous), "Migration lacks the separate physical0016 verifier"
                assert await previous(connection)
                await connection.execute(
                    text(
                        "ALTER TABLE provider_model_entry DROP CONSTRAINT provider_model_entry_model_check"
                    )
                )
                assert not await previous(connection)
        finally:
            await engine.dispose()

    asyncio.run(probe())


@pytest.mark.parametrize("s1", [False, True])
def test_finite_upgrade_retains_stop_fence_and_rejects_replay(
    empty_database_url: URL, monkeypatch: pytest.MonkeyPatch, s1: bool
) -> None:
    from omnis import migrate

    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", empty_database_url.render_as_string(hide_password=False)
    )
    migrate_to("0017_model_removal" if s1 else "0016_provider_models")
    body = reconciliation_payload()

    async def stopped() -> dict[str, object]:
        engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
        try:
            async with engine.begin() as connection:
                system = (
                    await connection.execute(
                        text("SELECT system_identifier::text FROM pg_control_system()")
                    )
                ).scalar_one()
                identity = (
                    await connection.execute(
                        text("SELECT instance_id FROM instance_control WHERE id=1")
                    )
                ).scalar_one()
                raw_grant = body["grant"]
                assert isinstance(raw_grant, dict)
                grant = dict(raw_grant)
                grant.update(instance_id=str(identity), owner_uuid=str(uuid4()))
                body.update(system_identifier=system, grant=grant)
                await connection.execute(
                    text(
                        "UPDATE instance_control SET generation=2, admission_open=FALSE, shutdown_command_id=:command, quiesced_generation=2, quiesced_at=clock_timestamp() WHERE id=1"
                    ),
                    {"command": grant["command_id"]},
                )
                await connection.execute(
                    text(
                        "UPDATE supervisor_lease SET epoch=1, owner=NULL, expires_at=NULL WHERE id=1"
                    )
                )
                for kind, expected, command_id in (
                    ("SHUTDOWN", 1, grant["command_id"]),
                    ("FINALIZE", 2, grant["finalize_command_id"]),
                ):
                    await connection.execute(
                        text(
                            "INSERT INTO instance_command(command_id,kind,expected_generation,result_generation,owner_epoch) VALUES (:id,:kind,:expected,2,1)"
                        ),
                        {"id": command_id, "kind": kind, "expected": expected},
                    )
                import json

                await connection.execute(
                    text(
                        "INSERT INTO instance_stop_fence(id,instance_id,command_id,finalize_command_id,owner_uuid,generation,owner_epoch,daemon_id,inventory,state) VALUES (1,:instance,:command,:finalized,:owner,2,1,:daemon,CAST(:inventory AS jsonb),'STOP_PENDING')"
                    ),
                    {
                        "instance": identity,
                        "command": grant["command_id"],
                        "finalized": grant["finalize_command_id"],
                        "owner": grant["owner_uuid"],
                        "daemon": grant["daemon_id"],
                        "inventory": json.dumps(grant["inventory"]),
                    },
                )
                return body
        finally:
            await engine.dispose()

    body = asyncio.run(stopped())
    request = StopReconciliation.model_validate(body)
    monkeypatch.setenv("OMNIS_EXPECTED_SYSTEM_ID", request.system_identifier)
    upgrade = getattr(migrate, "upgrade_t1", None)
    assert callable(upgrade), "Migrator lacks finite stopped0016→0017 admission"
    # A mismatched finalized receipt must deny before DDL and preserve the stamp.
    bad = request.model_copy(update={"grant": request.grant.model_copy(update={"generation": 3})})
    with pytest.raises((ValueError, RuntimeError)):
        upgrade(bad, s1=s1)
    upgrade(request, s1=s1)
    with pytest.raises((ValueError, RuntimeError)):
        upgrade(request, s1=s1)

    async def verify() -> None:
        engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
        try:
            async with engine.connect() as connection:
                if s1:
                    assert await schema_reason_on(connection) is None
                else:
                    assert await db.schema0017_reason_on(connection) is None
                    assert (
                        await schema_reason_on(connection) is db.ReadinessReason.SCHEMA_INCOMPATIBLE
                    )
                service = InstanceService(engine)
                stored = await service._grant(connection)
                assert stored is not None
                assert stored.model_dump(mode="json") == request.grant.model_dump(mode="json")
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM instance_stop_reconciliation")
                    )
                ).scalar_one() == 0
                assert (
                    await connection.execute(
                        text("SELECT admission_open FROM instance_control WHERE id=1")
                    )
                ).scalar_one() is False
        finally:
            await engine.dispose()

    asyncio.run(verify())


def source_t1_connection(physical: str, stamp: str, mutation: str = "none") -> Mock:
    """Real comparators over synthetic catalog rows; never opens PostgreSQL."""
    connection = source_catalog_connection()
    catalog_execute = connection.execute
    columns = [
        ("id", "smallint", True, "nextval('instance_control_id_seq'::regclass)"),
        ("instance_id", "uuid", True, "gen_random_uuid()"),
        ("admission_open", "boolean", True, "false"),
        ("shutdown_command_id", "uuid", False, None),
        ("generation", "bigint", True, "0"),
        ("quiesced_generation", "bigint", False, None),
        ("quiesced_at", "timestamp with time zone", False, None),
    ]

    async def execute(statement: object, parameters: dict[str, object] | None = None) -> Mock:
        query = str(statement)
        result = Mock()
        if query == "SELECT version_num FROM alembic_version":
            result.scalars.return_value.all.return_value = [stamp]
        elif "FROM instance_control WHERE id = 1" in query:
            result.first.return_value = (1, str(uuid4()), False, None, 0, None, None)
        elif "'instance_control'::regclass" in query:
            if "pg_attribute" in query:
                result.all.return_value = columns[:-1] if mutation == "instance" else columns
            else:
                result.all.return_value = [
                    ("instance_control_pkey", "p", "PRIMARY KEY (id)", True, True),
                    ("instance_control_instance_id_key", "u", "UNIQUE (instance_id)", True, True),
                    ("ck_instance_control_singleton", "c", "CHECK ((id = 1))", True, True),
                    (
                        "ck_instance_control_generation",
                        "c",
                        "CHECK ((generation >= 0))",
                        True,
                        True,
                    ),
                    *[
                        (f"instance_control_{name}_not_null", "n", f"NOT NULL {name}", True, True)
                        for name, _, required, _ in columns
                        if required
                    ],
                ]
        elif (
            parameters == {"table": "public.model_relay_authority"}
            and physical != db.SCHEMA_REVISION
        ):
            result.all.return_value = []
        else:
            result = await catalog_execute(statement, parameters)
            assert isinstance(result, Mock)
            if parameters == {"table": "public.provider_model_entry"} and mutation == "physical":
                result.all.return_value = [
                    (
                        SOURCE_OIDS["provider_model_entry"],
                        "foreign",
                        "provider_model_entry",
                        "r",
                        "p",
                    )
                ]
            if parameters == {"table": "provider_model_entry"}:
                rows = result.all.return_value
                if "pg_attribute" in query and (
                    physical == "0016_provider_models" or mutation == "column"
                ):
                    result.all.return_value = [
                        row for row in rows if row[0] != "removed_registry_revision"
                    ]
                elif "pg_constraint" in query and physical == "0016_provider_models":
                    result.all.return_value = [
                        row for row in rows if row[0] != "provider_model_removed_registry_fk"
                    ] + [
                        (
                            "provider_model_entry_instance_id_connection_id_model_key",
                            "u",
                            "UNIQUE (instance_id, connection_id, model)",
                            True,
                            True,
                        )
                    ]
                elif "pg_trigger" in query:
                    if physical == "0016_provider_models":
                        result.all.return_value = [(rows[0][0], 58, *rows[0][2:])]
                    elif mutation == "retire":
                        result.all.return_value = rows[:1]
            if (
                "public.provider_model_available_unique" in query
                and physical == "0016_provider_models"
            ):
                result.one_or_none.return_value = None
        return result

    connection.execute = AsyncMock(side_effect=execute)
    return connection


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "physical", ["0016_provider_models", "0017_model_removal", db.SCHEMA_REVISION]
)
@pytest.mark.parametrize(
    "check", ["schema0016_reason_on", "schema0017_reason_on", "schema_reason_on"]
)
@pytest.mark.parametrize("mutation", ["none", "stamp", "physical", "column", "retire", "instance"])
async def test_source_finite_schema_postcondition(
    monkeypatch: pytest.MonkeyPatch, physical: str, check: str, mutation: str
) -> None:
    probe = {
        "schema0016_reason_on": db.schema0016_reason_on,
        "schema0017_reason_on": db.schema0017_reason_on,
        "schema_reason_on": db.schema_reason_on,
    }[check]
    expected = {
        "schema0016_reason_on": "0016_provider_models",
        "schema0017_reason_on": "0017_model_removal",
        "schema_reason_on": db.SCHEMA_REVISION,
    }[check]
    stamp = "wrong_stamp" if mutation == "stamp" else expected
    connection = source_t1_connection(physical, stamp, mutation)
    run_check = AsyncMock(return_value=physical == db.SCHEMA_REVISION)
    monkeypatch.setattr(db, "run_schema_matches", run_check)
    valid = physical == expected and mutation == "none"
    # 0016 has no retirement column/trigger; these mutations have no effect there.
    if physical == expected == "0016_provider_models" and mutation in {"column", "retire"}:
        valid = True
    # Later schemas retain the complete physical0017 contract, but not its stamp.
    if physical == db.SCHEMA_REVISION and expected == "0017_model_removal" and mutation == "none":
        valid = True
    assert await probe(connection) is (None if valid else db.ReadinessReason.SCHEMA_INCOMPATIBLE)
    if check != "schema_reason_on":
        run_check.assert_not_awaited()
    elif valid:
        run_check.assert_awaited_once_with(connection)


@pytest.mark.parametrize("s1", [False, True])
@pytest.mark.parametrize("mutation", ["none", "column", "retire", "stamp"])
def test_source_upgrade_env_uses_finite_postcheck(
    monkeypatch: pytest.MonkeyPatch, mutation: str, s1: bool
) -> None:
    import runpy

    from alembic import context

    from omnis import migrate

    request = StopReconciliation.model_validate(reconciliation_payload())
    revision = "0019_agent_runs" if s1 else "0017_model_removal"
    monkeypatch.setattr(db, "run_schema_matches", AsyncMock(return_value=True))
    connection = source_t1_connection(
        revision,
        "wrong_stamp" if mutation == "stamp" else revision,
        mutation,
    )
    connection.run_sync = AsyncMock()
    engine = Mock()
    engine.begin.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    engine.dispose = AsyncMock()
    config = Config()
    config.attributes["s1_upgrade" if s1 else "t1_upgrade"] = request
    monkeypatch.setenv("OMNIS_DATABASE_URL", "postgresql+psycopg://synthetic@localhost/unused")
    monkeypatch.setattr(context, "config", config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.create_async_engine", lambda *args, **kwargs: engine
    )
    admission = AsyncMock()
    monkeypatch.setattr(migrate, "admit_t1_upgrade", admission)
    env_path = str(Path(__file__).parents[1] / "src/omnis/migrations/env.py")
    if mutation == "none":
        runpy.run_path(env_path)
    else:
        with pytest.raises(
            RuntimeError,
            match="Physical0019 readback required" if s1 else "Physical0017 readback required",
        ):
            runpy.run_path(env_path)
    admission.assert_awaited_once_with(connection, engine, request, s1=s1)
    connection.run_sync.assert_awaited_once()
    engine.dispose.assert_awaited_once()


@pytest.mark.parametrize("s1", [False, True])
def test_source_upgrade_target_remains_finite(monkeypatch: pytest.MonkeyPatch, s1: bool) -> None:
    from omnis import migrate

    request = StopReconciliation.model_validate(reconciliation_payload())
    monkeypatch.setenv("OMNIS_EXPECTED_SYSTEM_ID", request.system_identifier)
    upgrade = Mock()
    monkeypatch.setattr(command, "upgrade", upgrade)
    migrate.upgrade_t1(request, s1=s1)
    assert upgrade.call_args.args[1] == ("0019_agent_runs" if s1 else "0017_model_removal")
    assert upgrade.call_args.args[0].attributes["s1_upgrade" if s1 else "t1_upgrade"] == request


@pytest.mark.asyncio
@pytest.mark.parametrize("s1", [False, True])
@pytest.mark.parametrize("fault", ["none", "schema", "foreign", "uncertain", "unsettled"])
async def test_source_finite_admission_keeps_original_closed_grant(
    monkeypatch: pytest.MonkeyPatch, s1: bool, fault: str
) -> None:
    from datetime import datetime, timezone

    from omnis import migrate
    from omnis.modules.instance.records import InstanceRecord, LeaseRecord

    request = StopReconciliation.model_validate(reconciliation_payload())
    if fault == "uncertain":
        request = request.model_copy(
            update={"grant": request.grant.model_copy(update={"state": "STOP_UNCERTAIN"})}
        )
    check = AsyncMock(return_value="incompatible" if fault == "schema" else None)
    monkeypatch.setattr(migrate, "schema0017_reason_on" if s1 else "schema0016_reason_on", check)
    now = datetime.now(timezone.utc)
    instance = InstanceRecord(
        id=1,
        instance_id=request.grant.instance_id,
        admission_open=False,
        shutdown_command_id=request.grant.command_id,
        generation=request.grant.generation,
        quiesced_generation=request.grant.generation,
        quiesced_at=now,
    )
    lease = LeaseRecord(
        id=1, owner=request.grant.owner_uuid, epoch=request.grant.owner_epoch, expires_at=now
    )
    connection, engine = Mock(), Mock()
    rows = [Mock(), Mock(), Mock()]
    rows[0].mappings.return_value.one.return_value = instance.model_dump()
    rows[1].mappings.return_value.one.return_value = lease.model_dump()
    rows[2].scalar_one.return_value = fault == "unsettled"
    connection.execute = AsyncMock(side_effect=rows)
    grant = (
        request.grant.model_copy(update={"owner_uuid": uuid4()})
        if fault == "foreign"
        else request.grant
    )
    read_grant, closed = AsyncMock(return_value=grant), AsyncMock()
    monkeypatch.setattr(InstanceService, "_grant", read_grant)
    monkeypatch.setattr(InstanceService, "_closed_stop", closed)
    if fault == "none":
        await migrate.admit_t1_upgrade(connection, engine, request, s1=s1)
    else:
        with pytest.raises(
            ValueError,
            match={
                "schema": "Physical0017 required" if s1 else "Physical0016 required",
                "foreign": "Exact stopped grant required",
                "uncertain": "Exact stopped grant required",
                "unsettled": "Unsettled operations",
            }[fault],
        ):
            await migrate.admit_t1_upgrade(connection, engine, request, s1=s1)
    if fault in ("none", "unsettled"):
        closed.assert_awaited_once_with(connection, instance, lease, request.grant)
    else:
        closed.assert_not_awaited()
    queries = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert all(query.startswith("SELECT") for query in queries)
    if fault != "schema":
        assert "FOR UPDATE" in queries[0] and "FOR UPDATE" in queries[1]


@pytest.mark.parametrize("s1", [False, True])
def test_source_finite_job_uses_unchanged_bounded_parser(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path, s1: bool
) -> None:
    from omnis import migrate, stop_reconcile
    from omnis.modules.instance.stop_contract import canonical_json

    request = StopReconciliation.model_validate(reconciliation_payload())
    path = tmp_path / "request"
    raw = canonical_json(request.model_dump(mode="json")).encode()
    path.write_bytes(raw + b" " * (16384 - len(raw)))
    original = stop_reconcile.read_request
    with path.open("rb") as stream:
        monkeypatch.setattr(stop_reconcile, "read_request", lambda: original(stream.fileno()))
        job = Mock()
        monkeypatch.setattr(migrate, "upgrade_t1", job)
        monkeypatch.setattr(
            sys, "argv", ["omnis.migrate", "--upgrade-s1" if s1 else "--upgrade-t1"]
        )
        with pytest.raises(SystemExit) as exit_info:
            migrate.main()
    assert exit_info.value.code == 0
    job.assert_called_once_with(request, s1=s1)
    response = json.loads(capsys.readouterr().out)
    assert response == {
        "ok": True,
        "schema": "0019_agent_runs" if s1 else "0017_model_removal",
        "request": request.model_dump(mode="json"),
    }
    path.write_bytes(raw + b" " * (16385 - len(raw)))
    with path.open("rb") as stream:
        with pytest.raises(ValueError, match="input too large"):
            original(stream.fileno())


@pytest.mark.asyncio
@pytest.mark.parametrize("revision", ["0016_provider_models", "0017_model_removal"])
async def test_source_finite_stamp_is_not_current_api_readiness(revision: str) -> None:
    connection = source_t1_connection(revision, revision)
    assert await schema_reason_on(connection) is db.ReadinessReason.SCHEMA_INCOMPATIBLE
