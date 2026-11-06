"""SOURCE owner decisions only. No database/lease/drain proof is claimed here."""

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import TextClause

from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.runs.run_contract import BrainDecision, RunCommand, RunControl, RunView, StartRun
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.transport.local_control import decode_control_frame


def fixture_run() -> RunView:
    instance = str(uuid4())
    return RunView(
        instance_id=instance,
        engagement_id=str(uuid4()),
        run_id=str(uuid4()),
        setup_ref=Ref(instance_id=instance, kind="run-setup-v1", id=str(uuid4()), digest="a" * 64),
        revision=1,
        generation=0,
        owner_id=str(uuid4()),
        owner_epoch=1,
        fence=1,
        state="RUNNING",
    )


def test_start_revision_cannot_be_a_boolean() -> None:
    run = fixture_run()
    with pytest.raises(ValueError):
        StartRun.model_validate(
            {
                "command_id": str(uuid4()),
                "expected_generation": 0,
                "expected_revision": True,
                "setup_ref": run.setup_ref.model_dump(),
            }
        )


@pytest.mark.parametrize("revision", [True, 1.0, None])
def test_consumed_refs_are_not_repaired_before_lookup(revision: object) -> None:
    ref = {**fixture_run().setup_ref.model_dump(), "revision": revision}
    with pytest.raises(ValueError):
        BrainDecision.model_validate(
            {"action": "finish", "summary": "Inert", "detail": "Done", "consumed_refs": [ref]}
        )


