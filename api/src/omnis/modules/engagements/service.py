"""Transactional draft create/read/list; revision digests bind exact authored payloads."""

import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.core.persistence import DatabaseContractError, read_record
from omnis.modules.engagements.schemas import (
    EngagementDraft,
    EngagementPage,
    EngagementSummary,
    EngagementView,
)


class EngagementNotFound(Exception):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def revision_digest(revision_id: UUID, revision: int, payload: EngagementDraft) -> str:
    envelope = {
        "schema_version": 1,
        "kind": "engagement-revision",
        "id": str(revision_id),
        "revision": revision,
        "payload": payload.model_dump(mode="json"),
    }
    return hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()


def checked_view(row: object) -> EngagementView:
    view = read_record(EngagementView, row)
    if view.digest != revision_digest(view.id, view.revision, view.payload):
        raise DatabaseContractError("Persisted engagement revision digest mismatch")
    return view


class EngagementService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def create(self, payload: EngagementDraft) -> EngagementView:
        engagement_id, revision_id = uuid4(), uuid4()
        digest = revision_digest(revision_id, 1, payload)
        async with self.engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO engagement (id, current_revision) VALUES (:id, 1)"),
                {"id": engagement_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO engagement_revision "
                    "(id, engagement_id, revision, schema_version, kind, digest, payload) "
                    "VALUES (:id, :engagement, 1, 1, 'engagement-revision', :digest, CAST(:payload AS jsonb))"
                ),
                {
                    "id": revision_id,
                    "engagement": engagement_id,
                    "digest": digest,
                    "payload": canonical_json(payload.model_dump(mode="json")),
                },
            )
        # Return committed data from a fresh connection, never an echo of the request.
        return await self.read(engagement_id)

    async def read(self, engagement_id: UUID) -> EngagementView:
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT e.id AS engagement_id, r.schema_version, r.kind, r.id, "
                            "r.revision, r.digest, r.payload, r.created_at "
                            "FROM engagement e JOIN engagement_revision r "
                            "ON r.engagement_id = e.id AND r.revision = e.current_revision "
                            "WHERE e.id = :engagement"
                        ),
                        {"engagement": engagement_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise EngagementNotFound()
        return checked_view(row)

    async def list_page(self, limit: int, after: UUID | None) -> EngagementPage:
        async with self.engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT e.id AS engagement_id, r.id, r.revision, r.digest, "
                            "r.payload->>'name' AS name, "
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
        items = [read_record(EngagementSummary, row) for row in rows[:limit]]
        has_more = len(rows) > limit
        return EngagementPage(
            items=items,
            has_more=has_more,
            next_page=items[-1].engagement_id if has_more else None,
        )
