"""Receive-only coherent projections; no owner, callback or SDK is invoked."""

import json
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.run_contract import (
    AgentEvent,
    AgentHistory,
    AgentPage,
    AgentRow,
    Attempt,
    DispatchUsage,
    EventPage,
    RoleUsage,
    RunEvent,
    RunMetrics,
    RunSummary,
    RunView,
    UsageMeasures,
    UsageRecord,
    UsageSubtotal,
    UsageSummary,
    UsageTotals,
    usage_observation,
)

# One row per owned dispatch, including lost responses. Legacy duplicates never add charge.
_USAGE_SOURCE = """
WITH owned AS (
 SELECT d.*, a.role, a.payload AS actor,
        CASE WHEN a.role='BRAIN' THEN CAST(:brain AS jsonb) ELSE CAST(:recon AS jsonb) END AS choice
 FROM run_dispatch d JOIN run_attempt a ON a.instance_id=d.instance_id AND a.run_id=d.run_id
   AND a.task_id=d.task_id AND a.attempt_id=d.attempt_id
 WHERE d.instance_id=:instance AND d.run_id=:run
   AND (CAST(:attempt AS text) IS NULL OR d.attempt_id::text=:attempt)
), legacy AS (
 SELECT d.dispatch_id,min(r.id::text) AS id,min(r.payload::text) AS lo,max(r.payload::text) AS hi
 FROM owned d JOIN model_record_v2 r ON r.instance_id=d.instance_id
   AND r.kind='run-usage-v1' AND r.payload->>'dispatch_id'=d.dispatch_id::text
 WHERE NOT (d.payload ? 'usage_ref') GROUP BY d.dispatch_id
), sources AS (
 SELECT d.*, r.payload AS usage_payload, r.kind AS usage_kind, r.id AS usage_id,
        r.digest AS usage_digest, r.created_at AS observed_at,
        CASE WHEN d.payload ? 'usage_ref' THEN
          d.payload->'usage_ref'=jsonb_build_object('instance_id',r.instance_id::text,
              'id',r.id::text,'kind','run-usage-v2','revision',1,'digest',r.digest)
          AND d.payload#>>'{usage_ref,revision}'='1' AND r.kind='run-usage-v2' AND r.revision=1
          AND r.payload->>'instance_id'=d.instance_id::text
          AND r.payload->>'run_id'=d.run_id::text AND r.payload->>'task_id'=d.task_id::text
          AND r.payload->>'attempt_id'=d.attempt_id::text AND r.payload->>'dispatch_id'=d.dispatch_id::text
          AND r.payload->>'role'=d.role AND r.payload->>'configured_model'=d.choice->>'model'
          AND r.payload->>'connection_id'=d.choice->>'connection_id'
          AND r.payload->'connection_revision'=d.choice->'connection_revision'
        WHEN legacy.id IS NOT NULL THEN legacy.lo=legacy.hi AND r.kind='run-usage-v1' AND r.revision=1
        ELSE TRUE END AS receipt_valid
 FROM owned d
 LEFT JOIN legacy ON legacy.dispatch_id=d.dispatch_id
 LEFT JOIN model_record_v2 r ON r.instance_id=d.instance_id
   AND r.id::text=COALESCE(d.payload#>>'{usage_ref,id}',legacy.id)
), usage_rows AS (
 SELECT *, NOT COALESCE(receipt_valid AND payload->'setup_ref'=CAST(:setup AS jsonb)
       AND actor->>'instance_id'=instance_id::text AND actor->>'run_id'=run_id::text
       AND actor->>'task_id'=task_id::text AND actor->>'attempt_id'=attempt_id::text
       AND actor->>'role'=role AND actor->>'configured_model'=choice->>'model',FALSE) AS invalid,
   CASE WHEN usage_kind='run-usage-v1' THEN jsonb_build_object(
      'input_tokens',usage_payload->'prompt_tokens','output_tokens',usage_payload->'completion_tokens')
      ELSE usage_payload->'measures' END AS measures
 FROM sources
)
"""


