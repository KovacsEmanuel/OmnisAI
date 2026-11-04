"""S1 PG/API owner journey, collected only until parent admits real-consumer QA.

Uses the existing disposable PG and private control fixtures. SDK replies and
physical relay ACK are explicitly scripted: this proves owner/SQL/API causality,
not provider inference, network confinement or physical Stop.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import httpcore
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.core.run_schema import RUN_COLUMNS
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_store as records
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.run_contract import (
    Attempt,
    AttemptInspection,
    RunSummary,
    Setup,
    UsageSummary,
)
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.provider_catalog_models import CatalogModel
from omnis.modules.settings.provider_catalog_runtime import CatalogResult
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_model_models import ModelRegistryControl
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.security.sessions import SessionStore, code_digest
from omnis.supervisor.model_sender import ModelSender
from omnis.transport.local_control import LocalControl
from test_agent_core_publication import publish_core
from test_engagements import draft


@pytest.mark.asyncio
@pytest.mark.parametrize("needs_you", [False, True])
async def test_run_api_pg_three_causal_tasks_and_receive_only_replay(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    needs_you: bool,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    initial = await service.owned_status(owner, epoch)
    generation = await service.open(uuid4(), initial.generation, owner, epoch)

    async def renew() -> None:
        while True:
            await asyncio.sleep(0.5)
            await service.heartbeat(owner, epoch)

    heartbeat = asyncio.create_task(renew())
    vault, key = tmp_path / "vault", tmp_path / "key"
    vault.mkdir(mode=0o700)
    key.mkdir(mode=0o700)
    settings = ProviderSettingsOwner(
        service, owner, epoch, ProviderVault(vault, key, str(initial.instance_id))
    )
    sender = ModelSender(ipc_directory / "unused-egress")
    model_owner = ApiKeyModelTest(settings, sender)
    run_owner = None
    sink_calls: list[bytes] = []
    decisions = 0
    worker_results = 0
    ui = os.environ.get("OMNIS_S1_RUN_UI") == "1"
    expected_decisions = 5 if needs_you else 4
    expected_calls = expected_decisions + 6

    async def drain_scripted(*, recovery: bool = False) -> None:
        # Only this test bypasses physical ACK. Never used by installed startup.
        async with engine.begin() as db:
            _, scopes = await records.relay_pending(db, str(initial.instance_id))
            for scope in scopes:
                await records.retire_relay(db, scope)

    monkeypatch.setattr(model_owner, "retire_relay", drain_scripted)

    class Body:
        def __init__(self, value: object) -> None:
            self.raw = json.dumps(value).encode()

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield self.raw

        async def aclose(self) -> None:
            return None

    async def sink(request: httpcore.Request) -> httpcore.Response:
        nonlocal decisions, worker_results
        assert isinstance(request.stream, AsyncIterable)
        raw = b"".join([part async for part in request.stream])
        sink_calls.append(raw)
        body = json.loads(raw)
        message: dict[str, object] = {"role": "assistant"}
        finish = "stop"
        if body.get("tools"):
            assert body["model"] == "fixture/s1-recon"
            if body["messages"][-1]["role"] != "tool":
                finish = "tool_calls"
                message.update(
                    content=None,
                    tool_calls=[
                        {
                            "id": str(uuid4()),
                            "type": "function",
                            "function": {"name": "read_context", "arguments": "{}"},
                        }
                    ],
                )
            else:
                tool = json.loads(body["messages"][-1]["content"])
                worker_results += 1
                final = json.dumps(
                    {
                        "summary": f"Synthetic result {worker_results}",
                        "consumed_refs": [tool["ref"]],
                        "gaps": [],
                    }
                )
                if worker_results == 1:
                    finish = "tool_calls"
                    message.update(
                        content=None,
                        tool_calls=[
                            {
                                "id": str(uuid4()),
                                "type": "function",
                                "function": {"name": "finish", "arguments": final},
                            }
                        ],
                    )
                else:
                    message["content"] = final
        else:
            assert body["model"] == "fixture/s1"
            decisions += 1
            input_value = json.loads(body["messages"][-1]["content"])
            consumed = [item["ref"] for item in input_value["inbox"]]
            assert len(consumed) == (0 if decisions == 1 else 1)
            message["content"] = json.dumps(
                {
                    "action": "ask"
                    if needs_you and decisions == 1
                    else "delegate"
                    if worker_results < 3
                    else "finish",
                    "summary": "Consume exact stored result",
                    "consumed_refs": consumed,
                    "detail": f"Read selected inert context for causal task {decisions}",
                }
            )
        return httpcore.Response(
            200,
            headers=[(b"content-type", b"application/json")],
            content=Body(
                {
                    "id": str(uuid4()),
                    "object": "chat.completion",
                    "created": 0,
                    "model": body["model"],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                }
            ),
        )

    monkeypatch.setattr(sender.transport.pool, "handle_async_request", sink)

    async def census() -> dict[str, tuple[object, ...]]:
        values = {}
        async with engine.connect() as db:
            for table in (*RUN_COLUMNS, "model_record_v2", "model_relay_authority"):
                row = (
                    await db.execute(
                        text(
                            f"SELECT count(*),md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'')) FROM {table} t"
                        )
                    )
                ).one()
                values[table] = tuple(row)
        return values

    def totals(calls: int) -> dict[str, object]:
        return {
            "dispatches": calls,
            "unobserved_dispatches": 0,
            **{
                name: {
                    "value": str(per_call * calls),
                    "observed_dispatches": calls,
                    "state": "OBSERVED",
                }
                for name, per_call in (
                    ("input_tokens", 10),
                    ("output_tokens", 10),
                    ("total_tokens", 20),
                )
            },
            **{
                name: {"value": None, "observed_dispatches": 0, "state": "UNKNOWN"}
                for name in (
                    "cached_tokens",
                    "reasoning_tokens",
                    "cache_creation_tokens",
                    "cost_observed",
                )
            },
        }

    def assert_usage(value: UsageSummary, role_calls: dict[str, int], scope: str) -> None:
        assert value.scope == scope and value.accounting_policy == "MONITOR"
        assert value.totals.model_dump() == totals(sum(role_calls.values()))
        assert len(value.roles) == len(role_calls)
        assert {item.role: item.model_dump() for item in value.roles} == {
            role: {
                "role": role,
                "configured_model": "fixture/s1" if role == "BRAIN" else "fixture/s1-recon",
                "connection_id": connection_id,
                "connection_revision": 1,
                "totals": totals(calls),
            }
            for role, calls in role_calls.items()
        }

    async def assert_checkpoint(current_owner: AgentRunOwner) -> None:
        if current_owner.tasks:
            await asyncio.wait_for(asyncio.gather(*tuple(current_owner.tasks.values())), 2)
        counts = {
            "run_setup": 1,
            "agent_run": 1,
            "run_task": expected_decisions + 3,
            "run_attempt": expected_decisions + 3,
            "run_dispatch": expected_calls,
            "run_dispatch_event": expected_calls * 3,
            "run_inbox": 3 + int(needs_you),
            "run_question": int(needs_you),
            "run_event_counter": 1,
            "run_event": 11 + expected_decisions + int(needs_you),
            "run_command": 2 + int(needs_you),
        }
        assert set(counts) == set(RUN_COLUMNS)
        async with engine.connect() as db:
            for table, count in counts.items():
                assert await db.scalar(text(f"SELECT count(*) FROM {table}")) == count, table
            for table, predicate in (
                ("run_dispatch", "state IN ('RESERVED','SENT','UNKNOWN')"),
                ("run_inbox", "consumed_decision_id IS NULL OR held"),
                ("run_attempt", "state IN ('RUNNING','NEEDS_RECONCILIATION')"),
                ("run_question", "state<>'CONSUMED'"),
                ("model_relay_authority", "state='ACTIVE'"),
            ):
                assert (
                    await db.scalar(text(f"SELECT count(*) FROM {table} WHERE {predicate}")) == 0
                ), table
            assert await db.scalar(text("SELECT state FROM agent_run")) == "LIMITED"
            assert (
                await db.scalar(
                    text(
                        "SELECT count(*) FROM run_attempt WHERE role='RECON' AND state='SUCCEEDED'"
                    )
                )
                == 3
            )
            assert await db.scalar(
                text("SELECT (payload->>'through_cursor')::bigint FROM agent_run")
            ) == await db.scalar(text("SELECT max(sequence) FROM run_event"))
            for kind, count in {
                "run-context-v1": 1,
                "run-composition-v1": 2,
                "run-setup-v1": 1,
                "run-step-v1": expected_calls,
                "run-usage-v2": expected_calls,
                "run-tool-result-v1": 3,
                "run-result-v1": 3,
                "run-decision-v2": expected_decisions,
                "run-answer-v1": int(needs_you),
                "run-late-response-v1": 0,
            }.items():
                assert (
                    await db.scalar(
                        text("SELECT count(*) FROM model_record_v2 WHERE kind=:kind"),
                        {"kind": kind},
                    )
                    == count
                ), kind
            assert {
                row[0]: row[1]
                for row in (
                    await db.execute(
                        text(
                            "SELECT payload->>'summary',count(*) FROM run_event "
                            "WHERE payload->>'kind'='tool_called' GROUP BY payload->>'summary'"
                        )
                    )
                ).all()
            } == {"read_context": 3, "finish": 1}
            actors = {
                actor.attempt_id: actor
                for raw in (await db.execute(text("SELECT payload FROM run_attempt"))).scalars()
                for actor in [Attempt.model_validate(raw)]
            }
            workers = [actor for actor in actors.values() if actor.role == "RECON"]
            assert len(workers) == len({actor.task_id for actor in workers}) == 3
            assert len({actor.attempt_id for actor in workers}) == 3
            identity = str(await db.scalar(text("SELECT run_id FROM agent_run")))
            reference = Ref.model_validate(
                await db.scalar(text("SELECT payload->'setup_ref' FROM agent_run"))
            )
            snapshot = Setup.model_validate_json(
                json.dumps(
                    await records.resolve(db, str(initial.instance_id), reference, "run-setup-v1")
                )
            )
            retained = {}
            for actor in actors.values():
                assert actor.run_id == identity and actor.instance_id == str(initial.instance_id)
                assert actor.state == "SUCCEEDED" and actor.result_ref is not None
                raw_result = await records.resolve(
                    db, actor.instance_id, actor.result_ref, actor.result_ref.kind
                )
                assert actor.result_ref.digest == records.digest(raw_result)
                retained[actor.attempt_id] = raw_result
            for config, model in (
                (snapshot.brain, "fixture/s1"),
                (snapshot.recon, "fixture/s1-recon"),
            ):
                assert config.choice.model_dump() == {
                    "connection_id": connection_id,
                    "connection_revision": 1,
                    "model": model,
                    "output_tokens": 1024,
                }
                assert config.connection.connection_id == connection_id
                assert config.connection.revision == 1
                capabilities = CatalogResult.model_validate(
                    await records.resolve(
                        db, str(initial.instance_id), config.capabilities_ref, "catalog-result"
                    )
                )
                assert capabilities.connection == config.connection
                assert capabilities.state == "READY"
                assert {entry.model for entry in capabilities.entries} == {
                    "fixture/s1",
                    "fixture/s1-recon",
                }

        before = await census()
        previous: dict[str, object] | None = None
        # New HTTP clients/connections read the same rows; this is not a process restart.
        app = create_app()
        app.state.db_engine = engine
        for _ in range(2):
            observed: dict[str, object] = {}
            inspections: dict[str, AttemptInspection] = {}
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
            ) as http:
                http.cookies.set("omnis_session", grant.token)
                selected = await http.get("/api/v1/settings/providers")
                assert selected.status_code == 200, selected.text
                selection = selected.json()["selection"]
                assert snapshot.selection_snapshot.model_dump(mode="json") == selection
                assert snapshot.selection_revision == selection["revision"]
                assert selection["default"] == snapshot.brain.choice.model_dump(mode="json")
                assert selection["brain"] is None
                assert selection["recon"] == snapshot.recon.choice.model_dump(mode="json")
                observed["selection"] = selected.json()
                response = await http.get(f"/api/v1/runs/{identity}/summary")
                assert response.status_code == 200, response.text
                summary = RunSummary.model_validate_json(response.content)
                assert summary.run.state == "LIMITED" and summary.run.setup_ref == reference
                assert not summary.has_more and summary.owner_live and not summary.phase_active
                assert {actor.attempt_id: actor for actor in summary.attempts} == actors
                assert_usage(summary.usage, {"BRAIN": expected_decisions, "RECON": 6}, "RUN")
                if needs_you:
                    assert summary.question is not None and summary.question.state == "CONSUMED"
                else:
                    assert summary.question is None
                summary_json = response.json()
                summary_json.pop("as_of")
                observed["summary"] = summary_json
                for actor in summary.attempts:
                    response = await http.get(
                        f"/api/v1/runs/{identity}/attempts/{actor.attempt_id}"
                    )
                    assert response.status_code == 200, response.text
                    inspected = AttemptInspection.model_validate_json(response.content)
                    inspections[actor.attempt_id] = inspected
                    assert {key: getattr(inspected, key) for key in Attempt.model_fields} == {
                        key: getattr(actor, key) for key in Attempt.model_fields
                    }
                    expected_model = "fixture/s1-recon" if actor.role == "RECON" else "fixture/s1"
                    assert actor.configured_model == actor.observed_model == expected_model
                    calls = 2 if actor.role == "RECON" else 1
                    assert inspected.usage is not None
                    assert_usage(inspected.usage, {actor.role: calls}, "ATTEMPT")
                    assert not inspected.dispatches_has_more and len(inspected.dispatches) == calls
                    assert len({item.dispatch_id for item in inspected.dispatches}) == calls
                    for dispatch in inspected.dispatches:
                        usage = dispatch.usage
                        assert dispatch.state == "SETTLED" and usage is not None
                        assert dispatch.usage_ref is not None
                        assert dispatch.usage_ref.kind == "run-usage-v2"
                        assert dispatch.usage_ref.digest == records.digest(
                            usage.model_dump(mode="json")
                        )
                        assert dispatch.reserved_at is not None and dispatch.sent_at is not None
                        assert dispatch.settled_at is not None
                        assert dispatch.reserved_at <= dispatch.sent_at <= dispatch.settled_at
                        assert (
                            usage.instance_id,
                            usage.run_id,
                            usage.task_id,
                            usage.attempt_id,
                            usage.dispatch_id,
                            usage.role,
                        ) == (
                            actor.instance_id,
                            identity,
                            actor.task_id,
                            actor.attempt_id,
                            dispatch.dispatch_id,
                            actor.role,
                        )
                        assert usage.configured_model == usage.observed_model == expected_model
                        assert (
                            usage.connection_id == connection_id and usage.connection_revision == 1
                        )
                        assert usage.reported.model_dump() == {
                            "prompt_tokens": 10,
                            "completion_tokens": 10,
                            "total_tokens": 20,
                            "input_tokens": None,
                            "output_tokens": None,
                            "cached_tokens": None,
                            "reasoning_tokens": None,
                            "cache_read_input_tokens": None,
                            "cache_creation_input_tokens": None,
                            "cost": None,
                            "prompt_tokens_details": {"cached_tokens": None},
                            "completion_tokens_details": {"reasoning_tokens": None},
                        }
                        assert usage.measures.model_dump() == {
                            "input_tokens": 10,
                            "output_tokens": 10,
                            "total_tokens": 20,
                            "cached_tokens": None,
                            "reasoning_tokens": None,
                            "cache_creation_tokens": None,
                            "cost_observed": None,
                        }
                    if actor.role == "RECON":
                        assert inspected.result is not None and inspected.decision is None
                        assert inspected.decision_completion_kind is None
                        result = inspected.result
                        assert (result.run_id, result.task_id, result.attempt_id) == (
                            identity,
                            actor.task_id,
                            actor.attempt_id,
                        )
                        assert result.model_dump(mode="json") == retained[actor.attempt_id]
                        assert result.completion_kind == (
                            "finish" if result.summary == "Synthetic result 1" else "direct"
                        )
                        assert result.state == "SUCCEEDED" and result.gaps == []
                        assert actor.read_receipt_ref is not None
                        assert result.consumed_refs == [actor.read_receipt_ref]
                        assert result.summary == actor.result_summary
                    else:
                        assert inspected.result is None and inspected.consumption is None
                        assert inspected.decision_completion_kind == "direct"
                        assert inspected.decision is not None
                        assert retained[actor.attempt_id] == {
                            "run_id": identity,
                            "task_id": actor.task_id,
                            "attempt_id": actor.attempt_id,
                            "completion_kind": "direct",
                            "decision": inspected.decision.model_dump(mode="json"),
                        }
                        assert inspected.decision.consumed_refs == actor.input_refs
                    inspection_json = response.json()
                    inspection_json.pop("as_of")
                    observed[actor.attempt_id] = inspection_json

            assert {inspections[actor.attempt_id].result_summary for actor in workers} == {
                "Synthetic result 1",
                "Synthetic result 2",
                "Synthetic result 3",
            }
            consumers = set()
            for actor in workers:
                consumption = inspections[actor.attempt_id].consumption
                assert consumption is not None and not consumption.held
                assert consumption.consumer_attempt_id is not None
                brain = inspections[consumption.consumer_attempt_id]
                consumers.add(brain.attempt_id)
                assert brain.role == "BRAIN" and brain.decision is not None
                assert brain.result_ref == consumption.decision_ref
                assert brain.decision.consumed_refs == [actor.result_ref]
                assert brain.decision.action == (
                    "finish" if actor.result_summary == "Synthetic result 3" else "delegate"
                )
            assert len(consumers) == 3
            assert sorted(
                item.decision.action for item in inspections.values() if item.decision is not None
            ) == sorted(
                ["delegate", "delegate", "delegate", "finish"] + (["ask"] if needs_you else [])
            )
            if previous is not None:
                assert observed == previous
            previous = observed
            assert await census() == before and len(sink_calls) == expected_calls

    try:
        catalog, _, publication = await publish_core(engine, tmp_path / "catalog")
        connection_id = str(uuid4())
        await settings.handle(
            KeySettingsControl.model_validate(
                {
                    "op": "provider_settings",
                    "request": {
                        "action": "save_connection",
                        "command_id": str(uuid4()),
                        "connection_id": connection_id,
                        "expected_revision": 0,
                        "provider": "openrouter",
                        "secret": "synthetic-s1-not-a-key",
                    },
                }
            )
        )
        await settings.handle(
            ModelRegistryControl.model_validate(
                {
                    "op": "provider_models",
                    "request": {
                        "action": "save_models",
                        "command_id": str(uuid4()),
                        "expected_registry_revision": 0,
                        "connection_id": connection_id,
                        "connection_revision": 1,
                        "models": [
                            {
                                "entry_id": str(uuid4()),
                                "expected_revision": 0,
                                "model": model,
                                "output_tokens": 1024,
                            }
                            for model in ("fixture/s1", "fixture/s1-recon")
                        ],
                    },
                }
            )
        )
        await settings.handle(
            KeySettingsControl.model_validate(
                {
                    "op": "provider_settings",
                    "request": {
                        "action": "save_selection_v2",
                        "command_id": str(uuid4()),
                        "expected_revision": 0,
                        "default": {
                            "connection_id": connection_id,
                            "connection_revision": 1,
                            "model": "fixture/s1",
                            "output_tokens": 1024,
                        },
                        "brain": None,
                        "recon": None
                        if ui
                        else {
                            "connection_id": connection_id,
                            "connection_revision": 1,
                            "model": "fixture/s1-recon",
                            "output_tokens": 1024,
                        },
                        "investigator": None,
                        "validator": None,
                    },
                }
            )
        )
        async with engine.begin() as db:
            connection = await settings.require_connection(db, connection_id, 1)
            await records.put(
                db,
                str(initial.instance_id),
                "catalog-result",
                CatalogResult(
                    command_id=str(uuid4()),
                    connection=connection,
                    state="READY",
                    reason=None,
                    # Synthetic capabilities, not provider discovery or inference.
                    entries=[
                        CatalogModel(model=model, max_output_tokens=4096, supports_max_tokens=True)
                        for model in ("fixture/s1", "fixture/s1-recon")
                    ],
                ).model_dump(mode="json"),
            )
        run_owner = AgentRunOwner(model_owner, catalog)
        control_dir = ipc_directory / "control"
        control_dir.mkdir(mode=0o700)
        monkeypatch.setenv("OMNIS_CONTROL_DIR", str(control_dir))
        monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
        sessions = SessionStore(engine)
        await sessions.register(code_digest("s1-synthetic-pair"), issuance_id=uuid4())
        grant = await sessions.exchange("s1-synthetic-pair")
        async with LocalControl(control_dir, service, owner, epoch) as control:
            control.agent_run = run_owner.handle
            control.model_test = model_owner.handle
            control.provider_catalog = model_owner.catalog_handle

            async def provider(
                command: KeySettingsControl | ModelRegistryControl,
            ) -> dict[str, object]:
                return (await settings.handle(command)).model_dump(mode="json")

            control.provider_settings = provider
            if ui:
                assert needs_you, "Browser target requires the Needs you journey"
                from test_web_e2e import settings_models_browser

                output = tmp_path / "s1-browser"
                output.mkdir(mode=0o700)
                await settings_models_browser(
                    migrated_database_url, control_dir, output, scenario="s1-run"
                )
                assert worker_results == 3 and decisions == 5 and len(sink_calls) == 11
                await assert_checkpoint(run_owner)
                return
            app = create_app()
            app.state.db_engine = engine
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
            ) as http:
                http.cookies.set("omnis_session", grant.token)
                headers = {"Origin": "http://127.0.0.1:8765", "X-CSRF-Token": grant.csrf}
                created = await http.post("/api/v1/engagements", json=draft(), headers=headers)
                assert created.status_code == 201, created.text
                view = created.json()
                preflight = {
                    "command_id": str(uuid4()),
                    "expected_generation": generation,
                    "engagement_id": view["engagement_id"],
                    "draft_ref": {key: view[key] for key in ("kind", "id", "revision", "digest")},
                    "selection_revision": 1,
                    "publication_ref": publication,
                    "synthetic_context": "Selected synthetic input from normal caller",
                    "data_consent": True,
                }
                publications = await http.get("/api/v1/runs/publications")
                assert publications.status_code == 200 and publication in publications.json()
                prepared = await http.post(
                    f"/api/v1/engagements/{view['engagement_id']}/run-preflight",
                    json=preflight,
                    headers=headers,
                )
                assert prepared.status_code == 200, prepared.text
                assert sink_calls == []
                async with engine.connect() as db:
                    setup = await records.resolve(
                        db,
                        str(initial.instance_id),
                        Ref.model_validate(prepared.json()["setup_ref"]),
                        "run-setup-v1",
                    )
                    assert setup["draft_ref"] == preflight["draft_ref"]
                    selection = await settings.selection(db)
                    assert selection is not None
                    assert setup["selection_snapshot"] == selection.model_dump(mode="json")
                start = {
                    "command_id": str(uuid4()),
                    "expected_generation": generation,
                    "expected_revision": 1,
                    "setup_ref": prepared.json()["setup_ref"],
                }
                started = await http.post("/api/v1/runs", json=start, headers=headers)
                assert started.status_code == 202, started.text
                identity = started.json()["run_id"]
                if needs_you:
                    async with asyncio.timeout(15):
                        while True:
                            pending = (await http.get(f"/api/v1/runs/{identity}/summary")).json()
                            if pending["question"] is not None:
                                break
                            await asyncio.sleep(0.05)
                    assert pending["question"]["state"] == "PENDING" and len(sink_calls) == 1
                    answer = {
                        "action": "answer",
                        "command_id": str(uuid4()),
                        "expected_generation": generation,
                        "expected_revision": pending["run"]["revision"],
                        "run_id": identity,
                        "question_id": pending["question"]["question_id"],
                        "answer": "Synthetic clarification; scope unchanged",
                    }
                    foreign = await http.post(
                        f"/api/v1/runs/{identity}/commands",
                        json={**answer, "question_id": str(uuid4())},
                        headers=headers,
                    )
                    assert foreign.status_code == 409 and len(sink_calls) == 1
                    stale = await http.post(
                        f"/api/v1/runs/{identity}/commands",
                        json={**answer, "expected_revision": 1},
                        headers=headers,
                    )
                    assert stale.status_code == 409 and len(sink_calls) == 1
                    admitted = await http.post(
                        f"/api/v1/runs/{identity}/commands", json=answer, headers=headers
                    )
                    assert admitted.status_code == 202, admitted.text
                    assert (
                        await http.get(f"/api/v1/runs/commands/{answer['command_id']}")
                    ).json() == admitted.json()
                async with asyncio.timeout(15):
                    while True:
                        response = await http.get(f"/api/v1/runs/{identity}/summary")
                        assert response.status_code == 200, response.text
                        if response.json()["run"]["state"] == "LIMITED":
                            break
                        if run_owner.failed:
                            raise AssertionError("Owner step failed")
                        await asyncio.sleep(0.05)
                assert (
                    worker_results == 3
                    and decisions == expected_decisions
                    and len(sink_calls) == expected_calls
                )
                async with engine.connect() as db:
                    tasks = (
                        await db.execute(
                            text(
                                "SELECT task_id,attempt_id,state FROM run_attempt WHERE instance_id=:instance AND run_id=:run AND role='RECON'"
                            ),
                            {"instance": str(initial.instance_id), "run": identity},
                        )
                    ).all()
                    assert (
                        len(tasks) == 3
                        and len({row[0] for row in tasks}) == 3
                        and len({row[1] for row in tasks}) == 3
                    )
                    assert all(row[2] == "SUCCEEDED" for row in tasks)
                    assert await db.scalar(
                        text(
                            "SELECT count(*) FROM run_inbox WHERE run_id=:run AND consumed_decision_id IS NOT NULL"
                        ),
                        {"run": identity},
                    ) == (4 if needs_you else 3)
                # Exercise physical root/snapshot immutability against actual producer rows.
                async with engine.connect() as db:
                    for sql in (
                        "UPDATE agent_run SET setup_id=gen_random_uuid() WHERE run_id=:run",
                        "UPDATE agent_run SET payload=jsonb_set(payload,'{generation}','999') WHERE run_id=:run",
                        "UPDATE run_setup SET draft_id=gen_random_uuid() WHERE setup_id=(SELECT setup_id FROM agent_run WHERE run_id=:run)",
                        "UPDATE model_record_v2 SET payload='{}'::jsonb WHERE id=(SELECT setup_id FROM agent_run WHERE run_id=:run)",
                        "UPDATE run_task SET role='BRAIN' WHERE run_id=:run AND role='RECON'",
                    ):
                        with pytest.raises(DBAPIError):
                            async with db.begin_nested():
                                await db.execute(text(sql), {"run": identity})

                async with engine.connect() as db:
                    for sql, denial_params in (
                        (
                            "UPDATE run_attempt SET instance_id=:foreign WHERE run_id=:run",
                            {"foreign": str(uuid4()), "run": identity},
                        ),
                        (
                            "UPDATE run_dispatch SET task_id=:foreign WHERE run_id=:run",
                            {"foreign": str(uuid4()), "run": identity},
                        ),
                    ):
                        with pytest.raises(DBAPIError) as refused:
                            async with db.begin_nested():
                                await db.execute(text(sql), denial_params)
                        assert getattr(refused.value.orig, "sqlstate", None) == "23503"
                    with pytest.raises(DBAPIError) as overlap:
                        async with db.begin_nested():
                            await db.execute(
                                text(
                                    "UPDATE run_attempt SET state='NEEDS_RECONCILIATION',payload=jsonb_set(payload,'{state}','\"NEEDS_RECONCILIATION\"') WHERE attempt_id=:id"
                                ),
                                {"id": tasks[0][1]},
                            )
                            await db.execute(
                                text(
                                    "UPDATE run_attempt SET state='RUNNING',payload=jsonb_set(payload,'{state}','\"RUNNING\"') WHERE attempt_id=:id"
                                ),
                                {"id": tasks[1][1]},
                            )
                    assert getattr(overlap.value.orig, "sqlstate", None) == "23505"

                before_readback = await census()
                replay = await http.post("/api/v1/runs", json=start, headers=headers)
                assert replay.json() == started.json()
                conflict = await http.post(
                    "/api/v1/runs",
                    json={**start, "expected_generation": generation + 1},
                    headers=headers,
                )
                assert conflict.status_code == 409
                # Keyset pages use only committed events; no GET schedules work.
                cursor = None
                sequences: list[int] = []
                while True:
                    params: dict[str, str | int] = {"limit": 2}
                    if cursor is not None:
                        params["after"] = cursor
                    page = (await http.get(f"/api/v1/runs/{identity}/events", params=params)).json()
                    sequences.extend(item["sequence"] for item in page["events"])
                    if not page["has_more"]:
                        break
                    assert page["events"]
                    cursor = f"{identity}:{page['through_cursor']}"
                assert sequences == sorted(set(sequences)) and len(sequences) > 6
                denied_cursor = await http.get(
                    f"/api/v1/runs/{identity}/events", params={"after": f"{uuid4()}:1"}
                )
                assert denied_cursor.status_code == 422
                await assert_checkpoint(run_owner)
                assert await census() == before_readback
    finally:
        try:
            if run_owner is not None:
                await run_owner.drain()
            await sender.close()
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            try:
                await service.release(owner, epoch)
            finally:
                await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [False, True])
async def test_run_migration_exact_readiness_negative_controls(
    empty_database_url: URL, previous: bool
) -> None:
    import subprocess
    import sys

    from omnis.core.run_schema import run_schema_matches

    root = Path(__file__).resolve().parents[1]
    for revision in (
        ("0018_model_relay_authority", "0019_agent_runs") if previous else ("0019_agent_runs",)
    ):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "alembic",
                "-c",
                str(root / "alembic.ini"),
                "upgrade",
                revision,
            ],
            cwd=root,
            env={
                "PATH": os.environ["PATH"],
                "HOME": os.environ["HOME"],
                "TMPDIR": os.environ["TMPDIR"],
                "OMNIS_DATABASE_URL": empty_database_url.render_as_string(hide_password=False),
            },
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            revision,
            result.returncode,
            result.stderr.decode(errors="replace"),
        )
    engine = database_engine(empty_database_url.render_as_string(hide_password=False))
    try:
        async with engine.connect() as db:
            assert await run_schema_matches(db)
            for attack in (
                "ALTER TABLE run_setup DISABLE TRIGGER run_no_change",
                "CREATE TABLE run_event_shadow () INHERITS (run_event)",
                "ALTER TABLE run_task DROP CONSTRAINT run_task_role_check; ALTER TABLE run_task ADD CHECK (true)",
                "DROP INDEX run_attempt_one_worker; CREATE UNIQUE INDEX run_attempt_one_worker ON run_attempt(instance_id,run_id) WHERE role='RECON' AND state='RUNNING'",
                "CREATE OR REPLACE FUNCTION public.run_root_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$BEGIN RETURN NEW; END;$$",
            ):
                transaction = await db.begin_nested()
                try:
                    await db.execute(text(attack))
                    assert not await run_schema_matches(db), attack
                finally:
                    await transaction.rollback()
                assert await run_schema_matches(db)
    finally:
        await engine.dispose()
