"""Real PG/copy-installed projection journey; upstream cold transport is a protocol seed.

No SQL/resolver/projection/serializer doubles. No native loader, SDK, provider or
model is executed. The runner owns one fresh UDS/no-network DB and retains data.
"""

import asyncio
import importlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from importlib.abc import MetaPathFinder
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.exc import ProgrammingError

ROOT = Path(__file__).resolve().parents[2]
MARKER = "SYNTHETIC_PRIVATE_MARKER_B06C_PG"


class ProjectionPins(TypedDict):
    projection_ref: object
    owner_id: str
    run_id: str
    binding_ref: object
    policy_digest: str


def _bootstrap(installed: bool) -> dict[str, str]:
    # Only fixture helpers are read from the checkout. Installed runtime imports
    # must resolve before/after setup to site-packages, never api/src.
    if not installed:
        sys.path.insert(0, str(ROOT / "api/src"))
    sys.path.insert(0, str(ROOT / "api/tests"))
    if not installed:
        sys.path.insert(0, str(ROOT / "integrations/hermes/src"))

    class NoNativeProvider(MetaPathFinder):
        def find_spec(self, fullname: str, path: object = None, target: object = None) -> None:
            if fullname.split(".")[0] in {"hermes", "openai", "anthropic", "litellm", "run_agent"}:
                raise AssertionError("Native/provider import outside projection fixture scope")

    sys.meta_path.insert(0, NoNativeProvider())
    origins = {}
    for name in (
        "omnis.policy.model_projection",
        "omnis.modules.runs.model_projection",
        "omnis.modules.tasks.managed_composition",
        "omnis_hermes.model_projection",
    ):
        module = importlib.import_module(name)
        assert module.__file__ is not None
        path = Path(module.__file__).resolve()
        if installed:
            assert Path(sys.prefix).resolve() in path.parents
            assert path.stat().st_nlink == 1
        origins[name] = sha256(path.read_bytes()).hexdigest()
    return origins


