"""Real SOURCE PG admission-data tracer; native identities/transport are a seed.

SQL, qualification, owner/fencing, explicit configuration DATA producer/receipt,
first reader, projection and approval persistence are real. Native runtime,
actual initialization/turn, model compatibility, SDK and inference are not claimed.
"""

import asyncio
import importlib
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.engine import URL

from fixtures.b06b_publication.consumer import canonical, mapping, sequence
from fixtures.b06b_pure_probe.consumer import Probe
from fixtures.c03_journey import publish_capture
from fixtures.c03_records import qualify_records
from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlConflict
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
from omnis.supervisor.runtime_client import RuntimeClient
from test_managed_contract import stage
from test_model_admission import protocol_configuration
from test_model_projection import text_digests
from test_native_preparation import command, worker_fixture
from test_ready_model_configuration import configuration


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
    protocol_mode: bool = False,
    protocol_order: str = "nominal",
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
) -> None:
    """Actual SQL + both UDS; only retained native identity is a synthetic seed.

    Observer C runs its own READ COMMITTED connection immediately inside write,
    then delegates the exact original bytes. No transport method is substituted.
    """
    import json
    import os
    import tempfile
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    import psycopg
    from sqlalchemy.ext.asyncio import AsyncConnection

    from omnis.core.db import validated_database_url
    from omnis.modules.instance.records import InstanceRecord, LeaseRecord
    from omnis.modules.runs import model_protocol
    from omnis.supervisor.native_tasks import control_task
    from omnis.transport.local_control import LocalControl
    from test_native_task_client import peer_client

    adapter = importlib.import_module("omnis_hermes.model_admission")
    command_value = {
        **lifecycle,
        "action": "model_protocol_prepare",
        "data_approval": decision,
        "provider_config_ref": ready["provider_config_ref"],
        "protocol_id": str(uuid4()),
        "protocol_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 3},
    }
    command = NativeTaskCommand.model_validate(command_value)
    wire: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    reserved, stop_locked, release_stop = asyncio.Event(), asyncio.Event(), asyncio.Event()
    received, release_ack = asyncio.Event(), asyncio.Event()
    actual_fence, actual_locked = service.native_preparation_commit, service._locked
    fence_count, blocker_pid = 0, 0
    send_tasks: list[asyncio.Task[dict[str, object]]] = []
    stop_tasks: list[asyncio.Task[int]] = []

    @asynccontextmanager
    async def fenced(who: UUID, epoch: int, generation: int) -> AsyncIterator[AsyncConnection]:
        nonlocal fence_count, blocker_pid
        fence_count += 1
        current = fence_count
        async with actual_fence(who, epoch, generation) as conn:
            if order == "send_first" and current == 2:
                blocker_pid = int((await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one())
            yield conn
        if current == 1:  # actual RESERVE transaction has committed
            reserved.set()
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

    def cold(payload: dict[str, object]) -> dict[str, object]:
        body = mapping(mapping(payload["binding"])["payload"])
        return mapping(
            adapter.cold_preflight(
                payload,
                native_root_id=body["native_root_id"],
                native_entries=body["entries"],
                source_configuration=protocol_configuration(payload),
            )
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
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="dapg-") as name:
            root = Path(name)
            async with peer_client(
                root,
                wire,
                result=cold,
                runtime_boot=owner.runtime.boot,
                observed=received,
                hold=release_ack if order == "send_first" else None,
            ) as runtime:
                assert runtime.epoch == owner.epoch
                owner.runtime = runtime
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
                    root, service, owner.owner, owner.epoch, native_task=owner.handle
                ):

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

                    if order == "nominal":
                        reply = await control_task(root, command_value)
                    else:
                        try:
                            sender = asyncio.create_task(control_task(root, command_value))
                            send_tasks.append(sender)
                            if order == "stop_first":
                                await asyncio.wait_for(reserved.wait(), 1)
                            else:
                                await asyncio.wait_for(received.wait(), 1.5)
                                assert len(observations) == 1  # committed SENT before real write
                            stopper = asyncio.create_task(
                                service.shutdown(
                                    uuid4(), command.expected_generation, owner.owner, owner.epoch
                                ),
                                name="protocol-stop",
                            )
                            stop_tasks.append(stopper)
                            if order == "stop_first":
                                await asyncio.wait_for(stop_locked.wait(), 1)
                            waiter_pid = await waiter_observed()
                            assert waiter_pid > 0 and not sender.done() and not stopper.done()
                            if order == "stop_first":
                                assert not wire and not observations
                                release_stop.set()
                                await asyncio.wait_for(stopper, 1)
                                with pytest.raises(CatalogError):
                                    await asyncio.wait_for(sender, 1)
                            else:
                                # Stop is actually blocked on A until the finite exchange ends.
                                assert not stopper.done()
                                release_ack.set()
                                await asyncio.wait_for(sender, 2)
                                await asyncio.wait_for(stopper, 1)
                            reply = await control_task(root, command_value)  # receive-only, stopped
                        finally:
                            release_stop.set()
                            release_ack.set()
                            for task in [*send_tasks, *stop_tasks]:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(*send_tasks, *stop_tasks, return_exceptions=True)
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
                    if order == "nominal":
                        await service.shutdown(
                            uuid4(), command.expected_generation, owner.owner, owner.epoch
                        )
                    replay = await control_task(root, command_value)
                    assert replay["protocol_accounting"] == accounting
                    assert len(wire) == (0 if order == "stop_first" else 1)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["nominal", "stop_first", "send_first"])
async def test_pg_protocol_sent_committed_before_exact_write_and_poststop_readback(
    migrated_database_url: URL,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    order: str,
) -> None:
    await test_pg_explicit_decision_projection_owner_rollback_replay_and_stop(
        migrated_database_url,
        tmp_path,
        monkeypatch,
        protocol_mode=True,
        protocol_order=order,
    )
