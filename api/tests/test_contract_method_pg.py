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

from fixtures.b06b_publication.consumer import canonical, mapping, sequence, sha
from fixtures.b06b_pure_probe.consumer import Probe
from fixtures.c03_journey import publish_capture
from fixtures.c03_records import qualify_records
from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlCode, ControlConflict
from omnis.modules.instance.schemas import NativePrepareCommand, NativeTaskCommand
from omnis.modules.instance.service import InstanceService, RuntimeAuthority
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
observed = forbidden | {"run_contract", "_read_bound_input", "run_handler", "_contract_guard", "release", "validate_stage", "stage", "initialize_contract", "predicate_values"}
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
    if event == "return" and name == "predicate_values" and type(arg) is dict and arg:
        emit("bound-predicates", "SATISFIED" if all(v is True for v in arg.values()) else "GAP", len(arg))
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


# Instrument only forbidden execution aliases, then call the existing managed
# CLI entry in a NEW interpreter. No emitter, evaluator, owner or reader double.
RESTART_READER = r"""
import importlib
import json
import os
import sys
from pathlib import Path
source, observer = sys.argv[1:3]
sys.path.insert(0, source)
fd = os.open(observer, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
def emit(status, name):
    raw = json.dumps({"status": status, "name": name, "pid": os.getpid()}).encode() + b"\n"
    if os.write(fd, raw) != len(raw):
        raise RuntimeError("Observer unavailable")
def deny(name):
    def guard(*args, **kwargs):
        emit("FORBIDDEN", name)
        raise AssertionError("RESTART_RERAN_EXECUTION")
    return guard
for name in ("skill_catalog", "candidate_catalog"):
    module = importlib.import_module("omnis.modules.settings." + name)
    module.evaluate_pure = deny(name + ".evaluate_pure")
module = importlib.import_module("omnis.modules.runs.pure_probe")
module.evaluate_pure = deny("pure_probe.evaluate_pure")
module = importlib.import_module("omnis.modules.tasks.module_registry")
module.run_handler = deny("module_registry.run_handler")
module = importlib.import_module("omnis.modules.runs.managed_admission")
module.BuildSource.build = deny("BuildSource.build")
module.ManagedAdmission._build = deny("ManagedAdmission._build")
client = importlib.import_module("omnis.supervisor.runtime_client")
client.RuntimeClient.__init__ = deny("RuntimeClient.__init__")
emit("READY", "managed-cli")
try:
    code = module.main(sys.argv[3:])
    emit("EXIT", str(code))
    raise SystemExit(code)
finally:
    os.close(fd)
"""


def require_empty_stderr(stderr: bytes) -> None:
    """Refuse contradictory diagnostics without pytest rendering private bytes."""
    if stderr:
        raise AssertionError("RESTART_CLI_CONTRADICTORY_DIAGNOSTIC") from None


