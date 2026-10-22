"""T1 Settings contract and real PostgreSQL owner consumer; no provider calls."""

import asyncio
import json
import threading
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner, SettingsConflict
from omnis.modules.settings.provider_vault import CredentialRef, ProviderVault, VaultLocked


def save(connection_id: str, revision: int = 0, secret: str = "synthetic-key") -> dict[str, object]:
    return {
        "op": "provider_settings",
        "request": {
            "action": "save_connection",
            "command_id": str(uuid4()),
            "connection_id": connection_id,
            "expected_revision": revision,
            "provider": "openrouter",
            "secret": secret,
        },
    }


def test_final_wire_size_and_secret_repr() -> None:
    maximum = 9223372036854775807
    request = save(str(uuid4()), maximum, '\\"' * 256)
    command = KeySettingsControl.model_validate(request)
    assert "secret='" not in repr(command)
    assert command.wire()["request"] == request["request"]
    assert len(command.wire_bytes()) <= 3600
    frame = (
        json.dumps(
            {"version": 1, "capability": "a" * 64, "command": command.wire()},
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    assert len(frame) <= 4096
    selection = {
        "connection_id": str(uuid4()),
        "connection_revision": maximum,
        "model": '\\"' * 128,
        "output_tokens": 65536,
    }
    complete = KeySettingsControl.model_validate(
        {
            "op": "provider_settings",
            "request": {
                "action": "save_selection",
                "command_id": str(uuid4()),
                "expected_revision": maximum,
                "default": selection,
                "brain": selection,
                "investigator": selection,
                "validator": selection,
            },
        }
    )
    assert len(complete.wire_bytes()) <= 3600
    frame = (
        json.dumps(
            {"version": 1, "capability": "a" * 64, "command": complete.wire()},
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    assert len(frame) <= 4096


@pytest.mark.parametrize("secret", ["", "x" * 513, "white space", "line\n", "é", "\x00"])
def test_invalid_secrets_are_bounded(secret: str) -> None:
    with pytest.raises(ValueError):
        KeySettingsControl.model_validate(save(str(uuid4()), secret=secret))


@pytest.mark.asyncio
async def test_save_rotate_revoke_replay_selection_and_no_secret_in_db(
    migrated_database_url: URL, tmp_path: Path
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    process = uuid4()
    epoch = await service.acquire(process)
    status = await service.owned_status(process, epoch)
    await service.open(uuid4(), status.generation, process, epoch)
    data, keys = tmp_path / "vault", tmp_path / "keys"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    instance = str(status.instance_id)
    vault = ProviderVault(data, keys, instance)
    owner = ProviderSettingsOwner(service, process, epoch, vault)
    connection = str(uuid4())
    first = save(connection, secret="synthetic-secret-canary")
    try:
        result = await owner.handle(KeySettingsControl.model_validate(first))
        assert result.connections[0].revision == 1
        assert result.connections[0].enabled
        assert result.vault_status == "UNLOCKED"
        assert "synthetic-secret-canary" not in result.model_dump_json()
        assert await owner.handle(KeySettingsControl.model_validate(first)) == result
        changed = save(connection, secret="synthetic-other")
        changed_request, first_request = changed["request"], first["request"]
        assert isinstance(changed_request, dict) and isinstance(first_request, dict)
        changed["request"] = {**changed_request, "command_id": first_request["command_id"]}
        with pytest.raises(SettingsConflict, match="COMMAND_CONFLICT"):
            await owner.handle(KeySettingsControl.model_validate(changed))
        with pytest.raises(SettingsConflict, match="REVISION_CONFLICT"):
            await owner.handle(KeySettingsControl.model_validate(save(connection)))
        selected = {
            "connection_id": connection,
            "connection_revision": 1,
            "model": "synthetic/model",
            "output_tokens": 64,
        }
        selection = KeySettingsControl.model_validate(
            {
                "op": "provider_settings",
                "request": {
                    "action": "save_selection",
                    "command_id": str(uuid4()),
                    "expected_revision": 0,
                    "default": selected,
                    "brain": None,
                    "investigator": selected,
                    "validator": None,
                },
            }
        )
        configured = await owner.handle(selection)
        assert configured.selection is not None
        assert configured.selection.revision == 1
        assert configured.selection.investigator == configured.selection.default
        rotated = await owner.handle(
            KeySettingsControl.model_validate(save(connection, 1, "rotated-key"))
        )
        assert rotated.connections[0].revision == 2
        # Replay uses original receipt, not the edited head or stale selected revision.
        assert await owner.handle(selection) == configured
        with pytest.raises(SettingsConflict, match="CONNECTION_UNAVAILABLE"):
            await owner.handle(
                KeySettingsControl.model_validate(
                    {
                        "op": "provider_settings",
                        "request": {
                            **selection.request.model_dump(mode="json"),
                            "command_id": str(uuid4()),
                            "expected_revision": 1,
                        },
                    }
                )
            )
        (keys / "master.key").unlink()
        revoked = await owner.handle(
            KeySettingsControl.model_validate(
                {
                    "op": "provider_settings",
                    "request": {
                        "action": "revoke_connection",
                        "command_id": str(uuid4()),
                        "connection_id": connection,
                        "expected_revision": 2,
                    },
                }
            )
        )
        assert not revoked.connections[0].enabled
        assert revoked.connections[0].revision == 3
        assert revoked.vault_status == "LOCKED"
        assert not revoked.connections[0].credential_present
        async with engine.connect() as db:
            for table in (
                "provider_connection_revision",
                "provider_selection_revision",
                "provider_settings_command",
            ):
                serialized = str(
                    (await db.execute(text(f"SELECT row_to_json(t)::text FROM {table} t"))).all()
                )
                assert "synthetic-secret-canary" not in serialized
                assert sha256(b"synthetic-secret-canary").hexdigest() not in serialized
                assert "rotated-key" not in serialized
        current = await ProviderSettingsOwner(
            service, process, epoch, ProviderVault(data, keys, instance)
        ).handle(
            KeySettingsControl.model_validate(
                {"op": "provider_settings", "request": {"action": "read"}}
            )
        )
        assert current.connections == revoked.connections
    finally:
        await service.release(process, epoch)
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage",
    [
        "missing_both",
        "instance_id_number",
        "instance_id_list",
        "secret_id_number",
        "secret_id_list",
    ],
)
async def test_damaged_vault_stays_locked_with_committed_local_revoke(
    migrated_database_url: URL, tmp_path: Path, damage: str
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    process = uuid4()
    epoch = await service.acquire(process)
    status = await service.owned_status(process, epoch)
    await service.open(uuid4(), status.generation, process, epoch)
    data, keys = tmp_path / "vault", tmp_path / "keys"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    vault = ProviderVault(data, keys, str(status.instance_id))
    owner = ProviderSettingsOwner(service, process, epoch, vault)
    connection = str(uuid4())
    read = KeySettingsControl.model_validate(
        {"op": "provider_settings", "request": {"action": "read"}}
    )
    try:
        initial = await owner.handle(KeySettingsControl.model_validate(save(connection)))
        assert initial.vault_status == "UNLOCKED"
        if damage == "missing_both":
            (data / "vault.json").unlink()
            (keys / "master.key").unlink()
        else:
            field, kind = damage.rsplit("_", 1)
            payload = json.loads((data / "vault.json").read_text())
            payload["entries"][0]["ref"][field] = 123 if kind == "number" else []
            (data / "vault.json").write_text(json.dumps(payload))
        before = {path: path.read_bytes() for root in (data, keys) for path in root.iterdir()}
        with pytest.raises(VaultLocked):
            await owner.handle(KeySettingsControl.model_validate(save(connection, 1)))
        assert {
            path: path.read_bytes() for root in (data, keys) for path in root.iterdir()
        } == before
        locked = await owner.handle(read)
        assert locked.vault_status == "LOCKED"
        assert locked.connections[0].revision == 1
        assert not locked.connections[0].credential_present
        revoke = KeySettingsControl.model_validate(
            {
                "op": "provider_settings",
                "request": {
                    "action": "revoke_connection",
                    "command_id": str(uuid4()),
                    "connection_id": connection,
                    "expected_revision": 1,
                },
            }
        )
        revoked = await owner.handle(revoke)
        assert revoked.vault_status == "LOCKED"
        assert not revoked.connections[0].enabled
        assert not revoked.connections[0].credential_present
        assert revoked.connections[0].revision == 2
        assert (await owner.handle(read)).connections == revoked.connections
        assert await owner.handle(revoke) == revoked
        async with engine.connect() as db:
            assert (
                await db.execute(text("SELECT count(*) FROM provider_connection_revision"))
            ).scalar_one() == 2
            assert (
                await db.execute(text("SELECT count(*) FROM provider_settings_command"))
            ).scalar_one() == 2
        # Even a revoked head retains credential history; it is not a fresh setup.
        with pytest.raises(VaultLocked):
            await owner.handle(KeySettingsControl.model_validate(save(connection, 2)))
        assert {
            path: path.read_bytes() for root in (data, keys) for path in root.iterdir()
        } == before
    finally:
        await service.release(process, epoch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_save_keeps_writer_owned_until_quiescent(
    migrated_database_url: URL, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    process = uuid4()
    epoch = await service.acquire(process)
    status = await service.owned_status(process, epoch)
    await service.open(uuid4(), status.generation, process, epoch)
    data, keys = tmp_path / "vault", tmp_path / "keys"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    vault = ProviderVault(data, keys, str(status.instance_id))
    owner = ProviderSettingsOwner(service, process, epoch, vault)
    entered, release = threading.Event(), threading.Event()
    original = vault.put

    def slow_put(reference: object, secret: str) -> None:
        entered.set()
        assert release.wait(5)
        assert isinstance(reference, CredentialRef)
        original(reference, secret)

    monkeypatch.setattr(vault, "put", slow_put)
    command = KeySettingsControl.model_validate(save(str(uuid4())))
    task = asyncio.create_task(owner.handle(command))
    try:
        async with asyncio.timeout(3):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not await owner.drain()
        with pytest.raises(ValueError, match="writer"):
            await owner.handle(KeySettingsControl.model_validate(save(str(uuid4()))))
        release.set()
        assert await owner.drain()
        async with engine.connect() as db:
            assert (
                await db.execute(text("SELECT count(*) FROM provider_connection_revision"))
            ).scalar_one() == 0
            assert (
                await db.execute(text("SELECT count(*) FROM provider_settings_command"))
            ).scalar_one() == 0
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await service.release(process, epoch)
        await engine.dispose()
