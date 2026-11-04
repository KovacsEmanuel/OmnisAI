"""Readiness comparator controls; these are not PostgreSQL DDL evidence."""

import pytest
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import TextClause

from omnis.core import run_schema


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corruption",
    [
        "none",
        "constraint",
        "fk",
        "predicate",
        "keys",
        "trigger",
        "trigger_body",
        "default",
        "unique_invalid",
    ],
)
async def test_readiness_rejects_same_count_weakened_schema(
    monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    connection = object.__new__(AsyncConnection)
    names = list(run_schema.RUN_COLUMNS)
    reached: set[str] = set()

    async def scalar(
        self: AsyncConnection, statement: TextClause, parameters: dict[str, object]
    ) -> int:
        if "name" in parameters:
            return names.index(str(parameters["name"])) + 1
        reached.add("unique_invalid")
        return int(corruption == "unique_invalid")

    async def execute(
        self: AsyncConnection, statement: TextClause, parameters: dict[str, object]
    ) -> CursorResult[tuple[object, ...]]:
        query = str(statement)
        name = names[int(str(parameters.get("oid", 1))) - 1]
        rows: list[tuple[object, ...]]
        if "pg_attribute" in query:
            reached.add("default")
            rows = [
                (
                    key,
                    kind,
                    (name, key) not in run_schema.NULLABLE,
                    "'foreign'::text"
                    if corruption == "default"
                    else run_schema.DEFAULTS.get((name, key)),
                    "",
                    "",
                )
                for key, kind in run_schema.RUN_COLUMNS[name].items()
            ]
        elif "pg_get_constraintdef" in query:
            reached.update(("constraint", "fk"))
            rows = [
                (
                    definition,
                    True,
                    True,
                    False,
                    False,
                    not (corruption == "fk" and definition.startswith("FOREIGN KEY")),
                )
                for definition in sorted(run_schema.CONSTRAINTS[name])
            ]
            if corruption == "constraint":
                rows[0] = ("CHECK (true)", *rows[0][1:])
        elif "pg_trigger" in query:
            reached.update(("trigger", "trigger_body"))
            rows = list(run_schema.TRIGGERS[name])
            if rows and corruption == "trigger":
                rows = []
            if rows and corruption == "trigger_body":
                rows[0] = (*rows[0][:4], "BEGIN RETURN NEW; END;", *rows[0][5:])
        elif "pg_index" in query:
            reached.update(("predicate", "keys"))
            _, keys, predicate = run_schema.INDEXES[
                str(parameters["index"]).removeprefix("public.")
            ]
            count = len(keys.split())
            rows = [
                (
                    True,
                    True,
                    True,
                    True,
                    True,
                    "2" if corruption == "keys" else keys,
                    "false" if corruption == "predicate" else predicate,
                    True,
                    count,
                    count,
                    False,
                    "btree",
                )
            ]
        else:
            raise AssertionError(query)
        result: CursorResult[tuple[object, ...]] = object.__new__(CursorResult)
        monkeypatch.setattr(result, "all", lambda: rows)
        return result

    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    assert await run_schema.run_schema_matches(connection) == (corruption == "none")
    if corruption != "none":
        assert corruption in reached


def test_migration_emits_root_immutability_and_setup_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import runpy
    from pathlib import Path

    from alembic import op

    statements: list[str] = []
    monkeypatch.setattr(op, "execute", lambda sql: statements.append(str(sql)))
    module = runpy.run_path(
        str(Path(__file__).parents[1] / "src/omnis/migrations/versions/0019_agent_runs.py")
    )
    upgrade = module["upgrade"]
    assert callable(upgrade)
    upgrade()
    ddl = "\n".join(statements)
    assert "CREATE TRIGGER run_root_guard BEFORE INSERT OR UPDATE ON agent_run" in ddl
    assert "CREATE TRIGGER run_setup_binding BEFORE INSERT ON run_setup" in ddl
    assert "FOREIGN KEY(instance_id,setup_id,engagement_id)" in ddl
    assert "FOREIGN KEY(instance_id,run_id,task_id,role)" in ddl