async def usage_parameters(
    db: AsyncConnection, run: RunView, attempt: str | None
) -> dict[str, object]:
    snapshot = await store.setup(db, run.instance_id, run.setup_ref)
    return {
        "instance": run.instance_id,
        "run": run.run_id,
        "attempt": attempt,
        "brain": snapshot.brain.choice.model_dump_json(),
        "recon": snapshot.recon.choice.model_dump_json(),
        "setup": run.setup_ref.model_dump_json(),
    }


async def usage_summary(
    db: AsyncConnection, run: RunView, attempt: str | None = None
) -> UsageSummary:
    params = await usage_parameters(db, run, attempt)
    expressions = []
    for key in UsageMeasures.model_fields:
        value = f"measures->>'{key}'"
        if key == "cost_observed":
            expression = f"CASE WHEN jsonb_typeof(measures->'{key}')='string' AND length({value})<=128 AND {value} ~ '^[0-9]+(\\.[0-9]+)?$' THEN ({value})::numeric END"
        else:
            expression = f"CASE WHEN jsonb_typeof(measures->'{key}')='number' AND {value} ~ '^[0-9]{{1,16}}$' THEN CASE WHEN ({value})::numeric<=9007199254740991 THEN ({value})::numeric END END"
        expressions.append(f"{expression} AS {key}")
    aggregates = []
    for key in UsageMeasures.model_fields:
        column = "counted_total" if key == "total_tokens" else key
        aggregates.append(f"sum({column})::text AS {key},count({column}) AS {key}_observed")
    sql = (
        _USAGE_SOURCE
        + ", numeric_usage AS (SELECT *,"
        + ",".join(expressions)
        + " FROM usage_rows), measured AS (SELECT *, CASE WHEN usage_kind='run-usage-v1' THEN CASE WHEN input_tokens+output_tokens<=9007199254740991 THEN input_tokens+output_tokens END ELSE total_tokens END AS counted_total FROM numeric_usage) "
        + (
            "SELECT role,count(*) AS dispatches,count(*) FILTER (WHERE usage_id IS NULL) AS unobserved,"
            "count(*) FILTER (WHERE invalid) AS invalid,"
            + ",".join(aggregates)
            + " FROM measured GROUP BY GROUPING SETS ((),(role))"
        )
    )
    rows = (await db.execute(text(sql), params)).mappings().all()
    if len(rows) > 3:
        raise records.ModelConflict("PROJECTION_LIMIT")
    total, roles = None, []
    for row in rows:
        if row["invalid"]:
            raise records.ModelConflict("REF_UNAVAILABLE")
        fields: dict[str, object] = {
            "dispatches": row["dispatches"],
            "unobserved_dispatches": row["unobserved"],
        }
        for key in UsageMeasures.model_fields:
            covered = row[key + "_observed"]
            fields[key] = UsageSubtotal(
                value=row[key],
                observed_dispatches=covered,
                state="UNKNOWN"
                if covered == 0
                else "OBSERVED"
                if covered == row["dispatches"]
                else "PARTIAL",
            )
        totals = UsageTotals.model_validate(fields)
        if row["role"] is None:
            total = totals
        else:
            role = row["role"]
            if role not in {"BRAIN", "RECON"}:
                raise records.ModelConflict("REF_UNAVAILABLE")
            choice = json.loads(str(params["brain" if role == "BRAIN" else "recon"]))
            roles.append(
                RoleUsage(
                    role=role,
                    configured_model=choice["model"],
                    connection_id=choice["connection_id"],
                    connection_revision=choice["connection_revision"],
                    totals=totals,
                )
            )
    if total is None:
        raise records.ModelConflict("REF_UNAVAILABLE")
    return UsageSummary(scope="RUN" if attempt is None else "ATTEMPT", totals=total, roles=roles)


