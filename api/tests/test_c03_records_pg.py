"""Real records CLI/PG tracer. Preparation double here is not installed native QA."""

import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from fixtures.b06b_publication.consumer import (
    canonical,
    cli_command,
    mapping,
    sequence,
    strict_json,
)
from fixtures.b06b_pure_probe.consumer import Probe
from fixtures.c03_journey import publish_capture
from fixtures.c03_records import EVALUATION_VALUE, qualify_records
from omnis.core.db import database_engine
from omnis.modules.instance.schemas import NativePrepareCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.tasks.managed_contract import blocked_result
from omnis.supervisor.runtime_client import RuntimeClient
from test_native_preparation import command, worker_fixture


def test_records_qualification_publish_run_composition_replay(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    url = request.getfixturevalue("migrated_database_url")
    dsn = url.render_as_string(hide_password=False)
    qualified, evaluation = qualify_records(tmp_path / "records-run", dsn)
    seed = qualified.seed
    assert mapping(evaluation["input_ref"])["kind"] == "contract-case-records"
    assert mapping(mapping(evaluation["input"])["payload"])["value"] == EVALUATION_VALUE
    assert mapping(mapping(evaluation["context"])["payload"])["namespace"] == "PACKAGE_EVAL"
    pure = mapping(mapping(qualified.pure["evaluation"])["payload"])
    assert pure["protocol"] == "c03-static-pure-records-v3"
    assert [json.loads(str(v)) for v in sequence(pure["outputs"])] == [
        {
            "operations": [
                {"method": "GET", "path": "/evaluation-a", "statuses": [200, 404]},
                {"method": "POST", "path": "/evaluation-z", "statuses": [201]},
            ]
        },
        {
            "surface_map": [
                {"path": "/evaluation-a", "methods": ["GET"], "operation_count": 1},
                {"path": "/evaluation-z", "methods": ["POST"], "operation_count": 1},
            ]
        },
    ]
    published, snapshot = publish_capture(qualified, dsn)
    release_request = seed.request(publication_ref=published["publication_ref"])
    release_before = canonical(seed.success("readback", release_request, dsn))
    assert b"/evaluation-" not in canonical(snapshot)
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    selected = probe.success(
        "select",
        probe.write(snapshot_ref=snapshot["snapshot_ref"], recipe_key="records-mapper"),
        dsn,
    )

    def cli(
        module: str, operation: str, value: dict[str, object], expected: int = 0
    ) -> dict[str, object]:
        path = seed.directory / ("records-" + uuid4().hex + ".json")
        path.write_bytes(canonical(value))
        result = subprocess.run(
            cli_command(
                module, operation, "--request", str(path), "--catalog-root", str(seed.root)
            ),
            env=seed.environment(dsn),
            cwd=seed.directory,
            capture_output=True,
            text=True,
            timeout=25,
        )
        assert result.returncode in (0, 2), f"unexpected exit={result.returncode}"
        output = strict_json(result.stdout if result.returncode == 0 else result.stderr)
        assert result.returncode == expected, (
            f"{operation}: exit={result.returncode} reason={output.get('reason')}"
        )
        assert not (result.stderr if expected == 0 else result.stdout)
        return output

    async def run() -> None:
        engine = database_engine(dsn)
        service, supervisor = InstanceService(engine), uuid4()

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
            epoch = await service.acquire(supervisor)
            status = await service.owned_status(supervisor, epoch)
            runtime = RuntimeDouble(seed.directory, generation=status.generation, epoch=epoch)
            runtime.boot = str(uuid4())
            preparation = NativePrepareCommand.model_validate(
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
                preparation
            )
            producer, consumer = (
                "omnis.modules.runs.contract_inputs",
                "omnis.modules.runs.managed_admission",
            )
            context_request = seed.write(
                schema_version=2,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
            )
            context = cli(producer, "create-context", context_request)
            new_value = {
                "records": [
                    {"method": "POST", "path": "/RUN-z/é🦊", "status": 201},
                    {"method": "GET", "path": "/RUN-a", "status": 404},
                    {"method": "GET", "path": "/RUN-a", "status": 200},
                ]
            }
            input_request = seed.write(
                schema_version=2, context_ref=context["context_ref"], input=new_value
            )
            created_input = cli(producer, "create-input", input_request)
            assert created_input["input_ref"] != evaluation["input_ref"]
            read_request = seed.request(command_id=input_request["command_id"])
            input_read = cli(producer, "read-input", read_request)
            assert mapping(mapping(input_read["input"])["payload"])["value"] == new_value
            assert mapping(mapping(input_read["context"])["payload"])["namespace"] == "RUN"
            assert cli(producer, "create-input", input_request)["created"] is False
            assert (
                cli(producer, "create-input", {**input_request, "input": {"records": []}}, 2)[
                    "reason"
                ]
                == "COMMAND_CONFLICT"
            )
            assignment = seed.write(
                schema_version=3,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
                task_count=1,
                context_ref=context["context_ref"],
                slot_values=[{"slot_name": "records", "refs": [created_input["input_ref"]]}],
            )
            prepared = cli(consumer, "prepare-composed", assignment)
            graph = [mapping(r) for r in sequence(prepared["records"])]
            bound = next(r for r in graph if r["kind"] == "bound-procedure")
            resolved = mapping(mapping(bound["payload"])["resolved_procedure"])
            assert resolved["slots"] == [] and len(sequence(resolved["probe"])) == 2
            assert mapping(sequence(resolved["probe"])[0])["input_bindings"] == [
                {"name": "records", "source_ref": created_input["input_ref"], "selector": "records"}
            ]
            brief = mapping(sequence(prepared["briefs"])[0])
            requirements = sequence(
                mapping(mapping(brief["payload"])["method_plan"])["requirements"]
            )
            assert len(requirements) == 3
            assert [mapping(r)["required"] for r in requirements] == [True, True, False]
            assert mapping(blocked_result(brief)["payload"])["consumed_input_refs"] == []
            composition = next(r for r in graph if r["kind"] == "prompt-composition")
            sections = sequence(json.loads(str(mapping(composition["payload"])["text"])))
            assert mapping(mapping(mapping(sections[4])["input"])["payload"])["value"] == new_value
            assert mapping(sections[4])["version"] == 2
            assert (
                mapping(mapping(sections[4])["context"])["payload"]
                == mapping(input_read["context"])["payload"]
            )
            historical = canonical(prepared["records"])
            assert canonical(cli(consumer, "prepare-composed", assignment)["records"]) == historical
            assert (
                canonical(
                    cli(consumer, "readback", seed.request(command_id=assignment["command_id"]))[
                        "records"
                    ]
                )
                == historical
            )
            async with engine.begin() as conn:
                stage = await ManagedAdmission(engine, seed.root).stage_payload(
                    conn, seed.owner, prepared["manifest_ref"]
                )
            assert stage["protocol"] == "omnis-managed-admission-v3"
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integrations/hermes/src"))
            try:
                native = importlib.import_module("omnis_hermes.managed_admission_contract")
                assert native.validate_stage(stage) == prepared["manifest"]
            finally:
                sys.path.pop(0)
            second_context = cli(
                producer, "create-context", {**context_request, "command_id": str(uuid4())}
            )
            second_input = cli(
                producer,
                "create-input",
                seed.write(
                    schema_version=2,
                    context_ref=second_context["context_ref"],
                    input={"records": []},
                ),
            )
            second = cli(
                consumer,
                "prepare-composed",
                {
                    **assignment,
                    "command_id": str(uuid4()),
                    "context_ref": second_context["context_ref"],
                    "slot_values": [{"slot_name": "records", "refs": [second_input["input_ref"]]}],
                },
            )
            second_composition = next(
                mapping(r)
                for r in sequence(second["records"])
                if mapping(r)["kind"] == "prompt-composition"
            )
            second_sections = sequence(
                json.loads(str(mapping(second_composition["payload"])["text"]))
            )
            assert mapping(mapping(mapping(second_sections[4])["input"])["payload"])["value"] == {
                "records": []
            }
            for i in (0, 1):
                assert (
                    mapping(mapping(sections[i])["record"])["payload"]
                    == mapping(mapping(second_sections[i])["record"])["payload"]
                )
            assert (
                canonical(
                    cli(consumer, "readback", seed.request(command_id=assignment["command_id"]))[
                        "records"
                    ]
                )
                == historical
            )
            assert canonical(seed.success("readback", release_request, dsn)) == release_before
        finally:
            await engine.dispose()

    asyncio.run(run())
