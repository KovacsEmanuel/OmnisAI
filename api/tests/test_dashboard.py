"""B03 Dashboard through authenticated HTTP and an attested PostgreSQL snapshot."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection, event
from sqlalchemy.engine import URL
from sqlalchemy.sql import Executable

from conftest import connect_test_database
from omnis.api import create_app
from omnis.modules.engagements.schemas import EngagementDraft
from omnis.modules.engagements.service import canonical_json, revision_digest
from test_engagements import ORIGIN, draft, pair_session


@pytest.mark.asyncio
async def test_dashboard_global_total_keyset_and_no_run(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            csrf = await pair_session(app, client)
            empty = await client.get("/api/v1/dashboard?limit=2")
            assert empty.status_code == 200, empty.text
            value = empty.json()
            assert value["data"]["total_engagements"] == 0
            assert value["data"]["items"] == []
            assert value["has_more"] is False and value["next_page"] is None
            created = []
            for i in range(5):
                response = await client.post(
                    "/api/v1/engagements",
                    json={**draft(), "name": f"Real stored draft {i}"},
                    headers={"origin": ORIGIN, "x-csrf-token": csrf},
                )
                assert response.status_code == 201
                created.append(response.json())
            collected = []
            path = "/api/v1/dashboard?limit=2"
            while True:
                response = await client.get(path)
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "no-store"
                page = response.json()
                assert page["schema_version"] == 1 and page["context"] == "GLOBAL"
                assert page["engagement_id"] is page["run_id"] is None
                assert page["scope_revision_id"] is page["through_cursor"] is None
                assert page["data_state"] == "AVAILABLE"
                assert datetime.fromisoformat(page["as_of"]).tzinfo is not None
                assert page["limit"] == 2
                assert page["data"]["total_engagements"] == 5
                assert page["data"]["active_run"] is None
                assert page["data"]["run_state"] == "NOT_RUN"
                assert page["data"]["attention_state"] == "UNAVAILABLE"
                for metric in page["data"]["metrics"].values():
                    assert metric == {"state": "UNAVAILABLE", "value": None, "reason": "NOT_RUN"}
                assert len(page["data"]["items"]) <= 2
                for item in page["data"]["items"]:
                    assert item["run_id"] is item["through_cursor"] is None
                    assert item["run_state"] == item["stage"] == "NOT_RUN"
                    assert item["scope_revision_id"] == item["id"]
                collected.extend(page["data"]["items"])
                if not page["has_more"]:
                    assert page["next_page"] is None
                    break
                path = f"/api/v1/dashboard?limit=2&after={page['next_page']}"
            assert [item["engagement_id"] for item in collected] == sorted(
                item["engagement_id"] for item in created
            )
            assert len({item["engagement_id"] for item in collected}) == 5
            assert {item["id"] for item in collected} == {item["id"] for item in created}
            token = (await client.get("/api/v1/dashboard?limit=2")).json()["next_page"]
            # A cursor belongs to this query, not a different page size or the B02 list.
            assert (await client.get(f"/api/v1/dashboard?limit=3&after={token}")).status_code == 422
            assert (await client.get(f"/api/v1/engagements?after={token}")).status_code == 422
            assert (
                await client.get(f"/api/v1/dashboard?after={created[0]['engagement_id']}")
            ).status_code == 422


@pytest.mark.asyncio
async def test_dashboard_count_and_page_keep_one_read_only_repeatable_snapshot(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            await pair_session(app, client)
            engine = app.state.db_engine
            assert engine is not None
            states: list[tuple[object, object]] = []
            payload = EngagementDraft.model_validate_json(canonical_json(draft()))
            engagement_id, revision_id = uuid4(), uuid4()
            # Separate real PG connection commits between the count and page reads.
            with connect_test_database(migrated_database_url) as writer:

                def after_count(
                    connection: Connection,
                    clause: Executable,
                    multiparams: object,
                    params: object,
                    options: object,
                    result: object,
                ) -> None:
                    if (
                        "from engagement" not in str(clause).lower()
                        or "total_engagements" not in str(clause)
                        or states
                    ):
                        return
                    states.append(
                        (
                            connection.exec_driver_sql("SHOW transaction_isolation").scalar_one(),
                            connection.exec_driver_sql("SHOW transaction_read_only").scalar_one(),
                        )
                    )
                    writer.execute(
                        "INSERT INTO engagement (id, current_revision) VALUES (%s, 1)",
                        (engagement_id,),
                    )
                    writer.execute(
                        "INSERT INTO engagement_revision "
                        "(id, engagement_id, revision, schema_version, kind, digest, payload) "
                        "VALUES (%s, %s, 1, 1, 'engagement-revision', %s, %s::jsonb)",
                        (
                            revision_id,
                            engagement_id,
                            revision_digest(revision_id, 1, payload),
                            canonical_json(payload.model_dump(mode="json")),
                        ),
                    )
                    writer.commit()

                event.listen(engine.sync_engine, "after_execute", after_count)
                try:
                    response = await client.get("/api/v1/dashboard")
                finally:
                    event.remove(engine.sync_engine, "after_execute", after_count)
            assert response.status_code == 200, response.text
            assert states == [("repeatable read", "on")]
            first = response.json()
            assert first["data"]["total_engagements"] == 0
            assert first["data"]["items"] == []
            assert datetime.fromisoformat(first["as_of"]) <= datetime.now(timezone.utc)
            # Transaction is returned to the pool before HTTP response / another read.
            assert engine.pool.checkedout() == 0
            later = (await client.get("/api/v1/dashboard")).json()
            assert later["data"]["total_engagements"] == 1
            assert later["data"]["items"][0]["engagement_id"] == str(engagement_id)
            assert later["as_of"] >= first["as_of"]


@pytest.mark.asyncio
async def test_dashboard_boundary_query_cookie_host_origin_and_expiry(
    monkeypatch: pytest.MonkeyPatch, migrated_database_url: URL
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get("/api/v1/dashboard")).status_code == 401
            await pair_session(app, client)
            for query, status in [
                ("limit=0", 422),
                ("limit=51", 422),
                ("limit=bad", 422),
                ("after=not-a-cursor", 422),
                ("limit=2&limit=3", 400),
                ("foreign=synthetic_marker", 400),
                ("limit", 400),
                ("after=" + "x" * 257, 400),
            ]:
                response = await client.get("/api/v1/dashboard?" + query)
                assert response.status_code == status, (query, response.text)
                assert "synthetic_marker" not in response.text
            assert (
                await client.get("/api/v1/dashboard", headers={"host": "evil.example"})
            ).status_code == 400
            assert (
                await client.get("/api/v1/dashboard", headers={"origin": "http://evil.example"})
            ).status_code == 403
            assert (
                await client.get(
                    "/api/v1/dashboard", headers={"cookie": "omnis_session=bad; omnis_session=bad"}
                )
            ).status_code == 401
            assert (await client.get("/api/pairing?limit=2")).status_code == 400
            assert (await client.get("/api/session?limit=2")).status_code == 400
            assert (await client.get("/api/v1/dashboard?limit=50")).status_code == 200
            with connect_test_database(migrated_database_url) as connection:
                connection.execute(
                    "UPDATE ui_session SET expires_at = clock_timestamp() - interval '1 second'"
                )
            assert (await client.get("/api/v1/dashboard")).status_code == 401


@pytest.mark.asyncio
async def test_dashboard_unavailable_does_not_leak_or_bypass_missing_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMNIS_DATABASE_URL", raising=False)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (await client.get("/api/v1/dashboard")).status_code == 401
            response = await client.get(
                "/api/v1/dashboard", headers={"cookie": "omnis_session=synthetic_marker"}
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "CONTROL_UNAVAILABLE"
            assert "synthetic_marker" not in response.text
            assert UUID(response.json()["error"]["correlation_id"])
