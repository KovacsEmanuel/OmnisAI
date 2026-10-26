"""SOURCE ASGI/private UDS/real PG; synthetic pairing/key, zero provider IO."""

import asyncio
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_model_models import ModelRegistryControl
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.security.sessions import SessionStore, code_digest
from omnis.transport.local_control import LocalControl


@pytest.mark.asyncio
async def test_paired_api_save_receipt_conflict_reload_and_stop(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    process = uuid4()
    epoch: int | None = None
    stopped = asyncio.Event()

    async def renew(owner_id: UUID, owner_epoch: int) -> int:
        beats = 0
        while not stopped.is_set():
            await service.heartbeat(owner_id, owner_epoch)
            beats += 1
            try:
                await asyncio.wait_for(stopped.wait(), timeout=1)
            except TimeoutError:
                pass
        return beats

    try:
        epoch = await service.acquire(process)
        initial = await service.owned_status(process, epoch)
        generation = await service.open(uuid4(), initial.generation, process, epoch)
        directory = ipc_directory / "c"
        directory.mkdir(mode=0o700)
        data, keys = tmp_path / "vault", tmp_path / "keys"
        data.mkdir(mode=0o700)
        keys.mkdir(mode=0o700)
        monkeypatch.setenv("OMNIS_CONTROL_DIR", str(directory))
        monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
        vault = ProviderVault(data, keys, str(initial.instance_id))
        owner = ProviderSettingsOwner(service, process, epoch, vault)
        sessions = SessionStore(engine)
        await sessions.register(code_digest("synthetic-pairing"), issuance_id=uuid4())
        grant = await sessions.exchange("synthetic-pairing")
        path = "/api/v1/settings/providers"
        command_id = str(uuid4())
        payload = {
            "action": "save_connection",
            "command_id": command_id,
            "connection_id": str(uuid4()),
            "expected_revision": 0,
            "provider": "openrouter",
            "secret": "synthetic-api-secret-canary",
        }
        async with (
            asyncio.TaskGroup() as supervisor,
            LocalControl(directory, service, process, epoch) as control,
        ):
            heartbeat = supervisor.create_task(renew(process, epoch))

            async def handle(
                command: KeySettingsControl | ModelRegistryControl,
            ) -> dict[str, object]:
                return (await owner.handle(command)).model_dump(mode="json")

            control.provider_settings = handle
            app = create_app()
            app.state.db_engine = engine
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
            ) as http:
                headers = {"Origin": "http://127.0.0.1:8765", "Content-Type": "application/json"}
                assert (await http.put(path, json=payload, headers=headers)).status_code == 401
                http.cookies.set("omnis_session", grant.token)
                assert (await http.put(path, json=payload, headers=headers)).status_code == 403
                headers["X-CSRF-Token"] = grant.csrf
                invalid = {**payload, "secret": "synthetic-api-secret-canary "}
                denied = await http.put(path, json=invalid, headers=headers)
                assert denied.status_code == 422
                assert "synthetic-api-secret-canary" not in denied.text
                duplicate = json.dumps(payload)[:-1] + ',"secret":"duplicate"}'
                assert (await http.put(path, content=duplicate, headers=headers)).status_code == 422
                assert (
                    await http.put(path, content=b"x" * 4097, headers=headers)
                ).status_code == 413
                saved = await http.put(path, json=payload, headers=headers)
                assert saved.status_code == 200
                assert saved.json()["connections"][0]["revision"] == 1
                assert saved.headers["cache-control"] == "no-store"
                assert "synthetic-api-secret-canary" not in saved.text
                assert (await http.get(path + "/commands/" + command_id)).json() == saved.json()
                assert (await http.put(path, json=payload, headers=headers)).json() == saved.json()
                changed = await http.put(
                    path, json={**payload, "secret": "changed"}, headers=headers
                )
                assert changed.status_code == 409
                assert changed.json()["error"]["code"] == "COMMAND_CONFLICT"
                stale = await http.put(
                    path, json={**payload, "command_id": str(uuid4())}, headers=headers
                )
                assert stale.status_code == 409
                assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
                models_path = "/api/v1/settings/models"
                empty = (await http.get(models_path)).json()
                assert empty["entries"] == [] and empty["registry_revision"] == 0
                choice = {
                    "connection_id": payload["connection_id"],
                    "connection_revision": 1,
                    "model": "fixture/0",
                    "output_tokens": 64,
                }
                assignments = {
                    "action": "save_selection",
                    "command_id": str(uuid4()),
                    "expected_revision": 0,
                    "default": choice,
                    "brain": {**choice, "output_tokens": 32},
                    "investigator": None,
                    "validator": None,
                }
                # Old free-text callers remain valid until the guided assignments caller exists.
                assigned = await http.put(path, json=assignments, headers=headers)
                assert assigned.status_code == 200
                model_rows = [
                    {
                        "entry_id": str(uuid4()),
                        "expected_revision": 0,
                        "model": f"fixture/{index}",
                        "output_tokens": 64,
                    }
                    for index in range(63)
                ]
                registry_payload = {
                    "action": "save_models",
                    "command_id": str(uuid4()),
                    "expected_registry_revision": 0,
                    "connection_id": payload["connection_id"],
                    "connection_revision": 1,
                    "models": model_rows,
                }
                assert len(json.dumps(registry_payload).encode()) > 4096
                registered = await http.put(models_path, json=registry_payload, headers=headers)
                assert registered.status_code == 200
                receipt = registered.json()
                registry_command = models_path + "/commands/" + str(registry_payload["command_id"])
                assert (await http.get(registry_command)).json() == receipt
                assert (
                    await http.put(models_path, json=registry_payload, headers=headers)
                ).json() == receipt
                assigned = await http.put(path, json=assignments, headers=headers)
                assert assigned.status_code == 200
                selected = assigned.json()["selection"]
                assert (
                    selected["brain"]["output_tokens"] == 32
                    and selected["default"]["output_tokens"] == 64
                )
                async with engine.connect() as db:
                    before = [
                        (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
                        for table in (
                            "provider_model_registry_revision",
                            "provider_model_entry",
                            "provider_model_entry_revision",
                            "provider_model_command",
                            "provider_selection_revision",
                            "provider_settings_command",
                        )
                    ]
                invalid_requests = [
                    (
                        {
                            **registry_payload,
                            "models": [{**model_rows[0], "output_tokens": 2}],
                        },
                        409,
                        "COMMAND_CONFLICT",
                    ),
                    ({**registry_payload, "command_id": str(uuid4())}, 409, "REVISION_CONFLICT"),
                    (
                        {
                            **registry_payload,
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 1,
                            "models": [{**model_rows[0], "entry_id": str(uuid4())}],
                        },
                        409,
                        "COMMAND_CONFLICT",
                    ),
                    (
                        {
                            **registry_payload,
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 1,
                            "connection_id": str(uuid4()),
                        },
                        409,
                        "CONNECTION_UNAVAILABLE",
                    ),
                    (
                        {
                            **registry_payload,
                            "command_id": str(uuid4()),
                            "models": model_rows + model_rows[:2],
                        },
                        422,
                        "INVALID_INPUT",
                    ),
                ]
                for invalid_request, status_code, reason in invalid_requests:
                    refused = await http.put(models_path, json=invalid_request, headers=headers)
                    assert (
                        refused.status_code == status_code
                        and refused.json()["error"]["code"] == reason
                    )
                async with engine.connect() as db:
                    after = [
                        (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
                        for table in (
                            "provider_model_registry_revision",
                            "provider_model_entry",
                            "provider_model_entry_revision",
                            "provider_model_command",
                            "provider_selection_revision",
                            "provider_settings_command",
                        )
                    ]
                assert before == after
                assert (
                    await http.put(models_path, content=b" " * 65537, headers=headers)
                ).status_code == 413
                assert (
                    await http.put(models_path + "/", content=b" " * 4097, headers=headers)
                ).status_code == 413
                assert (
                    await http.post(models_path, content=b" " * 4097, headers=headers)
                ).status_code == 413
                duplicate = json.dumps(registry_payload)[:-1] + ',"action":"save_models"}'
                assert (
                    await http.put(models_path, content=duplicate, headers=headers)
                ).status_code == 422
                assert (
                    await http.get(models_path + "/commands/" + str(uuid4()))
                ).status_code == 404
                # Capacity is per instance, including a second provider with the same exact model ID.
                other_connection = str(uuid4())
                other_saved = await http.put(
                    path,
                    json={
                        **payload,
                        "command_id": str(uuid4()),
                        "connection_id": other_connection,
                        "provider": "orcarouter",
                    },
                    headers=headers,
                )
                assert other_saved.status_code == 200
                other_model = {
                    **registry_payload,
                    "command_id": str(uuid4()),
                    "expected_registry_revision": 1,
                    "connection_id": other_connection,
                    "models": [{**model_rows[0], "entry_id": str(uuid4())}],
                }
                assert (
                    await http.put(models_path, json=other_model, headers=headers)
                ).status_code == 200
                overflow = {
                    **other_model,
                    "command_id": str(uuid4()),
                    "expected_registry_revision": 2,
                    "models": [
                        {
                            **model_rows[0],
                            "entry_id": str(uuid4()),
                            "model": "fixture/65",
                        }
                    ],
                }
                denied = await http.put(models_path, json=overflow, headers=headers)
                assert (
                    denied.status_code == 409 and denied.json()["error"]["code"] == "REGISTRY_FULL"
                )
                assert (await http.get(path)).json()["selection"] == selected
                assert (
                    await http.get(models_path + "/pages/1/" + receipt["next_after"])
                ).status_code == 409
                page = (await http.get(models_path)).json()
                collected = list(page["entries"])
                while page["next_after"] is not None:
                    page = (await http.get(models_path + "/pages/2/" + page["next_after"])).json()
                    assert page["registry_revision"] == 2 and page["total"] == 64
                    collected.extend(page["entries"])
                assert len(collected) == len({entry["entry_id"] for entry in collected}) == 64
                competing = {
                    **registry_payload,
                    "expected_registry_revision": 2,
                    "models": [{**model_rows[0], "expected_revision": 1}],
                }
                edits = await asyncio.gather(
                    *(
                        http.put(
                            models_path,
                            json={
                                **competing,
                                "command_id": str(uuid4()),
                                "models": [
                                    {**model_rows[0], "expected_revision": 1, "output_tokens": cap}
                                ],
                            },
                            headers=headers,
                        )
                        for cap in (16, 32)
                    )
                )
                assert sorted(edit.status_code for edit in edits) == [200, 409]
                assert (
                    next(edit for edit in edits if edit.status_code == 409).json()["error"]["code"]
                    == "REVISION_CONFLICT"
                )
                assert (await http.get(registry_command)).json() == receipt
                # Reload uses a fresh ASGI app and the original owner/DB, never a replayed Save.
                fresh = create_app()
                fresh.state.db_engine = engine
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=fresh),
                    base_url="http://127.0.0.1:8765",
                    cookies={"omnis_session": grant.token},
                ) as reloaded:
                    assert (await reloaded.get(path)).json()["connections"] == saved.json()[
                        "connections"
                    ] + other_saved.json()["connections"][1:]
                    assert (await reloaded.get(models_path)).json()["total"] == 64
                revoked = await http.put(
                    path,
                    json={
                        "action": "revoke_connection",
                        "command_id": str(uuid4()),
                        "connection_id": payload["connection_id"],
                        "expected_revision": 1,
                    },
                    headers=headers,
                )
                assert revoked.status_code == 200
                stale_model = {
                    **competing,
                    "command_id": str(uuid4()),
                    "expected_registry_revision": 3,
                    "models": [{**model_rows[0], "expected_revision": 2}],
                }
                denied = await http.put(models_path, json=stale_model, headers=headers)
                assert (
                    denied.status_code == 409
                    and denied.json()["error"]["code"] == "CONNECTION_UNAVAILABLE"
                )
                assert (await http.get(models_path)).json()["registry_revision"] == 3
                latest_page = (await http.get(models_path)).json()
                await service.shutdown(uuid4(), generation, process, epoch)
                assert (await http.get(path + "/commands/" + command_id)).json() == saved.json()
                assert (await http.put(path, json=payload, headers=headers)).json() == saved.json()
                refused = await http.put(
                    path,
                    json={**payload, "command_id": str(uuid4()), "expected_revision": 1},
                    headers=headers,
                )
                assert refused.status_code == 503
                assert (await http.get(registry_command)).json() == receipt
                assert (
                    await http.put(models_path, json=overflow, headers=headers)
                ).status_code == 503
            stopped.set()
        assert heartbeat.result() > 0
        # A fresh owner/epoch/vault and control listener read the same durable registry/receipt.
        await service.release(process, epoch)
        epoch = None
        process = uuid4()
        epoch = await service.acquire(process)
        owner = ProviderSettingsOwner(
            service, process, epoch, ProviderVault(data, keys, str(initial.instance_id))
        )
        stopped.clear()
        async with (
            asyncio.TaskGroup() as supervisor,
            LocalControl(directory, service, process, epoch) as restarted,
        ):
            heartbeat = supervisor.create_task(renew(process, epoch))
            restarted.provider_settings = handle
            fresh = create_app()
            fresh.state.db_engine = engine
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=fresh),
                base_url="http://127.0.0.1:8765",
                cookies={"omnis_session": grant.token},
            ) as http:
                assert (await http.get(registry_command)).json() == receipt
                assert (await http.get(models_path)).json() == latest_page
                assert (await http.get(path)).json()["selection"] == selected
            stopped.set()
        assert heartbeat.result() > 0
    finally:
        primary = sys.exception()
        try:
            try:
                if epoch is not None:
                    await service.release(process, epoch)
            finally:
                await engine.dispose()
        except BaseException as cleanup:
            if primary is not None:
                raise primary from cleanup
            raise


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, "0015_model_test_v2"])
async def test_registry_schema_empty_upgrade_backfill_and_constraints(
    empty_database_url: URL, previous: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import psycopg

    from conftest import connect_test_database
    from omnis.core.db import readiness_reason

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
        assert result.returncode == 0

    before: dict[str, list[tuple[object, ...]]] = {}
    connection, command = str(uuid4()), str(uuid4())
    historical = (
        "provider_connection_revision",
        "provider_selection_revision",
        "provider_settings_command",
    )
    if previous is not None:
        migrate(previous)
        with connect_test_database(empty_database_url) as db:
            identity_row = db.execute("SELECT instance_id FROM instance_control").fetchone()
            assert identity_row is not None
            instance = str(identity_row[0])
            for revision, enabled in ((1, True), (2, False)):
                db.execute(
                    "INSERT INTO provider_connection_revision VALUES (%s,%s,'openrouter',%s,%s,%s,1)",
                    (instance, connection, revision, enabled, str(uuid4())),
                )
            choice = {
                "connection_id": connection,
                "connection_revision": 1,
                "model": "Exact/ID",
                "output_tokens": 64,
            }
            payload = {
                "action": "save_selection",
                "command_id": command,
                "expected_revision": 1,
                "default": choice,
                "brain": {**choice, "output_tokens": 32},
                "investigator": {**choice, "model": "exact/ID", "output_tokens": 16},
                "validator": None,
            }
            db.execute(
                "INSERT INTO provider_selection_revision VALUES (%s,%s,1,%s::jsonb)",
                (
                    instance,
                    str(uuid4()),
                    json.dumps({**payload, "default": {**choice, "model": "history/only"}}),
                ),
            )
            db.execute(
                "INSERT INTO provider_selection_revision VALUES (%s,%s,2,%s::jsonb)",
                (instance, command, json.dumps(payload)),
            )
            db.execute(
                "INSERT INTO provider_settings_command VALUES (%s,%s,%s,'{}')",
                (instance, command, "a" * 64),
            )
            for table in historical:
                before[table] = db.execute(f"SELECT * FROM {table} ORDER BY 1,2,3").fetchall()
    migrate("head")
    with connect_test_database(empty_database_url) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0016_provider_models",
        )
        identity_row = db.execute("SELECT instance_id FROM instance_control").fetchone()
        assert identity_row is not None
        instance = str(identity_row[0])
        if previous is not None:
            for table in historical:
                assert (
                    db.execute(f"SELECT * FROM {table} ORDER BY 1,2,3").fetchall() == before[table]
                )
            entries = db.execute(
                "SELECT e.model,r.output_tokens,r.connection_revision FROM provider_model_entry e "
                'JOIN provider_model_entry_revision r USING(instance_id,entry_id,connection_id) ORDER BY e.model COLLATE "C"'
            ).fetchall()
            assert entries == [("Exact/ID", 64, 1), ("exact/ID", 16, 1)]
            # Re-running backfill is receive-only once a registry revision exists.
            migration = importlib.import_module("omnis.migrations.versions.0016_provider_models")
            monkeypatch.setattr(migration.op, "execute", db.execute)
            migration.backfill()
            assert db.execute("SELECT count(*) FROM provider_model_entry_revision").fetchone() == (
                2,
            )
            entry_row = db.execute(
                "SELECT entry_id FROM provider_model_entry WHERE model='Exact/ID'"
            ).fetchone()
            assert entry_row is not None
            entry = str(entry_row[0])
            db.execute("INSERT INTO provider_model_registry_revision VALUES (%s,2)", (instance,))
            invalid_sql = [
                (
                    "INSERT INTO provider_model_entry VALUES (%s,%s,%s,'Exact/ID')",
                    (instance, str(uuid4()), connection),
                ),
                (
                    "INSERT INTO provider_model_entry VALUES (%s,%s,%s,'bad model')",
                    (instance, str(uuid4()), connection),
                ),
                (
                    "INSERT INTO provider_model_entry_revision VALUES (%s,%s,2,%s,3,2,64)",
                    (instance, entry, connection),
                ),
                (
                    "INSERT INTO provider_model_entry_revision VALUES (%s,%s,2,%s,1,3,64)",
                    (instance, entry, connection),
                ),
                (
                    "INSERT INTO provider_model_entry_revision VALUES (%s,%s,2,%s,1,2,0)",
                    (instance, entry, connection),
                ),
                (
                    "INSERT INTO provider_model_entry_revision VALUES (%s,%s,2,%s,1,2,65537)",
                    (instance, entry, connection),
                ),
            ]
            expected_constraints = (
                "provider_model_entry_instance_id_connection_id_model_key",
                "provider_model_entry_model_check",
                "provider_model_entry_connection_fk",
                "provider_model_entry_registry_fk",
                "provider_model_entry_revision_output_tokens_check",
                "provider_model_entry_revision_output_tokens_check",
            )
            for (statement, parameters), expected in zip(
                invalid_sql, expected_constraints, strict=True
            ):
                with pytest.raises(psycopg.Error) as refused, db.transaction():
                    db.execute(statement, parameters)
                assert refused.value.diag.constraint_name == expected
            for table in (
                "provider_model_entry",
                "provider_model_entry_revision",
                "provider_model_registry_revision",
                "provider_model_command",
            ):
                with pytest.raises(psycopg.Error), db.transaction():
                    db.execute(f"DELETE FROM {table}")
        else:
            assert db.execute("SELECT count(*) FROM provider_model_entry").fetchone() == (0,)
    engine = database_engine(empty_database_url.render_as_string(hide_password=False))
    try:
        assert await readiness_reason(engine) is None
        async with engine.begin() as connection_db:
            await connection_db.execute(
                text(
                    "ALTER TABLE provider_model_entry_revision DROP CONSTRAINT provider_model_entry_connection_fk"
                )
            )
        assert await readiness_reason(engine) is not None
    finally:
        await engine.dispose()
