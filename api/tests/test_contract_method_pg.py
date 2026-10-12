"""One private PG -> existing owner -> real pinned native CONTRACT/PURE journey.

SOURCE_HOST_NOT_INSTALLED: stock inert stdio + NativePeer + RuntimeHost and
RuntimeClient, not an OCI/installed gate. Only document preparation is the reused
qualification prerequisite double. No native result/runtime/peer is substituted.
The full source pin must already exist; this test never installs or downloads it.
"""

import asyncio
import importlib
import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text as sql

from fixtures.b06b_publication.consumer import canonical, mapping, sequence
from fixtures.b06b_pure_probe.consumer import Probe
from fixtures.c03_journey import publish_capture
from fixtures.c03_records import qualify_records
from omnis.core.db import database_engine
from omnis.modules.instance.schemas import NativePrepareCommand, NativeTaskCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.contract_inputs import ContractInputs
from omnis.modules.runs.managed_admission import BuildSource, ManagedAdmission
from omnis.modules.runs.native_preparation import NativePreparation
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks.managed_contract import integer, manifest_protocol
from omnis.supervisor.native_tasks import NativeTaskOwner
from omnis.supervisor.runtime_client import RuntimeClient
from test_native_preparation import command, worker_fixture

ROOT = Path(__file__).resolve().parents[2]
PIN = Path("/home/kali/.hermes/cache/scratch/contract-method-evidence/pinned")
LIBRARIES = Path(
    "/home/kali/.hermes/installs/87750418cc01d4b0/environments/"
    "c6fe66d0fd3a44a49cf44d34581c3c52/venv/lib/python3.14/site-packages"
)

