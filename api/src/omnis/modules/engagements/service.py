"""Transactional draft history and CAS; revision digests bind exact authored payloads."""

import hashlib
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.core.persistence import DatabaseContractError, read_record
from omnis.modules.engagements.schemas import (
    EngagementDraft,
    EngagementPage,
    EngagementSummary,
    EngagementView,
    LegacyEngagementDraft,
    RevisionPage,
)


class EngagementNotFound(Exception):
    pass


class EngagementConflict(Exception):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def revision_digest(revision_id: UUID, revision: int, payload: LegacyEngagementDraft) -> str:
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

    async def revision_page(
        self, engagement_id: UUID, limit: int, after: int | None
    ) -> RevisionPage:
        async with self.engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM engagement WHERE id = :id"), {"id": engagement_id}
            )
            if exists is None:
                raise EngagementNotFound()
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT engagement_id, schema_version, kind, id, revision, "
                            "digest, payload, created_at FROM engagement_revision "
                            "WHERE engagement_id = :id AND revision > :after "
                            "ORDER BY revision LIMIT :page_size"
                        ),
                        {"id": engagement_id, "after": after or 0, "page_size": limit + 1},
                    )
                )
                .mappings()
                .all()
            )
        items = [checked_view(row) for row in rows[:limit]]
        more = len(rows) > limit
        return RevisionPage(
            items=items, has_more=more, next_page=items[-1].revision if more else None
        )

    async def edit(
        self,
        engagement_id: UUID,
        expected_revision: int,
        expected_digest: str,
        command_id: UUID,
        payload: EngagementDraft,
    ) -> EngagementView:
        if (
            type(engagement_id) is not UUID
            or type(expected_revision) is not int
            or not 1 <= expected_revision < 2147483647
            or type(expected_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None
            or type(command_id) is not UUID
            or type(payload) is not EngagementDraft
        ):
            raise ValueError("Invalid engagement edit authority")
        # Serialize writers on the engagement row, including duplicate commands.
        # A receipt is the revision itself; no mutable command cache is needed.
        async with self.engine.begin() as connection:
            current = await connection.scalar(
                text("SELECT current_revision FROM engagement WHERE id = :id FOR UPDATE"),
                {"id": engagement_id},
            )
            if current is None:
                raise EngagementNotFound()
            previous = (
                (
                    await connection.execute(
                        text(
                            "SELECT engagement_id, schema_version, kind, id, revision, "
                            "digest, payload, created_at FROM engagement_revision "
                            "WHERE engagement_id = :id AND revision = :revision"
                        ),
                        {"id": engagement_id, "revision": expected_revision},
                    )
                )
                .mappings()
                .one_or_none()
            )
            receipt = (
                (
                    await connection.execute(
                        text(
                            "SELECT engagement_id, schema_version, kind, id, revision, "
                            "digest, payload, created_at FROM engagement_revision "
                            "WHERE engagement_id = :id AND command_id = :command"
                        ),
                        {"id": engagement_id, "command": command_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if receipt is not None:
                saved = checked_view(receipt)
                if (
                    saved.revision != expected_revision + 1
                    or previous is None
                    or checked_view(previous).digest != expected_digest
                    or saved.payload != payload
                ):
                    raise EngagementConflict()
                return saved
            if (
                current != expected_revision
                or previous is None
                or checked_view(previous).digest != expected_digest
            ):
                raise EngagementConflict()
            next_revision = expected_revision + 1
            revision_id = uuid4()
            digest = revision_digest(revision_id, next_revision, payload)
            await connection.execute(
                text(
                    "INSERT INTO engagement_revision "
                    "(id, engagement_id, revision, command_id, schema_version, kind, digest, payload) "
                    "VALUES (:revision_id, :id, :revision, :command, 1, "
                    "'engagement-revision', :digest, CAST(:payload AS jsonb))"
                ),
                {
                    "revision_id": revision_id,
                    "id": engagement_id,
                    "revision": next_revision,
                    "command": command_id,
                    "digest": digest,
                    "payload": canonical_json(payload.model_dump(mode="json")),
                },
            )
            await connection.execute(
                text("UPDATE engagement SET current_revision = :revision WHERE id = :id"),
                {"revision": next_revision, "id": engagement_id},
            )
        # Read the committed immutable receipt, not the possibly newer head.
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT engagement_id, schema_version, kind, id, revision, "
                            "digest, payload, created_at FROM engagement_revision WHERE id = :id"
                        ),
                        {"id": revision_id},
                    )
                )
                .mappings()
                .one()
            )
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