async def dispatch_usage(
    db: AsyncConnection, run: RunView, actor: Attempt
) -> tuple[list[DispatchUsage], bool]:
    rows = (
        (
            await db.execute(
                text(
                    _USAGE_SOURCE
                    + """
        SELECT u.*, e.reserved_at,e.sent_at,e.settled_at FROM usage_rows u
        LEFT JOIN LATERAL (
          SELECT min(created_at) FILTER (WHERE state='RESERVED') AS reserved_at,
            min(created_at) FILTER (WHERE state='SENT') AS sent_at,
            min(created_at) FILTER (WHERE state IN ('SETTLED','UNKNOWN','RELEASED')) AS settled_at
          FROM run_dispatch_event WHERE instance_id=u.instance_id AND dispatch_id=u.dispatch_id
        ) e ON TRUE ORDER BY u.dispatch_id LIMIT 21
    """
                ),
                await usage_parameters(db, run, actor.attempt_id),
            )
        )
        .mappings()
        .all()
    )
    items = []
    for row in rows[:20]:
        if row["invalid"]:
            raise records.ModelConflict("REF_UNAVAILABLE")
        reference, usage = None, None
        if row["usage_id"] is not None:
            reference = Ref(
                instance_id=actor.instance_id,
                id=str(row["usage_id"]),
                kind=row["usage_kind"],
                digest=row["usage_digest"],
            )
            payload = await records.resolve(db, actor.instance_id, reference, reference.kind)
            if reference.kind == "run-usage-v2":
                usage = UsageRecord.model_validate_json(json.dumps(payload))
            else:
                choice = row["choice"]
                usage = UsageRecord(
                    **usage_observation({"usage": payload}).model_dump(),
                    instance_id=actor.instance_id,
                    run_id=actor.run_id,
                    task_id=actor.task_id,
                    attempt_id=actor.attempt_id,
                    dispatch_id=str(row["dispatch_id"]),
                    role=actor.role,
                    configured_model=choice["model"],
                    connection_id=choice["connection_id"],
                    connection_revision=choice["connection_revision"],
                    observed_at=row["observed_at"],
                )
            if (
                usage.instance_id,
                usage.run_id,
                usage.task_id,
                usage.attempt_id,
                usage.dispatch_id,
            ) != (
                actor.instance_id,
                actor.run_id,
                actor.task_id,
                actor.attempt_id,
                str(row["dispatch_id"]),
            ):
                raise records.ModelConflict("REF_UNAVAILABLE")
        items.append(
            DispatchUsage(
                dispatch_id=str(row["dispatch_id"]),
                state=row["state"],
                usage_ref=reference,
                usage=usage,
                reserved_at=row["reserved_at"],
                sent_at=row["sent_at"],
                settled_at=row["settled_at"],
            )
        )
    return items, len(rows) > 20


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


async def overview_metrics(db: AsyncConnection, run: RunView) -> RunMetrics:
    row = (
        (
            await db.execute(
                text("""
        WITH actors AS (
          SELECT count(DISTINCT CASE WHEN role='BRAIN' THEN 'brain' ELSE task_id::text END) AS agents,
            count(*) AS attempts, count(*) FILTER (WHERE state='FAILED') AS failed_attempts
          FROM run_attempt WHERE instance_id=:instance AND run_id=:run
        ), requests AS (
          SELECT count(*) FILTER (WHERE EXISTS (SELECT 1 FROM run_dispatch_event e
              WHERE e.instance_id=d.instance_id AND e.dispatch_id=d.dispatch_id AND e.state='SENT')) AS sent,
            count(*) FILTER (WHERE state='RESERVED') AS reserved,
            count(*) FILTER (WHERE state='RELEASED') AS released,
            count(*) FILTER (WHERE state='SENT') AS inflight,
            count(*) FILTER (WHERE state='SETTLED') AS settled,
            count(*) FILTER (WHERE state='UNKNOWN') AS unknown
          FROM run_dispatch d WHERE instance_id=:instance AND run_id=:run
        ), timing AS (
          SELECT min((payload->>'created_at')::timestamptz) FILTER (WHERE payload->>'kind'='started') AS started_at,
            CASE WHEN :terminal THEN max((payload->>'created_at')::timestamptz) END AS finished_at
          FROM run_event WHERE instance_id=:instance AND run_id=:run
        ) SELECT * FROM actors CROSS JOIN requests CROSS JOIN timing
    """),
                {
                    "instance": run.instance_id,
                    "run": run.run_id,
                    "terminal": run.state in {"STOPPED", "COMPLETED", "LIMITED"},
                },
            )
        )
        .mappings()
        .one()
    )
    return RunMetrics.model_validate(dict(row))


