"""Bounded real owner/storage consumer; synthetic setup, no SDK/provider dispatch.

Run only through the existing test-s1-run-pg private-fixture gate after review.
"""

import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine
from omnis.modules.engagements.schemas import EngagementDraft
from omnis.modules.engagements.service import EngagementService
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_store as records
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.run_contract import BrainDecision, RunControl, RunView, Setup, WorkerFinal
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.supervisor.model_relay_protocol import Scope
from test_engagements import draft
from test_run_owner_source import fixture_setup_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("clarify", [False, True])
async def test_run_stagnation_pg_retains_progress_across_owner_recreation(
    migrated_database_url: URL, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clarify: bool
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner_id = uuid4()
    epoch = await service.acquire(owner_id)
    initial = await service.owned_status(owner_id, epoch)
    generation = await service.open(uuid4(), initial.generation, owner_id, epoch)
    instance = str(initial.instance_id)

    async def renew() -> None:
        while True:
            await asyncio.sleep(0.5)
            await service.heartbeat(owner_id, epoch)

    heartbeat = asyncio.create_task(renew())
    vault, key = tmp_path / "vault", tmp_path / "key"
    vault.mkdir(mode=0o700)
    key.mkdir(mode=0o700)
    settings = ProviderSettingsOwner(service, owner_id, epoch, ProviderVault(vault, key, instance))

    def owner() -> AgentRunOwner:
        # Only the prerequisite setup/DATA and scheduler are synthetic; storage/consumers are real.
        value = object.__new__(AgentRunOwner)
        value.instance, value.settings, value.service = instance, settings, service
        value.closing, value.draining, value.failed = False, False, False
        value.tasks, value.continuations = {}, set()
        monkeypatch.setattr(value, "check_data", AsyncMock())
        monkeypatch.setattr(value, "spawn", lambda identity: None)
        return value

    try:
        engagement = await EngagementService(engine).create(EngagementDraft.model_validate(draft()))
        async with service.admission(generation, owner_id, epoch) as db:
            context_ref = await records.put(
                db,
                instance,
                "run-context-v1",
                {
                    "text": "Frozen synthetic input",
                    "data_policy": "SELECTED_SYNTHETIC_ONLY",
                },
            )
            composition = await records.put(db, instance, "run-composition-v1", {"skill_refs": []})
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
                    "expected_generation": generation,
                    "context_ref": context_ref.model_dump(),
                    "composition_refs": [composition.model_dump(), composition.model_dump()],
                }
            )
            setup_ref = await records.put(
                db, instance, "run-setup-v1", snapshot.model_dump(mode="json")
            )
            await db.execute(
                text(
                    "INSERT INTO run_setup(instance_id,setup_id,engagement_id,draft_id) "
                    "VALUES (:instance,:setup,:engagement,:draft)"
                ),
                {
                    "instance": instance,
                    "setup": setup_ref.id,
                    "engagement": str(engagement.engagement_id),
                    "draft": str(engagement.id),
                },
            )
            run = RunView(
                instance_id=instance,
                run_id=str(uuid4()),
                engagement_id=str(engagement.engagement_id),
                setup_ref=setup_ref,
                revision=1,
                generation=generation,
                owner_id=str(owner_id),
                owner_epoch=epoch,
                fence=1,
                state="RUNNING",
            )
            await store.save_run(db, run, initial=True)
            run = await owner().new_attempt(
                db, run, snapshot, role="BRAIN", brief="First inert task", parent=None
            )
            await store.save_run(db, run)
        run_id = run.run_id
        workers = 0
        clarified = 0
        questions = [
            "Does synthetic label A denote Alice?",
            "Does synthetic label B denote Bob?",
            "Does synthetic label C denote Carol?",
            "Does synthetic label D denote Diana?",
        ]
        expected_stagnation = 0
        for index in range(12):
            runtime = owner()  # No in-memory novelty cache survives a consumer boundary.
            async with service.admission(generation, owner_id, epoch) as db:
                run = await store.run(db, instance, run_id)
                assert run.active_attempt_id is not None
                brain = await store.attempt(db, run, run.active_attempt_id)
                assert brain.role == "BRAIN"
                answer = any(ref.kind == "run-answer-v1" for ref in brain.input_refs)
                expected_stagnation = (
                    0 if workers == 1 or answer else min(3, expected_stagnation + 1)
                )
                asking = (
                    clarify and clarified < len(questions) and (answer or expected_stagnation == 2)
                )
                decision = BrainDecision(
                    action="ask" if asking else "delegate",
                    summary=f"Reworded summary {index}",
                    detail=questions[clarified] if asking else f"Equivalent inert task {index}",
                    consumed_refs=brain.input_refs,
                )
                await runtime.complete(db, run, brain, decision.model_dump_json(), None)
            async with engine.connect() as db:
                run = await store.run(db, instance, run_id)
                assert run.stagnation == expected_stagnation
                if run.state == "LIMITED":
                    assert run.reason == "STAGNATION" and run.active_attempt_id is None
                    assert (
                        await db.scalar(
                            text(
                                "SELECT count(*) FROM run_attempt WHERE run_id=:run AND state='RUNNING'"
                            ),
                            {"run": run_id},
                        )
                        == 0
                    )
                    assert (
                        await db.scalar(
                            text(
                                "SELECT count(*) FROM run_question WHERE run_id=:run AND state<>'CONSUMED'"
                            ),
                            {"run": run_id},
                        )
                        == 0
                    )
                    assert (
                        await db.scalar(
                            text(
                                "SELECT count(*) FROM run_inbox WHERE run_id=:run AND consumed_decision_id IS NULL"
                            ),
                            {"run": run_id},
                        )
                        == 0
                    )
                    assert (
                        await db.scalar(
                            text(
                                "SELECT payload->>'summary' FROM run_event WHERE run_id=:run ORDER BY sequence DESC LIMIT 1"
                            ),
                            {"run": run_id},
                        )
                        == "STAGNATION"
                    )
                    assert await db.scalar(text("SELECT count(*) FROM run_dispatch")) == 0
                    break
                assert run.state == "RUNNING"
            if asking:
                assert run.question_id is not None
                await runtime.handle(
                    RunControl.model_validate(
                        {
                            "op": "agent_run",
                            "request": {
                                "action": "answer",
                                "command_id": str(uuid4()),
                                "run_id": run_id,
                                "expected_generation": generation,
                                "expected_revision": run.revision,
                                "question_id": run.question_id,
                                "answer": "Yes",
                            },
                        }
                    )
                )
                clarified += 1
                continue
            assert run.active_attempt_id is not None
            scope = Scope(
                instance,
                "MODEL_DISPATCH",
                str(uuid4()),
                str(owner_id),
                generation,
                epoch,
                run.fence,
                (datetime.now(UTC) + timedelta(seconds=300)).isoformat(),
                "openrouter",
                1,
            )
            output = await runtime.execute_tool(
                run_id, scope, run.active_attempt_id, snapshot, "read_context", "{}", str(uuid4())
            )
            read_ref = Ref.model_validate(json.loads(output)["ref"])
            await runtime.execute_tool(
                run_id,
                scope,
                run.active_attempt_id,
                snapshot,
                "finish",
                WorkerFinal(
                    summary=f"New result words {index}", consumed_refs=[read_ref], gaps=[]
                ).model_dump_json(),
                str(uuid4()),
            )
            workers += 1
            async with service.admission(generation, owner_id, epoch) as db:
                run = await store.run(db, instance, run_id)
                assert run.reason == "RESULT_READY" and run.active_attempt_id is None
                run = await owner().new_attempt(
                    db, run, snapshot, role="BRAIN", brief="Consume result", parent=None
                )
                await store.save_run(db, run)
                if workers == 1:
                    assert (
                        await db.scalar(
                            text("SELECT count(*) FROM run_task WHERE run_id=:run"), {"run": run_id}
                        )
                        == 3
                    )
        else:
            pytest.fail("Equivalent inert inputs did not reach finite STAGNATION")
        assert clarified == (4 if clarify else 0) and workers == (6 if clarify else 4)
        async with engine.connect() as db:
            readback = await store.run(db, instance, run_id)
            assert readback == run
            answers = (
                await db.execute(
                    text(
                        "SELECT q.payload->>'text', r.payload->>'text' "
                        "FROM run_inbox i JOIN model_record_v2 r "
                        "ON r.instance_id=i.instance_id AND r.id=i.result_id "
                        "JOIN run_question q ON q.instance_id=i.instance_id AND q.run_id=i.run_id "
                        "AND q.question_id::text=r.payload->>'question_id' "
                        "WHERE i.instance_id=:instance AND i.run_id=:run "
                        "AND r.kind='run-answer-v1' AND i.consumed_decision_id IS NOT NULL"
                    ),
                    {"instance": instance, "run": run_id},
                )
            ).all()
            assert len(answers) == clarified
            assert set(answers) == (
                {(question, "Yes") for question in questions} if clarify else set()
            )
            attempts = (
                (
                    await db.execute(
                        text("SELECT payload FROM run_attempt WHERE run_id=:run"), {"run": run_id}
                    )
                )
                .scalars()
                .all()
            )
            assert all(value["state"] == "SUCCEEDED" for value in attempts)
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        try:
            await service.release(owner_id, epoch)
        finally:
            await engine.dispose()
