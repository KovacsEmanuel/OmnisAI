"""SOURCE-only schema/DDL controls; catalog rows are explicit driver doubles."""

import re
from importlib import import_module
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.core.db import SCHEMA_REVISION
from omnis.core.managed_schema import MANAGED_TABLES
from omnis.core.schema import AUTHORITY_TABLES, authority_schema_matches


def test_mission_revision_head_keeps_historical_chain() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == SCHEMA_REVISION == "0014_provider_settings"
    revision = scripts.get_revision("0013_mission_revisions")
    assert revision is not None and revision.down_revision == "0012_contract_methods"


def test_mission_extension_is_not_a_generic_rekey() -> None:
    assert "managed_mission_revision" in MANAGED_TABLES
    columns, constraints = MANAGED_TABLES["managed_mission_revision"]
    assert columns == {
        "mission_id": ("uuid", True, None),
        "owner_id": ("uuid", True, None),
        "run_id": ("uuid", True, None),
        "revision": ("bigint", True, None),
        "envelope": ("jsonb", True, None),
    }
    assert (
        "managed_mission_revision_pkey",
        "p",
        "PRIMARY KEY (mission_id, revision)",
        True,
        True,
    ) in constraints
    assert (
        "managed_mission_revision_root_fkey",
        "f",
        "FOREIGN KEY (mission_id, owner_id, run_id) REFERENCES managed_record(id, owner_id, run_id)",
        True,
        True,
    ) in constraints
    assert ("managed_record_pkey", "p", "PRIMARY KEY (id)", True, True) in MANAGED_TABLES[
        "managed_record"
    ][1]


def test_mission_revision_ddl_emits_guard_and_immutable_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = import_module("omnis.migrations.versions.0013_mission_revisions")
    operations = Mock()
    monkeypatch.setattr(migration, "op", operations)
    migration.upgrade()
    sql = "\n".join(str(call.args[0]) for call in operations.execute.call_args_list)
    assert "CREATE TABLE public.managed_mission_revision" in sql
    assert "BEFORE INSERT ON public.managed_mission_revision" in sql
    assert "BEFORE UPDATE OR DELETE OR TRUNCATE ON public.managed_mission_revision" in sql
    assert "ALTER TABLE public.managed_record ADD CONSTRAINT managed_record_id_owner_run_key" in sql
    assert "DROP " not in sql and "UPDATE managed_record" not in sql


