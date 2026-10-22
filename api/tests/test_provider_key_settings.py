"""T1 Settings contract and real PostgreSQL owner consumer; no provider calls."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from multiprocessing.connection import Connection
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings import provider_vault
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


def _predecessor_writer(
    data: Path, keys: Path, reference: CredentialRef, phase: str, channel: Connection[str, str]
) -> None:
    async def run() -> None:
        engine = database_engine("postgresql+psycopg://unused")  # No connection is opened.
        vault = ProviderVault(data, keys, reference.instance_id)
        owner = ProviderSettingsOwner(InstanceService(engine), uuid4(), 1, vault)
        entered = threading.Event()

        def pause() -> None:
            channel.send("ready")
            entered.set()
            assert channel.poll(10), "SOURCE release deadline"
            assert channel.recv() == "release"

        original = provider_vault._durable

        def durable(path: Path, value: bytes) -> None:
            pause()
            original(path, value)

        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        queued = loop.run_in_executor(None, pause) if phase == "queued" else None
        with pytest.MonkeyPatch.context() as patch:
            if phase == "active":
                patch.setattr(provider_vault, "_durable", durable)
            control = asyncio.create_task(
                owner._vault_write(lambda: vault.put(reference, "synthetic-predecessor"))
            )
            try:
                async with asyncio.timeout(3):
                    while not entered.is_set() or not owner.writes:
                        await asyncio.sleep(0.001)
                control.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await control
                channel.send("cancelled")
                if queued is not None:
                    await queued
                await asyncio.gather(*owner.writes)
                assert vault.contains(reference)
                channel.send("done")
            finally:
                await asyncio.gather(control, return_exceptions=True)
                await engine.dispose()

    try:
        asyncio.run(run())
    finally:
        channel.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["active", "queued"])
async def test_successor_drain_accounts_for_cross_process_writers(
    tmp_path: Path, phase: str
) -> None:
    data, keys = tmp_path / "vault", tmp_path / "keys"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    reference = CredentialRef(str(uuid4()), str(uuid4()), 1, "openrouter")
    vault = ProviderVault(data, keys, reference.instance_id)
    vault.bootstrap()
    before = (data / "vault.json").read_bytes()
    engine = database_engine("postgresql+psycopg://unused")
    successor = ProviderSettingsOwner(InstanceService(engine), uuid4(), 2, vault)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    predecessor = context.Process(
        target=_predecessor_writer, args=(data, keys, reference, phase, child)
    )
    predecessor.start()
    child.close()
    try:
        for expected in ("ready", "cancelled"):
            assert await asyncio.to_thread(parent.poll, 5)
            assert parent.recv() == expected
        assert not successor.writes
        assert not await successor.drain()
        assert (data / "vault.json").read_bytes() == before
    finally:
        parent.send("release")
        await asyncio.to_thread(predecessor.join, 10)
        if predecessor.is_alive():
            predecessor.kill()
            await asyncio.to_thread(predecessor.join, 3)
        parent.close()
        await engine.dispose()
    assert predecessor.exitcode == 0
    assert await successor.drain()
    assert vault.contains(reference)
    settled = (data / "vault.json").read_bytes()
    assert settled != before
    await asyncio.sleep(0.05)
    assert (data / "vault.json").read_bytes() == settled


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["shutdown", "queued", "active"])
async def test_failed_submit_settles_reservation_without_late_unowned_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    data, keys = tmp_path / "vault", tmp_path / "keys"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    reference = CredentialRef(str(uuid4()), str(uuid4()), 1, "openrouter")
    vault = ProviderVault(data, keys, reference.instance_id)
    vault.bootstrap()
    before = (data / "vault.json").read_bytes()
    engine = database_engine("postgresql+psycopg://unused")  # SOURCE: no DB connection.
    owner = ProviderSettingsOwner(InstanceService(engine), uuid4(), 1, vault)
    successor = ProviderSettingsOwner(InstanceService(engine), uuid4(), 2, vault)
    entered, release, unblock = threading.Event(), threading.Event(), threading.Event()
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=2 if failure == "active" else 1)
    loop.set_default_executor(pool)
    blocker = loop.run_in_executor(None, unblock.wait, 10) if failure == "active" else None

    def write() -> None:
        entered.set()
        if failure == "active":
            assert release.wait(10), "SOURCE active writer release deadline"
        vault.put(reference, "synthetic-submit-failure")

    def refuse_start(thread: threading.Thread) -> None:
        if failure == "active":
            unblock.set()
            assert entered.wait(3), "SOURCE already-started writer deadline"
        raise RuntimeError("can't start new thread")

    try:
        if failure == "shutdown":
            pool.shutdown()
        with monkeypatch.context() as patch:
            if failure != "shutdown":
                patch.setattr(threading.Thread, "start", refuse_start)
            with pytest.raises(RuntimeError, match="after shutdown|can't start new thread"):
                await owner._vault_write(write)
        await asyncio.sleep(0)
        assert not owner.writes
        assert (data / "vault.json").read_bytes() == before
        if failure == "active":
            assert entered.is_set()
            assert not await successor.drain()
        else:
            assert not entered.is_set()
            assert await successor.drain()
        release.set()
        if failure == "queued":
            # A real failed Thread.start left the original work item in this pool's queue.
            await loop.run_in_executor(None, lambda: None)
        pool.shutdown(wait=True)
        if blocker is not None:
            assert await blocker
        assert await successor.drain()
        if failure == "active":
            assert vault.get(reference) == "synthetic-submit-failure"
        else:
            assert not entered.is_set()
            assert (data / "vault.json").read_bytes() == before
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        recovered = CredentialRef(reference.instance_id, str(uuid4()), 1, "openrouter")
        await owner._vault_write(lambda: vault.put(recovered, "synthetic-recovered"))
        assert vault.get(recovered) == "synthetic-recovered"
        assert await successor.drain()
    finally:
        release.set()
        unblock.set()
        pool.shutdown(wait=True)
        if blocker is not None:
            await blocker
        await engine.dispose()


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
@pytest.mark.parametrize("phase", ["active", "pre_lock"])
async def test_cancelled_save_keeps_writer_owned_until_quiescent(
    migrated_database_url: URL, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
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
    vault.bootstrap()
    entered, release = threading.Event(), threading.Event()
    original = vault.put

    def slow_put(reference: object, secret: str) -> None:
        entered.set()
        assert release.wait(10)
        assert isinstance(reference, CredentialRef)
        original(reference, secret)

    original_durable = provider_vault._durable

    def slow_durable(path: Path, value: bytes) -> None:
        entered.set()
        assert release.wait(10)
        original_durable(path, value)

    if phase == "active":
        monkeypatch.setattr(provider_vault, "_durable", slow_durable)
    else:
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
        await service.release(process, epoch)
        process = uuid4()
        epoch = await service.acquire(process)
        assert epoch == owner.epoch + 1
        successor = ProviderSettingsOwner(
            service, process, epoch, ProviderVault(data, keys, str(status.instance_id))
        )
        service.runtime_drain = successor.drain
        assert not successor.writes
        with pytest.raises(ControlConflict, match="SHUTDOWN_INCOMPLETE"):
            await service.quiesce(process, epoch)
        assert (await service.owned_status(process, epoch)).quiesced_generation is None
        release.set()
        assert await owner.drain()
        await service.quiesce(process, epoch)
        quiesced = await service.owned_status(process, epoch)
        assert quiesced.quiesced_generation == quiesced.generation
        settled = (data / "vault.json").read_bytes()
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            await owner.handle(KeySettingsControl.model_validate(save(str(uuid4()))))
        assert (data / "vault.json").read_bytes() == settled
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
