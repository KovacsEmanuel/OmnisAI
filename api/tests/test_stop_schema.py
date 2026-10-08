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


@pytest.mark.parametrize(
    "table_under_test",
    [
        "instance_stop_reconciliation",
        "engagement_revision",
        "catalog_record",
        "catalog_identity",
        "catalog_reservation",
        "catalog_command",
    ],
)
@pytest.mark.parametrize("unconditional", [True, False])
@pytest.mark.asyncio
async def test_schema_refuses_conditional_immutability_trigger(
    table_under_test: str, unconditional: bool
) -> None:
    # Driver rows are substituted; this exercises the real schema decision.
    responses = []
    for table, (columns, constraints) in AUTHORITY_TABLES.items():
        column_result = Mock()
        column_result.all.return_value = [(name, *spec) for name, spec in columns.items()]
        constraint_result = Mock()
        quoted_names = {"grant": '"grant"'}  # Observed PostgreSQL catalog form, not product output.
        required = {
            (
                f"{table}_{name}_not_null",
                "n",
                f"NOT NULL {quoted_names.get(name, name)}",
                True,
                True,
            )
            for name, (_, not_null, _) in columns.items()
            if not_null
        }
        constraint_result.all.return_value = list(constraints | required)
        responses.extend([column_result, constraint_result])
    triggers = {
        "instance_stop_reconciliation": (
            "stop_reconciliation_immutable",
            "reject_stop_reconciliation_mutation",
            "Stop reconciliation receipts are immutable",
        ),
        "engagement_revision": (
            "engagement_revision_immutable",
            "reject_engagement_revision_mutation",
            "Engagement revisions are immutable",
        ),
        **{
            table: ("catalog_immutable", "catalog_immutable", "immutable catalog ledger")
            for table in (
                "catalog_record",
                "catalog_identity",
                "catalog_reservation",
                "catalog_command",
            )
        },
    }
    singleton = Mock()
    singleton.one.return_value = (True, True)

    async def execute(statement: object, parameters: object = None) -> Mock:
        if "FROM pg_trigger" in str(statement):
            assert isinstance(parameters, dict) and parameters.get("table") in triggers
            table = parameters["table"]
            name, function, message = triggers[table]
            row = (
                name,
                58,
                "O",
                function,
                f"BEGIN\n        RAISE EXCEPTION '{message}';\n        END;",
                "plpgsql",
                False,
                0,
                0,
                unconditional if table == table_under_test else True,
                "",
                "trigger",
            )
            trigger = Mock()
            trigger.all.return_value = [row]
            if "t.tgqual IS NULL" not in str(statement):
                trigger.all.return_value = [row[:9]]
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
    assert script.get_current_head() == SCHEMA_REVISION == "0010_catalog_publications"
    assert "instance_stop_reconciliation" in AUTHORITY_TABLES
    assert AUTHORITY_TABLES["instance_stop_fence"][0]["owner_uuid"] == ("uuid", False, None)
