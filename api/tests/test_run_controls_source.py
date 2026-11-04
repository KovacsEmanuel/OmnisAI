"""Actual owner commands with a transaction seam, not SQL or physical drain proof."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql.elements import TextClause

from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.runs.run_contract import (
    CommandReceipt,
    Question,
    RunCommand,
    RunControl,
    RunView,
    Setup,
)
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from test_run_owner_source import fixture_run, fixture_setup_payload


@dataclass
class Owned:
    owner: AgentRunOwner
    run: RunView
    question: Question | None
    writes: list[str]


@pytest.fixture
def owned(monkeypatch: pytest.MonkeyPatch) -> Owned:
    run = fixture_run()
    owner = object.__new__(AgentRunOwner)
    engine = object.__new__(AsyncEngine)
    db = object.__new__(AsyncConnection)
    service = InstanceService(engine)
    settings = object.__new__(ProviderSettingsOwner)
    settings.owner, settings.epoch, settings.lock = UUID(run.owner_id), 1, asyncio.Lock()
    owner.settings, owner.service, owner.instance = settings, service, run.instance_id
    owner.closing, owner.draining, owner.failed, owner.tasks = False, False, False, {}
    from unittest.mock import AsyncMock

    from omnis.modules.settings.provider_vault import ProviderVault

    settings.vault = object.__new__(ProviderVault)
    monkeypatch.setattr(ProviderVault, "get", lambda self, reference: "synthetic-unused-key")
    monkeypatch.setattr(ProviderSettingsOwner, "connections", AsyncMock(return_value=[]))
    state = Owned(owner, run, None, [])

    @asynccontextmanager
    async def connection() -> AsyncIterator[AsyncConnection]:
        yield db

    def connect(self: AsyncEngine) -> AbstractAsyncContextManager[AsyncConnection]:
        assert self is engine
        return connection()

    @asynccontextmanager
    async def admission(
        self: InstanceService, generation: int, owner: UUID, epoch: int
    ) -> AsyncIterator[AsyncConnection]:
        assert generation == state.run.generation and owner == settings.owner and epoch == 1
        yield db
        state.writes.append("commit")

    async def read_run(db: AsyncConnection, instance: str, identity: str) -> RunView:
        assert instance == run.instance_id and identity == run.run_id
        return state.run

    async def save_run(db: AsyncConnection, value: RunView, *, initial: bool = False) -> None:
        state.run = value
        state.writes.append("run:" + value.state)

    async def setup(db: AsyncConnection, instance: str, reference: Ref) -> Setup:
        assert reference == run.setup_ref
        return object.__new__(Setup)

    async def revalidate(self: AgentRunOwner, db: AsyncConnection, snapshot: Setup) -> None:
        state.writes.append("revalidate")

    async def new_attempt(
        self: AgentRunOwner,
        db: AsyncConnection,
        current: RunView,
        snapshot: Setup,
        *,
        role: str,
        brief: str,
        parent: str | None,
    ) -> RunView:
        state.writes.append("new_attempt")
        return current.model_copy(update={"active_attempt_id": str(uuid4())})

    async def replay(
        db: AsyncConnection, instance: str, command: str, payload: object | None = None
    ) -> CommandReceipt | None:
        return None

    async def receipt(
        db: AsyncConnection, instance: str, request: object, result: CommandReceipt
    ) -> None:
        state.writes.append("receipt")

    async def event(db: AsyncConnection, value: RunView, kind: str, summary: str) -> int:
        state.writes.append("event")
        return 1

    async def question(db: AsyncConnection, value: RunView) -> Question | None:
        return state.question

    async def drain(self: AgentRunOwner, identity: str) -> None:
        assert not settings.lock.locked()
        assert state.writes[-1] == "commit" and state.run.fence == run.fence + 1
        assert state.run.state in {"PAUSING", "STOPPING"}
        state.writes.append("drain")

    async def execute(
        self: AsyncConnection, statement: TextClause, parameters: dict[str, object]
    ) -> CursorResult[tuple[object, ...]]:
        assert "UPDATE run_inbox SET held=false" in str(statement)
        assert parameters == {"instance": run.instance_id, "run": run.run_id}
        state.writes.append("release_inbox")
        result: CursorResult[tuple[object, ...]] = object.__new__(CursorResult)
        result.rowcount = 1
        return result

    monkeypatch.setattr(AsyncEngine, "connect", connect)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    monkeypatch.setattr(InstanceService, "admission", admission)
    monkeypatch.setattr(store, "run", read_run)
    monkeypatch.setattr(store, "save_run", save_run)
    monkeypatch.setattr(store, "setup", setup)
    monkeypatch.setattr(store, "question", question)
    monkeypatch.setattr(store, "replay", replay)
    monkeypatch.setattr(store, "receipt", receipt)
    monkeypatch.setattr(store, "event", event)
    monkeypatch.setattr(AgentRunOwner, "revalidate", revalidate)
    monkeypatch.setattr(AgentRunOwner, "new_attempt", new_attempt)
    monkeypatch.setattr(AgentRunOwner, "drain_run", drain)
    monkeypatch.setattr(AgentRunOwner, "spawn", lambda self, identity: state.writes.append("spawn"))
    return state


def command(state: Owned, action: str, **changes: object) -> RunControl:
    return RunControl(
        op="agent_run",
        request=RunCommand.model_validate(
            {
                "action": action,
                "command_id": str(uuid4()),
                "run_id": state.run.run_id,
                "expected_generation": state.run.generation,
                "expected_revision": state.run.revision,
                **changes,
            }
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["pause", "stop"])
async def test_owner_commits_fence_and_receipt_before_awaiting_drain(
    owned: Owned, action: str
) -> None:
    result = await owned.owner.handle(command(owned, action))
    assert result["state"] == "ADMITTED" and owned.writes[-1] == "drain"


@pytest.mark.asyncio
@pytest.mark.parametrize("pending", [False, True])
async def test_manual_resume_releases_held_results_but_never_answers_question(
    owned: Owned, pending: bool
) -> None:
    owned.run = owned.run.model_copy(update={"state": "PAUSED"})
    if pending:
        owned.question = Question(
            question_id=str(uuid4()),
            run_id=owned.run.run_id,
            task_id=str(uuid4()),
            revision=1,
            cause="Clarify",
            text="Which input?",
            refs=[],
            state="PENDING",
        )
    await owned.owner.handle(command(owned, "resume"))
    assert "release_inbox" in owned.writes
    assert ("new_attempt" in owned.writes) is not pending
    assert owned.writes.index("revalidate") < owned.writes.index("release_inbox")
    if not pending:
        assert owned.writes.index("release_inbox") < owned.writes.index("new_attempt")


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["HOLD", "PAUSED", "STOPPED", "NEEDS_RECONCILIATION"])
async def test_answer_cannot_resume_or_change_control_state(owned: Owned, state: str) -> None:
    owned.run = owned.run.model_copy(update={"state": state})
    with pytest.raises(ModelConflict):
        await owned.owner.handle(
            command(owned, "answer", question_id=str(uuid4()), answer="Resume and widen ROE")
        )
    assert owned.writes == [] and owned.run.state == state


@pytest.mark.asyncio
async def test_stale_revision_cannot_stop_or_write_receipt(owned: Owned) -> None:
    with pytest.raises(ModelConflict, match="REVISION_CONFLICT"):
        await owned.owner.handle(command(owned, "stop", expected_revision=2))
    assert owned.writes == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exit_kind, expected",
    [
        ("direct", "SUCCEEDED"),
        ("incomplete", "INCONCLUSIVE"),
        ("error", "FAILED"),
        ("cancel", "CANCELLED"),
        ("brain_finish", "SUCCEEDED"),
    ],
)
async def test_actual_owner_finalization_persists_before_continuation(
    owned: Owned, monkeypatch: pytest.MonkeyPatch, exit_kind: str, expected: str
) -> None:
    from omnis.modules.runs import model_test_store as records
    from omnis.modules.runs.run_contract import Attempt, BrainDecision, WorkerFinal

    reference = Ref(
        instance_id=owned.run.instance_id,
        kind="run-tool-result-v1",
        id=str(uuid4()),
        digest="a" * 64,
    )
    actor = Attempt(
        instance_id=owned.run.instance_id,
        run_id=owned.run.run_id,
        task_id=str(uuid4()),
        attempt_id=str(uuid4()),
        role="BRAIN" if exit_kind == "brain_finish" else "RECON",
        parent_task_id=None,
        state="RUNNING",
        brief="Inert",
        input_refs=[reference],
        input_text="Inert",
        instructions="Inert",
        configured_model="fixture/recon",
        skill_refs=[],
        read_receipt_ref=None if exit_kind == "incomplete" else reference,
        correction_count=1,
    )
    saved: list[Attempt] = []
    payloads: list[dict[str, object]] = []

    async def setup(db: AsyncConnection, instance: str, ref: Ref) -> Setup:
        return Setup.model_validate(
            {**fixture_setup_payload(), "context_ref": reference.model_dump()}
        )

    async def put(db: AsyncConnection, instance: str, kind: str, payload: dict[str, object]) -> Ref:
        payloads.append(payload)
        owned.writes.append("persist:" + kind)
        return reference.model_copy(update={"kind": kind})

    async def save_attempt(db: AsyncConnection, attempt: Attempt, *, initial: bool = False) -> None:
        saved.append(attempt)
        owned.writes.append("attempt")

    async def add_inbox(db: AsyncConnection, run: RunView, ref: Ref) -> None:
        owned.writes.append("inbox")

    async def consume(
        db: AsyncConnection, run: RunView, references: list[Ref], decision: Ref
    ) -> None:
        assert references == [reference] and payloads
        owned.writes.append("consume")

    async def event(*args: object, **kwargs: object) -> int:
        owned.writes.append("event")
        return 1

    monkeypatch.setattr(store, "setup", setup)
    monkeypatch.setattr(records, "put", put)
    monkeypatch.setattr(store, "save_attempt", save_attempt)
    monkeypatch.setattr(store, "add_inbox", add_inbox)
    monkeypatch.setattr(store, "consume", consume)
    monkeypatch.setattr(store, "event", event)
    output: str | None = WorkerFinal(
        summary="Inert result", consumed_refs=[reference], gaps=[]
    ).model_dump_json()
    reason: str | None = None
    if exit_kind == "error":
        output, reason = None, "MODEL_RESPONSE_UNKNOWN"
    elif exit_kind == "cancel":
        output, reason = None, "CANCELLED"
        owned.run = owned.run.model_copy(update={"state": "STOPPING"})
    elif exit_kind == "brain_finish":
        output = BrainDecision(
            action="finish", summary="Read result", detail="S1 only", consumed_refs=[reference]
        ).model_dump_json()
    await owned.owner.complete(object.__new__(AsyncConnection), owned.run, actor, output, reason)
    assert len(saved) == 1 and saved[0].state == expected
    assert "new_attempt" not in owned.writes and "spawn" not in owned.writes
    if exit_kind == "brain_finish":
        assert owned.writes == [
            "persist:run-decision-v1",
            "consume",
            "attempt",
            "event",
            "run:LIMITED",
        ]
    else:
        assert owned.writes[:4] == ["persist:run-result-v1", "attempt", "inbox", "event"]
        assert "consume" not in owned.writes


@pytest.mark.asyncio
async def test_dispatch_absolute_deadline_includes_secret_loading(
    owned: Owned, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnis.modules.instance.domain import InstanceStatus
    from omnis.modules.runs import model_test_store as records
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.modules.runs.run_contract import Attempt, RoleConfig
    from omnis.modules.settings.provider_vault import ProviderVault
    from omnis.supervisor.agent_runner import AgentStep, StepResult
    from omnis.supervisor.model_relay_protocol import Scope

    config = RoleConfig.model_validate(
        {
            "choice": {
                "connection_id": str(uuid4()),
                "connection_revision": 1,
                "model": "fixture/recon",
                "output_tokens": 128,
            },
            "connection": {
                "connection_id": str(uuid4()),
                "provider": "openrouter",
                "revision": 1,
                "enabled": True,
                "secret_id": str(uuid4()),
                "credential_revision": 1,
            },
            "capabilities_ref": owned.run.setup_ref.model_dump(),
        }
    )
    actor = Attempt(
        instance_id=owned.run.instance_id,
        run_id=owned.run.run_id,
        task_id=str(uuid4()),
        attempt_id=str(uuid4()),
        role="RECON",
        parent_task_id=None,
        state="RUNNING",
        brief="Inert",
        input_refs=[],
        input_text="Inert",
        instructions="Inert",
        configured_model="fixture/recon",
        skill_refs=[],
    )
    owned.run = owned.run.model_copy(update={"active_attempt_id": actor.attempt_id})
    owned.owner.settings.vault = object.__new__(ProviderVault)
    owned.owner.model_owner = object.__new__(ApiKeyModelTest)
    owned.owner.runner = object.__new__(AgentStep)
    bounded = False
    original_timeout = asyncio.timeout

    @asynccontextmanager
    async def timeout_at(when: float | None) -> AsyncIterator[None]:
        nonlocal bounded
        assert when is not None and 299 < when - asyncio.get_running_loop().time() <= 300
        bounded = True
        # Deliberate SOURCE timer shortening; not a real elapsed-300s claim.
        async with original_timeout(0):
            yield

    async def secret_load(*args: object, **kwargs: object) -> str:
        assert bounded, "Vault await is outside the operation deadline"
        await asyncio.sleep(0)
        raise AssertionError("Deadline must expire before SDK")

    async def status(self: InstanceService, owner: UUID, epoch: int) -> InstanceStatus:
        return InstanceStatus(UUID(owned.run.instance_id), 0, True, None, None, 1, True, False)

    async def setup(db: AsyncConnection, instance: str, reference: Ref) -> Setup:
        return Setup.model_validate(
            {**fixture_setup_payload(), "brain": config.model_dump(), "recon": config.model_dump()}
        )

    async def attempt(db: AsyncConnection, run: RunView, identity: str) -> Attempt:
        return actor

    async def put(db: AsyncConnection, instance: str, kind: str, payload: dict[str, object]) -> Ref:
        return owned.run.setup_ref.model_copy(update={"kind": kind})

    async def scope(
        db: AsyncConnection, fields: dict[str, object], *, allocate: bool = False
    ) -> Scope:
        assert allocate
        return Scope(
            owned.run.instance_id,
            "MODEL_DISPATCH",
            str(fields["id"]),
            owned.run.owner_id,
            0,
            1,
            owned.run.fence,
            str(fields["deadline"]),
            "openrouter",
            1,
        )

    async def execute(
        self: AsyncConnection, statement: TextClause, parameters: dict[str, object]
    ) -> CursorResult[tuple[object, ...]]:
        assert "INSERT INTO run_dispatch" in str(statement)
        return object.__new__(CursorResult)

    async def dispatch_event(*args: object) -> None:
        return None

    async def retire(self: ApiKeyModelTest, *, recovery: bool = False) -> None:
        owned.writes.append("retire")

    async def finish(
        self: AgentRunOwner,
        db: AsyncConnection,
        identity: str,
        attempt_id: str,
        scope: Scope,
        result: StepResult | None,
        reason: str | None,
        *,
        admitted: bool,
    ) -> bool:
        assert result is None and reason == "MODEL_RESPONSE_UNKNOWN" and admitted
        owned.writes.append("expired")
        return False

    monkeypatch.setattr(asyncio, "timeout_at", timeout_at)
    monkeypatch.setattr(asyncio, "to_thread", secret_load)
    monkeypatch.setattr(InstanceService, "owned_status", status)
    monkeypatch.setattr(store, "setup", setup)
    monkeypatch.setattr(store, "attempt", attempt)
    monkeypatch.setattr(records, "put", put)
    monkeypatch.setattr(records, "relay_scope", scope)
    monkeypatch.setattr(store, "dispatch_event", dispatch_event)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    monkeypatch.setattr(ApiKeyModelTest, "retire_relay", retire)
    monkeypatch.setattr(AgentRunOwner, "finish_step", finish)
    await owned.owner.work(owned.run.run_id)
    assert "expired" in owned.writes


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_ack", [False, True])
async def test_recovery_drains_before_unknown_without_spawning(
    owned: Owned, monkeypatch: pytest.MonkeyPatch, lost_ack: bool
) -> None:
    from sqlalchemy.engine import ScalarResult

    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.supervisor.model_relay import RelayFailure

    owned.owner.model_owner = object.__new__(ApiKeyModelTest)
    db = object.__new__(AsyncConnection)

    async def retire(self: ApiKeyModelTest, *, recovery: bool = False) -> None:
        assert recovery
        owned.writes.append("drain_ack")
        if lost_ack:
            raise RelayFailure("RELAY_CONTROL_UNCERTAIN")

    @asynccontextmanager
    async def begin(self: AsyncEngine) -> AsyncIterator[AsyncConnection]:
        assert owned.writes == ["drain_ack"]
        yield db

    async def execute(
        self: AsyncConnection, statement: TextClause, parameters: dict[str, object]
    ) -> CursorResult[tuple[object, ...]]:
        result: CursorResult[tuple[object, ...]] = object.__new__(CursorResult)
        if "UPDATE run_dispatch" in str(statement):
            assert "state IN ('SENT','RESERVED')" in str(statement)
            assert "THEN 'RELEASED' ELSE 'UNKNOWN'" in str(statement)
            monkeypatch.setattr(result, "all", lambda: [(str(uuid4()), "UNKNOWN")])
        else:
            assert "SELECT run_id" in str(statement)
            values: ScalarResult[str] = object.__new__(ScalarResult)
            monkeypatch.setattr(values, "all", lambda: [owned.run.run_id])
            monkeypatch.setattr(result, "scalars", lambda: values)
        return result

    async def dispatch_event(db: AsyncConnection, instance: str, identity: str, state: str) -> None:
        assert state == "UNKNOWN"
        owned.writes.append("UNKNOWN")

    monkeypatch.setattr(ApiKeyModelTest, "retire_relay", retire)
    monkeypatch.setattr(AsyncEngine, "begin", begin)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    monkeypatch.setattr(store, "dispatch_event", dispatch_event)
    if lost_ack:
        with pytest.raises(RelayFailure, match="RELAY_CONTROL_UNCERTAIN"):
            await owned.owner.recover()
        assert owned.writes == ["drain_ack"]
    else:
        await owned.owner.recover()
        assert owned.run.state == "NEEDS_RECONCILIATION" and owned.run.reason == "OWNER_LOST"
        assert owned.writes == ["drain_ack", "UNKNOWN", "event", "run:NEEDS_RECONCILIATION"]
