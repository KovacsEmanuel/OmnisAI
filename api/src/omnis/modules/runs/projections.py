"""Receive-only coherent projections; no owner, callback or SDK is invoked."""

import json
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.run_contract import Attempt, EventPage, RunEvent, RunSummary, RunView


async def read_run(db: AsyncConnection, identity: str) -> RunView:
    payload: object = await db.scalar(
        text(
            "SELECT payload FROM agent_run WHERE run_id=:id AND instance_id=(SELECT instance_id FROM instance_control WHERE id=1)"
        ),
        {"id": identity},
    )
    if payload is None:
        raise records.ModelConflict("NOT_FOUND")
    return RunView.model_validate_json(json.dumps(payload))


async def summary(engine: AsyncEngine, identity: str, limit: int = 20) -> RunSummary:
    async with engine.connect() as connection:
        db = await connection.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        async with db.begin():
            run = await read_run(db, identity)
            question = await store.question(db, run)
            owner_live = bool(
                await db.scalar(
                    text(
                        "SELECT 1 FROM supervisor_lease l JOIN instance_control i ON i.id=l.id WHERE l.owner=:owner AND l.epoch=:epoch AND l.expires_at>clock_timestamp() AND i.generation=:generation AND i.admission_open"
                    ),
                    {"owner": run.owner_id, "epoch": run.owner_epoch, "generation": run.generation},
                )
            )
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT payload FROM run_attempt WHERE instance_id=:instance AND run_id=:run ORDER BY attempt_id LIMIT :limit"
                        ),
                        {"instance": run.instance_id, "run": identity, "limit": limit + 1},
                    )
                )
                .scalars()
                .all()
            )
            result = RunSummary(
                run=run,
                owner_live=owner_live,
                phase_active=owner_live
                and run.state == "RUNNING"
                and run.active_attempt_id is not None,
                question=question,
                attempts=[],
                has_more=len(rows) > limit,
                as_of=datetime.now(UTC),
            )
            for row in rows[:limit]:
                item = Attempt.model_validate_json(json.dumps(row))
                proposed = result.model_copy(update={"attempts": [*result.attempts, item]})
                if len(proposed.model_dump_json().encode()) > 65536:
                    result = result.model_copy(update={"has_more": True})
                    break
                result = proposed
            return result


async def events(engine: AsyncEngine, identity: str, after: str | None, limit: int) -> EventPage:
    cursor = 0
    if after is not None:
        prefix, separator, number = after.partition(":")
        if (
            prefix != identity
            or separator != ":"
            or not number.isascii()
            or not number.isdecimal()
            or len(number) > 19
            or int(number) > 9223372036854775807
            or str(int(number)) != number
        ):
            raise records.ModelConflict("CURSOR_DENIED")
        cursor = int(number)
    async with engine.connect() as connection:
        db = await connection.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        async with db.begin():
            run = await read_run(db, identity)
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT payload FROM run_event WHERE instance_id=:instance AND run_id=:run AND sequence>:after ORDER BY sequence LIMIT :limit"
                        ),
                        {
                            "instance": run.instance_id,
                            "run": identity,
                            "after": cursor,
                            "limit": limit + 1,
                        },
                    )
                )
                .scalars()
                .all()
            )
            result = EventPage(
                run_id=identity,
                through_cursor=cursor,
                events=[],
                has_more=len(rows) > limit,
                as_of=datetime.now(UTC),
            )
            for row in rows[:limit]:
                item = RunEvent.model_validate_json(json.dumps(row))
                proposed = result.model_copy(
                    update={"events": [*result.events, item], "through_cursor": item.sequence}
                )
                if len(proposed.model_dump_json().encode()) > 65536:
                    result = result.model_copy(update={"has_more": True})
                    break
                result = proposed
            return result