async def _produce(directory: Path) -> None:
    from fixtures.b06b_publication.consumer import canonical, mapping, sequence
    from fixtures.b06b_pure_probe.consumer import Probe
    from fixtures.c03_journey import publish_capture
    from fixtures.c03_records import qualify_records
    from omnis.core.db import database_engine
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.contract_inputs import ContractInputs
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.runs.model_projection import ModelProjections
    from omnis.modules.runs.native_preparation import NativePreparation
    from omnis.modules.settings import candidate_store as records
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.policy.model_projection import SyntheticApproval
    from test_managed_contract import stage
    from test_model_projection import text_digests
    from test_native_preparation import command, worker_fixture

    dsn = os.environ["OMNIS_DATABASE_URL"]
    qualified, _ = qualify_records(directory / "seed", dsn)
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
    stopped = asyncio.Event()
    heartbeat: asyncio.Task[None] | None = None

    async def renew(epoch: int) -> None:
        while not stopped.is_set():
            await service.heartbeat(supervisor, epoch)
            try:
                await asyncio.wait_for(stopped.wait(), timeout=1)
            except TimeoutError:
                pass

    # Reuse the declared C03 prerequisite protocol fixture. This is NOT a native
    # loader/root attestation; the projection consumer/resolver/store stay real.
    from omnis.supervisor.runtime_client import RuntimeClient

    class PreparationProtocolSeed(RuntimeClient):
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
        heartbeat = asyncio.create_task(renew(epoch))
        runtime = PreparationProtocolSeed(seed.directory, generation=status.generation, epoch=epoch)
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
        inputs = ContractInputs(engine, seed.root)
        managed = ManagedAdmission(engine, seed.root)
        projections = ModelProjections(managed)
        assignments = []
        for index in range(2):
            context = await inputs.create_context(
                seed.write(
                    schema_version=2,
                    selection_ref=selected["selection_ref"],
                    preparation_command_id=preparation.command_id,
                )
            )
            created_input = await inputs.create_input(
                seed.write(
                    schema_version=2,
                    context_ref=context["context_ref"],
                    input={
                        "records": [
                            {"method": "GET", "path": "/" + MARKER + "?q=" + MARKER, "status": 200}
                        ]
                    },
                )
            )
            prepared = await managed.prepare_composed(
                seed.write(
                    schema_version=3,
                    selection_ref=selected["selection_ref"],
                    preparation_command_id=preparation.command_id,
                    task_count=1,
                    context_ref=context["context_ref"],
                    slot_values=[{"slot_name": "records", "refs": [created_input["input_ref"]]}],
                )
            )
            manifest = mapping(prepared["manifest"])
            assert mapping(manifest["payload"])["resolution"] == "NO_MODEL"
            assert mapping(manifest["payload"])["effective"] is None
            composition = next(
                mapping(r)
                for r in sequence(prepared["records"])
                if mapping(r)["kind"] == "prompt-composition"
            )
            staged = stage(manifest)
            staged["protocol"] = "omnis-managed-admission-v3"
            staged["native_root_id"] = str(staged["native_root_id"]) + "-fixture-" + str(index)
            # Two declared protocol inputs need distinct opaque child/session
            # tokens under one boot; preserve managed_task's real uniqueness.
            for entry in sequence(staged["entries"]):
                value = mapping(entry)
                for field in ("native_child_id", "native_session_id"):
                    value[field] = str(value[field]) + "-fixture-" + str(index)
            fence = {
                "instance_id": str(status.instance_id),
                "owner": str(supervisor),
                "epoch": epoch,
                "generation": status.generation,
            }
            async with service.native_preparation_commit(
                supervisor, epoch, status.generation
            ) as conn:
                await managed.reserve_dispatch(conn, seed.owner, prepared["manifest_ref"], "stage")
            async with service.native_preparation_commit(
                supervisor, epoch, status.generation
            ) as conn:
                binding = await managed.commit_binding(
                    conn, seed.owner, prepared["manifest_ref"], staged, runtime.boot, fence
                )
            assignments.append(
                {
                    "manifest": manifest,
                    "composition": composition,
                    "binding": binding,
                    "input_ref": created_input["input_ref"],
                    "context_ref": context["context_ref"],
                }
            )
            assert index == len(assignments) - 1
        actual, foreign = assignments
        manifest, composition, binding = [
            mapping(actual[k]) for k in ("manifest", "composition", "binding")
        ]
        run = str(mapping(manifest["payload"])["run_id"])
        approval = SyntheticApproval(
            seed.owner,
            run,
            canonical(records.reference(composition)),
            text_digests(composition),
            (),
        )
        args = (
            seed.owner,
            records.reference(manifest),
            records.reference(binding),
            records.reference(composition),
        )

        async def count() -> int:
            async with engine.connect() as conn:
                return int(
                    (
                        await conn.execute(
                            sql(
                                "SELECT count(*) FROM managed_record WHERE owner_id=:owner AND envelope->>'kind'='model-projection'"
                            ),
                            {"owner": seed.owner},
                        )
                    ).scalar_one()
                )

        assert await count() == 0
        # Actual post-INSERT transaction abort, not a mocked storage outcome.
        with pytest.raises(RuntimeError, match="OWNED_TRANSACTION_ABORT"):
            async with engine.begin() as conn:
                await projections.prepare(conn, *args, approval)
                assert (
                    await conn.execute(
                        sql(
                            "SELECT count(*) FROM managed_record WHERE owner_id=:owner AND envelope->>'kind'='model-projection'"
                        ),
                        {"owner": seed.owner},
                    )
                ).scalar_one() == 1
                raise RuntimeError("OWNED_TRANSACTION_ABORT")
        assert await count() == 0
        async with engine.begin() as conn:
            projected = await projections.prepare(conn, *args, approval)
        assert await count() == 1
        async with engine.begin() as conn:
            assert await projections.prepare(conn, *args, approval) == projected
        assert await count() == 1
        source_bytes = canonical(
            (await managed.readback_manifest(seed.owner, records.reference(manifest)))["records"]
        )
        assert MARKER.encode() in source_bytes
        assert MARKER.encode() not in canonical(projected)
        with pytest.raises(ProgrammingError):
            async with engine.begin() as conn:
                await conn.execute(
                    sql("UPDATE managed_record SET envelope=envelope WHERE id=:id"),
                    {"id": projected["id"]},
                )
        foreign_refs = [
            records.reference(mapping(foreign[k])) for k in ("manifest", "binding", "composition")
        ]
        prepare_denials = [
            (str(uuid4()), args[1], args[2], args[3], approval),
            (seed.owner, foreign_refs[0], args[2], args[3], approval),
            (seed.owner, args[1], foreign_refs[1], args[3], approval),
            (seed.owner, args[1], args[2], foreign_refs[2], approval),
            (*args, replace(approval, run_id=str(uuid4()))),
            (*args, replace(approval, approved_text_digests=frozenset())),
            (*args, replace(approval, known_secrets=("NO_MODEL",))),
        ]
        for denied in prepare_denials:
            with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED") as error:
                async with engine.begin() as conn:
                    await projections.prepare(conn, *denied)
            assert str(error.value) == "MODEL_PROJECTION_REJECTED"
            assert await count() == 1
        ref = records.reference(projected)
        read_denials = [
            (str(uuid4()), run, ref),
            (seed.owner, str(uuid4()), ref),
            *[
                (seed.owner, run, {**ref, **delta})
                for delta in (
                    {"revision": 2},
                    {"revision": True},
                    {"digest": "0" * 64},
                    {"kind": "prompt-composition"},
                    {"id": str(uuid4())},
                )
            ],
        ]
        for owner, run_pin, projection_pin in read_denials:
            with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED"):
                async with engine.begin() as conn:
                    await projections.read(conn, owner, run_pin, projection_pin, approval)
            assert await count() == 1
        # Unknown raw fields must be denied by the actual source-value producer,
        # before a new immutable input or projection can appear.
        async with engine.connect() as conn:
            input_count = (
                await conn.execute(
                    sql(
                        "SELECT count(*) FROM managed_record WHERE owner_id=:owner AND envelope->>'kind'='contract-case-records'"
                    ),
                    {"owner": seed.owner},
                )
            ).scalar_one()
        for field in (
            "body",
            "headers",
            "cookies",
            "storageState",
            "stack_trace",
            "evidence_bytes",
            "screenshot",
        ):
            with pytest.raises(CatalogError, match="INVALID_CASE_INPUT"):
                await inputs.create_input(
                    seed.write(
                        schema_version=2,
                        context_ref=actual["context_ref"],
                        input={"records": [], field: MARKER},
                    )
                )
            assert await count() == 1
            async with engine.connect() as conn:
                assert (
                    await conn.execute(
                        sql(
                            "SELECT count(*) FROM managed_record WHERE owner_id=:owner AND envelope->>'kind'='contract-case-records'"
                        ),
                        {"owner": seed.owner},
                    )
                ).scalar_one() == input_count
        async with engine.begin() as conn:
            assert await projections.read(conn, seed.owner, run, ref, approval) == projected
        (directory / "trusted-read.json").write_bytes(
            canonical(
                {
                    "owner_id": seed.owner,
                    "run_id": run,
                    "projection_ref": ref,
                    "manifest_ref": args[1],
                    "binding_ref": args[2],
                    "composition_ref": args[3],
                    "catalog_root": str(seed.root),
                    "approved_text_digests": sorted(approval.approved_text_digests),
                }
            )
        )
        (directory / "expected-projection.json").write_bytes(canonical(projected))
        (directory / "producer-report.json").write_bytes(
            canonical(
                {
                    "status": "PASS_SCOPED",
                    "projection_ref": ref,
                    "projection_digest": mapping(projected["payload"])["projection_digest"],
                    "transaction_abort": True,
                    "replay_exact": True,
                    "immutable": True,
                    "prepare_denials": len(prepare_denials),
                    "read_denials": len(read_denials),
                    "source_extra_denials": 7,
                    "private_marker_retained": True,
                    "projection_marker_absent": True,
                    "upstream": "SYNTHETIC_PROTOCOL_SEED_NOT_NATIVE_PROOF",
                    "zero_model_provider_target": "STRUCTURAL_NO_MODEL; native/provider imports forbidden",
                }
            )
        )
        stopped.set()
        await heartbeat
        heartbeat = None
        await service.shutdown(uuid4(), status.generation, supervisor, epoch)
    finally:
        stopped.set()
        if heartbeat is not None:
            await heartbeat
        await engine.dispose()


