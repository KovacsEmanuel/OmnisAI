"""Real SOURCE PG admission-data tracer; native identities/transport are a seed.

SQL, qualification, owner/fencing, explicit configuration DATA producer/receipt,
first reader, projection and approval persistence are real. Native runtime,
actual initialization/turn, model compatibility, SDK and inference are not claimed.
"""

import asyncio
import importlib
import json
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Literal, TypedDict
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.engine import URL

from fixtures.b06b_publication.consumer import canonical, mapping, sequence
from fixtures.b06b_pure_probe.consumer import Probe
from fixtures.c03_journey import publish_capture
from fixtures.c03_records import qualify_records
from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlCode, ControlConflict
from omnis.modules.instance.schemas import NativePrepareCommand, NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_dispatch import ModelDispatch
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import load_json
from omnis.policy.model_projection import SyntheticApproval, projection_input
from omnis.supervisor.native_tasks import NativeTaskOwner
from omnis.supervisor.runtime_client import FrozenPreflight, RuntimeClient
from test_managed_contract import stage
from test_model_admission import (
    assert_protocol_budget_accounting,
    assert_protocol_budget_records,
    assert_protocol_failure_records,
    assert_protocol_records,
    protocol_configuration,
    wait_protocol_marker,
)
from test_model_projection import text_digests
from test_native_preparation import command, worker_fixture
from test_ready_model_configuration import configuration

ProtocolCaller = Literal["sender", "second"]
ProtocolPhase = Literal[
    "control",
    "owner",
    "domain.readback",
    "protocol.replay",
    "protocol.reserve",
    "protocol.mark_sent",
    "protocol.settle",
    "protocol.readback",
    "protocol.qualified",
    "dispatch.read",
    "qa.t0_locked",
    "qa.before_a",
]


class ProtocolTimingRow(TypedDict):
    caller: ProtocolCaller
    phase: ProtocolPhase
    entered_ms: int
    elapsed_ms: int
    outcome: Literal["PENDING", "RETURNED", "RAISED"]


@dataclass
class _ProtocolSpan:
    caller: ProtocolCaller
    phase: ProtocolPhase
    started: float
    ended: float | None = None
    outcome: Literal["PENDING", "RETURNED", "RAISED"] = "PENDING"


class ProtocolTiming:
    """First two racing callers or finite caps commands; do NOT sum nested spans.

    No argument/result/error bytes, new tasks, timers or authority. Delegation
    runs in the original task. RAISED includes cancellation, never success.
    """

    def __init__(self) -> None:
        self.handlers: dict[object, ProtocolCaller] = {}
        self.spans: list[_ProtocolSpan] = []

    @contextmanager
    def phase(self, caller: ProtocolCaller, phase: ProtocolPhase) -> Iterator[None]:
        assert len(self.spans) < 64, "protocol timing capacity"
        span = _ProtocolSpan(caller, phase, monotonic())
        self.spans.append(span)
        try:
            yield
        except BaseException:
            span.outcome = "RAISED"
            raise
        else:
            span.outcome = "RETURNED"
        finally:
            span.ended = monotonic()

    def delegate[**P, R](
        self, phase: ProtocolPhase, original: Callable[P, Awaitable[R]]
    ) -> Callable[P, Awaitable[R]]:
        async def measured(*args: P.args, **kwargs: P.kwargs) -> R:
            caller = self.handlers.get(asyncio.current_task())
            if caller is None:
                return await original(*args, **kwargs)
            with self.phase(caller, phase):
                return await original(*args, **kwargs)

        return measured

    def snapshot(self) -> list[ProtocolTimingRow]:
        now = monotonic()
        return [
            {
                "caller": span.caller,
                "phase": span.phase,
                "entered_ms": int(1000 * (span.started - self.spans[0].started)),
                "elapsed_ms": int(
                    1000 * ((now if span.ended is None else span.ended) - span.started)
                ),
                "outcome": span.outcome,
            }
            for span in self.spans
        ]


def report_protocol_failure(
    capsys: pytest.CaptureFixture[str],
    error: BaseException,
    *,
    order: str,
    await_site: str,
    markers: dict[str, asyncio.Event],
    tasks: Mapping[str, asyncio.Task[dict[str, object]] | asyncio.Task[int] | asyncio.Task[None]],
    progress: dict[str, int | float | None],
    timing: ProtocolTiming | None = None,
    source_control: bool = False,
) -> dict[str, object]:
    """One synchronous pre-cleanup snapshot; never format exception/input bytes.

    Names/keys come only from the finite test sites below. Capture is disabled
    ONLY for this sanitized line: pytest --tb=line omits ordinary captured output.
    PENDING means no exception was observed, not a fabricated task failure.
    """

    def failure(exc: BaseException) -> dict[str, object]:
        types = {
            TimeoutError: "TimeoutError",
            asyncio.CancelledError: "CancelledError",
            CatalogError: "CatalogError",
            ControlConflict: "ControlConflict",
            AssertionError: "AssertionError",
            ValueError: "ValueError",
            TypeError: "TypeError",
            RuntimeError: "RuntimeError",
            OSError: "OSError",
        }
        reason: str | None = None
        if type(exc) is CatalogError:
            allowed = {
                "TASK_UNAVAILABLE",
                "TASK_REJECTED",
                "TASK_INDETERMINATE",
                "COMMAND_CONFLICT",
                "CONTROL_TIMEOUT",
                "CONTROL_UNAVAILABLE",
                "LEASE_LOST",
                "INVALID_REQUEST",
            }
            reason = exc.reason if type(exc.reason) is str and exc.reason in allowed else "OTHER"
        elif type(exc) is ControlConflict:
            reason = exc.code.value if type(exc.code) is ControlCode else "OTHER"
        return {"type": types.get(type(exc), "OTHER"), "reason": reason}

    states: dict[str, object] = {}
    for name, task in tasks.items():
        if not task.done():
            states[name] = {"state": "PENDING"}
        elif task.cancelled():
            states[name] = {"state": "CANCELLED"}
        else:
            exc = task.exception()
            states[name] = (
                {"state": "RETURNED"} if exc is None else {"state": "FAILED", **failure(exc)}
            )
    start = progress["readiness_started"]
    end = progress["readiness_finished"]
    snapshot: dict[str, object] = {
        "scope": "SOURCE_CONTROL" if source_control else "PG",
        "order": order,
        "await_site": await_site,
        "error": failure(error),
        "markers": {name: event.is_set() for name, event in markers.items()},
        "tasks": states,
        **{
            key: progress[key]
            for key in (
                "owner_entered",
                "fence_entered",
                "readiness_entered",
                "readiness_completed",
            )
        },
        "readiness_elapsed_ms": (
            None if start is None else int(1000 * ((monotonic() if end is None else end) - start))
        ),
        "timing": [] if timing is None else timing.snapshot(),
    }
    with capsys.disabled():
        print("\nP2_PROTOCOL_FAILURE " + json.dumps(snapshot, sort_keys=True), flush=True)
    return snapshot


def synthetic_decision(owner: str, run: str, composition: dict[str, object]) -> dict[str, object]:
    """Test operator's exact synthetic seed classification; not production policy."""
    model_input = projection_input(
        composition,
        SyntheticApproval(
            owner, run, canonical(records.reference(composition)), text_digests(composition), ()
        ),
    )
    messages = sequence(model_input["messages"])
    system, user = [mapping(load_json(str(mapping(v)["content"]))) for v in messages]
    method = mapping(system["method"])
    texts = [mapping(v)["text"] for v in sequence(system["instructions"])]
    texts.append(method["objective"])
    for raw in sequence(method["requirements"]):
        item = mapping(raw)
        texts.extend([item["key"], item["description"], *sequence(item["step_ids"])])
    texts.extend(mapping(v)["id"] for v in sequence(method["steps"]))
    texts.extend(user[k] for k in ("objective_summary", "hypothesis", "priority_reason"))
    texts.extend(sequence(user["non_goals"]))
    texts.extend(mapping(v)["summary"] for v in sequence(user["context"]))
    digests = sorted({sha256(str(value).encode()).hexdigest() for value in texts})
    assert 1 <= len(digests) <= 32
    return {
        "decision_id": str(uuid4()),
        "composition_ref": records.reference(composition),
        "approved_text_digests": digests,
    }


