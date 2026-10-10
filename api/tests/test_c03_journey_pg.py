"""C03 real PG/CLI tracer. Native preparation double is explicit, not installed QA."""

import asyncio
import importlib
import json
import subprocess
import sys
from copy import deepcopy
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
from fixtures.c03_journey import publish_capture, qualify_capture
from omnis.core.db import database_engine
from omnis.modules.instance.schemas import NativePrepareCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import blocked_result
from omnis.supervisor.runtime_client import RuntimeClient
from test_native_preparation import command, worker_fixture


def test_c03_published_input_cli_assignment_and_replay(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = request.getfixturevalue("migrated_database_url")
    dsn = url.render_as_string(hide_password=False)
    qualified, evaluation = qualify_capture(tmp_path / "c03-run", dsn)
    seed = qualified.seed
    published, snapshot = publish_capture(qualified, dsn)
    release_before = canonical(
        seed.success("readback", seed.request(publication_ref=published["publication_ref"]), dsn)
    )
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    selected = probe.success(
        "select",
        probe.write(snapshot_ref=snapshot["snapshot_ref"], recipe_key="capture-mapper"),
        dsn,
    )

    def cli(
        module: str,
        operation: str,
        value: dict[str, object],
        expected: int = 0,
        raw: bytes | None = None,
    ) -> dict[str, object]:
        path = seed.directory / ("c03-" + uuid4().hex + ".json")
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
        assert result.returncode in (0, 2), f"CLI unexpected exit={result.returncode}"
        output = strict_json(result.stdout if result.returncode == 0 else result.stderr)
        assert result.returncode == expected, (
            f"CLI {operation} exit={result.returncode} reason={output.get('reason')}"
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
            producer = "omnis.modules.runs.contract_inputs"
            consumer = "omnis.modules.runs.managed_admission"
            context_request = seed.write(
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
            )
            context = cli(producer, "create-context", context_request)
            input_request = seed.write(
                context_ref=context["context_ref"],
                input={"capture": '[{"method":"POST","path":"/new-run-value","status":201}]'},
            )
            created_input = cli(producer, "create-input", input_request)
            assert created_input["input_ref"] != evaluation["input_ref"]
            input_read = cli(
                producer, "read-input", seed.request(command_id=input_request["command_id"])
            )
            assert (
                mapping(mapping(input_read["input"])["payload"])["value"] == input_request["input"]
            )
            assert mapping(mapping(input_read["context"])["payload"])["namespace"] == "RUN"
            assert cli(producer, "create-input", input_request)["created"] is False
            assert (
                cli(producer, "create-input", {**input_request, "input": {"capture": "[]"}}, 2)[
                    "reason"
                ]
                == "COMMAND_CONFLICT"
            )
            assignment = seed.write(
                schema_version=2,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
                task_count=1,
                context_ref=context["context_ref"],
                slot_values=[{"slot_name": "capture", "refs": [created_input["input_ref"]]}],
            )
            prepared = cli(consumer, "prepare-composed", assignment)
            assert prepared["created"] is True and prepared["stage_started"] is False
            graph = [mapping(r) for r in sequence(prepared["records"])]
            brief = mapping(sequence(prepared["briefs"])[0])
            bound = next(r for r in graph if r["kind"] == "bound-procedure")
            assert (
                len(sequence(mapping(mapping(brief["payload"])["method_plan"])["requirements"]))
                == 2
            )
            assert mapping(mapping(bound["payload"])["resolved_procedure"])["slots"] == []
            composition = next(r for r in graph if r["kind"] == "prompt-composition")
            sections = sequence(json.loads(str(mapping(composition["payload"])["text"])))
            material = mapping(sections[4])
            assert mapping(mapping(material["input"])["payload"])["value"] == input_request["input"]
            assert mapping(blocked_result(brief)["payload"])["consumed_input_refs"] == []
            historical = canonical(prepared["records"])
            replay = cli(consumer, "prepare-composed", assignment)
            assert replay["created"] is False and canonical(replay["records"]) == historical
            assert (
                cli(
                    consumer,
                    "prepare-composed",
                    {
                        **assignment,
                        "slot_values": [
                            {"slot_name": "capture", "refs": [evaluation["input_ref"]]}
                        ],
                    },
                    2,
                )["reason"]
                == "COMMAND_CONFLICT"
            )
            managed = ManagedAdmission(engine, seed.root)
            async with engine.begin() as conn:
                stage = await managed.stage_payload(conn, seed.owner, prepared["manifest_ref"])
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_task"))
                ).scalar_one() == 1
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integrations/hermes/src"))
            try:
                native = importlib.import_module("omnis_hermes.managed_admission_contract")
                assert native.validate_stage(stage) == prepared["manifest"]
            finally:
                sys.path.pop(0)

            # A new context/assignment consumes a different value; the first stays frozen.
            second_context = cli(
                producer, "create-context", {**context_request, "command_id": str(uuid4())}
            )
            second_input = cli(
                producer,
                "create-input",
                seed.write(context_ref=second_context["context_ref"], input={"capture": "[]"}),
            )
            second = cli(
                consumer,
                "prepare-composed",
                {
                    **assignment,
                    "command_id": str(uuid4()),
                    "context_ref": second_context["context_ref"],
                    "slot_values": [{"slot_name": "capture", "refs": [second_input["input_ref"]]}],
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
            for index in (0, 1):
                assert (
                    mapping(mapping(sections[index])["record"])["payload"]
                    == mapping(mapping(second_sections[index])["record"])["payload"]
                )
            assert mapping(mapping(mapping(second_sections[4])["input"])["payload"])["value"] == {
                "capture": "[]"
            }

            # Slow denials use a fresh, never-dispatched context, not the positive lease.
            denied_context = cli(
                producer, "create-context", {**context_request, "command_id": str(uuid4())}
            )
            denied_input = cli(
                producer,
                "create-input",
                seed.write(context_ref=denied_context["context_ref"], input={"capture": "[]"}),
            )
            negative_base = {
                **assignment,
                "command_id": str(uuid4()),
                "context_ref": denied_context["context_ref"],
                "slot_values": [{"slot_name": "capture", "refs": [denied_input["input_ref"]]}],
            }
            bad_refs = [
                ("absent", {**mapping(denied_input["input_ref"]), "id": str(uuid4())}),
                ("foreign-context", second_input["input_ref"]),
                ("evaluation-namespace", evaluation["input_ref"]),
                ("kind", {**mapping(denied_input["input_ref"]), "kind": "pure-probe-input"}),
                ("revision", {**mapping(denied_input["input_ref"]), "revision": 2}),
                ("digest", {**mapping(denied_input["input_ref"]), "digest": "f" * 64}),
                ("bool-revision", {**mapping(denied_input["input_ref"]), "revision": True}),
            ]
            mutations: list[tuple[str, dict[str, object]]] = [
                (
                    label,
                    {
                        **negative_base,
                        "command_id": str(uuid4()),
                        "slot_values": [{"slot_name": "capture", "refs": [bad]}],
                    },
                )
                for label, bad in bad_refs
            ]
            for label, slots in (
                ("missing-slot", []),
                ("unknown-slot", [{"slot_name": "unknown", "refs": [denied_input["input_ref"]]}]),
                ("duplicate-slot", sequence(negative_base["slot_values"]) * 2),
                ("zero-items", [{"slot_name": "capture", "refs": []}]),
                (
                    "overflow-items",
                    [{"slot_name": "capture", "refs": [denied_input["input_ref"]] * 2}],
                ),
            ):
                mutations.append(
                    (label, {**negative_base, "command_id": str(uuid4()), "slot_values": slots})
                )
            missing = deepcopy(negative_base)
            del missing["slot_values"]
            mutations.extend(
                [
                    ("missing-field", missing),
                    ("owner", {**negative_base, "owner_id": str(uuid4())}),
                    ("substitute-slotless-command", {**negative_base, "schema_version": 1}),
                ]
            )
            async with engine.begin() as conn:
                before_count = (
                    await conn.execute(sql("SELECT count(*) FROM managed_record"))
                ).scalar_one()
            denials: list[dict[str, object]] = []
            for label, invalid in mutations:
                result = cli(consumer, "prepare-composed", invalid, 2)
                assert result["reason"] not in {"DATABASE_UNAVAILABLE", "INPUT_UNAVAILABLE"}
                denials.append({"id": label, "reason": result["reason"]})
            for label, bad_value in (
                ("schema-type", True),
                ("leading-bom", "\ufeff[]"),
                ("control", "\x85"),
                ("unicode-byte-overflow", "é" * 2049),
            ):
                result = cli(
                    producer,
                    "create-input",
                    seed.write(
                        context_ref=denied_context["context_ref"], input={"capture": bad_value}
                    ),
                    2,
                )
                assert result["reason"] not in {"DATABASE_UNAVAILABLE", "INPUT_UNAVAILABLE"}
                denials.append({"id": label, "reason": result["reason"]})
            valid_wire = seed.write(
                context_ref=denied_context["context_ref"], input={"capture": "[]"}
            )
            for label, raw in (
                ("utf8", b"\xff"),
                ("json-bom", b"\xef\xbb\xbf" + canonical(valid_wire)),
                ("duplicate-key", canonical(valid_wire)[:-1] + b',"input":{"capture":"[]"}}'),
            ):
                result = cli(producer, "create-input", valid_wire, 2, raw)
                assert result["reason"] not in {"DATABASE_UNAVAILABLE", "INPUT_UNAVAILABLE"}
                denials.append({"id": label, "reason": result["reason"]})
            async with engine.begin() as conn:
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_record"))
                ).scalar_one() == before_count
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_run"))
                ).scalar_one() == 2
                assert (
                    await conn.execute(
                        sql(
                            "SELECT count(*) FROM managed_run WHERE stage_started OR release_started"
                        )
                    )
                ).scalar_one() == 0
            (seed.directory / "denials.json").write_bytes(canonical(denials))

            original_put = managed_store.put
            written: list[str] = []

            async def fail_after_write(
                conn: AsyncConnection, owner: str, run_id: str, value: object
            ) -> None:
                await original_put(conn, owner, run_id, value)
                if mapping(value)["kind"] == "bound-procedure":
                    written.append("bound-procedure")
                    raise RuntimeError("owned test cut after actual graph insert")

            with monkeypatch.context() as patched:
                patched.setattr(managed_store, "put", fail_after_write)
                with pytest.raises(RuntimeError, match="owned test cut"):
                    await ManagedAdmission(engine, seed.root).prepare_composed(negative_base)
            assert written == ["bound-procedure"]
            async with engine.begin() as conn:
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_record"))
                ).scalar_one() == before_count
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_run"))
                ).scalar_one() == 2

            # Observe the second transaction waiting on the real owner lock.
            ready, release = asyncio.Event(), asyncio.Event()
            holder_pid: list[int] = []
            original_build = ManagedAdmission._build

            async def paused_build(
                self: ManagedAdmission, conn: AsyncConnection, owner: str, value: dict[str, object]
            ) -> list[dict[str, object]]:
                holder_pid.append(
                    int((await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one())
                )
                result = await original_build(self, conn, owner, value)
                ready.set()
                await release.wait()
                return result

            concurrent: list[asyncio.Task[dict[str, object]]] = []
            with monkeypatch.context() as patched:
                patched.setattr(ManagedAdmission, "_build", paused_build)
                try:
                    concurrent.append(
                        asyncio.create_task(
                            ManagedAdmission(engine, seed.root).prepare_composed(negative_base)
                        )
                    )
                    await asyncio.wait_for(ready.wait(), 5)
                    concurrent.append(
                        asyncio.create_task(
                            ManagedAdmission(engine, seed.root).prepare_composed(negative_base)
                        )
                    )
                    observed_wait = False
                    async with asyncio.timeout(3):
                        while not observed_wait:
                            async with engine.connect() as observer:
                                observed_wait = bool(
                                    (
                                        await observer.execute(
                                            sql(
                                                "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE :holder = ANY(pg_blocking_pids(pid)))"
                                            ),
                                            {"holder": holder_pid[0]},
                                        )
                                    ).scalar_one()
                                )
                            if not observed_wait:
                                await asyncio.sleep(0.01)
                    assert observed_wait
                finally:
                    release.set()
                    outcomes = await asyncio.wait_for(asyncio.gather(*concurrent), 15)
            assert [o["created"] for o in outcomes] == [True, False]
            assert outcomes[0]["manifest_ref"] == outcomes[1]["manifest_ref"]
            async with engine.begin() as conn:
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_run"))
                ).scalar_one() == 3
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_task"))
                ).scalar_one() == 3

            def forbidden(*args: object, **kwargs: object) -> object:
                raise AssertionError("historical readback/replay executed or rebound")

            with monkeypatch.context() as patched:
                patched.setattr("omnis.modules.settings.candidate_catalog.evaluate_pure", forbidden)
                patched.setattr("omnis.modules.settings.skill_catalog.evaluate_pure", forbidden)
                patched.setattr("omnis.modules.tasks.managed_contract.build_records", forbidden)
                back = await ManagedAdmission(engine, seed.root).readback(
                    seed.request(command_id=assignment["command_id"])
                )
                assert canonical(back["records"]) == historical
                again = await ManagedAdmission(engine, seed.root).prepare_composed(assignment)
                assert again["created"] is False and canonical(again["records"]) == historical
            async with engine.begin() as conn:
                assert len(
                    await managed_store.graph(conn, seed.owner, str(prepared["run_id"]))
                ) == len(graph)
            retained = seed.success(
                "readback", seed.request(publication_ref=published["publication_ref"]), dsn
            )
            assert canonical(retained) == release_before
        finally:
            await engine.dispose()

    asyncio.run(run())