def source_catalog_connection(
    mutation: tuple[int, object] | None = None, trigger_index: int = 1
) -> Mock:
    """Synthetic driver rows, not PostgreSQL deparser/execution evidence."""
    migration = import_module("omnis.migrations.versions.0013_mission_revisions")
    with pytest.MonkeyPatch.context() as patcher:
        operations = Mock()
        patcher.setattr(migration, "op", operations)
        migration.upgrade()
    ddl = str(operations.execute.call_args.args[0])
    guard = re.search(r"managed_mission_revision_guard\(\).*?AS \$\$(.*?)\$\$", ddl, re.S)
    assert guard is not None
    rows: list[tuple[object, ...]] = [
        (
            "managed_mission_revision_no_change",
            58,
            "O",
            "managed_mission_revision_immutable",
            "BEGIN\n        RAISE EXCEPTION 'mission revisions are immutable';\n        END;",
            "plpgsql",
            False,
            0,
            0,
            True,
            "",
            "trigger",
        ),
        (
            "managed_mission_revision_root",
            7,
            "O",
            "managed_mission_revision_guard",
            guard.group(1),
            "plpgsql",
            False,
            0,
            0,
            True,
            "",
            "trigger",
        ),
    ]
    if mutation is not None:
        index, value = mutation
        row = list(rows[trigger_index])
        if index < len(row):
            row[index] = value
        rows[trigger_index] = tuple(row)
    legacy = {
        "managed_record": (
            "managed_record_no_change",
            "managed_record_immutable",
            "managed records are immutable",
        ),
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
            table: (
                "provider_settings_no_change",
                "provider_settings_immutable",
                "provider Settings history is immutable",
            )
            for table in (
                "provider_connection_revision",
                "provider_selection_revision",
                "provider_settings_command",
            )
        },
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

    async def execute(statement: object, parameters: dict[str, object] | None = None) -> Mock:
        result = Mock()
        query = str(statement)
        if parameters is None:
            result.one.return_value = (True, True)
            return result
        if "FROM pg_catalog.pg_class" in query:
            table = str(parameters["table"]).removeprefix("public.")
            oid = 42001 if table == "managed_mission_revision" else 42002
            result.all.return_value = [(oid, "public", table, "r", "p")]
            return result
        table = str(parameters.get("table", "managed_mission_revision")).removeprefix("public.")
        if "FROM pg_trigger" in query or "FROM pg_catalog.pg_trigger" in query:
            if table == "managed_mission_revision":
                if "p.proconfig," in query:
                    extended: list[tuple[object, ...]] = [
                        (
                            *row,
                            ["search_path=pg_catalog, pg_temp"] if index == 1 else None,
                            "f",
                            "v",
                            False,
                            False,
                            False,
                            True,
                            True,
                            "public",
                        )
                        for index, row in enumerate(rows)
                    ]
                    if mutation is not None and mutation[0] >= 12:
                        index, value = mutation
                        guard_row = list(extended[trigger_index])
                        guard_row[index] = value
                        extended[trigger_index] = tuple(guard_row)
                    result.all.return_value = extended
                else:
                    result.all.return_value = rows
            else:
                name, function, message = legacy[table]
                result.all.return_value = [
                    (
                        name,
                        58,
                        "O",
                        function,
                        f"BEGIN\n        RAISE EXCEPTION '{message}';\n        END;",
                        "plpgsql",
                        False,
                        0,
                        0,
                        True,
                        "",
                        "trigger",
                    )
                ]
        elif "FROM pg_attribute" in query or "FROM pg_catalog.pg_attribute" in query:
            result.all.return_value = [
                (name, *spec) for name, spec in AUTHORITY_TABLES[table][0].items()
            ]
        else:
            columns, constraints = AUTHORITY_TABLES[table]
            required = {
                (
                    f"{table}_{name}_not_null",
                    "n",
                    f"NOT NULL {'"grant"' if name == 'grant' else name}",
                    True,
                    True,
                )
                for name, (_, not_null, _) in columns.items()
                if not_null
            }
            result.all.return_value = [
                (*row, 42002 if row[1] == "f" else 0) if "confrelid" in query else row
                for row in constraints | required
            ]
        return result

    connection = Mock(spec=AsyncConnection)
    connection.dialect = Mock()
    connection.execute = AsyncMock(side_effect=execute)
    return connection


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger_index", [0, 1], ids=["immutable", "root_guard"])
@pytest.mark.parametrize(
    "mutation",
    [
        None,
        (0, "other"),
        (1, 5),
        (2, "D"),
        (3, "other"),
        (4, "BEGIN RETURN NEW; END;"),
        (5, "sql"),
        (6, True),
        (7, 1),
        (8, 1),
        (9, False),
        (10, "1"),
        (11, "text"),
        (12, False),
        (13, "p"),
        (14, "s"),
        (15, True),
        (16, True),
        (17, True),
        (18, False),
        (19, False),
        (20, "other"),
    ],
)
async def test_source_exact_mission_guard_attestation(
    mutation: tuple[int, object] | None, trigger_index: int
) -> None:
    assert await authority_schema_matches(source_catalog_connection(mutation, trigger_index)) is (
        mutation is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "column_type",
        "nullable",
        "default",
        "extra_column",
        "missing_constraint",
        "changed_constraint",
        "not_valid",
        "not_enforced",
        "root_key",
    ],
)
async def test_source_mission_readiness_refuses_catalog_drift(mutation: str) -> None:
    connection = source_catalog_connection()
    original_execute = connection.execute

    async def execute(statement: object, parameters: dict[str, object] | None = None) -> Mock:
        result = await original_execute(statement, parameters)
        assert isinstance(result, Mock)
        if parameters is None:
            return result
        table = str(parameters.get("table", "managed_mission_revision")).removeprefix("public.")
        if "pg_attribute" in str(statement) and table == "managed_mission_revision":
            column_rows = [(name, *spec) for name, spec in AUTHORITY_TABLES[table][0].items()]
            if mutation == "extra_column":
                column_rows.append(("extra", "text", False, None))
            elif mutation in {"column_type", "nullable", "default"}:
                index = {"column_type": 1, "nullable": 2, "default": 3}[mutation]
                changed: list[object] = list(column_rows[0])
                changed[index] = {
                    "column_type": "text",
                    "nullable": False,
                    "default": "gen_random_uuid()",
                }[mutation]
                result.all.return_value = [tuple(changed), *column_rows[1:]]
                return result
            result.all.return_value = column_rows
        elif "pg_constraint" in str(statement) and mutation in {
            "missing_constraint",
            "changed_constraint",
            "not_valid",
            "not_enforced",
            "root_key",
        }:
            target = "managed_record" if mutation == "root_key" else "managed_mission_revision"
            if table == target:
                constraint_rows = list(result.all.return_value)
                name = (
                    "managed_record_id_owner_run_key"
                    if mutation == "root_key"
                    else "managed_mission_revision_root_fkey"
                )
                retained = [row for row in constraint_rows if row[0] != name]
                matching = next(row for row in constraint_rows if row[0] == name)
                if mutation in {"changed_constraint", "not_valid", "not_enforced"}:
                    changed_constraint = list(matching)
                    index = {"changed_constraint": 2, "not_valid": 3, "not_enforced": 4}[mutation]
                    changed_constraint[index] = (
                        "FOREIGN KEY (mission_id) REFERENCES managed_record(id)"
                        if index == 2
                        else False
                    )
                    retained.append(tuple(changed_constraint))
                result.all.return_value = retained
        return result

    connection.execute = AsyncMock(side_effect=execute)
    assert await authority_schema_matches(connection) is False


