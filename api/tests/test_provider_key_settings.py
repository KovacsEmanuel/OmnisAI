"""T1 Settings contract and real PostgreSQL owner consumer; no provider calls."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from hashlib import sha256
from multiprocessing.connection import Connection
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings import provider_vault
from omnis.modules.settings.provider_key_models import KeySettingsControl, KeySettingsView
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner, SettingsConflict
from omnis.modules.settings.provider_model_models import ModelRegistryControl
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
        await owner.handle(
            ModelRegistryControl.model_validate(
                {
                    "op": "provider_models",
                    "request": {
                        "action": "save_models",
                        "command_id": str(uuid4()),
                        "expected_registry_revision": 0,
                        "connection_id": connection,
                        "connection_revision": 1,
                        "models": [
                            {
                                "entry_id": str(uuid4()),
                                "expected_revision": 0,
                                "model": "synthetic/model",
                                "output_tokens": 128,
                            }
                        ],
                    },
                }
            )
        )
        configured = await owner.handle(selection)
        assert configured.selection is not None
        assert configured.selection.revision == 1
        assert configured.selection.investigator == configured.selection.default
        rotated = await owner.handle(
            KeySettingsControl.model_validate(save(connection, 1, "rotated-key"))
        )
        assert rotated.connections[0].revision == 2
        with pytest.raises(SettingsConflict, match="MODEL_NOT_REGISTERED"):
            await owner.handle(
                KeySettingsControl.model_validate(
                    {
                        "op": "provider_settings",
                        "request": {
                            **selection.request.model_dump(mode="json"),
                            "command_id": str(uuid4()),
                            "expected_revision": 1,
                            "default": {**selected, "connection_revision": 2},
                            "investigator": None,
                        },
                    }
                )
            )
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,size",
    [
        ("model_test", 8192),
        ("native_task", 8192),
        ("provider_models", 256),
        ("provider_models", 65000),
        ("provider_models", 65536),
    ],
)
async def test_control_actual_writer_preserves_old_replies_and_bounds_registry(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, kind: str, size: int
) -> None:
    from omnis.modules.runs.model_test_contract import ModelTestView
    from omnis.transport.local_control import LocalControl

    engine = database_engine("postgresql+psycopg://unused")
    control = LocalControl(ipc_directory, InstanceService(engine), uuid4(), 1)
    payload: object = "a" * size
    wire_command: dict[str, object] = {"op": "status"}
    if kind == "model_test":
        wire_command = {"op": "model_test", "action": "read"}
        payload = ModelTestView(response_text="a" * size).model_dump(mode="json")
    if kind == "provider_models" and size == 256:
        from uuid import UUID

        from omnis.modules.settings.provider_model_models import (
            ModelEntry,
            ModelRegistryControl,
            ModelRegistryView,
        )

        maximum = 9223372036854775807
        entries = [
            ModelEntry(
                entry_id=str(UUID(int=index + 1)),
                revision=maximum,
                connection_id=str(UUID(int=1)),
                connection_revision=maximum,
                model="\\" * 250 + "".join('"' if bit == "1" else "\\" for bit in f"{index:06b}"),
                output_tokens=65536,
            )
            for index in range(64)
        ]
        wire_command = ModelRegistryControl.model_validate(
            {
                "op": "provider_models",
                "request": {
                    "action": "save_models",
                    "command_id": str(UUID(int=1)),
                    "expected_registry_revision": maximum,
                    "connection_id": str(UUID(int=1)),
                    "connection_revision": maximum,
                    "models": [
                        {
                            "entry_id": entry.entry_id,
                            "expected_revision": maximum,
                            "model": entry.model,
                            "output_tokens": 65536,
                        }
                        for entry in entries
                    ],
                },
            }
        ).wire()
        entries = entries[:16]
        payload = ModelRegistryView(
            command_id=str(UUID(int=1)),
            registry_revision=maximum,
            after=None,
            next_after=entries[-1].entry_id,
            total=64,
            entries=entries,
        ).model_dump(mode="json")
    monkeypatch.setattr(control, "_dispatch", AsyncMock(return_value={"ok": True, kind: payload}))
    async with await asyncio.start_unix_server(
        control._handle, path=str(ipc_directory / "reply.sock"), limit=65536
    ):
        reader, writer = await asyncio.open_unix_connection(
            ipc_directory / "reply.sock", limit=100000
        )
        try:
            frame = (
                json.dumps(
                    {"version": 1, "capability": control.capability, "command": wire_command},
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
            writer.write(frame)
            await writer.drain()
            raw = await asyncio.wait_for(reader.readuntil(b"\n"), 5)
            reply = json.loads(raw)
            print(f"ACTUAL_WRITER_{kind}_{size}: request={len(frame)} reply={len(raw)}")
            if kind == "provider_models" and size == 256:
                assert len(frame) == 41141 and len(raw) == 12096
            if kind == "provider_models" and size == 65536:
                assert len(raw) <= 65536 and reply["error"] == "CONTROL_UNAVAILABLE"
            else:
                assert reply["ok"] is True and reply[kind] == payload
                assert len(raw) <= 65536 if kind == "provider_models" else len(raw) > 4096
        finally:
            writer.close()
            await writer.wait_closed()
            await engine.dispose()


@pytest.mark.asyncio
async def test_registry_http_body_exception_is_exact_and_keeps_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from omnis.api import create_app

    monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as http:
        for method, path, size, expected in (
            ("PUT", "/api/v1/settings/models", 65536, 401),
            ("PUT", "/api/v1/settings/models", 65537, 413),
            ("PUT", "/api/v1/settings/models/", 4097, 413),
            ("POST", "/api/v1/settings/models", 4097, 413),
            ("PUT", "/api/v1/settings/providers", 4097, 413),
        ):
            response = await http.request(
                method,
                path,
                content=b" " * size,
                headers={"Origin": "http://127.0.0.1:8765", "Content-Type": "application/json"},
            )
            assert response.status_code == expected


def test_registry_authority_uses_typed_identity_revision_and_foreign_keys() -> None:
    from omnis.core.provider_schema import PROVIDER_TABLES

    assert {"provider_model_entry", "provider_model_entry_revision"} <= PROVIDER_TABLES.keys()
    identity, identity_constraints = PROVIDER_TABLES["provider_model_entry"]
    revision, revision_constraints = PROVIDER_TABLES["provider_model_entry_revision"]
    assert identity["model"] == ("text", True, None)
    assert {
        "connection_id",
        "connection_revision",
        "registry_revision",
        "output_tokens",
    } <= revision.keys()
    assert any(
        row[1:3] == ("u", "UNIQUE (instance_id, connection_id, model)")
        for row in identity_constraints
    )
    assert any(
        row[1:3]
        == (
            "f",
            "FOREIGN KEY (instance_id, connection_id, connection_revision) REFERENCES provider_connection_revision(instance_id, connection_id, revision)",
        )
        for row in revision_constraints
    )
    assert "entries" not in PROVIDER_TABLES["provider_model_registry_revision"][0]


def test_registry_model_sql_bounds_match_dto_and_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import re

    from omnis.core.provider_schema import PROVIDER_TABLES
    from omnis.modules.settings.provider_model_models import SaveModels

    migration = importlib.import_module("omnis.migrations.versions.0016_provider_models")
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    migration.upgrade()  # Capture emitted DDL/backfill only; no database connection.
    matched = re.search(r"model ~ '([^']+)'", statements[0])
    assert matched is not None
    pattern = matched.group(1)
    # PostgreSQL ARE bounds stop at 255, unlike Python's regex implementation.
    assert all(
        int(limit) <= 255
        for bounds in re.findall(r"\{(\d+)(?:,(\d*))?\}", pattern)
        for limit in bounds
        if limit
    )
    constraint = next(
        row[2]
        for row in PROVIDER_TABLES["provider_model_entry"][1]
        if row[0] == "provider_model_entry_model_check"
    )
    assert constraint == f"CHECK ((model ~ '{pattern}'::text))"
    request = {
        "action": "save_models",
        "command_id": str(uuid4()),
        "expected_registry_revision": 0,
        "connection_id": str(uuid4()),
        "connection_revision": 1,
    }
    printable = "".join(chr(code) for code in range(33, 127))
    for model, valid in (
        ("!", True),
        ((printable * 3)[:255], True),
        ((printable * 3)[:256], True),
        ("", False),
        ("x" * 257, False),
        ("with space", False),
        ("x\n", False),
        ("é", False),
        ("\x7f", False),
    ):
        assert (re.fullmatch(pattern, model) is not None) == valid
        payload = {
            **request,
            "models": [
                {
                    "entry_id": str(uuid4()),
                    "expected_revision": 0,
                    "model": model,
                    "output_tokens": 64,
                }
            ],
        }
        if valid:
            assert SaveModels.model_validate(payload).models[0].model == model
        else:
            with pytest.raises(ValueError):
                SaveModels.model_validate(payload)


def test_registry_has_separate_bounded_api_contract() -> None:
    from omnis.api import create_app

    schema = create_app().openapi()
    assert "/api/v1/settings/models" in schema["paths"]
    assert "SaveModels" in schema["components"]["schemas"]


def test_registry_merge_is_additive_exact_and_revision_checked() -> None:
    from omnis.modules.settings.provider_model_models import RegistryState, SaveModels
    from omnis.modules.settings.provider_model_service import merge_models

    connection, first, second = str(uuid4()), str(uuid4()), str(uuid4())
    request = SaveModels.model_validate(
        {
            "action": "save_models",
            "command_id": str(uuid4()),
            "expected_registry_revision": 0,
            "connection_id": connection,
            "connection_revision": 1,
            "models": [
                {
                    "entry_id": first,
                    "expected_revision": 0,
                    "model": "Exact/ID",
                    "output_tokens": 64,
                }
            ],
        }
    )
    state = merge_models(RegistryState(revision=0, entries=[]), request)
    assert state.revision == 1 and state.entries[0].revision == 1
    added = request.model_copy(
        update={
            "expected_registry_revision": 1,
            "models": [
                request.models[0].model_copy(update={"entry_id": second, "model": "exact/ID"})
            ],
        }
    )
    both = merge_models(state, added)
    assert both.revision == 2
    assert next(item for item in both.entries if item.entry_id == first) == state.entries[0]
    with pytest.raises(SettingsConflict, match="REVISION_CONFLICT"):
        merge_models(state, request)
    with pytest.raises(SettingsConflict, match="COMMAND_CONFLICT"):
        merge_models(
            state,
            added.model_copy(
                update={"models": [added.models[0].model_copy(update={"model": "Exact/ID"})]}
            ),
        )
    with pytest.raises(SettingsConflict, match="REVISION_CONFLICT"):
        merge_models(state, request.model_copy(update={"expected_registry_revision": 1}))
    with pytest.raises(SettingsConflict, match="COMMAND_CONFLICT"):
        merge_models(
            state,
            request.model_copy(
                update={
                    "expected_registry_revision": 1,
                    "connection_id": str(uuid4()),
                    "models": [request.models[0].model_copy(update={"expected_revision": 1})],
                }
            ),
        )


def test_registry_maximum_actual_dto_and_complete_wire_budgets() -> None:
    import json
    from uuid import UUID

    from omnis.modules.instance.schemas import ControlRequest
    from omnis.modules.settings.provider_model_models import (
        ModelEntry,
        ModelRegistryControl,
        ModelRegistryView,
        SaveModels,
    )

    maximum = 9223372036854775807
    identity = str(UUID(int=1))
    models = [
        {
            "entry_id": str(UUID(int=index + 1)),
            "expected_revision": maximum,
            "model": "\\" * 250 + "".join('"' if bit == "1" else "\\" for bit in f"{index:06b}"),
            "output_tokens": 65536,
        }
        for index in range(64)
    ]
    request = SaveModels.model_validate(
        {
            "action": "save_models",
            "command_id": identity,
            "expected_registry_revision": maximum,
            "connection_id": identity,
            "connection_revision": maximum,
            "models": models,
        }
    )
    control = ModelRegistryControl(op="provider_models", request=request)
    frame = (
        json.dumps(
            {"version": 1, "capability": "f" * 64, "command": control.wire()}, separators=(",", ":")
        ).encode()
        + b"\n"
    )
    parsed = ControlRequest.model_validate_json(frame)
    assert parsed.command == control
    entries = [
        ModelEntry(
            entry_id=item.entry_id,
            revision=maximum,
            connection_id=identity,
            connection_revision=maximum,
            model=item.model,
            output_tokens=65536,
        )
        for item in request.models[:16]
    ]
    view = ModelRegistryView(
        command_id=identity,
        registry_revision=maximum,
        after=None,
        next_after=entries[-1].entry_id,
        total=64,
        entries=entries,
    )
    reply = (
        json.dumps(
            {
                "ok": True,
                "provider_models": view.model_dump(mode="json"),
                "correlation_id": identity,
            }
        ).encode()
        + b"\n"
    )
    sizes = {
        "body": len(request.model_dump_json().encode()),
        "command": len(control.wire_bytes()),
        "frame": len(frame),
        "view": len(view.model_dump_json().encode()),
        "reply": len(reply),
    }
    print("REGISTRY_MAXIMUM_BYTES=" + json.dumps(sizes, sort_keys=True))
    assert sizes["body"] == 41001 and sizes["command"] == 41036 and sizes["frame"] == 41141
    assert sizes["reply"] <= 65536
    assert ModelRegistryView.model_validate_json(view.model_dump_json()) == view
    for bad in (
        {**request.model_dump(), "models": models + [models[0]]},
        {**request.model_dump(), "models": [models[0], models[0]]},
        {**request.model_dump(), "models": [{**models[0], "model": "with space"}]},
        {**request.model_dump(), "models": [{**models[0], "model": "x\n"}]},
        {**request.model_dump(), "models": [{**models[0], "expected_revision": True}]},
        {**request.model_dump(), "secret": "forbidden"},
    ):
        with pytest.raises(ValueError):
            SaveModels.model_validate(bad)


def test_registry_capacity_and_bound_pages() -> None:
    from uuid import UUID

    from omnis.modules.settings.provider_model_models import (
        ModelEntry,
        ReadModels,
        RegistryState,
        SaveModels,
    )
    from omnis.modules.settings.provider_model_service import merge_models, page

    connection = str(uuid4())
    entries = [
        ModelEntry(
            entry_id=str(UUID(int=index + 1)),
            revision=1,
            connection_id=connection,
            connection_revision=1,
            model=f"Exact/{index}",
            output_tokens=64,
        )
        for index in range(64)
    ]
    state = RegistryState(revision=1, entries=entries)
    request = SaveModels.model_validate(
        {
            "action": "save_models",
            "command_id": str(uuid4()),
            "expected_registry_revision": 1,
            "connection_id": str(uuid4()),
            "connection_revision": 1,
            "models": [
                {
                    "entry_id": str(uuid4()),
                    "expected_revision": 0,
                    "model": entries[0].model,
                    "output_tokens": 1,
                }
            ],
        }
    )
    with pytest.raises(SettingsConflict, match="REGISTRY_FULL"):
        merge_models(state, request)
    first = page(state, ReadModels(action="read"))
    second = page(state, ReadModels(action="read", registry_revision=1, after=first.next_after))
    assert len(first.entries) == len(second.entries) == 16 and first.total == second.total == 64
    assert set(item.entry_id for item in first.entries).isdisjoint(
        item.entry_id for item in second.entries
    )
    with pytest.raises(SettingsConflict, match="REVISION_CONFLICT"):
        page(state, ReadModels(action="read", registry_revision=0, after=first.next_after))
    with pytest.raises(SettingsConflict, match="NOT_FOUND"):
        page(state, ReadModels(action="read", registry_revision=1, after=str(uuid4())))
    with pytest.raises(ValueError):
        ReadModels(action="read", after=first.next_after)
    with pytest.raises(ValueError):
        first.model_validate({**first.model_dump(), "next_after": None})


def test_registry_frame_exception_never_relaxes_legacy_limits() -> None:
    import json

    from omnis.transport.local_control import decode_control_frame

    frame = json.dumps(
        {
            "version": 1,
            "capability": "f" * 64,
            "command": {"op": "provider_models", "request": {"action": "read"}},
        }
    ).encode()
    assert (
        decode_control_frame(frame + b" " * (65535 - len(frame)) + b"\n").command.op
        == "provider_models"
    )
    for invalid in (
        frame + b" " * (65536 - len(frame)) + b"\n",
        b'{"version":1,"version":1}\n',
        frame.replace(b'"version": 1', b'"version": NaN') + b"\n",
        frame.replace(b'"provider_models", "request": {"action": "read"}', b'"status"')
        + b" " * 4096
        + b"\n",
    ):
        with pytest.raises(ValueError):
            decode_control_frame(invalid)


@pytest.mark.asyncio
async def test_assignment_membership_denied_before_selection_or_receipt_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SOURCE transaction seam; real PostgreSQL controls remain in the PG consumer."""
    engine = database_engine("postgresql+psycopg://unused")
    service = InstanceService(engine)
    data, keys = tmp_path / "v", tmp_path / "k"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    owner = ProviderSettingsOwner(service, uuid4(), 1, ProviderVault(data, keys, str(uuid4())))
    connection = str(uuid4())
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db = Mock()
    db.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def admitted(*args: object) -> AsyncIterator[Mock]:
        yield db

    monkeypatch.setattr(type(service.engine), "connect", admitted)
    monkeypatch.setattr(service, "admission", admitted)
    monkeypatch.setattr(
        service,
        "owned_status",
        AsyncMock(return_value=Mock(instance_id=owner.vault.instance_id, generation=1)),
    )
    monkeypatch.setattr(owner, "receipt", AsyncMock(return_value=None))
    monkeypatch.setattr(owner, "selection", AsyncMock(return_value=None))
    monkeypatch.setattr(owner, "require_selection", AsyncMock())
    monkeypatch.setattr(
        owner,
        "view",
        AsyncMock(
            return_value=KeySettingsView(
                command_id=None, connections=[], selection=None, vault_status="UNCONFIGURED"
            )
        ),
    )
    command = KeySettingsControl.model_validate(
        {
            "op": "provider_settings",
            "request": {
                "action": "save_selection",
                "command_id": str(uuid4()),
                "expected_revision": 0,
                "default": {
                    "connection_id": connection,
                    "connection_revision": 1,
                    "model": "Not/Registered",
                    "output_tokens": 512,
                },
                "brain": None,
                "investigator": None,
                "validator": None,
            },
        }
    )
    try:
        with pytest.raises(SettingsConflict, match="MODEL_NOT_REGISTERED"):
            await owner.handle(command)
        assert all("INSERT" not in str(call.args[0]) for call in db.execute.call_args_list)
    finally:
        await engine.dispose()
