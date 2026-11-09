"""S1 transactions use the existing owner connection; readers never schedule work."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import model_test_store as records
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.run_contract import (
    Attempt,
    AttemptInspection,
    BrainDecision,
    CommandReceipt,
    DecisionRecord,
    InboxConsumption,
    Question,
    ResultRecord,
    RunEvent,
    RunView,
    Setup,
    UsageObservation,
    UsageRecord,
)
from omnis.modules.settings.provider_key_models import ModelSelection

TERMINAL = ("STOPPED", "COMPLETED", "LIMITED")


async def record_usage(
    db: AsyncConnection,
    run: RunView,
    actor: Attempt,
    dispatch: str,
    choice: ModelSelection,
    observation: UsageObservation,
) -> Ref:
    if (actor.instance_id, actor.run_id, actor.configured_model) != (
        run.instance_id,
        run.run_id,
        choice.model,
    ):
        raise records.ModelConflict("REF_UNAVAILABLE")
    raw: object = await db.scalar(
        text(
            "SELECT payload FROM run_dispatch WHERE instance_id=:instance AND run_id=:run "
            "AND task_id=:task AND attempt_id=:attempt AND dispatch_id=:id FOR UPDATE"
        ),
        {
            "instance": run.instance_id,
            "run": run.run_id,
            "task": actor.task_id,
            "attempt": actor.attempt_id,
            "id": dispatch,
        },
    )
    if not isinstance(raw, dict) or raw.get("setup_ref") != run.setup_ref.model_dump(mode="json"):
        raise records.ModelConflict("REF_UNAVAILABLE")
    value = UsageRecord(
        **observation.model_dump(),
        instance_id=run.instance_id,
        run_id=run.run_id,
        task_id=actor.task_id,
        attempt_id=actor.attempt_id,
        dispatch_id=dispatch,
        role=actor.role,
        configured_model=choice.model,
        connection_id=choice.connection_id,
        connection_revision=choice.connection_revision,
        observed_at=datetime.now(UTC),
    )
    if raw.get("usage_ref") is not None:
        reference = Ref.model_validate(raw["usage_ref"])
        if reference.revision != 1:
            raise records.ModelConflict("REF_UNAVAILABLE")
        prior = UsageRecord.model_validate_json(
            json.dumps(await records.resolve(db, run.instance_id, reference, "run-usage-v2"))
        )
        if prior.model_dump(exclude={"observed_at"}) != value.model_dump(exclude={"observed_at"}):
            raise records.ModelConflict("USAGE_CONFLICT")
        return reference
    reference = await records.put(
        db, run.instance_id, "run-usage-v2", value.model_dump(mode="json")
    )
    await db.execute(
        text(
            "UPDATE run_dispatch SET payload=CAST(:payload AS jsonb) WHERE instance_id=:instance "
            "AND dispatch_id=:id"
        ),
        {
            "instance": run.instance_id,
            "id": dispatch,
            "payload": json.dumps({**raw, "usage_ref": reference.model_dump(mode="json")}),
        },
    )
    return reference


async def dispatch_event(db: AsyncConnection, instance: str, identity: str, state: str) -> None:
    await db.execute(
        text(
            "INSERT INTO run_dispatch_event(instance_id,dispatch_id,sequence,state) SELECT :instance,:id,COALESCE(max(sequence),0)+1,:state FROM run_dispatch_event WHERE instance_id=:instance AND dispatch_id=:id"
        ),
        {"instance": instance, "id": identity, "state": state},
    )


async def run(db: AsyncConnection, instance: str, identity: str) -> RunView:
    raw: object = await db.scalar(
        text("SELECT payload FROM agent_run WHERE instance_id=:instance AND run_id=:id FOR UPDATE"),
        {"instance": instance, "id": identity},
    )
    if raw is None:
        raise records.ModelConflict("NOT_FOUND")
    return RunView.model_validate_json(json.dumps(raw))


async def save_run(db: AsyncConnection, value: RunView, *, initial: bool = False) -> None:
    params = {
        **value.model_dump(),
        "setup_id": value.setup_ref.id,
        "payload": value.model_dump_json(),
    }
    if initial:
        await db.execute(
            text(
                "INSERT INTO agent_run(instance_id,run_id,engagement_id,setup_id,revision,generation,owner_id,owner_epoch,fence,state,payload) VALUES (:instance_id,:run_id,:engagement_id,:setup_id,:revision,:generation,:owner_id,:owner_epoch,:fence,:state,CAST(:payload AS jsonb))"
            ),
            params,
        )
    else:
        await db.execute(
            text(
                "UPDATE agent_run SET revision=:revision,fence=:fence,state=:state,payload=CAST(:payload AS jsonb) WHERE instance_id=:instance_id AND run_id=:run_id"
            ),
            params,
        )


async def setup(db: AsyncConnection, instance: str, reference: Ref) -> Setup:
    if not await db.scalar(
        text("SELECT 1 FROM run_setup WHERE instance_id=:instance AND setup_id=:id"),
        {"instance": instance, "id": reference.id},
    ):
        raise records.ModelConflict("REF_UNAVAILABLE")
    return Setup.model_validate_json(
        json.dumps(await records.resolve(db, instance, reference, "run-setup-v1"))
    )


async def attempt(db: AsyncConnection, value: RunView, identity: str) -> Attempt:
    raw: object = await db.scalar(
        text(
            "SELECT payload FROM run_attempt WHERE instance_id=:instance AND run_id=:run AND attempt_id=:id"
        ),
        {"instance": value.instance_id, "run": value.run_id, "id": identity},
    )
    if raw is None:
        raise records.ModelConflict("NOT_FOUND")
    item = Attempt.model_validate_json(json.dumps(raw))
    if (item.instance_id, item.run_id, item.attempt_id) != (
        value.instance_id,
        value.run_id,
        identity,
    ):
        raise records.ModelConflict("REF_UNAVAILABLE")
    return item


async def decision_read(
    db: AsyncConnection, actor: Attempt, reference: Ref
) -> tuple[BrainDecision, str | None]:
    if actor.role != "BRAIN" or actor.state != "SUCCEEDED" or reference.revision != 1:
        raise records.ModelConflict("REF_UNAVAILABLE")
    if reference.kind == "run-decision-v2":
        raw = await records.resolve(db, actor.instance_id, reference, "run-decision-v2")
        value = DecisionRecord.model_validate(raw)
        if (value.run_id, value.task_id, value.attempt_id) != (
            actor.run_id,
            actor.task_id,
            actor.attempt_id,
        ):
            raise records.ModelConflict("REF_UNAVAILABLE")
        decision, completion = value.decision, value.completion_kind
    elif reference.kind == "run-decision-v1":
        decision = BrainDecision.model_validate(
            await records.resolve(db, actor.instance_id, reference, "run-decision-v1")
        )
        # Historical decisions have no embedded lineage; their immutable event binds it.
        if not await db.scalar(
            text(
                "SELECT 1 FROM run_event WHERE instance_id=:instance AND run_id=:run "
                "AND payload->>'task_id'=:task AND payload->>'attempt_id'=:attempt "
                "AND payload->>'kind'='decision' AND payload->'refs' @> CAST(:refs AS jsonb)"
            ),
            {
                "instance": actor.instance_id,
                "run": actor.run_id,
                "task": actor.task_id,
                "attempt": actor.attempt_id,
                "refs": json.dumps([reference.model_dump()]),
            },
        ):
            raise records.ModelConflict("REF_UNAVAILABLE")
        completion = None
    else:
        raise records.ModelConflict("REF_UNAVAILABLE")
    rows = (
        (
            await db.execute(
                text(
                    "SELECT r.instance_id::text,r.id::text,r.kind,r.revision,r.digest FROM run_inbox i "
                    "JOIN model_record_v2 r ON r.instance_id=i.instance_id AND r.id=i.result_id "
                    "WHERE i.instance_id=:instance AND i.run_id=:run AND i.consumed_decision_id=:id "
                    "AND NOT i.held LIMIT 33"
                ),
                {"instance": actor.instance_id, "run": actor.run_id, "id": reference.id},
            )
        )
        .mappings()
        .all()
    )
    consumed = [Ref.model_validate(dict(row)) for row in rows]
    if len(consumed) != len(decision.consumed_refs) or sorted(
        r.model_dump_json() for r in consumed
    ) != sorted(r.model_dump_json() for r in decision.consumed_refs):
        raise records.ModelConflict("REF_UNAVAILABLE")
    return decision, completion


async def inspect_completion(db: AsyncConnection, actor: Attempt) -> AttemptInspection:
    reference = actor.result_ref
    if reference is not None and reference.revision != 1:
        raise records.ModelConflict("REF_UNAVAILABLE")
    result = AttemptInspection(**actor.model_dump(), as_of=datetime.now(UTC))
    if reference is None:
        return result
    if reference.kind in {"run-decision-v1", "run-decision-v2"}:
        decision, completion = await decision_read(db, actor, reference)
        return AttemptInspection.model_validate(
            {**result.model_dump(), "decision": decision, "decision_completion_kind": completion}
        )
    payload = await records.resolve(db, actor.instance_id, reference, "run-result-v1")
    value = ResultRecord.model_validate(payload)
    if (value.run_id, value.task_id, value.attempt_id, value.state) != (
        actor.run_id,
        actor.task_id,
        actor.attempt_id,
        actor.state,
    ):
        raise records.ModelConflict("REF_UNAVAILABLE")
    row = (
        await db.execute(
            text(
                "SELECT held,consumed_decision_id::text FROM run_inbox "
                "WHERE instance_id=:instance AND run_id=:run AND result_id=:id"
            ),
            {"instance": actor.instance_id, "run": actor.run_id, "id": reference.id},
        )
    ).one_or_none()
    if row is None:
        raise records.ModelConflict("REF_UNAVAILABLE")
    consumed_ref, consumer_id = None, None
    if row[1] is not None:
        consumers = (
            (
                await db.execute(
                    text(
                        "SELECT payload FROM run_attempt WHERE instance_id=:instance AND run_id=:run "
                        "AND payload#>>'{result_ref,id}'=:id LIMIT 2"
                    ),
                    {"instance": actor.instance_id, "run": actor.run_id, "id": row[1]},
                )
            )
            .scalars()
            .all()
        )
        if len(consumers) != 1 or row[0]:
            raise records.ModelConflict("REF_UNAVAILABLE")
        consumer = Attempt.model_validate(consumers[0])
        consumed_ref, consumer_id = consumer.result_ref, consumer.attempt_id
        if (
            consumer.instance_id != actor.instance_id
            or consumer.run_id != actor.run_id
            or consumed_ref is None
        ):
            raise records.ModelConflict("REF_UNAVAILABLE")
        decision, _ = await decision_read(db, consumer, consumed_ref)
        if reference not in decision.consumed_refs:
            raise records.ModelConflict("REF_UNAVAILABLE")
    return result.model_copy(
        update={
            "result": value,
            "consumption": InboxConsumption(
                held=row[0], decision_ref=consumed_ref, consumer_attempt_id=consumer_id
            ),
        }
    )


async def save_attempt(db: AsyncConnection, value: Attempt, *, initial: bool = False) -> None:
    params = {**value.model_dump(), "payload": value.model_dump_json()}
    if initial:
        await db.execute(
            text(
                "INSERT INTO run_task(instance_id,run_id,task_id,role,parent_task_id) VALUES (:instance_id,:run_id,:task_id,:role,:parent_task_id)"
            ),
            params,
        )
        await db.execute(
            text(
                "INSERT INTO run_attempt(instance_id,run_id,task_id,attempt_id,role,state,payload) VALUES (:instance_id,:run_id,:task_id,:attempt_id,:role,:state,CAST(:payload AS jsonb))"
            ),
            params,
        )
    else:
        await db.execute(
            text(
                "UPDATE run_attempt SET state=:state,payload=CAST(:payload AS jsonb) WHERE instance_id=:instance_id AND run_id=:run_id AND attempt_id=:attempt_id"
            ),
            params,
        )


async def event(
    db: AsyncConnection,
    value: RunView,
    kind: str,
    summary: str,
    *,
    actor: Attempt | None = None,
    refs: list[Ref] | None = None,
    call_id: str | None = None,
) -> int:
    await db.execute(
        text(
            "INSERT INTO run_event_counter(engagement_id,sequence) VALUES (:id,0) ON CONFLICT DO NOTHING"
        ),
        {"id": value.engagement_id},
    )
    seq = await db.scalar(
        text(
            "UPDATE run_event_counter SET sequence=sequence+1 WHERE engagement_id=:id RETURNING sequence"
        ),
        {"id": value.engagement_id},
    )
    entry = RunEvent.model_validate(
        {
            "event_id": str(uuid4()),
            "run_id": value.run_id,
            "task_id": actor.task_id if actor else None,
            "attempt_id": actor.attempt_id if actor else None,
            "sequence": seq,
            "kind": kind,
            "summary": summary,
            "refs": refs or [],
            "call_id": call_id,
            "created_at": datetime.now(UTC),
        }
    )
    if len(entry.model_dump_json().encode()) > 16384:
        raise records.ModelConflict("EVENT_LIMIT")
    await db.execute(
        text(
            "INSERT INTO run_event(instance_id,run_id,engagement_id,sequence,event_id,payload) VALUES (:instance,:run,:engagement,:seq,:id,CAST(:payload AS jsonb))"
        ),
        {
            "instance": value.instance_id,
            "run": value.run_id,
            "engagement": value.engagement_id,
            "seq": seq,
            "id": entry.event_id,
            "payload": entry.model_dump_json(),
        },
    )
    return entry.sequence


async def inbox(db: AsyncConnection, value: RunView) -> list[tuple[Ref, dict[str, object]]]:
    rows = (
        (
            await db.execute(
                text(
                    "SELECT r.id::text,r.kind,r.digest,r.payload FROM run_inbox i JOIN model_record_v2 r ON r.instance_id=i.instance_id AND r.id=i.result_id WHERE i.instance_id=:instance AND i.run_id=:run AND i.consumed_decision_id IS NULL AND NOT i.held ORDER BY r.created_at,r.id LIMIT 33"
                ),
                {"instance": value.instance_id, "run": value.run_id},
            )
        )
        .mappings()
        .all()
    )
    if len(rows) > 32:
        raise records.ModelConflict("INBOX_LIMIT")
    result = []
    for row in rows:
        reference = Ref(
            instance_id=value.instance_id, kind=row["kind"], id=row["id"], digest=row["digest"]
        )
        result.append(
            (reference, await records.resolve(db, value.instance_id, reference, reference.kind))
        )
    return result


async def add_inbox(db: AsyncConnection, value: RunView, reference: Ref) -> None:
    await db.execute(
        text(
            "INSERT INTO run_inbox(instance_id,run_id,result_id,held) VALUES (:instance,:run,:id,:held)"
        ),
        {
            "instance": value.instance_id,
            "run": value.run_id,
            "id": reference.id,
            "held": value.state != "RUNNING",
        },
    )


async def inert_progress(
    db: AsyncConnection, value: RunView, snapshot: Setup, references: list[Ref]
) -> bool:
    # shortcut: S1 has only frozen reads and operator answers; extend with the next real producer.
    progress = False
    for reference in references:
        if reference.revision != 1:
            raise records.ModelConflict("REF_UNAVAILABLE")
        payload = await records.resolve(db, value.instance_id, reference, reference.kind)
        answer_text = None
        if reference.kind == "run-result-v1":
            result = ResultRecord.model_validate(payload)
            actor = await attempt(db, value, result.attempt_id)
            if (result.run_id, result.task_id, result.state) != (
                value.run_id,
                actor.task_id,
                actor.state,
            ) or actor.result_ref != reference:
                raise records.ModelConflict("REF_UNAVAILABLE")
            if result.state != "SUCCEEDED":
                continue
            read_ref = actor.read_receipt_ref
            if (
                actor.role != "RECON"
                or read_ref is None
                or read_ref.revision != 1
                or read_ref not in result.consumed_refs
                or any(ref not in (read_ref, snapshot.context_ref) for ref in result.consumed_refs)
                or len({ref.model_dump_json() for ref in result.consumed_refs})
                != len(result.consumed_refs)
                or result.gaps
                or actor.input_refs != [snapshot.context_ref]
                or actor.call_id is None
            ):
                raise records.ModelConflict("REF_UNAVAILABLE")
            receipt = await records.resolve(db, value.instance_id, read_ref, "run-tool-result-v1")
            context = await records.resolve(
                db, value.instance_id, snapshot.context_ref, "run-context-v1"
            )
            if receipt != {
                "run_id": value.run_id,
                "task_id": actor.task_id,
                "attempt_id": actor.attempt_id,
                "call_id": actor.call_id,
                "context_ref": snapshot.context_ref.model_dump(mode="json"),
                "context": context,
            }:
                raise records.ModelConflict("REF_UNAVAILABLE")
        elif reference.kind == "run-answer-v1":
            admitted = await question(db, value)
            answer_text = payload.get("text")
            if (
                admitted is None
                or admitted.run_id != value.run_id
                or admitted.question_id != value.question_id
                or admitted.state != "ANSWER_ADMITTED"
                or admitted.answer_ref != reference
                or admitted.command_id is None
                or not isinstance(answer_text, str)
                or not answer_text.strip()
                or payload
                != {
                    "question_id": admitted.question_id,
                    "text": answer_text,
                    "scope_change": False,
                }
                or payload.get("scope_change") is not False
            ):
                raise records.ModelConflict("REF_UNAVAILABLE")
        else:
            raise records.ModelConflict("REF_UNAVAILABLE")
        # Search the whole run's consumed set, not the bounded pending inbox or a recent page.
        seen = await db.scalar(
            text(
                "SELECT 1 FROM run_inbox i JOIN model_record_v2 r "
                "ON r.instance_id=i.instance_id AND r.id=i.result_id "
                "WHERE i.instance_id=:instance AND i.run_id=:run "
                "AND i.consumed_decision_id IS NOT NULL AND NOT i.held AND r.kind=:kind "
                "AND ((:kind='run-result-v1' AND r.payload->>'state'='SUCCEEDED') "
                "OR (:kind='run-answer-v1' AND r.payload->>'text'=:answer)) LIMIT 1"
            ),
            {
                "instance": value.instance_id,
                "run": value.run_id,
                "kind": reference.kind,
                "answer": answer_text,
            },
        )
        progress = progress or seen is None
    return progress


async def consume(
    db: AsyncConnection, value: RunView, references: list[Ref], decision: Ref
) -> None:
    pending = await inbox(db, value)
    expected = [ref for ref, _ in pending]
    if len(references) != len(expected) or set(ref.model_dump_json() for ref in references) != set(
        ref.model_dump_json() for ref in expected
    ):
        raise records.ModelConflict("CONSUMPTION_DENIED")
    for reference in references:
        result = await db.execute(
            text(
                "UPDATE run_inbox SET consumed_decision_id=:decision WHERE instance_id=:instance AND run_id=:run AND result_id=:id AND consumed_decision_id IS NULL AND NOT held"
            ),
            {
                "instance": value.instance_id,
                "run": value.run_id,
                "id": reference.id,
                "decision": decision.id,
            },
        )
        if result.rowcount != 1:
            raise records.ModelConflict("CONSUMPTION_DENIED")


async def question(db: AsyncConnection, value: RunView) -> Question | None:
    if value.question_id is None:
        return None
    raw = await db.scalar(
        text(
            "SELECT payload FROM run_question WHERE instance_id=:instance AND run_id=:run AND question_id=:id"
        ),
        {"instance": value.instance_id, "run": value.run_id, "id": value.question_id},
    )
    if raw is None:
        raise records.ModelConflict("REF_UNAVAILABLE")
    return Question.model_validate_json(json.dumps(raw))


async def save_question(
    db: AsyncConnection, value: RunView, item: Question, *, initial: bool = False
) -> None:
    params = {**item.model_dump(), "instance": value.instance_id, "payload": item.model_dump_json()}
    if initial:
        await db.execute(
            text(
                "INSERT INTO run_question(instance_id,run_id,task_id,question_id,state,payload) VALUES (:instance,:run_id,:task_id,:question_id,:state,CAST(:payload AS jsonb))"
            ),
            params,
        )
    else:
        await db.execute(
            text(
                "UPDATE run_question SET state=:state,payload=CAST(:payload AS jsonb) WHERE instance_id=:instance AND run_id=:run_id AND question_id=:question_id"
            ),
            params,
        )


async def replay(
    db: AsyncConnection, instance: str, command: str, payload: object | None = None
) -> CommandReceipt | None:
    row = (
        await db.execute(
            text(
                "SELECT request_digest,payload FROM run_command WHERE instance_id=:instance AND command_id=:id"
            ),
            {"instance": instance, "id": command},
        )
    ).one_or_none()
    if row is None:
        return None
    if payload is not None and records.digest(payload) != row[0]:
        raise records.ModelConflict("COMMAND_CONFLICT")
    return CommandReceipt.model_validate_json(json.dumps(row[1]))


async def receipt(
    db: AsyncConnection, instance: str, request: object, result: CommandReceipt
) -> None:
    await db.execute(
        text(
            "INSERT INTO run_command(instance_id,command_id,request_digest,payload) VALUES (:instance,:id,:digest,CAST(:payload AS jsonb))"
        ),
        {
            "instance": instance,
            "id": result.command_id,
            "digest": records.digest(request),
            "payload": result.model_dump_json(),
        },
    )
