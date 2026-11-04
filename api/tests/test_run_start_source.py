"""Start admission through the public route with SOURCE transaction/control seams."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_routes, run_store as store
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.run_contract import CommandReceipt, Setup, StartRun
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from test_run_owner_source import fixture_run, fixture_setup_payload
from test_run_routes_source import request_with_body


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["revision", "identity", "content", "removed", "current"])
async def test_start_rechecks_selection_and_registry_in_admission(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    run = fixture_run()
    snapshot = Setup.model_validate(fixture_setup_payload())
    db = object.__new__(AsyncConnection)
    owner = object.__new__(AgentRunOwner)
    owner.instance, owner.closing, owner.draining = run.instance_id, False, False
    owner.settings = object.__new__(ProviderSettingsOwner)
    owner.settings.owner, owner.settings.epoch = UUID(run.owner_id), run.owner_epoch
    owner.settings.lock = asyncio.Lock()
    owner.service = InstanceService(object.__new__(AsyncEngine))
    owner.model_owner = object.__new__(ApiKeyModelTest)
    owner.catalog = object.__new__(PublicationCatalog)
    admitted = False
    current = snapshot.selection_snapshot
    if change == "revision":
        current = current.model_copy(update={"revision": current.revision + 1})
    elif change == "identity":
        current = current.model_copy(update={"selection_id": str(uuid4())})
    elif change == "content":
        current = current.model_copy(
            update={"brain": current.default.model_copy(update={"model": "other"})}
        )

    @asynccontextmanager
    async def connection(*args: object) -> AsyncIterator[AsyncConnection]:
        yield db

    @asynccontextmanager
    async def admission(*args: object) -> AsyncIterator[AsyncConnection]:
        nonlocal admitted
        admitted = True
        yield db
        admitted = False

    async def selection(*args: object) -> object:
        assert admitted
        return current

    async def registered(*args: object) -> None:
        assert admitted
        if change == "removed":
            raise records.ModelConflict("MODEL_NOT_REGISTERED")

    monkeypatch.setattr(AsyncEngine, "connect", connection)
    monkeypatch.setattr(InstanceService, "admission", admission)
    monkeypatch.setattr(
        AsyncConnection, "scalar", AsyncMock(side_effect=[None, snapshot.draft_ref.revision])
    )
    monkeypatch.setattr(store, "replay", AsyncMock(return_value=None))
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(ProviderSettingsOwner, "selection", selection)
    monkeypatch.setattr(ProviderSettingsOwner, "require_registered", registered)
    monkeypatch.setattr(
        ProviderSettingsOwner,
        "require_selection",
        AsyncMock(return_value=snapshot.brain.connection),
    )
    monkeypatch.setattr(ApiKeyModelTest, "require_idle", AsyncMock())
    monkeypatch.setattr(PublicationCatalog, "load_core", AsyncMock())
    monkeypatch.setattr(records, "resolve", AsyncMock(return_value={}))
    saved, receipt, spawn = AsyncMock(), AsyncMock(), Mock()
    monkeypatch.setattr(store, "save_run", saved)
    monkeypatch.setattr(store, "receipt", receipt)
    monkeypatch.setattr(store, "event", AsyncMock(return_value=1))
    monkeypatch.setattr(AgentRunOwner, "new_attempt", AsyncMock(return_value=run))
    monkeypatch.setattr(AgentRunOwner, "spawn", spawn)
    monkeypatch.setattr(run_routes, "control_exchange", owner.handle)
    command = StartRun(
        command_id=str(uuid4()), expected_generation=0, expected_revision=1, setup_ref=run.setup_ref
    )
    response = await run_routes.mutate(
        request_with_body(command.model_dump_json().encode()), command
    )
    if change == "current":
        assert isinstance(response, CommandReceipt) and response.state == "ADMITTED"
        assert saved.await_count == 2 and receipt.await_count == spawn.call_count == 1
    else:
        assert not isinstance(response, CommandReceipt) and response.status_code == 409
        code = json.loads(bytes(response.body))["error"]["code"]
        assert code == ("MODEL_NOT_REGISTERED" if change == "removed" else "REVISION_CONFLICT")
        assert not saved.called and not receipt.called and not spawn.called


@pytest.mark.asyncio
async def test_active_run_revalidation_does_not_retarget_current_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = Setup.model_validate(fixture_setup_payload())
    owner = object.__new__(AgentRunOwner)
    owner.instance = fixture_run().instance_id
    owner.settings = object.__new__(ProviderSettingsOwner)
    owner.catalog = object.__new__(PublicationCatalog)
    selection = AsyncMock(side_effect=AssertionError("Active RUN must retain its own selection"))
    monkeypatch.setattr(ProviderSettingsOwner, "selection", selection)
    monkeypatch.setattr(
        ProviderSettingsOwner,
        "require_selection",
        AsyncMock(return_value=snapshot.brain.connection),
    )
    monkeypatch.setattr(records, "resolve", AsyncMock(return_value={}))
    monkeypatch.setattr(PublicationCatalog, "load_core", AsyncMock())
    await owner.revalidate(object.__new__(AsyncConnection), snapshot)
    assert not selection.called