def test_restart_stderr_refusal_keeps_private_bytes_out_of_pytest_report() -> None:
    require_empty_stderr(b"")
    marker = b"PUBLIC_SYNTHETIC_PRIVATE_DIAGNOSTIC"
    with pytest.raises(AssertionError) as refused:
        require_empty_stderr(marker)
    assert str(refused.value) == "RESTART_CLI_CONTRADICTORY_DIAGNOSTIC"
    for style in ("line", "short"):
        assert marker.decode() not in str(refused.getrepr(style=style))


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
@pytest.mark.parametrize(
    "first_final_after_stop,with_criteria,lost_reply,legacy_criteria",
    [
        (False, False, False, False),
        (False, True, False, False),
        (False, True, False, True),
        (True, True, False, False),
        (False, True, True, False),
        (True, True, True, False),
    ],
    ids=[
        "support-zero",
        "criteria-normal",
        "criteria-legacy717",
        "criteria-first-late-held",
        "lost-reply",
        "lost-reply-post-stop",
    ],
)
def test_contract_method_real_native_pg_owner_receipts_check_inbox(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_final_after_stop: bool,
    with_criteria: bool,
    lost_reply: bool,
    legacy_criteria: bool,
) -> None:
    scratch = Path(os.environ["TMPDIR"]).resolve(strict=True)
    assert scratch == Path("/home/kali/.hermes/cache/scratch") or scratch.is_relative_to(
        Path("/home/kali/.hermes/cache/scratch")
    )
    assert tmp_path.resolve().is_relative_to(scratch)
    assert PIN.is_dir() and (PIN / "run_agent.py").is_file(), "SOURCE_PIN_REQUIRED"
    assert LIBRARIES.is_dir(), "SOURCE_LIBRARIES_REQUIRED"
    # Use the exact pinned interpreter spelling: a worktree .venv alias changes
    # sys.prefix/import paths and is correctly outside the native audit roots.
    python = Path("/home/kali/OmnisAI/api/.venv/bin/python")
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
    proof_path = tmp_path / "method-history-proof.json"
    proof: dict[str, object] = {"first_final_after_stop": first_final_after_stop}

    def checkpoint(**fields: object) -> None:
        proof.update(fields)
        proof_path.write_bytes(canonical(proof))
        proof_path.chmod(0o600)

    async def restarted_cli(operation: str, back_request: dict[str, object]) -> dict[str, object]:
        path = tmp_path / ("restart-request-" + uuid4().hex + ".json")
        path.write_bytes(canonical(back_request))
        path.chmod(0o600)
        audit = tmp_path / ("restart-observer-" + uuid4().hex + ".jsonl")
        audit.touch(mode=0o600)
        child = await asyncio.create_subprocess_exec(
            str(python),
            "-I",
            "-B",
            "-c",
            RESTART_READER,
            str(ROOT / "api/src"),
            str(audit),
            operation,
            "--request",
            str(path),
            "--catalog-root",
            str(seed.root),
            cwd=tmp_path,
            env=seed.environment(dsn),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), 15)
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()
        # Diagnostic bytes stay private, including if the CLI unexpectedly fails.
        for suffix, raw in (("stdout", stdout), ("stderr", stderr)):
            output = audit.with_suffix("." + suffix)
            output.write_bytes(raw)
            output.chmod(0o600)
        events = [json.loads(line) for line in audit.read_text().splitlines()]
        assert events == [
            {"status": "READY", "name": "managed-cli", "pid": child.pid},
            {"status": "EXIT", "name": "0", "pid": child.pid},
        ], "RESTART_EXECUTION_OR_OBSERVER_FAILURE"
        assert child.pid != os.getpid()
        assert child.returncode == 0, "RESTART_CLI_FAILED"
        require_empty_stderr(stderr)
        checkpoint(
            restart_processes=[
                *sequence(proof.get("restart_processes", [])),
                {
                    "operation": operation,
                    "pid": child.pid,
                    "exit": child.returncode,
                    "execution_attempts": 0,
                },
            ]
        )
        return mapping(json.loads(stdout))

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
            criterion_ids = [str(uuid4()), str(uuid4())] if with_criteria else []
            context_request = seed.write(
                **({"criterion_ids": criterion_ids} if with_criteria else {}),
                schema_version=2,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
            )
            if with_criteria and not legacy_criteria:
                context = await inputs.create_method_context(context_request)
            else:
                from omnis.modules.tasks import managed_composition

                with monkeypatch.context() as historical:
                    historical.setattr(
                        managed_composition,
                        "COMPOSER_REVISION",
                        managed_composition.CRITERIA_COMPOSER_REVISION
                        if legacy_criteria
                        else managed_composition.COMPACT_COMPOSER_REVISION,
                    )
                    context = await inputs.create_method_context(context_request)
                checkpoint(
                    historical_composer_pin=managed_composition.CRITERIA_COMPOSER_REVISION
                    if legacy_criteria
                    else managed_composition.COMPACT_COMPOSER_REVISION
                )
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
                # Reconstruct the former inline representation from these exact
                # retained records; no seed/input/receipt is removed or recomputed.
                from omnis.modules.settings import candidate_store
                from omnis.modules.tasks import managed_composition

                if not context_only:
                    composition = next(r for r in graph if r["kind"] == "prompt-composition")
                    assert mapping(composition["payload"])["format"] == "record-refs-v1"
                    stage_payload = managed_composition.stage_payload(graph[-1], graph)
                    expanded = managed_composition.expanded_payload(
                        composition["payload"], stage_payload["record_pool"]
                    )
                    inline = candidate_store.envelope("prompt-composition", expanded)
                    original_graph = [inline if r is composition else r for r in graph]
                    reclaimed = len(canonical(original_graph)) - len(canonical(graph))
                    assert reclaimed > 0
                    assert len(canonical(graph)) + source.preparation_bytes <= 65536
                    assert canonical(
                        mapping(mapping(sequence(json.loads(str(expanded["text"])))[4])["input"])[
                            "payload"
                        ]
                    ) == canonical(mapping(mapping(case_input)["input"])["payload"])
                else:
                    reclaimed = 0
                    original_graph = graph
                # Sizes only: no credentials, payload values or receipt capabilities.
                (tmp_path / "method-build-sizes.json").write_text(
                    json.dumps(
                        {
                            "graph_bytes": len(canonical(graph)),
                            "preparation_bytes": source.preparation_bytes,
                            "total": len(canonical(graph)) + source.preparation_bytes,
                            "inline_total": len(canonical(original_graph))
                            + source.preparation_bytes,
                            "reclaimed_bytes": reclaimed,
                            "original_input_sha256": sha(
                                canonical(mapping(mapping(case_input)["input"])["payload"])
                            )
                            if case_input is not None
                            else None,
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
            if with_criteria and not legacy_criteria:
                briefs = [mapping(r) for r in sequence(prepared["briefs"])]
                assert len(briefs) == 1
                body = mapping(briefs[0]["payload"])
                assert [mapping(r)["predicate_id"] for r in sequence(body["done_when"])] == [
                    "normalize-records",
                    "build-surface-map",
                    "preserve-input-context",
                ]
                assert [mapping(r)["predicate_id"] for r in sequence(body["return_when"])] == [
                    "build-surface-map"
                ]
                checkpoint(
                    bound_predicate_producer="QUALIFIED_NONEMPTY",
                    done_predicates=3,
                    return_predicates=1,
                )
            if legacy_criteria:
                body = mapping(mapping(sequence(prepared["briefs"])[0])["payload"])
                assert body["done_when"] == [] and body["return_when"] == []
                assert len(sequence(body["criterion_bindings"])) == 2
                checkpoint(legacy_criteria_zero_predicates="QUALIFIED_717_ZERO")
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
            # A second, never-launched assignment is only a Stop-stage negative;
            # it uses the SAME published seed/value, not a new verifier/input.
            pending = None
            pending_request = None
            if first_final_after_stop:
                pending_context = await inputs.create_method_context(
                    seed.write(
                        schema_version=2,
                        selection_ref=selected["selection_ref"],
                        preparation_command_id=preparation.command_id,
                    )
                )
                pending_input = await inputs.create_input(
                    seed.write(
                        schema_version=2, context_ref=pending_context["context_ref"], input=value
                    )
                )
                pending_request = seed.write(
                    **{k: v for k, v in assignment.items() if k not in {"owner_id", "command_id"}},
                )
                pending_request["context_ref"] = pending_context["context_ref"]
                pending_request["slot_values"] = [
                    {"slot_name": "records", "refs": [pending_input["input_ref"]]}
                ]
                pending = await domain.prepare_method(pending_request)
                assert pending["run_id"] != prepared["run_id"]

            async def markers() -> dict[str, object]:
                async with engine.connect() as conn:
                    kinds = (
                        (
                            await conn.execute(
                                sql(
                                    "SELECT envelope->>'kind' AS kind,count(*) AS count "
                                    "FROM managed_record WHERE run_id=:run GROUP BY envelope->>'kind'"
                                ),
                                {"run": prepared["run_id"]},
                            )
                        )
                        .mappings()
                        .all()
                    )
                    counts = {str(r["kind"]): r["count"] for r in kinds}
                    inbox_counts = (
                        (
                            await conn.execute(
                                sql(
                                    "SELECT count(*) AS inbox,count(*) FILTER (WHERE i.delivered) AS delivered,"
                                    "count(*) FILTER (WHERE i.admitted) AS admitted,"
                                    "count(*) FILTER (WHERE i.turn_completed) AS turn_completed,"
                                    "count(*) FILTER (WHERE i.domain_result_consumed) AS consumed "
                                    "FROM managed_inbox i JOIN managed_task t ON t.task_id=i.task_id "
                                    "WHERE t.run_id=:run"
                                ),
                                {"run": prepared["run_id"]},
                            )
                        )
                        .mappings()
                        .one()
                    )
                return {"records": counts, **dict(inbox_counts)}

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
                original_ingest = domain.ingest_result
                seam_calls = 0

                async def stop_before_first_persist(
                    owner_id: str,
                    manifest_ref: object,
                    final: object,
                    runtime_boot: object,
                    authority: object,
                    *,
                    held: bool,
                ) -> dict[str, object]:
                    nonlocal seam_calls
                    seam_calls += 1
                    # This seam is AFTER _exchange returned the genuine native
                    # finite final AND native_preparation_commit exited. A real
                    # shutdown on its lock order must complete before ingest.
                    assert seam_calls == 1 and held is False
                    assert mapping(final)["status"] == "SUCCEEDED"
                    assert runtime_boot == runtime.boot
                    before = await domain.readback(
                        seed.request(command_id=assignment["command_id"])
                    )
                    assert before["release_started"] is True
                    assert (
                        before["results"] == [] and before["checks"] == [] and before["inbox"] == []
                    )
                    assert not any(
                        mapping(r)["kind"] == "native-task-receipt"
                        for r in sequence(before["records"])
                    )
                    original_binding = mapping(mapping(before["binding"])["payload"])
                    assert original_binding["runtime_boot"] == runtime_boot
                    assert canonical(original_binding["authority"]) == canonical(authority)
                    native_before_stop = observation.read_bytes()
                    done.set()
                    await heartbeat
                    stop_id = uuid4()
                    generation = await service.shutdown(
                        stop_id, status.generation, supervisor, epoch
                    )
                    stopped = await service.command_readback(
                        stop_id, "SHUTDOWN", status.generation, generation, supervisor, epoch
                    )
                    assert generation == status.generation + 1
                    assert stopped.admission_open is False
                    assert stopped.shutdown_command_id == stop_id
                    assert stopped.supervisor_epoch == epoch
                    checkpoint(
                        first_persist_cut="GENUINE_FINAL_BEFORE_DOMAIN_PERSIST",
                        original_boot=runtime_boot,
                        stop_generation=generation,
                        raw_before_stop=0,
                        inbox_before_stop=0,
                    )
                    received = await original_ingest(
                        owner_id, manifest_ref, final, runtime_boot, authority, held=held
                    )
                    late_inbox = mapping(sequence(received["inbox"])[0])
                    assert late_inbox["disposition"] == "HELD_FOR_RECONCILIATION"
                    assert {
                        k: late_inbox[k]
                        for k in (
                            "delivered",
                            "admitted",
                            "turn_completed",
                            "domain_result_consumed",
                        )
                    } == {
                        "delivered": True,
                        "admitted": False,
                        "turn_completed": False,
                        "domain_result_consumed": False,
                    }
                    assert observation.read_bytes() == native_before_stop
                    checkpoint(first_late_held="PASS", first_ingest_markers=await markers())
                    return received

                with monkeypatch.context() as pause:
                    if lost_reply:
                        # Physical reply loss at the Host's UDS writer frontier,
                        # AFTER the real native final passed Host validation.
                        # No substituted result, prompt resend or provider.
                        assert host.owner_writer is not None
                        wire = host.owner_writer
                        original_write = wire.write
                        dropped = []

                        def lose_final(raw: bytes) -> None:
                            reply = json.loads(raw)
                            final_reply = reply.get("managed", {})
                            if reply.get("ok") is True and final_reply.get("status") == "SUCCEEDED":
                                dropped.append(sha(canonical(final_reply)))
                                checkpoint(
                                    lost_reply_frontier="HOST_UDS_BEFORE_WRITE",
                                    retained_final_sha256=dropped[0],
                                )
                                wire.transport.abort()
                                raise ConnectionResetError("Owned reply deliberately lost")
                            original_write(raw)

                        pause.setattr(wire, "write", lose_final)
                        with pytest.raises(CatalogError, match="^TASK_INDETERMINATE$"):
                            await owner.handle(
                                NativeTaskCommand.model_validate({**lifecycle, "action": "release"})
                            )
                        assert len(dropped) == 1
                        # Join THIS connection owner and its bounded native drain.
                        await asyncio.wait_for(asyncio.gather(*list(host.clients)), 2)
                        assert runtime.reader is None and runtime.writer is None
                        assert host.process is not None and host.process.returncode is not None
                        before = await domain.readback(
                            seed.request(command_id=assignment["command_id"])
                        )
                        assert before["release_started"] is True
                        assert before["results"] == before["checks"] == before["inbox"] == []
                        checkpoint(
                            lost_reply_intent="RELEASE_STARTED_WITHOUT_RESULT",
                            raw_before_recovery=0,
                            inbox_before_recovery=0,
                        )
                        assert len(host.managed_finals) == 1
                        retained = next(iter(host.managed_finals.values()))
                        assert sha(retained) == dropped[0] and len(retained) <= 32768
                        checkpoint(retained_final_bytes=len(retained), retained_finals=1)
                        with pytest.raises(CatalogError, match="^TASK_INDETERMINATE$"):
                            await owner.handle(
                                NativeTaskCommand.model_validate({**lifecycle, "action": "release"})
                            )
                        assert canonical(
                            await domain.readback(seed.request(command_id=assignment["command_id"]))
                        ) == canonical(before)
                        if first_final_after_stop:
                            done.set()
                            await heartbeat
                            stop_id = uuid4()
                            generation = await service.shutdown(
                                stop_id, status.generation, supervisor, epoch
                            )
                            stopped = await service.command_readback(
                                stop_id,
                                "SHUTDOWN",
                                status.generation,
                                generation,
                                supervisor,
                                epoch,
                            )
                            assert (
                                generation == status.generation + 1
                                and stopped.admission_open is False
                            )
                            checkpoint(stop_generation=generation)
                        native_before_receive = observation.read_bytes()
                        recovery_attempts: list[str] = []
                        actual_exchange = runtime._exchange

                        async def only_receive(
                            op: str,
                            authority: RuntimeAuthority | None = None,
                            payload: dict[str, object] | None = None,
                        ) -> dict[str, object]:
                            recovery_attempts.append(op)
                            checkpoint(recovery_operations=recovery_attempts)
                            if op != "task_receive" or authority is not None:
                                raise AssertionError("RECOVERY_ATTEMPTED_NEW_WORK")
                            return await actual_exchange(op, authority, payload)

                        pause.setattr(runtime, "_exchange", only_receive)
                        # Unknown retained ticket on the SAME private receive channel.
                        from omnis.supervisor.runtime_client import RuntimeUnavailable

                        bound_body = mapping(mapping(before["binding"])["payload"])
                        receive_payload = {
                            "protocol": manifest_protocol(prepared["manifest"]),
                            "ticket": bound_body["ticket"],
                            "manifest_ref": prepared["manifest_ref"],
                        }
                        with pytest.raises(RuntimeUnavailable):
                            await runtime.receive(
                                {**receive_payload, "ticket": str(uuid4())},
                                expected_boot=runtime.boot,
                            )
                        assert canonical(
                            await domain.readback(seed.request(command_id=assignment["command_id"]))
                        ) == canonical(before)
                        with pytest.raises(CatalogError, match="^COMMAND_CONFLICT$"):
                            await owner.handle(
                                NativeTaskCommand.model_validate(
                                    {**lifecycle, "action": "receive", "expected_epoch": epoch + 1}
                                )
                            )
                        with pytest.raises(CatalogError, match="^COMMAND_CONFLICT$"):
                            await NativeTaskOwner(domain, service, uuid4(), epoch, runtime).handle(
                                NativeTaskCommand.model_validate({**lifecycle, "action": "receive"})
                            )
                        # Untrusted mutations of genuine retained bytes traverse
                        # this owner/ingest consumer; none is positive evidence.
                        for mutation in ("header", "foreign_child"):

                            async def corrupted_receive(
                                op: str,
                                authority: RuntimeAuthority | None = None,
                                payload: dict[str, object] | None = None,
                                *,
                                mutation: str = mutation,
                            ) -> dict[str, object]:
                                response = deepcopy(await only_receive(op, authority, payload))
                                corrupt = mapping(response["managed"])
                                execution = mapping(sequence(corrupt["executions"])[0])
                                if mutation == "foreign_child":
                                    execution["native_child_id"] = str(uuid4())
                                else:
                                    changed_result = mapping(sequence(execution["records"])[0])
                                    mapping(mapping(changed_result["payload"])["header"])[
                                        "task_id"
                                    ] = str(uuid4())
                                    changed_result["digest"] = sha(
                                        canonical(
                                            {
                                                k: v
                                                for k, v in changed_result.items()
                                                if k != "digest"
                                            }
                                        )
                                    )
                                return response

                            pause.setattr(runtime, "_exchange", corrupted_receive)
                            with pytest.raises(CatalogError):
                                await owner.handle(
                                    NativeTaskCommand.model_validate(
                                        {**lifecycle, "action": "receive"}
                                    )
                                )
                            assert canonical(
                                await domain.readback(
                                    seed.request(command_id=assignment["command_id"])
                                )
                            ) == canonical(before)
                        pause.setattr(runtime, "_exchange", only_receive)
                        released = await owner.handle(
                            NativeTaskCommand.model_validate({**lifecycle, "action": "receive"})
                        )
                        assert recovery_attempts == ["task_receive"] * 4
                        assert observation.read_bytes() == native_before_receive
                        recovered = await domain.readback(
                            seed.request(command_id=assignment["command_id"])
                        )
                        native_receipt = next(
                            mapping(r)
                            for r in sequence(recovered["records"])
                            if mapping(r)["kind"] == "native-task-receipt"
                        )
                        assert sha(canonical(native_receipt["payload"])) == dropped[0]
                        checkpoint(
                            lost_reply_recovered="PASS",
                            receive_negatives=[
                                "unknown_ticket",
                                "foreign_epoch",
                                "foreign_owner",
                                "header",
                                "foreign_child",
                            ],
                            first_late_held="PASS" if first_final_after_stop else None,
                        )
                    else:
                        if first_final_after_stop:
                            pause.setattr(domain, "ingest_result", stop_before_first_persist)
                        released = await owner.handle(
                            NativeTaskCommand.model_validate({**lifecycle, "action": "release"})
                        )
                assert seam_calls == int(first_final_after_stop and not lost_reply)
                assert released["task_status"] == "SUCCEEDED"
                assert released["binding_ref"] == staged["binding_ref"]
                back_request = seed.request(command_id=assignment["command_id"])
                back = await domain.readback(back_request)
                binding = mapping(back["binding"])
                assert mapping(mapping(binding["payload"])["authority"])["owner"] == str(supervisor)
                assert mapping(binding["payload"])["runtime_boot"] == runtime.boot
                assert back["status"] == "SUCCEEDED"
                if with_criteria:
                    outcomes = [mapping(o) for o in sequence(back["criterion_outcomes"])]
                    assert len(outcomes) == 2
                    payloads = [mapping(o["payload"]) for o in outcomes]
                    from omnis.modules.tasks.criterion_checks import REASON

                    assert all(p["reason"] == REASON for p in payloads)
                    assert {p["criterion_id"] for p in payloads} == set(criterion_ids)
                    assert all(
                        p["outcome"] == "BLOCKED"
                        and p["gaps"] == ["ORACLE_UNAVAILABLE", "CONTROLS_UNAVAILABLE"]
                        for p in payloads
                    )
                    assert payloads[0]["bound_procedure_ref"] == payloads[1]["bound_procedure_ref"]
                    checkpoint(criterion_outcomes=payloads, criterion_count=2)
                else:
                    assert "criterion_outcomes" not in back
                    assert not any(
                        mapping(r)["kind"] == "criterion-outcome" for r in sequence(back["records"])
                    )
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
                if with_criteria:
                    checkpoint(bound_predicate_persistent_check="COMPLETE")
                if with_criteria:
                    from omnis.modules.settings import candidate_store as stored
                    from omnis.modules.tasks import criterion_checks

                    # A child proposal cannot promote the trusted no-oracle rule.
                    # This helper control is SOURCE, not a second authentic emitter.
                    proposed = deepcopy(result)
                    proposed_body = mapping(proposed["payload"])
                    proposals = [mapping(p) for p in sequence(proposed_body["criterion_results"])]
                    for proposal in proposals:
                        proposal["proposed_outcome"] = "PASS"
                    proposed_body["criterion_results"] = proposals
                    proposed["payload"] = proposed_body
                    proposed["digest"] = sha(
                        canonical({k: v for k, v in proposed.items() if k != "digest"})
                    )
                    proposed_check = deepcopy(checks[0])
                    proposed_check_body = mapping(proposed_check["payload"])
                    proposed_check_body["task_result_ref"] = stored.reference(proposed)
                    proposed_check["payload"] = proposed_check_body
                    proposed_check["digest"] = sha(
                        canonical({k: v for k, v in proposed_check.items() if k != "digest"})
                    )
                    assert all(
                        p["outcome"] == "BLOCKED"
                        for p in criterion_checks.outcome_payloads(
                            sequence(back["briefs"])[0], proposed, proposed_check, graph
                        )
                    )

                    checkpoint(no_oracle_no_pass="PASS")
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
                # Even the ordinary pre-Stop fixture is an admission-CLOSED
                # inert instance, not a turn grant; receive_disposition requires
                # admission_open=True for RECEIVED. Preserve that prerequisite.
                assert status.admission_open is False
                assert inbox["disposition"] == "HELD_FOR_RECONCILIATION"
                native = next(r for r in graph if r["kind"] == "native-task-receipt")
                final = mapping(native["payload"])
                fence = mapping(binding["payload"])["authority"]
                durable_markers = await markers()
                assert durable_markers["inbox"] == durable_markers["delivered"] == 1
                assert (
                    durable_markers["admitted"]
                    == durable_markers["turn_completed"]
                    == durable_markers["consumed"]
                    == 0
                )
                assert {
                    k: mapping(durable_markers["records"])[k]
                    for k in (
                        "native-task-receipt",
                        "task-result",
                        "method-check",
                        "contract-tool-receipt",
                        "contract-artifact",
                    )
                } == {
                    "native-task-receipt": 1,
                    "task-result": 1,
                    "method-check": 1,
                    "contract-tool-receipt": 3,
                    "contract-artifact": 2,
                }
                duplicate = await domain.ingest_result(
                    seed.owner, prepared["manifest_ref"], final, runtime.boot, fence, held=False
                )
                assert canonical(duplicate) == canonical(back)
                assert await markers() == durable_markers
                # A changed copy of the received result is a negative request,
                # never an alternate producer or a modification of old evidence.
                conflict = deepcopy(final)
                changed = mapping(
                    sequence(mapping(sequence(conflict["executions"])[0])["records"])[0]
                )
                mapping(mapping(changed["payload"])["usage"])["cost"] = "1"
                changed["digest"] = sha(
                    canonical({k: v for k, v in changed.items() if k != "digest"})
                )
                with pytest.raises(CatalogError, match="^RESULT_CONFLICT$"):
                    await domain.ingest_result(
                        seed.owner,
                        prepared["manifest_ref"],
                        conflict,
                        runtime.boot,
                        fence,
                        held=False,
                    )
                assert canonical(await domain.readback(back_request)) == canonical(back)
                assert await markers() == durable_markers
                checkpoint(duplicate_conflict="PASS", durable_markers=durable_markers)
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

                execution_attempts: list[str] = []

                def no_rerun(*args: object, **kwargs: object) -> object:
                    execution_attempts.append("FORBIDDEN_EXECUTION")
                    checkpoint(execution_attempts=execution_attempts)
                    raise AssertionError("REPLAY_RERAN_EXECUTION")

                if first_final_after_stop:
                    assert pending is not None and pending_request is not None
                    pending_before = await domain.readback(
                        seed.request(command_id=pending_request["command_id"])
                    )
                    with monkeypatch.context() as blocked:
                        blocked.setattr(runtime, "_exchange", no_rerun)
                        with pytest.raises(ControlConflict) as stage_denied:
                            await owner.handle(
                                NativeTaskCommand.model_validate(
                                    {
                                        **lifecycle,
                                        "action": "stage",
                                        "command_id": pending_request["command_id"],
                                        "manifest_ref": pending["manifest_ref"],
                                        "expected_generation": proof["stop_generation"],
                                    }
                                )
                            )
                        assert stage_denied.value.code == ControlCode.INSTANCE_SHUTTING_DOWN
                    assert canonical(
                        await domain.readback(
                            seed.request(command_id=pending_request["command_id"])
                        )
                    ) == canonical(pending_before)
                    assert await markers() == durable_markers
                    assert observation.read_bytes() == native_before
                    assert execution_attempts == []
                    checkpoint(new_stage_denial="INSTANCE_SHUTTING_DOWN")
                    # Deny new IPC work while the same original owner lease is
                    # still live; managed() also retires its revoked client.
                    # The later restart oracle snapshots the fully joined peer.
                    with monkeypatch.context() as blocked:
                        blocked.setattr(runtime, "_exchange", no_rerun)
                        for action in ("task_stage", "task_release"):
                            with pytest.raises(ControlConflict) as denied:
                                await runtime.managed(
                                    service,
                                    supervisor,
                                    action,
                                    {
                                        "protocol": manifest_protocol(prepared["manifest"]),
                                        "ticket": final["ticket"],
                                        "manifest_ref": prepared["manifest_ref"],
                                        "binding": binding,
                                    },
                                )
                            assert denied.value.code == ControlCode.GENERATION_CONFLICT
                    assert execution_attempts == []
                    assert await markers() == durable_markers
                    assert canonical(await domain.readback(back_request)) == canonical(back)
                    checkpoint(new_runtime_release_stage_denial="GENERATION_CONFLICT")

            # The producer is now retired by its existing Host context; this
            # restart criterion belongs to the persistent managed reader, not
            # a live/renewed native grant. Keep the byte-exact observer oracle
            # on the fully joined producer, without filtering any event.
            await runtime.close()
            assert host.process is not None and host.process.returncode is not None
            assert not host._owned_pids()
            native_before = observation.read_bytes()
            with monkeypatch.context() as patcher:
                for module in ("skill_catalog", "candidate_catalog"):
                    patcher.setattr("omnis.modules.settings." + module + ".evaluate_pure", no_rerun)
                patcher.setattr("omnis.modules.runs.pure_probe.evaluate_pure", no_rerun)
                patcher.setattr("omnis.modules.tasks.module_registry.run_handler", no_rerun)
                patcher.setattr(BuildSource, "build", no_rerun)
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
                # Persistent managed CLI/readback/reconcile in fresh reader
                # processes on THIS owned DB; no runtime restart or adoption.
                assert canonical(await restarted_cli("readback", back_request)) == canonical(back)
                assert await markers() == durable_markers
                restarted = await restarted_cli("reconcile", back_request)
                assert canonical(restarted["records"]) == canonical(back["records"])
                restart_inbox = mapping(sequence(restarted["inbox"])[0])
                assert {
                    k: restart_inbox[k]
                    for k in (
                        "delivered",
                        "admitted",
                        "turn_completed",
                        "domain_result_consumed",
                        "disposition",
                    )
                } == {
                    **{
                        k: inbox[k]
                        for k in ("delivered", "admitted", "turn_completed", "disposition")
                    },
                    "domain_result_consumed": True,
                }
                consumed_markers = {**durable_markers, "consumed": 1}
                assert await markers() == consumed_markers
                assert canonical(await restarted_cli("reconcile", back_request)) == canonical(
                    restarted
                )
                assert canonical(await restarted_cli("readback", back_request)) == canonical(
                    restarted
                )
                assert await markers() == consumed_markers
                assert observation.read_bytes() == native_before
                assert execution_attempts == []
                checkpoint(
                    restart_reconcile="PASS",
                    consumed_markers=consumed_markers,
                    execution_attempts=execution_attempts,
                )
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
            assert await markers() == consumed_markers
            # Historical terminal receipt is receive-only after a real Stop.
            done.set()
            await heartbeat
            if not first_final_after_stop:
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
            assert await markers() == consumed_markers
            assert canonical(await domain.readback(back_request)) == canonical(prior)
            checkpoint(post_stop_duplicate="PASS", final_markers=await markers())
            async with engine.connect() as conn:
                assert (
                    await conn.execute(sql("SELECT count(*) FROM managed_inbox"))
                ).scalar_one() == 1
            if with_criteria:
                from omnis.modules.settings import candidate_store as stored
                from omnis.modules.tasks import managed_store

                # Append-only storage is preserved. After all positive restart/
                # idempotency checks, append one explicitly forged test outcome.
                # Never UPDATE/DELETE historical envelopes or treat it as evidence.
                target = mapping(sequence(prior["criterion_outcomes"])[0])
                forged = stored.envelope(
                    "criterion-outcome", {**mapping(target["payload"]), "outcome": "PASS"}
                )
                async with engine.begin() as conn:
                    await managed_store.lock(conn, seed.owner)
                    await managed_store.put(conn, seed.owner, str(prior["run_id"]), forged)
                with pytest.raises(CatalogError, match="^CRITERION_OUTCOME_MISMATCH$"):
                    await domain.readback(back_request)
                with pytest.raises(CatalogError, match="^CRITERION_OUTCOME_MISMATCH$"):
                    await domain.reconcile(back_request)
                checkpoint(
                    forged_outcome_readback="PASS",
                    adversarial_append_count=1,
                    post_adversarial_markers=await markers(),
                )
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
                checkpoint(
                    native_cleanup="PASS",
                    native_directory=str(host.directory),
                    native_exit=None if host.process is None else host.process.returncode,
                    native_owned_pids=sorted(host._owned_pids()),
                )
        rows = [json.loads(line) for line in observation.read_text().splitlines()]
        assert {"test": "observer", "status": "READY", "count": 1} in rows
        assert not any(r["test"].startswith("forbidden-") for r in rows)
        assert [r for r in rows if r["test"] == "run_contract"] == [
            {"test": "run_contract", "status": "REAL_AIAgent", "count": 1}
        ]
        assert len([r for r in rows if r["test"] == "_read_bound_input"]) == 1
        assert len([r for r in rows if r["test"] == "run_handler"]) == 2
        assert {"test": "native-release", "status": "SUCCEEDED", "count": 1} in rows
        if with_criteria and not legacy_criteria:
            assert [r for r in rows if r["test"] == "bound-predicates"] == [
                {"test": "bound-predicates", "status": "SATISFIED", "count": 3}
            ]
            checkpoint(
                native_bound_predicate_evaluation="SATISFIED", native_bound_predicate_count=3
            )
        checkpoint(
            native_run_contract=1,
            native_reads=1,
            native_handlers=2,
            forbidden_native_attempts=0,
            status="PASS_SOURCE_NOT_INSTALLED",
        )

    asyncio.run(run())
