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
    CommandReceipt,
    Question,
    RunEvent,
    RunView,
    Setup,
)

TERMINAL = ("STOPPED", "COMPLETED", "LIMITED")


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
    return Attempt.model_validate_json(json.dumps(raw))


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
