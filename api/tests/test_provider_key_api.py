"""SOURCE ASGI/private UDS/real PG; synthetic pairing/key, zero provider IO."""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.engine import URL

from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
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
    try:
        async with LocalControl(directory, service, process, epoch) as control:

            async def handle(command: KeySettingsControl) -> dict[str, object]:
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
                    ]
                await service.shutdown(uuid4(), generation, process, epoch)
                assert (await http.get(path + "/commands/" + command_id)).json() == saved.json()
                assert (await http.put(path, json=payload, headers=headers)).json() == saved.json()
                refused = await http.put(
                    path,
                    json={**payload, "command_id": str(uuid4()), "expected_revision": 1},
                    headers=headers,
                )
                assert refused.status_code == 503
    finally:
        await service.release(process, epoch)
        await engine.dispose()
