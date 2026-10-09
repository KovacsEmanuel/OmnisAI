"""Lifecycle probes; runtime double is not proof of native integration."""

import asyncio
import importlib
from types import ModuleType
from uuid import uuid4

import pytest

from test_managed_contract import stage


def consumer() -> ModuleType:
    try:
        return importlib.import_module("omnis.modules.runs.managed_admission")
    except ModuleNotFoundError:
        pytest.fail("durable managed admission consumer missing")


def test_durable_service_entrypoints_exist() -> None:
    module = consumer()
    for method in (
        "prepare",
        "load_manifest",
        "reserve_dispatch",
        "commit_binding",
        "ingest_result",
        "check",
        "reconcile",
        "readback",
        "readback_manifest",
    ):
        assert callable(getattr(module.ManagedAdmission, method, None)), method


def test_pg_result_before_check_reconcile_once_restart(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = consumer()
    from omnis.core.db import database_engine
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.native_preparation import NativePreparation
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.supervisor.runtime_client import RuntimeClient
    from test_b06b_pure_probe_pg import ledger, setup
    from test_native_preparation import command, worker_fixture

    p = setup(request)
    _, selected = p.selected()

    async def run() -> None:
        engine = database_engine(p.dsn)
        service, owner = InstanceService(engine), uuid4()

        class RuntimeDouble(RuntimeClient):
            async def prepare(
                self,
                service: InstanceService,
                supervisor_owner: object,
                bundle_ref: dict[str, object],
                bundle: dict[str, object],
            ) -> dict[str, object]:
                return {"preparation": worker_fixture(bundle)}

        try:
            epoch = await service.acquire(owner)
            status = await service.owned_status(owner, epoch)
            runtime = RuntimeDouble(p.probe.directory, generation=status.generation, epoch=epoch)
            runtime.boot = str(uuid4())
            prep = NativePrepareCommand.model_validate(
                {
                    **command(),
                    "owner_id": p.probe.owner,
                    "instance_id": str(status.instance_id),
                    "expected_epoch": epoch,
                    "expected_generation": status.generation,
                    "selection_ref": selected["selection_ref"],
                }
            )
            await NativePreparation(engine, p.probe.root, service, owner, epoch, runtime).prepare(
                prep
            )
            before = ledger(p.url)
            from omnis.modules.runs import pure_probe

            def no_pure_execution(*args: object, **kwargs: object) -> object:
                raise AssertionError("managed prepare/replay must never execute PURE")

            monkeypatch.setattr(pure_probe, "execute_outputs", no_pure_execution)
            managed = module.ManagedAdmission(engine, p.probe.root)
            req = {
                "schema_version": 1,
                "owner_id": p.probe.owner,
                "command_id": str(uuid4()),
                "selection_ref": selected["selection_ref"],
                "preparation_command_id": prep.command_id,
                "task_count": 2,
            }
            prepares = await asyncio.gather(managed.prepare(req), managed.prepare(req))
            assert sorted(p["created"] for p in prepares) == [False, True]
            prepared = next(p for p in prepares if p["created"])
            manifest = prepared["manifest"]
            reference = records.reference(manifest)
            read = {k: req[k] for k in ("schema_version", "owner_id", "command_id")}
            assert prepared["created"] is True
            assert [t["state"] for t in prepared["tasks"]] == ["QUEUED", "QUEUED"]
            from sqlalchemy import text as sql

            from omnis.modules.tasks import managed_store

            async with engine.begin() as conn:
                for brief in prepared["briefs"]:
                    header = brief["payload"]["header"]
                    cursor = await managed_store.by_id(
                        conn, p.probe.owner, prepared["run_id"], header["through_cursor"]
                    )
                    assert cursor["payload"] == {
                        "run_id": prepared["run_id"],
                        "sequence": 1,
                        "mission_ref": header["mission_revision"],
                        "focus_ref": header["focus_ref"],
                    }
                    with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
                        await managed_store.by_id(
                            conn, str(uuid4()), prepared["run_id"], cursor["id"]
                        )
                    with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
                        await managed_store.by_id(conn, p.probe.owner, str(uuid4()), cursor["id"])
            assert (await managed.prepare(req))["created"] is False
            assert ledger(p.url) == before
            staged = stage(manifest)
            fence = {
                "instance_id": str(status.instance_id),
                "owner": str(owner),
                "epoch": epoch,
                "generation": status.generation,
            }
            async with service.native_preparation_commit(owner, epoch, status.generation) as conn:
                await managed.reserve_dispatch(conn, p.probe.owner, reference, "stage")
            with pytest.raises(CatalogError, match="NEEDS_RECONCILIATION"):
                async with engine.begin() as conn:
                    await managed.reserve_dispatch(conn, p.probe.owner, reference, "stage")
            from copy import deepcopy

            with pytest.raises(CatalogError):
                await managed.prepare({**req, "task_count": True})
            with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
                await managed.prepare({**req, "task_count": 1})
            with pytest.raises(CatalogError):
                await managed.readback({**read, "owner_id": str(uuid4())})
            bad_stage = deepcopy(staged)
            bad_stage["entries"] = []
            with pytest.raises(CatalogError):
                async with engine.begin() as conn:
                    await managed.commit_binding(
                        conn, p.probe.owner, reference, bad_stage, runtime.boot, fence
                    )
            async with service.native_preparation_commit(owner, epoch, status.generation) as conn:
                binding = await managed.commit_binding(
                    conn, p.probe.owner, reference, staged, runtime.boot, fence
                )
            assert [t["state"] for t in (await managed.readback(read))["tasks"]] == [
                "BOUND",
                "BOUND",
            ]
            final = {
                **staged,
                "status": "BLOCKED",
                "reason": "NO_MODEL",
                "binding_ref": records.reference(binding),
            }
            async with service.native_preparation_commit(owner, epoch, status.generation) as conn:
                await managed.reserve_dispatch(conn, p.probe.owner, reference, "release")
            await service.shutdown(uuid4(), status.generation, owner, epoch)
            with pytest.raises(CatalogError, match="LINEAGE_MISMATCH"):
                await managed.ingest_result(
                    p.probe.owner, reference, final, str(uuid4()), fence, held=True
                )
            bad_final = {**final, "binding_ref": {**records.reference(binding), "revision": True}}
            with pytest.raises(CatalogError):
                await managed.ingest_result(
                    p.probe.owner, reference, bad_final, runtime.boot, fence, held=True
                )
            assert (await managed.readback(read))["results"] == []
            await managed.ingest_result(
                p.probe.owner, reference, final, runtime.boot, fence, held=False
            )
            raw = await managed.readback(read)
            assert [t["state"] for t in raw["tasks"]] == ["BLOCKED", "BLOCKED"]
            async with engine.begin() as conn:
                rows = (
                    (
                        await conn.execute(
                            sql(
                                "SELECT task_id,attempt_id,state FROM managed_task WHERE run_id=:run ORDER BY batch_index"
                            ),
                            {"run": prepared["run_id"]},
                        )
                    )
                    .mappings()
                    .all()
                )
                assert [
                    {
                        "task_id": str(r["task_id"]),
                        "attempt_id": str(r["attempt_id"]),
                        "state": r["state"],
                    }
                    for r in rows
                ] == [{k: t[k] for k in ("task_id", "attempt_id", "state")} for t in raw["tasks"]]
            assert len(raw["results"]) == 2 and raw["checks"] == []
            assert all(
                i["delivered"]
                and not i["admitted"]
                and not i["turn_completed"]
                and not i["domain_result_consumed"]
                for i in raw["inbox"]
            )
            assert all(i["disposition"] == "HELD_FOR_RECONCILIATION" for i in raw["inbox"])
            await managed.ingest_result(
                p.probe.owner, reference, final, runtime.boot, fence, held=True
            )
            checked = await managed.reconcile(read)
            assert len(checked["checks"]) == 2
            assert all(c["payload"]["status"] == "INCOMPLETE" for c in checked["checks"])
            assert all(
                i["domain_result_consumed"] and not i["turn_completed"] and not i["admitted"]
                for i in checked["inbox"]
            )
            assert await managed.readback_manifest(p.probe.owner, reference) == checked
            assert await managed.reconcile(read) == checked
            assert await module.ManagedAdmission(engine, p.probe.root).readback(read) == checked
            assert ledger(p.url) == before
            import os

            from fixtures.b06b_publication.consumer import cli_command
            from omnis.modules.settings.catalog_schema import canonical, load_json

            request_file = p.probe.directory / "managed-readback.json"
            request_file.write_bytes(canonical(read))
            child = await asyncio.create_subprocess_exec(
                *cli_command(
                    "omnis.modules.runs.managed_admission",
                    "readback",
                    "--request",
                    str(request_file),
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "OMNIS_DATABASE_URL": p.dsn},
            )
            out, err = await asyncio.wait_for(child.communicate(), 15)
            assert child.returncode == 0, err
            assert load_json(out) == checked
            # Author only shortened synthetic briefs; production uses unchanged
            # immutable deadlines. No instance restart or authority renewal.
            from datetime import UTC, datetime, timedelta

            from omnis.modules.settings.catalog_models import Limits, Procedure
            from omnis.modules.tasks import managed_contract

            original_builder = managed_contract.build_records

            def short_builder(
                selection: dict[str, object],
                preparation_ref: dict[str, object],
                procedure_ref: dict[str, object],
                procedure: Procedure,
                bindings: list[dict[str, object]],
                package: str,
                role: str,
                count: int,
                now: datetime,
                recipe_limits: Limits | None = None,
                *,
                composition_packages: list[dict[str, object]] | None = None,
            ) -> list[dict[str, object]]:
                assert composition_packages is None  # This unchanged probe is legacy v1.
                ceiling = min(
                    procedure.limits.deadline_seconds,
                    (recipe_limits or procedure.limits).deadline_seconds,
                )
                return original_builder(
                    selection,
                    preparation_ref,
                    procedure_ref,
                    procedure,
                    bindings,
                    package,
                    role,
                    count,
                    now - timedelta(seconds=ceiling - 3),
                    recipe_limits,
                )

            with monkeypatch.context() as clock_context:
                clock_context.setattr(managed_contract, "build_records", short_builder)
                for operation in ("stage", "release"):
                    short_req = {**req, "command_id": str(uuid4())}
                    short = await managed.prepare(short_req)
                    short_ref = short["manifest_ref"]
                    short_read = {
                        k: short_req[k] for k in ("schema_version", "owner_id", "command_id")
                    }
                    if operation == "release":
                        # Domain-only transaction: the parent proves the live
                        # supervisor fence. Unique synthetic native lineage.
                        short_stage = stage(short["manifest"])
                        async with engine.begin() as conn:
                            await managed.reserve_dispatch(conn, p.probe.owner, short_ref, "stage")
                            await managed.commit_binding(
                                conn, p.probe.owner, short_ref, short_stage, str(uuid4()), fence
                            )
                    before_expiry = await managed.readback(short_read)
                    deadline = datetime.fromisoformat(short["briefs"][0]["payload"]["deadline"])
                    await asyncio.sleep(
                        max(0, (deadline - datetime.now(UTC)).total_seconds()) + 0.05
                    )
                    with pytest.raises(CatalogError, match="BRIEF_EXPIRED"):
                        async with engine.begin() as conn:
                            await managed.reserve_dispatch(
                                conn, p.probe.owner, short_ref, operation
                            )
                    assert await managed.readback(short_read) == before_expiry
                    assert (await managed.prepare(short_req))["created"] is False
                    async with engine.begin() as conn:
                        started = (
                            await conn.execute(
                                sql(
                                    f"SELECT {operation}_started FROM managed_run WHERE run_id=:run"
                                ),
                                {"run": short["run_id"]},
                            )
                        ).scalar_one()
                        assert started is False
        finally:
            await engine.dispose()

    asyncio.run(run())