async def _read(directory: Path) -> None:
    from fixtures.b06b_publication.consumer import canonical, mapping, sequence
    from omnis.core.db import database_engine
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.runs.model_projection import ModelProjections
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.policy.model_projection import POLICY_DIGEST, SyntheticApproval

    # Optional integration package exists only in the declared copy installation,
    # not in the ordinary API environment used by the canonical type checker.
    adapter = importlib.import_module("omnis_hermes.model_projection")
    serialize_model_input = adapter.serialize_model_input
    validate_serialized_input = adapter.validate_serialized_input

    data = mapping(json.loads((directory / "trusted-read.json").read_bytes()))
    owner, run = str(data["owner_id"]), str(data["run_id"])
    approval = SyntheticApproval(
        owner,
        run,
        canonical(data["composition_ref"]),
        frozenset(str(v) for v in sequence(data["approved_text_digests"])),
        (),
    )
    expected = mapping(json.loads((directory / "expected-projection.json").read_bytes()))
    engine = database_engine(os.environ["OMNIS_DATABASE_URL"])
    try:
        service = ModelProjections(ManagedAdmission(engine, Path(str(data["catalog_root"]))))
        async with engine.begin() as conn:
            projected = await service.read(conn, owner, run, data["projection_ref"], approval)
        assert canonical(projected) == canonical(expected)
        pins: ProjectionPins = {
            "projection_ref": data["projection_ref"],
            "owner_id": owner,
            "run_id": run,
            "binding_ref": data["binding_ref"],
            "policy_digest": POLICY_DIGEST,
        }
        raw = serialize_model_input(projected, **pins)
        assert validate_serialized_input(raw, projected, **pins) == raw
        assert sha256(raw).hexdigest() == mapping(projected["payload"])["projection_digest"]
        assert MARKER.encode() not in raw
        user = mapping(
            json.loads(str(mapping(sequence(mapping(json.loads(raw))["messages"])[1])["content"]))
        )
        assert user["records"] == [
            {"index": 0, "method": "GET", "path": "/[redacted]", "status": 200}
        ]
        denied_channels = (
            "body",
            "headers",
            "cookies",
            "storageState",
            "history",
            "tool_results",
            "error",
            "log",
            "screenshot",
            "option_labels",
        )
        for channel in denied_channels:
            bad = {**mapping(json.loads(raw)), channel: MARKER}
            with pytest.raises(ValueError, match="Invalid model projection") as error:
                validate_serialized_input(canonical(bad), projected, **pins)
            assert MARKER not in str(error.value)
        for invalid_raw in (raw + b"\n", b" " * 32769, b'{"tools":[],"tools":[]}'):
            with pytest.raises(ValueError, match="Invalid model projection"):
                validate_serialized_input(invalid_raw, projected, **pins)
        stale_pins: ProjectionPins = {**pins, "policy_digest": "0" * 64}
        with pytest.raises(ValueError, match="Invalid model projection"):
            serialize_model_input(projected, **stale_pins)
        async with engine.begin() as conn:
            replay = await service.prepare(
                conn,
                owner,
                data["manifest_ref"],
                data["binding_ref"],
                data["composition_ref"],
                approval,
            )
            assert canonical(replay) == canonical(expected)
            count = (
                await conn.execute(
                    sql(
                        "SELECT count(*) FROM managed_record WHERE owner_id=:owner AND envelope->>'kind'='model-projection'"
                    ),
                    {"owner": owner},
                )
            ).scalar_one()
            assert count == 1
        with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED"):
            async with engine.begin() as conn:
                await service.read(
                    conn,
                    owner,
                    run,
                    data["projection_ref"],
                    replace(approval, known_secrets=("NO_MODEL",)),
                )
        (directory / "carrier.json").write_bytes(raw)
        (directory / "reader-report.json").write_bytes(
            canonical(
                {
                    "status": "PASS_SCOPED",
                    "projection_ref": data["projection_ref"],
                    "projection_digest": sha256(raw).hexdigest(),
                    "carrier_bytes": len(raw),
                    "restart_process_readback": True,
                    "replay_count": 1,
                    "carrier_extra_denials": len(denied_channels),
                    "carrier_bytes_denials": 3,
                    "known_secret_read_denied": True,
                    "full_sdk_native_consumer": "NOT_INTEGRATED",
                }
            )
        )
    finally:
        await engine.dispose()


