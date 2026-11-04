"""Recon SOURCE contracts/owner paths; SQL seam doubles are not PostgreSQL QA."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.model_test_contract import Snapshot
from omnis.modules.settings.provider_key_models import KeySettingsControl, KeySettingsView
from omnis.modules.settings.provider_key_service import (
    ConnectionRevision,
    ProviderSettingsOwner,
    SettingsConflict,
)
from omnis.modules.settings.provider_model_models import ModelEntry
from omnis.modules.settings.provider_model_service import require_removable
from omnis.modules.settings.provider_vault import ProviderVault

ID = "11111111-1111-4111-8111-111111111111"
CHOICE = {
    "connection_id": ID,
    "connection_revision": 1,
    "model": "Exact/Model",
    "output_tokens": 64,
}
LEGACY = {
    "action": "save_selection",
    "command_id": ID,
    "expected_revision": 0,
    "default": CHOICE,
    "brain": None,
    "investigator": None,
    "validator": None,
}


def view(selection: object, command_id: str | None = None) -> dict[str, object]:
    return {
        "schema_version": 2,
        "command_id": command_id,
        "vault_status": "UNCONFIGURED",
        "connections": [],
        "selection": selection,
        "reachable": "NOT_VERIFIED",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.parametrize("recon", [None, {**CHOICE, "model": "Recon/Model", "output_tokens": 37}])
async def test_selection_wire_read_receipt_and_snapshot_preserve_versions(
    tmp_path: Path,
    versioned: bool,
    recon: object,
) -> None:
    payload = {**LEGACY, **({"action": "save_selection_v2", "recon": recon} if versioned else {})}
    wire = {"op": "provider_settings", "request": payload}
    command = KeySettingsControl.model_validate(wire)
    expected = json.dumps(wire, separators=(",", ":"), allow_nan=False).encode()
    assert command.wire_bytes() == expected
    assert sha256(command.wire_bytes()).digest() == sha256(expected).digest()
    selected = {
        "selection_id": ID,
        "revision": 1,
        **{key: payload[key] for key in ("default", "brain", "investigator", "validator")},
        **({"schema_version": 2, "recon": recon} if versioned else {}),
    }
    expected_view = view(selected, ID)
    assert KeySettingsView.model_validate(expected_view).model_dump(mode="json") == expected_view
    engine = database_engine("postgresql+psycopg://unused")
    owner = ProviderSettingsOwner(
        InstanceService(engine), UUID(ID), 1, ProviderVault(tmp_path / "v", tmp_path / "k", ID)
    )
    result = Mock()
    db = Mock(execute=AsyncMock(return_value=result))
    try:
        result.mappings.return_value.one_or_none.return_value = {
            "selection_id": ID,
            "revision": 1,
            "payload": payload,
        }
        read = await owner.selection(db)
        assert read is not None and read.model_dump(mode="json") == selected
        result.mappings.return_value.one_or_none.return_value = {
            "request_digest": sha256(expected).hexdigest(),
            "result": expected_view,
        }
        receipt = await owner.receipt(db, ID)
        assert receipt is not None and receipt[1].model_dump(mode="json") == expected_view
        snapshot = {
            "schema_version": 2,
            "selection": selected,
            "connection": {
                "connection_id": ID,
                "provider": "openrouter",
                "revision": 1,
                "enabled": True,
                "secret_id": ID,
                "credential_revision": 1,
            },
            "capabilities_ref": {
                "instance_id": ID,
                "kind": "model-capabilities-v2",
                "id": ID,
                "revision": 1,
                "digest": "a" * 64,
            },
            "data_policy": "FIXED_SYNTHETIC_ONLY",
            "endpoint": "https://openrouter.ai/api/v1",
        }
        assert Snapshot.model_validate(snapshot).model_dump(mode="json") == snapshot
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "changes",
    [
        {"recon": CHOICE},
        {"action": "save_selection_v2"},
        {"action": "save_selection_v2", "recon": {}},
        {"action": "save_selection_v2", "recon": {**CHOICE, "output_tokens": True}},
        {"action": "save_selection_v3", "recon": None},
    ],
)
def test_recon_is_required_nullable_only_in_new_command(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        KeySettingsControl.model_validate(
            {"op": "provider_settings", "request": {**LEGACY, **changes}}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "stale", "disabled", "foreign", "unregistered"])
async def test_save_recon_validates_explicit_choice_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str | None,
) -> None:
    engine = database_engine("postgresql+psycopg://unused")
    owner = ProviderSettingsOwner(
        InstanceService(engine), UUID(ID), 1, ProviderVault(tmp_path / "v", tmp_path / "k", ID)
    )
    connection = ConnectionRevision(
        connection_id=ID,
        provider="openrouter",
        revision=1,
        enabled=True,
        secret_id=ID,
        credential_revision=1,
    )
    monkeypatch.setattr(
        owner,
        "connections",
        AsyncMock(
            return_value=[
                connection,
                connection.model_copy(
                    update={
                        "connection_id": "22222222-2222-4222-8222-222222222222",
                        "provider": "orcarouter",
                        "enabled": False,
                    }
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        owner.service, "owned_status", AsyncMock(return_value=Mock(instance_id=ID, generation=1))
    )
    payload = {
        **LEGACY,
        "action": "save_selection_v2",
        "recon": {
            **CHOICE,
            "model": "Missing/Model" if fault == "unregistered" else "Recon/Model",
            "connection_revision": 2 if fault == "stale" else 1,
            "connection_id": "22222222-2222-4222-8222-222222222222"
            if fault == "disabled"
            else "33333333-3333-4333-8333-333333333333"
            if fault == "foreign"
            else ID,
        },
    }
    stored: dict[str, object] = {}

    async def execute(statement: object, parameters: dict[str, object]) -> Mock:
        sql = str(statement)
        result = Mock()
        result.mappings.return_value.one_or_none.return_value = None
        if "INSERT INTO public.provider_selection_revision" in sql:
            stored["selection"] = json.loads(str(parameters["payload"]))
        elif "INSERT INTO public.provider_settings_command" in sql:
            stored["receipt"] = {
                "request_digest": parameters["digest"],
                "result": json.loads(str(parameters["result"])),
            }
        elif "SELECT selection_id" in sql and "selection" in stored:
            result.mappings.return_value.one_or_none.return_value = {
                "selection_id": ID,
                "revision": 1,
                "payload": stored["selection"],
            }
        elif "SELECT request_digest" in sql:
            result.mappings.return_value.one_or_none.return_value = stored.get("receipt")
        elif "SELECT 1 FROM public.provider_model_entry" in sql:
            result.scalar_one_or_none.return_value = (
                None if parameters["model"] == "Missing/Model" else 1
            )
        return result

    db = Mock(execute=AsyncMock(side_effect=execute))

    @asynccontextmanager
    async def admitted(*args: object) -> AsyncIterator[Mock]:
        yield db

    monkeypatch.setattr(type(engine), "connect", admitted)
    monkeypatch.setattr(owner.service, "admission", admitted)
    command = KeySettingsControl.model_validate({"op": "provider_settings", "request": payload})
    try:
        if fault is not None:
            reason = "MODEL_NOT_REGISTERED" if fault == "unregistered" else "CONNECTION_UNAVAILABLE"
            with pytest.raises(SettingsConflict, match=reason):
                await owner.handle(command)
            assert stored == {}
        else:
            saved = await owner.handle(command)
            assert (
                saved.selection is not None
                and saved.selection.model_dump()["recon"] == payload["recon"]
            )
            assert (await owner.resolve_role(db, saved.selection, "recon")).model_dump() == payload[
                "recon"
            ]
            assert (
                await owner.resolve_role(db, saved.selection, "investigator")
            ).model_dump() == CHOICE
            for inherited in (
                {
                    "selection_id": ID,
                    "revision": 1,
                    **{
                        key: LEGACY[key]
                        for key in ("default", "brain", "investigator", "validator")
                    },
                },
                {**saved.selection.model_dump(), "recon": None},
            ):
                historical = KeySettingsView.model_validate(view(inherited)).selection
                assert historical is not None
                assert (await owner.resolve_role(db, historical, "recon")).model_dump() == CHOICE
            for bad_recon, reason in (
                ({**CHOICE, "connection_revision": 2}, "CONNECTION_UNAVAILABLE"),
                ({**CHOICE, "model": "Missing/Model"}, "MODEL_NOT_REGISTERED"),
            ):
                invalid_read = KeySettingsView.model_validate(
                    view({**saved.selection.model_dump(), "recon": bad_recon})
                ).selection
                assert invalid_read is not None
                with pytest.raises(SettingsConflict, match=reason):
                    await owner.resolve_role(db, invalid_read, "recon")
            assert stored["selection"] == payload
            assert (await owner.handle(command)).model_dump() == saved.model_dump()
            read = KeySettingsControl.model_validate(
                {"op": "provider_settings", "request": {"action": "read"}}
            )
            assert (await owner.handle(read)).selection == saved.selection
            receipt = KeySettingsControl.model_validate(
                {"op": "provider_settings", "request": {"action": "read", "command_id": ID}}
            )
            assert (await owner.handle(receipt)).model_dump() == saved.model_dump()
            conflict = KeySettingsControl.model_validate(
                {"op": "provider_settings", "request": {**payload, "recon": None}}
            )
            with pytest.raises(SettingsConflict, match="COMMAND_CONFLICT"):
                await owner.handle(conflict)
            stale_save = KeySettingsControl.model_validate(
                {
                    "op": "provider_settings",
                    "request": {**payload, "command_id": "22222222-2222-4222-8222-222222222222"},
                }
            )
            monkeypatch.setattr(owner, "receipt", AsyncMock(return_value=None))
            with pytest.raises(SettingsConflict, match="REVISION_CONFLICT"):
                await owner.handle(stale_save)
            assert sum("INSERT" in str(call.args[0]) for call in db.execute.call_args_list) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("stale", [False, True])
async def test_remove_recon_matches_connection_and_model_even_when_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stale: bool,
) -> None:
    engine = database_engine("postgresql+psycopg://unused")
    owner = ProviderSettingsOwner(
        InstanceService(engine), UUID(ID), 1, ProviderVault(tmp_path / "v", tmp_path / "k", ID)
    )
    selected = KeySettingsView.model_validate(
        view(
            {
                "selection_id": ID,
                "revision": 1,
                "schema_version": 2,
                "default": CHOICE,
                "brain": None,
                "investigator": None,
                "validator": None,
                "recon": {
                    **CHOICE,
                    "model": "Recon/Model",
                    "connection_revision": 7 if stale else 1,
                },
            }
        )
    ).selection
    monkeypatch.setattr(owner, "selection", AsyncMock(return_value=selected))
    result = Mock()
    result.first.return_value = None
    db = Mock(execute=AsyncMock(return_value=result))
    entry = ModelEntry.model_validate(
        {**CHOICE, "model": "Recon/Model", "entry_id": ID, "revision": 1}
    )
    try:
        with pytest.raises(SettingsConflict, match="MODEL_IN_USE"):
            await require_removable(owner, db, entry)
        await require_removable(owner, db, entry.model_copy(update={"model": "Other/Model"}))
        await require_removable(
            owner,
            db,
            entry.model_copy(update={"connection_id": "22222222-2222-4222-8222-222222222222"}),
        )
    finally:
        await engine.dispose()


def test_recon_maximum_encoded_command_frame_and_view_fit_existing_limits() -> None:
    maximum = 9223372036854775807
    choice = {
        **CHOICE,
        "connection_revision": maximum,
        "model": '\\"' * 128,
        "output_tokens": 65536,
    }
    command = KeySettingsControl.model_validate(
        {
            "op": "provider_settings",
            "request": {
                **LEGACY,
                "action": "save_selection_v2",
                "expected_revision": maximum,
                **{
                    role: choice
                    for role in ("default", "brain", "investigator", "validator", "recon")
                },
            },
        }
    )
    assert len(command.wire_bytes()) == 3432
    frame = (
        json.dumps(
            {"version": 1, "capability": "a" * 64, "command": command.wire()},
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )
    assert len(frame) == 3537 and len(frame) <= 4096
    selection = {
        "selection_id": ID,
        "revision": maximum,
        "schema_version": 2,
        **command.request.model_dump(exclude={"action", "command_id", "expected_revision"}),
    }
    result = KeySettingsView.model_validate(
        {
            **view(selection, ID),
            "connections": [
                {
                    "connection_id": ID
                    if provider == "openrouter"
                    else "22222222-2222-4222-8222-222222222222",
                    "provider": provider,
                    "revision": maximum,
                    "enabled": False,
                    "credential_present": False,
                }
                for provider in ("openrouter", "orcarouter")
            ],
        }
    )
    assert len(result.model_dump_json().encode()) <= 4096
