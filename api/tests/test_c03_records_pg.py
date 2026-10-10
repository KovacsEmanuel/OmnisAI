"""Real records CLI/PG tracer. Preparation double here is not installed native QA."""

import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

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
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import blocked_result
from omnis.supervisor.runtime_client import RuntimeClient
from test_native_preparation import command, worker_fixture


def test_records_qualification_publish_run_composition_replay(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        module: str,
        operation: str,
        value: dict[str, object],
        expected: int = 0,
        raw: bytes | None = None,
    ) -> dict[str, object]:
        path = seed.directory / ("records-" + uuid4().hex + ".json")
        path.write_bytes(canonical(value) if raw is None else raw)
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

            # Slow negatives use an independent, never-dispatched assignment.
            negative_context_request = {**context_request, "command_id": str(uuid4())}
            negative_context = cli(producer, "create-context", negative_context_request)
            assert cli(producer, "create-context", negative_context_request)["created"] is False
            negative_input_request = seed.write(
                schema_version=2, context_ref=negative_context["context_ref"], input={"records": []}
            )
            negative_input = cli(producer, "create-input", negative_input_request)
            negative_assignment = {
                **assignment,
                "command_id": str(uuid4()),
                "context_ref": negative_context["context_ref"],
                "slot_values": [{"slot_name": "records", "refs": [negative_input["input_ref"]]}],
            }

            async def totals() -> dict[str, int]:
                async with engine.connect() as conn:
                    return {
                        name: int(
                            (await conn.execute(sql("SELECT count(*) FROM " + name))).scalar_one()
                        )
                        for name in (
                            "managed_record",
                            "managed_run",
                            "managed_task",
                            "managed_inbox",
                            "catalog_record",
                            "catalog_command",
                        )
                    }

            before_denials = await totals()
            good_ref = mapping(negative_input["input_ref"])
            ref_denials = [
                {**good_ref, "id": str(uuid4())},
                second_input["input_ref"],
                evaluation["input_ref"],
                {**good_ref, "kind": "contract-case-input"},
                {**good_ref, "revision": 2},
                {**good_ref, "revision": True},
                {**good_ref, "digest": "f" * 64},
            ]
            for bad_ref in ref_denials:
                assert (
                    cli(
                        consumer,
                        "prepare-composed",
                        {
                            **negative_assignment,
                            "slot_values": [{"slot_name": "records", "refs": [bad_ref]}],
                        },
                        2,
                    )["status"]
                    == "BLOCKED"
                )
                assert await totals() == before_denials
            for slots in (
                [],
                [{"slot_name": "records", "refs": []}],
                [{"slot_name": "records", "refs": [good_ref, good_ref]}],
                [{"slot_name": "records", "refs": [good_ref]}] * 2,
                [{"slot_name": "unknown", "refs": [good_ref]}],
                [{"slot_name": "capture", "refs": [good_ref]}],
                [{"slot_name": "records", "refs": [good_ref]}] * 129,
            ):
                assert (
                    cli(
                        consumer,
                        "prepare-composed",
                        {**negative_assignment, "slot_values": slots},
                        2,
                    )["status"]
                    == "BLOCKED"
                )
                assert await totals() == before_denials
            for delta in (
                {"owner_id": str(uuid4())},
                {"schema_version": 2},
                {"task_count": 2},
                {"task_count": True},
                {"context_ref": evaluation["context_ref"]},
            ):
                assert (
                    cli(consumer, "prepare-composed", {**negative_assignment, **delta}, 2)["status"]
                    == "BLOCKED"
                )
                assert await totals() == before_denials
            missing = {k: v for k, v in negative_assignment.items() if k != "slot_values"}
            assert cli(consumer, "prepare-composed", missing, 2)["status"] == "BLOCKED"
            row = {"method": "GET", "path": "/", "status": 200}
            bad_values: list[object] = [
                {},
                {"records": [], "extra": 1},
                {"records": "[]"},
                {"records": [None]},
                {"records": [{"method": "GET", "path": "/"}]},
                {"records": [{**row, "extra": 1}]},
                {"records": [{**row, "method": "TRACE"}]},
                {"records": [{**row, "path": "relative"}]},
                {"records": [{**row, "path": "/a b"}]},
                {"records": [{**row, "path": "/a\\b"}]},
                {"records": [{**row, "path": "/\x00"}]},
                {"records": [{**row, "path": "\ufeff/"}]},
                *[{"records": [{**row, "status": s}]} for s in (True, "200", 99, 600)],
                {"records": [row] * 129},
                {"records": [{**row, "path": "/" + "x" * 239}] * 40},
                {"capture": "[]"},
            ]
            for bad in bad_values:
                assert (
                    cli(
                        producer,
                        "create-input",
                        {**negative_input_request, "command_id": str(uuid4()), "input": bad},
                        2,
                    )["status"]
                    == "BLOCKED"
                )
                assert await totals() == before_denials
            for raw in (
                b"\xef\xbb\xbf" + canonical(negative_input_request),
                b"\xff",
                canonical(negative_input_request).decode().encode("utf-16"),
            ):
                assert (
                    cli(producer, "create-input", negative_input_request, 2, raw=raw)["status"]
                    == "BLOCKED"
                )
                assert await totals() == before_denials
            for input_delta in (
                {"schema_version": 1},
                {"context_ref": evaluation["context_ref"]},
                {"owner_id": str(uuid4())},
                {"provenance": {"source_kind": "SYNTHETIC"}},
                {"kind": "contract-case-records"},
            ):
                assert (
                    cli(
                        producer,
                        "create-input",
                        {**negative_input_request, "command_id": str(uuid4()), **input_delta},
                        2,
                    )["status"]
                    == "BLOCKED"
                )
                assert await totals() == before_denials

            # Actual INSERT fault cuts: retain the previously committed input prefix,
            # roll back every newly written assignment/context/input/command record.
            original_put = managed_store.put
            observed: list[str] = []
            for kind, operation, value in (
                ("task-brief", "assignment", negative_assignment),
                (
                    "contract-case-records",
                    "input",
                    {**negative_input_request, "command_id": str(uuid4())},
                ),
                ("mission", "context", {**context_request, "command_id": str(uuid4())}),
            ):

                async def fail_after_insert(
                    conn: AsyncConnection,
                    owner: str,
                    run_id: str,
                    item: dict[str, object],
                    expected_kind: str = kind,
                ) -> None:
                    await original_put(conn, owner, run_id, item)
                    if item["kind"] == expected_kind:
                        observed.append(expected_kind)
                        assert (
                            await conn.execute(
                                sql("SELECT count(*) FROM managed_record WHERE id=:id"),
                                {"id": item["id"]},
                            )
                        ).scalar_one() == 1
                        raise CatalogError("RECORDS_FAULT_AFTER_INSERT")

                with monkeypatch.context() as patcher:
                    patcher.setattr(managed_store, "put", fail_after_insert)
                    with pytest.raises(CatalogError, match="RECORDS_FAULT_AFTER_INSERT"):
                        if operation == "assignment":
                            await ManagedAdmission(engine, seed.root).prepare_composed(value)
                        elif operation == "input":
                            await ContractInputs(engine, seed.root).create_input(value)
                        else:
                            await ContractInputs(engine, seed.root).create_context(value)
                assert await totals() == before_denials
            assert observed == ["task-brief", "contract-case-records", "mission"]

            # A fresh process already read the records above; defining-module guards
            # now prove replay/readback does not execute methods or rebind inputs.
            def no_rerun(*args: object, **kwargs: object) -> object:
                raise AssertionError("replay/readback reran PURE or binding")

            with monkeypatch.context() as patcher:
                for module, symbol in (
                    ("omnis.modules.settings.skill_catalog", "evaluate_pure"),
                    ("omnis.modules.settings.candidate_catalog", "evaluate_pure"),
                    ("omnis.modules.tasks.module_registry", "run_handler"),
                    ("omnis.modules.tasks.managed_contract", "build_records"),
                ):
                    patcher.setattr(module + "." + symbol, no_rerun)
                patcher.setattr(ManagedAdmission, "_build", no_rerun)
                patcher.setattr(ContractInputs, "current_source", no_rerun)
                assert (await ContractInputs(engine, seed.root).create_context(context_request))[
                    "created"
                ] is False
                assert (await ContractInputs(engine, seed.root).create_input(input_request))[
                    "created"
                ] is False
                assert (
                    canonical(
                        (await ManagedAdmission(engine, seed.root).prepare_composed(assignment))[
                            "records"
                        ]
                    )
                    == historical
                )
                assert (
                    canonical(
                        (
                            await ManagedAdmission(engine, seed.root).readback(
                                seed.request(command_id=assignment["command_id"])
                            )
                        )["records"]
                    )
                    == historical
                )
            assert await totals() == before_denials
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_records_catalog_exact_admission_replay_and_changed_material_denied(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnis.modules.settings.candidate_catalog import CandidateCatalog

    url = request.getfixturevalue("migrated_database_url")
    dsn = url.render_as_string(hide_password=False)
    qualified, admitted = qualify_records(tmp_path / "records-evaluation", dsn)
    seed = qualified.seed
    input_body = mapping(mapping(admitted["input"])["payload"])
    provenance = mapping(input_body["provenance"])
    assert set(provenance) == {"producer_key", "producer_revision", "command_id", "source_kind"}
    assert provenance["producer_key"] == "contract-case-records"
    assert provenance["producer_revision"] == "contract-case-records-v1"
    assert provenance["source_kind"] == "SYNTHETIC"
    original = seed.request(
        schema_version=3,
        command_id=provenance["command_id"],
        snapshot_ref=qualified.frozen["snapshot_ref"],
        value=EVALUATION_VALUE,
    )

    async def run() -> None:
        engine = database_engine(dsn)
        catalog = CandidateCatalog(engine, seed.root)
        try:
            assert await catalog.dispatch("admit-evaluation-records", original) == admitted
            for operation, delta in (
                ("admit-evaluation-records", {"value": {"records": []}}),
                ("admit-evaluation-records", {"schema_version": 2}),
                ("admit-evaluation-capture", {"schema_version": 2}),
                ("admit-evaluation-records", {"owner_id": str(uuid4())}),
                (
                    "admit-evaluation-records",
                    {
                        "snapshot_ref": {
                            **mapping(qualified.frozen["snapshot_ref"]),
                            "digest": "f" * 64,
                        }
                    },
                ),
            ):
                with pytest.raises(CatalogError):
                    await catalog.dispatch(operation, {**original, **delta})
            with pytest.raises(CatalogError, match="UNBOUND_SLOT"):
                await catalog.dispatch(
                    "evaluate",
                    seed.write(
                        snapshot_ref=qualified.frozen["snapshot_ref"],
                        evaluation_kind="PURE",
                        input=EVALUATION_VALUE,
                    ),
                )
            for reference in (
                {**mapping(admitted["input_ref"]), "kind": "contract-case-input"},
                {**mapping(admitted["input_ref"]), "revision": True},
                {**mapping(admitted["input_ref"]), "revision": 2},
                {**mapping(admitted["input_ref"]), "digest": "f" * 64},
            ):
                with pytest.raises(CatalogError):
                    await catalog.dispatch(
                        "evaluate",
                        seed.write(
                            schema_version=3,
                            snapshot_ref=qualified.frozen["snapshot_ref"],
                            input_ref=reference,
                            evaluation_kind="PURE",
                        ),
                    )
            with pytest.raises(CatalogError):
                await catalog.dispatch(
                    "evaluate",
                    seed.write(
                        schema_version=2,
                        snapshot_ref=qualified.frozen["snapshot_ref"],
                        input_ref=admitted["input_ref"],
                        evaluation_kind="PURE",
                    ),
                )

            def no_evaluation(*args: object, **kwargs: object) -> object:
                raise AssertionError("qualification replay executed methods")

            with monkeypatch.context() as patcher:
                patcher.setattr("omnis.modules.settings.skill_catalog.evaluate_pure", no_evaluation)
                patcher.setattr(
                    "omnis.modules.settings.candidate_catalog.evaluate_pure", no_evaluation
                )
                patcher.setattr("omnis.modules.tasks.module_registry.run_handler", no_evaluation)
                for kind, expected in (("STATIC", qualified.static), ("PURE", qualified.pure)):
                    async with engine.connect() as conn:
                        command_id = str(
                            (
                                await conn.execute(
                                    sql(
                                        "SELECT command_id FROM catalog_command WHERE owner_id=:owner AND operation='evaluate' AND result->'evaluation_ref'->>'id'=:id"
                                    ),
                                    {
                                        "owner": seed.owner,
                                        "id": mapping(expected["evaluation_ref"])["id"],
                                    },
                                )
                            ).scalar_one()
                        )
                    replay = seed.request(
                        schema_version=3,
                        command_id=command_id,
                        snapshot_ref=qualified.frozen["snapshot_ref"],
                        input_ref=admitted["input_ref"],
                        evaluation_kind=kind,
                    )
                    assert await catalog.dispatch("evaluate", replay) == expected
                assert await catalog.dispatch("admit-evaluation-records", original) == admitted

            # New fixture only: change retained bytes, restore read-only mode, then
            # require the real qualifier/readback path to refuse rather than restamp.
            target = (
                seed.root
                / "candidates"
                / str(mapping(qualified.frozen["snapshot_ref"])["id"])
                / "packages/0/templates/procedures/map-records.yaml"
            )
            raw = target.read_bytes()
            target.chmod(0o600)
            target.write_bytes(raw + b"\n")
            target.chmod(0o400)
            with pytest.raises(CatalogError):
                await catalog.dispatch(
                    "admit-evaluation-records", {**original, "command_id": str(uuid4())}
                )
            with pytest.raises(CatalogError):
                await catalog.dispatch(
                    "readback", seed.request(snapshot_ref=qualified.frozen["snapshot_ref"])
                )
        finally:
            await engine.dispose()

    asyncio.run(run())