def test_source_guard_uses_public_root_and_fixed_lookup_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = import_module("omnis.migrations.versions.0013_mission_revisions")
    operations = Mock()
    monkeypatch.setattr(migration, "op", operations)
    migration.upgrade()
    ddl = str(operations.execute.call_args.args[0])
    guard = re.search(
        r"CREATE FUNCTION .*?managed_mission_revision_guard\(\)(.*?)AS \$\$(.*?)\$\$", ddl, re.S
    )
    assert guard is not None
    assert "SET search_path TO pg_catalog, pg_temp" in guard.group(1)
    assert "SECURITY DEFINER" not in guard.group(1)
    assert "FROM public.managed_record" in guard.group(2)
    from omnis.core.managed_schema import MISSION_REVISION_GUARD

    assert guard.group(2) == MISSION_REVISION_GUARD


@pytest.mark.asyncio
async def test_source_guard_attests_exact_proconfig_not_null_boolean() -> None:
    connection = source_catalog_connection()
    assert await authority_schema_matches(connection) is True
    queries = [str(call.args[0]) for call in connection.execute.call_args_list]
    guard_query = next(query for query in queries if "p.prokind" in query)
    assert "p.proconfig IS NULL" not in guard_query
    assert "p.proconfig," in guard_query


@pytest.mark.asyncio
async def test_source_mission_catalog_reads_bind_one_public_physical_oid() -> None:
    connection = source_catalog_connection()
    assert await authority_schema_matches(connection) is True
    calls = connection.execute.call_args_list
    identities = [call for call in calls if "FROM pg_catalog.pg_class" in str(call.args[0])]
    assert {call.args[1]["table"] for call in identities} == {
        "public.managed_mission_revision",
        "public.managed_record",
    }
    for call in identities:
        query = str(call.args[0])
        assert all(
            token in query
            for token in ("c.oid", "n.nspname", "c.relname", "c.relkind", "c.relpersistence")
        )
    mission_reads = [
        call for call in calls if "relation_oid" in (call.args[1] if len(call.args) > 1 else {})
    ]
    assert len(mission_reads) == 3
    assert all(call.args[1]["relation_oid"] == 42001 for call in mission_reads)
    assert all("to_regclass" not in str(call.args[0]) for call in mission_reads)
    constraint = next(
        call for call in mission_reads if "FROM pg_catalog.pg_constraint" in str(call.args[0])
    )
    assert "confrelid" in str(constraint.args[0])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identity_row",
    [
        None,
        (42001, "shadow", "managed_mission_revision", "r", "p"),
        (42001, "pg_temp_3", "managed_mission_revision", "r", "t"),
        (42001, "public", "other", "r", "p"),
        (42001, "public", "managed_mission_revision", "v", "p"),
        (42001, "public", "managed_mission_revision", "r", "u"),
        (True, "public", "managed_mission_revision", "r", "p"),
        ("42001", "public", "managed_mission_revision", "r", "p"),
        (0, "public", "managed_mission_revision", "r", "p"),
        (42001, "public", "managed_mission_revision", "r", "p", "unknown"),
    ],
)
async def test_source_mission_refuses_noncanonical_physical_identity(
    identity_row: tuple[object, ...] | None,
) -> None:
    connection = source_catalog_connection()
    original_execute = connection.execute

    async def execute(statement: object, parameters: dict[str, object] | None = None) -> Mock:
        result = await original_execute(statement, parameters)
        assert isinstance(result, Mock)
        if "FROM pg_catalog.pg_class" in str(statement) and parameters == {
            "table": "public.managed_mission_revision"
        }:
            result.all.return_value = [] if identity_row is None else [identity_row]
        return result

    connection.execute = AsyncMock(side_effect=execute)
    assert await authority_schema_matches(connection) is False


