"""Exact owner-scoped publication consumer. Human authority is a TTY channel."""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import NoReturn

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.runs.plan_snapshot import snapshot_payload

from . import candidate_store as store
from . import publication_store as heads
from .candidate_catalog import (
    COMPILER_REVISION,
    EVALUATOR_REVISION,
    CandidateCatalog,
    payload,
    uuid_string,
    valid_ref,
)
from .candidate_index import resolved_index
from .candidate_material import digest
from .catalog_models import CatalogError, CompiledCatalog, Profile
from .catalog_schema import canonical, dto
from .publication_models import load_request, selection, validate_request
from .skill_catalog import read_file


def check_evaluations(
    value: dict[str, object], records: list[dict[str, object]], closure: list[object]
) -> None:
    if len(records) != 2:
        raise CatalogError("EVALUATION_MISMATCH")
    capture_v2 = payload(records[0]).get("protocol") == "c03-static-pure-capture-v2"
    records_v3 = payload(records[0]).get("protocol") == "c03-static-pure-records-v3"
    if capture_v2 or records_v3:
        first_input = valid_ref(payload(records[0]).get("input_ref"))
        second_input = valid_ref(payload(records[1]).get("input_ref"))
        if (
            first_input["kind"]
            != ("contract-case-records" if records_v3 else "contract-case-input")
            or first_input != second_input
        ):
            raise CatalogError("EVALUATION_MISMATCH")
    for kind, record in zip(("STATIC", "PURE"), records, strict=True):
        body = payload(record)
        expected = {
            "snapshot_ref": value["snapshot_ref"],
            "material_digest": value["material_digest"],
            "resolved_index_digest": value["resolved_index_digest"],
            "dependency_closure_digest": value["dependency_closure_digest"],
            "dependency_closure_refs": closure,
            "compiler_revision": COMPILER_REVISION,
            "evaluator_revision": EVALUATOR_REVISION,
            "evaluator": "omnis-static-pure-records-v3"
            if records_v3
            else "omnis-static-pure-capture-v2"
            if capture_v2
            else "omnis-static-pure-v1",
            "protocol": "c03-static-pure-records-v3"
            if records_v3
            else "c03-static-pure-capture-v2"
            if capture_v2
            else "b06a-static-pure-v1",
            "created_by": value["owner_id"],
            "evaluation_kind": kind,
            "status": kind + "_PASS",
            "reason": None,
            "resolution": "NO_MODEL",
            "effective": None,
            "model_ref": None,
        }
        if (
            record["kind"] != "evaluation-receipt"
            or store.reference(record) != value[kind.lower() + "_evaluation_ref"]
            or not set(expected) <= set(body)
            or any(body.get(key) != item for key, item in expected.items())
        ):
            raise CatalogError("EVALUATION_MISMATCH")


def check_profile(profile: Profile) -> None:
    if any(recipe.role == "REVIEWER" for recipe in profile.agent_recipes):
        raise CatalogError("REVIEWER_NOT_SUPPORTED")


def check_profile_bytes(raw: bytes, source: dict[str, object]) -> None:
    files = source.get("files")
    if not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict):
        raise CatalogError("SOURCE_DRAFT_MISMATCH")
    if files[0] != {"path": "profile.yaml", "sha256": digest(raw), "size": len(raw)}:
        raise CatalogError("FROZEN_MATERIAL_MISMATCH")
    profile = dto(raw, Profile)
    if profile.key != source.get("key"):
        raise CatalogError("SOURCE_DRAFT_MISMATCH")
    check_profile(profile)


