"""P1 draft persistence through the real local HTTP and PostgreSQL boundaries."""

import asyncio
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.engine import URL

from conftest import connect_test_database
from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.modules.engagements.schemas import EngagementDraft, LegacyEngagementDraft
from omnis.modules.engagements.service import EngagementService, canonical_json, revision_digest
from omnis.security.sessions import SessionStore, code_digest

ORIGIN = "http://127.0.0.1:8765"


def draft() -> dict[str, object]:
    return {
        "name": "Synthetic invoice lab",
        "authorization": {
            "owner": "Synthetic operator",
            "statement": "Synthetic authorized fixture only",
            "valid_from": "2030-01-01T00:00:00Z",
            "valid_until": "2030-12-31T00:00:00Z",
        },
        "scope": [
            {
                "origin": "https://lab.example",
                "port": 443,
                "path_prefix": "/api",
                "exclusions": ["/api/private"],
                "access": "ATTACKABLE",
            }
        ],
        "assessment_mode": "FOCUSED_TEST",
        "objective_text": "  Test only invoice ownership. Do not change data.  ",
        "objective_constraints": [],
        "workflow_profile_ref": None,
        **declarative_fields(),
    }


def declarative_fields() -> dict[str, object]:
    return {
        "application_context": {
            "seed_urls": ["https://lab.example/api/invoices"],
            "priority_workflows": ["Invoice review 😀"],
            "test_objects": ["private invoice", "shared invoice"],
            "import_ref": None,
        },
        "effect_rules": [
            {"effect_class": "LIMITED_WRITE", "decision": "DENY", "note": "No writes"},
        ],
        "budgets": {
            "max_requests": 100,
            "max_duration_seconds": 3600,
            "max_storage_bytes": 1048576,
            "validation_reserved_requests": 20,
            "max_model_calls": 0,
        },
        "data_policy": {
            "model_projection": "NONE",
            "research_egress": "NONE",
            "retention_days": 30,
        },
        "business_matrix": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "principal": "synthetic-owner",
                "role": "owner",
                "tenant": "synthetic-tenant",
                "object": "private invoice",
                "operation": "READ",
                "expected": "ALLOW",
                "source": "synthetic operator statement",
                "source_revision": 1,
            }
        ],
        "business_rules_ref": None,
    }


async def pair_session(app: FastAPI, client: AsyncClient) -> str:
    code = secrets.token_urlsafe(24)
    await SessionStore(app.state.db_engine).register(code_digest(code), issuance_id=uuid4())
    pairing = await client.post("/api/pairing", json={"code": code}, headers={"origin": ORIGIN})
    assert pairing.status_code == 200
    csrf = pairing.json()["csrf_token"]
    assert isinstance(csrf, str)
    return csrf


