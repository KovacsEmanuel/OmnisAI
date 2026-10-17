"""SOURCE only: real metadata reader/ASGI, synthetic driver rows; no PG or qualification."""

import copy
from collections.abc import AsyncIterator, Callable
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


def fixture_rows(
    version: int = 1,
    mutate: Callable[[str, dict[str, object]], None] | None = None,
    *,
    extra_entities: int = 0,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    from hashlib import sha256

    def sha(value: object) -> str:
        return sha256(canonical(value)).hexdigest()

    owner, group = str(uuid4()), str(uuid4())
    rows: dict[str, dict[str, object]] = {}

    def add(kind: str, payload: dict[str, object]) -> dict[str, object]:
        if mutate is not None:
            mutate(kind, payload)
        record = store.envelope(kind, payload)
        rows[str(record["id"])] = {
            **store.reference(record),
            "owner_id": UUID(owner),
            "group_id": UUID(group),
            "envelope": record,
        }
        return store.reference(record)

    from omnis.modules.settings.candidate_catalog import COMPILER_REVISION, EVALUATOR_REVISION

    material, compiler, evaluator = "a" * 64, COMPILER_REVISION, EVALUATOR_REVISION
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
    index: dict[str, object] = {
        "refs": [],
        "steps": [],
        "requested": preference,
        "resolution": "NO_MODEL",
        "dependency_closure_refs": [],
        "dependency_artifact_refs": [],
        "catalog_bindings": [],
    }
    sources, candidates = [source], [profile_ref]
    procedure = {"kind": "procedure", "id": str(uuid4()), "revision": 1, "digest": "f" * 64}
    schema = {"kind": "schema", "id": str(uuid4()), "revision": 1, "digest": "f" * 64}
    if version > 1:
        profile_ref["digest"] = source["digest"]
        package_digest = sha(files)
        procedure["digest"] = schema["digest"] = package_digest
        package = {"kind": "package", "id": str(uuid4()), "revision": 1, "digest": package_digest}
        entities = [(package, "contract-package"), (procedure, "map"), (schema, "input")]
        entities.extend(
            (
                {
                    "kind": "asset",
                    "id": str(uuid4()),
                    "revision": 1,
                    "digest": package_digest,
                },
                f"asset-{i}",
            )
            for i in range(extra_entities)
        )
        sources.append(
            add(
                "source-draft",
                {
                    "source_kind": "package",
                    "package_key": "contract-package",
                    "prefix": "packages/0",
                    "files": files,
                    "package_digest": package_digest,
                    "identities": [[ref["kind"], key] for ref, key in entities],
                    "created_by": owner,
                    "author_kind": "OPERATOR",
                    "material_digest": material,
                },
            )
        )
        candidates.extend(ref for ref, _ in entities)
        index["catalog_bindings"] = [
            {"package_key": "contract-package", "entity_kind": ref["kind"], "key": key, "ref": ref}
            for ref, key in entities
        ] + [
            {
                "package_key": "@profile",
                "entity_kind": "profile",
                "key": "contract-profile",
                "ref": profile_ref,
            }
        ]
        index["refs"] = [
            {
                "package_key": "contract-package",
                "entity_kind": "procedure",
                "key": "map",
                "digest": package_digest,
            }
        ]
    if mutate is not None:
        mutate("resolved-index", index)
    shared = {
        "draft_ref": source,
        "source_draft_refs": sources,
        "material_digest": material,
        "resolved_index_digest": sha(index),
        "candidate_refs": candidates,
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
    capture_ref = None
    if version > 1:
        from pathlib import Path

        from omnis.modules.settings.candidate_catalog import CandidateCatalog
        from omnis.modules.tasks.contract_case_input import produce_input

        # Producer-shaped SOURCE, NOT a PG capture/qualification/publication.
        producer = object.__new__(CandidateCatalog)
        snapshot_record = cast(dict[str, object], rows[str(snapshot["id"])]["envelope"])
        admission = add(
            "evaluation-admission",
            producer.admission_payload(
                owner,
                snapshot_record,
                procedure,
                schema,
                version - 1,
            ),
        )
        context = add(
            "contract-input-context",
            {
                "version": version - 1,
                "namespace": "PACKAGE_EVAL",
                "owner_id": owner,
                "basis_ref": admission,
                "snapshot_ref": snapshot,
                "procedure_ref": procedure,
                "schema_ref": schema,
                "selection_ref": None,
                "mission_ref": None,
                "focus_ref": None,
            },
        )
        raw = (
            Path(__file__).parents[2]
            / "skills"
            / (
                "records-mapping-contract/templates/schemas/records.schema.json"
                if version == 3
                else "recon-mapping-contract/templates/schemas/capture.schema.json"
            )
        ).read_bytes()
        context_record = cast(dict[str, object], rows[str(context["id"])]["envelope"])
        valid_context = store.envelope(
            "contract-input-context",
            {
                **cast(dict[str, object], context_record["payload"]),
                "version": version - 1,
                "namespace": "PACKAGE_EVAL",
                "owner_id": owner,
            },
        )
        produced = produce_input(
            valid_context, {"records": []} if version == 3 else {"capture": ""}, raw, str(uuid4())
        )
        capture_ref = add(
            str(produced["kind"]),
            {
                **cast(dict[str, object], produced["payload"]),
                "context_ref": context,
            },
        )
    evaluations = []
    for kind in ("STATIC", "PURE"):
        input_ref = (
            capture_ref
            if version > 1
            else None
            if kind == "STATIC"
            else capture_ref
            if version > 1
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
                    "evaluator": "omnis-static-pure-records-v3"
                    if version == 3
                    else "omnis-static-pure-capture-v2"
                    if version == 2
                    else "omnis-static-pure-v1",
                    "protocol": "c03-static-pure-records-v3"
                    if version == 3
                    else "c03-static-pure-capture-v2"
                    if version == 2
                    else "b06a-static-pure-v1",
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
            "candidate_refs": candidates,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("author_kind", ["OPERATOR", "AI", "IMPORT"])
async def test_retained_capture_protocols_inspect_without_compilation(
    version: int,
    author_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.settings import candidate_catalog, candidate_index, skill_catalog
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_publication import check_evaluations

    def mutate(kind: str, body: dict[str, object]) -> None:
        if kind in ("source-draft", "technical-review"):
            body["author_kind"] = author_kind

    head, rows = fixture_rows(version, mutate)
    identity = str(head["publication_id"])
    record = cast(dict[str, object], rows[identity]["envelope"])
    body = cast(dict[str, object], record["payload"])
    receipts = [
        cast(dict[str, object], r["envelope"])
        for r in rows.values()
        if r["kind"] == "evaluation-receipt"
    ]
    check_evaluations({**body, "owner_id": str(head["owner_id"])}, receipts, [])

    attempts: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        attempts.append("compile/evaluate/open material")
        raise AssertionError("inspection must not compile/evaluate/open material")

    for module, name in (
        (candidate_catalog, "compile_material"),
        (candidate_catalog, "read_material"),
        (candidate_catalog, "evaluate_pure"),
        (candidate_index, "compile_material"),
        (skill_catalog, "compile_catalog"),
        (skill_catalog, "evaluate_pure"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    view = await inspect_publication(
        cast(AsyncConnection, Connection(head, rows)), identity, str(record["digest"])
    )
    assert view.static == "RECORDED_STATIC_PASS" and view.pure == "RECORDED_PURE_PASS"
    assert view.material == "NOT_VERIFIED" and view.runtime == "NOT_AVAILABLE"
    assert view.assessment_selectable is False
    assert attempts == []
    projected = view.model_dump(mode="json")
    for field in (
        "publication_ref",
        "snapshot_ref",
        "technical_review_ref",
        "static_evaluation_ref",
        "pure_evaluation_ref",
        "confirmation_ref",
        "source_draft_refs",
        "compiler_revision",
        "evaluator_revision",
    ):
        assert projected[field] == (
            store.reference(record) if field == "publication_ref" else body[field]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "version,source_kind",
    [(1, "profile"), (2, "profile"), (2, "package"), (3, "profile"), (3, "package")],
)
@pytest.mark.parametrize("author_kind", ["UNKNOWN", None, ["IMPORT"]])
async def test_unknown_source_authorship_refuses(
    version: int, source_kind: str, author_kind: object
) -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    def mutate(kind: str, body: dict[str, object]) -> None:
        if kind == "source-draft" and body["source_kind"] == source_kind:
            body["author_kind"] = author_kind

    head, rows = fixture_rows(version, mutate)
    identity = str(head["publication_id"])
    with pytest.raises(CatalogError, match="^CATALOG_METADATA_UNAVAILABLE$"):
        await inspect_publication(
            cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("confirmation_author", ["AI", "IMPORT", "UNKNOWN"])
async def test_import_authorship_still_requires_operator_confirmation(
    version: int, confirmation_author: str
) -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    def mutate(kind: str, body: dict[str, object]) -> None:
        if kind in ("source-draft", "technical-review"):
            body["author_kind"] = "IMPORT"
        elif kind == "operator-confirmation":
            body["author_kind"] = confirmation_author

    head, rows = fixture_rows(version, mutate)
    identity = str(head["publication_id"])
    with pytest.raises(CatalogError, match="^CATALOG_METADATA_UNAVAILABLE$"):
        await inspect_publication(
            cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [2, 3])
@pytest.mark.parametrize(
    "target,field,replacement",
    [
        ("evaluation-receipt", "protocol", "unknown-protocol"),
        ("evaluation-receipt", "evaluator", "unknown-evaluator"),
        ("contract-input-context", "namespace", "RUN"),
        ("contract-input-context", "version", True),
        ("contract-input-context", "version", 3),
        ("contract-input-context", "owner_id", "00000000-0000-4000-8000-000000000000"),
        ("contract-input-context", "snapshot_ref", "wrong-ref"),
        ("contract-input-context", "procedure_ref", "wrong-ref"),
        ("contract-input-context", "schema_ref", "wrong-ref"),
        ("contract-input-context", "basis_ref", "wrong-ref"),
        ("evaluation-admission", "snapshot_ref", "wrong-ref"),
        ("evaluation-admission", "procedure_ref", "wrong-ref"),
        ("evaluation-admission", "schema_ref", "wrong-ref"),
        ("evaluation-admission", "material_digest", "b" * 64),
        ("evaluation-admission", "resolved_index_digest", "b" * 64),
        ("evaluation-admission", "compiler_revision", "sha256:" + "b" * 64),
        ("evaluation-admission", "version", True),
        ("evaluation-admission", "namespace", "RUN"),
        ("case-input", "version", True),
        ("case-input", "schema_ref", "wrong-ref"),
        ("case-input", "context_ref", "wrong-ref"),
        ("case-input", "owner_id", "00000000-0000-4000-8000-000000000000"),
        ("case-input", "extra", True),
    ],
)
async def test_capture_retained_join_refuses_wrong_contract(
    version: int,
    target: str,
    field: str,
    replacement: object,
) -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    def mutate(kind: str, body: dict[str, object]) -> None:
        if kind == target or (
            target == "case-input" and kind in ("contract-case-input", "contract-case-records")
        ):
            body[field] = (
                {**cast(dict[str, object], body[field]), "id": str(uuid4())}
                if replacement == "wrong-ref"
                else replacement
            )

    head, rows = fixture_rows(version, mutate)
    identity = str(head["publication_id"])
    with pytest.raises(CatalogError, match="CATALOG_METADATA_UNAVAILABLE"):
        await inspect_publication(
            cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [2, 3])
@pytest.mark.parametrize("kind", ["contract-input-context", "evaluation-admission", "case-input"])
@pytest.mark.parametrize("field", ["owner_id", "group_id"])
async def test_capture_rows_bind_owner_and_group(version: int, kind: str, field: str) -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    head, rows = fixture_rows(version)
    identity = str(head["publication_id"])
    actual_kind = (
        ("contract-case-records" if version == 3 else "contract-case-input")
        if kind == "case-input"
        else kind
    )
    next(r for r in rows.values() if r["kind"] == actual_kind)[field] = uuid4()
    with pytest.raises(CatalogError, match="CATALOG_METADATA_UNAVAILABLE"):
        await inspect_publication(
            cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [2, 3])
async def test_static_and_pure_must_retain_the_same_exact_input(version: int) -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    alternate: dict[str, object] = {}

    def mutate(kind: str, body: dict[str, object]) -> None:
        if kind in ("contract-case-input", "contract-case-records"):
            alternate.update(store.envelope(kind, copy.deepcopy(body)))
        if kind == "evaluation-receipt" and body["evaluation_kind"] == "PURE":
            body["input_ref"] = store.reference(alternate)

    head, rows = fixture_rows(version, mutate)
    rows[str(alternate["id"])] = {
        **store.reference(alternate),
        "envelope": alternate,
        "owner_id": head["owner_id"],
        "group_id": next(iter(rows.values()))["group_id"],
    }
    identity = str(head["publication_id"])
    with pytest.raises(CatalogError, match="CATALOG_METADATA_UNAVAILABLE"):
        await inspect_publication(
            cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
        )


@pytest.mark.asyncio
async def test_named_index_projection_preserves_retained_producer_fields() -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication

    head, rows = fixture_rows(3)
    identity = str(head["publication_id"])
    view = await inspect_publication(
        cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
    )
    review = cast(
        dict[str, object],
        next(r for r in rows.values() if r["kind"] == "technical-review")["envelope"],
    )
    index = cast(dict[str, object], cast(dict[str, object], review["payload"])["resolved_index"])
    assert view.model_dump(mode="json").get("catalog_bindings") == index["catalog_bindings"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    [
        "package_key",
        "kind",
        "digest",
        "missing_package",
        "duplicate",
        "aliased_id",
        "extra",
        "over_limit",
        "unknown_kind",
        "source_digest",
        "source_identity",
        "source_identity_extra",
    ],
)
async def test_named_index_rejects_unbound_or_malformed_mapping(attack: str) -> None:
    from omnis.modules.settings.catalog_inspection import READ_FAILURES, inspect_publication

    def mutate(kind: str, body: dict[str, object]) -> None:
        if kind == "source-draft" and body["source_kind"] == "package":
            if attack == "source_digest":
                body["package_digest"] = "b" * 64
            elif attack == "source_identity":
                body["identities"] = [["package", "different-key"]]
            elif attack == "source_identity_extra":
                body["identities"] = [["package", "contract-package", "extra"]]
        if kind != "resolved-index":
            return
        bindings = cast(list[dict[str, object]], body["catalog_bindings"])
        if attack == "package_key":
            bindings[0]["package_key"] = "wrong-package"
        elif attack == "kind":
            bindings[0]["entity_kind"] = "schema"
        elif attack == "digest":
            bindings[0]["ref"] = {**cast(dict[str, object], bindings[0]["ref"]), "digest": "b" * 64}
        elif attack == "missing_package":
            del bindings[0]
        elif attack == "duplicate":
            bindings.append(copy.deepcopy(bindings[0]))
        elif attack == "aliased_id":
            cast(dict[str, object], bindings[1]["ref"])["id"] = cast(
                dict[str, object], bindings[0]["ref"]
            )["id"]
        elif attack == "extra":
            bindings[0]["extra"] = True
        elif attack == "over_limit":
            body["catalog_bindings"] = bindings * 33
        elif attack == "unknown_kind":
            bindings[0]["entity_kind"] = "unknown"

    head, rows = fixture_rows(3, mutate)
    identity = str(head["publication_id"])
    with pytest.raises(READ_FAILURES):
        await inspect_publication(
            cast(AsyncConnection, Connection(head, rows)), identity, str(rows[identity]["digest"])
        )


@pytest.mark.asyncio
async def test_named_index_accepts_128_exact_bindings_and_refuses_129() -> None:
    from omnis.modules.settings.catalog_inspection import inspect_publication
    from omnis.modules.settings.catalog_models import CatalogError

    for count in (128, 129):
        head, rows = fixture_rows(3, extra_entities=count - 4)
        identity = str(head["publication_id"])
        db = cast(AsyncConnection, Connection(head, rows))
        if count == 128:
            view = await inspect_publication(db, identity, str(rows[identity]["digest"]))
            assert len(view.catalog_bindings) == 128
        else:
            # The existing bounded-envelope guard refuses before projection.
            with pytest.raises(CatalogError, match="^COUNT_LIMIT$"):
                await inspect_publication(db, identity, str(rows[identity]["digest"]))


def test_named_index_allows_retained_release_bindings_outside_selected_closure() -> None:
    """Producer keeps ALL release bindings; closure contains selected refs only."""
    from omnis.modules.settings.catalog_inspection import named_index
    from omnis.modules.settings.catalog_models import CatalogError

    _, rows = fixture_rows(3)
    records = [cast(dict[str, object], row["envelope"]) for row in rows.values()]
    body = cast(
        dict[str, object], next(r for r in records if r["kind"] == "catalog-publication")["payload"]
    )
    review = cast(
        dict[str, object], next(r for r in records if r["kind"] == "technical-review")["payload"]
    )
    index = cast(dict[str, object], review["resolved_index"])
    sources = [
        (store.reference(r), cast(dict[str, object], r["payload"]))
        for r in records
        if r["kind"] == "source-draft"
    ]
    external = [
        {
            "package_key": "dependency",
            "entity_kind": kind,
            "key": key,
            "ref": {
                "kind": kind,
                "id": str(uuid4()),
                "revision": 1,
                "digest": "c" * 64,
            },
        }
        for kind, key in (
            ("package", "dependency"),
            ("procedure", "selected"),
            ("schema", "unselected"),
        )
    ]
    closure = [external[0]["ref"], external[1]["ref"]]
    retained_index = {
        **index,
        "catalog_bindings": [*cast(list[object], index["catalog_bindings"]), *external],
    }
    retained_body = {**body, "dependency_closure_refs": closure}
    projected = named_index(retained_body, retained_index, sources)
    assert [b.model_dump(mode="json") for b in projected][-2:] == external[:2]
    assert all(b.key != "unselected" for b in projected)
    with pytest.raises(CatalogError, match="CATALOG_METADATA_UNAVAILABLE"):
        named_index(
            {**retained_body, "dependency_closure_refs": closure[1:]}, retained_index, sources
        )
    malformed = copy.deepcopy(retained_index)
    cast(
        dict[str, object], cast(list[dict[str, object]], malformed["catalog_bindings"])[-1]["ref"]
    )["digest"] = "b" * 64
    with pytest.raises(CatalogError, match="CATALOG_METADATA_UNAVAILABLE"):
        named_index(retained_body, malformed, sources)


def test_behavior_revision_contract_preserves_real_producer_pins() -> None:
    from pydantic import TypeAdapter, ValidationError

    from omnis.modules.settings.candidate_catalog import COMPILER_REVISION, EVALUATOR_REVISION
    from omnis.modules.settings.catalog_inspection_models import CatalogInspection

    for field, value in (
        ("compiler_revision", COMPILER_REVISION),
        ("evaluator_revision", EVALUATOR_REVISION),
    ):
        adapter = TypeAdapter(CatalogInspection.model_fields[field].rebuild_annotation())
        assert adapter.validate_python(value, strict=True) == value
        for invalid in (value[7:], value.upper(), "sha256:" + "z" * 64, True):
            with pytest.raises(ValidationError):
                adapter.validate_python(invalid, strict=True)