class PublicationCatalog:
    def __init__(self, engine: AsyncEngine, root: Path) -> None:
        self.engine = engine
        self.candidates = CandidateCatalog(engine, root)
        self.root = self.candidates.root

    async def dispatch(self, operation: str, request: object) -> dict[str, object]:
        if operation == "confirm":
            raise CatalogError("OPERATOR_CONFIRMATION_REQUIRED")
        value = validate_request(operation, request)
        async with asyncio.timeout(15):
            return await self._dispatch(operation, value)

    async def _selected(
        self, connection: AsyncConnection, owner: str, value: dict[str, object]
    ) -> tuple[str, str, dict[str, object]]:
        group, sources = await self.candidates.sources(connection, owner, value)
        draft = next((r for r in sources if store.reference(r) == value["draft_ref"]), None)
        if draft is None:
            raise CatalogError("SOURCE_DRAFT_MISMATCH")
        key = heads.profile_key(draft)
        if await self.candidates.rejected(connection, owner, group):
            raise CatalogError("CANDIDATE_REJECTED")
        back = await self.candidates.snapshot_readback(
            connection, owner, valid_ref(value["snapshot_ref"])
        )
        snapshot = back["snapshot"]
        index = back["resolved_index"]
        if not isinstance(snapshot, dict) or not isinstance(index, dict):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        snapshot_group, _ = await store.get(connection, owner, valid_ref(value["snapshot_ref"]))
        body = payload(snapshot)
        if snapshot_group != group:
            raise CatalogError("SNAPSHOT_MISMATCH")
        check_profile_bytes(
            read_file(self.root / "candidates" / str(snapshot["id"]) / "profile.yaml", 262144),
            payload(draft),
        )
        for field in (
            "draft_ref",
            "source_draft_refs",
            "technical_review_ref",
            "material_digest",
            "resolved_index_digest",
        ):
            if body.get(field) != value[field]:
                raise CatalogError("PUBLICATION_SELECTION_MISMATCH")
        closure = body.get("dependency_closure_refs")
        refs = body.get("candidate_refs")
        if not isinstance(closure, list) or not isinstance(refs, list):
            raise CatalogError("SNAPSHOT_MISMATCH")
        profiles = [valid_ref(ref) for ref in refs if valid_ref(ref)["kind"] == "profile"]
        if (
            len(profiles) != 1
            or profiles[0] != body["profile_ref"]
            or value["dependency_closure_digest"] != digest(canonical(closure))
            or index.get("resolution") != "NO_MODEL"
            or index.get("dependency_closure_refs") != closure
            or not isinstance(index.get("dependency_artifact_refs"), list)
        ):
            raise CatalogError("PUBLICATION_SELECTION_MISMATCH")
        evaluations: list[dict[str, object]] = []
        available = back.get("evaluations")
        if not isinstance(available, list):
            raise CatalogError("EVALUATION_MISMATCH")
        for field in ("static_evaluation_ref", "pure_evaluation_ref"):
            receipt_group, receipt = await store.get(connection, owner, valid_ref(value[field]))
            if receipt_group != group or receipt not in available:
                raise CatalogError("EVALUATION_MISMATCH")
            evaluations.append(receipt)
        check_evaluations(value, evaluations, closure)
        back["evaluations"] = evaluations
        return group, key, back

    async def _confirmation(
        self, connection: AsyncConnection, owner: str, group: str, value: dict[str, object]
    ) -> dict[str, object]:
        confirmation_group, record = await store.get(
            connection, owner, valid_ref(value["confirmation_ref"])
        )
        body = payload(record)
        actor = body.get("actor")
        if (
            confirmation_group != group
            or record["kind"] != "operator-confirmation"
            or set(body) != {"selection", "actor", "author_kind", "created_by"}
            or body.get("selection") != selection(value)
            or body.get("created_by") != owner
            or body.get("author_kind") != "OPERATOR"
            or type(actor) is not str
            or re.fullmatch(r"local-operator:(?:0|[1-9][0-9]*)", actor) is None
        ):
            raise CatalogError("CONFIRMATION_MISMATCH")
        return record

    def _publication_payload(
        self, owner: str, key: str, value: dict[str, object], back: dict[str, object]
    ) -> dict[str, object]:
        snapshot, index = back["snapshot"], back["resolved_index"]
        if not isinstance(snapshot, dict) or not isinstance(index, dict):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        body = payload(snapshot)
        generation = value["expected_head_generation"]
        if type(generation) is not int or generation >= 2**63 - 1:
            raise CatalogError("INVALID_REQUEST")
        return {
            **selection(value),
            "confirmation_ref": value["confirmation_ref"],
            "profile_key": key,
            "generation": generation + 1,
            "profile_ref": body["profile_ref"],
            "candidate_refs": body["candidate_refs"],
            "dependency_closure_refs": body["dependency_closure_refs"],
            "dependency_artifact_refs": index["dependency_artifact_refs"],
            "compiler_revision": COMPILER_REVISION,
            "evaluator_revision": EVALUATOR_REVISION,
            "created_by": owner,
            "state": "PUBLISHED",
            "resolution": "NO_MODEL",
            "effective": None,
            "assessment_selectable": False,
        }

    async def _readback(
        self, connection: AsyncConnection, owner: str, ref: dict[str, object]
    ) -> dict[str, object]:
        group, publication = await store.get(connection, owner, ref)
        if publication["kind"] != "catalog-publication":
            raise CatalogError("PUBLICATION_MISMATCH")
        body = payload(publication)
        value = validate_request(
            "publish",
            {
                "schema_version": 1,
                "owner_id": owner,
                "command_id": publication["id"],
                **selection(body),
                "confirmation_ref": body.get("confirmation_ref"),
            },
        )
        source_group, key, back = await self._selected(connection, owner, value)
        await self._confirmation(connection, owner, group, value)
        if source_group != group or body != self._publication_payload(owner, key, value, back):
            raise CatalogError("PUBLICATION_MISMATCH")
        return {
            "publication_ref": ref,
            "publication": publication,
            "snapshot": back["snapshot"],
            "resolved_index": back["resolved_index"],
            "evaluations": back["evaluations"],
            "state": "PUBLISHED",
            "assessment_selectable": False,
        }

    async def load_probe(
        self, connection: AsyncConnection, owner: str, ref: dict[str, object]
    ) -> tuple[str, dict[str, object], Profile, CompiledCatalog]:
        """Revalidate exact publication/material without executing qualification PURE."""
        owner = uuid_string(owner)
        if valid_ref(ref)["kind"] != "run-snapshot":
            raise CatalogError("SNAPSHOT_MISMATCH")
        group, snapshot = await store.get(connection, owner, ref)
        body = payload(snapshot)
        # RELEASE recompilation executes its qualification input. This interim
        # consumer cannot admit it while promising execution-free readback.
        if body.get("dependency_artifact_refs") != []:
            raise CatalogError("RELEASE_DEPENDENCY_NOT_SUPPORTED")
        back = await self._readback(connection, owner, valid_ref(body.get("publication_ref")))
        publication = back["publication"]
        index = back["resolved_index"]
        candidate = back["snapshot"]
        if (
            not isinstance(publication, dict)
            or not isinstance(index, dict)
            or not isinstance(candidate, dict)
        ):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        publication_group, _ = await store.get(connection, owner, store.reference(publication))
        if group != publication_group or body != snapshot_payload(publication):
            raise CatalogError("SNAPSHOT_MISMATCH")
        candidate_body = payload(candidate)
        _, records = await self.candidates.sources(connection, owner, candidate_body)
        directory = self.root / "candidates" / str(candidate["id"])
        raw = read_file(directory / "profile.yaml", 262144)
        draft = next(r for r in records if store.reference(r) == candidate_body["draft_ref"])
        check_profile_bytes(raw, payload(draft))
        refs = candidate_body["candidate_refs"]
        if not isinstance(refs, list):
            raise CatalogError("SNAPSHOT_MISMATCH")
        compiled = await self.candidates.compile_pinned(
            connection, owner, directory, records, [valid_ref(r) for r in refs], index
        )
        if resolved_index(compiled) != index or compiled.material_digest != body["material_digest"]:
            raise CatalogError("SNAPSHOT_MISMATCH")
        return group, snapshot, dto(raw, Profile), compiled

    async def _revalidate(
        self,
        connection: AsyncConnection,
        owner: str,
        operation: str,
        value: dict[str, object],
        result: dict[str, object],
    ) -> None:
        if operation == "confirm":
            group, _, _ = await self._selected(connection, owner, value)
            record = await self._confirmation(
                connection,
                owner,
                group,
                {**value, "confirmation_ref": result.get("confirmation_ref")},
            )
            if result != {"confirmation_ref": store.reference(record), "confirmation": record}:
                raise CatalogError("STORAGE_INCOMPATIBLE")
        elif operation == "publish":
            back = await self._readback(connection, owner, valid_ref(result.get("publication_ref")))
            publication = back["publication"]
            if not isinstance(publication, dict):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            publication_body = payload(publication)
            if (
                selection(publication_body) != selection(value)
                or publication_body.get("confirmation_ref") != value["confirmation_ref"]
            ):
                raise CatalogError("PUBLICATION_SELECTION_MISMATCH")
            if result != {
                "publication_ref": back["publication_ref"],
                "publication": publication,
                "state": "PUBLISHED",
                "generation": publication_body["generation"],
            }:
                raise CatalogError("STORAGE_INCOMPATIBLE")
        elif operation == "snapshot":
            back = await self._readback(connection, owner, valid_ref(value["publication_ref"]))
            publication = back["publication"]
            if not isinstance(publication, dict):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            group, _ = await store.get(connection, owner, valid_ref(value["publication_ref"]))
            snapshot_group, snapshot = await store.get(
                connection, owner, valid_ref(result.get("snapshot_ref"))
            )
            if (
                snapshot_group != group
                or snapshot["kind"] != "run-snapshot"
                or payload(snapshot) != snapshot_payload(publication)
                or result != {"snapshot_ref": store.reference(snapshot), "snapshot": snapshot}
            ):
                raise CatalogError("SNAPSHOT_MISMATCH")

    async def _dispatch(self, operation: str, value: dict[str, object]) -> dict[str, object]:
        owner = uuid_string(value["owner_id"])
        async with self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            if operation == "head":
                _, draft = await store.get(connection, owner, valid_ref(value["draft_ref"]))
                return await heads.head(connection, owner, draft)
            if operation == "readback":
                return await self._readback(connection, owner, valid_ref(value["publication_ref"]))
            command = uuid_string(value["command_id"])
            result: dict[str, object]
            prior = await store.replay(connection, owner, command, operation, value)
            if prior is not None:
                await self._revalidate(connection, owner, operation, value, prior)
                return prior
            if operation == "snapshot":
                back = await self._readback(connection, owner, valid_ref(value["publication_ref"]))
                publication = back["publication"]
                if not isinstance(publication, dict):
                    raise CatalogError("STORAGE_INCOMPATIBLE")
                group, _ = await store.get(connection, owner, valid_ref(value["publication_ref"]))
                record = store.envelope("run-snapshot", snapshot_payload(publication))
                await store.put(connection, owner, group, record)
                result = {"snapshot_ref": store.reference(record), "snapshot": record}
            else:
                group, key, back = await self._selected(connection, owner, value)
                _, draft = await store.get(connection, owner, valid_ref(value["draft_ref"]))
                current = await heads.head(connection, owner, draft)
                heads.check_head(current, value)
                if operation == "confirm":
                    record = store.envelope(
                        "operator-confirmation",
                        {
                            "selection": selection(value),
                            "actor": "local-operator:" + str(os.getuid()),
                            "author_kind": "OPERATOR",
                            "created_by": owner,
                        },
                    )
                    await store.put(connection, owner, group, record)
                    result = {"confirmation_ref": store.reference(record), "confirmation": record}
                else:
                    await self._confirmation(connection, owner, group, value)
                    record = store.envelope(
                        "catalog-publication", self._publication_payload(owner, key, value, back)
                    )
                    await store.put(connection, owner, group, record)
                    generation = await heads.promote(connection, owner, key, value, record)
                    result = {
                        "publication_ref": store.reference(record),
                        "publication": record,
                        "state": "PUBLISHED",
                        "generation": generation,
                    }
            await store.complete(connection, owner, command, operation, value, result)
        # Re-read committed immutable records and bytes on a new owning transaction.
        async with self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            committed = await store.replay(connection, owner, command, operation, value)
            if committed is None:
                raise CatalogError("STORAGE_INCOMPATIBLE")
            await self._revalidate(connection, owner, operation, value, committed)
            return committed

    async def _operator_confirm(self, request: object) -> dict[str, object]:
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise CatalogError("OPERATOR_CONFIRMATION_REQUIRED")
        value = validate_request("confirm", request)
        owner = uuid_string(value["owner_id"])
        async with asyncio.timeout(15), self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            prior = await store.replay(
                connection, owner, uuid_string(value["command_id"]), "confirm", value
            )
            if prior is not None:
                await self._revalidate(connection, owner, "confirm", value, prior)
                return prior
            _, _, back = await self._selected(connection, owner, value)
            _, draft = await store.get(connection, owner, valid_ref(value["draft_ref"]))
            heads.check_head(await heads.head(connection, owner, draft), value)
        print(
            canonical(
                {
                    "selection": selection(value),
                    "evaluation_statuses": ["STATIC_PASS", "PURE_PASS"],
                    "assessment_selectable": False,
                    "resolution": "NO_MODEL",
                }
            ).decode(),
            file=sys.stderr,
        )
        print(
            "Operator: confirm exact publication selection (type yes): ",
            end="",
            file=sys.stderr,
            flush=True,
        )
        if sys.stdin.readline(16) != "yes\n":
            raise CatalogError("OPERATOR_CONFIRMATION_REQUIRED")
        # No lock is held while waiting for a human; recheck CAS and every pin afterwards.
        async with asyncio.timeout(15):
            return await self._dispatch("confirm", value)


