"""Admitted private-PG gate only; never run without the attested disposable fixture."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from omnis.core.db import database_engine, readiness_reason
from omnis.modules.runs import model_test_store as store


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, "0017_model_removal"])
async def test_relay_upgrade_preserves_records_and_original_authority(
    empty_database_url: URL, previous: str | None
) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": os.environ["PATH"],
        "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
    }

    def migrate(revision: str) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "alembic",
                "-c",
                str(root / "alembic.ini"),
                "upgrade",
                revision,
            ],
            cwd=root,
            env=env,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr.decode()

    engine = database_engine(empty_database_url.render_as_string(hide_password=False))
    retained = None
    historical = {"command_id": str(uuid4()), "historical": True}
    try:
        if previous:
            migrate(previous)
            async with engine.begin() as db:
                instance = str(
                    (
                        await db.execute(
                            text("SELECT instance_id FROM instance_control WHERE id=1")
                        )
                    ).scalar_one()
                )
                retained = await store.put(db, instance, "metadata-request", historical)
        migrate("head")
        assert await readiness_reason(engine) is None
        async with engine.begin() as db:
            instance = str(
                (
                    await db.execute(
                        text("SELECT instance_id FROM instance_control WHERE id=1 FOR UPDATE")
                    )
                ).scalar_one()
            )
            if retained:
                assert await store.resolve(db, instance, retained, "metadata-request") == historical
            fields = {
                "instance_id": instance,
                "kind": "MODEL_DISPATCH",
                "id": str(uuid4()),
                "execution_owner_id": str(uuid4()),
                "generation": 1,
                "owner_epoch": 1,
                "cancel_epoch": 1,
                "deadline": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
                "provider": "openrouter",
            }
            scope = await store.relay_scope(db, fields, allocate=True)
            assert scope.operation_serial == 1 and scope.id == fields["id"]
            assert await store.relay_scope(db, fields, allocate=True) == scope
        await engine.dispose()
        engine = database_engine(empty_database_url.render_as_string(hide_password=False))
        async with engine.begin() as db:
            await db.execute(text("SELECT id FROM instance_control WHERE id=1 FOR UPDATE"))
            assert await store.relay_scope(db, fields) == scope
            with pytest.raises(store.ModelConflict, match="RELAY_AUTHORITY_DENIED"):
                await store.relay_scope(db, {**fields, "owner_epoch": 2}, allocate=True)
            assert await store.relay_pending(db, instance) == (0, [scope])
            await store.retire_relay(db, scope)
            assert await store.relay_pending(db, instance) == (1, [])
            assert await store.relay_scope(db, fields, allocate=True) == scope
            with pytest.raises(store.ModelConflict):
                await store.relay_scope(db, fields)
            next_scope = await store.relay_scope(db, {**fields, "id": str(uuid4())}, allocate=True)
            assert next_scope.operation_serial == 2
        for statement in (
            "UPDATE model_relay_authority SET deadline='2099-01-01T00:00:00+00:00'",
            "UPDATE model_relay_authority SET state='ACTIVE' WHERE operation_serial=1",
            "DELETE FROM model_relay_authority",
            "TRUNCATE model_relay_authority",
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as db:
                    await db.execute(text(statement))
        async with engine.begin() as db:
            await db.execute(
                text("ALTER TABLE model_relay_authority DISABLE TRIGGER model_relay_guard")
            )
        assert await readiness_reason(engine) is not None
    finally:
        await engine.dispose()