def test_pg_projection_persistent_restart_and_copy_installed(tmp_path: Path) -> None:
    from sqlalchemy.engine import make_url

    from conftest import connect_test_database, verify_test_database

    raw_dsn = os.environ.get("OMNIS_TEST_DATABASE_URL")
    assert raw_dsn, "Dedicated owned fixture required"
    url = make_url(raw_dsn)
    receipt = verify_test_database(url)
    assert url.database == "omnis_test"
    with connect_test_database(url) as conn:
        assert conn.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        ).fetchone() == (0,)
    root = Path(os.environ["TMPDIR"])
    installed = root / "installed/venv/bin/python"
    manifest = json.loads((root / "installed-origin.json").read_bytes())
    assert installed.is_file() and manifest["python"] == str(installed)
    directory = root / "projection-journey"
    directory.mkdir(mode=0o700)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root / "home"),
        "TMPDIR": str(root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "OMNIS_DATABASE_URL": raw_dsn,
        "OMNIS_EXPECTED_SYSTEM_ID": receipt.system_identifier,
        "OMNIS_B06B_INSTALLED": "1",
        "OMNIS_B06B_PYTHON": str(installed),
    }
    migration = subprocess.run(
        [str(installed), "-I", "-B", "-m", "omnis.migrate", "--initialize"],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert migration.returncode == 0, "Real installed migration failed"
    for mode in ("produce", "read"):
        completed = subprocess.run(
            [str(installed), "-I", "-B", str(Path(__file__).resolve()), mode, str(directory)],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert completed.returncode == 0, (
            f"{mode}: exit={completed.returncode}; {completed.stderr[-2000:]}"
        )
        assert MARKER not in completed.stdout + completed.stderr
        result = json.loads(completed.stdout)
        assert result["status"] == "PASS_SCOPED" and result["mode"] == mode
        assert result["origins"] == {
            name: value["sha256"] for name, value in manifest["origins"].items()
        }
    producer = json.loads((directory / "producer-report.json").read_bytes())
    reader = json.loads((directory / "reader-report.json").read_bytes())
    assert producer["projection_ref"] == reader["projection_ref"]
    assert producer["projection_digest"] == reader["projection_digest"]
    with connect_test_database(url) as conn:
        assert conn.execute(
            "SELECT count(*) FROM managed_record WHERE envelope->>'kind'='model-projection'"
        ).fetchone() == (1,)
        assert conn.execute(
            "SELECT count(*) FROM managed_record WHERE envelope->>'kind'='runtime-binding'"
        ).fetchone() == (2,)
    # Keep the actual base DB and private synthetic corpus; no DROP/cleanup here.
    # The existing runner drains family, retires its exact CID and retains PGDATA.
    assert (directory / "carrier.json").is_file()


if __name__ == "__main__":
    assert len(sys.argv) == 3 and sys.argv[1] in ("produce", "read")
    os.environ["OMNIS_B06B_INSTALLED"] = "1"
    os.environ["OMNIS_B06B_PYTHON"] = sys.executable
    origins = _bootstrap(installed=True)
    mode, directory = sys.argv[1], Path(sys.argv[2])
    asyncio.run(_produce(directory) if mode == "produce" else _read(directory))
    assert not {"hermes", "openai", "anthropic", "litellm", "run_agent"}.intersection(sys.modules)
    print(json.dumps({"status": "PASS_SCOPED", "mode": mode, "origins": origins}))