def main(argv: list[str] | None = None) -> int:
    class SafeParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = SafeParser()
    parser.add_argument("operation", choices=("head", "confirm", "publish", "readback", "snapshot"))
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog-root", required=True)
    try:
        args = parser.parse_args(argv)
        if args.operation == "confirm" and (not sys.stdin.isatty() or not sys.stderr.isatty()):
            raise CatalogError("OPERATOR_CONFIRMATION_REQUIRED")
        request = load_request(read_file(Path(args.request)))
        validate_request(args.operation, request)
        url = os.environ.get("OMNIS_DATABASE_URL")
        if not url:
            raise CatalogError("DATABASE_UNAVAILABLE")

        async def run() -> dict[str, object]:
            engine = database_engine(url)
            try:
                catalog = PublicationCatalog(engine, Path(args.catalog_root))
                if args.operation == "confirm":
                    return await catalog._operator_confirm(request)
                return await catalog.dispatch(args.operation, request)
            finally:
                await engine.dispose()

        print(canonical(asyncio.run(run())).decode())
        return 0
    except CatalogError as error:
        reason = error.reason
    except (SQLAlchemyError, TimeoutError):
        reason = "DATABASE_UNAVAILABLE"
    except (OSError, UnicodeError, RecursionError, ValueError, KeyError, TypeError):
        reason = "INPUT_UNAVAILABLE"
    print(canonical({"status": "BLOCKED", "reason": reason}).decode(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
