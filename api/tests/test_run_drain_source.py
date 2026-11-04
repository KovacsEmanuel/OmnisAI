"""Owner quiescence transitions/cursor with transaction and physical-drain seams."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.engine import CursorResult, ScalarResult
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql.elements import TextClause

from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.run_contract import RunView
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from test_run_owner_source import fixture_run


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["pause", "stop", "models", "recovery"])
@pytest.mark.parametrize("ack", [True, False])
async def test_drain_state_event_and_cursor_commit_together_once(
    monkeypatch: pytest.MonkeyPatch, mode: str, ack: bool
) -> None:
    initial = fixture_run().model_copy(
        update={
            "state": "PAUSING" if mode == "pause" else "STOPPING" if mode == "stop" else "RUNNING",
            "through_cursor": 5,
            "revision": 7,
        }
    )
    current = initial
    db = object.__new__(AsyncConnection)
    owner = object.__new__(AgentRunOwner)
    owner.instance, owner.tasks, owner.continuations = current.instance_id, {}, set()
    owner.failed, owner.closing, owner.draining = False, False, False
    owner.drain_lock = asyncio.Lock()
    owner.settings = object.__new__(ProviderSettingsOwner)
    owner.settings.lock = asyncio.Lock()
    owner.settings.owner, owner.settings.epoch = UUID(current.owner_id), current.owner_epoch
    owner.service = InstanceService(object.__new__(AsyncEngine))
    owner.model_owner = object.__new__(ApiKeyModelTest)
    events: list[str] = []
    commits: list[tuple[str, int, int]] = []
    drained = False
    in_transaction = False
    event_cursor = 5

    @asynccontextmanager
    async def begin(self: AsyncEngine) -> AsyncIterator[AsyncConnection]:
        nonlocal in_transaction
        in_transaction = True
        yield db
        commits.append((current.state, current.through_cursor, len(events)))
        in_transaction = False

    async def read(*args: object) -> RunView:
        return current

    async def event(connection: AsyncConnection, value: RunView, kind: str, summary: str) -> int:
        nonlocal event_cursor
        assert connection is db and in_transaction and kind == "control"
        if value.state in {"PAUSED", "STOPPED", "NEEDS_RECONCILIATION"}:
            assert drained
        events.append(value.state)
        event_cursor += 1
        return event_cursor

    async def save(connection: AsyncConnection, value: RunView, *, initial: bool = False) -> None:
        nonlocal current
        assert connection is db and in_transaction
        current = value

    async def retire(self: ApiKeyModelTest, *, recovery: bool = False) -> None:
        nonlocal drained
        assert not in_transaction and recovery == (mode == "recovery")
        if not ack:
            raise OSError("synthetic drain ACK lost")
        drained = True

    async def execute(
        self: AsyncConnection, sql: TextClause, params: object
    ) -> CursorResult[tuple[object, ...]]:
        result: CursorResult[tuple[object, ...]] = object.__new__(CursorResult)
        if "UPDATE run_dispatch" in str(sql):
            monkeypatch.setattr(result, "all", lambda: [])
        else:
            rows: ScalarResult[str] = object.__new__(ScalarResult)
            monkeypatch.setattr(
                rows, "all", lambda: [] if current.state in store.TERMINAL else [current.run_id]
            )
            monkeypatch.setattr(result, "scalars", lambda: rows)
        return result

    monkeypatch.setattr(AsyncEngine, "begin", begin)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    monkeypatch.setattr(store, "run", read)
    monkeypatch.setattr(store, "save_run", save)
    monkeypatch.setattr(store, "event", event)
    monkeypatch.setattr(ApiKeyModelTest, "retire_relay", retire)
    spawn = AsyncMock(side_effect=AssertionError("No wake during drain"))
    monkeypatch.setattr(AgentRunOwner, "spawn", spawn)

    async def invoke() -> None:
        if mode == "recovery":
            await owner.recover()
        elif mode == "models":
            assert await owner.drain_models()
        else:
            await owner.drain_run(current.run_id)

    if not ack:
        with pytest.raises(OSError, match="ACK lost"):
            await invoke()
        assert current.state not in {"PAUSED", "STOPPED", "NEEDS_RECONCILIATION"}
        assert events == (["STOPPING"] if mode == "models" else [])
    else:
        await invoke()
        expected = (
            "PAUSED"
            if mode == "pause"
            else "NEEDS_RECONCILIATION"
            if mode == "recovery"
            else "STOPPED"
        )
        assert current.state == expected
        assert events == (["STOPPING", "STOPPED"] if mode == "models" else [expected])
        assert current.through_cursor == 5 + len(events)
        assert current.revision == 7 + len(events)
        assert commits[-1] == (expected, current.through_cursor, len(events))
        before = current
        await invoke()
        assert current == before
        assert len(events) == (2 if mode == "models" else 1)
    assert not spawn.called
