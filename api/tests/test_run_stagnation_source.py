"""Complete/finish consumers with synthetic storage; no PG or provider proof."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.run_contract import Attempt, BrainDecision, Question, Setup, WorkerFinal
from omnis.supervisor.model_relay_protocol import Scope
from test_run_controls_source import Owned
from test_run_controls_source import owned as owned
from test_run_owner_source import fixture_setup_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["delegate", "ask"])
@pytest.mark.parametrize("proof", ["valid", "missing", "foreign", "corrupt", "context"])
async def test_equivalent_inert_results_stop_before_successor(
    owned: Owned, monkeypatch: pytest.MonkeyPatch, action: str, proof: str
) -> None:
    db = object.__new__(AsyncConnection)
    context = {"text": "Frozen inert input", "data_policy": "SELECTED_SYNTHETIC_ONLY"}
    context_ref = owned.run.setup_ref.model_copy(
        update={"kind": "run-context-v1", "digest": records.digest(context)}
    )
    snapshot = Setup.model_validate(fixture_setup_payload()).model_copy(
        update={"context_ref": context_ref}
    )
    payloads: dict[str, dict[str, object]] = {context_ref.id: dict(context)}
    actors: dict[str, Attempt] = {}
    consumed: list[Ref] = []
    pending: list[Ref] = []
    events: list[str] = []

    async def put(db: AsyncConnection, instance: str, kind: str, payload: dict[str, object]) -> Ref:
        ref = Ref(instance_id=instance, kind=kind, id=str(uuid4()), digest=records.digest(payload))
        payloads[ref.id] = payload
        return ref

    async def resolve(db: AsyncConnection, instance: str, ref: Ref, kind: str) -> dict[str, object]:
        payload = payloads.get(ref.id)
        if (
            ref.instance_id != instance
            or ref.kind != kind
            or ref.revision != 1
            or payload is None
            or ref.digest != records.digest(payload)
        ):
            raise records.ModelConflict("REF_UNAVAILABLE")
        return payload

    async def save(db: AsyncConnection, value: Attempt, *, initial: bool = False) -> None:
        actors[value.attempt_id] = value

    async def attempt(db: AsyncConnection, value: object, identity: str) -> Attempt:
        return actors[identity]

    async def add(db: AsyncConnection, value: object, ref: Ref) -> None:
        pending.append(ref)

    async def consume(db: AsyncConnection, value: object, refs: list[Ref], decision: Ref) -> None:
        assert refs == pending
        consumed.extend(refs)
        pending.clear()

    async def event(*args: object, **kwargs: object) -> int:
        events.append(str(args[3]))
        return len(events)

    history = AsyncMock(side_effect=lambda *args, **kwargs: 1 if consumed else None)
    monkeypatch.setattr(AsyncConnection, "scalar", history)
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(store, "attempt", attempt)
    monkeypatch.setattr(store, "save_attempt", save)
    monkeypatch.setattr(store, "add_inbox", add)
    monkeypatch.setattr(store, "consume", consume)
    monkeypatch.setattr(store, "event", event)
    question_write = AsyncMock()
    monkeypatch.setattr(store, "save_question", question_write)
    monkeypatch.setattr(records, "put", put)
    monkeypatch.setattr(records, "resolve", resolve)

    # The initial Brain is one causal task, not progress or a permanent third agent.
    owned.run = owned.run.model_copy(update={"stagnation": 1})
    for index, expected in enumerate((0, 1, 2, 3)):
        actor = Attempt(
            instance_id=owned.run.instance_id,
            run_id=owned.run.run_id,
            task_id=str(uuid4()),
            attempt_id=str(uuid4()),
            role="RECON",
            parent_task_id=None,
            state="RUNNING",
            brief=f"Reworded equivalent task {index}",
            input_refs=[context_ref],
            input_text="Frozen input",
            instructions=snapshot.recon_instructions,
            configured_model=snapshot.recon.choice.model,
            skill_refs=[],
        )
        actors[actor.attempt_id] = actor
        owned.run = owned.run.model_copy(update={"active_attempt_id": actor.attempt_id})
        scope = Scope(
            owned.run.instance_id,
            "MODEL_DISPATCH",
            str(uuid4()),
            owned.run.owner_id,
            owned.run.generation,
            owned.run.owner_epoch,
            owned.run.fence,
            (datetime.now(UTC) + timedelta(seconds=300)).isoformat(),
            "openrouter",
            1,
        )
        output = await owned.owner.execute_tool(
            owned.run.run_id, scope, actor.attempt_id, snapshot, "read_context", "{}", str(uuid4())
        )
        read = Ref.model_validate(json.loads(output)["ref"])
        final = WorkerFinal(summary=f"Paraphrase {index}", consumed_refs=[read], gaps=[])
        await owned.owner.execute_tool(
            owned.run.run_id,
            scope,
            actor.attempt_id,
            snapshot,
            "finish",
            final.model_dump_json(),
            str(uuid4()),
        )
        if proof == "missing":
            del payloads[read.id]
        elif proof == "corrupt":
            payloads[read.id]["context"] = {"text": "untrusted new words"}
        elif proof in {"foreign", "context"}:
            changed = dict(payloads[read.id])
            changed["run_id" if proof == "foreign" else "context_ref"] = (
                str(uuid4())
                if proof == "foreign"
                else context_ref.model_copy(update={"id": str(uuid4())}).model_dump()
            )
            bad_read = await put(db, owned.run.instance_id, "run-tool-result-v1", changed)
            bad_result = await put(
                db,
                owned.run.instance_id,
                "run-result-v1",
                {
                    **payloads[pending[0].id],
                    "consumed_refs": [bad_read.model_dump()],
                },
            )
            pending[:] = [bad_result]
            actors[actor.attempt_id] = actors[actor.attempt_id].model_copy(
                update={"read_receipt_ref": bad_read, "result_ref": bad_result}
            )
        brain = actor.model_copy(
            update={
                "role": "BRAIN",
                "task_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "input_refs": list(pending),
                "read_receipt_ref": None,
            }
        )
        owned.run = owned.run.model_copy(update={"active_attempt_id": brain.attempt_id})
        writes = owned.writes.count("new_attempt")
        questions = question_write.await_count
        decision = BrainDecision.model_validate(
            {
                "action": action if expected == 3 else "delegate",
                "summary": f"New words {index}",
                "detail": f"Equivalent objective {index}",
                "consumed_refs": pending,
            }
        )
        if proof != "valid":
            before = owned.run
            with pytest.raises(records.ModelConflict, match="REF_UNAVAILABLE"):
                await owned.owner.complete(db, owned.run, brain, decision.model_dump_json(), None)
            assert owned.run == before and not consumed
            assert owned.writes.count("new_attempt") == writes
            return
        await owned.owner.complete(db, owned.run, brain, decision.model_dump_json(), None)
        assert owned.run.stagnation == expected
        if expected == 3:
            assert owned.run.state == "LIMITED" and owned.run.reason == "STAGNATION"
            assert owned.run.active_attempt_id is None
            assert owned.writes.count("new_attempt") == writes
            assert question_write.await_count == questions
            assert "STAGNATION" in events
        else:
            assert owned.run.state == "RUNNING"
    assert len({ref.id for ref in consumed}) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["new", "repeat", "missing", "foreign", "corrupt"])
async def test_operator_information_requires_its_admitted_proof(
    owned: Owned, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    db = object.__new__(AsyncConnection)
    snapshot = Setup.model_validate(fixture_setup_payload())
    question_id = str(uuid4())
    payload: dict[str, object] = {
        "question_id": question_id,
        "text": "The required precondition is now true",
        "scope_change": False,
    }
    ref = Ref(
        instance_id=owned.run.instance_id,
        kind="run-answer-v1",
        id=str(uuid4()),
        digest=records.digest(payload),
    )
    actor = Attempt(
        instance_id=owned.run.instance_id,
        run_id=owned.run.run_id,
        task_id=str(uuid4()),
        attempt_id=str(uuid4()),
        role="BRAIN",
        parent_task_id=None,
        state="RUNNING",
        brief="Clarification",
        input_refs=[ref],
        input_text="Clarification",
        instructions="Inert",
        configured_model="fixture/brain",
        skill_refs=[],
    )
    owned.run = owned.run.model_copy(
        update={
            "stagnation": 2,
            "question_id": question_id,
            "active_attempt_id": actor.attempt_id,
        }
    )
    owned.question = Question(
        question_id=question_id,
        run_id=owned.run.run_id,
        task_id=str(uuid4()),
        revision=1,
        cause="Clarify",
        text="Precondition?",
        refs=[],
        state="ANSWER_ADMITTED",
        answer_ref=ref,
        command_id=str(uuid4()),
    )
    if mode == "missing":
        owned.question = None
    elif mode == "foreign":
        owned.question = owned.question.model_copy(update={"run_id": str(uuid4())})
    if mode == "corrupt":
        payload["scope_change"] = True
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(store, "save_attempt", AsyncMock())
    monkeypatch.setattr(store, "save_question", AsyncMock())
    monkeypatch.setattr(store, "event", AsyncMock(return_value=1))
    monkeypatch.setattr(store, "consume", AsyncMock())
    monkeypatch.setattr(
        records, "put", AsyncMock(return_value=ref.model_copy(update={"kind": "run-decision-v2"}))
    )
    monkeypatch.setattr(records, "resolve", AsyncMock(return_value=payload))
    monkeypatch.setattr(
        AsyncConnection, "scalar", AsyncMock(return_value=1 if mode == "repeat" else None)
    )
    decision = BrainDecision(
        action="delegate", summary="Consume clarification", detail="Inert", consumed_refs=[ref]
    )
    if mode in {"missing", "foreign", "corrupt"}:
        with pytest.raises(records.ModelConflict):
            await owned.owner.complete(db, owned.run, actor, decision.model_dump_json(), None)
        assert "new_attempt" not in owned.writes and owned.run.stagnation == 2
    else:
        await owned.owner.complete(db, owned.run, actor, decision.model_dump_json(), None)
        assert owned.run.stagnation == (0 if mode == "new" else 3)
        assert (owned.run.state == "LIMITED") is (mode == "repeat")
