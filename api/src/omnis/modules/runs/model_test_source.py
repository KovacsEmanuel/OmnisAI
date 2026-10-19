"""Finite private provisioning of the shipped synthetic package, never publication consent."""

import argparse
import asyncio
import base64
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError

from omnis.modules.instance.domain import ControlConflict, InstanceStatus
from omnis.modules.instance.schemas import NativePrepareCommand
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.runs.model_test_operation import key, load, save
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import load_json
from omnis.modules.settings.skill_catalog import read_file
from omnis.modules.tasks.managed_contract import mapping, sequence
from omnis.supervisor.runtime_client import RuntimeUnavailable

if TYPE_CHECKING:
    from omnis.supervisor.native_tasks import NativeTaskOwner

PACKAGE = "records-mapping-contract"
FILES = (
    "SKILL.md",
    "omnis.yaml",
    "NOTICE.md",
    "references/methodology.md",
    "templates/procedures/map-records.yaml",
    "templates/schemas/records.schema.json",
    "templates/schemas/operations.schema.json",
    "templates/schemas/surface_map.schema.json",
    "templates/schemas/empty.schema.json",
)


def verify_shipped(bundle: dict[str, object], catalog: Path, source: Path) -> None:
    body = mapping(bundle["payload"])
    packages = sequence(body["packages"])
    if body["recipe_key"] != "records-mapper" or len(packages) != 1:
        raise CatalogError("PREPARATION_REJECTED")
    package = mapping(packages[0])
    files = {
        str(mapping(f)["path"]): base64.b64decode(str(mapping(f)["content_b64"]), validate=True)
        for f in sequence(package["files"])
    }
    if package["package_key"] != PACKAGE or set(files) != set(FILES):
        raise CatalogError("PREPARATION_REJECTED")
    if any(
        raw != read_file(source / "skills" / PACKAGE / name, 8192) for name, raw in files.items()
    ):
        raise CatalogError("PREPARATION_REJECTED")
    candidate = str(mapping(body["candidate_snapshot_ref"])["id"])
    if read_file(catalog / "candidates" / candidate / "profile.yaml", 262144) != read_file(
        source / "profile.yaml", 262144
    ):
        raise CatalogError("PREPARATION_REJECTED")


async def provision(
    owner: "NativeTaskOwner", command: ModelTestControl, status: InstanceStatus
) -> dict[str, object]:
    identity = str(status.instance_id)
    root = owner.domain.root
    source = os.environ.get("OMNIS_MODEL_TEST_SOURCE_ROOT")
    if root is None or source != "/opt/omnis/model-test" or owner.model_test_closing:
        raise CatalogError("CATALOG_REQUIRED")
    prepared = NativePrepareCommand.model_validate(
        {
            "op": "native_prepare",
            "schema_version": 1,
            "owner_id": identity,
            "command_id": key(identity, "preparation"),
            "instance_id": identity,
            "expected_generation": status.generation,
            "expected_epoch": owner.epoch,
            "selection_ref": command.selection_ref,
        }
    )
    preparation = NativePreparation(
        owner.domain.engine, root, owner.service, owner.owner, owner.epoch, owner.runtime
    )
    async with owner.service.native_preparation_commit(
        owner.owner, owner.epoch, status.generation
    ) as connection:
        await records.lock(connection, "fixed-model-test:" + identity)
        existing = await load(connection, identity, "source")
        if existing is not None:
            if mapping(existing["payload"])["selection_ref"] != command.selection_ref:
                raise CatalogError("COMMAND_CONFLICT")
            return {"status": "PREPARED_RESTART_REQUIRED"}
        if await load(connection, identity, "provision") is not None:
            raise CatalogError("TASK_INDETERMINATE")
        # This revalidates actual Publish/qualification and all retained source before launch.
        _, bundle = await preparation.build(connection, prepared)
        verify_shipped(bundle, root, Path(source))
        if (await owner.runtime.status())["state"] != "IDLE":
            raise CatalogError("PREPARATION_BUSY")
        await save(connection, identity, "provision", {"selection_ref": command.selection_ref})
    phase = "LAUNCH"
    try:
        await owner.runtime.launch_inert(owner.service, owner.owner)
        phase = "HEARTBEAT"
        await owner.service.heartbeat(owner.owner, owner.epoch)
        phase = "RENEW"
        await owner.runtime.renew(owner.service, owner.owner)
        phase = "PREPARE"
        await preparation.prepare(prepared)
    except BaseException as error:
        # The control transport normalizes this exception after it leaves the owner.
        with suppress(BaseException):
            kind = next(
                (
                    label
                    for cls, label in (
                        (asyncio.CancelledError, "CANCELLED"),
                        (TimeoutError, "TIMEOUT"),
                        (RuntimeUnavailable, "RUNTIME_UNAVAILABLE"),
                        (ControlConflict, "CONTROL_CONFLICT"),
                        (SQLAlchemyError, "DB_ERROR"),
                        (OSError, "OS_ERROR"),
                        (ValueError, "VALUE_ERROR"),
                    )
                    if isinstance(error, cls)
                ),
                "OTHER",
            )
            sys.stderr.write(f"MODEL_TEST_PROVISION_FAILURE phase={phase} error={kind}\n")
            sys.stderr.flush()
        raise
    inputs = ContractInputs(owner.domain.engine, root)
    context = await inputs.create_method_context(
        {
            "schema_version": 2,
            "owner_id": identity,
            "command_id": key(identity, "context"),
            "selection_ref": command.selection_ref,
            "preparation_command_id": prepared.command_id,
        }
    )
    original = await inputs.create_input(
        {
            "schema_version": 2,
            "owner_id": identity,
            "command_id": key(identity, "input"),
            "context_ref": context["context_ref"],
            "input": {"records": [{"method": "GET", "path": "/synthetic", "status": 200}]},
        }
    )
    assigned = await owner.domain.prepare_method(
        {
            "schema_version": 3,
            "owner_id": identity,
            "command_id": key(identity, "assignment"),
            "selection_ref": command.selection_ref,
            "preparation_command_id": prepared.command_id,
            "task_count": 1,
            "context_ref": context["context_ref"],
            "slot_values": [{"slot_name": "records", "refs": [original["input_ref"]]}],
        }
    )
    async with owner.service.native_preparation_commit(
        owner.owner, owner.epoch, status.generation
    ) as connection:
        await records.lock(connection, "fixed-model-test:" + identity)
        await save(
            connection,
            identity,
            "source",
            {
                "owner_id": identity,
                "command_id": key(identity, "assignment"),
                "manifest_ref": assigned["manifest_ref"],
                "selection_ref": command.selection_ref,
            },
        )
    return {"status": "PREPARED_RESTART_REQUIRED"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind the explicitly published fixed Test model source"
    )
    parser.add_argument(
        "--request",
        type=Path,
        required=True,
        help="JSON containing the real published execution-selection ref only",
    )
    args = parser.parse_args()
    try:
        from omnis.modules.runs.model_test_routes import control_exchange

        body = mapping(load_json(read_file(args.request, 4096)))
        if set(body) != {"selection_ref"}:
            raise ValueError("Only the published selection is accepted")
        command = ModelTestControl.model_validate(
            {"op": "model_test", "action": "provision", **body}
        )
        result = asyncio.run(control_exchange(command))
        print(result)
        return 0
    except (OSError, ValueError, CatalogError, TimeoutError):
        print("MODEL_TEST_PROVISIONING_BLOCKED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