def agent_cursor(run: RunView, after: str | None) -> str | None:
    if after is None:
        return None
    prefix = f"{run.run_id}:{run.revision}:"
    key = after.removeprefix(prefix)
    if not after.startswith(prefix) or not valid_agent(key):
        raise records.ModelConflict("CURSOR_DENIED")
    return key


def valid_agent(value: str) -> bool:
    from uuid import UUID

    if value == "brain":
        return True
    try:
        return str(UUID(value, version=4)) == value
    except ValueError:
        return False


async def agent_page(db: AsyncConnection, run: RunView, after: str | None, limit: int) -> AgentPage:
    key = agent_cursor(run, after)
    if key is not None and not await db.scalar(
        text(
            "SELECT 1 FROM run_attempt WHERE instance_id=:instance AND run_id=:run AND (CASE WHEN role='BRAIN' THEN 'brain' ELSE task_id::text END)=:agent LIMIT 1"
        ),
        {"instance": run.instance_id, "run": run.run_id, "agent": key},
    ):
        raise records.ModelConflict("CURSOR_DENIED")
    # Revision-bound keysets refuse a changed roster rather than silently skip new UUIDs.
    rows = (
        (
            await db.execute(
                text("""
        WITH grouped AS (
          SELECT CASE WHEN role='BRAIN' THEN 'brain' ELSE task_id::text END AS agent_id,
            role, count(*) AS attempts
          FROM run_attempt WHERE instance_id=:instance AND run_id=:run GROUP BY 1,2
        ) SELECT g.*, a.attempt_id::text, a.state, a.payload->>'brief' AS brief,
            CASE WHEN p.role='BRAIN' THEN 'brain' ELSE p.task_id::text END AS parent_agent_id
          FROM grouped g JOIN LATERAL (
            SELECT a.* FROM run_attempt a
            WHERE a.instance_id=:instance AND a.run_id=:run
              AND (CASE WHEN a.role='BRAIN' THEN 'brain' ELSE a.task_id::text END)=g.agent_id
            ORDER BY (a.attempt_id::text=:active) DESC,
              (SELECT max(e.sequence) FROM run_event e WHERE e.instance_id=a.instance_id
                AND e.run_id=a.run_id AND e.payload->>'attempt_id'=a.attempt_id::text) DESC NULLS LAST,
              a.attempt_id DESC LIMIT 1
          ) a ON TRUE LEFT JOIN run_task p ON p.instance_id=a.instance_id AND p.run_id=a.run_id
              AND p.task_id::text=a.payload->>'parent_task_id' AND g.role<>'BRAIN'
          WHERE CAST(:after AS text) IS NULL OR (g.agent_id<>'brain' AND (:after='brain' OR g.agent_id>:after))
          ORDER BY (g.role='BRAIN') DESC,g.agent_id LIMIT :limit
    """),
                {
                    "instance": run.instance_id,
                    "run": run.run_id,
                    "active": run.active_attempt_id,
                    "after": key,
                    "limit": limit + 1,
                },
            )
        )
        .mappings()
        .all()
    )
    result = AgentPage(
        run_id=run.run_id,
        revision=run.revision,
        agents=[],
        has_more=len(rows) > limit,
        next_after=None,
        as_of=datetime.now(UTC),
    )
    for row in rows[:limit]:
        item = AgentRow.model_validate(dict(row))
        proposed = result.model_copy(update={"agents": [*result.agents, item]})
        if len(proposed.model_dump_json().encode()) > 65000:
            result = result.model_copy(update={"has_more": True})
            break
        result = proposed
    if result.has_more:
        if not result.agents:
            raise records.ModelConflict("PROJECTION_LIMIT")
        result = result.model_copy(
            update={"next_after": f"{run.run_id}:{run.revision}:{result.agents[-1].agent_id}"}
        )
    return result


async def agents(engine: AsyncEngine, identity: str, after: str | None, limit: int) -> AgentPage:
    async with engine.connect() as connection:
        db = await connection.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        async with db.begin():
            return await agent_page(db, await read_run(db, identity), after, limit)