# Only import routing, fresh environment and a read-only observer around the
# existing stock entrypoint. This is NOT a JSON-RPC emitter or native service.
BOOTSTRAP = r"""
import importlib.abc
import importlib.util
import json
import os
import runpy
import sys
import threading
import time
from pathlib import Path

source, managed, inert, adapter, libraries, home, evidence = map(Path, sys.argv[1:])
if not home.is_dir() or any(home.iterdir()):
    raise ValueError("Fresh home required")
evidence_fd = os.open(evidence, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
def emit(test, status, count=1):
    raw = json.dumps({"test": test, "status": status, "count": count},
                     separators=(",", ":")).encode() + b"\n"
    if os.write(evidence_fd, raw) != len(raw):
        raise RuntimeError("Observer unavailable")
os.environ.clear()
os.environ.update(HOME=str(home), HERMES_HOME=str(home / "hermes"),
    TMPDIR=str(home), HERMES_OMNIS_INERT="1", HERMES_DISABLE_LAZY_INSTALLS="1",
    HERMES_SKIP_NODE_BOOTSTRAP="1", PYTHONDONTWRITEBYTECODE="1", LANG="C.UTF-8")
os.chdir(home)
allowed = (source, managed, inert, adapter, libraries, home,
           Path(sys.executable).resolve().parents[1],
           Path("/home/kali/OmnisAI/api/.venv"))
bootstrap_path = Path(__file__).absolute()

def audit(event, args):
    denied = event in {"socket.connect", "subprocess.Popen", "os.system"}
    if event == "open" and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        denied |= name.endswith((".env", "auth.json", "credentials.json"))
        if name.startswith("/home/kali/"):
            path = Path(name).absolute()
            denied |= path != bootstrap_path and not any(path == p or p in path.parents for p in allowed)
    if denied:
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).absolute()
            category = ("OWN_FRESH_HOME" if path == home or home in path.parents
                        else "OUTSIDE_FRESH_HOME")
            emit("denied-open-origin", category)
            emit("denied-open-caller", sys._getframe(1).f_code.co_name)
            if path.name in {".env", "auth.json", "credentials.json"}:
                emit("denied-credential-file", path.name)
        emit("forbidden-effect", event)
        raise RuntimeError("Forbidden native effect")
sys.addaudithook(audit)

class Overlay(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        relative = Path(*fullname.split("."))
        for overlay in (managed, inert):
            package = overlay / relative / "__init__.py"
            if package.is_file():
                return importlib.util.spec_from_file_location(fullname, package,
                    submodule_search_locations=[str(package.parent), str(source / relative)])
            module = (overlay / relative).with_suffix(".py")
            if module.is_file():
                return importlib.util.spec_from_file_location(fullname, module)
sys.meta_path.insert(0, Overlay())
sys.path[:0] = [str(source), str(adapter)]
# Pure Python libraries only: no active profile, .pth evaluation or site startup.
sys.path.append(str(libraries))
import agent
agent.__path__[:0] = [str(managed / "agent"), str(inert / "agent")]

forbidden = {"init_agent", "_resolve_child_runtime", "run_conversation",
    "handle_function_call", "_init_client", "_resolve_runtime",
    "load_credential_pool", "get_api_key", "discover_builtin_tools", "discover_plugins"}
observed = forbidden | {"run_contract", "_read_bound_input", "run_handler", "_contract_guard", "release", "validate_stage", "stage", "initialize_contract"}
entered = {}
def observe(frame, event, arg):
    if event not in {"call", "return"}:
        return
    name = frame.f_code.co_name
    if name not in observed:
        return
    filename = frame.f_code.co_filename
    native = any(str(root) in filename for root in (source, managed, inert, adapter))
    if not native:
        return
    if name in {"validate_stage", "stage", "initialize_contract"}:
        if event == "call":
            entered[id(frame)] = time.monotonic_ns()
            emit(name, "ENTERED")
        elif id(frame) in entered:
            elapsed = (time.monotonic_ns() - entered.pop(id(frame))) // 1_000_000
            emit(name, "RETURNED_MS", elapsed)
    if event == "call" and name in forbidden:
        emit("forbidden-sink", name)
        raise RuntimeError("Forbidden native sink")
    if event == "call" and name == "run_contract" and "self" in frame.f_locals:
        actual = frame.f_locals.get("self")
        module = sys.modules.get("run_agent")
        real = module is not None and type(actual) is module.AIAgent
        emit("run_contract", "REAL_AIAgent" if real else "WRONG_TYPE")
        if not real:
            raise RuntimeError("Native child is not real")
    if event == "call" and name in {"_read_bound_input", "run_handler"}:
        emit(name, "ENTERED")
    if event == "return" and name == "_contract_guard":
        emit("contract-guard", "APPROVED" if arg is True else "REFUSED")
    if event == "return" and name == "release" and type(arg) is dict:
        if arg.get("protocol") == "omnis-managed-admission-v4":
            emit("native-release", arg.get("status", "UNKNOWN"))
            rows = arg.get("executions", [])
            if type(rows) is list and len(rows) == 1:
                values = rows[0].get("records", [])
                for kind in ("task-result", "contract-tool-receipt", "contract-artifact"):
                    emit(kind, "NATIVE", sum(r.get("kind") == kind for r in values))
sys.setprofile(observe)
threading.setprofile(observe)
emit("observer", "READY")
try:
    runpy.run_module("tui_gateway.entry", run_name="__main__")
except BaseException as error:
    emit("bootstrap-exception", type(error).__name__)
    cursor = error.__traceback__
    while cursor is not None:
        emit("bootstrap-frame", cursor.tb_frame.f_code.co_name)
        emit("bootstrap-source", Path(cursor.tb_frame.f_code.co_filename).name, cursor.tb_lineno)
        cursor = cursor.tb_next
    raise
finally:
    emit("observer", "EXIT")
    os.close(evidence_fd)
"""


class PreparationPrerequisite(RuntimeClient):
    """Only a document-loading prerequisite double; real transport otherwise."""

    async def prepare(
        self,
        service: InstanceService,
        supervisor_owner: object,
        bundle_ref: dict[str, object],
        bundle: dict[str, object],
    ) -> dict[str, object]:
        return {"preparation": worker_fixture(bundle)}