def test_run_command_and_full_private_frame_have_independent_bounds() -> None:
    run = fixture_run()
    command = RunCommand(
        action="answer",
        command_id=str(uuid4()),
        run_id=run.run_id,
        expected_generation=0,
        expected_revision=1,
        question_id=str(uuid4()),
        answer="Synthetic clarification",
    )
    control = RunControl(op="agent_run", request=command)
    frame = (
        ControlRequest(version=1, capability="a" * 64, command=control).model_dump_json().encode()
        + b"\n"
    )
    assert decode_control_frame(frame).command == control
    exact = frame[:-1] + b" " * (4096 - len(frame)) + b"\n"
    assert len(exact) == 4096 and decode_control_frame(exact).command == control
    with pytest.raises(ValueError, match="Oversized legacy frame"):
        decode_control_frame(exact[:-1] + b" \n")
    with pytest.raises(ValueError):
        RunCommand.model_validate({**command.model_dump(), "answer": "\t" * 1800})


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["exact", "foreign", "duplicate", "missing"])
async def test_brain_consumption_requires_exact_pending_refs_before_write(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    run = fixture_run()
    reference = Ref(
        instance_id=run.instance_id, id=str(uuid4()), kind="run-result-v1", digest="b" * 64
    )
    decision = Ref(
        instance_id=run.instance_id, id=str(uuid4()), kind="run-decision-v1", digest="c" * 64
    )
    connection = object.__new__(AsyncConnection)
    updates: list[dict[str, object]] = []

    async def inbox(db: AsyncConnection, current: RunView) -> list[tuple[Ref, dict[str, object]]]:
        assert db is connection and current == run
        return [(reference, {"summary": "Retained worker result"})]

    async def execute(
        self: AsyncConnection, statement: TextClause, parameters: dict[str, object]
    ) -> CursorResult[tuple[object, ...]]:
        assert self is connection and "consumed_decision_id IS NULL" in str(statement)
        updates.append(parameters)
        result: CursorResult[tuple[object, ...]] = object.__new__(CursorResult)
        result.rowcount = 1
        return result

    monkeypatch.setattr(store, "inbox", inbox)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    supplied = [reference]
    if mode == "foreign":
        supplied = [reference.model_copy(update={"id": str(uuid4())})]
    elif mode == "duplicate":
        supplied = [reference, reference]
    elif mode == "missing":
        supplied = []
    if mode == "exact":
        await store.consume(connection, run, supplied, decision)
        assert updates == [
            {
                "instance": run.instance_id,
                "run": run.run_id,
                "id": reference.id,
                "decision": decision.id,
            }
        ]
    else:
        with pytest.raises(ModelConflict, match="CONSUMPTION_DENIED"):
            await store.consume(connection, run, supplied, decision)
        assert updates == []


@pytest.mark.asyncio
async def test_settings_drain_is_not_permanent_owner_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = object.__new__(AgentRunOwner)
    settings = object.__new__(ProviderSettingsOwner)
    settings.lock = asyncio.Lock()
    owner.settings, owner.closing, owner.draining = settings, False, False
    owner.drain_lock = asyncio.Lock()

    async def bounded(self: AgentRunOwner) -> bool:
        assert self.draining
        return True

    monkeypatch.setattr(AgentRunOwner, "_drain_models", bounded)
    assert await owner.drain_models()
    assert not owner.closing and not owner.draining
    assert await owner.drain()
    assert (owner.closing, owner.draining) == (True, False)


@pytest.mark.asyncio
async def test_admitted_wake_waits_for_the_existing_owner_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = object.__new__(AgentRunOwner)
    owner.tasks, owner.closing, owner.failed = {}, False, False
    owner.continuations = set()
    entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = 0
    active = 0
    peak = 0

    async def work(self: AgentRunOwner, identity: str) -> None:
        nonlocal calls, active, peak
        calls += 1
        active += 1
        peak = max(peak, active)
        entered.set()
        await release.wait()
        active -= 1
        if calls == 2:
            completed.set()

    monkeypatch.setattr(AgentRunOwner, "work", work)
    owner.spawn("owned-run")
    try:
        await asyncio.wait_for(entered.wait(), 1)
        owner.spawn("owned-run")
        assert calls == 1
        release.set()
        await asyncio.wait_for(completed.wait(), 1)
        assert calls == 2 and peak == 1
    finally:
        release.set()
        if owner.tasks:
            await asyncio.wait_for(asyncio.gather(*tuple(owner.tasks.values())), 1)


@pytest.mark.parametrize("state", ["PAUSED", "HOLD", "STOPPING", "STOPPED", "NEEDS_RECONCILIATION"])
def test_owner_does_not_admit_effects_from_control_states(state: str) -> None:
    run = fixture_run()
    owner = object.__new__(AgentRunOwner)
    settings = object.__new__(ProviderSettingsOwner)
    settings.owner, settings.epoch = UUID(run.owner_id), run.owner_epoch
    owner.settings, owner.closing, owner.draining = settings, False, False
    owner.require_owned(run)
    with pytest.raises(ModelConflict, match="AUTHORITY_DENIED"):
        owner.require_owned(run.model_copy(update={"state": state}))
    with pytest.raises(ModelConflict, match="AUTHORITY_DENIED"):
        owner.require_owned(run.model_copy(update={"owner_epoch": run.owner_epoch + 1}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor", ["foreign:1", "self:01", "self:-1", "self:1.0", "self:9223372036854775808"]
)
async def test_event_cursor_rejected_before_database(cursor: str) -> None:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from omnis.modules.runs.projections import events

    identity = str(uuid4())
    with pytest.raises(ModelConflict, match="CURSOR_DENIED"):
        await events(object.__new__(AsyncEngine), identity, cursor.replace("self", identity), 20)


def test_worker_cannot_repeat_consumed_ref_to_claim_completion() -> None:
    from omnis.modules.runs.run_contract import WorkerFinal

    ref = fixture_run().setup_ref
    with pytest.raises(ValueError):
        WorkerFinal(summary="Claimed twice", consumed_refs=[ref, ref], gaps=[])


def fixture_setup_payload() -> dict[str, object]:
    from test_engagements import draft

    run = fixture_run()
    ref = run.setup_ref.model_dump()
    choice = {
        "connection_id": str(uuid4()),
        "connection_revision": 1,
        "model": "fixture/recon",
        "output_tokens": 1024,
    }
    selection = {
        "selection_id": str(uuid4()),
        "revision": 7,
        "schema_version": 2,
        "default": choice,
        "brain": None,
        "recon": choice,
        "investigator": {**choice, "model": "retained-not-enabled"},
        "validator": None,
    }
    config = {
        "choice": choice,
        "connection": {
            "connection_id": choice["connection_id"],
            "provider": "openrouter",
            "revision": 1,
            "enabled": True,
            "secret_id": str(uuid4()),
            "credential_revision": 1,
        },
        "capabilities_ref": ref,
    }
    value = {
        "engagement_id": run.engagement_id,
        "draft_ref": {
            "kind": "engagement-revision",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "a" * 64,
        },
        "draft": draft(),
        "expected_generation": 0,
        "selection_revision": 7,
        "selection_snapshot": selection,
        "catalog_owner_id": str(uuid4()),
        "publication_ref": {
            "kind": "catalog-publication",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "b" * 64,
        },
        "context_ref": ref,
        "brain": config,
        "recon": config,
        "brain_instructions": "Inert",
        "recon_instructions": "Inert",
        "composition_refs": [ref, ref],
    }
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,kinds",
    [("BRAIN", ()), ("BRAIN", ("run-result-v1", "run-answer-v1")), ("RECON", ())],
)
async def test_new_attempt_brain_completion_contract_matches_exact_inputs(
    monkeypatch: pytest.MonkeyPatch, role: str, kinds: tuple[str, ...]
) -> None:
    from unittest.mock import AsyncMock

    from omnis.modules.runs import model_test_store as records
    from omnis.modules.runs.run_contract import Attempt, Setup

    run = fixture_run()
    context = run.setup_ref.model_copy(update={"kind": "run-context-v1"})
    snapshot = Setup.model_validate(fixture_setup_payload()).model_copy(
        update={"context_ref": context}
    )
    refs = [
        Ref(instance_id=run.instance_id, id=str(uuid4()), kind=kind, digest="b" * 64)
        for kind in kinds
    ]
    pending = [(ref, {"summary": "Retained inert result"}) for ref in refs]
    inbox = AsyncMock(return_value=pending)
    saved: list[Attempt] = []
    db = object.__new__(AsyncConnection)
    owner = object.__new__(AgentRunOwner)
    owner.instance = run.instance_id

    async def save(connection: AsyncConnection, value: Attempt, *, initial: bool = False) -> None:
        assert connection is db and initial
        saved.append(value)

    monkeypatch.setattr(store, "inbox", inbox)
    monkeypatch.setattr(store, "save_attempt", save)
    monkeypatch.setattr(records, "resolve", AsyncMock(return_value={"skill_refs": []}))
    updated = await owner.new_attempt(
        db, run, snapshot, role=role, brief="Inert selected context", parent=None
    )
    assert len(saved) == 1 and updated.active_attempt_id == saved[0].attempt_id
    attempt = saved[0]
    expected: dict[str, object] = {
        "brief": "Inert selected context",
        "context_ref": context.model_dump(mode="json"),
        "inbox": [
            {"ref": ref.model_dump(mode="json"), "result": payload} for ref, payload in pending
        ],
    }
    if role == "BRAIN":
        inbox.assert_awaited_once_with(db, run)
        assert attempt.input_refs == refs and context not in attempt.input_refs
        expected["completion_contract"] = {
            "consumed_refs": [ref.model_dump(mode="json") for ref in refs],
            "rule": (
                "Copy exactly this consumed_refs list into the decision, each ref once and unchanged. "
                "An empty list means []. context_ref is read context, not a consumed result; "
                "do not add it or invent refs."
            ),
        }
    else:
        inbox.assert_not_awaited()
        assert attempt.input_refs == [context]
    assert attempt.input_text == json.dumps(expected, ensure_ascii=False, separators=(",", ":"))


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["RESULT_READY", "idle", "active"])
async def test_brain_activation_checkpoint_commits_before_sdk(
    monkeypatch: pytest.MonkeyPatch, start: str
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from sqlalchemy.ext.asyncio import AsyncEngine

    from omnis.modules.instance.domain import InstanceStatus
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs import model_test_store as records
    from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
    from omnis.modules.runs.run_contract import Attempt, Setup
    from omnis.modules.settings.provider_vault import ProviderVault
    from omnis.supervisor.agent_runner import AgentStep, StepInput
    from omnis.supervisor.model_relay_protocol import Scope

    run = fixture_run().model_copy(
        update={
            "revision": 7,
            "through_cursor": 5,
            "reason": "RESULT_READY" if start != "idle" else None,
        }
    )
    snapshot = Setup.model_validate(fixture_setup_payload())
    owner = object.__new__(AgentRunOwner)
    owner.instance, owner.closing, owner.draining = run.instance_id, False, False
    owner.settings = object.__new__(ProviderSettingsOwner)
    owner.settings.owner, owner.settings.epoch = UUID(run.owner_id), run.owner_epoch
    owner.settings.lock = asyncio.Lock()
    owner.settings.vault = object.__new__(ProviderVault)
    owner.service = InstanceService(object.__new__(AsyncEngine))
    owner.model_owner = object.__new__(ApiKeyModelTest)
    owner.runner = object.__new__(AgentStep)
    db = object.__new__(AsyncConnection)
    actors: dict[str, Attempt] = {}
    commits: list[RunView] = []
    result_ref = run.setup_ref.model_copy(update={"kind": "run-result-v1"})

    async def save_attempt(db: AsyncConnection, value: Attempt, *, initial: bool = False) -> None:
        assert initial
        actors[value.attempt_id] = value

    async def save_run(db: AsyncConnection, value: RunView, *, initial: bool = False) -> None:
        nonlocal run
        run = value

    async def relay_scope(
        db: AsyncConnection, fields: dict[str, object], *, allocate: bool = False
    ) -> Scope:
        assert allocate
        return Scope.parse({**fields, "operation_serial": 1})

    @asynccontextmanager
    async def admission(*args: object) -> AsyncIterator[AsyncConnection]:
        yield db
        commits.append(run)

    class BeforeSDK(BaseException):
        pass

    async def before_sdk(*args: object, **kwargs: object) -> None:
        assert commits and commits[-1] == run
        step = args[0]
        assert isinstance(step, StepInput) and run.active_attempt_id is not None
        assert step.input_text == actors[run.active_attempt_id].input_text
        assert json.loads(step.input_text)["completion_contract"]["consumed_refs"] == [
            result_ref.model_dump(mode="json")
        ]
        raise BeforeSDK

    event = AsyncMock(return_value=6)
    reserve = AsyncMock()
    sdk = AsyncMock(side_effect=before_sdk)
    monkeypatch.setattr(ProviderVault, "get", lambda *args: "synthetic-unused-key")
    monkeypatch.setattr(InstanceService, "admission", admission)
    monkeypatch.setattr(
        InstanceService,
        "owned_status",
        AsyncMock(
            return_value=InstanceStatus(UUID(run.instance_id), 0, True, None, None, 1, True, False)
        ),
    )
    monkeypatch.setattr(AsyncConnection, "execute", reserve)
    monkeypatch.setattr(store, "run", AsyncMock(side_effect=lambda *args: run))
    monkeypatch.setattr(store, "save_run", save_run)
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(store, "save_attempt", save_attempt)
    monkeypatch.setattr(
        store, "attempt", AsyncMock(side_effect=lambda db, run, identity: actors[identity])
    )
    monkeypatch.setattr(
        store, "inbox", AsyncMock(return_value=[(result_ref, {"summary": "Inert"})])
    )
    monkeypatch.setattr(store, "event", event)
    monkeypatch.setattr(store, "dispatch_event", AsyncMock())
    monkeypatch.setattr(records, "resolve", AsyncMock(return_value={"skill_refs": []}))
    monkeypatch.setattr(records, "put", AsyncMock(return_value=run.setup_ref))
    monkeypatch.setattr(records, "relay_scope", relay_scope)
    monkeypatch.setattr(AgentRunOwner, "data_connections", AsyncMock(return_value=()))
    monkeypatch.setattr(ApiKeyModelTest, "retire_relay", AsyncMock())
    monkeypatch.setattr(AgentStep, "run", sdk)
    if start == "active":
        run = await owner.new_attempt(
            db, run, snapshot, role="BRAIN", brief="Already active", parent=None
        )
    before = run
    if start == "idle":
        await owner.work(run.run_id)
        assert not actors and not reserve.called and not sdk.called
    else:
        with pytest.raises(BeforeSDK):
            await owner.work(run.run_id)
        assert len(actors) == 1 and reserve.await_count == sdk.await_count == 1
        assert "INSERT INTO run_dispatch" in str(reserve.call_args.args[0])
    if start == "RESULT_READY":
        assert (run.revision, run.through_cursor, run.reason) == (8, 6, None)
        assert run.active_attempt_id is not None
        brain = actors[run.active_attempt_id]
        assert brain.role == "BRAIN" and brain.input_refs == [result_ref]
        event.assert_awaited_once_with(
            db,
            run.model_copy(update={"revision": 7, "through_cursor": 5, "reason": "RESULT_READY"}),
            "control",
            "Brain activated from retained results",
            actor=brain,
            refs=[result_ref],
        )
    else:
        assert run == before and not event.called
    assert commits == [run]


def test_setup_retains_exact_complete_selection_without_enabling_other_roles() -> None:
    from omnis.modules.runs.run_contract import Setup

    value = fixture_setup_payload()
    retained = Setup.model_validate(value)
    assert retained.model_dump(mode="json")["selection_snapshot"] == value["selection_snapshot"]
    assert "investigator" not in Setup.model_fields and "validator" not in Setup.model_fields
    with pytest.raises(ValueError):
        Setup.model_validate({**value, "selection_revision": 8})


def test_command_and_envelope_exact_3600_byte_boundaries() -> None:
    run = fixture_run()
    command = RunCommand(
        action="answer",
        command_id=str(uuid4()),
        run_id=run.run_id,
        question_id=str(uuid4()),
        expected_generation=0,
        expected_revision=1,
        answer="x",
    )
    for envelope in (False, True):
        empty = command.model_copy(update={"answer": ""})
        base = len(
            (
                RunControl.model_construct(op="agent_run", request=empty).model_dump_json()
                if envelope
                else empty.model_dump_json()
            ).encode()
        )
        remaining = 3600 - base
        value = command.model_copy(
            update={"answer": "\t" * (remaining // 2) + "x" * (remaining % 2)}
        )
        dto = (
            RunControl(op="agent_run", request=value)
            if envelope
            else RunCommand.model_validate(value.model_dump())
        )
        assert len(dto.model_dump_json().encode()) == 3600
        over = value.model_copy(update={"answer": (value.answer or "") + "x"})
        with pytest.raises(ValueError):
            if envelope:
                RunControl(op="agent_run", request=over)
            else:
                RunCommand.model_validate(over.model_dump())
