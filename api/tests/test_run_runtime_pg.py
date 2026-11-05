"""S1 PG/API owner journey, collected only until parent admits real-consumer QA.

The original journey scripts SDK replies and relay ACKs for owner/SQL/API proof.
The opt-in physical-control test below uses the real SDK, sender and host relay
with a programmed local TLS peer: fault injection, never provider inference.
"""

import asyncio
import importlib
import json
import os
import socket as network_socket
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime, timedelta
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
    RunEvent,
    RunSummary,
    Setup,
    UsageSummary,
)
from omnis.modules.runs.run_runtime import AgentRunOwner
from omnis.modules.settings.provider_catalog_models import CatalogControl, CatalogModel, CatalogView
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

S1_CATALOG_PAGE = {
    "data": [
        {
            "id": model,
            "top_provider": {"max_completion_tokens": 4096},
            "supported_parameters": ["max_tokens"],
        }
        for model in ("fixture/s1", "fixture/s1-recon")
    ],
    "total_count": 2,
}


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
    metadata_calls: list[bytes] = []
    decisions = 0
    worker_results = 0
    ui = os.environ.get("OMNIS_S1_RUN_UI") == "1"
    expected_decisions = 5 if needs_you else 4
    expected_calls = expected_decisions + 6
    expected_result_activations = expected_decisions - 1 - int(needs_you)

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
        if request.method == b"GET" and request.url.target == b"/api/v1/models?offset=0&limit=1000":
            assert ui and not raw and not metadata_calls
            metadata_calls.append(request.url.target)
            return httpcore.Response(
                200,
                headers=[(b"content-type", b"application/json")],
                content=Body(S1_CATALOG_PAGE),
            )
        assert request.method == b"POST" and request.url.target == b"/api/v1/chat/completions"
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
            "run_event": 11 + expected_decisions + int(needs_you) + expected_result_activations,
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
            events = [
                RunEvent.model_validate_json(json.dumps(raw))
                for raw in (await db.execute(text("SELECT payload FROM run_event"))).scalars()
            ]
            assert {
                kind: sum(event.kind == kind for event in events)
                for kind in {e.kind for e in events}
            } == {
                "started": 1,
                "decision": expected_decisions,
                "tool_called": 4,
                "tool_result": 3,
                "result": 3,
                "control": int(needs_you) + expected_result_activations,
            }
            activations = [
                event
                for event in events
                if event.summary == "Brain activated from retained results"
            ]
            assert len(activations) == expected_result_activations
            assert {event.attempt_id for event in activations} == {
                actor.attempt_id
                for actor in actors.values()
                if actor.role == "BRAIN"
                and any(ref.kind == "run-result-v1" for ref in actor.input_refs)
            }
            for event in activations:
                assert event.kind == "control" and event.attempt_id is not None
                brain = actors[event.attempt_id]
                assert event.task_id == brain.task_id and event.run_id == brain.run_id
                assert event.refs == brain.input_refs and event.call_id is None
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
        if ui:
            # UI search needs the owned request/result pair, not the RUN-only result seed.
            catalog_command_id = str(uuid4())
            await model_owner.catalog_handle(
                CatalogControl.model_validate(
                    {
                        "op": "provider_catalog",
                        "request": {
                            "action": "refresh",
                            "command_id": catalog_command_id,
                            "connection_id": connection_id,
                            "connection_revision": 1,
                        },
                    }
                )
            )
            async with asyncio.timeout(15):
                while model_owner.tasks:
                    await asyncio.sleep(0.01)
            assert not model_owner.settlement_failed and not sender.transport.backend.relay.failed
            cached_catalog = CatalogView.model_validate(
                await model_owner.catalog_handle(
                    CatalogControl.model_validate(
                        {
                            "op": "provider_catalog",
                            "request": {
                                "action": "search",
                                "connection_id": connection_id,
                                "connection_revision": 1,
                            },
                        }
                    )
                )
            )
            assert cached_catalog.catalog_command_id == catalog_command_id
            assert cached_catalog.connection_id == connection_id
            assert cached_catalog.connection_revision == 1
            assert cached_catalog.state == "READY" and cached_catalog.reason is None
            assert cached_catalog.total == 2 and cached_catalog.next_offset is None
            assert cached_catalog.entries == [
                CatalogModel(model=model, max_output_tokens=4096, supports_max_tokens=True)
                for model in ("fixture/s1", "fixture/s1-recon")
            ]
            assert metadata_calls == [b"/api/v1/models?offset=0&limit=1000"] and not sink_calls
        else:
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
                            CatalogModel(
                                model=model, max_output_tokens=4096, supports_max_tokens=True
                            )
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
                assert len(metadata_calls) == 1
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
@pytest.mark.skipif(
    os.environ.get("OMNIS_S1_RUN_PHYSICAL") != "1",
    reason="Explicit reviewed physical-control target; includes a real 300s operation",
)
@pytest.mark.parametrize("scenario", ["stop", "pause", "hold", "owner_loss", "deadline"])
async def test_run_physical_control_pg(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    """Real SDK/PG/UDS/relay/TLS, programmed local peer, never live inference.

    Linearization: SENT commits before OPEN; Stop/Pause commit their run fence
    before FENCE/DRAIN; only real ACKs permit DRAINED/final readback. The owner-loss
    barrier is before OPEN, outside admission/Settings locks, never inside WRITE.
    """
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.schemas import ControlRequest
    from omnis.modules.runs.run_contract import RunControl
    from omnis.supervisor.model_relay import CipherStream
    from omnis.supervisor.model_relay_protocol import Scope
    from omnis.transport import local_control
    from test_model_test_v2 import tls_contexts

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "cli/src"))
    start_relay = importlib.import_module("omnis_cli.forwarder").start_auth_forwarder
    server_context, client_context = tls_contexts(tmp_path)
    relay_directory = ipc_directory / "r"
    socket_path = relay_directory / "model-egress.sock"
    assert len(bytes(socket_path)) <= 107
    relay = server = run_owner = sender = None
    peers: list[asyncio.Task[None]] = []
    received: list[int] = []
    responses: list[int] = []
    frame_sizes: list[tuple[int, int]] = []
    upstream: list[network_socket.socket] = []
    handed: list[int] = []
    opens: list[tuple[Scope, str]] = []
    fences: list[tuple[Scope, float, str, int]] = []
    acks: list[tuple[str, Scope, float]] = []
    phase = "positive"
    entered = asyncio.Event()
    release_open = asyncio.Event()
    loop = asyncio.get_running_loop()
    original_connect = loop.sock_connect
    original_send = network_socket.socket.send
    original_decode = local_control.decode_control_frame

    def decode_frame(frame: bytes) -> ControlRequest:
        result = original_decode(frame)
        if isinstance(result.command, RunControl):
            command_size = len(result.command.model_dump_json().encode())
            assert command_size <= 3600 and len(frame) <= 4096
            frame_sizes.append((command_size, len(frame)))
        return result

    monkeypatch.setattr(local_control, "decode_control_frame", decode_frame)

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

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        peers.append(task)
        peer_phase = phase
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            assert header.split(b"\r\n", 1)[0] == b"POST /api/v1/chat/completions HTTP/1.1"
            lengths = [
                line.split(b":", 1)[1].strip()
                for line in header.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            ]
            assert len(lengths) == 1 and 0 < int(lengths[0]) <= 32768
            raw = await reader.readexactly(int(lengths[0]))
            received.append(len(raw))
            body = json.loads(raw)
            assert body["model"] == "fixture/s1" and body["max_tokens"] == 1024
            assert body["provider"] == {"allow_fallbacks": False, "require_parameters": True}
            if peer_phase in {"stop", "pause", "deadline"}:
                # Incomplete response with progress defeats the 15s idle timeout,
                # not the unmodified absolute 300s owner deadline.
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 131072\r\n\r\n "
                )
                await writer.drain()
                responses.append(1)
                entered.set()
                for _ in range(330):
                    try:
                        assert await asyncio.wait_for(reader.read(1), 1) == b""
                        return
                    except TimeoutError:
                        writer.write(b" ")
                        await writer.drain()
                        responses[-1] += 1
                raise AssertionError("Owner did not close the incomplete TLS response")
            message: dict[str, object] = {"role": "assistant"}
            finish = "stop"
            if body.get("tools") and body["messages"][-1]["role"] != "tool":
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
            elif body.get("tools"):
                tool_result = json.loads(body["messages"][-1]["content"])
                message["content"] = json.dumps(
                    {
                        "summary": "Synthetic physical S1 result",
                        "consumed_refs": [tool_result["ref"]],
                        "gaps": [],
                    }
                )
            else:
                inbox = json.loads(body["messages"][-1]["content"])["inbox"]
                message["content"] = json.dumps(
                    {
                        "action": "delegate"
                        if peer_phase == "positive" and not inbox
                        else "finish",
                        "summary": "Synthetic physical S1 decision",
                        "consumed_refs": [item["ref"] for item in inbox],
                        "detail": "Read the selected inert context only",
                    }
                )
            payload = (
                {"error": {"code": "free_quota_exhausted"}}
                if peer_phase == "hold"
                else {
                    "id": "synthetic-physical-not-provider-live",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body["model"],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                }
            )
            response = json.dumps(payload).encode()
            assert len(response) <= 131072
            responses.append(len(response))
            status = b"429 Too Many Requests" if peer_phase == "hold" else b"200 OK"
            writer.write(
                b"HTTP/1.1 "
                + status
                + b"\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(response)).encode()
                + b"\r\n\r\n"
                + response
            )
            await writer.drain()
            assert await reader.read(1) == b""  # Owner closes each retired dispatch.
        except ConnectionError:
            if peer_phase not in {"stop", "pause", "deadline"}:
                raise
            # Physical FENCE may reset the peer instead of delivering a TLS EOF.
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()

    def local_dns(
        host: str, port: int, family: int = 0, type: int = 0, proto: int = 0, flags: int = 0
    ) -> list[tuple[object, ...]]:
        assert host == "openrouter.ai" and port == 443 and flags == 0
        assert family in (0, network_socket.AF_INET)
        assert type in (0, network_socket.SOCK_STREAM)
        assert proto in (0, network_socket.IPPROTO_TCP)
        return [
            (
                network_socket.AF_INET,
                network_socket.SOCK_STREAM,
                network_socket.IPPROTO_TCP,
                "",
                ("8.8.8.8", 443),
            )
        ]

    async def local_connect(
        sock: network_socket.socket, destination: str | tuple[object, ...]
    ) -> None:
        if sock.family == network_socket.AF_UNIX:
            await original_connect(sock, destination)
        else:
            assert destination == ("8.8.8.8", 443)
            upstream.append(sock)
            await original_connect(sock, address)  # Only the owned loopback TLS peer.

    def observe_send(sock: network_socket.socket, data: bytes, flags: int = 0) -> int:
        size = original_send(sock, data, flags)
        if any(sock is item for item in upstream):
            handed.append(size)
        return size

    lease_acquired = False
    heartbeat: asyncio.Task[None] | None = None
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        service = InstanceService(engine)
        owner = uuid4()
        epoch = await service.acquire(owner)
        lease_acquired = True
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
        relay_directory.mkdir(mode=0o700)
        relay = await start_relay(relay_directory, model=True)
        server = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=server_context)
        address = server.sockets[0].getsockname()
        monkeypatch.setattr(network_socket, "getaddrinfo", local_dns)
        monkeypatch.setattr(loop, "sock_connect", local_connect)
        monkeypatch.setattr(network_socket.socket, "send", observe_send)
        sender = ModelSender(socket_path, client_context)
        model_owner = ApiKeyModelTest(settings, sender)
        catalog, _, publication = await publish_core(engine, tmp_path / "catalog")
        run_owner = AgentRunOwner(model_owner, catalog)
        original_rpc = sender.transport.backend.relay.rpc

        async def observe_rpc(
            action: str,
            scope: Scope,
            connection: str | None = None,
            sequence: int = 0,
            data: bytes = b"",
            size: int = 0,
            timeout: float = 1,
            write_deadline: str | None = None,
            retire_through: int | None = None,
        ) -> tuple[str, bytes]:
            if action == "OPEN":
                assert connection is not None
                opens.append((scope, connection))
                async with engine.connect() as db:
                    assert (
                        await db.scalar(
                            text("SELECT state FROM run_dispatch WHERE dispatch_id=:id"),
                            {"id": scope.id},
                        )
                        == "SENT"
                    )
                if phase == "owner_loss":
                    entered.set()
                    await release_open.wait()  # SENT, no socket opened; no lock held.
            if action == "FENCE":
                fence_started = loop.time()
                async with engine.connect() as db:
                    identity, state, fence = (
                        await db.execute(
                            text(
                                "SELECT r.run_id::text,r.state,r.fence FROM agent_run r JOIN run_dispatch d USING(run_id) WHERE d.dispatch_id=:id"
                            ),
                            {"id": scope.id},
                        )
                    ).one()
                fences.append((scope, fence_started, state, fence))
                if phase in {"stop", "pause"} and state in {"STOPPING", "PAUSING"}:
                    # Read committed fence, then veto through CipherStream before host ACK.
                    active_owner = run_owner
                    assert active_owner is not None and sender is not None
                    prior_wire = sum(handed)
                    stale = CipherStream(
                        sender.transport.backend.relay,
                        opens[-1][1],
                        scope,
                        lambda: active_owner.write_guard(identity, scope),
                    )
                    with pytest.raises(records.ModelConflict) as refused:
                        await stale.send(b"stale-before-fence-ack")
                    assert refused.value.code == "AUTHORITY_DENIED" and sum(handed) == prior_wire
            reply = await original_rpc(
                action,
                scope,
                connection,
                sequence,
                data,
                size,
                timeout,
                write_deadline,
                retire_through,
            )
            if action in {"FENCE", "DRAIN"} and reply[0] == "OK":
                acks.append((action, scope, loop.time()))
            return reply

        monkeypatch.setattr(sender.transport.backend.relay, "rpc", observe_rpc)
        connection_id = str(uuid4())
        choice = {
            "connection_id": connection_id,
            "connection_revision": 1,
            "model": "fixture/s1",
            "output_tokens": 1024,
        }
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
                                "model": "fixture/s1",
                                "output_tokens": 1024,
                            }
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
                        "default": choice,
                        "brain": None,
                        "recon": None,
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
                    entries=[
                        CatalogModel(
                            model="fixture/s1", max_output_tokens=4096, supports_max_tokens=True
                        )
                    ],
                ).model_dump(mode="json"),
            )  # Synthetic capabilities, not provider discovery.
        control_dir = ipc_directory / "control"
        control_dir.mkdir(mode=0o700)
        monkeypatch.setenv("OMNIS_CONTROL_DIR", str(control_dir))
        monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
        sessions = SessionStore(engine)
        await sessions.register(code_digest("s1-physical-pair"), issuance_id=uuid4())
        grant = await sessions.exchange("s1-physical-pair")
        async with LocalControl(control_dir, service, owner, epoch) as control:
            control.agent_run = run_owner.handle
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
                prepared = await http.post(
                    f"/api/v1/engagements/{view['engagement_id']}/run-preflight",
                    json={
                        "command_id": str(uuid4()),
                        "expected_generation": generation,
                        "engagement_id": view["engagement_id"],
                        "draft_ref": {
                            key: view[key] for key in ("kind", "id", "revision", "digest")
                        },
                        "selection_revision": 1,
                        "publication_ref": publication,
                        "synthetic_context": "Owned synthetic physical control fixture",
                        "data_consent": True,
                    },
                    headers=headers,
                )
                assert prepared.status_code == 200, prepared.text
                assert not received and not opens
                start = {
                    "expected_generation": generation,
                    "expected_revision": 1,
                    "setup_ref": prepared.json()["setup_ref"],
                }

                async def summary(identity: str, state: str, seconds: int = 15) -> RunSummary:
                    async with asyncio.timeout(seconds):
                        while True:
                            response = await http.get(f"/api/v1/runs/{identity}/summary")
                            assert response.status_code == 200, response.text
                            value = RunSummary.model_validate_json(response.content)
                            assert run_owner is not None and not run_owner.failed
                            if value.run.state == state and identity not in run_owner.tasks:
                                return value
                            await asyncio.sleep(0.02)

                positive = await http.post(
                    "/api/v1/runs", json={**start, "command_id": str(uuid4())}, headers=headers
                )
                assert positive.status_code == 202, positive.text
                good = await summary(positive.json()["run_id"], "LIMITED")
                assert len(received) == len(opens) == 4 and sum(handed) > 0
                worker = next(item for item in good.attempts if item.role == "RECON")
                inspected = await http.get(
                    f"/api/v1/runs/{good.run.run_id}/attempts/{worker.attempt_id}"
                )
                assert inspected.status_code == 200, inspected.text
                result = AttemptInspection.model_validate_json(inspected.content)
                assert result.result is not None and result.result.state == "SUCCEEDED"
                assert result.result.summary == "Synthetic physical S1 result"
                assert result.result.consumed_refs == [worker.read_receipt_ref]
                assert (
                    result.consumption is not None
                    and result.consumption.consumer_attempt_id is not None
                )
                before = await census()
                reread = await http.get(
                    f"/api/v1/runs/{good.run.run_id}/attempts/{worker.attempt_id}"
                )
                assert reread.status_code == 200
                assert AttemptInspection.model_validate_json(reread.content).model_dump(
                    exclude={"as_of"}
                ) == result.model_dump(exclude={"as_of"})
                assert await census() == before and len(received) == 4

                phase = scenario
                started_mono, started_utc = loop.time(), datetime.now(UTC)
                started = await http.post(
                    "/api/v1/runs", json={**start, "command_id": str(uuid4())}, headers=headers
                )
                assert started.status_code == 202, started.text
                identity = started.json()["run_id"]
                if scenario != "hold":
                    await asyncio.wait_for(entered.wait(), 15)
                else:
                    held = await summary(identity, "HOLD")
                    assert held.run.reason == "PROVIDER_QUOTA"
                scope, stream_id = opens[-1]
                assert len(opens) == 5
                wire_at_fault = (len(received), len(upstream), sum(handed))
                deadline_origin = datetime.fromisoformat(scope.deadline) - timedelta(seconds=300)
                assert 0 <= (deadline_origin - started_utc).total_seconds() < 10
                reserved_mono = started_mono + (deadline_origin - started_utc).total_seconds()
                control_started = loop.time()
                command: dict[str, object] | None = None
                if scenario in {"stop", "pause"}:
                    response = await http.get(f"/api/v1/runs/{identity}/summary")
                    current = RunSummary.model_validate_json(response.content)
                    command = {
                        "action": scenario,
                        "command_id": str(uuid4()),
                        "run_id": identity,
                        "expected_generation": generation,
                        "expected_revision": current.run.revision,
                    }
                    stopped = await http.post(
                        f"/api/v1/runs/{identity}/commands", json=command, headers=headers
                    )
                    assert stopped.status_code == 202, stopped.text
                    end = await summary(identity, "STOPPED" if scenario == "stop" else "PAUSED")
                    first_fence = next(item for item in fences if item[0] == scope)
                    assert first_fence[2:] == (
                        "STOPPING" if scenario == "stop" else "PAUSING",
                        scope.cancel_epoch + 1,
                    )
                    assert control_started <= first_fence[1] and loop.time() - control_started < 10
                    assert end.run.fence == scope.cancel_epoch + 1 and not end.phase_active
                elif scenario == "owner_loss":
                    before = await census()
                    stale_before_loss = await http.post(
                        f"/api/v1/runs/{identity}/commands",
                        json={
                            "action": "stop",
                            "command_id": str(uuid4()),
                            "run_id": identity,
                            "expected_generation": generation,
                            "expected_revision": 999,
                        },
                        headers=headers,
                    )
                    assert stale_before_loss.status_code == 409
                    assert stale_before_loss.json()["error"]["code"] == "REVISION_CONFLICT"
                    assert await census() == before and len(received) == 4
                    heartbeat.cancel()
                    with suppress(asyncio.CancelledError):
                        await heartbeat
                    async with asyncio.timeout(8):
                        while True:
                            async with engine.connect() as db:
                                expired = await db.scalar(
                                    text(
                                        "SELECT expires_at<=clock_timestamp() FROM supervisor_lease WHERE id=1"
                                    )
                                )
                            if expired:
                                break
                            await asyncio.sleep(0.05)
                    # Actual PG lease expiry/takeover, not SIGKILL or a forged clock.
                    owner = uuid4()
                    epoch = await service.acquire(owner)
                    heartbeat = asyncio.create_task(renew())
                    recovered_settings = ProviderSettingsOwner(
                        service, owner, epoch, settings.vault
                    )
                    recovery = AgentRunOwner(ApiKeyModelTest(recovered_settings, sender), catalog)
                    await recovery.recover()
                    old_task = run_owner.tasks[identity]
                    assert not old_task.done()
                    async with engine.connect() as db:
                        assert (
                            await db.scalar(
                                text("SELECT state FROM run_dispatch WHERE dispatch_id=:id"),
                                {"id": scope.id},
                            )
                            == "UNKNOWN"
                        )
                        assert (
                            await db.scalar(
                                text("SELECT payload->>'reason' FROM agent_run WHERE run_id=:id"),
                                {"id": identity},
                            )
                            == "OWNER_LOST"
                        )
                    recovered_rows = await census()
                    old_task.cancel()
                    await asyncio.wait_for(old_task, 3)
                    assert await census() == recovered_rows
                    end = await summary(identity, "NEEDS_RECONCILIATION")
                    assert end.run.reason == "OWNER_LOST" and len(received) == 4
                    assert (len(received), len(upstream), sum(handed)) == wire_at_fault
                    async with engine.connect() as db:
                        assert (
                            await db.scalar(
                                text("SELECT state FROM run_dispatch WHERE dispatch_id=:id"),
                                {"id": scope.id},
                            )
                            == "UNKNOWN"
                        )
                    before = await census()
                    await recovery.recover()
                    assert await census() == before and len(received) == 4
                elif scenario == "deadline":
                    await asyncio.wait_for(asyncio.shield(run_owner.tasks[identity]), 320)
                    end = await summary(identity, "NEEDS_RECONCILIATION", 320)
                    assert end.run.reason == "MODEL_RESPONSE_UNKNOWN"
                    first_fence = next(item for item in fences if item[0] == scope)
                    operation_seconds = first_fence[1] - reserved_mono
                    drain_seconds = (
                        max(t for action, s, t in acks if action == "DRAIN" and s == scope)
                        - first_fence[1]
                    )
                    assert 299.5 <= operation_seconds <= 305
                    assert 0 <= drain_seconds < 10
                    assert 290 <= responses[-1] <= 330
                    print(
                        f"S1_DEADLINE operation_seconds={operation_seconds:.3f} drain_seconds={drain_seconds:.3f}"
                    )

                assert not run_owner.failed and not model_owner.settlement_failed
                assert not sender.transport.backend.relay.failed
                assert {action for action, s, _ in acks if s == scope} == {"FENCE", "DRAIN"}
                async with engine.connect() as db:
                    assert (
                        await db.scalar(
                            text("SELECT state FROM model_relay_authority WHERE id=:id"),
                            {"id": scope.id},
                        )
                        == "DRAINED"
                    )
                    assert (
                        await db.scalar(
                            text(
                                "SELECT count(*) FROM run_dispatch WHERE state IN ('RESERVED','SENT')"
                            )
                        )
                        == 0
                    )
                before, wire_before = await census(), (len(received), len(opens), sum(handed))
                stale_stream = CipherStream(
                    sender.transport.backend.relay,
                    stream_id,
                    scope,
                    lambda: run_owner.write_guard(identity, scope),
                )
                if scenario == "owner_loss":
                    with pytest.raises(ControlConflict) as lost:
                        await stale_stream.send(b"stale-owned-ciphertext")
                    assert lost.value.code.value == "LEASE_LOST"
                else:
                    with pytest.raises(records.ModelConflict) as denied:
                        await stale_stream.send(b"stale-owned-ciphertext")
                    assert denied.value.code == "AUTHORITY_DENIED"
                # Receive-only reads and stale CAS cannot schedule work or mutate any run table.
                for _ in range(3):
                    assert (await http.get(f"/api/v1/runs/{identity}/summary")).status_code == 200
                stale = {
                    "action": "resume",
                    "command_id": str(uuid4()),
                    "run_id": identity,
                    "expected_generation": generation,
                    "expected_revision": 1,
                }
                if scenario != "owner_loss":
                    refused = await http.post(
                        f"/api/v1/runs/{identity}/commands", json=stale, headers=headers
                    )
                    assert refused.status_code == 409, refused.text
                    assert refused.json()["error"]["code"] == "REVISION_CONFLICT"
                assert await census() == before
                assert (len(received), len(opens), sum(handed)) == wire_before
                if scenario in {"hold", "pause"}:
                    # No background task remains; manual Resume alone creates a new dispatch.
                    assert (
                        identity not in run_owner.tasks and identity not in run_owner.continuations
                    )
                    current = (await http.get(f"/api/v1/runs/{identity}/summary")).json()["run"]
                    phase = "resume"
                    resumed = await http.post(
                        f"/api/v1/runs/{identity}/commands",
                        json={
                            **stale,
                            "command_id": str(uuid4()),
                            "expected_revision": current["revision"],
                        },
                        headers=headers,
                    )
                    assert resumed.status_code == 202, resumed.text
                    await summary(identity, "LIMITED")
                    fresh = opens[-1][0]
                    assert len(opens) == 6 and len(received) == 6
                    assert fresh.id != scope.id and fresh.operation_serial > scope.operation_serial
                    assert fresh.cancel_epoch > scope.cancel_epoch
                    async with engine.connect() as db:
                        states = (
                            await db.execute(
                                text(
                                    "SELECT state,count(*) FROM run_dispatch WHERE run_id=:run GROUP BY state ORDER BY state"
                                ),
                                {"run": identity},
                            )
                        ).all()
                        assert [tuple(row) for row in states] == [("SETTLED", 1), ("UNKNOWN", 1)]
                assert frame_sizes and max(received) <= 32768 and max(responses) <= 131072
                await asyncio.wait_for(asyncio.gather(*peers), 3)
                print(
                    f"S1_PHYSICAL scenario={scenario} requests={len(received)} "
                    f"request_max={max(received)} response_max={max(responses)} "
                    f"command_max={max(item[0] for item in frame_sizes)} "
                    f"frame_max={max(item[1] for item in frame_sizes)}"
                )
    finally:
        try:
            if run_owner is not None:
                assert await run_owner.drain()
        finally:
            try:
                try:
                    if sender is not None:
                        await sender.close()
                finally:
                    try:
                        if relay is not None:
                            relay.close()
                            await relay.wait_closed()
                    finally:
                        if server is not None:
                            server.close()
                            server.close_clients()
                        for task in peers:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*peers, return_exceptions=True)
                        if server is not None:
                            await asyncio.wait_for(server.wait_closed(), 3)
            finally:
                try:
                    if heartbeat is not None:
                        heartbeat.cancel()
                        with suppress(asyncio.CancelledError):
                            await heartbeat
                finally:
                    try:
                        if lease_acquired:
                            await service.release(owner, epoch)
                    finally:
                        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["none", "acquire", "owned_status", "open", "vault", "socket", "heartbeat", "release"],
)
async def test_run_physical_cleanup_source(failure: str) -> None:
    """Execute the real setup/finally AST, stopping before any relay/network/DB effect."""
    import __future__

    import ast
    from collections.abc import Awaitable, Callable
    from pathlib import PurePosixPath
    from types import SimpleNamespace
    from typing import cast
    from unittest.mock import AsyncMock, Mock

    tree = ast.parse(Path(__file__).read_bytes())
    consumer = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "test_run_physical_control_pg"
    )
    start = next(
        index + 1
        for index, node in enumerate(consumer.body)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "tls_contexts"
    )
    protected = next(node for node in consumer.body if isinstance(node, ast.Try) and node.finalbody)
    boundary = next(
        index
        for index, node in enumerate(protected.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "relay" for target in node.targets)
    )
    protected.body = (
        protected.body[:boundary]
        + ast.parse("await heartbeat" if failure in {"heartbeat", "release"} else "return").body
    )
    probe = ast.parse("async def probe(): pass")
    function = cast(ast.AsyncFunctionDef, probe.body[0])
    function.body = consumer.body[start:]

    primary = RuntimeError("inert setup/heartbeat failure")
    secondary = RuntimeError("inert release failure")
    engine = Mock(dispose=AsyncMock())
    factory = Mock(return_value=engine)
    service = Mock(
        acquire=AsyncMock(return_value=1),
        owned_status=AsyncMock(return_value=SimpleNamespace(instance_id=uuid4(), generation=0)),
        open=AsyncMock(return_value=1),
        heartbeat=AsyncMock(side_effect=primary),
        release=AsyncMock(side_effect=secondary if failure == "release" else None),
    )
    if failure in {"acquire", "owned_status", "open"}:
        getattr(service, failure).side_effect = primary
    cleanup = Mock()
    cleanup.attach_mock(service.release, "release")
    cleanup.attach_mock(engine.dispose, "dispose")

    class MemoryPath(PurePosixPath):
        def mkdir(self, mode: int) -> None:
            assert mode == 0o700

    path = MemoryPath("/" + "x" * (110 if failure == "socket" else 10))
    namespace = {
        **globals(),
        "migrated_database_url": Mock(),
        "ipc_directory": path,
        "tmp_path": path,
        "monkeypatch": Mock(),
        "local_control": Mock(),
        "database_engine": factory,
        "InstanceService": Mock(return_value=service),
        "ProviderVault": Mock(side_effect=primary if failure == "vault" else None),
        "ProviderSettingsOwner": Mock(),
    }
    exec(
        compile(
            ast.fix_missing_locations(probe),
            __file__,
            "exec",
            flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    run = cast(Callable[[], Awaitable[None]], namespace["probe"])
    before = asyncio.all_tasks()
    try:
        if failure == "none":
            await run()
        else:
            with pytest.raises((AssertionError, RuntimeError)) as caught:
                await run()
            if failure == "socket":
                assert isinstance(caught.value, AssertionError)
            elif failure == "release":
                assert caught.value is secondary and caught.value.__context__ is primary
            else:
                assert caught.value is primary
        pending = asyncio.all_tasks() - before
        observed = [call[0] for call in cleanup.mock_calls]
        print(f"S1_CLEANUP_SOURCE failure={failure} pending={len(pending)} cleanup={observed}")
        assert not pending
        assert factory.call_count == int(failure != "socket")
        assert observed == (
            []
            if failure == "socket"
            else ["dispose"]
            if failure == "acquire"
            else ["release", "dispose"]
        )
        if failure not in {"acquire", "socket"}:
            service.release.assert_awaited_once_with(service.acquire.call_args.args[0], 1)
    finally:
        leaked = asyncio.all_tasks() - before
        for task in leaked:
            task.cancel()
        await asyncio.gather(*leaked, return_exceptions=True)


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
