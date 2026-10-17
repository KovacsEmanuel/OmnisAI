"""SOURCE only: real metadata reader/ASGI, synthetic driver rows; no PG or qualification."""

import copy
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.catalog_schema import canonical


@pytest.mark.asyncio
async def test_authenticated_routes_are_read_only_and_bind_exact_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    import httpx

    from omnis.api import create_app
    from omnis.security import host_origin
    from omnis.security.sessions import SessionGrant, SessionStore

    head, rows = fixture_rows()
    connection = Connection(head, rows)

    class Engine:
        @asynccontextmanager
        async def connect(self) -> AsyncIterator["Connection"]:
            yield connection

    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    grant = SessionGrant("synthetic-source-only")
    monkeypatch.setattr(SessionStore, "authenticate", AsyncMock(return_value=grant))
    app = create_app()
    app.state.db_engine = Engine()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        path = "/api/v1/settings/catalog"
        assert (await client.get(path)).status_code == 401
        client.cookies.set("omnis_session", grant.token)
        page = await client.get(path)
        assert page.status_code == 200
        assert page.headers["cache-control"] == "no-store"
        ref = page.json()["items"][0]["publication_ref"]
        detail = path + "/publications/" + ref["id"] + "/" + ref["digest"]
        assert (await client.get(detail)).status_code == 200
        assert (await client.get(detail[:-64] + "f" * 64)).status_code == 503
        assert (await client.get(path + "?owner_id=" + str(uuid4()))).status_code == 400
        assert (
            await client.post(
                path, headers={"Origin": "http://127.0.0.1:8765", "X-CSRF-Token": grant.csrf}
            )
        ).status_code == 405


def fixture_rows() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    from hashlib import sha256

    def sha(value: object) -> str:
        return sha256(canonical(value)).hexdigest()

    owner, group = str(uuid4()), str(uuid4())
    rows: dict[str, dict[str, object]] = {}

    def add(kind: str, payload: dict[str, object]) -> dict[str, object]:
        record = store.envelope(kind, payload)
        rows[str(record["id"])] = {
            **store.reference(record),
            "owner_id": UUID(owner),
            "group_id": UUID(group),
            "envelope": record,
        }
        return store.reference(record)

    material, compiler, evaluator = "a" * 64, "b" * 64, "c" * 64
    profile_ref = {"kind": "profile", "id": str(uuid4()), "revision": 1, "digest": "d" * 64}
    files = [{"path": "profile.yaml", "sha256": "e" * 64, "size": 25}]
    source = add(
        "source-draft",
        {
            "source_kind": "profile",
            "key": "contract-profile",
            "prefix": "",
            "files": files,
            "identities": [["profile", "contract-profile"]],
            "created_by": owner,
            "author_kind": "OPERATOR",
            "material_digest": material,
        },
    )
    preference = {
        "model_key": None,
        "effort": None,
        "requirement": "PREFERRED",
        "on_unavailable": "BLOCK",
    }
    index = {
        "refs": [],
        "steps": [],
        "requested": preference,
        "resolution": "NO_MODEL",
        "dependency_closure_refs": [],
        "dependency_artifact_refs": [],
        "catalog_bindings": [],
    }
    shared = {
        "draft_ref": source,
        "source_draft_refs": [source],
        "material_digest": material,
        "resolved_index_digest": sha(index),
        "candidate_refs": [profile_ref],
        "dependency_closure_refs": [],
        "compiler_revision": compiler,
        "created_by": owner,
    }
    review = add(
        "technical-review",
        {
            **shared,
            "resolved_index": index,
            "dependency_closure_digest": sha([]),
            "reviewed_at": "2026-10-17T00:00:00+00:00",
            "started_at": "2026-10-17T00:00:00+00:00",
            "duration_ns": 1,
            "limits": {"max_material_bytes": 8388608, "dispatch_timeout_seconds": 15},
            "resolution": "NO_MODEL",
            "effective": None,
            "checker": "omnis-static-v1",
            "protocol": "b06a-static-v1",
            "author_kind": "OPERATOR",
            "status": "STATIC_PASS",
            "reason": None,
        },
    )
    snapshot = add(
        "candidate-snapshot", {**shared, "profile_ref": profile_ref, "technical_review_ref": review}
    )
    evaluations = []
    for kind in ("STATIC", "PURE"):
        input_ref = (
            None
            if kind == "STATIC"
            else add(
                "evaluation-input", {"snapshot_ref": snapshot, "input": {}, "created_by": owner}
            )
        )
        evaluations.append(
            add(
                "evaluation-receipt",
                {
                    "snapshot_ref": snapshot,
                    "material_digest": material,
                    "resolved_index_digest": sha(index),
                    "dependency_closure_refs": [],
                    "dependency_closure_digest": sha([]),
                    "compiler_revision": compiler,
                    "evaluator_revision": evaluator,
                    "evaluator": "omnis-static-pure-v1",
                    "protocol": "b06a-static-pure-v1",
                    "tool_versions": {"trusted_handlers": "contract-v1"},
                    "corpus_ref": None,
                    "evaluation_kind": kind,
                    "input_ref": input_ref,
                    "requested": preference,
                    "resolution": "NO_MODEL",
                    "effective": None,
                    "model_ref": None,
                    "created_by": owner,
                    "status": kind + "_PASS",
                    "reason": None,
                    "outputs": [],
                    "evidence_refs": [],
                    "target_evidence": "NOT_APPLICABLE",
                    "limits": {
                        "max_input_bytes": 1048576,
                        "max_output_bytes": 1024,
                        "dispatch_timeout_seconds": 15,
                    },
                    "limitations": ["STATIC/PURE synthetic only"],
                    "started_at": "2026-10-17T00:00:00+00:00",
                    "finished_at": "2026-10-17T00:00:00+00:00",
                    "duration_ns": 1,
                },
            )
        )
    selection: dict[str, object] = {
        key: shared[key]
        for key in ("draft_ref", "source_draft_refs", "material_digest", "resolved_index_digest")
    }
    selection.update(
        {
            "expected_head_generation": 1,
            "snapshot_ref": snapshot,
            "technical_review_ref": review,
            "static_evaluation_ref": evaluations[0],
            "pure_evaluation_ref": evaluations[1],
            "dependency_closure_digest": sha([]),
        }
    )
    confirmation = add(
        "operator-confirmation",
        {
            "selection": selection,
            "actor": "local-operator:1000",
            "author_kind": "OPERATOR",
            "created_by": owner,
        },
    )
    publication = add(
        "catalog-publication",
        {
            **selection,
            "confirmation_ref": confirmation,
            "profile_key": "contract-profile",
            "generation": 2,
            "profile_ref": profile_ref,
            "candidate_refs": [profile_ref],
            "dependency_closure_refs": [],
            "dependency_artifact_refs": [],
            "compiler_revision": compiler,
            "evaluator_revision": evaluator,
            "created_by": owner,
            "state": "PUBLISHED",
            "resolution": "NO_MODEL",
            "effective": None,
            "assessment_selectable": False,
        },
    )
    head = {
        "owner_id": UUID(owner),
        "profile_key": "contract-profile",
        "generation": 2,
        "draft_id": UUID(str(source["id"])),
        "publication_id": UUID(str(publication["id"])),
    }
    return head, rows


class Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "Result":
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, object]]:
        return self.rows


class Connection:
    def __init__(self, head: dict[str, object], rows: dict[str, dict[str, object]]) -> None:
        self.head, self.rows = head, rows
        self.queries: list[str] = []

    async def execute(self, query: object, params: dict[str, object] | None = None) -> Result:
        sql = str(query)
        self.queries.append(sql)
        assert sql.startswith("SELECT "), sql
        if "catalog_publication_head" in sql:
            return Result([self.head] if self.head["publication_id"] else [])
        assert params is not None
        row = self.rows.get(str(params["id"]))
        return Result([row] if row else [])


@pytest.mark.asyncio
async def test_exact_retained_inspection_does_not_follow_changed_head() -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication, published_page

    head, rows = fixture_rows()
    connection = Connection(head, rows)
    db = cast(AsyncConnection, connection)
    page = await published_page(db, None)
    assert len(page.items) == 1 and not page.has_more and page.next_after is None
    ref = page.items[0].publication_ref
    first = await inspect_publication(db, ref.id, ref.digest)
    assert first.review == "RECORDED_STATIC_PASS"
    assert first.static == "RECORDED_STATIC_PASS" and first.pure == "RECORDED_PURE_PASS"
    assert first.material == "NOT_VERIFIED" and first.runtime == "NOT_AVAILABLE"
    assert first.benchmark == first.fixture == first.security == "NOT_VERIFIED"
    assert first.assessment_selectable is False
    head["publication_id"] = None
    assert (await published_page(db, None)).items == []
    assert await inspect_publication(db, ref.id, ref.digest) == first


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack", ["row_digest", "owner", "group", "bool_revision", "unknown_payload", "missing_review"]
)
async def test_tampered_or_missing_records_refuse(attack: str) -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    head, rows = fixture_rows()
    identity = str(head["publication_id"])
    digest = str(rows[identity]["digest"])
    row = rows[identity]
    if attack == "row_digest":
        row["digest"] = "f" * 64
    elif attack in ("owner", "group"):
        target = next(r for r in rows.values() if r["kind"] == "technical-review")
        target[attack + "_id"] = uuid4()
    elif attack == "missing_review":
        del rows[next(k for k, v in rows.items() if v["kind"] == "technical-review")]
    else:
        record = copy.deepcopy(row["envelope"])
        assert isinstance(record, dict)
        if attack == "bool_revision":
            record["revision"] = True
        else:
            payload = record["payload"]
            assert isinstance(payload, dict)
            payload["unexpected"] = True
        from hashlib import sha256

        record["digest"] = sha256(
            canonical({k: v for k, v in record.items() if k != "digest"})
        ).hexdigest()
        row["envelope"] = record
        row["digest"] = digest = str(record["digest"])
    with pytest.raises(CatalogError):
        await inspect_publication(cast(AsyncConnection, Connection(head, rows)), identity, digest)


@pytest.mark.parametrize(
    "value",
    [
        True,
        {"kind": "schema", "id": str(uuid4()), "revision": True, "digest": "a" * 64},
        {"files": [{"path": "profile.yaml", "sha256": "a" * 64, "size": 1, "unknown": True}]},
    ],
)
def test_strict_nested_metadata_cannot_alias_integer_pins(value: object) -> None:
    from omnis.modules.settings.catalog_inspection import metadata_tree
    from omnis.modules.settings.catalog_models import CatalogError

    with pytest.raises(CatalogError):
        metadata_tree({"duration_ns": value} if value is True else {"pin": value})
