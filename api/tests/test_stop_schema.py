"""No-DB revision/contract checks; physical PostgreSQL gates remain separate."""

from importlib import import_module
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.core.db import SCHEMA_REVISION
from omnis.core.schema import AUTHORITY_TABLES, authority_schema_matches


def test_reconciliation_migration_quotes_reserved_grant_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = import_module("omnis.migrations.versions.0006_stop_reconciliation")
    operations = Mock()
    monkeypatch.setattr(migration, "op", operations)
    migration.upgrade()
    sql = "\n".join(str(call.args[0]) for call in operations.execute.call_args_list)
    assert '"grant" jsonb NOT NULL' in sql


@pytest.mark.parametrize("unconditional", [True, False])
@pytest.mark.asyncio
async def test_schema_refuses_conditional_immutability_trigger(unconditional: bool) -> None:
    # Driver rows are substituted; this exercises the real schema decision.
    responses = []
    for table, (columns, constraints) in AUTHORITY_TABLES.items():
        column_result = Mock()
        column_result.all.return_value = [(name, *spec) for name, spec in columns.items()]
        constraint_result = Mock()
        required = {
            (f"{table}_{name}_not_null", "n", f"NOT NULL {name}", True, True)
            for name, (_, not_null, _) in columns.items()
            if not_null
        }
        constraint_result.all.return_value = list(constraints | required)
        responses.extend([column_result, constraint_result])
    trigger = Mock()
    trigger.all.return_value = [
        (
            "stop_reconciliation_immutable",
            58,
            "O",
            "reject_stop_reconciliation_mutation",
            "BEGIN\n        RAISE EXCEPTION 'Stop reconciliation receipts are immutable';\n        END;",
            "plpgsql",
            False,
            0,
            0,
            unconditional,
            "",
            "trigger",
        )
    ]
    singleton = Mock()
    singleton.one.return_value = (True, True)

    async def execute(statement: object, parameters: object = None) -> Mock:
        if "FROM pg_trigger" in str(statement):
            if "t.tgqual IS NULL" not in str(statement):
                trigger.all.return_value = [row[:9] for row in trigger.all.return_value]
            return trigger
        if not responses:
            return singleton
        return responses.pop(0)

    connection = Mock(spec=AsyncConnection)
    connection.execute = AsyncMock(side_effect=execute)
    assert await authority_schema_matches(connection) is unconditional


def test_stop_reconciliation_is_new_schema_authority() -> None:
    script = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    )
    assert script.get_current_head() == SCHEMA_REVISION == "0006_stop_reconciliation"
    assert "instance_stop_reconciliation" in AUTHORITY_TABLES
    assert AUTHORITY_TABLES["instance_stop_fence"][0]["owner_uuid"] == ("uuid", False, None)
