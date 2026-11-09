"""Real PG/API reader regression; synthetic retained history, never live LLM agents.

Use only the existing test-s1-run-pg migrated private fixture after parent review.
No owner, scheduler, provider, target or new fixture lifecycle is introduced.
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.api import create_app
from omnis.modules.engagements.schemas import EngagementDraft
from omnis.modules.engagements.service import EngagementService
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.run_contract import AgentHistory, AgentPage, Attempt, RunSummary, Setup
from omnis.security.sessions import SessionStore, code_digest
from test_engagements import draft
from test_run_owner_source import fixture_run, fixture_setup_payload


@pytest.mark.asyncio
async def test_run_activity_pg_live_keyset_and_scoped_reciprocal_history(
    migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "OMNIS_DATABASE_URL", migrated_database_url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
    app = create_app()
    async with app.router.lifespan_context(app):
        engine = app.state.db_engine
        initial = await InstanceService(engine).status()
        instance = str(initial.instance_id)
        engagement = await EngagementService(engine).create(EngagementDraft.model_validate(draft()))
        async with engine.begin() as db:
            snapshot = Setup.model_validate(
                {
                    **fixture_setup_payload(),
                    "engagement_id": str(engagement.engagement_id),
                    "draft_ref": {
                        "kind": "engagement-revision",
                        "id": str(engagement.id),
                        "revision": engagement.revision,
                        "digest": engagement.digest,
                    },
                }
            )
            setup_ref = await records.put(
                db, instance, "run-setup-v1", snapshot.model_dump(mode="json")
            )
            await db.execute(
                text(
                    "INSERT INTO run_setup(instance_id,setup_id,engagement_id,draft_id) VALUES (:instance,:setup,:engagement,:draft)"
                ),
                {
                    "instance": instance,
                    "setup": setup_ref.id,
                    "engagement": str(engagement.engagement_id),
                    "draft": str(engagement.id),
                },
            )
            run = fixture_run().model_copy(
                update={
                    "instance_id": instance,
                    "engagement_id": str(engagement.engagement_id),
                    "setup_ref": setup_ref,
                    "revision": 7,
                }
            )
            await store.save_run(db, run, initial=True)
            brain = Attempt(
                instance_id=instance,
                run_id=run.run_id,
                task_id=str(uuid4()),
                attempt_id=str(uuid4()),
                role="BRAIN",
                parent_task_id=None,
                state="RUNNING",
                brief="Retained synthetic Brain",
                input_refs=[],
                input_text="{}",
                instructions="Inert",
                configured_model="fixture/no-dispatch",
                skill_refs=[],
            )
            await store.save_attempt(db, brain, initial=True)
            workers = []
            for index in range(1, 26):
                actor = brain.model_copy(
                    update={
                        "task_id": f"10000000-0000-4000-8000-{index:012d}",
                        "attempt_id": str(uuid4()),
                        "role": "RECON",
                        "parent_task_id": brain.task_id,
                        "state": "SUCCEEDED",
                        "brief": "Retained synthetic worker",
                    }
                )
                await store.save_attempt(db, actor, initial=True)
                workers.append(actor)
            actor = workers[0]
            for kind, call in [
                ("tool_called", "reused"),
                ("tool_result", "reused"),
                ("tool_called", "reused"),
                ("result", "reused"),
                ("tool_result", "orphan"),
                ("tool_called", "missing"),
                ("tool_called", "duplicate-call"),
                ("tool_called", "duplicate-call"),
                ("tool_result", "duplicate-call"),
                ("tool_called", "duplicate-result"),
                ("tool_result", "duplicate-result"),
                ("result", "duplicate-result"),
                ("tool_called", None),
                ("tool_result", None),
                ("result", None),
                ("control", None),
                ("tool_called", "distinct"),
                ("tool_result", "distinct"),
            ]:
                await store.event(
                    db, run, kind, "Synthetic retained event", actor=actor, call_id=call
                )
            await store.event(
                db, run, "tool_called", "Pending Brain call", actor=brain, call_id="reused"
            )
            other_brain = brain.model_copy(
                update={"task_id": str(uuid4()), "attempt_id": str(uuid4()), "state": "FAILED"}
            )
            await store.save_attempt(db, other_brain, initial=True)
            through = await store.event(
                db,
                run,
                "tool_result",
                "Other Brain attempt gap",
                actor=other_brain,
                call_id="reused",
            )
            run = run.model_copy(update={"through_cursor": through})
            await store.save_run(db, run)

        origin = "http://127.0.0.1:8765"
        root = f"/api/v1/runs/{run.run_id}"
        async with AsyncClient(transport=ASGITransport(app=app), base_url=origin) as client:
            for suffix in (
                "agents?limit=20",
                f"agents/{actor.task_id}/events?after={run.run_id}:{actor.task_id}:0",
            ):
                denied = await client.get(f"{root}/{suffix}")
                assert (
                    denied.status_code == 401
                    and denied.json()["error"]["code"] == "UNAUTHENTICATED"
                )
            sessions = SessionStore(engine)
            await sessions.register(code_digest("s1-activity-synthetic"), issuance_id=uuid4())
            grant = await sessions.exchange("s1-activity-synthetic")
            client.cookies.set("omnis_session", grant.token)

            first_response = await client.get(f"{root}/agents?limit=20")
            assert first_response.status_code == 200
            first = AgentPage.model_validate_json(first_response.content)
            assert len(first.agents) == 20 and first.has_more and first.next_after
            assert first.agents[0].agent_id == "brain" and first.agents[0].attempts == 2
            async with engine.begin() as db:
                # Same storage shape as ordinary read_context activity, without changing membership.
                await store.event(
                    db, run, "tool_called", "read_context", actor=brain, call_id="activity"
                )
                through = await store.event(
                    db, run, "tool_result", "Context read", actor=brain, call_id="activity"
                )
                run = run.model_copy(update={"revision": 8, "through_cursor": through})
                await store.save_run(db, run)
            second_response = await client.get(
                f"{root}/agents", params={"after": first.next_after, "limit": 20}
            )
            assert second_response.status_code == 200
            second = AgentPage.model_validate_json(second_response.content)
            ids = [a.agent_id for a in first.agents + second.agents]
            assert len(ids) == len(set(ids)) == 26 and not second.has_more and second.revision == 8
            repeated = await client.get(
                f"{root}/agents", params={"after": first.next_after, "limit": 20}
            )
            assert (
                repeated.status_code == 200
                and AgentPage.model_validate_json(repeated.content).agents == second.agents
            )

            async with engine.begin() as db:
                earlier = actor.model_copy(
                    update={
                        "task_id": "00000000-0000-4000-8000-000000000001",
                        "attempt_id": str(uuid4()),
                    }
                )
                await store.save_attempt(db, earlier, initial=True)
                run = run.model_copy(update={"revision": 9})
                await store.save_run(db, run)
            continued = await client.get(
                f"{root}/agents", params={"after": first.next_after, "limit": 20}
            )
            assert continued.status_code == 200
            continued_page = AgentPage.model_validate_json(continued.content)
            assert continued_page.agents == second.agents and continued_page.revision == 9
            refreshed = await client.get(f"{root}/agents?limit=20")
            assert refreshed.status_code == 200
            assert earlier.task_id in [
                a.agent_id for a in AgentPage.model_validate_json(refreshed.content).agents
            ]
            metrics = await client.get(f"{root}/summary")
            assert (
                metrics.status_code == 200
                and RunSummary.model_validate_json(metrics.content).metrics.agents == 27
            )
            for cursor in (
                f"{uuid4()}:7:brain",
                f"{run.run_id}:7:{uuid4()}",
                f"{run.run_id}:07:brain",
            ):
                denied = await client.get(f"{root}/agents", params={"after": cursor})
                assert (
                    denied.status_code == 422 and denied.json()["error"]["code"] == "CURSOR_DENIED"
                )

            history_url = f"{root}/agents/{actor.task_id}/events"
            response = await client.get(
                history_url, params={"after": f"{run.run_id}:{actor.task_id}:0", "limit": 3}
            )
            assert response.status_code == 200
            left = AgentHistory.model_validate_json(response.content)
            assert left.has_more and [(e.sequence, e.paired_sequence) for e in left.events] == [
                (1, 2),
                (2, 1),
                (3, 4),
            ]
            response = await client.get(
                history_url, params={"after": f"{run.run_id}:{actor.task_id}:3", "limit": 50}
            )
            assert response.status_code == 200
            right = AgentHistory.model_validate_json(response.content)
            assert right.events[0].pairing == "MATCHED" and right.events[0].paired_sequence == 3
            assert not right.has_more and right.through_cursor == 18
            by_sequence = {e.sequence: e for e in left.events + right.events}
            for sequence in range(5, 15):
                assert (
                    by_sequence[sequence].pairing == "UNMATCHED"
                    and by_sequence[sequence].paired_sequence is None
                )
            direct = by_sequence[15]
            assert direct.kind == "result" and direct.call_id is None
            assert direct.pairing == "NOT_APPLICABLE" and direct.paired_sequence is None
            assert by_sequence[16].pairing == "NOT_APPLICABLE"
            assert by_sequence[17].paired_sequence == 18 and by_sequence[18].paired_sequence == 17
            brain_response = await client.get(
                f"{root}/agents/brain/events?after={run.run_id}:brain:0"
            )
            assert brain_response.status_code == 200
            brain_events = AgentHistory.model_validate_json(brain_response.content).events
            assert [(e.sequence, e.pairing, e.paired_sequence) for e in brain_events[:2]] == [
                (19, "PENDING", None),
                (20, "UNMATCHED", None),
            ]
            denied = await client.get(history_url, params={"after": f"{run.run_id}:brain:0"})
            assert denied.status_code == 422 and denied.json()["error"]["code"] == "CURSOR_DENIED"
            denied = await client.get(f"{root}/agents/{uuid4()}/events?after={run.run_id}:brain:0")
            assert denied.status_code == 422
            denied = await client.get(f"{root}/agents/{uuid4()}/events")
            assert denied.status_code == 404
            async with engine.connect() as db:
                assert (
                    await db.scalar(
                        text(
                            "SELECT count(*) FROM run_dispatch WHERE instance_id=:instance AND run_id=:run"
                        ),
                        {"instance": instance, "run": run.run_id},
                    )
                    == 0
                )