@pytest.mark.asyncio
async def test_declarative_context_and_matrix_persist_at_first_save_and_edit(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    initial = draft()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            created = await client.post(
                "/api/v1/engagements",
                json=initial,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert created.status_code == 201, created.text
            assert created.json()["payload"] == initial
            url = f"/api/v1/engagements/{created.json()['engagement_id']}"
            changed = {**initial, "objective_text": "Only read private invoice 😀"}
            changed["effect_rules"] = [
                {"effect_class": "SESSION_CHANGE", "decision": "UNKNOWN", "note": "No login yet"},
            ]
            budgets = initial["budgets"]
            matrix = initial["business_matrix"]
            assert isinstance(budgets, dict) and isinstance(matrix, list)
            assert matrix and isinstance(matrix[0], dict)
            changed["budgets"] = {**budgets, "max_requests": 50}
            changed["business_matrix"] = [
                {**matrix[0], "expected": "DENY", "source_revision": 2},
            ]
            updated = await client.put(
                url,
                json=changed,
                headers={
                    "origin": ORIGIN,
                    "x-csrf-token": csrf,
                    "if-match": created.headers["etag"],
                    "x-command-id": str(uuid4()),
                },
            )
            assert updated.status_code == 200 and updated.json()["payload"] == changed
            cookie = client.cookies["omnis_session"]
    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        async with AsyncClient(
            transport=ASGITransport(app=fresh_app),
            base_url=ORIGIN,
            cookies={"omnis_session": cookie},
        ) as client:
            read = await client.get(url)
            assert read.status_code == 200 and read.json() == updated.json()
            history = await client.get(url + "/revisions")
            assert history.status_code == 200
            assert [item["payload"] for item in history.json()["items"]] == [initial, changed]


@pytest.mark.asyncio
async def test_foreign_refs_and_nested_invalid_fields_cannot_advance_the_head(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            headers = {"origin": ORIGIN, "x-csrf-token": csrf}
            first = await client.post("/api/v1/engagements", json=draft(), headers=headers)
            other = await client.post("/api/v1/engagements", json=draft(), headers=headers)
            assert first.status_code == other.status_code == 201
            url = f"/api/v1/engagements/{first.json()['engagement_id']}"
            foreign = {
                "kind": "business-rules",
                "id": other.json()["engagement_id"],
                "revision": 1,
                "digest": other.json()["digest"],
            }
            cases: list[tuple[str, dict[str, object]]] = []
            for field in ("workflow_profile_ref", "business_rules_ref"):
                invalid = draft()
                invalid[field] = foreign
                cases.append((field, invalid))
            invalid = draft()
            context = invalid["application_context"]
            assert isinstance(context, dict)
            context["import_ref"] = foreign
            cases.append(("application_context.import_ref", invalid))
            invalid = draft()
            invalid["objective_constraints"] = [
                {
                    "id": str(uuid4()),
                    "kind": "READ_ONLY",
                    "text": "No guessed operations",
                    "operation_refs": [foreign],
                }
            ]
            cases.append(("objective_constraints.0.operation_refs", invalid))
            invalid = draft()
            context = invalid["application_context"]
            assert isinstance(context, dict)
            context["seed_urls"] = ["https://lab.example:"]
            cases.append(("application_context.seed_urls", invalid))
            invalid = draft()
            effects = invalid["effect_rules"]
            assert isinstance(effects, list) and isinstance(effects[0], dict)
            effects[0]["note"] = "synthetic_marker\x00"
            cases.append(("effect_rules.0.note", invalid))
            invalid = draft()
            matrix = invalid["business_matrix"]
            assert isinstance(matrix, list) and isinstance(matrix[0], dict)
            matrix[0]["source"] = "synthetic_marker\x00"
            cases.append(("business_matrix.0.source", invalid))
            invalid = draft()
            budgets = invalid["budgets"]
            assert isinstance(budgets, dict)
            budgets["validation_reserved_requests"] = 101
            cases.append(("budgets.validation_reserved_requests", invalid))
            for field, invalid in cases:
                response = await client.put(
                    url,
                    json=invalid,
                    headers={
                        **headers,
                        "if-match": first.headers["etag"],
                        "x-command-id": str(uuid4()),
                    },
                )
                assert response.status_code == 422, field
                assert field in {item["field"] for item in response.json()["error"]["field_errors"]}
                assert "synthetic_marker" not in response.text
            assert (await client.get(url)).json() == first.json()
            with connect_test_database(migrated_database_url) as connection:
                assert connection.execute(
                    "SELECT current_revision FROM engagement WHERE id=%s",
                    (first.json()["engagement_id"],),
                ).fetchone() == (1,)


@pytest.mark.asyncio
async def test_legacy_first_save_remains_exact_and_editable_without_backfill(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    raw = {key: value for key, value in draft().items() if key not in declarative_fields()}
    legacy = LegacyEngagementDraft.model_validate(raw)
    engagement_id, revision_id = uuid4(), uuid4()
    digest = revision_digest(revision_id, 1, legacy)
    with connect_test_database(migrated_database_url) as connection:
        connection.execute(
            "INSERT INTO engagement (id,current_revision) VALUES (%s,1)", (engagement_id,)
        )
        connection.execute(
            "INSERT INTO engagement_revision "
            "(id,engagement_id,revision,schema_version,kind,digest,payload) "
            "VALUES (%s,%s,1,1,'engagement-revision',%s,%s::jsonb)",
            (revision_id, engagement_id, digest, canonical_json(legacy.model_dump(mode="json"))),
        )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            url = f"/api/v1/engagements/{engagement_id}"
            before = await client.get(url)
            assert before.status_code == 200
            assert before.json()["payload"] == raw
            assert before.json()["digest"] == digest
            edited = await client.put(
                url,
                json=draft(),
                headers={
                    "origin": ORIGIN,
                    "x-csrf-token": csrf,
                    "if-match": before.headers["etag"],
                    "x-command-id": str(uuid4()),
                },
            )
            assert edited.status_code == 200
            history = await client.get(url + "/revisions")
            assert history.status_code == 200
            assert history.json()["items"] == [before.json(), edited.json()]


@pytest.mark.asyncio
async def test_first_save_has_canonical_revision_and_survives_new_app(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    body = draft()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            created = await client.post(
                "/api/v1/engagements",
                json=body,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert created.status_code == 201
            saved = created.json()
            assert UUID(saved["engagement_id"])
            assert UUID(saved["id"])
            assert saved["schema_version"] == 1
            assert saved["kind"] == "engagement-revision"
            assert saved["revision"] == 1
            assert saved["payload"] == body
            canonical = json.dumps(
                {
                    key: saved[key]
                    for key in ("schema_version", "kind", "id", "revision", "payload")
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            assert saved["digest"] == hashlib.sha256(canonical).hexdigest()
            cookie = client.cookies["omnis_session"]

    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        async with AsyncClient(
            transport=ASGITransport(app=fresh_app),
            base_url=ORIGIN,
            cookies={"omnis_session": cookie},
        ) as client:
            read = await client.get(f"/api/v1/engagements/{saved['engagement_id']}")
            assert read.status_code == 200, (
                read.json()["error"]["code"] if read.status_code != 200 else ""
            )
            assert read.json() == saved
            listing = await client.get("/api/v1/engagements?limit=1")
            assert listing.status_code == 200
            assert listing.json()["items"][0]["engagement_id"] == saved["engagement_id"]
            assert listing.json()["items"][0]["name"] == body["name"]
            assert "payload" not in listing.json()["items"][0]
            assert listing.json()["has_more"] is False
            assert listing.json()["next_page"] is None


@pytest.mark.asyncio
async def test_edit_creates_one_revision_and_replays_original_receipt(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            original = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert original.status_code == 201
            url = f"/api/v1/engagements/{original.json()['engagement_id']}"
            etag = f'"rev-1-{original.json()["digest"]}"'
            assert original.headers["etag"] == etag
            edit = draft()
            edit["objective_text"] = "Synthetic edit — byte-for-byte 😀"
            command_id = str(uuid4())
            headers = {
                "origin": ORIGIN,
                "x-csrf-token": csrf,
                "if-match": etag,
                "x-command-id": command_id,
            }
            updated = await client.put(url, json=edit, headers=headers)
            assert updated.status_code == 200, updated.text
            assert updated.json()["revision"] == 2
            assert updated.json()["payload"] == edit
            assert updated.headers["etag"] == f'"rev-2-{updated.json()["digest"]}"'
            assert (await client.get(url)).json() == updated.json()
            with connect_test_database(migrated_database_url) as connection:
                assert connection.execute(
                    "SELECT current_revision FROM engagement WHERE id = %s",
                    (original.json()["engagement_id"],),
                ).fetchone() == (2,)
                assert connection.execute(
                    "SELECT revision, digest, payload FROM engagement_revision "
                    "WHERE engagement_id = %s ORDER BY revision",
                    (original.json()["engagement_id"],),
                ).fetchall() == [
                    (1, original.json()["digest"], draft()),
                    (2, updated.json()["digest"], edit),
                ]
            history = await client.get(url + "/revisions?limit=1")
            assert history.status_code == 200
            assert history.json()["items"][0] == original.json()
            assert history.json()["next_page"] == 1
            next_page = await client.get(url + "/revisions?limit=1&after=1")
            assert next_page.status_code == 200
            assert next_page.json()["items"] == [updated.json()]
            assert next_page.json()["has_more"] is False
            replay = await client.put(url, json=edit, headers=headers)
            assert replay.status_code == 200 and replay.json() == updated.json()
            conflicting = dict(edit)
            conflicting["objective_text"] = "Different request"
            denied = await client.put(url, json=conflicting, headers=headers)
            assert denied.status_code == 409
            stale = await client.put(
                url, json=conflicting, headers={**headers, "x-command-id": str(uuid4())}
            )
            assert stale.status_code == 409
            assert (await client.get(url)).json() == updated.json()
            saved = updated.json()
            cookie = client.cookies["omnis_session"]

    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        async with AsyncClient(
            transport=ASGITransport(app=fresh_app),
            base_url=ORIGIN,
            cookies={"omnis_session": cookie},
        ) as fresh:
            read = await fresh.get(url)
            assert read.status_code == 200 and read.json() == saved
            assert read.headers["etag"] == f'"rev-2-{saved["digest"]}"'
            history = await fresh.get(url + "/revisions")
            assert history.status_code == 200
            assert [item["revision"] for item in history.json()["items"]] == [1, 2]


@pytest.mark.parametrize("bad_revision", [True, 1.0, "1"])
@pytest.mark.asyncio
async def test_edit_service_rejects_noninteger_revision_before_write_and_replay(
    migrated_database_url: URL, bad_revision: int
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        service = EngagementService(engine)
        payload = EngagementDraft.model_validate(draft())
        first = await service.create(payload)
        with pytest.raises(ValueError):
            await service.edit(first.engagement_id, bad_revision, first.digest, uuid4(), payload)
        assert await service.read(first.engagement_id) == first
        command = uuid4()
        updated = await service.edit(first.engagement_id, 1, first.digest, command, payload)
        with pytest.raises(ValueError):
            await service.edit(first.engagement_id, bad_revision, first.digest, command, payload)
        assert await service.read(first.engagement_id) == updated
        assert await service.edit(first.engagement_id, 1, first.digest, command, payload) == updated
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_two_editors_overlap_on_the_real_postgres_row_lock(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as first:
            csrf = await pair_session(app, first)
            original = await first.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert original.status_code == 201
            url = f"/api/v1/engagements/{original.json()['engagement_id']}"
            headers = {"origin": ORIGIN, "x-csrf-token": csrf, "if-match": original.headers["etag"]}
            cookie = first.cookies["omnis_session"]
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url=ORIGIN,
                cookies={"omnis_session": cookie},
            ) as second:
                left, right = draft(), draft()
                left["name"], right["name"] = "Left editor", "Right editor"
                with (
                    connect_test_database(migrated_database_url) as holder,
                    connect_test_database(migrated_database_url, autocommit=True) as observer,
                ):
                    holder.execute(
                        "SELECT current_revision FROM engagement WHERE id = %s FOR UPDATE",
                        (original.json()["engagement_id"],),
                    )
                    owner_pid = holder.info.backend_pid
                    a = asyncio.create_task(
                        first.put(
                            url,
                            json=left,
                            headers={**headers, "x-command-id": str(uuid4())},
                        )
                    )
                    b = asyncio.create_task(
                        second.put(
                            url,
                            json=right,
                            headers={**headers, "x-command-id": str(uuid4())},
                        )
                    )
                    try:
                        deadline = time.monotonic() + 1.5
                        waiting = 0
                        direct = 0
                        while time.monotonic() < deadline:
                            row = observer.execute(
                                "SELECT count(*), count(*) FILTER "
                                "(WHERE pg_blocking_pids(pid) @> ARRAY[%s::int]) "
                                "FROM pg_stat_activity WHERE datname = current_database() "
                                "AND pid <> pg_backend_pid() "
                                "AND cardinality(pg_blocking_pids(pid)) > 0",
                                (owner_pid,),
                            ).fetchone()
                            assert (
                                row is not None
                                and isinstance(row[0], int)
                                and isinstance(row[1], int)
                            )
                            waiting, direct = row[0], row[1]
                            if waiting >= 2 and direct >= 1:
                                break
                            await asyncio.sleep(0.05)
                        if not (waiting >= 2 and direct >= 1):
                            active = observer.execute(
                                "SELECT wait_event_type, left(query, 90), pg_blocking_pids(pid) "
                                "FROM pg_stat_activity WHERE datname=current_database() "
                                "AND pid <> pg_backend_pid()"
                            ).fetchall()
                            pytest.fail(f"Both editors must overlap in PG lock queue: {active}")
                    finally:
                        holder.commit()
                    results = await asyncio.wait_for(asyncio.gather(a, b), timeout=6)
                assert sorted(response.status_code for response in results) == [200, 409]
                accepted = next(
                    response.json() for response in results if response.status_code == 200
                )
                assert (await first.get(url)).json() == accepted
                history = await first.get(url + "/revisions")
                assert history.status_code == 200
                assert [item["revision"] for item in history.json()["items"]] == [1, 2]


@pytest.mark.asyncio
async def test_edit_headers_and_local_boundary_deny_without_mutation(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            original = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert original.status_code == 201
            url = f"/api/v1/engagements/{original.json()['engagement_id']}"
            valid = {
                "origin": ORIGIN,
                "x-csrf-token": csrf,
                "if-match": original.headers["etag"],
                "x-command-id": str(uuid4()),
            }
            for changed, status in (
                ({"origin": "http://foreign.invalid"}, 403),
                ({"host": "foreign.invalid"}, 400),
                ({"x-csrf-token": "bad"}, 403),
                ({"if-match": "W/" + original.headers["etag"]}, 422),
                ({"if-match": "*"}, 422),
                ({"if-match": '"rev-01-' + original.json()["digest"] + '"'}, 422),
                ({"x-command-id": str(uuid4()).upper()}, 422),
            ):
                denied = await client.put(url, json=draft(), headers={**valid, **changed})
                assert denied.status_code == status
            for missing in ("if-match", "x-command-id"):
                denied = await client.put(
                    url,
                    json=draft(),
                    headers={key: value for key, value in valid.items() if key != missing},
                )
                assert denied.status_code == 422
            oversized = await client.put(url, content=b"x" * 1048577, headers=valid)
            assert oversized.status_code == 413
            malformed = await client.put(
                url,
                content=b"{",
                headers={**valid, "content-type": "application/json"},
            )
            assert malformed.status_code == 422
            assert (await client.get(url)).json() == original.json()


@pytest.mark.asyncio
async def test_focused_whitespace_is_a_sanitized_objective_field_error(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            invalid = draft()
            invalid["objective_text"] = " \t\n"
            response = await client.post(
                "/api/v1/engagements",
                json=invalid,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert response.status_code == 422
            assert {"field": "objective_text", "code": "INVALID_VALUE"} in response.json()["error"][
                "field_errors"
            ]
            assert "synthetic" not in response.text.lower()


@pytest.mark.asyncio
async def test_constraint_uuid_and_html_are_persisted_as_inert_data(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            body = draft()
            body["objective_text"] = "Verifică <script>window.synthetic=1</script> 😀"
            body["objective_constraints"] = [
                {
                    "id": str(uuid4()),
                    "kind": "EXCLUDE_FEATURE",
                    "text": "Nu încărca HTML executabil",
                    "operation_refs": [],
                }
            ]
            created = await client.post(
                "/api/v1/engagements",
                json=body,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert created.status_code == 201
            assert created.json()["payload"] == body
            assert created.headers["content-type"].startswith("application/json")
            assert created.headers["x-content-type-options"] == "nosniff"
            read = await client.get(f"/api/v1/engagements/{created.json()['engagement_id']}")
            assert read.status_code == 200 and read.json() == created.json()


@pytest.mark.asyncio
async def test_invalid_unicode_is_rejected_as_a_sanitized_field_error(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            invalid = draft()
            invalid["objective_text"] = "\ud800"
            response = await client.post(
                "/api/v1/engagements",
                content=json.dumps(invalid, ensure_ascii=True).encode("ascii"),
                headers={
                    "origin": ORIGIN,
                    "x-csrf-token": csrf,
                    "content-type": "application/json",
                },
            )
            assert response.status_code == 422
            assert {"field": "objective_text", "code": "INVALID_VALUE"} in response.json()["error"][
                "field_errors"
            ]
            assert "ud800" not in response.text.lower()


@pytest.mark.asyncio
async def test_full_default_and_maximum_focused_objective_are_saved_without_truncation(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            full = draft()
            full["assessment_mode"] = "FULL_ASSESSMENT"
            full["objective_text"] = ""
            response = await client.post(
                "/api/v1/engagements",
                json=full,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert response.status_code == 201
            assert response.json()["payload"]["objective_text"] == (
                "Evaluează suprafața Web/API autorizată în limitele profilului selectat."
            )
            maximum = draft()
            maximum["objective_text"] = "😀" * 8192
            saved = await client.post(
                "/api/v1/engagements",
                json=maximum,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert saved.status_code == 201
            assert saved.json()["payload"]["objective_text"] == maximum["objective_text"]
            too_long = draft()
            too_long["objective_text"] = "😀" * 8193
            denied = await client.post(
                "/api/v1/engagements",
                json=too_long,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert denied.status_code == 422
            assert {"field": "objective_text", "code": "TOO_LONG"} in denied.json()["error"][
                "field_errors"
            ]


@pytest.mark.asyncio
async def test_list_uses_bounded_keyset_pagination_and_rejects_foreign_queries(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            created_ids = set()
            for index in range(3):
                body = draft()
                body["name"] = f"Synthetic case {index}"
                created = await client.post(
                    "/api/v1/engagements",
                    json=body,
                    headers={"origin": ORIGIN, "x-csrf-token": csrf},
                )
                assert created.status_code == 201
                created_ids.add(created.json()["engagement_id"])
            seen: list[str] = []
            cursor: str | None = None
            for index in range(3):
                url = "/api/v1/engagements?limit=1"
                if cursor is not None:
                    url += f"&after={cursor}"
                page = await client.get(url)
                assert page.status_code == 200
                result = page.json()
                assert len(result["items"]) == 1
                seen.append(result["items"][0]["engagement_id"])
                assert result["has_more"] is (index < 2)
                cursor = result["next_page"]
            assert seen == sorted(created_ids)
            assert cursor is None
            for url in (
                "/api/v1/engagements?limit=51",
                "/api/v1/engagements?after=not-a-uuid",
            ):
                denied = await client.get(url)
                assert denied.status_code == 422
                assert denied.json()["error"]["field_errors"]
            for url in (
                "/api/v1/engagements?limit=1&limit=2",
                "/api/v1/engagements?secret=synthetic_marker",
                "/api/session?limit=1",
            ):
                denied = await client.get(url)
                assert denied.status_code == 400
                assert denied.json()["error"]["code"] == "QUERY_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_create_preserves_host_origin_session_csrf_and_pairing_body_limit(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            valid = draft()
            assert (await client.get("/api/v1/engagements")).status_code == 401
            assert (
                await client.post("/api/v1/engagements", json=valid, headers={"origin": ORIGIN})
            ).status_code == 401
            csrf = await pair_session(app, client)
            for headers, status in (
                ({"x-csrf-token": csrf}, 403),
                ({"origin": "http://attacker.invalid", "x-csrf-token": csrf}, 403),
                ({"origin": ORIGIN, "host": "attacker.invalid", "x-csrf-token": csrf}, 400),
                ({"origin": ORIGIN}, 403),
            ):
                denied = await client.post("/api/v1/engagements", json=valid, headers=headers)
                assert denied.status_code == status
            oversized = await client.post(
                "/api/v1/engagements",
                content=b"x" * 1048577,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert oversized.status_code == 413
            pairing_oversized = await client.post(
                "/api/pairing",
                content=b"x" * 4097,
                headers={"origin": ORIGIN},
            )
            assert pairing_oversized.status_code == 413
            missing = await client.get(f"/api/v1/engagements/{uuid4()}")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_bad_authorization_start_is_a_field_error_not_a_server_failure(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            invalid = draft()
            authorization = invalid["authorization"]
            assert isinstance(authorization, dict)
            authorization["valid_from"] = "synthetic_invalid_window"
            denied = await client.post(
                "/api/v1/engagements",
                json=invalid,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert denied.status_code == 422
            assert {"field": "authorization.valid_from", "code": "INVALID_VALUE"} in denied.json()[
                "error"
            ]["field_errors"]
            assert "synthetic_invalid_window" not in denied.text


@pytest.mark.asyncio
async def test_revision_is_immutable_in_postgresql_after_save(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            saved = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert saved.status_code == 201
            revision_id = saved.json()["id"]
            digest = saved.json()["digest"]
        with connect_test_database(migrated_database_url) as connection:
            with pytest.raises(psycopg.Error, match="Engagement revisions are immutable"):
                connection.execute(
                    "UPDATE engagement_revision SET digest = %s WHERE id = %s",
                    ("a" * 64, revision_id),
                )
            connection.rollback()
            assert connection.execute(
                "SELECT digest FROM engagement_revision WHERE id = %s", (revision_id,)
            ).fetchone() == (digest,)


@pytest.mark.asyncio
async def test_malformed_scope_refs_and_extra_fields_never_create_a_draft(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            foreign_profile = draft()
            foreign_profile["workflow_profile_ref"] = {"kind": "package", "id": str(uuid4())}
            hostile_origin = draft()
            hostile_origin["scope"] = [
                {
                    "origin": "https://user@lab.example",
                    "port": 443,
                    "path_prefix": "/api",
                    "exclusions": [],
                    "access": "ATTACKABLE",
                }
            ]
            foreign_operation = draft()
            foreign_operation["objective_constraints"] = [
                {
                    "id": str(uuid4()),
                    "kind": "READ_ONLY",
                    "text": "synthetic",
                    "operation_refs": [{"kind": "operation", "id": str(uuid4())}],
                }
            ]
            extra = draft()
            extra["synthetic_secret_marker"] = "never-reflect"
            backwards_window = draft()
            backwards_window["authorization"] = {
                "owner": "Synthetic operator",
                "statement": "Synthetic only",
                "valid_from": "2030-12-31T00:00:00Z",
                "valid_until": "2030-01-01T00:00:00Z",
            }
            for payload, field in (
                (foreign_profile, "workflow_profile_ref"),
                (hostile_origin, "scope.0.origin"),
                (foreign_operation, "objective_constraints.0.operation_refs"),
                (extra, "body"),
                (backwards_window, "authorization.valid_until"),
            ):
                denied = await client.post(
                    "/api/v1/engagements",
                    json=payload,
                    headers={"origin": ORIGIN, "x-csrf-token": csrf},
                )
                assert denied.status_code == 422
                assert field in {error["field"] for error in denied.json()["error"]["field_errors"]}
                assert "never-reflect" not in denied.text
            malformed = await client.post(
                "/api/v1/engagements",
                content=b"{",
                headers={
                    "origin": ORIGIN,
                    "x-csrf-token": csrf,
                    "content-type": "application/json",
                },
            )
            assert malformed.status_code == 422
            listing = await client.get("/api/v1/engagements")
            assert listing.status_code == 200 and listing.json()["items"] == []


@pytest.mark.asyncio
async def test_new_process_reads_the_committed_revision_exactly(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL, tmp_path: Path
) -> None:
    database_url = migrated_database_url.render_as_string(hide_password=False)
    monkeypatch.setenv("OMNIS_DATABASE_URL", database_url)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            saved = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert saved.status_code == 201
    script = (
        "import asyncio,json,os,sys\n"
        "from uuid import UUID\n"
        "from omnis.core.db import database_engine\n"
        "from omnis.modules.engagements.service import EngagementService\n"
        "async def read():\n"
        "    engine=database_engine(os.environ['OMNIS_DATABASE_URL'])\n"
        "    try:\n"
        "        view=await EngagementService(engine).read(UUID(sys.argv[1]))\n"
        "        print(json.dumps(view.model_dump(mode='json'),ensure_ascii=False))\n"
        "    finally:\n"
        "        await engine.dispose()\n"
        "asyncio.run(read())\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, saved.json()["engagement_id"]],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", ""), "OMNIS_DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, "Fresh reader refused persisted draft"
    assert json.loads(result.stdout) == saved.json()


@pytest.mark.asyncio
async def test_nul_in_any_authored_text_is_rejected_before_postgres(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    cases: list[tuple[str, dict[str, object]]] = []
    for field in ("name", "objective_text"):
        payload = draft()
        payload[field] = "reject_me_\x00"
        cases.append((field, payload))
    for field in ("owner", "statement"):
        payload = draft()
        authorization = payload["authorization"]
        assert isinstance(authorization, dict)
        authorization[field] = "reject_me_\x00"
        cases.append((f"authorization.{field}", payload))
    for field in ("origin", "path_prefix", "exclusions"):
        payload = draft()
        scope = payload["scope"]
        assert isinstance(scope, list) and isinstance(scope[0], dict)
        scope[0][field] = ["/reject_me_\x00"] if field == "exclusions" else "reject_me_\x00"
        suffix = ".0" if field == "exclusions" else ""
        cases.append((f"scope.0.{field}{suffix}", payload))
    payload = draft()
    payload["objective_constraints"] = [
        {"id": str(uuid4()), "kind": "READ_ONLY", "text": "reject_me_\x00", "operation_refs": []}
    ]
    cases.append(("objective_constraints.0.text", payload))

    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            for field, invalid in cases:
                response = await client.post(
                    "/api/v1/engagements",
                    json=invalid,
                    headers={"origin": ORIGIN, "x-csrf-token": csrf},
                )
                assert response.status_code == 422, field
                assert field in {
                    error["field"] for error in response.json()["error"]["field_errors"]
                }
                assert "reject_me_" not in response.text
            listing = await client.get("/api/v1/engagements")
            assert listing.status_code == 200 and listing.json()["items"] == []
            accepted = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert accepted.status_code == 201


@pytest.mark.asyncio
async def test_origin_with_empty_port_is_denied_with_a_valid_control(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            invalid = draft()
            scope = invalid["scope"]
            assert isinstance(scope, list) and isinstance(scope[0], dict)
            scope[0]["origin"] = "https://lab.example:"
            response = await client.post(
                "/api/v1/engagements",
                json=invalid,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert response.status_code == 422
            assert {"field": "scope.0.origin", "code": "INVALID_VALUE"} in response.json()["error"][
                "field_errors"
            ]
            accepted = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert accepted.status_code == 201


def test_combined_draft_budget_rejects_the_cartesian_field_maximum() -> None:
    oversized = draft()
    oversized["scope"] = [
        {
            "origin": "https://lab.example",
            "port": 443,
            "path_prefix": "/api",
            "exclusions": ["/" + "x" * 2047 for _ in range(32)],
            "access": "BLOCKED",
        }
        for _ in range(64)
    ]
    with pytest.raises(ValidationError) as caught:
        EngagementDraft.model_validate(oversized)
    assert any(error["type"] == "draft_too_large" for error in caught.value.errors())
    assert EngagementDraft.model_validate(draft()).assessment_mode == "FOCUSED_TEST"


@pytest.mark.asyncio
async def test_large_objective_and_context_roundtrip_within_declared_aggregate_limit(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    payload = draft()
    payload["objective_text"] = "😀" * 8192
    payload["scope"] = [
        {
            "origin": "https://lab.example",
            "port": 443,
            "path_prefix": "/api",
            "exclusions": ["/" + "x" * 2047 for _ in range(32)],
            "access": "BLOCKED",
        }
        for _ in range(8)
    ]
    assert EngagementDraft.model_validate(payload)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            created = await client.post(
                "/api/v1/engagements",
                json=payload,
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert created.status_code == 201
            assert created.json()["payload"] == payload
            read = await client.get(f"/api/v1/engagements/{created.json()['engagement_id']}")
            assert read.status_code == 200 and read.json() == created.json()
            changed = {**payload, "name": "Large context edited"}
            updated = await client.put(
                f"/api/v1/engagements/{created.json()['engagement_id']}",
                json=changed,
                headers={
                    "origin": ORIGIN,
                    "x-csrf-token": csrf,
                    "if-match": created.headers["etag"],
                    "x-command-id": str(uuid4()),
                },
            )
            assert updated.status_code == 200 and updated.json()["payload"] == changed
            assert (
                await client.get(f"/api/v1/engagements/{created.json()['engagement_id']}")
            ).json() == updated.json()


@pytest.mark.asyncio
async def test_aggregate_overflow_within_http_cap_is_a_sanitized_body_error(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    payload = draft()
    entries = [
        {
            "origin": "https://lab.example",
            "port": 443,
            "path_prefix": "/api",
            "exclusions": ["/" + "x" * 2047 for _ in range(32)],
            "access": "BLOCKED",
        }
        for _ in range(16)
    ]
    last_exclusions = entries[-1]["exclusions"]
    assert isinstance(last_exclusions, list)
    entries[-1]["exclusions"] = last_exclusions[:12]
    payload["scope"] = entries
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert 1_000_000 < len(encoded) < 1_048_576
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            denied = await client.post(
                "/api/v1/engagements",
                content=encoded,
                headers={
                    "origin": ORIGIN,
                    "x-csrf-token": csrf,
                    "content-type": "application/json",
                },
            )
            assert denied.status_code == 422
            assert {"field": "body", "code": "TOO_LONG"} in denied.json()["error"]["field_errors"]
            assert "x" * 128 not in denied.text
            listing = await client.get("/api/v1/engagements")
            assert listing.status_code == 200 and listing.json()["items"] == []
            original = await client.post(
                "/api/v1/engagements",
                json=draft(),
                headers={"origin": ORIGIN, "x-csrf-token": csrf},
            )
            assert original.status_code == 201
            url = f"/api/v1/engagements/{original.json()['engagement_id']}"
            headers = {
                "origin": ORIGIN,
                "x-csrf-token": csrf,
                "if-match": original.headers["etag"],
                "x-command-id": str(uuid4()),
            }
            edit_denied = await client.put(
                url,
                content=encoded,
                headers={**headers, "content-type": "application/json"},
            )
            assert edit_denied.status_code == 422
            assert {"field": "body", "code": "TOO_LONG"} in edit_denied.json()["error"][
                "field_errors"
            ]
            wire_denied = await client.put(url, content=b"x" * 1048577, headers=headers)
            assert wire_denied.status_code == 413
            assert (await client.get(url)).json() == original.json()
