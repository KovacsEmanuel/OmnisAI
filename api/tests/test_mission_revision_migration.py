"""Real private-PG storage definitions; run only after exact-snapshot review.

Rows below are canonical synthetic SQL fixtures, NOT native TaskResult execution,
application M2 read/write, compatibility, qualification or source freshness proof.
The existing fixture attests daemon/container/socket and connected cluster identity.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL

from conftest import connect_test_database, verify_test_database
from omnis.core.db import ReadinessReason, database_engine, schema_reason_on

HEAD = "0013_mission_revisions"
PREVIOUS = "0012_contract_methods"


def sealed(
    kind: str, identity: str, revision: int, payload: dict[str, object]
) -> dict[str, object]:
    """Independent CanonicalJSON encoder for storage fixtures, no product consumer."""
    body: dict[str, object] = {
        "schema_version": 1,
        "kind": kind,
        "id": identity,
        "revision": revision,
        "payload": payload,
    }
    body["digest"] = hashlib.sha256(canonical(body)).hexdigest()
    return body


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def migrate(url: URL, target: str) -> None:
    root = Path(__file__).resolve().parents[1]
    verify_test_database(url.set(database="omnis_test"))
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "alembic",
            "-c",
            str(root / "alembic.ini"),
            "upgrade",
            target,
        ],
        cwd=root,
        env={**os.environ, "OMNIS_DATABASE_URL": url.render_as_string(hide_password=False)},
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, f"mission migration exit={completed.returncode}"


def snapshot(
    connection: psycopg.Connection[tuple[object, ...]],
) -> dict[str, list[tuple[object, ...]]]:
    tables = connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' "
        "AND tablename NOT IN ('alembic_version','managed_mission_revision') ORDER BY tablename"
    ).fetchall()
    return {
        str(row[0]): connection.execute(
            sql.SQL("SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text").format(
                sql.Identifier("public", str(row[0]))
            )
        ).fetchall()
        for row in tables
    }


def put_root(
    connection: psycopg.Connection[tuple[object, ...]],
    owner: str,
    run: str,
    record: dict[str, object],
) -> None:
    connection.execute(
        "INSERT INTO public.managed_record(id,owner_id,run_id,envelope) VALUES (%s,%s,%s,%s::jsonb)",
        (record["id"], owner, run, canonical(record).decode()),
    )


def mission_pair() -> tuple[str, str, dict[str, object], dict[str, object]]:
    owner, run, identity = (str(uuid4()) for _ in range(3))
    first = sealed(
        "mission", identity, 1, {"basis_refs": [], "sql_fixture": "not native execution"}
    )
    ref = {key: first[key] for key in ("kind", "id", "revision", "digest")}
    second = sealed("mission", identity, 2, {"basis_refs": [ref], "sql_fixture": "storage only"})
    return owner, run, first, second


def put_revision(
    connection: psycopg.Connection[tuple[object, ...]],
    owner: str,
    run: str,
    record: object,
    identity: str,
    revision: object = 2,
) -> None:
    connection.execute(
        "INSERT INTO public.managed_mission_revision(mission_id,owner_id,run_id,revision,envelope) VALUES (%s,%s,%s,%s,%s::jsonb)",
        (identity, owner, run, revision, canonical(record).decode()),
    )


def seed_history(
    connection: psycopg.Connection[tuple[object, ...]],
    owner: str,
    run: str,
    first: dict[str, object],
) -> None:
    put_root(connection, owner, run, first)
    ids = {
        kind: str(uuid4()) for kind in ("manifest", "brief", "result", "check", "task", "attempt")
    }
    for kind in ("run", "manifest", "brief", "result", "check"):
        put_root(
            connection,
            owner,
            run,
            sealed(
                kind,
                run if kind == "run" else ids[kind],
                1,
                {"sql_fixture": "not native execution"},
            ),
        )
    connection.execute(
        "INSERT INTO managed_run(run_id,owner_id,command_id,request_digest,manifest_id) VALUES (%s,%s,%s,%s,%s)",
        (run, owner, str(uuid4()), "a" * 64, ids["manifest"]),
    )
    connection.execute(
        "INSERT INTO managed_task(task_id,attempt_id,run_id,batch_index,brief_id,result_id,check_id,state) VALUES (%s,%s,%s,0,%s,%s,%s,'SUCCEEDED')",
        (ids["task"], ids["attempt"], run, ids["brief"], ids["result"], ids["check"]),
    )
    connection.execute(
        "INSERT INTO managed_inbox VALUES (%s,%s,true,false,false,true,'RECEIVED')",
        (ids["result"], ids["task"]),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "populated_previous", [False, True], ids=["empty0013", "populated0012_to0013"]
)
async def test_pg_mission_revision_upgrade_preserves_rows_fks_and_reopen(
    empty_database_url: URL, populated_previous: bool
) -> None:
    owner, run, first, second = mission_pair()
    before: dict[str, list[tuple[object, ...]]] = {}
    fks_before: list[tuple[object, ...]] = []
    if populated_previous:
        migrate(empty_database_url, PREVIOUS)
        with connect_test_database(empty_database_url) as connection:
            seed_history(connection, owner, run, first)
            before = snapshot(connection)
            fks_before = connection.execute(
                "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='f' ORDER BY conrelid::regclass::text,conname"
            ).fetchall()
    migrate(empty_database_url, HEAD)
    with connect_test_database(empty_database_url) as connection:
        if populated_previous:
            assert snapshot(connection) == before
            fks_after = connection.execute(
                "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='f' AND conrelid <> 'managed_mission_revision'::regclass ORDER BY conrelid::regclass::text,conname"
            ).fetchall()
            assert fks_after == fks_before
        else:
            seed_history(connection, owner, run, first)
        original = snapshot(connection)
        put_revision(connection, owner, run, second, str(first["id"]))
    # Close/reopen through the attestor, not an in-memory receipt comparison.
    with connect_test_database(empty_database_url) as connection:
        assert snapshot(connection) == original
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (HEAD,)
        assert connection.execute(
            "SELECT envelope FROM managed_record WHERE id=%s", (first["id"],)
        ).fetchone() == (first,)
        assert connection.execute(
            "SELECT envelope FROM managed_mission_revision WHERE mission_id=%s AND revision=2",
            (first["id"],),
        ).fetchone() == (second,)
        for record in (first, second):
            assert (
                record["digest"]
                == hashlib.sha256(
                    canonical({k: v for k, v in record.items() if k != "digest"})
                ).hexdigest()
            )
    engine = database_engine(empty_database_url.render_as_string(hide_password=False))
    try:
        async with engine.connect() as connection:
            assert await schema_reason_on(connection) is ReadinessReason.SCHEMA_INCOMPATIBLE
    finally:
        await engine.dispose()


def test_pg_mission_revision_denials_are_atomic_before_valid_insert(
    migrated_database_url: URL,
) -> None:
    owner, run, first, second = mission_pair()
    identity = str(first["id"])
    with connect_test_database(migrated_database_url, autocommit=True) as connection:
        put_root(connection, owner, run, first)
        nonmission = sealed("focus", str(uuid4()), 1, {})
        put_root(connection, owner, run, nonmission)
        # The legacy CHECKs deliberately remain weaker. The new root guard must
        # independently refuse string/missing M1 revisions and schema versions.
        malformed_roots: list[dict[str, object]] = []
        for field in ("revision", "schema_version"):
            for missing in (False, True):
                root = sealed("mission", str(uuid4()), 1, {})
                if missing:
                    del root[field]
                else:
                    root[field] = "1"
                put_root(connection, owner, run, root)
                malformed_roots.append(root)
        original = snapshot(connection)
        invalid: list[tuple[str, str, str, object, object]] = []
        invalid_fields: dict[str, list[object]] = {
            "schema_version": [None, True, "1", 1.5, 1.0, 0, 2],
            "revision": [None, True, "2", 2.5, 2.0, 0, -1, 1, 3],
            "kind": [None, True, "focus", "task-result", 2],
            "id": [None, True, 2, str(uuid4())],
        }
        for field, values in invalid_fields.items():
            for value in values:
                invalid.append((identity, owner, run, {**second, field: value}, 2))
            invalid.append(
                (identity, owner, run, {k: v for k, v in second.items() if k != field}, 2)
            )
        for value in (None, True, "object", [], 2):
            invalid.append((identity, owner, run, value, 2))
        ref = {key: first[key] for key in ("kind", "id", "revision", "digest")}
        bases: tuple[object, ...] = (
            None,
            {},
            [],
            [ref, ref],
            [{**ref, "id": str(uuid4())}],
            [{**ref, "digest": "b" * 64}],
            [{**ref, "revision": 2}],
            [{**ref, "revision": True}],
            [{**ref, "revision": "1"}],
            [{**ref, "revision": 1.0}],
            [{**ref, "kind": "focus"}],
            [{**ref, "extra": 1}],
        )
        for basis in bases:
            invalid.append((identity, owner, run, {**second, "payload": {"basis_refs": basis}}, 2))
        invalid.extend(
            [
                (identity, owner, run, {**second, "payload": {}}, 2),
                (identity, owner, run, {k: v for k, v in second.items() if k != "payload"}, 2),
                (identity, str(uuid4()), run, second, 2),
                (identity, owner, str(uuid4()), second, 2),
                (str(uuid4()), owner, run, second, 2),
            ]
        )
        # Matching ownership/UUID is insufficient when the actual root kind is not mission.
        bad_root = sealed(
            "mission",
            str(nonmission["id"]),
            2,
            {"basis_refs": [{**ref, "id": nonmission["id"], "digest": nonmission["digest"]}]},
        )
        invalid.append((str(nonmission["id"]), owner, run, bad_root, 2))
        for root in malformed_roots:
            bad_child = sealed(
                "mission",
                str(root["id"]),
                2,
                {"basis_refs": [{**ref, "id": root["id"], "digest": root["digest"]}]},
            )
            invalid.append((str(root["id"]), owner, run, bad_child, 2))
        for revision in (None, True, 0, -1, 1, 3):
            invalid.append((identity, owner, run, second, revision))
        for key, row_owner, row_run, record, row_revision in invalid:
            with pytest.raises(psycopg.Error):
                put_revision(connection, row_owner, row_run, record, key, row_revision)
            assert connection.execute(
                "SELECT count(*) FROM managed_mission_revision"
            ).fetchone() == (0,)
            assert snapshot(connection) == original
        put_revision(connection, owner, run, second, identity)
        with pytest.raises(psycopg.Error):
            put_revision(connection, owner, run, second, identity)
        # The unchanged generic revision1 ledger still refuses real M2.
        with pytest.raises(psycopg.Error):
            put_root(connection, owner, run, sealed("focus", str(uuid4()), 2, {}))
        for table in ("managed_record", "managed_mission_revision"):
            for operation in (
                "UPDATE {} SET envelope=envelope",
                "DELETE FROM {}",
                "TRUNCATE {} CASCADE",
            ):
                with pytest.raises(psycopg.Error):
                    connection.execute(sql.SQL(operation).format(sql.Identifier(table)))
        assert snapshot(connection) == original
        assert connection.execute("SELECT envelope FROM managed_mission_revision").fetchall() == [
            (second,)
        ]


DDL_MUTATIONS = [
    "ALTER TABLE managed_mission_revision ALTER COLUMN envelope SET DEFAULT '{}'::jsonb",
    "ALTER TABLE managed_mission_revision ALTER COLUMN owner_id DROP NOT NULL",
    "ALTER TABLE managed_mission_revision ADD COLUMN unexpected text",
    "ALTER TABLE managed_mission_revision DROP CONSTRAINT managed_mission_revision_pkey",
    "ALTER TABLE managed_mission_revision DROP CONSTRAINT managed_mission_revision_root_fkey",
    "ALTER TABLE managed_mission_revision DROP CONSTRAINT managed_mission_revision_revision_check",
    "ALTER TABLE managed_mission_revision ADD CONSTRAINT unexpected CHECK (revision=2)",
    "ALTER TABLE managed_mission_revision DROP CONSTRAINT managed_mission_revision_number_check; ALTER TABLE managed_mission_revision ADD CONSTRAINT managed_mission_revision_number_check CHECK (revision=2) NOT VALID",
    "ALTER TABLE managed_mission_revision DROP CONSTRAINT managed_mission_revision_revision_check; ALTER TABLE managed_mission_revision ADD CONSTRAINT managed_mission_revision_revision_check CHECK ((envelope->>'revision')='2') NOT ENFORCED",
    "ALTER TABLE managed_mission_revision DISABLE TRIGGER managed_mission_revision_root",
    "ALTER TABLE managed_mission_revision ENABLE ALWAYS TRIGGER managed_mission_revision_root",
    "DROP TRIGGER managed_mission_revision_root ON managed_mission_revision",
    "ALTER TABLE managed_mission_revision DISABLE TRIGGER managed_mission_revision_no_change",
    "CREATE OR REPLACE FUNCTION managed_mission_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RETURN NEW; END;$$",
    "CREATE OR REPLACE FUNCTION managed_mission_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RETURN NULL; END;$$",
    "DROP TRIGGER managed_mission_revision_root ON managed_mission_revision; CREATE TRIGGER managed_mission_revision_root AFTER INSERT ON managed_mission_revision FOR EACH ROW EXECUTE FUNCTION managed_mission_revision_guard()",
    "DROP TRIGGER managed_mission_revision_root ON managed_mission_revision; CREATE TRIGGER managed_mission_revision_root BEFORE INSERT ON managed_mission_revision FOR EACH ROW WHEN (NEW.revision=2) EXECUTE FUNCTION managed_mission_revision_guard()",
    "CREATE TRIGGER unexpected BEFORE INSERT ON managed_mission_revision FOR EACH ROW EXECUTE FUNCTION managed_mission_revision_guard()",
    "UPDATE alembic_version SET version_num='0012_contract_methods'",
    "DROP TABLE managed_mission_revision",
    "ALTER FUNCTION managed_mission_revision_guard() SET search_path TO public",
    "ALTER FUNCTION managed_mission_revision_guard() STABLE",
    "ALTER FUNCTION managed_mission_revision_immutable() SECURITY DEFINER",
    "ALTER FUNCTION managed_mission_revision_immutable() STRICT",
    "ALTER TABLE managed_mission_revision DROP CONSTRAINT managed_mission_revision_root_fkey; ALTER TABLE managed_record DROP CONSTRAINT managed_record_id_owner_run_key",
    "ALTER FUNCTION public.managed_mission_revision_guard() RESET search_path",
    "ALTER FUNCTION public.managed_mission_revision_guard() SET search_path TO pg_temp, pg_catalog",
    "ALTER FUNCTION public.managed_mission_revision_guard() SET statement_timeout TO '1s'",
    "ALTER TABLE public.managed_mission_revision SET UNLOGGED",
    "CREATE TEMP TABLE managed_mission_revision (LIKE public.managed_mission_revision INCLUDING ALL); DROP TABLE public.managed_mission_revision",
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", DDL_MUTATIONS, ids=[f"ddl-{i}" for i in range(len(DDL_MUTATIONS))]
)
async def test_pg_mission_revision_exact_readiness_refuses_mutated_ddl(
    migrated_database_url: URL, mutation: str
) -> None:
    verify_test_database(migrated_database_url.set(database="omnis_test"))
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        async with engine.connect() as connection:
            assert await schema_reason_on(connection) is None
            await connection.execute(text(mutation))
            assert await schema_reason_on(connection) is ReadinessReason.SCHEMA_INCOMPATIBLE
            await connection.rollback()
        async with engine.connect() as connection:
            assert await schema_reason_on(connection) is None
    finally:
        await engine.dispose()


def test_mission_revision_downgrade_explicitly_refuses() -> None:
    from importlib import import_module

    migration = import_module("omnis.migrations.versions.0013_mission_revisions")
    with pytest.raises(RuntimeError, match="reviewed backup restoration"):
        migration.downgrade()


def test_pg_mission_guard_ignores_temp_root_on_first_call_and_rolls_back(
    migrated_database_url: URL,
) -> None:
    owner, run, first, second = mission_pair()
    focus = sealed("focus", str(uuid4()), 1, {})
    shadow = sealed("mission", str(focus["id"]), 1, {"shadow": True})
    bad_child = sealed(
        "mission",
        str(focus["id"]),
        2,
        {
            "basis_refs": [{key: shadow[key] for key in ("kind", "id", "revision", "digest")}],
        },
    )
    # This fresh session has never invoked the mission guard. The negative must
    # be its first call; a prior public-root plan could hide the old vulnerability.
    with connect_test_database(migrated_database_url) as connection:
        original = snapshot(connection)
        connection.execute("SET LOCAL search_path TO public")
        put_root(connection, owner, run, focus)
        put_root(connection, owner, run, first)
        roots = snapshot(connection)
        connection.execute(
            "CREATE TEMP TABLE managed_record (id uuid, owner_id uuid, run_id uuid, envelope jsonb)"
        )
        connection.execute(
            "INSERT INTO pg_temp.managed_record VALUES (%s,%s,%s,%s::jsonb)",
            (shadow["id"], owner, run, canonical(shadow).decode()),
        )
        with pytest.raises(psycopg.errors.RaiseException, match="invalid mission revision root"):
            with connection.transaction():
                put_revision(connection, owner, run, bad_child, str(focus["id"]))
        assert snapshot(connection) == roots
        assert connection.execute(
            "SELECT count(*) FROM public.managed_mission_revision"
        ).fetchone() == (0,)
        # Same session, still shadowed: a genuine public mission must succeed
        # even when the temporary same-UUID row is a nonmission with another digest.
        fake_focus = sealed("focus", str(first["id"]), 1, {"shadow": True})
        connection.execute(
            "INSERT INTO pg_temp.managed_record VALUES (%s,%s,%s,%s::jsonb)",
            (fake_focus["id"], owner, run, canonical(fake_focus).decode()),
        )
        put_revision(connection, owner, run, second, str(first["id"]))
        assert connection.execute(
            "SELECT envelope FROM public.managed_mission_revision"
        ).fetchall() == [(second,)]
        assert snapshot(connection) == roots
        connection.rollback()
        assert snapshot(connection) == original
        assert connection.execute(
            "SELECT count(*) FROM public.managed_mission_revision"
        ).fetchone() == (0,)
        assert connection.execute("SELECT to_regclass('pg_temp.managed_record')").fetchone() == (
            None,
        )


def test_pg_mission_id_refuses_numeric_uuid_alias_before_canonical_string(
    migrated_database_url: URL,
) -> None:
    owner, run = str(uuid4()), str(uuid4())
    identity = "11111111-1111-4111-8111-111111111111"
    first = sealed("mission", identity, 1, {"basis_refs": []})
    second = sealed(
        "mission",
        identity,
        2,
        {
            "basis_refs": [{key: first[key] for key in ("kind", "id", "revision", "digest")}],
        },
    )
    with connect_test_database(migrated_database_url) as connection:
        original = snapshot(connection)
        put_root(connection, owner, run, first)
        roots = snapshot(connection)
        for alias in (11111111111141118111111111111111, "11111111111141118111111111111111"):
            invalid = {**second, "id": alias}
            invalid["digest"] = hashlib.sha256(
                canonical({k: v for k, v in invalid.items() if k != "digest"})
            ).hexdigest()
            with pytest.raises(psycopg.errors.CheckViolation) as refused:
                with connection.transaction():
                    put_revision(connection, owner, run, invalid, identity)
            assert refused.value.diag.constraint_name == "managed_mission_revision_id_check"
            assert snapshot(connection) == roots
            assert connection.execute(
                "SELECT count(*) FROM public.managed_mission_revision"
            ).fetchone() == (0,)
        put_revision(connection, owner, run, second, identity)
        assert connection.execute(
            "SELECT envelope FROM public.managed_record WHERE id=%s", (identity,)
        ).fetchone() == (first,)
        assert connection.execute(
            "SELECT envelope FROM public.managed_mission_revision"
        ).fetchall() == [(second,)]
        connection.rollback()
        assert snapshot(connection) == original
        assert connection.execute(
            "SELECT count(*) FROM public.managed_mission_revision"
        ).fetchone() == (0,)


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", [False, True], ids=["absent_public", "public_like_alias"])
async def test_pg_mission_readiness_refuses_moved_public_relation_and_rolls_back(
    migrated_database_url: URL,
    replacement: bool,
) -> None:
    verify_test_database(migrated_database_url.set(database="omnis_test"))
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        async with engine.connect() as connection:
            assert await schema_reason_on(connection) is None
            original_oid = (
                await connection.execute(
                    text("SELECT 'public.managed_mission_revision'::regclass::oid")
                )
            ).scalar_one()
            await connection.execute(text("CREATE SCHEMA mission_shadow"))
            # With both tables still public, a caller-first harmless namespace is valid.
            await connection.execute(text("SET LOCAL search_path TO mission_shadow, public"))
            assert await schema_reason_on(connection) is None
            await connection.execute(
                text("ALTER TABLE public.managed_mission_revision SET SCHEMA mission_shadow")
            )
            if replacement:
                await connection.execute(
                    text(
                        "CREATE TABLE public.managed_mission_revision (LIKE mission_shadow.managed_mission_revision INCLUDING ALL)"
                    )
                )
            alias_oid = (
                await connection.execute(text("SELECT 'managed_mission_revision'::regclass::oid"))
            ).scalar_one()
            assert alias_oid == original_oid
            assert await schema_reason_on(connection) is ReadinessReason.SCHEMA_INCOMPATIBLE
            await connection.rollback()
            # Readiness and the original exact public physical identity return on rollback.
            assert await schema_reason_on(connection) is None
            restored_oid = (
                await connection.execute(
                    text("SELECT 'public.managed_mission_revision'::regclass::oid")
                )
            ).scalar_one()
            assert restored_oid == original_oid
            assert (
                await connection.execute(text("SELECT to_regnamespace('mission_shadow')"))
            ).scalar_one() is None
        async with engine.connect() as connection:
            assert await schema_reason_on(connection) is None
    finally:
        await engine.dispose()