@pytest.mark.asyncio
async def test_source_mission_refuses_fk_target_oid_alias() -> None:
    connection = source_catalog_connection()
    original_execute = connection.execute

    async def execute(statement: object, parameters: dict[str, object] | None = None) -> Mock:
        result = await original_execute(statement, parameters)
        assert isinstance(result, Mock)
        if "confrelid" in str(statement):
            result.all.return_value = [
                (*row[:5], 42003 if row[1] == "f" else row[5]) for row in result.all.return_value
            ]
        return result

    connection.execute = AsyncMock(side_effect=execute)
    assert await authority_schema_matches(connection) is False


def test_source_mission_id_check_preserves_json_string_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = import_module("omnis.migrations.versions.0013_mission_revisions")
    operations = Mock()
    monkeypatch.setattr(migration, "op", operations)
    migration.upgrade()
    ddl = str(operations.execute.call_args.args[0])
    identity = re.search(
        r"CONSTRAINT managed_mission_revision_id_check\s+(CHECK .*?),\s+CONSTRAINT", ddl, re.S
    )
    assert identity is not None
    assert identity.group(1) == "CHECK ((envelope->'id' = to_jsonb(mission_id::text)) IS TRUE)"
    assert (
        "managed_mission_revision_id_check",
        "c",
        "CHECK ((((envelope -> 'id'::text) = to_jsonb((mission_id)::text)) IS TRUE))",
        True,
        True,
    ) in MANAGED_TABLES["managed_mission_revision"][1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configuration",
    [
        None,
        ["search_path=public"],
        ["search_path=pg_temp, pg_catalog"],
        ["search_path=pg_catalog, pg_temp", "statement_timeout=1s"],
        ["search_path=pg_catalog, pg_temp, public"],
    ],
)
async def test_source_guard_refuses_nonexact_proconfig(configuration: object) -> None:
    assert await authority_schema_matches(source_catalog_connection((12, configuration))) is False
