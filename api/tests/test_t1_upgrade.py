"""Finite migration preconditions; synthetic stopped history, no provider IO."""

import asyncio
import json
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core import schema
from omnis.core.db import database_engine, schema_reason_on
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import StopReconciliation
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


def test_finite_upgrade_retains_stop_fence_and_rejects_replay(
    empty_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnis import migrate

    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", empty_database_url.render_as_string(hide_password=False)
    )
    migrate_to("0016_provider_models")
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
        upgrade(bad)
    upgrade(request)
    with pytest.raises((ValueError, RuntimeError)):
        upgrade(request)

    async def verify() -> None:
        engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
        try:
            async with engine.connect() as connection:
                assert await schema_reason_on(connection) is None
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