@pytest.mark.skipif(
    os.environ.get("OMNIS_CONTRACT_METHOD_NATIVE_PG") != "1",
    reason="Explicit pinned native SOURCE consumer QA; not default unit/installed evidence",
)
def test_contract_method_real_native_pg_owner_receipts_check_inbox(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = Path(os.environ["TMPDIR"]).resolve(strict=True)
    assert scratch == Path("/home/kali/.hermes/cache/scratch") or scratch.is_relative_to(
        Path("/home/kali/.hermes/cache/scratch")
    )
    assert tmp_path.resolve().is_relative_to(scratch)
    assert PIN.is_dir() and (PIN / "run_agent.py").is_file(), "SOURCE_PIN_REQUIRED"
    assert LIBRARIES.is_dir(), "SOURCE_LIBRARIES_REQUIRED"
    python = ROOT / "api/.venv/bin/python"
    assert python.is_file(), "PINNED_PYTHON_REQUIRED"
    url = request.getfixturevalue("migrated_database_url")
    dsn = url.render_as_string(hide_password=False)
    qualified, evaluation = qualify_records(tmp_path / "qualified", dsn)
    seed = qualified.seed
    _, snapshot = publish_capture(qualified, dsn)
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    selected = probe.success(
        "select",
        probe.write(snapshot_ref=snapshot["snapshot_ref"], recipe_key="records-mapper"),
        dsn,
    )
    bootstrap = tmp_path / "native_bootstrap.py"
    bootstrap.write_text(BOOTSTRAP)
    bootstrap.chmod(0o600)
    home = tmp_path / "native-home"
    home.mkdir(mode=0o700)
    observation = tmp_path / "native-observation.jsonl"
    observation.touch(mode=0o600)
    adapter = ROOT / "integrations/hermes/src"
    monkeypatch.syspath_prepend(str(adapter))
    host_module = importlib.import_module("omnis_hermes.runtime_host")

    async def run() -> None:
        engine = database_engine(dsn)
        service, supervisor = InstanceService(engine), uuid4()
        domain, inputs = ManagedAdmission(engine, seed.root), ContractInputs(engine, seed.root)
        runtime = None
        host = None
        done = asyncio.Event()
        heartbeat: asyncio.Task[None] | None = None
        try:
            epoch = await service.acquire(supervisor)
            status = await service.owned_status(supervisor, epoch)

            async def maintain_owner() -> None:
                # Same real lease producer as the supervisor; no changed TTL,
                # synthetic grant or native deadline extension.
                while not done.is_set():
                    await service.heartbeat(supervisor, epoch)
                    try:
                        await asyncio.wait_for(done.wait(), 0.5)
                    except TimeoutError:
                        pass

            heartbeat = asyncio.create_task(maintain_owner())
            assert str(supervisor) != seed.owner
            # A pytest node name is not a portable AF_UNIX endpoint path.
            directory = scratch / ("cm-" + uuid4().hex)
            assert len(os.fsencode(directory / "runtime.sock")) < 108
            directory.mkdir(mode=0o700)
            runtime = PreparationPrerequisite(directory, generation=status.generation, epoch=epoch)
            host = host_module.RuntimeHost(
                directory,
                _test_launch=host_module.TestLaunch(
                    (
                        str(python),
                        "-I",
                        "-B",
                        str(bootstrap),
                        str(PIN),
                        str(ROOT / "integrations/hermes/upstream/managed-source"),
                        str(ROOT / "integrations/hermes/upstream/inert-source"),
                        str(adapter),
                        str(LIBRARIES),
                        str(home),
                        str(observation),
                    ),
                    home,
                ),
            )
            # Preparation needs the actual fresh host's boot identity, even
            # though its document worker is the explicit prerequisite double.
            runtime.boot = host.boot
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
            context_request = seed.write(
                schema_version=2,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
            )
            context = await inputs.create_method_context(context_request)
            value = {
                "records": [
                    {"method": "POST", "path": "/pure-z/é", "status": 201},
                    {"method": "GET", "path": "/pure-a", "status": 404},
                    {"method": "GET", "path": "/pure-a", "status": 200},
                ]
            }
            input_request = seed.write(
                schema_version=2, context_ref=context["context_ref"], input=value
            )
            original = await inputs.create_input(input_request)
            assert original["input_ref"] != evaluation["input_ref"]
            assignment = seed.write(
                schema_version=3,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
                task_count=1,
                context_ref=context["context_ref"],
                slot_values=[{"slot_name": "records", "refs": [original["input_ref"]]}],
            )
            actual_build = BuildSource.build

            def measured_build(
                source: BuildSource,
                *,
                count: int = 1,
                composed: bool = True,
                context_only: bool = False,
                prefix: list[dict[str, object]] | None = None,
                case_input: dict[str, object] | None = None,
                method_execution: bool = False,
            ) -> list[dict[str, object]]:
                graph = actual_build(
                    source,
                    count=count,
                    composed=composed,
                    context_only=context_only,
                    prefix=prefix,
                    case_input=case_input,
                    method_execution=method_execution,
                )
                # Sizes only: no credentials, payload values or receipt capabilities.
                (tmp_path / "method-build-sizes.json").write_text(
                    json.dumps(
                        {
                            "graph_bytes": len(canonical(graph)),
                            "preparation_bytes": source.preparation_bytes,
                            "total": len(canonical(graph)) + source.preparation_bytes,
                            "records": [
                                {"kind": r["kind"], "bytes": len(canonical(r))} for r in graph
                            ],
                        }
                    )
                )
                return graph

            with monkeypatch.context() as observer:
                observer.setattr(BuildSource, "build", measured_build)
                prepared = await domain.prepare_method(assignment)
            assert manifest_protocol(prepared["manifest"]) == ("omnis-managed-admission-v4")
            lifecycle = {
                "op": "native_task",
                "schema_version": 1,
                "owner_id": seed.owner,
                "command_id": assignment["command_id"],
                "instance_id": str(status.instance_id),
                "expected_epoch": epoch,
                "expected_generation": status.generation,
                "manifest_ref": prepared["manifest_ref"],
            }
            async with host:
                await service.heartbeat(supervisor, epoch)
                await runtime.connect()
                assert (await runtime.launch_inert(service, supervisor))["state"] == "READY"
                await runtime.renew(service, supervisor)
                owner = NativeTaskOwner(domain, service, supervisor, epoch, runtime)
                staged = await owner.handle(
                    NativeTaskCommand.model_validate({**lifecycle, "action": "stage"})
                )
                assert staged["task_status"] == "BOUND"
                # Release immediately after committed stage: the native 4.5s
                # deadline is unchanged. No readback/negative between the two.
                # Fail closed: no direct-native rescue or fabricated final.
                released = await owner.handle(
                    NativeTaskCommand.model_validate({**lifecycle, "action": "release"})
                )
                assert released["task_status"] == "SUCCEEDED"
                assert released["binding_ref"] == staged["binding_ref"]
                back_request = seed.request(command_id=assignment["command_id"])
                back = await domain.readback(back_request)
                binding = mapping(back["binding"])
                assert mapping(mapping(binding["payload"])["authority"])["owner"] == str(supervisor)
                assert mapping(binding["payload"])["runtime_boot"] == runtime.boot
                assert back["status"] == "SUCCEEDED"
                result = mapping(sequence(back["results"])[0])
                assert mapping(result["payload"])["consumed_input_refs"] == [original["input_ref"]]
                assert mapping(result["payload"])["usage"] == {
                    "state": "KNOWN",
                    "model_calls": 0,
                    "target_actions": 0,
                    "cost": "0",
                }
                graph = [mapping(r) for r in sequence(back["records"])]
                receipts = [r for r in graph if r["kind"] == "contract-tool-receipt"]
                artifacts = [r for r in graph if r["kind"] == "contract-artifact"]
                assert len(receipts) == 3 and len(artifacts) == 2
                ordered = sorted(
                    receipts, key=lambda r: integer(mapping(r["payload"])["sequence"], 0)
                )
                assert [mapping(r["payload"])["sequence"] for r in ordered] == [0, 1, 2]
                assert mapping(ordered[0]["payload"])["output_ref"] == original["input_ref"]
                checks = [mapping(r) for r in sequence(back["checks"])]
                assert len(checks) == 1 and mapping(checks[0]["payload"])["status"] == "COMPLETE"
                inbox = mapping(sequence(back["inbox"])[0])
                assert {
                    k: inbox[k]
                    for k in ("delivered", "admitted", "turn_completed", "domain_result_consumed")
                } == {
                    "delivered": True,
                    "admitted": False,
                    "turn_completed": False,
                    "domain_result_consumed": False,
                }
                native = next(r for r in graph if r["kind"] == "native-task-receipt")
                final = mapping(native["payload"])
                fence = mapping(binding["payload"])["authority"]
                # Challenge real received bytes, not an invented execution.
                for bad_boot, bad_final, reason in (
                    (str(uuid4()), final, "LINEAGE_MISMATCH"),
                    (runtime.boot, {**final, "native_root_id": str(uuid4())}, "MANAGED_REJECTED"),
                ):
                    with pytest.raises(CatalogError, match=reason):
                        await domain.ingest_result(
                            seed.owner,
                            prepared["manifest_ref"],
                            bad_final,
                            bad_boot,
                            fence,
                            held=False,
                        )
                    assert canonical((await domain.readback(back_request))["records"]) == canonical(
                        back["records"]
                    )
                malformed = deepcopy(final)
                mapping(sequence(malformed["executions"])[0])["native_child_id"] = str(uuid4())
                with pytest.raises(CatalogError):
                    await domain.ingest_result(
                        seed.owner,
                        prepared["manifest_ref"],
                        malformed,
                        runtime.boot,
                        fence,
                        held=False,
                    )
                # No new native calls/evaluator/actions on replay or durable readback.
                native_before = observation.read_bytes()

                def no_rerun(*args: object, **kwargs: object) -> object:
                    raise AssertionError("REPLAY_RERAN_EXECUTION")

                with monkeypatch.context() as patcher:
                    for module in ("skill_catalog", "candidate_catalog"):
                        patcher.setattr(
                            "omnis.modules.settings." + module + ".evaluate_pure", no_rerun
                        )
                    patcher.setattr("omnis.modules.tasks.module_registry.run_handler", no_rerun)
                    patcher.setattr(ManagedAdmission, "_build", no_rerun)
                    assert (await domain.prepare_method(assignment))["created"] is False
                    assert canonical((await domain.readback(back_request))["records"]) == canonical(
                        back["records"]
                    )
                    assert (
                        await owner.handle(
                            NativeTaskCommand.model_validate({**lifecycle, "action": "release"})
                        )
                    )["task_status"] == "SUCCEEDED"
                    assert (
                        mapping(sequence((await domain.reconcile(back_request))["inbox"])[0])[
                            "domain_result_consumed"
                        ]
                        is True
                    )
                    assert (
                        mapping(sequence((await domain.reconcile(back_request))["inbox"])[0])[
                            "domain_result_consumed"
                        ]
                        is True
                    )
                assert observation.read_bytes() == native_before
                # Historical terminal receipt is receive-only after a real Stop.
                done.set()
                await heartbeat
                await service.shutdown(uuid4(), status.generation, supervisor, epoch)
                prior = await domain.readback(back_request)
                assert canonical(
                    (
                        await domain.ingest_result(
                            seed.owner,
                            prepared["manifest_ref"],
                            final,
                            runtime.boot,
                            fence,
                            held=True,
                        )
                    )["records"]
                ) == canonical(prior["records"])
                assert observation.read_bytes() == native_before
                async with engine.connect() as conn:
                    assert (
                        await conn.execute(sql("SELECT count(*) FROM managed_inbox"))
                    ).scalar_one() == 1
        finally:
            done.set()
            try:
                if heartbeat is not None:
                    await heartbeat
            finally:
                try:
                    if runtime is not None:
                        await runtime.close()
                finally:
                    await engine.dispose()
            if host is not None and host.process is not None:
                assert host.process.returncode is not None, "NATIVE_CLEANUP_UNCERTAIN"
                assert not host._owned_pids(), "NATIVE_FAMILY_UNCERTAIN"
            if host is not None:
                assert not (host.directory / "runtime.sock").exists()
                assert not (host.directory / "runtime.boot").exists()
        rows = [json.loads(line) for line in observation.read_text().splitlines()]
        assert {"test": "observer", "status": "READY", "count": 1} in rows
        assert not any(r["test"].startswith("forbidden-") for r in rows)
        assert [r for r in rows if r["test"] == "run_contract"] == [
            {"test": "run_contract", "status": "REAL_AIAgent", "count": 1}
        ]
        assert len([r for r in rows if r["test"] == "_read_bound_input"]) == 1
        assert len([r for r in rows if r["test"] == "run_handler"]) == 2
        assert {"test": "native-release", "status": "SUCCEEDED", "count": 1} in rows

    asyncio.run(run())
