"""Real private-PG qualification/durability. Native reply double is labeled.

Run only through the parent's existing attested database runner. No Docker or
alternate database fixture is created here. Requires the final composer pin.
"""

import asyncio
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.exc import ProgrammingError

from fixtures.b06b_composition import new_two_skill_seed, qualify_two
from fixtures.b06b_publication.consumer import (
    canonical,
    cli_command,
    confirmed,
    mapping,
    publish_request,
    sequence,
    strict_json,
)
from fixtures.b06b_pure_probe.consumer import Probe
from omnis.core.db import database_engine
from omnis.modules.instance.schemas import NativePrepareCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks import managed_composition
from omnis.supervisor.runtime_client import RuntimeClient
from test_b06b_pure_probe_pg import Published
from test_composition_admission_regressions import authored_case
from test_managed_contract import stage
from test_native_preparation import command, worker_fixture


@pytest.mark.parametrize(
    "case", ["valid", "empty_signal", "empty_requirement", "bom_requirement", "bom_objective"]
)
def test_pg_composed_two_skills_cli_replay_binding_readback_and_denials(
    request: pytest.FixtureRequest,
    case: str,
) -> None:
    # Fail before requesting any database if parent has not sealed real source.
    managed_composition.prompt_settings()
    url = request.getfixturevalue("migrated_database_url")
    seed = new_two_skill_seed()
    if case != "valid":
        from omnis.modules.settings.catalog_schema import load_json

        source = seed.package / "templates/procedures/publication-map.yaml"
        source.write_bytes(canonical(authored_case(mapping(load_json(source.read_bytes())), case)))
    dsn = url.render_as_string(hide_password=False)
    qualified = qualify_two(seed, dsn)
    publication = seed.success(
        "publish", publish_request(qualified, confirmed(qualified, dsn)), dsn
    )
    snapshot = seed.success(
        "snapshot", seed.write(publication_ref=publication["publication_ref"]), dsn
    )
    p = Published(
        qualified,
        Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner),
        url,
        snapshot,
    )
    _, selected = p.selected()

    async def run() -> None:
        engine = database_engine(dsn)
        service, supervisor_owner = InstanceService(engine), uuid4()

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
            epoch = await service.acquire(supervisor_owner)
            status = await service.owned_status(supervisor_owner, epoch)
            runtime = RuntimeDouble(seed.directory, generation=status.generation, epoch=epoch)
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
            await NativePreparation(
                engine, seed.root, service, supervisor_owner, epoch, runtime
            ).prepare(prep)
            managed = ManagedAdmission(engine, seed.root)
            req = {
                "schema_version": 1,
                "owner_id": seed.owner,
                "command_id": str(uuid4()),
                "selection_ref": selected["selection_ref"],
                "preparation_command_id": prep.command_id,
                "task_count": 1,
            }
            if case != "valid":
                async with engine.begin() as conn:
                    before = [
                        (await conn.execute(sql(f"SELECT count(*) FROM {table}"))).scalar_one()
                        for table in (
                            "managed_record",
                            "managed_run",
                            "managed_task",
                            "managed_inbox",
                        )
                    ]
                with pytest.raises(CatalogError):
                    await managed.prepare_composed(req)
                async with engine.begin() as conn:
                    after = [
                        (await conn.execute(sql(f"SELECT count(*) FROM {table}"))).scalar_one()
                        for table in (
                            "managed_record",
                            "managed_run",
                            "managed_task",
                            "managed_inbox",
                        )
                    ]
                assert before == after == [0, 0, 0, 0]
                return
            file = seed.directory / "composed-request.json"
            file.write_bytes(canonical(req))
            process = await asyncio.create_subprocess_exec(
                *cli_command(
                    "omnis.modules.runs.managed_admission",
                    "prepare-composed",
                    "--request",
                    str(file),
                    "--catalog-root",
                    str(seed.root),
                ),
                env=seed.environment(dsn),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(process.communicate(), 25)
            assert process.returncode == 0, err
            prepared = strict_json(out.decode())
            assert prepared["created"] is True
            replay = await managed.prepare_composed(req)
            assert replay == {**prepared, "created": False}
            with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
                await managed.prepare(req)
            with pytest.raises(CatalogError):
                await managed.prepare_composed({**req, "composition_version": 1})
            read = {k: req[k] for k in ("schema_version", "owner_id", "command_id")}
            with pytest.raises(CatalogError):
                await managed.readback({**read, "owner_id": str(uuid4())})
            manifest, reference = prepared["manifest"], prepared["manifest_ref"]
            async with engine.begin() as conn:
                payload = await managed.stage_payload(conn, seed.owner, reference)
            composition = mapping(sequence(payload["compositions"])[0])
            sections = __import__("json").loads(mapping(composition["payload"])["text"])
            assert len(sections[4:]) == 2
            assert [s["package_ref"] for s in sections[4:]] == mapping(
                mapping(sequence(prepared["briefs"])[0])["payload"]
            )["package_refs"]
            # Ordinary deletion is rejected by the physical immutable trigger.
            with pytest.raises(ProgrammingError):
                async with engine.begin() as conn:
                    await conn.execute(
                        sql("DELETE FROM managed_record WHERE id=:id"), {"id": composition["id"]}
                    )
            # Explicit disposable-DB corruption seam, not a product mutation:
            # restore the trigger before calling the consumer; rollback restores the row.
            with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
                async with engine.begin() as conn:
                    await conn.execute(
                        sql("ALTER TABLE managed_record DISABLE TRIGGER managed_record_no_change")
                    )
                    await conn.execute(
                        sql("DELETE FROM managed_record WHERE id=:id"), {"id": composition["id"]}
                    )
                    await conn.execute(
                        sql("ALTER TABLE managed_record ENABLE TRIGGER managed_record_no_change")
                    )
                    await managed.reserve_dispatch(conn, seed.owner, reference, "stage")
            assert (await managed.readback(read))["stage_started"] is False
            staged = {**stage(mapping(manifest)), "protocol": "omnis-managed-admission-v2"}
            fence = {
                "instance_id": str(status.instance_id),
                "owner": str(supervisor_owner),
                "epoch": epoch,
                "generation": status.generation,
            }
            async with service.native_preparation_commit(
                supervisor_owner, epoch, status.generation
            ) as conn:
                await managed.reserve_dispatch(conn, seed.owner, reference, "stage")
            async with service.native_preparation_commit(
                supervisor_owner, epoch, status.generation
            ) as conn:
                binding = await managed.commit_binding(
                    conn, seed.owner, reference, staged, runtime.boot, fence
                )
            assert mapping(sequence(mapping(binding["payload"])["entries"])[0])[
                "composition_ref"
            ] == records.reference(composition)
            async with service.native_preparation_commit(
                supervisor_owner, epoch, status.generation
            ) as conn:
                await managed.reserve_dispatch(conn, seed.owner, reference, "release")
            await service.shutdown(uuid4(), status.generation, supervisor_owner, epoch)
            final = {
                **staged,
                "status": "BLOCKED",
                "reason": "NO_MODEL",
                "binding_ref": records.reference(binding),
            }
            await managed.ingest_result(
                seed.owner, reference, final, runtime.boot, fence, held=True
            )
            checked = await managed.reconcile(read)
            assert (
                mapping(mapping(sequence(checked["checks"])[0])["payload"])["status"]
                == "INCOMPLETE"
            )
            assert mapping(sequence(checked["inbox"])[0])["turn_completed"] is False
            file.write_bytes(canonical(read))
            result = await asyncio.to_thread(
                subprocess.run,
                cli_command(
                    "omnis.modules.runs.managed_admission", "readback", "--request", str(file)
                ),
                env=seed.environment(dsn),
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            assert strict_json(result.stdout) == checked
            assert (await ManagedAdmission(engine).readback(read)) == checked
        finally:
            await engine.dispose()

    asyncio.run(run())