@pytest.mark.asyncio
async def test_pg_explicit_decision_projection_owner_rollback_replay_and_stop(
    migrated_database_url: URL,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    protocol_mode: bool = False,
    protocol_order: str = "nominal",
    protocol_logs: pytest.LogCaptureFixture | None = None,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    adapter = importlib.import_module("omnis_hermes.model_admission")
    dsn = migrated_database_url.render_as_string(hide_password=False)
    qualified, _ = qualify_records(tmp_path / "qualified-records", dsn)
    seed = qualified.seed
    _, snapshot = publish_capture(qualified, dsn)
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    selected = probe.success(
        "select",
        probe.write(snapshot_ref=snapshot["snapshot_ref"], recipe_key="records-mapper"),
        dsn,
    )
    engine = database_engine(dsn)
    service, supervisor = InstanceService(engine), uuid4()
    done = asyncio.Event()
    heartbeat: asyncio.Task[None] | None = None
    native_calls: list[str] = []

    class NativeProtocolSeed(RuntimeClient):
        """SYNTHETIC_PROTOCOL_SEED_NOT_NATIVE_PROOF; no agent is constructed."""

        async def prepare(
            self,
            service: InstanceService,
            supervisor_owner: UUID,
            bundle_ref: dict[str, object],
            bundle: dict[str, object],
        ) -> dict[str, object]:
            return {"preparation": worker_fixture(bundle)}

        async def managed(
            self,
            service: InstanceService,
            owner: UUID,
            operation: str,
            payload: dict[str, object],
        ) -> dict[str, object]:
            # Exercise CURRENT authority, not a synthetic grant or cached TTL.
            await service.runtime_authority(owner, self.epoch, self.generation, inert_probe=True)
            native_calls.append(operation)
            if operation == "task_stage":
                result = stage(mapping(payload["manifest"]))
                result["protocol"] = payload["protocol"]
                return result
            assert operation == "task_model_preflight"
            body = mapping(mapping(payload["binding"])["payload"])
            return mapping(
                adapter.cold_preflight(
                    payload,
                    native_root_id=body["native_root_id"],
                    native_entries=body["entries"],
                    source_configuration=protocol_configuration(payload),
                )
            )

    async def renew(epoch: int) -> None:
        while not done.is_set():
            await service.heartbeat(supervisor, epoch)
            try:
                await asyncio.wait_for(done.wait(), timeout=0.5)
            except TimeoutError:
                pass

    async def counts() -> tuple[int, int, int]:
        async with engine.connect() as conn:
            values = []
            for kinds in (
                "'model-data-approval'",
                "'model-projection'",
                "'model-budget','model-reservation','model-dispatch','native-turn'",
            ):
                values.append(
                    int(
                        (
                            await conn.execute(
                                sql(
                                    "SELECT count(*) FROM managed_record WHERE owner_id=:owner "
                                    "AND envelope->>'kind' IN (" + kinds + ")"
                                ),
                                {"owner": seed.owner},
                            )
                        ).scalar_one()
                    )
                )
            return values[0], values[1], values[2]

    try:
        epoch = await service.acquire(supervisor)
        status = await service.owned_status(supervisor, epoch)
        heartbeat = asyncio.create_task(renew(epoch))
        runtime = NativeProtocolSeed(seed.directory, generation=status.generation, epoch=epoch)
        runtime.boot = str(uuid4())
        prep = NativePrepareCommand.model_validate(
            {
                **command(),
                "owner_id": seed.owner,
                "instance_id": str(status.instance_id),
                "expected_epoch": epoch,
                "expected_generation": status.generation,
                "selection_ref": selected["selection_ref"],
            }
        )
        await NativePreparation(engine, seed.root, service, supervisor, epoch, runtime).prepare(
            prep
        )
        inputs, domain = ContractInputs(engine, seed.root), ManagedAdmission(engine, seed.root)
        context = await inputs.create_context(
            seed.write(
                schema_version=2,
                selection_ref=selected["selection_ref"],
                preparation_command_id=prep.command_id,
            )
        )
        item = await inputs.create_input(
            seed.write(
                schema_version=2,
                context_ref=context["context_ref"],
                input={
                    "records": [
                        {"method": "GET", "path": "/SYNTHETIC_PRIVATE_I1?q=secret", "status": 200}
                    ]
                },
            )
        )
        request = seed.write(
            schema_version=3,
            selection_ref=selected["selection_ref"],
            preparation_command_id=prep.command_id,
            task_count=1,
            context_ref=context["context_ref"],
            slot_values=[{"slot_name": "records", "refs": [item["input_ref"]]}],
        )
        prepared = await domain.prepare_composed(request)
        manifest = mapping(prepared["manifest"])
        run = str(mapping(manifest["payload"])["run_id"])
        composition = next(
            mapping(v)
            for v in sequence(prepared["records"])
            if mapping(v)["kind"] == "prompt-composition"
        )
        lifecycle: dict[str, object] = {
            "op": "native_task",
            "schema_version": 1,
            "owner_id": seed.owner,
            "command_id": request["command_id"],
            "instance_id": str(status.instance_id),
            "expected_epoch": epoch,
            "expected_generation": status.generation,
            "manifest_ref": prepared["manifest_ref"],
            "action": "stage",
        }
        owner = NativeTaskOwner(domain, service, supervisor, epoch, runtime)
        consumer = ModelDispatch(domain)
        config = configuration()  # explicit SOURCE material, not account/model/turn authority
        if protocol_order == "budget":
            config["technical_caps"] = {"calls": 1, "output_tokens": 64, "wall_seconds": 2}
        configuration_command = NativeTaskCommand.model_validate(
            {**lifecycle, "action": "model_configuration", "configuration": config}
        )
        authority: dict[str, object] = {
            "instance_id": str(status.instance_id),
            "owner": str(supervisor),
            "epoch": epoch,
            "generation": status.generation,
        }

        async def configuration_records() -> list[dict[str, object]]:
            async with engine.connect() as conn:
                rows = (
                    (
                        await conn.execute(
                            sql(
                                "SELECT envelope FROM managed_record WHERE owner_id=:owner AND run_id=:run "
                                "AND (envelope->>'kind'='provider-config' OR "
                                "(envelope->>'kind'='contract-input-command' AND "
                                "envelope->'payload'->>'operation'='model_configuration')) ORDER BY id"
                            ),
                            {"owner": seed.owner, "run": run},
                        )
                    )
                    .scalars()
                    .all()
                )
            return [mapping(row) for row in rows]

        assert await configuration_records() == [] and native_calls == []
        # Real INSERT + immutable command receipt in one transaction, then rollback.
        rollback_source = {**config, "decision_id": str(uuid4())}
        with pytest.raises(RuntimeError, match="OWNED_READY_CONFIGURATION_ROLLBACK"):
            async with service.native_preparation_commit(
                supervisor, epoch, status.generation
            ) as conn:
                await consumer.prepare_ready_configuration(
                    conn, seed.owner, prepared["manifest_ref"], rollback_source, authority
                )
                assert (
                    await conn.execute(
                        sql(
                            "SELECT count(*) FROM managed_record WHERE owner_id=:owner AND run_id=:run "
                            "AND (envelope->>'kind'='provider-config' OR "
                            "(envelope->>'kind'='contract-input-command' AND "
                            "envelope->'payload'->>'operation'='model_configuration'))"
                        ),
                        {"owner": seed.owner, "run": run},
                    )
                ).scalar_one() == 2
                raise RuntimeError("OWNED_READY_CONFIGURATION_ROLLBACK")
        assert await configuration_records() == []

        ready = await owner.handle(configuration_command)
        assert ready["configuration_status"] == "READY"
        assert ready["initialization_status"] == ready["inference_status"] == "HOLD"
        from omnis.policy.ready_model_configuration import initialization_data

        actual_records = await configuration_records()
        assert len(actual_records) == 2
        config_record = next(row for row in actual_records if row["kind"] == "provider-config")
        receipt = next(row for row in actual_records if row["kind"] == "contract-input-command")
        assert ready["provider_config_ref"] == records.reference(config_record)
        assert mapping(config_record["payload"])["configuration"] == config
        assert mapping(config_record["payload"])["inference_authorized"] is False
        assert mapping(receipt["payload"])["command_id"] == config["decision_id"]
        assert mapping(receipt["payload"])["result_refs"] == {
            "provider_config_ref": ready["provider_config_ref"]
        }
        assert str(ready["initialization_data"]).encode() == initialization_data(config)
        assert ready == await owner.handle(configuration_command)
        assert actual_records == await configuration_records()
        # New engine/connection/consumer reads committed JSONB, not caller aliases.
        reader_engine = database_engine(dsn)
        try:
            reader = ModelDispatch(ManagedAdmission(reader_engine, seed.root))
            async with reader_engine.begin() as conn:
                read_configuration = await reader.read_ready_initialization(
                    conn,
                    seed.owner,
                    prepared["manifest_ref"],
                    ready["provider_config_ref"],
                    authority,
                )
            assert read_configuration == initialization_data(config)
            for denied_owner, denied_authority in (
                (str(uuid4()), authority),
                (seed.owner, {**authority, "generation": status.generation + 1}),
            ):
                with pytest.raises(CatalogError):
                    async with reader_engine.begin() as conn:
                        await reader.read_ready_initialization(
                            conn,
                            denied_owner,
                            prepared["manifest_ref"],
                            ready["provider_config_ref"],
                            denied_authority,
                        )
        finally:
            await reader_engine.dispose()
        with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
            await owner.handle(
                NativeTaskCommand.model_validate(
                    {
                        **lifecycle,
                        "action": "model_configuration",
                        "configuration": {**config, "model_id": "CHANGED_EXPLICIT_INPUT"},
                    }
                )
            )
        assert actual_records == await configuration_records()
        assert native_calls == [] and await counts() == (0, 0, 0)

        bound = await owner.handle(NativeTaskCommand.model_validate(lifecycle))
        assert bound["task_status"] == "BOUND"
        with pytest.raises(CatalogError, match="MODEL_CONFIGURATION_REJECTED"):
            await owner.handle(configuration_command)
        assert actual_records == await configuration_records()
        decision = synthetic_decision(seed.owner, run, composition)
        assert await counts() == (0, 0, 0)
        # Real INSERTs followed by rollback, not a mock that never writes.
        with pytest.raises(RuntimeError, match="OWNED_ROLLBACK"):
            async with service.native_preparation_commit(
                supervisor, epoch, status.generation
            ) as conn:
                await consumer.prepare(
                    conn, seed.owner, prepared["manifest_ref"], bound["binding_ref"], decision
                )
                assert (
                    await conn.execute(
                        sql(
                            "SELECT count(*) FROM managed_record WHERE owner_id=:owner "
                            "AND envelope->>'kind' IN ('model-data-approval','model-projection')"
                        ),
                        {"owner": seed.owner},
                    )
                ).scalar_one() == 2
                raise RuntimeError("OWNED_ROLLBACK")
        assert await counts() == (0, 0, 0)
        preflight = NativeTaskCommand.model_validate(
            {**lifecycle, "action": "model_preflight", "data_approval": decision}
        )
        answer = await owner.handle(preflight)
        assert answer == await owner.handle(preflight)
        admission = mapping(answer["model_admission"])
        assert admission["reason"] == "NO_MODEL" and admission["native_turn"] is None
        assert admission["model_calls"] == 0 and await counts() == (1, 1, 0)
        model_context = mapping(admission["model_context"])
        assert model_context["selection_ref"] == selected["selection_ref"]
        assert model_context["purpose"] == "SUPPORT"
        assert model_context["execution_kind"] == "CONTRACT_PROBE"
        assert model_context["resolution"] == "NO_MODEL" and model_context["effective"] is None
        assert mapping(model_context["requested"]) == {
            "model_key": None,
            "effort": None,
            "requirement": "PREFERRED",
            "on_unavailable": "BLOCK",
        }
        # Preserve catalog work_kind; SUPPORT is the execution purpose, not a
        # rewritten label for the published technique.
        from omnis.modules.settings.catalog_models import Manifest
        from omnis.modules.settings.catalog_schema import dto

        authored = dto((seed.package / "omnis.yaml").read_bytes(), Manifest)
        assert model_context["source_work_kind"] == authored.techniques[0].work_kind
        assert native_calls == ["task_stage", "task_model_preflight", "task_model_preflight"]
        for supplied, reason in (
            ({**decision, "approved_text_digests": ["0" * 64]}, "MODEL_DATA_DECISION_CONFLICT"),
            (
                {**decision, "decision_id": str(uuid4()), "approved_text_digests": ["0" * 64]},
                "MODEL_PROJECTION_REJECTED",
            ),
        ):
            with pytest.raises(CatalogError, match=reason):
                await owner.handle(
                    NativeTaskCommand.model_validate(
                        {**lifecycle, "action": "model_preflight", "data_approval": supplied}
                    )
                )
            assert await counts() == (1, 1, 0)
        async with engine.begin() as conn:
            read = await consumer.read(
                conn,
                seed.owner,
                run,
                bound["binding_ref"],
                admission["data_approval_ref"],
                admission["projection_ref"],
            )
        assert b"SYNTHETIC_PRIVATE_I1" not in adapter.validate_preflight(read["payload"])
        assert mapping(read["payload"])["model_context"] == model_context
        # The catalog is append-only. Insert a new, deliberately untrusted
        # selection in the same owned group inside a rolled-back transaction;
        # its valid new Ref must NOT bypass the qualified producer comparison.
        from omnis.modules.runs.pure_probe import PureProbe

        with pytest.raises(RuntimeError, match="OWNED_SELECTION_POISON_ROLLBACK"):
            async with engine.begin() as conn:
                original_selection = mapping(model_context["selection"])
                payload = deepcopy(mapping(original_selection["payload"]))
                payload["requested"] = {
                    **mapping(payload["requested"]),
                    "model_key": "unapproved-model",
                }
                group, _ = await records.get(
                    conn, seed.owner, mapping(model_context["selection_ref"])
                )
                envelope = records.envelope("execution-selection", payload)
                await records.put(conn, seed.owner, group, envelope)
                with pytest.raises(CatalogError, match="SELECTION_MISMATCH"):
                    await PureProbe(engine, seed.root)._selection(
                        conn, seed.owner, records.reference(envelope)
                    )
                raise RuntimeError("OWNED_SELECTION_POISON_ROLLBACK")
        assert await counts() == (1, 1, 0)
        with pytest.raises(CatalogError):
            async with engine.begin() as conn:
                await consumer.read(
                    conn,
                    str(uuid4()),
                    run,
                    bound["binding_ref"],
                    admission["data_approval_ref"],
                    admission["projection_ref"],
                )
        assert await counts() == (1, 1, 0)
        if protocol_mode:
            done.set()
            assert heartbeat is not None
            await heartbeat
            heartbeat = None
            await service.heartbeat(supervisor, epoch)
            await protocol_pg_consumer(
                migrated_database_url,
                owner,
                service,
                lifecycle,
                ready,
                decision,
                consumer,
                monkeypatch,
                protocol_order,
                capsys,
                protocol_logs,
            )
            return
        done.set()
        await heartbeat
        heartbeat = None
        await service.shutdown(uuid4(), status.generation, supervisor, epoch)
        before = list(native_calls)
        with pytest.raises(ControlConflict):
            await owner.handle(preflight)
        assert native_calls == before and await counts() == (1, 1, 0)
        # Receive-only data readback after Stop cannot create turn/reservation/send.
        async with engine.begin() as conn:
            assert read == await consumer.read(
                conn,
                seed.owner,
                run,
                bound["binding_ref"],
                admission["data_approval_ref"],
                admission["projection_ref"],
            )
        assert await counts() == (1, 1, 0)
    finally:
        done.set()
        if heartbeat is not None:
            await heartbeat
        await engine.dispose()


async def protocol_pg_consumer(
    database_url: URL,
    owner: NativeTaskOwner,
    service: InstanceService,
    lifecycle: dict[str, object],
    ready: dict[str, object],
    decision: dict[str, object],
    consumer: ModelDispatch,
    monkeypatch: pytest.MonkeyPatch,
    order: str,
    capsys: pytest.CaptureFixture[str],
    logs: pytest.LogCaptureFixture | None = None,
) -> None:
    """Actual SQL + both UDS; only retained native identity is a synthetic seed.

    Observer C runs its own READ COMMITTED connection immediately inside write,
    then delegates the exact original bytes. No transport method is substituted.
    """
    import json
    import os
    import tempfile
    from collections import Counter
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    import psycopg
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

    from omnis.core.db import ReadinessReason, readiness_reason, validated_database_url
    from omnis.modules.instance.records import InstanceRecord, LeaseRecord
    from omnis.modules.runs import model_protocol
    from omnis.modules.tasks import managed_store
    from omnis.supervisor.native_tasks import control_task
    from omnis.transport import local_control
    from omnis.transport.local_control import LocalControl
    from test_native_task_client import peer_client

    adapter = importlib.import_module("omnis_hermes.model_admission")
    command_value = {
        **lifecycle,
        "action": "model_protocol_prepare",
        "data_approval": decision,
        "provider_config_ref": ready["provider_config_ref"],
        "protocol_id": str(uuid4()),
        "protocol_caps": {
            "calls": 1,
            "output_tokens": 64,
            "wall_seconds": 1 if order == "timeout" else 3,
        },
    }
    command = NativeTaskCommand.model_validate(command_value)
    wire: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    reserved, stop_locked, release_stop = asyncio.Event(), asyncio.Event(), asyncio.Event()
    received, release_ack = asyncio.Event(), asyncio.Event()
    actual_fence, actual_locked = service.native_preparation_commit, service._locked
    fence_count, blocker_pid = 0, 0
    concurrent = order in {"duplicate", "conflict"}
    admission_case = order in {"budget", "budget_conflict", "deadline_b"}
    failure_case = order in {"eof", "timeout", "cancel", "invalid_ack", "late_stop", "data_denials"}
    settle_entered, release_settle = asyncio.Event(), asyncio.Event()
    timeout_produced = asyncio.Event()
    protocol_errors: list[str] = []
    frozen_values: list[FrozenPreflight] = []
    a_pid = 0
    a_open = asyncio.Event()
    t0_ready, release_t0 = asyncio.Event(), asyncio.Event()
    second_finished = asyncio.Event()
    t0_records: list[object] = []
    second_lock_entered, second_lock_acquired = asyncio.Event(), asyncio.Event()
    duplicate_waiter_pid = 0
    second_handler: object = None
    readback_tasks: set[object] = set()
    request_count = 0
    authority_calls = 0
    reserve_calls = 0
    baseline_ids: set[str] = set()
    duplicate_accounting: dict[str, object] = {}
    actual_readback, actual_lock = owner.domain.readback, managed_store.lock
    actual_authority, actual_reserve = service.runtime_authority, model_protocol.reserve
    send_tasks: list[asyncio.Task[dict[str, object]]] = []
    stop_tasks: list[asyncio.Task[int]] = []
    await_site = "sender_start"
    readiness_entered = readiness_completed = 0
    readiness_started: float | None = None
    readiness_finished: float | None = None
    timing = ProtocolTiming()
    failure_reported = False

    # Exact original awaits; only trusted finite names and monotonic spans.
    monkeypatch.setattr(
        model_protocol, "replay", timing.delegate("protocol.replay", model_protocol.replay)
    )
    monkeypatch.setattr(
        model_protocol, "mark_sent", timing.delegate("protocol.mark_sent", model_protocol.mark_sent)
    )
    monkeypatch.setattr(
        model_protocol, "settle", timing.delegate("protocol.settle", model_protocol.settle)
    )
    monkeypatch.setattr(
        model_protocol, "readback", timing.delegate("protocol.readback", model_protocol.readback)
    )
    monkeypatch.setattr(
        model_protocol, "qualified", timing.delegate("protocol.qualified", model_protocol.qualified)
    )

    async def observed_readiness(engine: AsyncEngine | None) -> ReadinessReason | None:
        nonlocal readiness_entered, readiness_completed, readiness_started, readiness_finished
        readiness_entered += 1
        readiness_started, readiness_finished = monotonic(), None
        result = await readiness_reason(engine)
        readiness_completed += 1
        readiness_finished = monotonic()
        return result

    monkeypatch.setattr(local_control, "readiness_reason", observed_readiness)

    def observe(error: BaseException) -> None:
        nonlocal failure_reported
        if failure_reported:
            return
        failure_reported = True
        report_protocol_failure(
            capsys,
            error,
            order=order,
            await_site=await_site,
            markers={
                "t0_ready": t0_ready,
                "reserved": reserved,
                "received": received,
                "stop_locked": stop_locked,
                "second_lock_entered": second_lock_entered,
                "second_lock_acquired": second_lock_acquired,
            },
            tasks={
                **dict(zip(("sender", "second"), send_tasks, strict=False)),
                **dict(zip(("stopper",), stop_tasks, strict=False)),
            },
            progress={
                "owner_entered": request_count,
                "fence_entered": fence_count,
                "readiness_entered": readiness_entered,
                "readiness_completed": readiness_completed,
                "readiness_started": readiness_started,
                "readiness_finished": readiness_finished,
            },
            timing=timing,
        )

    @asynccontextmanager
    async def fenced(who: UUID, epoch: int, generation: int) -> AsyncIterator[AsyncConnection]:
        nonlocal fence_count, blocker_pid, t0_records, a_pid
        fence_count += 1
        current = fence_count
        async with actual_fence(who, epoch, generation) as conn:
            if order == "send_first" and current == 2:
                blocker_pid = int((await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one())
            if order == "deadline_b" and current == 2:
                a_pid = int((await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one())
                a_open.set()
            try:
                yield conn
            finally:
                if order == "deadline_b" and current == 2:
                    a_open.clear()
            if concurrent and current == 1:
                # Product T0 holds Instance/lease/managed/budget locks and has
                # written reserve + command receipt, but has NOT committed.
                with timing.phase("sender", "qa.t0_locked"):
                    blocker_pid = int(
                        (await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one()
                    )
                    t0_records = list(
                        (
                            await conn.execute(
                                sql(
                                    "SELECT to_jsonb(t) FROM managed_record t ORDER BY to_jsonb(t)::text"
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    rows = [mapping(r)["envelope"] for r in t0_records]
                    added = [mapping(r) for r in rows if str(mapping(r)["id"]) not in baseline_ids]
                    assert Counter(str(r["kind"]) for r in added) == {
                        "model-budget": 1,
                        "model-dispatch-owner": 1,
                        "model-reservation": 1,
                        "model-dispatch": 1,
                        "contract-input-command": 1,
                    }
                    t0_ready.set()
                    await asyncio.wait_for(release_t0.wait(), 1.5)
        if current == 1:  # actual RESERVE transaction has committed
            reserved.set()
            if order == "deadline_b":
                # The original public command still bounds this pause. The test
                # acquires its managed blocker only AFTER T0 commits.
                await release_t0.wait()
            if concurrent:
                # Let the actual waiter finish receive-only before A can add
                # SENT; this makes zero writes/send by the second falsifiable.
                with timing.phase("sender", "qa.before_a"):
                    await asyncio.wait_for(second_finished.wait(), 1.5)
            if order == "stop_first":
                await asyncio.wait_for(stop_locked.wait(), 1)

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, InstanceRecord, LeaseRecord]]:
        nonlocal blocker_pid
        async with actual_locked() as row:
            task = asyncio.current_task()
            if order == "stop_first" and task is not None and task.get_name() == "protocol-stop":
                blocker_pid = int(
                    (await row[0].execute(sql("SELECT pg_backend_pid()"))).scalar_one()
                )
                stop_locked.set()
                await asyncio.wait_for(release_stop.wait(), 1.5)
            yield row

    monkeypatch.setattr(service, "native_preparation_commit", fenced)
    monkeypatch.setattr(service, "_locked", locked)

    async def protocol_handle(value: NativeTaskCommand) -> dict[str, object]:
        try:
            return await owner.handle(value)
        except CatalogError as error:
            if admission_case:
                protocol_errors.append(error.reason)
            raise

    async def observed_handle(value: NativeTaskCommand) -> dict[str, object]:
        nonlocal request_count, second_handler
        request_count += 1
        if request_count == 2:
            second_handler = asyncio.current_task()
        if admission_case or request_count <= (2 if concurrent else 1):
            task = asyncio.current_task()
            caller: ProtocolCaller = "second" if concurrent and request_count == 2 else "sender"
            timing.handlers[task] = caller
            try:
                with timing.phase(caller, "owner"):
                    return await protocol_handle(value)
            finally:
                timing.handlers.pop(task)
        return await protocol_handle(value)

    async def observed_readback(value: object) -> dict[str, object]:
        task = asyncio.current_task()
        readback_tasks.add(task)
        try:
            return await actual_readback(value)
        finally:
            readback_tasks.remove(task)

    async def observed_lock(conn: AsyncConnection, who: str) -> None:
        nonlocal duplicate_waiter_pid
        # The initial domain readback, not protocol.replay, takes the first
        # managed lock. Pin THIS connection before delegating the real lock.
        observe = asyncio.current_task() is second_handler and not second_lock_entered.is_set()
        if observe:
            assert asyncio.current_task() in readback_tasks
            duplicate_waiter_pid = int(
                (await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one()
            )
            second_lock_entered.set()
        await actual_lock(conn, who)
        if observe:
            second_lock_acquired.set()

    from omnis.modules.instance.service import RuntimeAuthority

    async def observed_authority(
        who: UUID, epoch: int, generation: int, *, inert_probe: bool = False
    ) -> RuntimeAuthority:
        nonlocal authority_calls
        authority_calls += 1
        return await actual_authority(who, epoch, generation, inert_probe=inert_probe)

    async def observed_reserve(
        conn: AsyncConnection,
        dispatch: ModelDispatch,
        value: NativeTaskCommand,
        prepared: dict[str, object],
        config: dict[str, object],
        frozen: FrozenPreflight,
    ) -> dict[str, object]:
        nonlocal reserve_calls
        reserve_calls += 1
        if order == "deadline_b":
            frozen_values.append(frozen)
        refs = await actual_reserve(conn, dispatch, value, prepared, config, frozen)
        if admission_case:
            from omnis.policy import budgets

            pending = await budgets.readback(conn, value.owner_id, refs["dispatch_ref"])
            assert pending["state"] == "RESERVED" and pending["usage_state"] == "UNKNOWN"
            assert pending["charged_calls"] == 1 and pending["charged_output_tokens"] == 64
        return refs

    monkeypatch.setattr(
        owner.domain, "readback", timing.delegate("domain.readback", observed_readback)
    )
    monkeypatch.setattr(
        model_protocol, "reserve", timing.delegate("protocol.reserve", observed_reserve)
    )
    if concurrent:
        monkeypatch.setattr(managed_store, "lock", observed_lock)
    if concurrent or admission_case or failure_case:
        monkeypatch.setattr(service, "runtime_authority", observed_authority)

    if order == "late_stop":
        actual_settle = model_protocol.settle

        async def late_settle(
            conn: AsyncConnection,
            dispatch: ModelDispatch,
            value: NativeTaskCommand,
            refs: dict[str, object],
            result: object,
        ) -> dict[str, object]:
            # A has unlocked; T2 has not acquired managed/budget locks yet.
            settle_entered.set()
            await release_settle.wait()
            return await actual_settle(conn, dispatch, value, refs, result)

        monkeypatch.setattr(model_protocol, "settle", late_settle)

    def cold(payload: dict[str, object]) -> dict[str, object]:
        body = mapping(mapping(payload["binding"])["payload"])
        result = mapping(
            adapter.cold_preflight(
                payload,
                native_root_id=body["native_root_id"],
                native_entries=body["entries"],
                source_configuration=protocol_configuration(payload),
            )
        )
        return (
            {**result, "extra": "SYNTHETIC_PRIVATE_ACK_ERROR"} if order == "invalid_ack" else result
        )

    dsn = database_url.render_as_string(hide_password=False)
    url = validated_database_url(dsn)
    # Only this attested fixture's existing UDS, no query override or fallback.
    with psycopg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
        connect_timeout=2,
        options="-c statement_timeout=2000",
        autocommit=True,
    ) as observer:

        def census() -> dict[str, list[object]]:
            # Protocol writes only managed_record. Retain complete sorted rows,
            # not just counts, plus lifecycle/revision/catalog neighbours.
            # Stop is outside this comparison; no authority is renewed here.
            return {
                table: [
                    r[0]
                    for r in observer.execute(
                        f"SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text"
                    ).fetchall()
                ]
                for table in (
                    "managed_record",
                    "managed_run",
                    "managed_task",
                    "managed_inbox",
                    "managed_mission_revision",
                    "catalog_record",
                    "catalog_command",
                )
                + (
                    ("instance_control", "supervisor_lease", "instance_command")
                    if failure_case
                    else ()
                )
            }

        before = census() if concurrent or admission_case or failure_case else {}
        settled: dict[str, list[object]] = {}
        baseline_records = [
            mapping(mapping(r)["envelope"]) for r in before.get("managed_record", [])
        ]
        baseline_ids = {str(r["id"]) for r in baseline_records}
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="dapg-") as name:
            root = Path(name)
            async with peer_client(
                root,
                wire,
                result=cold,
                runtime_boot=owner.runtime.boot,
                observed=received,
                reply=order != "eof",
                failure=order if order in {"timeout", "cancel"} else None,
                hold=release_ack if order == "send_first" else None,
            ) as runtime:
                assert runtime.epoch == owner.epoch
                owner.runtime = runtime
                if order == "timeout":
                    from omnis.supervisor.runtime_client import RuntimeUnavailable

                    actual_exchange = runtime.exchange_frozen

                    async def timeout_exchange(frozen: FrozenPreflight) -> dict[str, object]:
                        try:
                            return await actual_exchange(frozen)
                        except RuntimeUnavailable as error:
                            if type(error.__context__) is TimeoutError and received.is_set():
                                timeout_produced.set()
                            raise

                    monkeypatch.setattr(runtime, "exchange_frozen", timeout_exchange)
                writer = runtime.writer
                assert writer is not None
                actual_write = writer.write

                def write(data: bytes) -> None:
                    frame = mapping(load_json(data))
                    rows = observer.execute(
                        "SELECT d.envelope, t.envelope FROM managed_record d "
                        "JOIN managed_record x ON x.owner_id=d.owner_id "
                        "AND x.envelope->>'kind'='model-dispatch' "
                        "AND x.envelope->'payload'->'dispatch_owner_ref'->>'id'=d.envelope->>'id' "
                        "JOIN managed_record t ON t.owner_id=d.owner_id "
                        "AND t.envelope->'payload'->'dispatch_ref'->>'id'=x.envelope->>'id' "
                        "WHERE d.owner_id=%s AND d.envelope->>'kind'='model-dispatch-owner' "
                        "AND d.envelope->'payload'->>'request_id'=%s "
                        "AND t.envelope->>'kind'='model-dispatch-transition' "
                        "AND t.envelope->'payload'->>'state'='SENT'",
                        (command.owner_id, frame["id"]),
                    ).fetchall()
                    assert len(rows) == 1
                    descriptor = mapping(mapping(rows[0][0])["payload"])
                    actual_body = json.dumps(frame["payload"], separators=(",", ":")).encode()
                    assert sha256(data).hexdigest() == descriptor["frame_digest"]
                    assert sha256(actual_body).hexdigest() == descriptor["body_digest"]
                    assert actual_body.decode() == descriptor["body"]
                    assert descriptor["admitted_caps"] == command.protocol_caps
                    observations.append({"state": "SENT", "request_id": frame["id"]})
                    actual_write(data)

                monkeypatch.setattr(writer, "write", write)
                async with LocalControl(
                    root,
                    service,
                    owner.owner,
                    owner.epoch,
                    native_task=observed_handle,
                ) as control:

                    async def measured_control(
                        value: dict[str, object], caller: ProtocolCaller
                    ) -> dict[str, object]:
                        with timing.phase(caller, "control"):
                            return await control_task(root, value)

                    async def waiter_observed() -> int:
                        async with asyncio.timeout(0.75):
                            while True:
                                # Never reuse a cached pg_stat_activity query snapshot.
                                observer.execute("SELECT pg_stat_clear_snapshot()")
                                waiting = observer.execute(
                                    "SELECT pid FROM pg_stat_activity WHERE datname=current_database() "
                                    "AND %s=ANY(pg_blocking_pids(pid)) "
                                    "AND query LIKE '%%instance_control%%FOR UPDATE%%'",
                                    (blocker_pid,),
                                ).fetchall()
                                if len(waiting) == 1:
                                    assert waiting[0][0] != blocker_pid
                                    return int(waiting[0][0])
                                await asyncio.sleep(0.01)

                    if failure_case:
                        from omnis.policy import budgets

                        public_errors: list[str] = []

                        def private_channels(reply: dict[str, object]) -> None:
                            assert logs is not None
                            captured = capsys.readouterr()
                            public = (
                                json.dumps(reply)
                                + json.dumps(public_errors)
                                + captured.out
                                + captured.err
                                + logs.text
                            ).encode()
                            if any(
                                marker in public
                                for marker in (
                                    b"SYNTHETIC_PRIVATE_I1",
                                    b"SYNTHETIC_PRIVATE_ACK_ERROR",
                                    runtime.capability.encode(),
                                    control.capability.encode(),
                                    dsn.encode(),
                                    (url.password or "").encode(),
                                )
                                if marker
                            ):
                                raise AssertionError("private admission sentinel escaped")

                        try:
                            if order == "data_denials":
                                # Separate never-launched context; no positive grant
                                # is consumed by this finite pre-reserve bookkeeping.
                                bad_approval = {
                                    **decision,
                                    "decision_id": str(uuid4()),
                                    "approved_text_digests": ["0" * 64],
                                }
                                controls: dict[str, dict[str, object]] = {
                                    "DATA": {"data_approval": bad_approval},
                                    "owner": {"owner_id": str(uuid4())},
                                    "config": {
                                        "provider_config_ref": {
                                            **mapping(ready["provider_config_ref"]),
                                            "id": str(uuid4()),
                                        }
                                    },
                                    "projection": {
                                        "data_approval": {
                                            **bad_approval,
                                            "composition_ref": {
                                                **mapping(decision["composition_ref"]),
                                                "digest": "0" * 64,
                                            },
                                        }
                                    },
                                    "ref": {
                                        "manifest_ref": {
                                            **mapping(lifecycle["manifest_ref"]),
                                            "id": str(uuid4()),
                                        }
                                    },
                                    "digest": {
                                        "provider_config_ref": {
                                            **mapping(ready["provider_config_ref"]),
                                            "digest": "0" * 64,
                                        }
                                    },
                                }
                                for label, change in controls.items():
                                    await service.heartbeat(owner.owner, owner.epoch)
                                    prior = census()
                                    await_site = "pre_reserve_" + label
                                    with pytest.raises(CatalogError) as denied_data:
                                        await control_task(root, {**command_value, **change})
                                    public_errors.append(str(denied_data.value))
                                    assert denied_data.value.reason == (
                                        "COMMAND_CONFLICT" if label == "ref" else "TASK_REJECTED"
                                    )
                                    if census() != prior:
                                        raise AssertionError("private admission census changed")
                                    assert reserve_calls == 0 and not wire and not observations
                                private_channels({})
                                return
                            await service.heartbeat(owner.owner, owner.epoch)
                            before = census()
                            started = monotonic()
                            sender = asyncio.create_task(measured_control(command_value, "sender"))
                            send_tasks.append(sender)
                            stopped: dict[str, list[object]] = {}
                            if order == "cancel":
                                await_site = "cancel_after_peer_read"
                                await wait_protocol_marker(received, sender)
                                handlers = [
                                    t for t in timing.handlers if isinstance(t, asyncio.Task)
                                ]
                                assert len(handlers) == 1 and not handlers[0].done()
                                handlers[0].cancel()  # actual owner, not only its client
                            elif order == "late_stop":
                                await_site = "t2_before_stop"
                                await wait_protocol_marker(settle_entered, sender)
                                at_t2 = census()
                                assert len(wire) == len(observations) == 1
                                assert not any(
                                    mapping(mapping(r)["envelope"])["kind"]
                                    in {"model-protocol-receipt", "model-usage-receipt"}
                                    for r in at_t2["managed_record"]
                                )
                                await_site = "stop_commit_before_t2"
                                stop_id = uuid4()
                                assert (
                                    await service.shutdown(
                                        stop_id,
                                        command.expected_generation,
                                        owner.owner,
                                        owner.epoch,
                                    )
                                    == command.expected_generation + 1
                                )
                                stopped = census()
                                if stopped["managed_record"] != at_t2["managed_record"]:
                                    raise AssertionError("private admission census changed")
                                instance = mapping(stopped["instance_control"][0])
                                assert instance["generation"] == command.expected_generation + 1
                                assert instance["admission_open"] is False
                                assert instance["shutdown_command_id"] == str(stop_id)
                                assert (
                                    len(stopped["instance_command"])
                                    == len(at_t2["instance_command"]) + 1
                                )
                                if stopped["supervisor_lease"] != at_t2["supervisor_lease"]:
                                    raise AssertionError("private admission census changed")
                                assert authority_calls == reserve_calls == 1
                                release_settle.set()
                            await_site = "failure_or_late_join"
                            if order == "late_stop":
                                reply = await sender
                            else:
                                with pytest.raises(CatalogError) as denied:
                                    await sender
                                public_errors.append(str(denied.value))
                                assert denied.value.reason == (
                                    "TASK_REJECTED"
                                    if order in {"invalid_ack", "cancel"}
                                    else "TASK_INDETERMINATE"
                                )
                                if order == "timeout":
                                    assert timeout_produced.is_set(), (
                                        "inner post-write timeout absent"
                                    )
                                assert runtime.reader is None and runtime.writer is None
                                reply = await control_task(root, command_value)
                            assert monotonic() - started < 4.25  # observation, not a grant
                            accounting = mapping(reply["protocol_accounting"])
                            settled = census()
                            graph = [
                                mapping(mapping(r)["envelope"]) for r in settled["managed_record"]
                            ]
                            if order == "late_stop":
                                assert_protocol_records(
                                    graph, baseline_ids, command_value, accounting
                                )
                                assert_protocol_budget_accounting(
                                    accounting, command_value, "PREPARE"
                                )
                            else:
                                assert_protocol_failure_records(
                                    graph, baseline_ids, command_value, accounting
                                )
                            if [
                                r
                                for r in settled["managed_record"]
                                if str(mapping(r)["id"]) in baseline_ids
                            ] != before["managed_record"]:
                                raise AssertionError("private admission census changed")
                            comparison = stopped if order == "late_stop" else before
                            if {k: v for k, v in settled.items() if k != "managed_record"} != {
                                k: v for k, v in comparison.items() if k != "managed_record"
                            }:
                                raise AssertionError("private admission census changed")
                            assert (
                                authority_calls
                                == reserve_calls
                                == len(wire)
                                == len(observations)
                                == 1
                            )
                            reader_engine = database_engine(dsn)
                            try:
                                fresh = ModelDispatch(
                                    ManagedAdmission(reader_engine, owner.domain.root)
                                )
                                async with reader_engine.begin() as conn:
                                    refs = await model_protocol.replay(conn, command)
                                    assert refs is not None
                                    assert (
                                        await model_protocol.readback(conn, fresh, command, refs)
                                        == accounting
                                    )
                                    state = await budgets.readback(
                                        conn, command.owner_id, refs["dispatch_ref"]
                                    )
                                    assert state["charged_calls"] == 1
                                    assert state["charged_output_tokens"] == (
                                        0 if order == "late_stop" else 64
                                    )
                            finally:
                                await reader_engine.dispose()
                            assert (await control_task(root, command_value))[
                                "protocol_accounting"
                            ] == accounting
                            with pytest.raises(CatalogError) as denied:
                                await control_task(
                                    root,
                                    {
                                        **command_value,
                                        "protocol_caps": {
                                            "calls": 1,
                                            "output_tokens": 63,
                                            "wall_seconds": mapping(command_value["protocol_caps"])[
                                                "wall_seconds"
                                            ],
                                        },
                                    },
                                )
                            assert denied.value.reason == "COMMAND_CONFLICT"
                            if census() != settled:
                                raise AssertionError("private admission census changed")
                            assert authority_calls == reserve_calls == len(wire) == 1
                            public_errors.append(str(denied.value))
                            private_channels(reply)
                            if b"SYNTHETIC_PRIVATE_I1" in adapter.validate_preflight(
                                mapping(wire[0]["payload"])
                            ):
                                raise AssertionError("private admission sentinel escaped")
                            if order == "late_stop":
                                original = next(
                                    r for r in graph if r["kind"] == "model-protocol-receipt"
                                )
                                descriptor = next(
                                    r for r in graph if r["kind"] == "model-dispatch-owner"
                                )
                                forged = records.envelope(
                                    "model-protocol-receipt",
                                    {
                                        **mapping(original["payload"]),
                                        "extra": "SYNTHETIC_PRIVATE_ACK_ERROR",
                                    },
                                )
                                async with owner.domain.engine.begin() as conn:
                                    await managed_store.put(
                                        conn,
                                        command.owner_id,
                                        str(mapping(descriptor["payload"])["run_id"]),
                                        forged,
                                    )
                                poisoned = census()
                                assert (
                                    len(poisoned["managed_record"])
                                    == len(settled["managed_record"]) + 1
                                )
                                if {k: v for k, v in poisoned.items() if k != "managed_record"} != {
                                    k: v for k, v in settled.items() if k != "managed_record"
                                }:
                                    raise AssertionError("private admission census changed")
                                with pytest.raises(CatalogError) as denied_receipt:
                                    await control_task(root, command_value)
                                assert denied_receipt.value.reason == "TASK_REJECTED"
                                public_errors.append(str(denied_receipt.value))
                                private_channels(reply)
                                if census() != poisoned:
                                    raise AssertionError("private admission census changed")
                                assert authority_calls == reserve_calls == len(wire) == 1
                            return
                        except BaseException as error:
                            observe(error)
                            raise
                        finally:
                            release_settle.set()
                            for pending in send_tasks:
                                if not pending.done():
                                    pending.cancel()
                            await asyncio.gather(*send_tasks, return_exceptions=True)
                    if admission_case:
                        from time import monotonic_ns

                        from omnis.policy import budgets

                        accepted: list[tuple[dict[str, object], dict[str, object]]] = []
                        try:
                            if order == "budget_conflict":
                                run_record = next(
                                    r for r in baseline_records if r["kind"] == "managed-run"
                                )
                                async with owner.domain.engine.begin() as conn:
                                    seeded = await budgets.create_budget(
                                        conn,
                                        command.owner_id,
                                        records.reference(run_record),
                                        {**model_protocol.LIMITS, "output_tokens": 127},
                                    )
                                before_conflict = census()
                                await service.heartbeat(owner.owner, owner.epoch)
                                await_site = "budget_conflict"
                                with pytest.raises(CatalogError) as denied:
                                    await measured_control(command_value, "sender")
                                assert denied.value.reason == "TASK_REJECTED"
                                assert protocol_errors == ["MODEL_BUDGET_CONFLICT"]
                                assert census() == before_conflict
                                assert not observations and not wire
                                assert reserve_calls == authority_calls == 1
                                assert [
                                    mapping(mapping(r)["envelope"])
                                    for r in before_conflict["managed_record"]
                                    if mapping(mapping(r)["envelope"])["kind"] == "model-budget"
                                ] == [seeded]
                                return

                            if order == "budget":
                                # Source configuration was published by the actual
                                # READY producer before binding, not changed in SQL.
                                await service.heartbeat(owner.owner, owner.epoch)
                                await_site = "qualified_cap_refusal"
                                with pytest.raises(CatalogError) as denied:
                                    await measured_control(command_value, "sender")
                                assert denied.value.reason == "TASK_REJECTED"
                                assert protocol_errors == ["MODEL_PROTOCOL_CAP_REJECTED"]
                                assert census() == before
                                assert not observations and not wire and reserve_calls == 0
                                command_value["protocol_caps"] = {
                                    "calls": 1,
                                    "output_tokens": 64,
                                    "wall_seconds": 2,
                                }
                                command = NativeTaskCommand.model_validate(command_value)
                                for action, purpose in (
                                    ("model_protocol_prepare", "PREPARE"),
                                    ("model_protocol_validation", "VALIDATION"),
                                ):
                                    if accepted:
                                        # The existing peer serves one frame per connection.
                                        # Only a NEW id may use this new stream; replay
                                        # below never opens another stream or resends.
                                        await runtime.close()
                                        (
                                            runtime.reader,
                                            runtime.writer,
                                        ) = await asyncio.open_unix_connection(
                                            str(root / "peer.sock")
                                        )
                                        assert runtime.writer is not None
                                        actual_write = runtime.writer.write
                                        monkeypatch.setattr(runtime.writer, "write", write)
                                    value = {
                                        **command_value,
                                        "action": action,
                                        "protocol_id": str(uuid4()),
                                    }
                                    # The setup's heartbeat loop was joined. Multi-command
                                    # tests renew normally BETWEEN joined public commands.
                                    await service.heartbeat(owner.owner, owner.epoch)
                                    await_site = "budget_accept"
                                    before_accept = census()
                                    prior_ids = {
                                        str(mapping(r)["id"])
                                        for r in before_accept["managed_record"]
                                    }
                                    answer = await measured_control(value, "sender")
                                    assert [
                                        r
                                        for r in census()["managed_record"]
                                        if str(mapping(r)["id"]) in prior_ids
                                    ] == before_accept["managed_record"]
                                    accounting = mapping(answer["protocol_accounting"])
                                    assert_protocol_budget_accounting(accounting, value, purpose)
                                    accepted.append((value, accounting))
                                    prior = census()
                                    sent_count = len(wire)
                                    await service.heartbeat(owner.owner, owner.epoch)
                                    await_site = "budget_exhausted"
                                    with pytest.raises(CatalogError) as denied:
                                        await measured_control(
                                            {**value, "protocol_id": str(uuid4())}, "sender"
                                        )
                                    assert denied.value.reason == "TASK_REJECTED"
                                    assert protocol_errors[-1] == "MODEL_BUDGET_EXHAUSTED"
                                    assert census() == prior
                                    assert len(wire) == len(observations) == sent_count
                                assert reserve_calls == 4 and authority_calls == 5
                                settled = census()
                                graph = [
                                    mapping(mapping(r)["envelope"])
                                    for r in settled["managed_record"]
                                ]
                                assert_protocol_budget_records(graph, baseline_ids, accepted)
                                assert [
                                    r
                                    for r in settled["managed_record"]
                                    if str(mapping(r)["id"]) in baseline_ids
                                ] == before["managed_record"]
                                assert {
                                    k: v for k, v in settled.items() if k != "managed_record"
                                } == {k: v for k, v in before.items() if k != "managed_record"}
                                await service.heartbeat(owner.owner, owner.epoch)
                                await service.shutdown(
                                    uuid4(), command.expected_generation, owner.owner, owner.epoch
                                )
                            else:
                                # Let the ORIGINAL five-second lease age naturally;
                                # its derived grant then expires inside control's 4s.
                                # Never update expiry/caps/grant/clock or DB timeouts.
                                await service.heartbeat(owner.owner, owner.epoch)
                                while True:
                                    lease_time = observer.execute(
                                        "SELECT extract(epoch FROM expires_at-clock_timestamp()) FROM supervisor_lease WHERE id=1"
                                    ).fetchone()
                                    assert lease_time is not None
                                    remaining = float(lease_time[0])
                                    if remaining <= 3:
                                        break
                                    await asyncio.sleep(remaining - 3)
                                entered_b = asyncio.Event()
                                b_pid = 0
                                actual_mark = model_protocol.mark_sent

                                async def waiting_mark(
                                    conn: AsyncConnection,
                                    dispatch: ModelDispatch,
                                    value: NativeTaskCommand,
                                    refs: dict[str, object],
                                    frozen: FrozenPreflight,
                                ) -> None:
                                    nonlocal b_pid
                                    assert a_open.is_set() and a_pid > 0
                                    assert frozen is frozen_values[0]
                                    # Keep the REAL lock wait inside the default 2s
                                    # statement timeout, using only original time left.
                                    await asyncio.sleep(
                                        max(0, (frozen.deadline_ns - monotonic_ns()) / 1e9 - 1)
                                    )
                                    b_pid = int(
                                        (
                                            await conn.execute(sql("SELECT pg_backend_pid()"))
                                        ).scalar_one()
                                    )
                                    assert (
                                        await conn.execute(sql("SHOW statement_timeout"))
                                    ).scalar_one() == "2s"
                                    entered_b.set()
                                    await actual_mark(conn, dispatch, value, refs, frozen)

                                monkeypatch.setattr(model_protocol, "mark_sent", waiting_mark)
                                sender = asyncio.create_task(
                                    measured_control(command_value, "sender")
                                )
                                send_tasks.append(sender)
                                try:
                                    await_site = "deadline_t0_committed"
                                    await wait_protocol_marker(reserved, sender)
                                    reserved_census = census()
                                    reserved_graph = [
                                        mapping(mapping(r)["envelope"])
                                        for r in reserved_census["managed_record"]
                                    ]
                                    added = [
                                        r
                                        for r in reserved_graph
                                        if str(r["id"]) not in baseline_ids
                                    ]
                                    assert Counter(str(r["kind"]) for r in added) == {
                                        "model-budget": 1,
                                        "model-dispatch-owner": 1,
                                        "model-reservation": 1,
                                        "model-dispatch": 1,
                                        "contract-input-command": 1,
                                    }
                                    descriptor = mapping(
                                        next(
                                            r for r in added if r["kind"] == "model-dispatch-owner"
                                        )["payload"]
                                    )
                                    assert len(frozen_values) == 1
                                    frozen = frozen_values[0]
                                    assert descriptor["deadline_ns"] == frozen.deadline_ns
                                    async with owner.domain.engine.begin() as blocker:
                                        await actual_lock(blocker, command.owner_id)
                                        blocker_pid = int(
                                            (
                                                await blocker.execute(
                                                    sql("SELECT pg_backend_pid()")
                                                )
                                            ).scalar_one()
                                        )
                                        release_t0.set()
                                        await_site = "deadline_b_entered"
                                        await wait_protocol_marker(entered_b, sender)
                                        # Observe the actual B backend waiting on OUR
                                        # managed lock while A retains Instance/lease.
                                        while True:
                                            if sender.done():
                                                sender.result()
                                                raise AssertionError("sender ended before B wait")
                                            observer.execute("SELECT pg_stat_clear_snapshot()")
                                            waiting = observer.execute(
                                                "SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND pid=%s AND %s=ANY(pg_blocking_pids(pid)) AND wait_event_type='Lock'",
                                                (b_pid, blocker_pid),
                                            ).fetchall()
                                            if waiting == [(b_pid,)]:
                                                break
                                            await asyncio.sleep(0.005)
                                        assert (
                                            len({a_pid, b_pid, blocker_pid}) == 3
                                            and a_open.is_set()
                                        )
                                        assert monotonic_ns() < frozen.deadline_ns
                                        assert (
                                            census() == reserved_census
                                            and not wire
                                            and not observations
                                        )
                                        await_site = "deadline_original_expiry"
                                        await asyncio.sleep(
                                            max(0, (frozen.deadline_ns - monotonic_ns()) / 1e9)
                                        )
                                        # Both persisted UTC and frozen monotonic deadlines
                                        # have actually expired before releasing the blocker.
                                        while True:
                                            expiry = observer.execute(
                                                "SELECT clock_timestamp() >= %s::timestamptz",
                                                (descriptor["deadline"],),
                                            ).fetchone()
                                            assert expiry is not None
                                            if expiry[0] is True:
                                                break
                                            if sender.done():
                                                sender.result()
                                                raise AssertionError("sender ended before expiry")
                                            await asyncio.sleep(0.001)
                                        assert a_open.is_set() and not sender.done()
                                    await_site = "deadline_join"
                                    with pytest.raises(CatalogError) as denied:
                                        await sender
                                    assert denied.value.reason == "TASK_REJECTED"
                                    assert protocol_errors == ["MODEL_DEADLINE_EXPIRED"]
                                    assert not a_open.is_set() and not observations and not wire
                                    assert census() == reserved_census
                                    assert authority_calls == reserve_calls == 1
                                    reply = await control_task(root, command_value)
                                    accounting = mapping(reply["protocol_accounting"])
                                    assert (
                                        accounting["state"] == "RESERVED"
                                        and accounting["usage_state"] == "UNKNOWN"
                                    )
                                    assert (
                                        accounting["protocol_calls"] == 1
                                        and accounting["model_calls"] == 0
                                    )
                                    assert accounting["output_tokens"] is None
                                    assert (
                                        accounting["requested_caps"]
                                        == accounting["admitted_caps"]
                                        == command.protocol_caps
                                    )
                                    assert all(
                                        accounting[k] is None
                                        for k in (
                                            "cost_observed",
                                            "cost_estimate",
                                            "provider_receipt_ref",
                                        )
                                    )
                                    accepted.append((command_value, accounting))
                                except BaseException as error:
                                    observe(error)  # first snapshot, BEFORE cancelling/joining
                                    raise
                                finally:
                                    release_t0.set()
                                    if not sender.done():
                                        sender.cancel()
                                    await asyncio.gather(sender, return_exceptions=True)
                            settled = census()
                            calls_before = (
                                authority_calls,
                                reserve_calls,
                                len(wire),
                                len(observations),
                            )
                            reader_engine = database_engine(dsn)
                            try:
                                fresh = ModelDispatch(
                                    ManagedAdmission(reader_engine, owner.domain.root)
                                )
                                for value, accounting in accepted:
                                    replay = await control_task(root, value)
                                    assert replay["protocol_accounting"] == accounting
                                    dto = NativeTaskCommand.model_validate(value)
                                    async with reader_engine.begin() as conn:
                                        refs = await model_protocol.replay(conn, dto)
                                        assert refs is not None
                                        assert (
                                            await model_protocol.readback(conn, fresh, dto, refs)
                                            == accounting
                                        )
                                        state = await budgets.readback(
                                            conn, dto.owner_id, refs["dispatch_ref"]
                                        )
                                        assert state["charged_calls"] == 1
                                        assert state["charged_output_tokens"] == (
                                            64 if order == "deadline_b" else 0
                                        )
                            finally:
                                await reader_engine.dispose()
                            assert census() == settled
                            assert (
                                authority_calls,
                                reserve_calls,
                                len(wire),
                                len(observations),
                            ) == calls_before
                            assert len(wire) == (0 if order == "deadline_b" else 2)
                            return
                        except BaseException as error:
                            observe(error)
                            raise
                    if concurrent:
                        other_value = {
                            **command_value,
                            "protocol_caps": {
                                **mapping(command_value["protocol_caps"]),
                                "output_tokens": 63 if order == "conflict" else 64,
                            },
                        }
                        NativeTaskCommand.model_validate(other_value)
                        try:
                            sender = asyncio.create_task(measured_control(command_value, "sender"))
                            send_tasks.append(sender)
                            await_site = "t0_ready"
                            await wait_protocol_marker(t0_ready, sender)
                            # A separate connection cannot see any of T0's writes.
                            assert census() == before and not wire and not observations
                            second = asyncio.create_task(measured_control(other_value, "second"))
                            send_tasks.append(second)
                            async with asyncio.timeout(0.75):
                                await_site = "second_lock_entered"
                                await second_lock_entered.wait()
                                await_site = "duplicate_pg_waiter"
                                while True:
                                    observer.execute("SELECT pg_stat_clear_snapshot()")
                                    waiting = observer.execute(
                                        "SELECT pid FROM pg_stat_activity WHERE datname=current_database() "
                                        "AND pid=%s AND %s=ANY(pg_blocking_pids(pid)) "
                                        "AND wait_event_type='Lock'",
                                        (duplicate_waiter_pid, blocker_pid),
                                    ).fetchall()
                                    if waiting == [(duplicate_waiter_pid,)]:
                                        break
                                    await asyncio.sleep(0.01)
                            assert duplicate_waiter_pid != blocker_pid
                            assert not second_lock_acquired.is_set()
                            assert not sender.done() and not second.done()
                            assert census() == before and not wire and not observations
                            release_t0.set()
                            await_site = "join_second"
                            if order == "conflict":
                                with pytest.raises(CatalogError) as denied:
                                    await second
                                assert denied.value.reason == "COMMAND_CONFLICT"
                            else:
                                duplicate = await second
                                duplicate_accounting = mapping(duplicate["protocol_accounting"])
                                assert duplicate_accounting["state"] == "RESERVED"
                                assert duplicate_accounting["usage_state"] == "UNKNOWN"
                            after_second = census()
                            assert after_second == {**before, "managed_record": t0_records}
                            assert not wire and not observations and not sender.done()
                            second_finished.set()
                            await_site = "join_sender"
                            # Original control deadline, not a new phase budget.
                            reply = await sender
                            assert second_lock_acquired.is_set()
                            assert authority_calls == reserve_calls == 1
                        except BaseException as error:
                            observe(error)
                            raise
                        finally:
                            release_t0.set()
                            second_finished.set()
                            for pending in send_tasks:
                                if not pending.done():
                                    pending.cancel()
                            await asyncio.gather(*send_tasks, return_exceptions=True)
                    elif order == "nominal":
                        try:
                            reply = await measured_control(command_value, "sender")
                        except BaseException as error:
                            observe(error)
                            raise
                    else:
                        try:
                            sender = asyncio.create_task(measured_control(command_value, "sender"))
                            send_tasks.append(sender)
                            if order == "stop_first":
                                await_site = "reserved"
                                await wait_protocol_marker(reserved, sender)
                            else:
                                await_site = "received"
                                await wait_protocol_marker(received, sender)
                                assert len(observations) == 1  # committed SENT before real write
                            stopper = asyncio.create_task(
                                service.shutdown(
                                    uuid4(), command.expected_generation, owner.owner, owner.epoch
                                ),
                                name="protocol-stop",
                            )
                            stop_tasks.append(stopper)
                            if order == "stop_first":
                                await_site = "stop_locked"
                                await asyncio.wait_for(stop_locked.wait(), 1)
                            await_site = "stop_pg_waiter"
                            waiter_pid = await waiter_observed()
                            assert waiter_pid > 0 and not sender.done() and not stopper.done()
                            if order == "stop_first":
                                assert not wire and not observations
                                release_stop.set()
                                await_site = "join_stopper"
                                await asyncio.wait_for(stopper, 1)
                                await_site = "join_sender"
                                with pytest.raises(CatalogError):
                                    await sender
                            else:
                                # Stop is actually blocked on A until the finite exchange ends.
                                assert not stopper.done()
                                release_ack.set()
                                await_site = "join_sender"
                                await sender
                                await_site = "join_stopper"
                                await asyncio.wait_for(stopper, 1)
                            await_site = "poststop_replay"
                            reply = await control_task(root, command_value)  # receive-only, stopped
                        except BaseException as error:
                            observe(error)
                            raise
                        finally:
                            release_stop.set()
                            release_ack.set()
                            for task in [*send_tasks, *stop_tasks]:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(*send_tasks, *stop_tasks, return_exceptions=True)
                    # Same channel on success: nominal/conflict are timing controls,
                    # not missing observations. This is NOT the final test verdict.
                    with capsys.disabled():
                        print(
                            "\nP2_PROTOCOL_TIMING "
                            + json.dumps(
                                {
                                    "scope": "PG",
                                    "order": order,
                                    "timing": timing.snapshot(),
                                },
                                sort_keys=True,
                            ),
                            flush=True,
                        )
                    accounting = mapping(reply["protocol_accounting"])
                    if order == "stop_first":
                        assert accounting["state"] == "RELEASED"
                        assert accounting["usage_state"] == "UNKNOWN"
                        assert (
                            accounting["protocol_calls"] == 0
                            and accounting["output_tokens"] is None
                        )
                        assert len(observations) == len(wire) == 0
                        async with owner.domain.engine.begin() as conn:
                            refs = await model_protocol.replay(conn, command)
                            assert refs is not None
                            from omnis.policy import budgets

                            state = await budgets.readback(
                                conn, command.owner_id, refs["dispatch_ref"]
                            )
                            assert all(
                                mapping(mapping(row)["payload"])["state"] != "SENT"
                                for row in sequence(state["history"])
                            )
                    else:
                        assert (
                            accounting["state"] == "SETTLED"
                            and accounting["usage_state"] == "KNOWN"
                        )
                        assert (
                            accounting["protocol_calls"] == 1 and accounting["output_tokens"] == 0
                        )
                        assert len(observations) == len(wire) == 1
                    assert accounting["model_calls"] == 0
                    if concurrent:
                        settled = census()
                        graph = [mapping(mapping(r)["envelope"]) for r in settled["managed_record"]]
                        assert_protocol_records(graph, baseline_ids, command_value, accounting)
                        assert [
                            r
                            for r in settled["managed_record"]
                            if str(mapping(r)["id"]) in baseline_ids
                        ] == before["managed_record"]
                        assert {k: v for k, v in settled.items() if k != "managed_record"} == {
                            k: v for k, v in before.items() if k != "managed_record"
                        }
                        if order == "duplicate":
                            for key in ("descriptor_ref", "dispatch_ref", "request_id"):
                                assert duplicate_accounting[key] == accounting[key]
                        # Same valid changed request after settlement: public
                        # conflict and exact durable snapshots must remain stable.
                        conflict_value = {
                            **command_value,
                            "protocol_caps": {"calls": 1, "output_tokens": 63, "wall_seconds": 3},
                        }
                        with pytest.raises(CatalogError) as denied:
                            await control_task(root, conflict_value)
                        assert denied.value.reason == "COMMAND_CONFLICT"
                        assert census() == settled
                        assert authority_calls == reserve_calls == len(wire) == 1
                    if order == "nominal":
                        await service.shutdown(
                            uuid4(), command.expected_generation, owner.owner, owner.epoch
                        )
                    replay = await control_task(root, command_value)
                    assert replay["protocol_accounting"] == accounting
                    assert len(wire) == (0 if order == "stop_first" else 1)
                    if concurrent:
                        assert census() == settled
                        assert authority_calls == reserve_calls == 1
                    reader_engine = database_engine(dsn)
                    try:
                        fresh = ModelDispatch(ManagedAdmission(reader_engine, owner.domain.root))
                        async with reader_engine.begin() as conn:
                            refs = await model_protocol.replay(conn, command)
                            assert refs is not None
                            assert (
                                await model_protocol.readback(conn, fresh, command, refs)
                                == accounting
                            )
                    finally:
                        await reader_engine.dispose()
                    if concurrent:
                        assert census() == settled
                        assert authority_calls == reserve_calls == len(wire) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "order", ["eof", "timeout", "cancel", "invalid_ack", "late_stop", "data_denials"]
)
async def test_pg_protocol_failure_late_accounting_and_data(
    migrated_database_url: URL,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    order: str,
) -> None:
    await test_pg_explicit_decision_projection_owner_rollback_replay_and_stop(
        migrated_database_url,
        tmp_path,
        monkeypatch,
        capsys,
        protocol_mode=True,
        protocol_order=order,
        protocol_logs=caplog,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["budget", "budget_conflict", "deadline_b"])
async def test_pg_protocol_caps_validation_immutable_budget_and_deadline(
    migrated_database_url: URL,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    order: str,
) -> None:
    await test_pg_explicit_decision_projection_owner_rollback_replay_and_stop(
        migrated_database_url,
        tmp_path,
        monkeypatch,
        capsys,
        protocol_mode=True,
        protocol_order=order,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["nominal", "stop_first", "send_first"])
async def test_pg_protocol_sent_committed_before_exact_write_and_poststop_readback(
    migrated_database_url: URL,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    order: str,
) -> None:
    await test_pg_explicit_decision_projection_owner_rollback_replay_and_stop(
        migrated_database_url,
        tmp_path,
        monkeypatch,
        capsys,
        protocol_mode=True,
        protocol_order=order,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["duplicate", "conflict"])
async def test_pg_protocol_concurrent_duplicate_and_conflict(
    migrated_database_url: URL,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    order: str,
) -> None:
    await test_pg_explicit_decision_projection_owner_rollback_replay_and_stop(
        migrated_database_url,
        tmp_path,
        monkeypatch,
        capsys,
        protocol_mode=True,
        protocol_order=order,
    )
