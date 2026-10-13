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
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from fixtures.b06b_publication.consumer import Seed, canonical, mapping, sequence, sha
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
bootstrap_started_ns = time.monotonic_ns()
audit_ns = 0
audit_calls = 0

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
def timed_audit(event, args):
    global audit_ns, audit_calls
    before = time.monotonic_ns()
    try:
        audit(event, args)
    finally:
        audit_ns += time.monotonic_ns() - before
        audit_calls += 1
sys.addaudithook(timed_audit)

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
observed = forbidden | {"main", "run_contract", "_read_bound_input", "run_handler", "_contract_guard", "release", "validate_stage", "stage", "initialize_contract", "predicate_values"}
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
    if event == "call" and name == "main" and filename == str(inert / "tui_gateway/entry.py"):
        emit("bootstrap-import", "ELAPSED_MS", (time.monotonic_ns() - bootstrap_started_ns) // 1_000_000)
        emit("bootstrap-audit", "ELAPSED_MS", audit_ns // 1_000_000)
        emit("bootstrap-audit", "CALLS", audit_calls)
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
# Filtering code objects before requesting a frame avoids millions of
# object.__getattr__(frame, "f_code") audit events during native imports.
# Monitoring is interpreter-local and covers new native threads as well.
observer_roots = tuple(str(root) for root in (source, managed, inert, adapter))
def monitored(code):
    return code.co_name in observed and any(root in code.co_filename for root in observer_roots)
def monitor_call(code, offset):
    if not monitored(code):
        return sys.monitoring.DISABLE
    observe(sys._getframe(1), "call", None)
def monitor_return(code, offset, value):
    if not monitored(code):
        return sys.monitoring.DISABLE
    observe(sys._getframe(1), "return", value)
observer_id = sys.monitoring.PROFILER_ID
sys.monitoring.use_tool_id(observer_id, "omnis-contract-observer")
sys.monitoring.register_callback(observer_id, sys.monitoring.events.PY_START, monitor_call)
sys.monitoring.register_callback(observer_id, sys.monitoring.events.PY_RETURN, monitor_return)
sys.monitoring.set_events(observer_id, sys.monitoring.events.PY_START | sys.monitoring.events.PY_RETURN)
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


def launch_rpc_phase(value: object) -> str:
    if type(value) is str and value in {
        "client.capabilities",
        "gateway.capabilities",
        "omnis.inert.probe_unknown",
    }:
        return value
    return "gateway.ready"


def launch_exception_chain(error: BaseException) -> list[dict[str, str]]:
    """Bounded public tags only; never evaluate or retain exception reprs."""
    exception_types = {
        "RuntimeUnavailable",
        "ProtocolError",
        "RPCError",
        "TimeoutError",
        "CancelledError",
        "ValueError",
        "IncompleteReadError",
        "LimitOverrunError",
    }
    public_reasons = {
        "Runtime exchange unavailable",
        "Runtime refused",
        "Native RPC deadline",
        "Native ready deadline",
        "Native transport unavailable",
        "Required capabilities missing",
        "Unexpected unknown probe",
        "Unknown probe was accepted",
    }
    rows: list[dict[str, str]] = []
    current: BaseException | None = error
    while current is not None and len(rows) < 4:
        name = type(current).__name__
        arguments = current.args
        reason = arguments[0] if len(arguments) == 1 and type(arguments[0]) is str else ""
        rows.append(
            {
                "type": name if name in exception_types else "OTHER_EXCEPTION",
                "reason": reason
                if name in exception_types and reason in public_reasons
                else "UNCLASSIFIED",
            }
        )
        current = current.__context__
    return rows


def test_launch_failure_diagnostic_preserves_public_context_not_raw_error() -> None:
    diagnostic = globals().get("launch_exception_chain")
    assert callable(diagnostic), "LAUNCH_FAILURE_DIAGNOSTIC_MISSING"
    marker = "PUBLIC_SYNTHETIC_PRIVATE_LAUNCH_ERROR"
    outer = ValueError("Runtime exchange unavailable")
    inner = TimeoutError("Native ready deadline")
    opaque = RuntimeError(marker)
    outer.__context__ = inner
    inner.__context__ = opaque
    opaque.__context__ = outer
    result = diagnostic(outer)
    assert result == [
        {"type": "ValueError", "reason": "Runtime exchange unavailable"},
        {"type": "TimeoutError", "reason": "Native ready deadline"},
        {"type": "OTHER_EXCEPTION", "reason": "UNCLASSIFIED"},
        {"type": "ValueError", "reason": "Runtime exchange unavailable"},
    ]
    assert marker not in canonical(result).decode()

    class ValueErrorWithPrivateRepr(ValueError):
        def __str__(self) -> str:
            raise AssertionError("PRIVATE_EXCEPTION_REPR_EVALUATED")

    hostile = ValueErrorWithPrivateRepr(marker)
    assert diagnostic(hostile) == [{"type": "OTHER_EXCEPTION", "reason": "UNCLASSIFIED"}]
    assert diagnostic(ValueError(marker)) == [{"type": "ValueError", "reason": "UNCLASSIFIED"}]


def test_launch_rpc_phase_projects_exact_public_strings_only() -> None:
    marker = "PUBLIC_SYNTHETIC_PRIVATE_PHASE"

    class SpoofedMethod(str):
        def __hash__(self) -> int:
            return hash("client.capabilities")

        def __eq__(self, other: object) -> bool:
            return other == "client.capabilities"

    for method in (
        "client.capabilities",
        "gateway.capabilities",
        "omnis.inert.probe_unknown",
    ):
        assert launch_rpc_phase(method) == method
    invalid: tuple[object, ...] = (None, True, [], {}, marker, SpoofedMethod(marker))
    for value in invalid:
        assert launch_rpc_phase(value) == "gateway.ready"


def test_restart_stderr_refusal_keeps_private_bytes_out_of_pytest_report() -> None:
    require_empty_stderr(b"")
    marker = b"PUBLIC_SYNTHETIC_PRIVATE_DIAGNOSTIC"
    with pytest.raises(AssertionError) as refused:
        require_empty_stderr(marker)
    assert str(refused.value) == "RESTART_CLI_CONTRADICTORY_DIAGNOSTIC"
    for style in ("line", "short"):
        assert marker.decode() not in str(refused.getrepr(style=style))


@pytest.mark.parametrize(
    "scenario",
    ["unrelated", "observed", "forbidden", "foreign", "threaded", "threaded-denied", "returned"],
)
def test_bootstrap_observer_filters_before_frame_audit(scenario: str) -> None:
    """Exercise the actual bootstrap observer in a disposable interpreter only."""
    observer = BOOTSTRAP.split("forbidden =", 1)[1].split('emit("observer", "READY")', 1)[0]
    setup = r"""
import json, sys, threading, time
from pathlib import Path
source, managed, inert, adapter = (Path("/synthetic/" + p) for p in
                                    ("source", "managed", "inert", "adapter"))
rows = []
def emit(test, status, count=1):
    rows.append({"test": test, "status": status, "count": count})
frame_audits = 0
def audit(event, args):
    global frame_audits
    if event == "object.__getattr__" and args[1] == "f_code":
        frame_audits += 1
sys.addaudithook(audit)
"""
    exercise = r"""
scenario = sys.argv[1]
body_entered = []
name = {"unrelated": "ordinary", "observed": "run_handler",
        "forbidden": "init_agent", "foreign": "init_agent",
        "threaded": "run_handler", "threaded-denied": "init_agent",
        "returned": "_contract_guard"}[scenario]
filename = "/foreign/control.py" if scenario == "foreign" else str(source / "control.py")
exec(compile("def " + name + "():\n    body_entered.append(True)\n    return True\n", filename, "exec"))
function = globals()[name]
def invoke():
    try:
        function()
    except RuntimeError as error:
        if str(error) != "Forbidden native sink":
            raise
# Allocate/count outside the measured invocation; no clocks as a pass oracle.
frame_audits = 0
if scenario.startswith("threaded"):
    child = threading.Thread(target=invoke)
    child.start()
    child.join(timeout=2)
    assert not child.is_alive()
else:
    for _ in range(200 if scenario == "unrelated" else 1):
        invoke()
measured_audits = frame_audits
sys.setprofile(None)
threading.setprofile(None)
if sys.monitoring.get_tool(sys.monitoring.PROFILER_ID) == "omnis-contract-observer":
    sys.monitoring.set_events(sys.monitoring.PROFILER_ID, 0)
    sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)
print(json.dumps({"rows": rows, "frame_audits": measured_audits,
                  "body_count": len(body_entered)}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", setup + "forbidden =" + observer + exercise, scenario],
        capture_output=True,
        timeout=10,
        check=False,
    )
    require_empty_stderr(result.stderr)
    assert result.returncode == 0
    actual = json.loads(result.stdout)
    if scenario == "unrelated":
        assert actual == {"rows": [], "frame_audits": 0, "body_count": 200}
    elif scenario in {"observed", "threaded"}:
        assert actual["rows"] == [{"test": "run_handler", "status": "ENTERED", "count": 1}]
        assert actual["body_count"] == 1
    elif scenario in {"forbidden", "threaded-denied"}:
        assert actual["rows"] == [{"test": "forbidden-sink", "status": "init_agent", "count": 1}]
        assert actual["body_count"] == 0
    elif scenario == "returned":
        assert actual["rows"] == [{"test": "contract-guard", "status": "APPROVED", "count": 1}]
        assert actual["body_count"] == 1
    else:
        assert actual == {"rows": [], "frame_audits": 0, "body_count": 1}


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
    "first_final_after_stop,with_criteria,lost_reply,legacy_criteria,early_return,applicability",
    [
        (False, False, False, False, False, None),
        (False, True, False, False, False, None),
        (False, True, False, True, False, None),
        (True, True, False, False, False, None),
        (False, True, True, False, False, None),
        (True, True, True, False, False, None),
        (False, True, False, False, True, None),
        (False, True, False, False, False, "applies"),
        (False, True, False, False, False, "not-applicable"),
        (False, True, False, False, False, "unknown"),
        (False, True, False, False, False, "precondition"),
        (False, True, False, False, False, "invalidation"),
        (False, True, False, False, False, "evidence-full"),
        (False, True, False, False, True, "evidence-optional-prefix"),
        (False, True, False, False, True, "evidence-required-prefix"),
        (False, True, False, False, False, "partial-requirement-full"),
        (False, True, False, False, True, "partial-requirement-prefix"),
        (False, True, False, False, False, "mission-consumer"),
    ],
    ids=[
        "support-zero",
        "criteria-normal",
        "criteria-legacy717",
        "criteria-first-late-held",
        "lost-reply",
        "lost-reply-post-stop",
        "qualified-early-return",
        "applicability-applies",
        "applicability-not-applicable",
        "applicability-unknown",
        "procedure-precondition",
        "procedure-invalidation",
        "evidence-full",
        "evidence-optional-prefix",
        "evidence-required-prefix",
        "partial-requirement-full",
        "partial-requirement-prefix",
        "mission-consumer",
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
    early_return: bool,
    applicability: str | None,
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
    if applicability is not None and applicability != "mission-consumer":
        import yaml

        from fixtures import c03_records
        from omnis.modules.settings.catalog_schema import load_yaml

        actual_seed = c03_records.records_seed

        def conditional_seed(directory: Path) -> Seed:
            seed = actual_seed(directory)
            path = seed.package / "templates/procedures/map-records.yaml"
            authored = mapping(load_yaml(path.read_bytes()))
            conditions = [
                {
                    "predicate_id": "contract.records-nonempty",
                    "input_refs": [{"kind": "CASE_SLOT_REF", "name": "records"}],
                    "expected": True,
                    "on_missing": "INCONCLUSIVE",
                }
            ]
            if applicability.startswith("partial-requirement-"):
                requirements = [mapping(r) for r in sequence(authored["method_requirements"])]
                requirements[0]["step_ids"] = ["normalize-operations", "build-map"]
                requirements[0]["artifact_schema_refs"] = deepcopy(
                    [
                        *sequence(requirements[0]["artifact_schema_refs"]),
                        *sequence(requirements[1]["artifact_schema_refs"]),
                    ]
                )
                authored["method_requirements"] = requirements
            elif applicability.startswith("evidence-"):
                authored["method_requirements"] = [
                    {
                        **mapping(raw),
                        "evidence_kinds": ["contract-artifact"] if index < 2 else [],
                        "required": applicability != "evidence-optional-prefix"
                        if index == 1
                        else mapping(raw)["required"],
                    }
                    for index, raw in enumerate(sequence(authored["method_requirements"]))
                ]
                authored["evidence_requirements"] = [
                    {
                        "kind": "contract-artifact",
                        "minimum": 2 if applicability == "evidence-full" else 1,
                        "mandatory": True,
                    }
                ]
            elif applicability == "precondition":
                authored["preconditions"] = conditions
            elif applicability == "invalidation":
                authored["invalidation_predicate_ids"] = ["contract.records-empty"]
            else:
                mapping(sequence(authored["method_requirements"])[1])["applies_if"] = conditions
            path.write_text(yaml.safe_dump(authored, sort_keys=False))
            return seed

        monkeypatch.setattr(c03_records, "records_seed", conditional_seed)
    incomplete = (
        early_return and applicability != "evidence-optional-prefix"
    ) or applicability in {"not-applicable", "unknown"}
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
        from omnis.supervisor.native_tasks import control_task
        from omnis.transport.local_control import LocalControl

        engine = database_engine(dsn)
        service, supervisor = InstanceService(engine), uuid4()
        domain, inputs = ManagedAdmission(engine, seed.root), ContractInputs(engine, seed.root)
        runtime = None
        host = None
        done = asyncio.Event()
        heartbeat: asyncio.Task[None] | None = None
        public_control: LocalControl | None = None
        dispatch_waiters: list[asyncio.Task[dict[str, object]]] = []
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
            if applicability is not None or (with_criteria and not legacy_criteria):
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
            if applicability == "not-applicable":
                value = {"records": []}
            input_request = seed.write(
                schema_version=2, context_ref=context["context_ref"], input=value
            )
            original = await inputs.create_input(input_request)
            assert original["input_ref"] != evaluation["input_ref"]
            if applicability in {"precondition", "invalidation"}:
                denied_context = await inputs.create_method_context(
                    seed.write(
                        schema_version=2,
                        selection_ref=selected["selection_ref"],
                        preparation_command_id=preparation.command_id,
                    )
                )
                denied_input = await inputs.create_input(
                    seed.write(
                        schema_version=2,
                        context_ref=denied_context["context_ref"],
                        input={"records": []},
                    )
                )
                async with engine.connect() as conn:
                    before_records = (
                        await conn.execute(sql("SELECT count(*) FROM managed_record"))
                    ).scalar_one()
                    before_runs = (
                        await conn.execute(sql("SELECT count(*) FROM managed_run"))
                    ).scalar_one()
                denial = (
                    "PROCEDURE_PRECONDITION_FALSE"
                    if applicability == "precondition"
                    else "PROCEDURE_INVALIDATED"
                )
                with pytest.raises(CatalogError, match="^" + denial + "$"):
                    await domain.prepare_method(
                        seed.write(
                            schema_version=3,
                            selection_ref=selected["selection_ref"],
                            preparation_command_id=preparation.command_id,
                            task_count=1,
                            context_ref=denied_context["context_ref"],
                            slot_values=[
                                {"slot_name": "records", "refs": [denied_input["input_ref"]]}
                            ],
                        )
                    )
                async with engine.connect() as conn:
                    assert (
                        await conn.execute(sql("SELECT count(*) FROM managed_record"))
                    ).scalar_one() == before_records
                    assert (
                        await conn.execute(sql("SELECT count(*) FROM managed_run"))
                    ).scalar_one() == before_runs
                checkpoint(
                    **{
                        (
                            "precondition_false"
                            if applicability == "precondition"
                            else "invalidation_true"
                        ): "REFUSED_BEFORE_ASSIGNMENT_WRITES",
                        applicability + "_native": "NOT_RUN_YET",
                    }
                )
            assignment = seed.write(
                schema_version=3,
                selection_ref=selected["selection_ref"],
                preparation_command_id=preparation.command_id,
                task_count=1,
                context_ref=context["context_ref"],
                slot_values=[{"slot_name": "records", "refs": [original["input_ref"]]}],
            )
            actual_build = BuildSource.build
            if early_return:
                assignment["return_predicate_id"] = (
                    "preserve-input-context"
                    if applicability == "partial-requirement-prefix"
                    else "normalize-records"
                )

            def measured_build(
                source: BuildSource,
                *,
                count: int = 1,
                composed: bool = True,
                context_only: bool = False,
                prefix: list[dict[str, object]] | None = None,
                case_input: dict[str, object] | None = None,
                method_execution: bool = False,
                return_predicate_id: object = None,
            ) -> list[dict[str, object]]:
                graph = actual_build(
                    source,
                    count=count,
                    composed=composed,
                    context_only=context_only,
                    prefix=prefix,
                    case_input=case_input,
                    method_execution=method_execution,
                    return_predicate_id=return_predicate_id,
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
                    *([] if applicability == "evidence-optional-prefix" else ["build-surface-map"]),
                ]
                assert [mapping(r)["predicate_id"] for r in sequence(body["return_when"])] == [
                    "preserve-input-context"
                    if applicability == "partial-requirement-prefix"
                    else "normalize-records"
                    if early_return
                    else "build-surface-map"
                ]
                checkpoint(
                    bound_predicate_producer="QUALIFIED_NONEMPTY",
                    done_predicates=len(sequence(body["done_when"])),
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

            async def mission_snapshot(conn: AsyncConnection) -> bytes:
                # Full rows/envelopes stay private; failures print only labels.
                snapshots: dict[str, object] = {}
                for table, query in (
                    ("records", "SELECT to_jsonb(r) FROM public.managed_record r ORDER BY id"),
                    (
                        "revision2",
                        "SELECT to_jsonb(r) FROM public.managed_mission_revision r ORDER BY mission_id,revision",
                    ),
                    ("runs", "SELECT to_jsonb(r) FROM public.managed_run r ORDER BY run_id"),
                    ("tasks", "SELECT to_jsonb(r) FROM public.managed_task r ORDER BY task_id"),
                    ("inbox", "SELECT to_jsonb(r) FROM public.managed_inbox r ORDER BY result_id"),
                ):
                    snapshots[table] = list((await conn.execute(sql(query))).scalars().all())
                return canonical(snapshots)

            async def mission_census() -> bytes:
                async with engine.connect() as conn:
                    return await mission_snapshot(conn)

            # Failure-only, fixed-field diagnostics at the real handshake seam.
            # Never retain RPC payloads, capabilities, exception reprs or stderr.
            from omnis_hermes.runtime_protocol import NativePeer

            original_handshake = NativePeer.handshake
            original_call = NativePeer.call
            diagnostic: dict[str, object] = {}

            async def observed_handshake(
                peer: NativePeer, *, ready_timeout: float | None = None
            ) -> dict[str, object]:
                before = time.monotonic_ns()
                try:
                    result = await original_handshake(peer, ready_timeout=ready_timeout)
                except BaseException as error:
                    phase = "gateway.ready"
                    cursor = error.__traceback__
                    while cursor is not None:
                        if cursor.tb_frame.f_code is original_call.__code__:
                            method = cursor.tb_frame.f_locals.get("method")
                            projected = launch_rpc_phase(method)
                            if projected != "gateway.ready":
                                phase = projected
                        cursor = cursor.tb_next
                    checkpoint(
                        launch_diagnostic={
                            "operation": "launch",
                            "phase": phase,
                            "elapsed_ms": (time.monotonic_ns() - before) // 1_000_000,
                            "remaining_ms": (host.deadline_ns - time.monotonic_ns()) // 1_000_000,
                            "host_state": host.state,
                            "ready_done": peer.ready.done(),
                            "ready_cancelled": peer.ready.cancelled(),
                            "transport_failed": peer.failure is not None,
                            "exceptions": launch_exception_chain(error),
                        }
                    )
                    raise
                diagnostic.update(
                    operation="launch",
                    phase="handshake_complete",
                    elapsed_ms=(time.monotonic_ns() - before) // 1_000_000,
                    remaining_ms=(host.deadline_ns - time.monotonic_ns()) // 1_000_000,
                    host_state=host.state,
                    ready_done=peer.ready.done(),
                    ready_cancelled=peer.ready.cancelled(),
                    transport_failed=peer.failure is not None,
                )
                return result

            monkeypatch.setattr(host_module.NativePeer, "handshake", observed_handshake)
            owner = NativeTaskOwner(domain, service, supervisor, epoch, runtime)

            async def observe_native_task(command: NativeTaskCommand) -> dict[str, object]:
                try:
                    return await owner.handle(command)
                except CatalogError as error:
                    # Retain a bounded domain reason before LocalControl masks it.
                    # Never retain exception text, private values or response bytes.
                    safe_reasons = {
                        "RESULT_SCHEMA_MISMATCH",
                        "RESULT_CONFLICT",
                        "METHOD_RECEIPT_MISMATCH",
                        "METHOD_SCHEMA_MISMATCH",
                        "METHOD_SCHEMA_INVALID",
                        "COMPOSITION_REJECTED",
                        "ASSIGNMENT_MISMATCH",
                        "LINEAGE_MISMATCH",
                        "MANAGED_REJECTED",
                        "TASK_REJECTED",
                    }
                    checkpoint(
                        public_owner_error={
                            "action": command.action,
                            "reason": error.reason
                            if type(error.reason) is str and error.reason in safe_reasons
                            else "UNCLASSIFIED_CATALOG_ERROR",
                        }
                    )
                    raise

            if applicability == "mission-consumer" or (
                applicability is not None
                and applicability.startswith(("evidence-", "partial-requirement-"))
            ):
                # Same owner, kernel peer and private capability; no response emitter.
                # Establish the listener before launch, not inside the native grant.
                public_control = await LocalControl(
                    directory,
                    service,
                    supervisor,
                    epoch,
                    native_task=observe_native_task
                    if applicability == "partial-requirement-prefix"
                    else owner.handle,
                ).__aenter__()

            # F01: pause AFTER the real reservation/owner lock, observe the
            # append transaction blocked in PostgreSQL, then let commit finish.
            # This adds no grant/deadline/Host; the same owner still sends once.
            overlap_operations: list[str] = []
            dispatch_censuses: dict[asyncio.Task[dict[str, object]], bytes] = {}
            waiter_pids: dict[asyncio.Task[dict[str, object]], int] = {}
            if applicability == "mission-consumer":
                from omnis.modules.tasks import managed_store

                owner_lock = managed_store.lock

                async def observed_owner_lock(conn: AsyncConnection, owner_id: str) -> None:
                    task = asyncio.current_task()
                    for waiter in dispatch_waiters:
                        if task is waiter:
                            waiter_pids[waiter] = (
                                await conn.execute(sql("SELECT pg_backend_pid()"))
                            ).scalar_one()
                    await owner_lock(conn, owner_id)

                monkeypatch.setattr(managed_store, "lock", observed_owner_lock)
                reserve_dispatch = domain.reserve_dispatch

                async def overlap_reservation(
                    conn: AsyncConnection, owner_id: str, manifest_ref: object, operation: str
                ) -> dict[str, object]:
                    manifest = await reserve_dispatch(conn, owner_id, manifest_ref, operation)
                    blocker = (await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one()
                    request = seed.write(
                        schema_version=1,
                        context_ref=context["context_ref"],
                        mission_ref=mapping(
                            mapping(mapping(sequence(prepared["briefs"])[0])["payload"])["header"]
                        )["mission_revision"],
                        criterion_id=str(uuid4()),
                    )
                    waiter = asyncio.create_task(inputs.append_mission(request))
                    dispatch_waiters.append(waiter)
                    dispatch_censuses[waiter] = await mission_snapshot(conn)
                    try:
                        async with asyncio.timeout(0.75), engine.connect() as observer:
                            while True:
                                pid = waiter_pids.get(waiter)
                                if (
                                    pid is not None
                                    and blocker
                                    in (
                                        await observer.execute(
                                            sql("SELECT pg_blocking_pids(:waiter)"), {"waiter": pid}
                                        )
                                    ).scalar_one()
                                ):
                                    break
                                if waiter.done():
                                    raise AssertionError("MISSION_APPEND_DID_NOT_WAIT")
                                await asyncio.sleep(0.01)
                        overlap_operations.append(operation)
                        return manifest
                    except BaseException:
                        waiter.cancel()
                        await asyncio.gather(waiter, return_exceptions=True)
                        raise

                monkeypatch.setattr(domain, "reserve_dispatch", overlap_reservation)
                original_exchange = runtime._exchange

                async def settle_append_before_send(
                    op: str,
                    authority: RuntimeAuthority | None = None,
                    payload: dict[str, object] | None = None,
                ) -> dict[str, object]:
                    if op in {"task_stage", "task_release"}:
                        waiter = dispatch_waiters[-1]
                        try:
                            await asyncio.wait_for(waiter, 0.75)
                        except CatalogError as error:
                            if error.reason != "NEEDS_RECONCILIATION":
                                raise AssertionError(
                                    "MISSION_APPEND_WRONG_DISPATCH_DENIAL"
                                ) from None
                        else:
                            raise AssertionError("MISSION_APPEND_CROSSED_DISPATCH")
                        if await mission_census() != dispatch_censuses[waiter]:
                            raise AssertionError("MISSION_DISPATCH_APPEND_DENIAL_CENSUS_CHANGED")
                    return await original_exchange(op, authority, payload)

                monkeypatch.setattr(runtime, "_exchange", settle_append_before_send)

            async def submit_task(action: str, *, phase: str = "ACTIVE") -> dict[str, object]:
                command = NativeTaskCommand.model_validate({**lifecycle, "action": action})
                if public_control is None:
                    return await owner.handle(command)
                answer = await control_task(directory, command.model_dump(mode="json"))
                checkpoint(
                    public_control_actions=[
                        *sequence(proof.get("public_control_actions", [])),
                        {"action": action, "phase": phase, "task_status": answer["task_status"]},
                    ]
                )
                return answer

            async with host:
                await service.heartbeat(supervisor, epoch)
                await runtime.connect()
                try:
                    ready = await runtime.launch_inert(service, supervisor)
                except BaseException as error:
                    checkpoint(launch_client_exceptions=launch_exception_chain(error))
                    raise
                assert ready["state"] == "READY"
                await runtime.renew(service, supervisor)
                checkpoint(launch_diagnostic=diagnostic)
                staged = await submit_task("stage")
                assert staged["task_status"] == "BOUND"
                # Release immediately after committed stage: the native 4.5s
                # deadline is unchanged. No readback/negative between the two.
                # Fail closed: no direct-native rescue or fabricated final.
                if applicability == "unknown":
                    qualified_schemas = domain._method_schemas
                    unavailable_checks = 0

                    async def unavailable_schema(
                        conn: AsyncConnection,
                        owner: str,
                        run_record: dict[str, object],
                        bound: dict[str, object],
                    ) -> dict[str, dict[str, object]]:
                        nonlocal unavailable_checks
                        unavailable_checks += 1
                        if unavailable_checks == 1:
                            # Controlled qualification unavailability only on
                            # the first independent check, never a fake result.
                            return {}
                        return await qualified_schemas(conn, owner, run_record, bound)

                    monkeypatch.setattr(domain, "_method_schemas", unavailable_schema)
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
                        if early_return:
                            original_check = domain.check

                            async def persisted_before_check(
                                owner_id: str, command_id: str
                            ) -> dict[str, object]:
                                persisted = await domain.readback(
                                    seed.request(command_id=command_id)
                                )
                                assert len(sequence(persisted["results"])) == 1
                                assert persisted["checks"] == []
                                raw = mapping(sequence(persisted["results"])[0])
                                assert mapping(raw["payload"])["status"] == (
                                    "INCONCLUSIVE" if incomplete else "SUCCEEDED"
                                )
                                assert len(sequence(mapping(raw["payload"])["method_results"])) == 3
                                checkpoint(raw_partial_persisted_before_method_check="PASS")
                                return await original_check(owner_id, command_id)

                            pause.setattr(domain, "check", persisted_before_check)
                        released = await submit_task("release")
                assert seam_calls == int(first_final_after_stop and not lost_reply)
                assert released["task_status"] == ("BLOCKED" if incomplete else "SUCCEEDED")
                assert released["binding_ref"] == staged["binding_ref"]
                back_request = seed.request(command_id=assignment["command_id"])
                back = await domain.readback(back_request)
                binding = mapping(back["binding"])
                assert mapping(mapping(binding["payload"])["authority"])["owner"] == str(supervisor)
                assert mapping(binding["payload"])["runtime_boot"] == runtime.boot
                assert back["status"] == ("BLOCKED" if incomplete else "SUCCEEDED")
                if with_criteria:
                    outcomes = [mapping(o) for o in sequence(back["criterion_outcomes"])]
                    assert len(outcomes) == 2
                    payloads = [mapping(o["payload"]) for o in outcomes]
                    from omnis.modules.tasks.criterion_checks import REASON

                    assert all(
                        p["reason"]
                        == REASON
                        + (
                            " MethodCheck is UNKNOWN; method eligibility remains unestablished."
                            if applicability == "unknown"
                            else ""
                        )
                        for p in payloads
                    )
                    assert {p["criterion_id"] for p in payloads} == set(criterion_ids)
                    assert all(
                        p["outcome"] == "BLOCKED"
                        and p["gaps"]
                        == [
                            "ORACLE_UNAVAILABLE",
                            "CONTROLS_UNAVAILABLE",
                            *(
                                ["METHOD_UNKNOWN"]
                                if applicability == "unknown"
                                else ["METHOD_INCOMPLETE"]
                                if incomplete
                                else []
                            ),
                        ]
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
                assert len(receipts) == (2 if early_return else 3) and len(artifacts) == (
                    1 if early_return else 2
                )
                ordered = sorted(
                    receipts, key=lambda r: integer(mapping(r["payload"])["sequence"], 0)
                )
                assert [mapping(r["payload"])["sequence"] for r in ordered] == (
                    [0, 1] if early_return else [0, 1, 2]
                )
                assert mapping(ordered[0]["payload"])["output_ref"] == original["input_ref"]
                checks = [mapping(r) for r in sequence(back["checks"])]
                expected_check = (
                    "UNKNOWN"
                    if applicability == "unknown"
                    else "INCOMPLETE"
                    if incomplete
                    else "COMPLETE"
                )
                if applicability == "invalidation":
                    bound = next(r for r in graph if r["kind"] == "bound-procedure")
                    procedure = mapping(mapping(bound["payload"])["resolved_procedure"])
                    assert procedure["invalidation_predicate_ids"] == ["contract.records-empty"]
                    methods = [
                        mapping(r) for r in sequence(mapping(result["payload"])["method_results"])
                    ]
                    assert len(methods) == 3 and all(r["state"] == "DONE" for r in methods)
                    checkpoint(
                        invalidation_native="NOT_INVALIDATED",
                        invalidation_method_check=expected_check,
                    )
                if applicability in {"applies", "not-applicable", "unknown"}:
                    plan = mapping(mapping(sequence(back["briefs"])[0])["payload"])["method_plan"]
                    planned = [mapping(r) for r in sequence(mapping(plan)["requirements"])]
                    assert [r["required"] for r in planned] == [True, True, False]
                    assert planned[1]["applicability"] == (
                        "NOT_APPLICABLE" if applicability == "not-applicable" else "APPLIES"
                    )
                    assert planned[1]["applicability_basis_refs"] == [original["input_ref"]]
                    methods = [
                        mapping(r) for r in sequence(mapping(result["payload"])["method_results"])
                    ]
                    assert methods[1]["state"] == (
                        "NOT_APPLICABLE" if applicability == "not-applicable" else "DONE"
                    )
                    if applicability == "not-applicable":
                        assert mapping(result["payload"])["status"] == "INCONCLUSIVE"
                        assert methods[1]["basis_refs"] == [original["input_ref"]]
                    checkpoint(
                        applicability=applicability,
                        retained_method_plan=plan,
                        unknown_is_not_na=expected_check == "UNKNOWN",
                    )
                assert (
                    len(checks) == 1 and mapping(checks[0]["payload"])["status"] == expected_check
                )
                if early_return:
                    methods = [
                        mapping(r) for r in sequence(mapping(result["payload"])["method_results"])
                    ]
                    assert [m["state"] for m in methods] == [
                        "PARTIAL" if applicability == "partial-requirement-prefix" else "DONE",
                        "NOT_RUN",
                        "DONE",
                    ]
                    assert mapping(result["payload"])["status"] == (
                        "INCONCLUSIVE" if incomplete else "SUCCEEDED"
                    )
                    assert mapping(checks[0]["payload"])["gap_refs"] == (
                        [m["ref"] for m in methods[:2]]
                        if applicability == "partial-requirement-prefix"
                        else [methods[1]["ref"]]
                    )
                if applicability is not None and applicability.startswith("partial-requirement-"):
                    from omnis.modules.settings import candidate_store as stored

                    body = mapping(result["payload"])
                    methods = [mapping(r) for r in sequence(body["method_results"])]
                    assert [m["state"] for m in methods] == (
                        ["PARTIAL", "NOT_RUN", "DONE"] if early_return else ["DONE"] * 3
                    )
                    assert methods[0]["basis_refs"] == [stored.reference(r) for r in ordered[1:]]
                    assert methods[0]["artifact_refs"] == [
                        mapping(r["payload"])["output_ref"] for r in ordered[1:]
                    ]
                    assert methods[2]["artifact_refs"] == [original["input_ref"]]
                    assert body["gaps"] == (
                        [
                            "PARTIAL: normalize-records (qualified early return).",
                            "NOT_RUN: build-surface-map (qualified early return).",
                        ]
                        if early_return
                        else []
                    )
                    assert body["evidence_refs"] == []
                    assert mapping(checks[0]["payload"])["checked_results"] == methods
                    checkpoint(
                        partial_requirement_method_results=methods,
                        partial_requirement_gaps=body["gaps"],
                        partial_requirement_check=expected_check,
                    )
                if applicability is not None and applicability.startswith("evidence-"):
                    from omnis.modules.settings import candidate_store as stored

                    body = mapping(result["payload"])
                    actual_proof = [stored.reference(a) for a in artifacts]
                    assert body["evidence_refs"] == actual_proof
                    methods = [mapping(r) for r in sequence(body["method_results"])]
                    assert len(methods) == 3
                    for index in range(1 if early_return else 2):
                        assert methods[index]["artifact_refs"] == [actual_proof[index]]
                    brief_body = mapping(mapping(sequence(back["briefs"])[0])["payload"])
                    assert brief_body["required_evidence"] == [
                        methods[0]["ref"],
                        *(
                            []
                            if applicability == "evidence-optional-prefix"
                            else [methods[1]["ref"]]
                        ),
                    ]
                    assert body["gaps"] == ([methods[1]["reason"]] if early_return else [])
                    assert methods[2]["artifact_refs"] == [original["input_ref"]]
                    checkpoint(
                        evidence_scenario=applicability,
                        actual_evidence_refs=actual_proof,
                        method_results=methods,
                        task_result_status=body["status"],
                        method_gaps=body["gaps"],
                        required_evidence=brief_body["required_evidence"],
                        method_check=expected_check,
                    )
                if with_criteria:
                    checkpoint(bound_predicate_persistent_check=expected_check)
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
                    "contract-tool-receipt": 2 if early_return else 3,
                    "contract-artifact": 1 if early_return else 2,
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
            if applicability == "mission-consumer":
                from omnis.modules.settings import candidate_store as stored
                from omnis.modules.tasks import managed_store

                m1_back = deepcopy(back)
                m1_graph = [mapping(r) for r in sequence(back["records"])]
                mission = next(r for r in m1_graph if r["kind"] == "mission")
                append_request = seed.write(
                    schema_version=1,
                    context_ref=context["context_ref"],
                    mission_ref=stored.reference(mission),
                    criterion_id=str(uuid4()),
                )

                async def private_input_cli(
                    operation: str, value: dict[str, object] | bytes, *, reason: str | None = None
                ) -> dict[str, object]:
                    path = tmp_path / ("mission-command-" + uuid4().hex + ".json")
                    path.write_bytes(value if isinstance(value, bytes) else canonical(value))
                    path.chmod(0o600)
                    child = await asyncio.create_subprocess_exec(
                        str(python),
                        "-I",
                        "-B",
                        "-c",
                        "import sys;sys.path.insert(0,sys.argv[1]);from omnis.modules.runs.contract_inputs import main;raise SystemExit(main(sys.argv[2:]))",
                        str(ROOT / "api/src"),
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
                        stdout, stderr = await asyncio.wait_for(child.communicate(), 20)
                    finally:
                        if child.returncode is None:
                            child.kill()
                            await child.wait()
                    for suffix, raw in (("stdout", stdout), ("stderr", stderr)):
                        output = path.with_suffix("." + suffix)
                        output.write_bytes(raw)
                        output.chmod(0o600)
                    if reason is not None:
                        expected = canonical({"status": "BLOCKED", "reason": reason}) + b"\n"
                        if (child.returncode, stdout, stderr) != (2, b"", expected):
                            raise AssertionError("PRIVATE_MISSION_DENIAL_TUPLE_MISMATCH")
                        return {}
                    if child.returncode != 0:
                        raise AssertionError("PRIVATE_MISSION_COMMAND_FAILED")
                    require_empty_stderr(stderr)
                    return mapping(json.loads(stdout))

                rollback_census = await mission_census()
                async with engine.begin() as conn:
                    await managed_store.lock(conn, seed.owner)
                    for table in ("managed_run", "managed_task", "managed_inbox"):
                        await conn.execute(
                            sql(
                                f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"
                            )
                        )
                    await inputs._require_settled(conn, seed.owner, str(back["run_id"]), m1_graph)
                if await mission_census() != rollback_census:
                    raise AssertionError("MISSION_TERMINAL_SHADOW_CENSUS_CHANGED")
                rollback_markers = await markers()

                async def fail_receipt(*args: object, **kwargs: object) -> None:
                    raise CatalogError("TEST_RECEIPT_ROLLBACK")

                with monkeypatch.context() as rollback:
                    rollback.setattr(managed_store, "command_complete", fail_receipt)
                    with pytest.raises(CatalogError, match="TEST_RECEIPT_ROLLBACK"):
                        await inputs.append_mission(append_request)
                assert await markers() == rollback_markers
                if await mission_census() != rollback_census:
                    raise AssertionError("MISSION_ROLLBACK_CENSUS_CHANGED")
                async with engine.connect() as conn:
                    assert (
                        await conn.execute(
                            sql(
                                "SELECT count(*) FROM public.managed_mission_revision WHERE run_id=:run"
                            ),
                            {"run": back["run_id"]},
                        )
                    ).scalar_one() == 0
                assert canonical(await domain.readback(back_request)) == canonical(m1_back)
                appended = await private_input_cli("append-mission", append_request)
                assert appended["created"] is True
                assert (await private_input_cli("append-mission", append_request))[
                    "created"
                ] is False
                read_request = {
                    k: append_request[k] for k in ("schema_version", "owner_id", "command_id")
                }
                read = await private_input_cli("read-mission", read_request)
                m2 = mapping(read["mission"])
                assert read["predecessor"] == mission and m2["id"] == mission["id"]
                assert m2["revision"] == 2
                shadow_census = await mission_census()
                async with engine.begin() as conn:
                    await managed_store.lock(conn, seed.owner)
                    # Same-session shadows cannot replace attested public rows.
                    await conn.execute(
                        sql(
                            "CREATE TEMP TABLE managed_record (id uuid,owner_id uuid,run_id uuid,envelope jsonb) ON COMMIT DROP"
                        )
                    )
                    await conn.execute(
                        sql(
                            "CREATE TEMP TABLE managed_mission_revision (mission_id uuid,owner_id uuid,run_id uuid,revision bigint,envelope jsonb) ON COMMIT DROP"
                        )
                    )
                    assert (
                        await managed_store.get(
                            conn, seed.owner, str(back["run_id"]), stored.reference(mission)
                        )
                        == mission
                    )
                    assert (
                        await managed_store.get(
                            conn, seed.owner, str(back["run_id"]), appended["mission_ref"]
                        )
                        == m2
                    )
                    assert (
                        await managed_store.by_id(
                            conn, seed.owner, str(back["run_id"]), mission["id"]
                        )
                        == mission
                    )
                    assert (
                        await conn.execute(
                            sql(
                                "SELECT count(*) FROM public.managed_mission_revision WHERE run_id=:run"
                            ),
                            {"run": back["run_id"]},
                        )
                    ).scalar_one() == 1
                    for wrong in (
                        {**mapping(appended["mission_ref"]), "digest": "0" * 64},
                        {**mapping(appended["mission_ref"]), "revision": True},
                        {**mapping(appended["mission_ref"]), "kind": "focus"},
                    ):
                        with pytest.raises(CatalogError):
                            await managed_store.get(conn, seed.owner, str(back["run_id"]), wrong)
                        if await mission_snapshot(conn) != shadow_census:
                            raise AssertionError("MISSION_SHADOW_DENIAL_CENSUS_CHANGED")
                back = await domain.readback(back_request)
                added = [
                    mapping(r)
                    for r in sequence(back["records"])
                    if mapping(r)["id"] not in {r["id"] for r in m1_graph}
                ]
                assert len(added) == 1 and added[0]["kind"] == "contract-input-command"
                historical_records = [
                    mapping(r)
                    for r in sequence(back["records"])
                    if mapping(r)["revision"] == 1 and mapping(r)["id"] != added[0]["id"]
                ]
                assert canonical(historical_records) == canonical(m1_graph)
                for field in (
                    "briefs",
                    "results",
                    "checks",
                    "criterion_outcomes",
                    "tasks",
                    "inbox",
                    "binding",
                    "manifest",
                ):
                    assert canonical(back[field]) == canonical(m1_back[field])
                assert overlap_operations == ["stage", "release"]
                # Opposite ordering on one fresh, never-dispatched assignment.
                # Release cannot have an authentic binding here: the real
                # BINDING_REQUIRED denial must not be bypassed with a fake one.
                fresh_context = await inputs.create_method_context(
                    seed.write(
                        schema_version=2,
                        selection_ref=selected["selection_ref"],
                        preparation_command_id=preparation.command_id,
                    )
                )
                fresh_input = await inputs.create_input(
                    seed.write(
                        schema_version=2,
                        context_ref=fresh_context["context_ref"],
                        input=value,
                    )
                )
                fresh_assignment = {
                    **assignment,
                    "command_id": str(uuid4()),
                    "context_ref": fresh_context["context_ref"],
                    "slot_values": [{"slot_name": "records", "refs": [fresh_input["input_ref"]]}],
                }
                fresh = await domain.prepare_method(fresh_assignment)
                fresh_request = seed.write(
                    schema_version=1,
                    context_ref=fresh_context["context_ref"],
                    mission_ref=mapping(
                        mapping(mapping(sequence(fresh["briefs"])[0])["payload"])["header"]
                    )["mission_revision"],
                    criterion_id=str(uuid4()),
                )
                qualified = inputs.current_source

                async def reserve_fresh(operation: str) -> dict[str, object]:
                    async with engine.begin() as conn:
                        return await reserve_dispatch(
                            conn, seed.owner, fresh["manifest_ref"], operation
                        )

                async def append_holds_lock(
                    conn: AsyncConnection,
                    owner_id: str,
                    context_record: object,
                    graph: list[dict[str, object]],
                ) -> BuildSource:
                    source = await qualified(conn, owner_id, context_record, graph)
                    blocker = (await conn.execute(sql("SELECT pg_backend_pid()"))).scalar_one()
                    for operation in ("stage", "release"):
                        dispatch_waiters.append(asyncio.create_task(reserve_fresh(operation)))
                    async with asyncio.timeout(0.75), engine.connect() as observer:
                        while True:
                            blocked = 0
                            for waiter in dispatch_waiters[-2:]:
                                pid = waiter_pids.get(waiter)
                                if (
                                    pid is not None
                                    and blocker
                                    in (
                                        await observer.execute(
                                            sql("SELECT pg_blocking_pids(:waiter)"), {"waiter": pid}
                                        )
                                    ).scalar_one()
                                ):
                                    blocked += 1
                            if blocked == 2:
                                break
                            if any(t.done() for t in dispatch_waiters[-2:]):
                                raise AssertionError("MISSION_DISPATCH_DID_NOT_WAIT")
                            await asyncio.sleep(0.01)
                    return source

                with monkeypatch.context() as append_pause:
                    append_pause.setattr(inputs, "current_source", append_holds_lock)
                    fresh_append = await inputs.append_mission(fresh_request)
                fresh_census = await mission_census()
                for waiter, reason in zip(
                    dispatch_waiters[-2:],
                    ("MISSION_REVISION_NEW_WORK_UNSUPPORTED", "BINDING_REQUIRED"),
                    strict=True,
                ):
                    with pytest.raises(CatalogError, match="^" + reason + "$"):
                        await asyncio.wait_for(waiter, 0.75)
                    if await mission_census() != fresh_census:
                        raise AssertionError("MISSION_DISPATCH_DENIAL_CENSUS_CHANGED")
                assert fresh_append["created"] is True
                assert canonical(await domain.readback(back_request)) == canonical(back)
                durable_markers = await markers()
                durable_census = await mission_census()
                for bad, reason in (
                    ({**append_request, "criterion_id": str(uuid4())}, "COMMAND_CONFLICT"),
                    ({**append_request, "owner_id": str(uuid4())}, "REF_UNAVAILABLE"),
                    (
                        {
                            **append_request,
                            "mission_ref": {**stored.reference(mission), "digest": "0" * 64},
                        },
                        "REF_MISMATCH",
                    ),
                    ({**append_request, "criterion_id": True}, "INVALID_REQUEST"),
                    ({**append_request, "mission_ref": stored.reference(m2)}, "MANAGED_REJECTED"),
                    ({**append_request, "command_id": str(uuid4())}, "MISSION_REVISION_CONFLICT"),
                    (b"\xef\xbb\xbf" + canonical(append_request), "INVALID_JSON"),
                ):
                    await private_input_cli("append-mission", bad, reason=reason)
                    assert await markers() == durable_markers
                    if await mission_census() != durable_census:
                        raise AssertionError("MISSION_DENIAL_CENSUS_CHANGED")
                with pytest.raises(CatalogError, match="MISSION_REVISION_NEW_WORK_UNSUPPORTED"):
                    await domain.prepare_method({**assignment, "command_id": str(uuid4())})
                if await mission_census() != durable_census:
                    raise AssertionError("MISSION_PREPARE_DENIAL_CENSUS_CHANGED")
                async with engine.begin() as conn:
                    with pytest.raises(CatalogError, match="MISSION_REVISION_NEW_WORK_UNSUPPORTED"):
                        await domain.stage_payload(conn, seed.owner, prepared["manifest_ref"])
                if await mission_census() != durable_census:
                    raise AssertionError("MISSION_STAGE_DENIAL_CENSUS_CHANGED")
                assert await markers() == durable_markers
                assert observation.read_bytes() == native_before
                checkpoint(
                    mission_revision_consumer="M1_IMMUTABLE_M2_APPENDED",
                    mission_refs=[stored.reference(mission), appended["mission_ref"]],
                    mission_new_work="REFUSED_BEFORE_WRITES_NATIVE",
                    mission_private_cli="APPEND_REPLAY_READ_AND_SEVEN_EXACT_DENIAL_TUPLES",
                    mission_overlap="RESERVATION_FIRST_STAGE_RELEASE_AND_APPEND_FIRST_STAGE_RELEASE",
                    mission_append_first_release="BINDING_REQUIRED_NO_FABRICATED_BINDING",
                    mission_census="ALL_FIVE_TABLE_ROWS_AND_ENVELOPES_EXACT_AFTER_EACH_FAULT_DENIAL",
                    mission_atomic_receipt_rollback="PASS",
                    mission_same_session_temp_shadow_reads="PUBLIC_EXACT",
                )
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
                assert (await submit_task("release"))["task_status"] == (
                    "BLOCKED" if incomplete else "SUCCEEDED"
                )
                if public_control is not None:
                    assert (await submit_task("receive"))["task_status"] == (
                        "BLOCKED" if incomplete else "SUCCEEDED"
                    )
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
            if public_control is not None:
                # Stop is the generation/fence transition above, not Host retirement.
                # Only the already committed result/check may reach this public reader.
                with monkeypatch.context() as receive_only:
                    for module in ("skill_catalog", "candidate_catalog"):
                        receive_only.setattr(
                            "omnis.modules.settings." + module + ".evaluate_pure", no_rerun
                        )
                    receive_only.setattr("omnis.modules.runs.pure_probe.evaluate_pure", no_rerun)
                    receive_only.setattr(
                        "omnis.modules.tasks.module_registry.run_handler", no_rerun
                    )
                    receive_only.setattr(BuildSource, "build", no_rerun)
                    receive_only.setattr(ManagedAdmission, "_build", no_rerun)
                    receive_only.setattr(runtime, "_exchange", no_rerun)
                    assert (await submit_task("release", phase="AFTER_STOP"))["task_status"] == (
                        "BLOCKED" if incomplete else "SUCCEEDED"
                    )
                    assert (await submit_task("receive", phase="AFTER_STOP"))["task_status"] == (
                        "BLOCKED" if incomplete else "SUCCEEDED"
                    )
                assert execution_attempts == []
                assert observation.read_bytes() == native_before
                assert await markers() == consumed_markers
                assert canonical(await domain.readback(back_request)) == canonical(prior)
                checkpoint(public_post_stop_cached_read="PASS")
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
            for waiter in dispatch_waiters:
                if not waiter.done():
                    waiter.cancel()
            await asyncio.gather(*dispatch_waiters, return_exceptions=True)
            done.set()
            try:
                if heartbeat is not None:
                    await heartbeat
            finally:
                try:
                    if runtime is not None:
                        await runtime.close()
                finally:
                    try:
                        if public_control is not None:
                            await public_control.__aexit__(None, None, None)
                            assert public_control.lock_fd is None
                            assert not (public_control.directory / "control.sock").exists()
                            assert not (public_control.directory / "control.cap").exists()
                            checkpoint(public_control_cleanup="PASS")
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
        assert len([r for r in rows if r["test"] == "run_handler"]) == (1 if early_return else 2)
        assert {
            "test": "native-release",
            "status": "INCONCLUSIVE" if incomplete and applicability != "unknown" else "SUCCEEDED",
            "count": 1,
        } in rows
        if with_criteria and not legacy_criteria:
            assert [r for r in rows if r["test"] == "bound-predicates"] == (
                [{"test": "bound-predicates", "status": "GAP", "count": 3}] * 2
                if early_return
                else [{"test": "bound-predicates", "status": "SATISFIED", "count": 3}]
            )
            checkpoint(
                native_bound_predicate_evaluation="GAP" if early_return else "SATISFIED",
                native_bound_predicate_count=3,
            )
        checkpoint(
            native_run_contract=1,
            native_reads=1,
            native_handlers=1 if early_return else 2,
            forbidden_native_attempts=0,
            status="PASS_SOURCE_NOT_INSTALLED",
        )

    asyncio.run(run())
