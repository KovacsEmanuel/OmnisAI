"""Parent-only attested PG gate; existing real qualified publication, native reply double.

No DB provisioning here. This file does not claim successful C03 qualification:
the slotless qualified source is a real negative control for RUN create-context.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text as sql

from omnis.core.db import database_engine
from omnis.modules.instance.schemas import NativePrepareCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.settings.catalog_models import CatalogError
from omnis.supervisor.runtime_client import RuntimeClient
from test_b06b_pure_probe_pg import setup
from test_managed_contract import ref
from test_native_preparation import command, worker_fixture


def test_pg_c03_slotless_source_and_missing_input_leave_no_assignment(
    request: pytest.FixtureRequest,
) -> None:
    p = setup(request)
    _, selected = p.selected()

    async def run() -> None:
        engine = database_engine(p.dsn)
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
            runtime = RuntimeDouble(p.probe.directory, generation=status.generation, epoch=epoch)
            runtime.boot = str(uuid4())
            preparation = NativePrepareCommand.model_validate(
                {
                    **command(),
                    "owner_id": p.probe.owner,
                    "instance_id": str(status.instance_id),
                    "expected_epoch": epoch,
                    "expected_generation": status.generation,
                    "selection_ref": selected["selection_ref"],
                }
            )
            await NativePreparation(
                engine, p.probe.root, service, supervisor_owner, epoch, runtime
            ).prepare(preparation)
            producer = ContractInputs(engine, p.probe.root)
            context_request: dict[str, object] = {
                "schema_version": 1,
                "owner_id": p.probe.owner,
                "command_id": str(uuid4()),
                "selection_ref": selected["selection_ref"],
                "preparation_command_id": preparation.command_id,
            }
            with pytest.raises(CatalogError, match="UNSUPPORTED_CAPTURE_SLOT"):
                await producer.create_context(context_request)
            context_ref = ref("contract-input-context")
            with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
                await producer.create_input(
                    {
                        "schema_version": 1,
                        "owner_id": p.probe.owner,
                        "command_id": str(uuid4()),
                        "context_ref": context_ref,
                        "input": {"capture": "new RUN data"},
                    }
                )
            with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
                await ManagedAdmission(engine, p.probe.root).prepare_composed(
                    {
                        **context_request,
                        "schema_version": 2,
                        "task_count": 1,
                        "context_ref": context_ref,
                        "slot_values": [
                            {"slot_name": "capture", "refs": [ref("contract-case-input")]}
                        ],
                    }
                )
            async with engine.begin() as conn:
                for table in ("managed_record", "managed_run", "managed_task", "managed_inbox"):
                    assert (
                        await conn.execute(sql(f"SELECT count(*) FROM {table}"))
                    ).scalar_one() == 0
        finally:
            await engine.dispose()

    asyncio.run(run())