async def agent_history(
    engine: AsyncEngine, identity: str, agent: str, after: str | None, limit: int
) -> AgentHistory:
    if not valid_agent(agent):
        raise records.ModelConflict("NOT_FOUND")
    cursor = 0
    if after is not None:
        prefix = f"{identity}:{agent}:"
        number = after.removeprefix(prefix)
        if (
            not after.startswith(prefix)
            or not number.isascii()
            or not number.isdecimal()
            or len(number) > 16
            or int(number) > 9007199254740991
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
            params = {
                "instance": run.instance_id,
                "run": identity,
                "agent": agent,
                "after": cursor,
                "limit": limit + 1,
            }
            exists = await db.scalar(
                text(
                    "SELECT 1 FROM run_attempt WHERE instance_id=:instance AND run_id=:run AND (CASE WHEN role='BRAIN' THEN 'brain' ELSE task_id::text END)=:agent LIMIT 1"
                ),
                params,
            )
            if not exists:
                raise records.ModelConflict("NOT_FOUND")
            rows = (
                (
                    await db.execute(
                        text("""
                SELECT e.payload, a.state, paired.sequence AS paired_sequence FROM run_event e
                JOIN run_attempt a ON a.instance_id=e.instance_id AND a.run_id=e.run_id
                  AND a.attempt_id::text=e.payload->>'attempt_id' AND a.task_id::text=e.payload->>'task_id'
                LEFT JOIN LATERAL (
                  SELECT p.sequence FROM run_event p WHERE p.instance_id=e.instance_id AND p.run_id=e.run_id
                    AND p.payload->>'task_id'=e.payload->>'task_id'
                    AND p.payload->>'attempt_id'=e.payload->>'attempt_id'
                    AND p.payload->>'call_id'=e.payload->>'call_id'
                    AND ((e.payload->>'kind'='tool_called' AND p.payload->>'kind' IN ('tool_result','result') AND p.sequence>e.sequence)
                      OR (e.payload->>'kind' IN ('tool_result','result') AND p.payload->>'kind'='tool_called' AND p.sequence<e.sequence))
                  ORDER BY p.sequence LIMIT 1
                ) paired ON TRUE
                WHERE e.instance_id=:instance AND e.run_id=:run AND e.sequence>:after
                  AND (CASE WHEN a.role='BRAIN' THEN 'brain' ELSE a.task_id::text END)=:agent
                ORDER BY e.sequence LIMIT :limit
            """),
                        params,
                    )
                )
                .mappings()
                .all()
            )
            result = AgentHistory(
                run_id=identity,
                agent_id=agent,
                through_cursor=cursor,
                events=[],
                has_more=len(rows) > limit,
                as_of=datetime.now(UTC),
            )
            for row in rows[:limit]:
                event = RunEvent.model_validate_json(json.dumps(row["payload"]))
                pairing = "NOT_APPLICABLE"
                if event.kind in {"tool_called", "tool_result"} or (
                    event.kind == "result" and event.call_id
                ):
                    pairing = (
                        "MATCHED"
                        if row["paired_sequence"] is not None
                        else "PENDING"
                        if event.kind == "tool_called" and row["state"] == "RUNNING"
                        else "UNMATCHED"
                    )
                item = AgentEvent.model_validate(
                    {
                        **event.model_dump(),
                        "pairing": pairing,
                        "paired_sequence": row["paired_sequence"],
                    }
                )
                proposed = result.model_copy(
                    update={"events": [*result.events, item], "through_cursor": item.sequence}
                )
                if len(proposed.model_dump_json().encode()) > 65536:
                    result = result.model_copy(update={"has_more": True})
                    break
                result = proposed
            if result.has_more and not result.events:
                raise records.ModelConflict("PROJECTION_LIMIT")
            return result


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
                metrics=await overview_metrics(db, run),
                usage=await usage_summary(db, run),
                owner_live=owner_live,
                phase_active=owner_live
                and run.state == "RUNNING"
                and run.active_attempt_id is not None,
                question=question,
                attempts=[],
                has_more=len(rows) > limit,
                as_of=datetime.now(UTC),
            )
            if len(result.model_dump_json().encode()) > 65536:
                raise records.ModelConflict("PROJECTION_LIMIT")
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
