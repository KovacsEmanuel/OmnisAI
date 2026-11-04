"""B03 global draft projection; no run tables, effects or synthetic counters."""

import json
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.core.persistence import DatabaseRecord, read_record
from omnis.modules.engagements.schemas import DraftRecord, EngagementSummary
from omnis.modules.runs.run_contract import RunView

# One fixed query/sort, bound to page size. This is pagination, not authority or SSE.
PAGE_PATTERN = (
    r"^d1\.([1-9]|[1-4][0-9]|50)\.([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)


class RunMetric(DraftRecord):
    state: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    value: Literal[None] = None
    reason: Literal["NOT_RUN"] = "NOT_RUN"


class DashboardMetrics(DraftRecord):
    confirmed: RunMetric = Field(default_factory=RunMetric)
    coverage: RunMetric = Field(default_factory=RunMetric)
    cost: RunMetric = Field(default_factory=RunMetric)


class DashboardEngagement(EngagementSummary):
    scope_revision_id: UUID
    run_id: UUID | None = None
    through_cursor: int | None = None
    run_state: Literal[
        "NOT_RUN",
        "RUNNING",
        "PAUSING",
        "PAUSED",
        "HOLD",
        "STOPPING",
        "STOPPED",
        "COMPLETED",
        "LIMITED",
        "NEEDS_RECONCILIATION",
    ] = "NOT_RUN"
    stage: Literal["NOT_RUN", "INERT"] = "NOT_RUN"


class DashboardData(DraftRecord):
    total_engagements: int = Field(ge=0)
    items: list[DashboardEngagement] = Field(max_length=50)
    active_run: RunView | None = None
    run_state: Literal[
        "NOT_RUN", "RUNNING", "PAUSING", "PAUSED", "HOLD", "STOPPING", "NEEDS_RECONCILIATION"
    ] = "NOT_RUN"
    attention_state: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    metrics: DashboardMetrics = Field(default_factory=DashboardMetrics)


class ProjectionEnvelope(DraftRecord):
    schema_version: Literal[1, 2] = 1
    context: Literal["GLOBAL"] = "GLOBAL"
    engagement_id: Literal[None] = None
    run_id: Literal[None] = None
    scope_revision_id: Literal[None] = None
    through_cursor: Literal[None] = None
    as_of: datetime
    data_state: Literal["AVAILABLE"] = "AVAILABLE"
    data: DashboardData
    limit: int = Field(ge=1, le=50)
    next_page: str | None = Field(default=None, max_length=42, pattern=PAGE_PATTERN)
    has_more: bool


class DashboardSnapshot(DatabaseRecord):
    total_engagements: int = Field(ge=0)
    as_of: datetime


def page_after(limit: int, token: str | None) -> UUID | None:
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Invalid dashboard page size")
    if token is None:
        return None
    match = re.fullmatch(PAGE_PATTERN, token)
    if match is None or int(match[1]) != limit:
        raise ValueError("Dashboard cursor context mismatch")
    return UUID(match[2])


async def dashboard_projection(
    engine: AsyncEngine, limit: int, token: str | None
) -> ProjectionEnvelope:
    after = page_after(limit, token)
    async with engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            )
            snapshot_row = (
                (
                    await connection.execute(
                        text(
                            "SELECT count(*) AS total_engagements, transaction_timestamp() AS as_of FROM engagement"
                        )
                    )
                )
                .mappings()
                .one()
            )
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT e.id AS engagement_id, r.id, r.id AS scope_revision_id, "
                            "r.revision, r.digest, r.payload->>'name' AS name, "
                            "r.payload->>'assessment_mode' AS assessment_mode, r.created_at "
                            "FROM engagement e JOIN engagement_revision r "
                            "ON r.engagement_id = e.id AND r.revision = e.current_revision "
                            "WHERE (CAST(:after AS uuid) IS NULL OR e.id > CAST(:after AS uuid)) "
                            "ORDER BY e.id LIMIT :page_size"
                        ),
                        {"after": after, "page_size": limit + 1},
                    )
                )
                .mappings()
                .all()
            )
            active_payload = await connection.scalar(
                text(
                    "SELECT payload FROM agent_run WHERE instance_id=(SELECT instance_id FROM instance_control WHERE id=1) AND state NOT IN ('STOPPED','COMPLETED','LIMITED')"
                )
            )
            run_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT DISTINCT ON (r.engagement_id) r.payload FROM agent_run r WHERE r.instance_id=(SELECT instance_id FROM instance_control WHERE id=1) AND r.engagement_id=ANY(CAST(:ids AS uuid[])) ORDER BY r.engagement_id,(SELECT max(e.sequence) FROM run_event e WHERE e.instance_id=r.instance_id AND e.run_id=r.run_id) DESC"
                        ),
                        {"ids": [row["engagement_id"] for row in rows[:limit]]},
                    )
                )
                .scalars()
                .all()
            )
    # Materialize and close the transaction/connection before decoding or HTTP I/O.
    snapshot = read_record(DashboardSnapshot, snapshot_row)
    items = [read_record(DashboardEngagement, row) for row in rows[:limit]]
    active = (
        RunView.model_validate_json(json.dumps(active_payload))
        if active_payload is not None
        else None
    )
    runs = [RunView.model_validate_json(json.dumps(row)) for row in run_rows]
    for index, item in enumerate(items):
        latest = next((run for run in runs if run.engagement_id == str(item.engagement_id)), None)
        if latest is not None:
            items[index] = item.model_copy(
                update={
                    "run_id": UUID(latest.run_id),
                    "through_cursor": latest.through_cursor,
                    "run_state": latest.state,
                    "stage": "INERT",
                }
            )
    more = len(rows) > limit
    return ProjectionEnvelope(
        schema_version=2 if runs or active else 1,
        as_of=snapshot.as_of,
        data=DashboardData.model_validate(
            {
                "total_engagements": snapshot.total_engagements,
                "items": items,
                "active_run": active,
                "run_state": active.state if active else "NOT_RUN",
            }
        ),
        limit=limit,
        has_more=more,
        next_page=f"d1.{limit}.{items[-1].engagement_id}" if more else None,
    )
