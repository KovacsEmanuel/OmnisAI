"""No-DB revision/contract checks; physical PostgreSQL gates remain separate."""

from importlib import import_module
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from omnis.core.db import SCHEMA_REVISION
from omnis.core.schema import AUTHORITY_TABLES, authority_schema_matches
from test_mission_revision_schema import source_catalog_connection


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
        "managed_record",
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
    # Reuse the complete catalog observer, including the new OID seam. Retain
    # all original fields and mutate only the selected legacy trigger condition.
    connection = source_catalog_connection()
    original_execute = connection.execute

    async def execute(statement: object, parameters: dict[str, object] | None = None) -> Mock:
        result = await original_execute(statement, parameters)
        assert isinstance(result, Mock)
        if "FROM pg_trigger" in str(statement) and parameters == {"table": table_under_test}:
            rows = []
            for row in result.all.return_value:
                changed = list(row)
                changed[9] = unconditional
                rows.append(tuple(changed))
            result.all.return_value = rows
        return result

    connection.execute = AsyncMock(side_effect=execute)
    assert await authority_schema_matches(connection) is unconditional
    assert any(
        "FROM pg_trigger" in str(call.args[0]) and call.args[1] == {"table": table_under_test}
        for call in connection.execute.call_args_list
    )


def test_stop_reconciliation_is_new_schema_authority() -> None:
    script = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    )
    assert script.get_current_head() == SCHEMA_REVISION == "0018_model_relay_authority"
    assert "instance_stop_reconciliation" in AUTHORITY_TABLES
    assert AUTHORITY_TABLES["instance_stop_fence"][0]["owner_uuid"] == ("uuid", False, None)
