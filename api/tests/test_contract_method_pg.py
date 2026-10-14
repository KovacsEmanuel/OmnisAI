"""One private PG -> existing owner -> real pinned native CONTRACT/PURE journey.

SOURCE_HOST_NOT_INSTALLED: stock inert stdio + NativePeer + RuntimeHost and
RuntimeClient, not an OCI/installed gate. Only document preparation is the reused
qualification prerequisite double. No native result/runtime/peer is substituted.
The full source pin must already exist; this test never installs or downloads it.
"""

import asyncio
import importlib
import inspect
import json
import os
import re
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Coroutine, Generator, Iterator
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, cast
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

if TYPE_CHECKING:
    from omnis_hermes.runtime_host import RuntimeHost

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
def emit(test, status, count=1, **fields):
    raw = json.dumps({"test": test, "status": status, "count": count, **fields},
                     separators=(",", ":")).encode() + b"\n"
    if getattr(emit_thread, "active", False):
        raise RuntimeError("Observer unavailable")
    emit_thread.active = True
    try:
        with emit_lock:
            if emit.events >= 256 or len(raw) > 4096 or emit.bytes + len(raw) > 65536:
                raise RuntimeError("Observer limit exceeded")
            if os.write(evidence_fd, raw) != len(raw):
                raise RuntimeError("Observer unavailable")
            emit.events += 1
            emit.bytes += len(raw)
    finally:
        emit_thread.active = False
emit.events = 0
emit.bytes = 0
emit_lock = threading.Lock()
emit_thread = threading.local()
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
from types import CodeType
# Ten fixed boundaries. LINE is local to these exact code objects, never global.
# END means the next fixed source boundary or PY_RETURN was reached, not READY.
phase_inventory = {
    (str(inert / "tui_gateway/entry.py"), "<module>", 1): (
        "ENTRY_MODULE_BEGIN", {23: ("ENTRY_SERVER_IMPORT_BEGIN", "ENTER"),
                                24: ("ENTRY_SERVER_IMPORT_BEGIN", "END")}),
    (str(inert / "tui_gateway/server.py"), "<module>", 1): (
        None, {36: ("SERVER_CONVERSATION_IMPORT_BEGIN", "ENTER"),
               37: ("SERVER_CONVERSATION_IMPORT_BEGIN", "END"),
               3363: ("SERVER_SPLIT_HANDLERS_IMPORT_BEGIN", "ENTER"),
               3386: ("SERVER_SPLIT_HANDLERS_IMPORT_BEGIN", "END")}),
    (str(managed / "agent/conversation_loop.py"), "<module>", 1): (
        "CONVERSATION_MODULE_BEGIN", {40: ("CONVERSATION_TURN_API_IMPORT_BEGIN", "ENTER"),
                                      41: ("CONVERSATION_TURN_API_IMPORT_BEGIN", "END")}),
    (str(managed / "tui_gateway/rpc_dispatch.py"), "<module>", 1): (
        "MANAGED_RPC_DISPATCH_MODULE_BEGIN", {}),
    (str(inert / "tui_gateway/entry.py"), "main", 439): (
        "ENTRY_MAIN_BEGIN", {464: ("ENTRY_READY_WRITE_BEGIN", "ENTER"),
                             469: ("ENTRY_READY_WRITE_BEGIN", "END")}),
}
phase_codes = {}
phase_entered = set()
phase_completed = set()
phase_labels = {"BOOTSTRAP_RUNPY_ENTRY_BEGIN"} | {
    label for label, lines in phase_inventory.values() if label is not None
} | {label for _, lines in phase_inventory.values() for label, edge in lines.values()}
def phase_transition(label, edge):
    if type(label) is not str or label not in phase_labels or type(edge) is not str or edge not in {"ENTER", "END"}:
        raise RuntimeError("Observer invalid phase")
    if edge == "ENTER":
        if label in phase_entered:
            return
        phase_entered.add(label)
    elif label not in phase_entered or label in phase_completed:
        return
    else:
        phase_completed.add(label)
    elapsed = (time.monotonic_ns() - bootstrap_started_ns) // 1_000_000
    metrics = (elapsed, audit_ns // 1_000_000, audit_calls)
    if any(type(value) is not int or not 0 <= value <= 10**12 for value in metrics):
        raise RuntimeError("Observer limit exceeded")
    emit("bootstrap-phase", label, edge=edge, elapsed_ms=metrics[0],
         audit_ms=metrics[1], audit_calls=metrics[2])
def phase_key(code):
    if type(code) is not CodeType:
        return None
    key = (code.co_filename, code.co_name, code.co_firstlineno)
    if key not in phase_inventory or code.co_qualname != code.co_name:
        return None
    if code.co_name == "<module>" and code.co_flags & 3:
        return None
    return key
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
observer_roots = tuple(str(root) + "/" for root in (source, managed, inert, adapter))
def monitored(code):
    return (type(code) is CodeType and code.co_name in observed
            and code.co_filename.startswith(observer_roots))
def monitor_call(code, offset):
    key = phase_key(code)
    if key is not None:
        bound = phase_codes.get(key)
        if bound is None:
            phase_codes[key] = code
            label, lines = phase_inventory[key]
            if lines:
                sys.monitoring.set_local_events(observer_id, code, sys.monitoring.events.LINE)
            if label is not None:
                phase_transition(label, "ENTER")
        elif bound is not code:
            return sys.monitoring.DISABLE
    if not monitored(code):
        return None if key is not None else sys.monitoring.DISABLE
    observe(sys._getframe(1), "call", None)
def monitor_return(code, offset, value):
    key = phase_key(code)
    if key is not None and phase_codes.get(key) is code:
        label, lines = phase_inventory[key]
        if label is not None:
            phase_transition(label, "END")
    if not monitored(code):
        return None if key is not None else sys.monitoring.DISABLE
    observe(sys._getframe(1), "return", value)
def monitor_line(code, line):
    key = phase_key(code)
    if key is None or phase_codes.get(key) is not code:
        return sys.monitoring.DISABLE
    boundary = phase_inventory[key][1].get(line)
    if boundary is not None:
        phase_transition(*boundary)
    # DISABLE only this non-boundary line; other fixed boundaries remain active.
    else:
        return sys.monitoring.DISABLE
observer_id = sys.monitoring.PROFILER_ID
sys.monitoring.use_tool_id(observer_id, "omnis-contract-observer")
sys.monitoring.register_callback(observer_id, sys.monitoring.events.PY_START, monitor_call)
sys.monitoring.register_callback(observer_id, sys.monitoring.events.PY_RETURN, monitor_return)
sys.monitoring.register_callback(observer_id, sys.monitoring.events.LINE, monitor_line)
sys.monitoring.set_events(observer_id, sys.monitoring.events.PY_START | sys.monitoring.events.PY_RETURN)
emit("observer", "READY")
phase_transition("BOOTSTRAP_RUNPY_ENTRY_BEGIN", "ENTER")
try:
    runpy.run_module("tui_gateway.entry", run_name="__main__")
    phase_transition("BOOTSTRAP_RUNPY_ENTRY_BEGIN", "END")
except BaseException as error:
    if type(error) is SystemExit and (error.code is None or type(error.code) is int and error.code == 0):
        emit("bootstrap-exit", "NORMAL_SYSTEM_EXIT")
    else:
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
installed = source == "INSTALLED"
if not installed:
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
if installed:
    # The compiler's defining evaluator and its imported aliases are all
    # instrumented above. Verify real package origins, not version metadata.
    prefix = Path(sys.prefix).absolute()
    modules = [importlib.import_module(name) for name in (
        "omnis.modules.settings.skill_catalog", "omnis.modules.settings.candidate_catalog",
        "omnis.modules.runs.pure_probe", "omnis.modules.tasks.module_registry",
        "omnis.modules.tasks.method_checks", "omnis.modules.tasks.method_checker_identity",
        "omnis.modules.runs.managed_admission", "omnis.supervisor.runtime_client")]
    if any(not Path(item.__file__).absolute().is_relative_to(prefix) for item in modules):
        emit("FORBIDDEN", "non-installed-origin")
        raise AssertionError("HISTORICAL_READER_ORIGIN_REFUSED")
    if any(Path(p).absolute().name == "src" or "/api/src" in p for p in sys.path):
        emit("FORBIDDEN", "source-sys-path")
        raise AssertionError("HISTORICAL_READER_ORIGIN_REFUSED")
    for name in ("connect", "_exchange", "prepare", "managed", "receive", "launch_inert", "renew"):
        setattr(client.RuntimeClient, name, deny("RuntimeClient." + name))
    emit("ORIGIN", "INSTALLED")
emit("READY", "managed-cli")
try:
    if installed and sys.argv[3] == "--history-control":
        # SOURCE controls exercise actual patched defining objects. A child
        # swallowing the exception still records FORBIDDEN independently.
        if len(sys.argv) == 5:
            selected = sys.argv[4]
            guards = {
                "skill_catalog.evaluate_pure": modules[0].evaluate_pure,
                "candidate_catalog.evaluate_pure": modules[1].evaluate_pure,
                "pure_probe.evaluate_pure": modules[2].evaluate_pure,
                "module_registry.run_handler": modules[3].run_handler,
                "BuildSource.build": module.BuildSource.build,
                "RuntimeClient._exchange": client.RuntimeClient._exchange,
            }
            try:
                guards[selected]()
            except AssertionError:
                pass
        code = 0
    else:
        code = module.main(sys.argv[3:])
    emit("EXIT", str(code))
    raise SystemExit(code)
finally:
    os.close(fd)
"""


HISTORICAL_COMMIT = "e6ffcf8ede7393332e6a928a00585ff0327a3d6a"
HISTORICAL_CALLER_SHA = "c498b38264e0f0238f6087d6e410cfe70fff2a54197e5b23f616a6bf920a0e6f"
HISTORICAL_CHECKER = "833b5690ada0c2669114dc7fc3755300d96116b773f9eb0c412fba024fac8fd9"
HISTORICAL_COMPOSER = "1042abaf48dae5e14a7fee5c879b68fb57313f7e53698a43becf5a57e7a52338"


def historical_migration_argv(python: Path, *, initialize: bool) -> list[str]:
    return [
        str(python),
        "-I",
        "-B",
        "-m",
        "omnis.migrate",
        *(["--initialize"] if initialize else []),
    ]


def historical_producer_source(original: bytes) -> str:
    """Harness adaptation only: old domain/native bytes and original finalizer.

    Stop after the authentic final/check and native drain, before old reader
    reconciliation and the intentional forged-outcome append. Current installed
    reader owns the first consumption. BOOTSTRAP is the reviewed observer seam;
    neither its routing nor these edits substitute domain/compiler/native bytes.
    """
    if sha(original) != HISTORICAL_CALLER_SHA:
        raise AssertionError("HISTORICAL_CALLER_BYTES_MISMATCH")
    import ast

    value = original.decode()
    tree = ast.parse(value)
    bootstrap = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "BOOTSTRAP"
    )
    lines = value.splitlines(keepends=True)
    assert bootstrap.end_lineno is not None
    observer_bootstrap = BOOTSTRAP.replace(
        'Path("/home/kali/OmnisAI/api/.venv")', "Path(sys.prefix)"
    )
    lines[bootstrap.lineno - 1 : bootstrap.end_lineno] = [
        "BOOTSTRAP = " + repr(observer_bootstrap) + "\n"
    ]
    value = "".join(lines)
    value = value.replace(
        'python = Path("/home/kali/OmnisAI/api/.venv/bin/python")',
        "python = Path(sys.executable)",
        1,
    )
    start = value.index(
        "            with monkeypatch.context() as patcher:",
        value.index("            native_before = observation.read_bytes()"),
    )
    end = value.index("        finally:\n            done.set()", start)
    value = (
        value[:start]
        + """            done.set()
            await heartbeat
            await service.shutdown(uuid4(), status.generation, supervisor, epoch)
            prior = await domain.readback(back_request)
            assert observation.read_bytes() == native_before
            handoff = tmp_path / "historical-handoff.json"
            handoff.write_bytes(canonical({
                "request": back_request, "catalog_root": str(seed.root),
                "readback": prior, "final": final,
                "native_observation": str(observation),
                "producer_proof": str(proof_path),
                "consumption_before_reader": (await markers())["consumed"],
            }))
            handoff.chmod(0o600)
            checkpoint(historical_handoff="AUTHENTIC_UNCONSUMED_FINAL_CHECK_STOPPED")
"""
        + value[end:]
    )
    # Module-scoped fixture wins over exported conftest. No source Alembic,
    # new database, or initialize here: the parent owns the fresh empty fixture.
    value += """\n@pytest.fixture
def migrated_database_url():
    from sqlalchemy.engine import make_url
    return make_url(os.environ["OMNIS_HISTORY_DATABASE_URL"])

# Test harness paths are allowed; every domain import must be the old wheel.
from omnis.modules.tasks.method_checker_identity import descriptor
assert descriptor()["code_digest"] == "833b5690ada0c2669114dc7fc3755300d96116b773f9eb0c412fba024fac8fd9", "OLD_INSTALLED_CHECKER_REQUIRED"
for name in ("omnis.core.db", "omnis.modules.runs.managed_admission", "omnis.modules.tasks.method_checks", "omnis.modules.settings.skill_catalog", "omnis.supervisor.native_tasks"):
    assert Path(importlib.import_module(name).__file__).absolute().is_relative_to(Path(sys.prefix).absolute()), "OLD_INSTALLED_DOMAIN_ORIGIN_REQUIRED"
assert not any("/api/src" in item for item in sys.path), "OLD_SOURCE_ALIAS_FORBIDDEN"
"""
    return value


def test_historical_producer_cut_preserves_authentic_bytes_and_teardown() -> None:
    """SOURCE: only adapt the historical caller, never execute its producer."""
    assert callable(globals().get("historical_producer_source")), "HISTORICAL_ORCHESTRATION_MISSING"
    old = subprocess.run(
        [
            "git",
            "show",
            "e6ffcf8ede7393332e6a928a00585ff0327a3d6a:api/tests/test_contract_method_pg.py",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    adapted = historical_producer_source(old)
    assert "forged_outcome_readback" not in adapted
    assert "adversarial_append_count" not in adapted
    assert "historical-handoff.json" in adapted
    assert "await runtime.close()" in adapted
    assert '"NATIVE_FAMILY_UNCERTAIN"' in adapted
    assert "final," in adapted and "prior = await domain.readback(back_request)" in adapted
    assert "python = Path(sys.executable)" in adapted
    assert "OMNIS_HISTORY_DATABASE_URL" in adapted
    with pytest.raises(AssertionError, match="HISTORICAL_CALLER_BYTES_MISMATCH"):
        historical_producer_source(old + b"\n")


def test_historical_producer_environment_satisfies_actual_skip_decorator() -> None:
    """Evaluate the actual call-site environment and unchanged old skip AST only."""
    import ast
    from types import SimpleNamespace

    journey = ast.parse(inspect.getsource(historical_installed_journey)).body[0]
    assert isinstance(journey, ast.FunctionDef)
    assignment = next(
        node
        for node in journey.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "producer_env"
    )
    environment = eval(
        compile(ast.Expression(assignment.value), "<producer-env>", "eval"),
        {"environments": {"old": {}}, "os": os, "dsn": "synthetic", "old": {"python": "owned"}},
    )
    old = subprocess.run(
        ["git", "show", HISTORICAL_COMMIT + ":api/tests/test_contract_method_pg.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    adapted = ast.parse(historical_producer_source(old))
    selected = next(
        node
        for node in adapted.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_contract_method_real_native_pg_owner_receipts_check_inbox"
    )
    skip = next(
        node.args[0]
        for node in selected.decorator_list
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "skipif"
    )
    expression = compile(ast.Expression(skip), "<actual-old-skip>", "eval")
    assert eval(expression, {"os": SimpleNamespace(environ={})}) is True
    assert eval(expression, {"os": SimpleNamespace(environ=environment)}) is False
    assert environment["OMNIS_CONTRACT_METHOD_NATIVE_PG"] == "1"


def test_historical_checker_fault_changes_key_only_and_reseals_private_copy() -> None:
    from omnis.modules.settings.candidate_store import envelope
    from omnis.modules.tasks.method_checker_identity import SEMANTICS, verify

    original = envelope(
        "method-checker",
        {
            "key": "managed.contract-pure.v2",
            "code_digest": HISTORICAL_CHECKER,
            "semantics": SEMANTICS,
        },
    )
    before = canonical(original)
    verify(original, pin=HISTORICAL_COMPOSER, receive_only=True, zero_predicates=False)
    altered = historical_fault_value("foreign-checker", original)
    payload = mapping(altered["payload"])
    assert payload["key"] != mapping(original["payload"])["key"]
    assert payload["code_digest"] == HISTORICAL_CHECKER
    assert payload["semantics"] == SEMANTICS
    assert {k: v for k, v in altered.items() if k not in {"payload", "digest"}} == {
        k: v for k, v in original.items() if k not in {"payload", "digest"}
    }
    assert altered["digest"] == sha(canonical({k: v for k, v in altered.items() if k != "digest"}))
    with pytest.raises(CatalogError) as denied:
        verify(altered, pin=HISTORICAL_COMPOSER, receive_only=True, zero_predicates=False)
    assert denied.value.reason == "METHOD_CHECKER_UNAVAILABLE"  # Library, not public CLI.
    assert canonical(original) == before


def test_historical_migration_argv_is_installed_and_never_reinitializes() -> None:
    assert callable(globals().get("historical_migration_argv")), "HISTORICAL_ORCHESTRATION_MISSING"
    python = Path("/owned/venv/bin/python")
    assert historical_migration_argv(python, initialize=True) == [
        str(python),
        "-I",
        "-B",
        "-m",
        "omnis.migrate",
        "--initialize",
    ]
    assert historical_migration_argv(python, initialize=False) == [
        str(python),
        "-I",
        "-B",
        "-m",
        "omnis.migrate",
    ]


def historical_reader_observations(
    events: list[object], pid: int, exit_code: int, *, fault: str | None = None
) -> int:
    expected: list[object] = [
        {"status": "ORIGIN", "name": "INSTALLED", "pid": pid},
        {"status": "READY", "name": "managed-cli", "pid": pid},
    ]
    if fault is not None:
        expected.append({"status": "FAULT", "name": fault, "pid": pid})
    expected.append({"status": "EXIT", "name": str(exit_code), "pid": pid})
    if (
        any(
            type(event) is not dict
            or set(event) != {"status", "name", "pid"}
            or type(event["pid"]) is not int
            for event in events
        )
        or events != expected
    ):
        raise AssertionError("HISTORICAL_READER_OBSERVER_REFUSED") from None
    return sum(mapping(event)["status"] == "FORBIDDEN" for event in events)


@pytest.mark.parametrize("violation", [None, "caught", "missing", "unknown"])
def test_historical_reader_observer_never_credits_caught_or_missing_evidence(
    violation: str | None,
) -> None:
    assert callable(globals().get("historical_reader_observations")), "INSTALLED_OBSERVER_MISSING"
    events: list[object] = [
        {"status": "ORIGIN", "name": "INSTALLED", "pid": 123},
        {"status": "READY", "name": "managed-cli", "pid": 123},
        {"status": "EXIT", "name": "0", "pid": 123},
    ]
    if violation == "caught":
        events.insert(2, {"status": "FORBIDDEN", "name": "skill_catalog.evaluate_pure", "pid": 123})
    elif violation == "missing":
        events = []
    elif violation == "unknown":
        mapping(events[0])["unexpected"] = "PRIVATE_SENTINEL"
    if violation is None:
        assert historical_reader_observations(events, 123, 0) == 0
    else:
        with pytest.raises(AssertionError, match="HISTORICAL_READER_OBSERVER_REFUSED"):
            historical_reader_observations(events, 123, 0)


def test_historical_installed_reader_origin_and_defining_evaluator_guard(tmp_path: Path) -> None:
    handle = os.environ.get("OMNIS_HISTORY_PREREQUISITES")
    if not handle:
        pytest.skip("Owned offline installed prerequisites not selected")
    manifest = mapping(json.loads(Path(handle).read_bytes()))
    artifacts = [mapping(a) for a in sequence(manifest["artifacts"])]
    for artifact in artifacts:
        origin = subprocess.run(
            [
                str(artifact["python"]),
                "-I",
                "-B",
                "-c",
                HISTORICAL_ORIGIN,
                str(artifact["source"]),
                str(artifact["wheel"]),
            ],
            cwd=tmp_path,
            env={
                "HOME": str(tmp_path),
                "TMPDIR": str(tmp_path),
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": str(ROOT / "api/src"),
            },
            capture_output=True,
            timeout=15,
            check=False,
        )
        if origin.returncode != 0 or origin.stderr:
            raise AssertionError("SOURCE_INSTALLED_ORIGIN_ATTESTATION_FAILED")
        observed = mapping(json.loads(origin.stdout))
        assert observed["installed_bytes"] == "EXACT_WHEEL_AND_GIT_EXPORT"
        if artifact["tag"] == "old":
            assert mapping(observed["descriptor"])["code_digest"] == HISTORICAL_CHECKER
    python = Path(str(next(a for a in artifacts if a["tag"] == "current")["python"]))
    assert "INSTALLED" in RESTART_READER, "INSTALLED_ORIGIN_GUARD_MISSING"
    for guard in (
        None,
        "skill_catalog.evaluate_pure",
        "candidate_catalog.evaluate_pure",
        "pure_probe.evaluate_pure",
        "module_registry.run_handler",
        "BuildSource.build",
        "RuntimeClient._exchange",
    ):
        audit = tmp_path / (uuid4().hex + ".jsonl")
        audit.touch(mode=0o600)
        child = subprocess.run(
            [
                str(python),
                "-I",
                "-B",
                "-c",
                RESTART_READER,
                "INSTALLED",
                str(audit),
                "--history-control",
                *([] if guard is None else [guard]),
            ],
            cwd=tmp_path,
            env={"HOME": str(tmp_path), "TMPDIR": str(tmp_path), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            timeout=15,
            check=False,
        )
        assert child.returncode == 0, "SOURCE_INSTALLED_READER_CONTROL_FAILED"
        require_empty_stderr(child.stderr)
        events = [json.loads(line) for line in audit.read_text().splitlines()]
        assert events[0]["status"] == "ORIGIN"
        pid = events[0]["pid"]
        if guard is None:
            assert historical_reader_observations(events, pid, 0) == 0
        else:
            with pytest.raises(AssertionError, match="HISTORICAL_READER_OBSERVER_REFUSED"):
                historical_reader_observations(events, pid, 0)
            assert [r["name"] for r in events if r["status"] == "FORBIDDEN"] == [guard]


def historical_fault_value(fault: str, original: dict[str, object]) -> dict[str, object]:
    """Private boundary-input faults, never writes/reseals positive history."""
    from copy import deepcopy
    from hashlib import sha256
    from typing import cast

    def obj(value: object) -> dict[str, object]:
        if type(value) is not dict:
            raise ValueError("HISTORICAL_FAULT_INPUT_INVALID")
        return cast(dict[str, object], value)

    def rows(value: object) -> list[object]:
        if type(value) is not list:
            raise ValueError("HISTORICAL_FAULT_INPUT_INVALID")
        return cast(list[object], value)

    value = deepcopy(original)
    if fault == "foreign-pin":
        value["pin"] = "0" * 64
    elif fault == "foreign-checker":
        obj(value["payload"])["key"] = "foreign-issuer"
        value["digest"] = sha256(
            json.dumps(
                {k: v for k, v in value.items() if k != "digest"},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
    elif fault == "producer-provenance":
        # Input has already passed envelope validation at this consumer seam;
        # preserve its ref so the actual provenance comparison is reached.
        obj(obj(value["payload"])["provenance"])["producer_key"] = "foreign-producer"
    elif fault == "foreign-ref":
        value["digest"] = "0" * 64
    elif fault == "result-header":
        obj(obj(value["payload"])["header"])["attempt_id"] = "00000000-0000-0000-0000-000000000002"
        value["digest"] = sha256(
            json.dumps(
                {k: v for k, v in value.items() if k != "digest"},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
    elif fault == "foreign-child":
        obj(rows(value["executions"])[0])["native_child_id"] = "foreign-child"
    else:
        raise ValueError("HISTORICAL_FAULT_UNSUPPORTED")
    return value


HISTORICAL_FAULT_SETUP = r"""
if installed:
    native = importlib.import_module("omnis.supervisor.native_tasks")
    native.NativeTaskOwner.__init__ = deny("NativeTaskOwner.__init__")
    native.NativeTaskOwner.handle = deny("NativeTaskOwner.handle")
    fault = os.environ.get("OMNIS_HISTORY_FAULT")
    fault_entered = False
    def enter_fault():
        global fault_entered
        if not fault_entered:
            emit("FAULT", fault)
            fault_entered = True
    if fault in {"foreign-pin", "foreign-checker"}:
        identity = importlib.import_module("omnis.modules.tasks.method_checker_identity")
        actual_verify = identity.verify
        def verify(checker, **kwargs):
            enter_fault()
            if fault == "foreign-pin":
                kwargs = historical_fault_value(fault, kwargs)
            else:
                checker = historical_fault_value(fault, checker)
            return actual_verify(checker, **kwargs)
        identity.verify = verify
    elif fault == "producer-provenance":
        checks = importlib.import_module("omnis.modules.tasks.method_checks")
        actual_input = checks._input
        def input_check(original, *args):
            enter_fault()
            return actual_input(historical_fault_value(fault, original), *args)
        checks._input = input_check
    elif fault == "foreign-ref":
        catalog = importlib.import_module("omnis.modules.settings.candidate_store")
        actual_get = catalog.get
        async def get(conn, owner, reference):
            enter_fault()
            return await actual_get(conn, owner, historical_fault_value(fault, reference))
        catalog.get = get
    elif fault == "result-header":
        from copy import deepcopy
        checks = importlib.import_module("omnis.modules.tasks.method_checks")
        actual_receipts = checks._receipts
        def receipts(records, *args):
            enter_fault()
            changed = deepcopy(records)
            changed[0] = historical_fault_value(fault, changed[0])
            return actual_receipts(changed, *args)
        checks._receipts = receipts
    elif fault == "foreign-child":
        contract = importlib.import_module("omnis.modules.tasks.managed_contract")
        actual_final = contract.validate_final
        def final(value, *args):
            enter_fault()
            return actual_final(historical_fault_value(fault, value), *args)
        contract.validate_final = final
    elif fault is not None:
        raise ValueError("HISTORICAL_FAULT_UNSUPPORTED")
"""
# The exact same SOURCE-tested input transform executes inside the installed
# observer, with no source-path import. No product evaluator/native replacement.
RESTART_READER = RESTART_READER.replace(
    'emit("READY", "managed-cli")',
    'emit("READY", "managed-cli")\n'
    + inspect.getsource(historical_fault_value)
    + HISTORICAL_FAULT_SETUP,
)


def historical_cli_result(code: int, stdout: bytes, stderr: bytes) -> dict[str, object]:
    """Retain raw logs privately; expose only an exact public CLI tuple."""
    import re

    try:
        if code == 0 and not stderr:
            return mapping(json.loads(stdout))
        if code == 2 and not stdout:
            result = mapping(json.loads(stderr))
            if (
                set(result) == {"status", "reason"}
                and result["status"] == "BLOCKED"
                and type(result["reason"]) is str
                and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", result["reason"])
            ):
                return result
    except (ValueError, AssertionError):
        pass
    raise AssertionError("HISTORICAL_CLI_TUPLE_REFUSED") from None


@pytest.mark.parametrize(
    "fault",
    [
        "foreign-pin",
        "foreign-checker",
        "producer-provenance",
        "foreign-ref",
        "result-header",
        "foreign-child",
    ],
)
def test_historical_faults_change_only_private_negative_input(fault: str) -> None:
    assert callable(globals().get("historical_fault_value")), "HISTORICAL_FAULT_BOUNDARY_MISSING"
    original: dict[str, object] = {
        "payload": {
            "code_digest": HISTORICAL_CHECKER,
            "provenance": {"producer_key": "contract-case-records"},
            "header": {"attempt_id": "00000000-0000-0000-0000-000000000001"},
        },
        "digest": "1" * 64,
        "executions": [{"native_child_id": "original"}],
    }
    before = canonical(original)
    altered = historical_fault_value(fault, original)
    assert canonical(original) == before
    assert canonical(altered) != before
    with pytest.raises(ValueError, match="HISTORICAL_FAULT_UNSUPPORTED"):
        historical_fault_value("unknown", original)


def test_historical_cli_tuple_refusal_preserves_private_output() -> None:
    assert callable(globals().get("historical_cli_result")), "HISTORICAL_REFUSAL_BOUNDARY_MISSING"
    assert historical_cli_result(0, b'{"records":[]}', b"") == {"records": []}
    assert historical_cli_result(2, b"", b'{"status":"BLOCKED","reason":"REF_MISMATCH"}') == {
        "status": "BLOCKED",
        "reason": "REF_MISMATCH",
    }
    for code, out, err in (
        (0, b"{}", b"PRIVATE_SENTINEL"),
        (2, b"PRIVATE_SENTINEL", b"{}"),
        (99, b"", b""),
        (2, b"", b'{"status":"BLOCKED","reason":"PRIVATE_SENTINEL","extra":1}'),
    ):
        with pytest.raises(AssertionError, match="HISTORICAL_CLI_TUPLE_REFUSED") as denied:
            historical_cli_result(code, out, err)
        assert "PRIVATE_SENTINEL" not in str(denied.value)


def historical_installed_plan(handle: Path) -> list[dict[str, object]]:
    """No-effect prerequisite fence before fixture/native acquisition."""
    try:
        manifest = mapping(json.loads(handle.read_bytes()))
        root = Path(str(manifest["root"])).resolve(strict=True)
        if (
            not root.is_relative_to(Path("/home/kali/.hermes/cache/scratch"))
            or manifest["status"] != "READY_PREREQUISITES_ONLY"
        ):
            raise ValueError("Owned prerequisites required")
        artifacts = [mapping(a) for a in sequence(manifest["artifacts"])]
        if (
            [a["tag"] for a in artifacts] != ["old", "current"]
            or artifacts[0]["commit"] != HISTORICAL_COMMIT
            or artifacts[1]["commit"] != "2891a3ff93c1a04904f375b509e4536248c094a0"
        ):
            raise ValueError("Snapshot mismatch")
        for artifact in artifacts:
            for field in ("source", "wheel", "python"):
                path = Path(str(artifact[field])).absolute()
                if not path.is_relative_to(root) or not path.exists():
                    raise ValueError("Missing owned prerequisite")
            if sha(Path(str(artifact["wheel"])).read_bytes()) != artifact["wheel_sha256"]:
                raise ValueError("Changed wheel")
            source = Path(str(artifact["source"]))
            for entry in sequence(artifact["files"]):
                file = mapping(entry)
                path = (source / str(file["path"])).resolve(strict=True)
                if not path.is_relative_to(source) or sha(path.read_bytes()) != file["sha256"]:
                    raise ValueError("Changed source export")
        return artifacts
    except (ValueError, OSError, KeyError, AssertionError):
        raise AssertionError("HISTORICAL_PREREQUISITE_REFUSED") from None


HISTORICAL_ORIGIN = r"""
import importlib, json, sys, zipfile
from pathlib import Path
python_root = Path(sys.prefix).absolute()
source, wheel = map(Path, sys.argv[1:3])
from omnis.modules.tasks.method_checker_identity import descriptor
import omnis
package = Path(omnis.__file__).absolute().parent
if not package.is_relative_to(python_root) or any("/api/src" in p for p in sys.path):
    raise AssertionError("HISTORICAL_ORIGIN_REFUSED")
with zipfile.ZipFile(wheel) as distribution:
    for name in distribution.namelist():
        if name.startswith("omnis/") and not name.endswith("/"):
            actual = package.parent / name
            expected = source / "api/src" / name
            if actual.read_bytes() != distribution.read(name) or actual.read_bytes() != expected.read_bytes():
                raise AssertionError("HISTORICAL_INSTALLED_BYTES_REFUSED")
print(json.dumps({"descriptor": descriptor(), "package": str(package), "prefix": str(python_root), "installed_bytes": "EXACT_WHEEL_AND_GIT_EXPORT"}))
"""


@pytest.fixture
def historical_database_fence() -> Iterator[dict[str, bool]]:
    """Acquire before the dynamic DB fixture; restore only after its finalizer.

    An unresolved family retains the exact DB. The original outer run_gate
    remains responsible for eventual drain; this fixture never owns processes.
    """
    import conftest

    state = {"unsettled": False, "producer_family_drained": False}
    from sqlalchemy.engine import URL

    actual_verify = conftest.verify_test_database

    def verify(url: URL) -> conftest.FixtureReceipt:
        if state["unsettled"]:
            raise AssertionError("HISTORICAL_DATABASE_RETAINED_FAMILY_UNCERTAIN")
        return actual_verify(url)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(conftest, "verify_test_database", verify)
        yield state


def historical_run_gate(
    argv: list[str],
    environment: dict[str, str],
    log: Path,
    timeout: int,
    *,
    cwd: Path | None = None,
) -> int:
    """Reuse the existing authoritative owner, including its strict readback."""
    from importlib.util import module_from_spec, spec_from_file_location

    name = "_omnis_historical_existing_gate"
    if name not in sys.modules:
        spec = spec_from_file_location(name, ROOT / "ops/run_test_db_gate.py")
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    gate = cast(Callable[[list[str], dict[str, str], Path, int], int], sys.modules[name].run_gate)
    if cwd is not None:
        # Existing run_gate starts at ROOT. Preserve the caller's owned cwd by
        # exec, in the SAME supervised PID, not another owner or subprocess.
        argv = [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import os,sys; os.chdir(sys.argv[1]); os.execv(sys.argv[2],sys.argv[2:])",
            str(cwd),
            *argv,
        ]
    return gate(argv, environment, log, timeout)


def historical_producer_settlement(
    handoff: dict[str, object], proof: dict[str, object], family_drained: object
) -> None:
    """No exit0/SKIP/bool-as-counter can release the destructive fixture fence."""
    if (
        family_drained is not True
        or proof.get("native_cleanup") != "PASS"
        or type(proof.get("native_exit")) is not int
        or type(proof.get("native_owned_pids")) is not list
        or proof["native_owned_pids"] != []
        or proof.get("historical_handoff") != "AUTHENTIC_UNCONSUMED_FINAL_CHECK_STOPPED"
        or proof.get("status") != "PASS_SOURCE_NOT_INSTALLED"
        or any(
            type(proof.get(key)) is not int or proof[key] != expected
            for key, expected in (
                ("native_run_contract", 1),
                ("native_reads", 1),
                ("native_handlers", 2),
            )
        )
        or type(handoff.get("consumption_before_reader")) is not int
        or handoff["consumption_before_reader"] != 0
    ):
        raise AssertionError("HISTORICAL_PRODUCER_AUTHENTICITY_OR_DRAIN_REFUSED")


@pytest.mark.parametrize("mode", ["timeout", "signal", "unknown", "positive", "skip"])
def test_historical_actual_invoke_fences_actual_fixture_drop(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual invoke/fixture generator; fake SQL, held-live owned stdlib child."""
    import ast
    import ctypes
    import signal
    from types import SimpleNamespace

    import conftest

    events: list[str] = []
    from sqlalchemy.engine import URL

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def execute(self, query: object) -> None:
            events.append("DROP" if "DROP DATABASE" in str(query) else "CREATE")

    def original_verify(url: URL) -> conftest.FixtureReceipt:
        return conftest.FixtureReceipt(
            schema_version=1,
            project="synthetic",
            socket_directory="synthetic",
            system_identifier="1",
            container_id="0" * 64,
        )

    monkeypatch.setattr(conftest, "verify_test_database", original_verify)
    monkeypatch.setattr(conftest, "connect_test_database", lambda *args, **kwargs: Connection())
    monkeypatch.setenv("OMNIS_TEST_DATABASE_URL", "postgresql+psycopg://synthetic/omnis_test")
    guard = cast(
        Callable[[], Generator[dict[str, bool], None, None]],
        inspect.unwrap(historical_database_fence),
    )()
    fence = next(guard)
    fixture = cast(
        Callable[[], Generator[object, None, None]], inspect.unwrap(conftest.empty_database_url)
    )()
    next(fixture)
    libc = ctypes.CDLL(None, use_errno=True)
    prior = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(prior), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    release_read, release_write = os.pipe()
    pidfd: int | None = None
    child_pid: int | None = None
    ready = tmp_path / "held-child-ready"
    report: dict[str, object] = {"calls": [], "status": "IN_PROGRESS"}

    def checkpoint(**fields: object) -> None:
        report.update(fields)
        if fence["unsettled"]:
            report["status"] = "UNCERTAIN"

    journey = ast.parse(inspect.getsource(historical_installed_journey)).body[0]
    assert isinstance(journey, ast.FunctionDef)
    invoke = next(n for n in journey.body if isinstance(n, ast.FunctionDef) and n.name == "invoke")
    namespace: dict[str, object] = {
        "subprocess": subprocess,
        "time": time,
        "deadline": time.monotonic() + 20,
        "checkpoint": checkpoint,
        "fence": fence,
        "report": report,
        "sequence": sequence,
        "private": lambda path, raw: path.write_bytes(raw),
        "tmp_path": tmp_path,
        "historical_run_gate": historical_run_gate,
    }
    tree = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            invoke,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(tree), "<actual-invoke>", "exec"), namespace)
    call = cast(
        Callable[[str, list[str], Path, dict[str, str], int], subprocess.CompletedProcess[bytes]],
        namespace["invoke"],
    )
    # Held on a parent-owned pipe, not a naturally expiring short sleep. Detached
    # and TERM-resistant; only exact pidfd rescue is credited below.
    child_code = (
        "import os,signal,sys; from pathlib import Path; os.setsid(); "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); signal.alarm(30); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); os.read(int(sys.argv[2]),1)"
    )
    leader_code = (
        "import os,signal,subprocess,sys,time; from pathlib import Path; "
        "subprocess.Popen([sys.executable,'-I','-B','-c',sys.argv[1],sys.argv[2],sys.argv[3]],"
        "pass_fds=(int(sys.argv[3]),),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "p=Path(sys.argv[2]); "
        "\nwhile not p.exists(): time.sleep(.01)\n"
        + (
            "time.sleep(30)"
            if mode == "timeout"
            else "os.kill(os.getpid(),signal.SIGTERM)"
            if mode == "signal"
            else "raise SystemExit(99)"
        )
    )
    actual_run = subprocess.run

    def run(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        capture_output: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        # Only add owned pipe inheritance; real subprocess.run drives all exits.
        return actual_run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            timeout=timeout,
            check=check,
            pass_fds=(release_read,),
        )

    namespace["subprocess"] = SimpleNamespace(
        run=run,
        TimeoutExpired=subprocess.TimeoutExpired,
        CompletedProcess=subprocess.CompletedProcess,
    )
    try:
        if mode in {"positive", "skip"}:
            result = call(
                "old-producer",
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    "from pathlib import Path; assert Path.cwd() == Path("
                    + repr(str(tmp_path))
                    + ")",
                ],
                tmp_path,
                {"PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
                3,
            )
            assert result.returncode == 0 and fence["unsettled"]
            if mode == "positive":
                historical_producer_settlement(
                    {"consumption_before_reader": 0},
                    {
                        "native_cleanup": "PASS",
                        "native_owned_pids": [],
                        "native_exit": 0,
                        "native_run_contract": 1,
                        "native_reads": 1,
                        "native_handlers": 2,
                        "historical_handoff": "AUTHENTIC_UNCONSUMED_FINAL_CHECK_STOPPED",
                        "status": "PASS_SOURCE_NOT_INSTALLED",
                    },
                    fence["producer_family_drained"],
                )
                fence["unsettled"] = False
        else:
            try:
                call(
                    "other-child",
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        "-c",
                        leader_code,
                        child_code,
                        str(ready),
                        str(release_read),
                    ],
                    tmp_path,
                    {"PATH": "/usr/bin:/bin"},
                    1,
                )
            except AssertionError as error:
                assert str(error) == "HISTORICAL_CHILD_TIMEOUT_FAMILY_UNCERTAIN"
            child_pid = int(ready.read_text())
            pidfd = os.pidfd_open(child_pid)
            assert os.waitid(os.P_PIDFD, pidfd, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None
        if mode == "positive":
            fixture.close()
            assert events == ["CREATE", "DROP"]
        else:
            with pytest.raises(
                AssertionError, match="HISTORICAL_DATABASE_RETAINED_FAMILY_UNCERTAIN"
            ):
                fixture.close()
            assert events == ["CREATE"]
            assert report["status"] == "UNCERTAIN"
        assert conftest.verify_test_database is not original_verify
    finally:
        try:
            fixture.close()
        except AssertionError as error:
            assert str(error) == "HISTORICAL_DATABASE_RETAINED_FAMILY_UNCERTAIN"
        if pidfd is None and ready.exists():
            child_pid = int(ready.read_text())
            pidfd = os.pidfd_open(child_pid)
        if pidfd is not None:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            until = time.monotonic() + 3
            waited = None
            while waited is None and time.monotonic() < until:
                waited = os.waitid(os.P_PIDFD, pidfd, os.WEXITED | os.WNOHANG)
                if waited is None:
                    time.sleep(0.01)
            os.close(pidfd)
            assert waited is not None and waited.si_code == os.CLD_KILLED
            assert waited.si_status == signal.SIGKILL and waited.si_pid == child_pid
        os.close(release_read)
        os.close(release_write)
        assert libc.prctl(36, prior.value, 0, 0, 0) == 0
        guard.close()
    assert conftest.verify_test_database is original_verify


@pytest.mark.parametrize(
    "field",
    [
        "native_run_contract",
        "native_reads",
        "native_handlers",
        "native_exit",
        "consumption_before_reader",
        "family_drained",
        "missing",
    ],
)
def test_historical_producer_settlement_refuses_false_green_types(field: str) -> None:
    proof: dict[str, object] = {
        "native_cleanup": "PASS",
        "native_owned_pids": [],
        "native_exit": 0,
        "native_run_contract": 1,
        "native_reads": 1,
        "native_handlers": 2,
        "historical_handoff": "AUTHENTIC_UNCONSUMED_FINAL_CHECK_STOPPED",
        "status": "PASS_SOURCE_NOT_INSTALLED",
    }
    handoff: dict[str, object] = {"consumption_before_reader": 0}
    historical_producer_settlement(handoff, proof, True)
    drained: object = True
    if field == "consumption_before_reader":
        handoff[field] = False
    elif field == "family_drained":
        drained = 1
    elif field == "missing":
        proof = {}
    else:
        proof[field] = True
    with pytest.raises(AssertionError, match="HISTORICAL_PRODUCER_AUTHENTICITY_OR_DRAIN_REFUSED"):
        historical_producer_settlement(handoff, proof, drained)


@pytest.mark.parametrize("settled", [True, False])
def test_historical_dynamic_fixture_teardown_order_is_real_pytest(
    tmp_path: Path, settled: bool
) -> None:
    """Actual pytest LIFO teardown, fake SQL; guard must outlive the DB fixture."""
    test = tmp_path / "test_order.py"
    test.write_text(
        "import sys,pytest,json; from pathlib import Path\n"
        + "settled="
        + repr(settled)
        + "\n"
        + "sys.path[:0] = "
        + repr([str(ROOT / "api/src"), str(ROOT / "api/tests")])
        + "\n"
        + "import conftest as original\n"
        "from test_contract_method_pg import historical_database_fence\n"
        "empty_database_url = original.empty_database_url\n"
        "events=[]\n"
        "class Connection:\n"
        " def __enter__(self): return self\n"
        " def __exit__(self,*args): pass\n"
        " def execute(self,q): events.append('DROP' if 'DROP DATABASE' in str(q) else 'CREATE')\n"
        "@pytest.fixture\n"
        "def seams(monkeypatch,request):\n"
        " def verify(url): events.append('VERIFY')\n"
        " monkeypatch.setattr(original,'verify_test_database',verify)\n"
        " monkeypatch.setattr(original,'connect_test_database',lambda *a,**k:Connection())\n"
        " monkeypatch.setenv('OMNIS_TEST_DATABASE_URL','postgresql+psycopg://synthetic/omnis_test')\n"
        " yield\n"
        " assert original.verify_test_database is verify\n"
        " assert (events[-2:]==['VERIFY','DROP']) if settled else events[-1:] == ['CREATE']\n"
        " Path('order-observed.json').write_text(json.dumps({'events':events,'restored':True}))\n"
        "def test_order(request,seams):\n"
        " state=request.getfixturevalue('historical_database_fence')\n"
        " request.getfixturevalue('empty_database_url')\n"
        " state['unsettled'] = not settled\n"
    )
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "pytest",
            str(test),
            "-q",
            "-p",
            "no:cacheprovider",
            "--tb=line",
            "--basetemp",
            str(tmp_path / "order-pytest"),
        ],
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "TMPDIR": str(tmp_path),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        capture_output=True,
        timeout=15,
        check=False,
    )
    if child.returncode != (0 if settled else 1):
        raise AssertionError("HISTORICAL_ACTUAL_PYTEST_TEARDOWN_ORDER_FAILED")
    assert b"1 passed" in child.stdout
    observed = mapping(json.loads((tmp_path / "order-observed.json").read_bytes()))
    assert observed["restored"] is True
    assert ("DROP" in sequence(observed["events"])) is settled
    if not settled:
        assert b"HISTORICAL_DATABASE_RETAINED_FAMILY_UNCERTAIN" in child.stdout


@pytest.mark.parametrize("mode", ["timeout", "signal", "unknown"])
def test_historical_existing_run_gate_drains_held_resistant_family(
    mode: str, tmp_path: Path
) -> None:
    """The reused owner, not this test, must kill/reap a held detached child."""
    import signal
    import threading

    ready, admitted, release = (tmp_path / name for name in ("ready", "admitted", "release"))
    pinned: list[int] = []
    failures: list[str] = []

    def observer() -> None:
        until = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < until:
            time.sleep(0.01)
        if not ready.exists():
            failures.append("NO_CHILD")
            return
        pinned.append(os.pidfd_open(int(ready.read_text())))
        admitted.touch()

    held = (
        "import os,signal,sys,time; from pathlib import Path; os.setsid(); "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); signal.alarm(30); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); p=Path(sys.argv[2]); "
        "\nwhile not p.exists(): time.sleep(.01)"
    )
    leader = (
        "import os,signal,subprocess,sys,time; from pathlib import Path; "
        "subprocess.Popen([sys.executable,'-I','-B','-c',sys.argv[1],sys.argv[2],sys.argv[3]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "p=Path(sys.argv[4]); \nwhile not p.exists(): time.sleep(.01)\n"
        + (
            "time.sleep(30)"
            if mode == "timeout"
            else "os.kill(os.getpid(),signal.SIGTERM)"
            if mode == "signal"
            else "raise SystemExit(99)"
        )
    )
    thread = threading.Thread(target=observer)
    thread.start()
    try:
        code = historical_run_gate(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                leader,
                held,
                str(ready),
                str(release),
                str(admitted),
            ],
            {"PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
            tmp_path / "family.log",
            2,
        )
        thread.join(timeout=6)
        assert not thread.is_alive() and not failures and len(pinned) == 1
        import select

        poll = select.poll()
        poll.register(pinned[0], select.POLLIN)
        assert poll.poll(1000)  # Exited, not a natural held-child completion.
        receipt = mapping(json.loads((tmp_path / "family.log.result.json").read_bytes()))
        assert receipt == {"schema_version": 1, "code": code, "family_drained": True}
        assert code == (124 if mode == "timeout" else 2)
        assert not release.exists()
    finally:
        release.touch()
        thread.join(timeout=6)
        for fd in pinned:
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(fd)


def historical_installed_journey(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    """H01/H02 only; existing runner owns the DB and entire producer family.

    Explicit parent review precedes all PG/native effects. No installation,
    network fallback, Host restart, schema fabrication, or source reader here.
    Faults are private in-process consumer-input seams, NOT corrupt durable DBs.
    Their public reasons are measured before same-channel reconcile comparison.
    """
    if os.environ.get("OMNIS_HISTORY_REVIEWED") != sha(Path(__file__).read_bytes()):
        raise AssertionError("HISTORICAL_EXACT_REVIEW_REQUIRED")
    handle = os.environ.get("OMNIS_HISTORY_PREREQUISITES")
    if not handle:
        raise AssertionError("HISTORICAL_PREREQUISITES_REQUIRED")
    old, current = historical_installed_plan(Path(handle))
    # Dynamic fixture finalizers are LIFO: this guard outlives empty_database_url.
    fence = mapping(request.getfixturevalue("historical_database_fence"))
    from psycopg import sql as pgsql

    from conftest import connect_test_database, verify_test_database

    deadline = time.monotonic() + 240
    report: dict[str, object] = {
        "status": "IN_PROGRESS",
        "scenario": "H01_H02_INSTALLED_HISTORY",
        "old_commit": HISTORICAL_COMMIT,
        "calls": [],
        "denials": [],
    }
    report_path = tmp_path / "installed-history-report.json"

    def private(path: Path, raw: bytes) -> None:
        path.write_bytes(raw)
        path.chmod(0o600)

    def checkpoint(**fields: object) -> None:
        report.update(fields)
        if fence["unsettled"]:
            report["status"] = "UNCERTAIN"
        private(report_path, canonical(report))

    def invoke(
        label: str, argv: list[str], cwd: Path, environment: dict[str, str], timeout: int = 15
    ) -> subprocess.CompletedProcess[bytes]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("HISTORICAL_BUDGET_EXHAUSTED")
        try:
            if label == "old-producer":
                fence["unsettled"] = True
                checkpoint(uncertain_phase=label)
                code = historical_run_gate(
                    argv,
                    environment,
                    tmp_path / "old-producer.gate.log",
                    int(min(timeout, remaining)),
                    cwd=cwd,
                )
                fence["producer_family_drained"] = True
                child = subprocess.CompletedProcess(argv, code, b"", b"")
            else:
                child = subprocess.run(
                    argv,
                    cwd=cwd,
                    env=environment,
                    capture_output=True,
                    timeout=min(timeout, remaining),
                    check=False,
                )
        except subprocess.TimeoutExpired:
            fence["unsettled"] = True
            checkpoint(status="UNCERTAIN", uncertain_phase=label)
            raise AssertionError("HISTORICAL_CHILD_TIMEOUT_FAMILY_UNCERTAIN") from None
        except BaseException:
            fence["unsettled"] = True
            checkpoint(status="UNCERTAIN", uncertain_phase=label)
            raise
        if child.returncode not in (0, 2):
            fence["unsettled"] = True
            checkpoint(status="UNCERTAIN", uncertain_phase=label)
        private(tmp_path / (label + ".stdout"), child.stdout)
        private(tmp_path / (label + ".stderr"), child.stderr)
        checkpoint(calls=[*sequence(report["calls"]), {"label": label, "exit": child.returncode}])
        return child

    homes = {tag: tmp_path / (tag + "-home") for tag in ("old", "current")}
    for home in homes.values():
        home.mkdir(mode=0o700)
    clean = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    # Attest exact wheel members/import paths before even acquiring the fixture.
    for artifact in (old, current):
        tag = str(artifact["tag"])
        child = invoke(
            tag + "-origin",
            [
                str(artifact["python"]),
                "-I",
                "-B",
                "-c",
                HISTORICAL_ORIGIN,
                str(artifact["source"]),
                str(artifact["wheel"]),
            ],
            homes[tag],
            {**clean, "HOME": str(homes[tag]), "TMPDIR": str(homes[tag])},
        )
        if child.returncode != 0 or child.stderr:
            raise AssertionError("HISTORICAL_INSTALLED_ORIGIN_FAILED") from None
        origin = mapping(json.loads(child.stdout))
        checkpoint(**{tag + "_origin": origin})
        if tag == "old" and mapping(origin["descriptor"])["code_digest"] != HISTORICAL_CHECKER:
            raise AssertionError("HISTORICAL_INSTALLED_CHECKER_MISMATCH")
    url = request.getfixturevalue("empty_database_url")
    dsn = url.render_as_string(hide_password=False)
    receipt = verify_test_database(url.set(database="omnis_test"))
    environments = {
        tag: {**clean, "HOME": str(home), "TMPDIR": str(home), "OMNIS_DATABASE_URL": dsn}
        for tag, home in homes.items()
    }

    def snapshot() -> dict[str, object]:
        with connect_test_database(url) as conn:
            names = [
                str(row[0])
                for row in conn.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                ).fetchall()
            ]
            result: dict[str, object] = {}
            for name in names:
                query = pgsql.SQL(
                    "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM public.{} t"
                ).format(pgsql.Identifier(name))
                row = conn.execute(query).fetchone()
                if row is None:
                    raise AssertionError("HISTORICAL_CENSUS_UNAVAILABLE")
                result[name] = row[0]
            return result

    if snapshot():
        raise AssertionError("HISTORICAL_INITIALIZE_REQUIRES_EMPTY_DATABASE")
    initialized = invoke(
        "old-initialize",
        historical_migration_argv(Path(str(old["python"])), initialize=True),
        homes["old"],
        {**environments["old"], "OMNIS_EXPECTED_SYSTEM_ID": receipt.system_identifier},
        30,
    )
    if initialized.returncode != 0:
        raise AssertionError("HISTORICAL_OLD_INITIALIZE_FAILED")
    if snapshot()["alembic_version"] != [{"version_num": "0012_contract_methods"}]:
        raise AssertionError("HISTORICAL_SCHEMA_0012_REQUIRED")
    old_source = Path(str(old["source"]))
    adapted = old_source / "api/tests/test_historical_installed_producer.py"
    private(
        adapted,
        historical_producer_source(
            (old_source / "api/tests/test_contract_method_pg.py").read_bytes()
        ).encode(),
    )
    producer_dir = tmp_path / "producer"
    # Old installed domain imports + old exported test harness ONLY.
    producer_env = {
        **environments["old"],
        "TMPDIR": os.environ["TMPDIR"],
        "OMNIS_CONTRACT_METHOD_QA": "1",
        "OMNIS_CONTRACT_METHOD_NATIVE_PG": "1",
        "OMNIS_HISTORY_DATABASE_URL": dsn,
        "OMNIS_B06B_INSTALLED": "1",
        "OMNIS_B06B_PYTHON": str(old["python"]),
    }
    producer = invoke(
        "old-producer",
        [
            str(old["python"]),
            "-I",
            "-B",
            "-m",
            "pytest",
            "-o",
            "pythonpath=",
            "--basetemp",
            str(producer_dir),
            str(adapted)
            + "::test_contract_method_real_native_pg_owner_receipts_check_inbox[partial-requirement-full]",
            "-q",
            "--tb=line",
        ],
        homes["old"],
        producer_env,
        120,
    )
    if producer.returncode != 0:
        raise AssertionError("HISTORICAL_AUTHENTIC_PRODUCER_FAILED") from None
    handoffs = list(producer_dir.rglob("historical-handoff.json"))
    if len(handoffs) != 1:
        raise AssertionError("HISTORICAL_POSITIVE_HANDOFF_MISSING")
    handoff = mapping(json.loads(handoffs[0].read_bytes()))
    producer_proof = mapping(json.loads(Path(str(handoff["producer_proof"])).read_bytes()))
    historical_producer_settlement(handoff, producer_proof, fence["producer_family_drained"])
    fence["unsettled"] = False
    checkpoint(status="IN_PROGRESS", producer_settlement="EXISTING_RUN_GATE_AND_AUTHENTIC_PROOF")
    before = snapshot()
    private(tmp_path / "positive-before-upgrade.json", canonical(before))
    observation = Path(str(handoff["native_observation"]))
    observed_before = observation.read_bytes()
    verify_test_database(url.set(database="omnis_test"))
    upgraded = invoke(
        "current-upgrade",
        historical_migration_argv(Path(str(current["python"])), initialize=False),
        homes["current"],
        environments["current"],
        30,
    )
    if upgraded.returncode != 0:
        raise AssertionError("HISTORICAL_CURRENT_UPGRADE_FAILED")
    after = snapshot()
    if (
        after.get("alembic_version") != [{"version_num": "0013_mission_revisions"}]
        or after.get("managed_mission_revision") != []
        or any(
            canonical(after[name]) != canonical(rows)
            for name, rows in before.items()
            if name != "alembic_version"
        )
    ):
        raise AssertionError("HISTORICAL_UPGRADE_CHANGED_IMMUTABLE_HISTORY")
    private(tmp_path / "positive-after-upgrade.json", canonical(after))
    back_request = mapping(handoff["request"])
    expected = mapping(handoff["readback"])
    catalog_root = Path(str(handoff["catalog_root"]))
    retained_material = {
        str(p.relative_to(catalog_root)): sha(p.read_bytes())
        for p in catalog_root.rglob("*")
        if p.is_file()
    }
    request_path = tmp_path / "installed-reader-request.json"
    private(request_path, canonical(back_request))

    def restarted_cli(operation: str, *, fault: str | None = None) -> dict[str, object]:
        label = "reader-" + str(len(sequence(report["calls"])))
        audit = tmp_path / (label + ".jsonl")
        audit.touch(mode=0o600)
        child = invoke(
            label,
            [
                str(current["python"]),
                "-I",
                "-B",
                "-c",
                RESTART_READER,
                "INSTALLED",
                str(audit),
                operation,
                "--request",
                str(request_path),
                "--catalog-root",
                str(catalog_root),
            ],
            homes["current"],
            {**environments["current"], **({"OMNIS_HISTORY_FAULT": fault} if fault else {})},
        )
        events = [json.loads(line) for line in audit.read_text().splitlines()]
        if not events:
            raise AssertionError("HISTORICAL_READER_OBSERVER_REFUSED")
        pid = mapping(events[0])["pid"]
        if type(pid) is not int:
            raise AssertionError("HISTORICAL_READER_OBSERVER_REFUSED")
        attempts = historical_reader_observations(events, pid, child.returncode, fault=fault)
        result = historical_cli_result(child.returncode, child.stdout, child.stderr)
        checkpoint(
            reader_observations=[
                *sequence(report.get("reader_observations", [])),
                {
                    "operation": operation,
                    "fault": fault,
                    "execution_attempts": attempts,
                    "exit": child.returncode,
                },
            ]
        )
        if fault is not None and (
            child.returncode != 2
            or result.get("reason")
            in {"DATABASE_UNAVAILABLE", "INVALID_REQUEST", "INVALID_ARGUMENTS"}
        ):
            raise AssertionError("HISTORICAL_FAULT_DID_NOT_REACH_PUBLIC_DOMAIN_DENIAL")
        return result

    if canonical(restarted_cli("readback")) != canonical(expected) or canonical(
        snapshot()
    ) != canonical(after):
        raise AssertionError("HISTORICAL_INSTALLED_READBACK_CHANGED_HISTORY")
    reconciled = restarted_cli("reconcile")
    expected_consumed = deepcopy(expected)
    for inbox in sequence(expected_consumed["inbox"]):
        mapping(inbox)["domain_result_consumed"] = True
    consumed_census = deepcopy(after)
    for inbox in sequence(consumed_census["managed_inbox"]):
        mapping(inbox)["domain_result_consumed"] = True
    if canonical(reconciled) != canonical(expected_consumed) or canonical(snapshot()) != canonical(
        consumed_census
    ):
        raise AssertionError("HISTORICAL_SINGLE_CONSUMPTION_CHANGED_IMMUTABLE_ROWS")
    if (
        sum(mapping(i)["domain_result_consumed"] is True for i in sequence(reconciled["inbox"]))
        != 1
    ):
        raise AssertionError("HISTORICAL_EXACT_ONE_CONSUMPTION_REQUIRED")
    for operation in ("reconcile", "readback"):
        if canonical(restarted_cli(operation)) != canonical(reconciled) or canonical(
            snapshot()
        ) != canonical(consumed_census):
            raise AssertionError("HISTORICAL_EXACT_REPLAY_CHANGED_HISTORY")
    for fault in (
        "foreign-pin",
        "foreign-checker",
        "producer-provenance",
        "foreign-ref",
        "result-header",
        "foreign-child",
    ):
        measured = restarted_cli("readback", fault=fault)
        # Preserve measured public reason BEFORE using it as a replay oracle.
        checkpoint(
            denials=[
                *sequence(report["denials"]),
                {
                    "fault": fault,
                    "public_tuple": {"exit": 2, **measured},
                    "scope": "CONTROLLED_CONSUMER_INPUT_NOT_DURABLE_MUTATION",
                },
            ]
        )
        if canonical(restarted_cli("reconcile", fault=fault)) != canonical(measured) or canonical(
            snapshot()
        ) != canonical(consumed_census):
            raise AssertionError("HISTORICAL_SAME_CHANNEL_DENIAL_OR_CENSUS_CHANGED")
        if canonical(restarted_cli("readback")) != canonical(reconciled):
            raise AssertionError("HISTORICAL_POSITIVE_CONTROL_REFUSED_AFTER_FAULT")
    if (
        observation.read_bytes() != observed_before
        or {
            str(p.relative_to(catalog_root)): sha(p.read_bytes())
            for p in catalog_root.rglob("*")
            if p.is_file()
        }
        != retained_material
        or canonical(snapshot()) != canonical(consumed_census)
    ):
        raise AssertionError("HISTORICAL_READER_CHANGED_NATIVE_MATERIAL_OR_ROWS")
    private(tmp_path / "positive-current-readback.json", canonical(reconciled))
    checkpoint(
        status="PASS_INSTALLED_DOMAIN_HISTORY_SCOPED",
        old_schema="0012_contract_methods",
        current_schema="0013_mission_revisions",
        handoff=str(handoffs[0]),
        retained_refs="EXACT_ORIGINAL",
        consumed=1,
        native_observation="UNCHANGED",
        material="UNCHANGED",
        limits=[
            "SOURCE_HOST_NOT_OCI_INSTALLED",
            "NO_HOST_RESTART_H03",
            "FAULTS_OBSERVER_INPUT_ONLY",
            "DENIAL_REASON_SEMANTICS_REQUIRE_PARENT_ADJUDICATION",
            "DB_AND_FAMILY_CLEANUP_OWNED_BY_EXISTING_RUNNER",
        ],
    )


def test_historical_installed_plan_refuses_changed_wheel_before_effects(tmp_path: Path) -> None:
    assert callable(globals().get("historical_installed_plan")), "HISTORICAL_PLAN_MISSING"
    handle = os.environ.get("OMNIS_HISTORY_PREREQUISITES")
    if not handle:
        pytest.skip("Owned offline prerequisites not selected")
    plan = historical_installed_plan(Path(handle))
    assert [p["tag"] for p in plan] == ["old", "current"]
    assert plan[0]["commit"] == HISTORICAL_COMMIT
    bad = mapping(json.loads(Path(handle).read_bytes()))
    mapping(sequence(bad["artifacts"])[0])["wheel_sha256"] = "0" * 64
    bad_path = tmp_path / "changed-prerequisites.json"
    bad_path.write_bytes(canonical(bad))
    with pytest.raises(AssertionError, match="HISTORICAL_PREREQUISITE_REFUSED"):
        historical_installed_plan(bad_path)


def test_historical_review_gate_precedes_database_fixture(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert callable(globals().get("historical_installed_journey")), "HISTORICAL_JOURNEY_MISSING"
    monkeypatch.delenv("OMNIS_HISTORY_REVIEWED", raising=False)

    def forbidden_fixture(name: str) -> object:
        raise AssertionError("DATABASE_ACQUIRED_BEFORE_REVIEW")

    monkeypatch.setattr(request, "getfixturevalue", forbidden_fixture)
    with pytest.raises(AssertionError, match="HISTORICAL_EXACT_REVIEW_REQUIRED"):
        test_contract_method_real_native_pg_owner_receipts_check_inbox(
            request,
            tmp_path,
            monkeypatch,
            False,
            True,
            False,
            False,
            False,
            "historical-installed",
        )


def require_empty_stderr(stderr: bytes) -> None:
    """Refuse contradictory diagnostics without pytest rendering private bytes."""
    if stderr:
        raise AssertionError("RESTART_CLI_CONTRADICTORY_DIAGNOSTIC") from None


BOOTSTRAP_PHASES = (
    "BOOTSTRAP_RUNPY_ENTRY_BEGIN",
    "ENTRY_MODULE_BEGIN",
    "ENTRY_SERVER_IMPORT_BEGIN",
    "SERVER_CONVERSATION_IMPORT_BEGIN",
    "CONVERSATION_MODULE_BEGIN",
    "CONVERSATION_TURN_API_IMPORT_BEGIN",
    "SERVER_SPLIT_HANDLERS_IMPORT_BEGIN",
    "MANAGED_RPC_DISPATCH_MODULE_BEGIN",
    "ENTRY_MAIN_BEGIN",
    "ENTRY_READY_WRITE_BEGIN",
)
OBSERVATION_BYTES = 65536
OBSERVATION_EVENTS = 256


def launch_observation_counter(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 10**12 else None


def launch_observation_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate observation field")
    return result


def launch_bootstrap_diagnostic(raw: bytes) -> dict[str, object]:
    """Inspect the original bounded channel before projecting public fields.

    Missing/invalid rows are not zero attempts or proof of a root cause. Keep
    valid prefixes and their last ENTER; unknown fields are flagged, not copied.
    Cumulative clocks include observer overhead and nested audit calls may overlap.
    """
    issues: set[str] = set()
    entered: list[str] = []
    completed: list[str] = []
    phase_events = 0
    last_enter: str | None = None
    elapsed_ms: int | None = None
    audit_ms: int | None = None
    audit_calls: int | None = None
    observer_ready: bool | None = None
    if len(raw) > OBSERVATION_BYTES:
        issues.add("BYTE_LIMIT")
    lines = raw[:OBSERVATION_BYTES].splitlines()
    if len(lines) > OBSERVATION_EVENTS:
        issues.add("EVENT_LIMIT")
        lines = lines[:OBSERVATION_EVENTS]
    if not raw:
        issues.add("NO_DATA")
    elif not raw.endswith(b"\n"):
        issues.add("INCOMPLETE_RECORD")
    base_fields = {"test", "status", "count"}
    phase_fields = base_fields | {"edge", "elapsed_ms", "audit_ms", "audit_calls"}
    # Legacy records stay on the same channel. Only finite public categories are
    # recognized; arbitrary exception/frame/caller names never enter this report.
    public_statuses = {
        "observer": {"READY", "EXIT"},
        "bootstrap-exit": {"NORMAL_SYSTEM_EXIT"},
        "bootstrap-import": {"ELAPSED_MS"},
        "bootstrap-audit": {"ELAPSED_MS", "CALLS"},
        "validate_stage": {"ENTERED", "RETURNED_MS"},
        "stage": {"ENTERED", "RETURNED_MS"},
        "initialize_contract": {"ENTERED", "RETURNED_MS"},
        "run_contract": {"REAL_AIAgent", "WRONG_TYPE"},
        "bound-predicates": {"SATISFIED", "GAP"},
        "_read_bound_input": {"ENTERED"},
        "run_handler": {"ENTERED"},
        "contract-guard": {"APPROVED", "REFUSED"},
        "native-release": {"SUCCEEDED", "INCONCLUSIVE"},
        "task-result": {"NATIVE"},
        "contract-tool-receipt": {"NATIVE"},
        "contract-artifact": {"NATIVE"},
    }
    for line in lines:
        if len(line) + 1 > 4096:
            issues.add("RECORD_LIMIT")
            continue
        try:
            value: object = json.loads(line, object_pairs_hook=launch_observation_object)
        except (ValueError, UnicodeError, RecursionError):
            issues.add("INVALID_RECORD")
            continue
        if type(value) is not dict:
            issues.add("INVALID_RECORD")
            continue
        row = mapping(value)
        test, status = row.get("test"), row.get("status")
        expected = phase_fields if test == "bootstrap-phase" else base_fields
        if set(row) != expected:
            issues.add("UNKNOWN_OR_MISSING_FIELDS")
            continue
        count = launch_observation_counter(row["count"])
        if type(test) is not str or type(status) is not str or count is None:
            issues.add("INVALID_RECORD")
            continue
        if test != "bootstrap-phase":
            if status not in public_statuses.get(test, set()):
                issues.add("UNKNOWN_EVENT")
            elif test == "observer" and status == "READY" and count == 1:
                observer_ready = True
            continue
        edge = row["edge"]
        if (
            status not in BOOTSTRAP_PHASES
            or type(edge) is not str
            or edge not in {"ENTER", "END"}
            or count != 1
        ):
            issues.add("UNKNOWN_OR_INVALID_PHASE")
            continue
        elapsed = launch_observation_counter(row["elapsed_ms"])
        audit_time = launch_observation_counter(row["audit_ms"])
        calls = launch_observation_counter(row["audit_calls"])
        if elapsed is None or audit_time is None or calls is None:
            issues.add("INVALID_COUNTER")
            continue
        if (
            (elapsed_ms is not None and elapsed < elapsed_ms)
            or (audit_ms is not None and audit_time < audit_ms)
            or (audit_calls is not None and calls < audit_calls)
        ):
            issues.add("COUNTER_REGRESSION")
            continue
        if (edge == "ENTER" and status in entered) or (
            edge == "END" and (status not in entered or status in completed)
        ):
            issues.add("INVALID_PHASE_ORDER")
            continue
        phase_events += 1
        elapsed_ms, audit_ms, audit_calls = elapsed, audit_time, calls
        if edge == "ENTER":
            entered.append(status)
            last_enter = status
        else:
            completed.append(status)
    if observer_ready is not True:
        issues.add("OBSERVER_UNCONFIRMED")
    if set(completed) != set(BOOTSTRAP_PHASES):
        issues.add("MISSING_PHASE_COMPLETION")
    # These three frames span the RPC reader loop and may unwind under Stop.
    # Their missing END remains INCOMPLETE; every import and READY write must end.
    long_lived = {"BOOTSTRAP_RUNPY_ENTRY_BEGIN", "ENTRY_MODULE_BEGIN", "ENTRY_MAIN_BEGIN"}
    return {
        "status": "INCOMPLETE" if issues else "OBSERVED",
        "pre_ready_complete": set(entered) == set(BOOTSTRAP_PHASES)
        and set(BOOTSTRAP_PHASES) - long_lived <= set(completed),
        "root_cause": "UNKNOWN",
        "observer_ready": observer_ready,
        "last_enter": last_enter,
        "completed": completed,
        "pending": [label for label in entered if label not in completed],
        "elapsed_ms": elapsed_ms,
        "audit_ms": audit_ms,
        "audit_calls": audit_calls,
        "phase_events": phase_events if entered else None,
        "issues": sorted(issues),
    }


def launch_bootstrap_checkpoint(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as stream:
            return launch_bootstrap_diagnostic(stream.read(OBSERVATION_BYTES + 1))
    except OSError:
        result = launch_bootstrap_diagnostic(b"")
        result["issues"] = ["OBSERVER_UNAVAILABLE"]
        return result


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


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "missing-end",
        "unknown-field",
        "unknown-label",
        "unknown-event",
        "boolean",
        "count-boolean",
        "float",
        "missing-counter",
        "missing-ready",
        "regression",
        "negative",
        "overbound",
        "wrong-edge",
        "duplicate",
        "duplicate-field",
        "truncated",
        "no-data",
        "event-limit",
        "record-limit",
        "byte-limit",
    ],
)
def test_launch_failure_diagnostic_bootstrap_evidence_is_bounded_and_incomplete(
    tmp_path: Path, mutation: str
) -> None:
    decoder = globals().get("launch_bootstrap_diagnostic")
    assert callable(decoder), "PRE_MAIN_FAILURE_DECODER_MISSING"
    labels = (
        "BOOTSTRAP_RUNPY_ENTRY_BEGIN",
        "ENTRY_MODULE_BEGIN",
        "ENTRY_SERVER_IMPORT_BEGIN",
        "SERVER_CONVERSATION_IMPORT_BEGIN",
        "CONVERSATION_MODULE_BEGIN",
        "CONVERSATION_TURN_API_IMPORT_BEGIN",
        "SERVER_SPLIT_HANDLERS_IMPORT_BEGIN",
        "MANAGED_RPC_DISPATCH_MODULE_BEGIN",
        "ENTRY_MAIN_BEGIN",
        "ENTRY_READY_WRITE_BEGIN",
    )
    rows: list[dict[str, object]] = [{"test": "observer", "status": "READY", "count": 1}]
    for label in labels:
        for edge in ("ENTER", "END"):
            rows.append(
                {
                    "test": "bootstrap-phase",
                    "status": label,
                    "count": 1,
                    "edge": edge,
                    "elapsed_ms": 7,
                    "audit_ms": 2,
                    "audit_calls": 11,
                }
            )
    if mutation == "missing-end":
        rows.pop()
    elif mutation == "unknown-field":
        rows[-1]["private"] = "PRIVATE_SOURCE_SENTINEL"
    elif mutation == "unknown-label":
        rows[-1]["status"] = "PRIVATE_SOURCE_SENTINEL"
    elif mutation == "unknown-event":
        rows.append({"test": "PRIVATE_SOURCE_SENTINEL", "status": "READY", "count": 1})
    elif mutation == "count-boolean":
        rows[-1]["count"] = True
    elif mutation == "float":
        rows[-1]["elapsed_ms"] = 7.0
    elif mutation == "missing-counter":
        del rows[-1]["elapsed_ms"]
    elif mutation == "missing-ready":
        rows.pop(0)
    elif mutation == "regression":
        rows[-1]["elapsed_ms"] = 6
    elif mutation in {"boolean", "negative", "overbound"}:
        rows[-1]["audit_calls"] = {"boolean": True, "negative": -1, "overbound": 10**12 + 1}[
            mutation
        ]
    elif mutation == "wrong-edge":
        rows[-1]["edge"] = "RETURNED_PRIVATE_SOURCE_SENTINEL"
    elif mutation == "duplicate":
        rows.append(rows[-1])
    elif mutation == "event-limit":
        rows.extend([rows[0]] * 256)
    raw = b"".join(canonical(r) + b"\n" for r in rows)
    if mutation == "truncated":
        raw += b'{"private":"PRIVATE_SOURCE_SENTINEL"'
    elif mutation == "no-data":
        raw = b""
    elif mutation == "duplicate-field":
        raw += b'{"test":"PRIVATE_SOURCE_SENTINEL","test":"observer","status":"READY","count":1}\n'
    elif mutation == "record-limit":
        raw += (
            canonical({"test": "PRIVATE_SOURCE_SENTINEL" * 256, "status": "READY", "count": 1})
            + b"\n"
        )
    elif mutation == "byte-limit":
        raw += b" " * 65537
    evidence = tmp_path / "decoder-evidence.jsonl"
    evidence.write_bytes(raw)
    evidence.chmod(0o600)
    decoded = mapping(decoder(evidence.read_bytes()))
    assert launch_bootstrap_checkpoint(evidence) == decoded
    assert b"PRIVATE_SOURCE_SENTINEL" not in canonical(decoded), "PRIVATE_FAILURE_DATA_LEAK"
    assert decoded["root_cause"] == "UNKNOWN"
    assert decoded["status"] == ("OBSERVED" if mutation == "none" else "INCOMPLETE")
    if mutation == "none":
        assert decoded["completed"] == list(labels)
        assert decoded["last_enter"] == labels[-1]
        assert decoded["pending"] == []
        assert decoded["elapsed_ms"] == 7 and decoded["audit_ms"] == 2
        assert decoded["audit_calls"] == 11 and decoded["phase_events"] == 20
    elif mutation != "no-data":
        assert decoded["last_enter"] == labels[-1]
    if mutation != "none":
        assert decoded["issues"]


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
    [
        "unrelated",
        "observed",
        "forbidden",
        "foreign",
        "sibling",
        "threaded",
        "threaded-denied",
        "repeated-denied",
        "returned",
    ],
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
        "sibling": "init_agent", "repeated-denied": "init_agent",
        "threaded": "run_handler", "threaded-denied": "init_agent",
        "returned": "_contract_guard"}[scenario]
filename = "/foreign/control.py" if scenario == "foreign" else str(source / "control.py")
if scenario == "sibling":
    filename = str(source) + "-sibling/control.py"
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
    for _ in range(200 if scenario == "unrelated" else 3 if scenario == "repeated-denied" else 1):
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
    elif scenario in {"forbidden", "threaded-denied", "repeated-denied"}:
        assert actual["rows"] == [
            {"test": "forbidden-sink", "status": "init_agent", "count": 1}
        ] * (3 if scenario == "repeated-denied" else 1)
        assert actual["body_count"] == 0
    elif scenario == "returned":
        assert actual["rows"] == [{"test": "contract-guard", "status": "APPROVED", "count": 1}]
        assert actual["body_count"] == 1
    else:
        assert actual == {"rows": [], "frame_audits": 0, "body_count": 1}


@pytest.mark.parametrize(
    "scenario",
    ["complete", "cutoff", "foreign", "sibling", "function", "spoofed-function", "wrong-type"],
)
def test_bootstrap_observer_pre_main_source_boundaries(tmp_path: Path, scenario: str) -> None:
    """SOURCE: compiled code at fixed paths, never imports or launches Hermes."""
    evidence = tmp_path / "source-observation.jsonl"
    evidence.touch(mode=0o600)
    emitter = BOOTSTRAP.split("def emit(", 1)[1].split("os.environ.clear()", 1)[0]
    observer = BOOTSTRAP.split("forbidden =", 1)[1].split("try:\n    runpy.run_module", 1)[0]
    setup = r"""
import json, os, sys, threading, time
from pathlib import Path
from types import CodeType, FunctionType
source, managed, inert, adapter = (Path("/synthetic/" + p) for p in
                                    ("source", "managed", "inert", "adapter"))
bootstrap_started_ns = time.monotonic_ns()
audit_ns, audit_calls = 0, 0
evidence_fd = os.open(sys.argv[1], os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
frame_audits = 0
def audit(event, args):
    global frame_audits
    if event == "object.__getattr__" and args[1] == "f_code":
        frame_audits += 1
sys.addaudithook(audit)
"""
    exercise = r"""
scenario = sys.argv[2]
def code_at(filename, statements):
    lines = ["\n"] * max(statements)
    for number, statement in statements.items():
        lines[number - 1] = statement + "\n"
    return compile("".join(lines), filename, "exec")
rpc_code = code_at(str(managed / "tui_gateway/rpc_dispatch.py"), {1: "'module'", 5: "pass"})
conversation_code = code_at(str(managed / "agent/conversation_loop.py"),
    {1: "'module'", 18: "pass", 40: "raise RuntimeError('PRIVATE_SOURCE_SENTINEL')" if scenario == "cutoff" else "pass", 41: "pass"})
server_code = code_at(str(inert / "tui_gateway/server.py"),
    {1: "pass", 36: "exec(conversation_code)", 37: "pass", 3363: "exec(rpc_code)", 3386: "pass"})
filename = str(inert / "tui_gateway/entry.py")
if scenario == "foreign":
    filename = "/foreign/tui_gateway/entry.py"
elif scenario == "sibling":
    filename = str(inert) + "-sibling/tui_gateway/entry.py"
if scenario in {"function", "spoofed-function", "wrong-type"}:
    module_code = code_at(filename, {1: "def ordinary():", 23: "    pass"})
    function_code = next(c for c in module_code.co_consts if type(c) is CodeType)
    if scenario == "spoofed-function":
        function_code = function_code.replace(co_name="<module>", co_qualname="<module>")
    code = function_code
else:
    statements = {1: "pass", 23: "exec(server_code)", 24: "pass"}
    if scenario == "complete":
        statements.update({439: "def main():", 441: "    pass", 464: "    pass", 469: "    return", 518: "main()"})
    code = code_at(filename, statements)
if scenario in {"foreign", "sibling"}:
    server_code = compile("pass", "/foreign/control.py", "exec")
cutoff_observed = False
try:
    if scenario in {"function", "spoofed-function"}:
        FunctionType(code, globals())()
    elif scenario == "wrong-type":
        monitor_call(object(), 0)
        monitor_return(object(), 0, 'PRIVATE_SOURCE_SENTINEL')
        monitor_line(object(), 23)
    else:
        exec(code)
except RuntimeError:
    cutoff_observed = True
if scenario != "cutoff":
    phase_transition("BOOTSTRAP_RUNPY_ENTRY_BEGIN", "END")
sys.monitoring.set_events(sys.monitoring.PROFILER_ID, 0)
sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)
os.close(evidence_fd)
print(json.dumps({"frame_audits": frame_audits, "cutoff_observed": cutoff_observed}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            setup + "def emit(" + emitter + "forbidden =" + observer + exercise,
            str(evidence),
            scenario,
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    require_empty_stderr(result.stderr)
    assert result.returncode == 0
    assert json.loads(result.stdout)["cutoff_observed"] is (scenario == "cutoff")
    raw = evidence.read_bytes()
    assert b"PRIVATE_SOURCE_SENTINEL" not in raw, "PRIVATE_SOURCE_DATA_LEAK"
    rows = [mapping(json.loads(line)) for line in raw.splitlines()]
    phases = [r for r in rows if r["test"] == "bootstrap-phase"]
    assert phases, "PRE_MAIN_PHASE_OBSERVATION_MISSING"
    assert phases[0]["status"] == "BOOTSTRAP_RUNPY_ENTRY_BEGIN"
    labels = {str(r["status"]) for r in phases}
    if scenario == "complete":
        assert labels == set(BOOTSTRAP_PHASES)
        assert all(
            {r["edge"] for r in phases if r["status"] == label} == {"ENTER", "END"}
            for label in labels
        )
    elif scenario == "cutoff":
        assert phases[-1]["status"] == "CONVERSATION_TURN_API_IMPORT_BEGIN"
        assert phases[-1]["edge"] == "ENTER"
        assert "ENTRY_MAIN_BEGIN" not in labels
    else:
        assert labels == {"BOOTSTRAP_RUNPY_ENTRY_BEGIN"}
        assert json.loads(result.stdout)["frame_audits"] == 0
    for row in phases:
        assert set(row) == {
            "test",
            "status",
            "count",
            "edge",
            "elapsed_ms",
            "audit_ms",
            "audit_calls",
        }
        assert row["count"] == 1
        for key in ("elapsed_ms", "audit_ms", "audit_calls"):
            value = row[key]
            assert type(value) is int and 0 <= value <= 10**12
    diagnostic = launch_bootstrap_checkpoint(evidence)
    assert diagnostic["root_cause"] == "UNKNOWN"
    assert diagnostic["status"] == ("OBSERVED" if scenario == "complete" else "INCOMPLETE")
    assert diagnostic["pre_ready_complete"] is (scenario == "complete")
    if scenario == "cutoff":
        assert diagnostic["last_enter"] == "CONVERSATION_TURN_API_IMPORT_BEGIN"
        assert "CONVERSATION_TURN_API_IMPORT_BEGIN" in sequence(diagnostic["pending"])
        assert diagnostic["completed"] == []
        assert diagnostic["phase_events"] == 6
    assert b"PRIVATE_SOURCE_SENTINEL" not in canonical(diagnostic), "PRIVATE_CHECKPOINT_DATA_LEAK"


@pytest.mark.parametrize(
    "scenario",
    [
        "available",
        "event-limit",
        "byte-limit",
        "record-limit",
        "closed-fd",
        "busy-tool",
        "reentrant",
    ],
)
def test_bootstrap_observer_emitter_limits_and_unavailability_fail_closed(
    tmp_path: Path, scenario: str
) -> None:
    evidence = tmp_path / "bounded-observation.jsonl"
    evidence.touch(mode=0o600)
    emitter = "def emit(" + BOOTSTRAP.split("def emit(", 1)[1].split("os.environ.clear()", 1)[0]
    observer = (
        "forbidden ="
        + BOOTSTRAP.split("forbidden =", 1)[1].split("try:\n    runpy.run_module", 1)[0]
    )
    program = r"""
import json, os, sys, threading, time
from pathlib import Path
source, managed, inert, adapter = (Path("/synthetic/" + p) for p in
                                    ("source", "managed", "inert", "adapter"))
bootstrap_started_ns = time.monotonic_ns()
audit_ns, audit_calls = 0, 0
path, scenario, emitter, observer = sys.argv[1:]
evidence_fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
exec(emitter)
body_entered, refused = False, False
try:
    if scenario == "closed-fd":
        os.close(evidence_fd)
    if scenario == "busy-tool":
        sys.monitoring.use_tool_id(sys.monitoring.PROFILER_ID, "foreign-control")
    if scenario == "reentrant":
        def recursive_write(fd, raw):
            emit("observer", "READY")
            raise AssertionError("REENTRANT_WRITE_NOT_REFUSED")
        os.write = recursive_write
    exec(observer)
    if scenario == "event-limit":
        for _ in range(256):
            emit("observer", "READY")
    elif scenario == "byte-limit":
        for _ in range(30):
            emit("observer", "x" * 3000)
    elif scenario == "record-limit":
        emit("observer", "x" * 4096)
    body_entered = True
except (RuntimeError, OSError, ValueError):
    refused = True
finally:
    sys.monitoring.set_events(sys.monitoring.PROFILER_ID, 0)
    sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)
    if scenario != "closed-fd":
        os.close(evidence_fd)
print(json.dumps({"body_entered": body_entered, "refused": refused,
                  "events": emit.events, "bytes": emit.bytes}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", program, str(evidence), scenario, emitter, observer],
        capture_output=True,
        timeout=10,
        check=False,
    )
    require_empty_stderr(result.stderr)
    assert result.returncode == 0
    actual = mapping(json.loads(result.stdout))
    assert actual["body_entered"] is (scenario == "available")
    assert actual["refused"] is (scenario != "available")
    assert 0 <= integer(actual["events"], 0) <= OBSERVATION_EVENTS
    raw = evidence.read_bytes()
    assert len(raw) == actual["bytes"] and len(raw) <= OBSERVATION_BYTES
    assert len(raw.splitlines()) == actual["events"]
    assert all(len(line) + 1 <= 4096 for line in raw.splitlines())
    if scenario in {"closed-fd", "busy-tool", "reentrant"}:
        assert raw == b""
        assert launch_bootstrap_checkpoint(evidence)["phase_events"] is None


def test_launch_failure_diagnostic_unavailable_observation_is_not_zero(tmp_path: Path) -> None:
    result = launch_bootstrap_checkpoint(tmp_path / "absent.jsonl")
    assert result["status"] == "INCOMPLETE"
    assert result["phase_events"] is None and result["elapsed_ms"] is None
    assert result["issues"] == ["OBSERVER_UNAVAILABLE"]


@pytest.mark.parametrize("missing", [None, "end", "label", "all-but-ready"])
def test_launch_failure_diagnostic_requires_pre_main_phase_evidence(missing: str | None) -> None:
    rows: list[dict[str, object]] = [{"test": "observer", "status": "READY", "count": 1}]
    for label in BOOTSTRAP_PHASES:
        for edge in ("ENTER", "END"):
            if (
                (
                    missing == "end"
                    and label == "CONVERSATION_TURN_API_IMPORT_BEGIN"
                    and edge == "END"
                )
                or (missing == "label" and label == "CONVERSATION_MODULE_BEGIN")
                or (missing == "all-but-ready" and label != "ENTRY_READY_WRITE_BEGIN")
            ):
                continue
            rows.append(
                dict(
                    test="bootstrap-phase",
                    status=label,
                    count=1,
                    edge=edge,
                    elapsed_ms=7,
                    audit_ms=2,
                    audit_calls=11,
                )
            )
    result = launch_bootstrap_diagnostic(b"".join(canonical(r) + b"\n" for r in rows))
    assert result["pre_ready_complete"] is (missing is None)
    if missing is not None:
        assert result["status"] == "INCOMPLETE"


def test_bootstrap_observer_concurrent_emitter_caps(tmp_path: Path) -> None:
    emitter = "def emit(" + BOOTSTRAP.split("def emit(", 1)[1].split("os.environ.clear()", 1)[0]
    program = r"""
import json, os, sys, threading
from types import SimpleNamespace
read_fd, evidence_fd = os.pipe()
actual_write = os.write
first_write, second_attempt, release = (threading.Event() for _ in range(3))
lock = threading.Lock()
class ObservedLock:
    def __enter__(self):
        if threading.current_thread().name == "second":
            second_attempt.set()
        lock.acquire()
    def __exit__(self, *args):
        lock.release()
def write(fd, raw):
    if threading.current_thread().name == "second":
        second_attempt.set()
    else:
        first_write.set()
    if not release.wait(2):
        raise RuntimeError("TEST_FUSE")
    return actual_write(fd, raw)
os = SimpleNamespace(write=write)
exec(sys.argv[1])
emit_lock = ObservedLock()
emit.events, emit.bytes = 255, 65000
failures = []
def invoke():
    try:
        emit("observer", "x" * 400)
    except RuntimeError:
        failures.append(True)
first = threading.Thread(target=invoke, name="first")
second = threading.Thread(target=invoke, name="second")
try:
    first.start()
    assert first_write.wait(2)
    second.start()
    assert second_attempt.wait(2)
finally:
    release.set()
    first.join(3)
    if second.ident is not None:
        second.join(3)
assert not first.is_alive() and not second.is_alive()
import os as real_os
real_os.close(evidence_fd)
raw = real_os.read(read_fd, 10000)
real_os.close(read_fd)
assert len(failures) == 1, "CONCURRENT_OBSERVER_LIMIT_BYPASS"
assert emit.events == 256 and emit.bytes == 65442 and len(raw) == 442
print("PASS")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", program, emitter],
        capture_output=True,
        timeout=10,
        check=False,
    )
    require_empty_stderr(result.stderr)
    assert result.returncode == 0


@pytest.mark.parametrize("exit_code", [0, None, True, 1, "PRIVATE_EXIT_SENTINEL"])
def test_bootstrap_observer_tail_normal_exit_is_finite(tmp_path: Path, exit_code: object) -> None:
    evidence = tmp_path / "exit-observation.jsonl"
    evidence.touch(mode=0o600)
    emitter = "def emit(" + BOOTSTRAP.split("def emit(", 1)[1].split("os.environ.clear()", 1)[0]
    tail = "try:\n    runpy.run_module" + BOOTSTRAP.split("try:\n    runpy.run_module", 1)[1]
    setup = r"""
import json, os, sys, threading
from pathlib import Path
from types import SimpleNamespace
evidence_fd = os.open(sys.argv[1], os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
code = json.loads(sys.argv[2])
def phase_transition(*args):
    pass
def invoke(*args, **kwargs):
    raise SystemExit(code)
runpy = SimpleNamespace(run_module=invoke)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            setup + emitter + tail,
            str(evidence),
            json.dumps(exit_code),
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    rows = [mapping(json.loads(line)) for line in evidence.read_bytes().splitlines()]
    normal = exit_code is None or (type(exit_code) is int and exit_code == 0)
    if normal:
        assert result.returncode == 0
        require_empty_stderr(result.stderr)
        assert rows == [
            {"test": "bootstrap-exit", "status": "NORMAL_SYSTEM_EXIT", "count": 1},
            {"test": "observer", "status": "EXIT", "count": 1},
        ]
        assert "UNKNOWN_EVENT" not in sequence(launch_bootstrap_checkpoint(evidence)["issues"])
    else:
        assert result.returncode != 0
        assert "UNKNOWN_EVENT" in sequence(launch_bootstrap_checkpoint(evidence)["issues"])


@pytest.mark.parametrize("scenario", ["runtime-restart", "runtime-restart-no-final"])
def test_h03_review_gate_precedes_database_and_container(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    monkeypatch.delenv("OMNIS_H03_NORMATIVE_REVIEWED", raising=False)
    monkeypatch.delenv("OMNIS_H03_INPUT_REVIEWED", raising=False)

    def forbidden_fixture(name: str) -> object:
        raise AssertionError("H03_EFFECT_BEFORE_REVIEW")

    monkeypatch.setattr(request, "getfixturevalue", forbidden_fixture)
    with pytest.raises(AssertionError, match="^H03_EXACT_TWO_REVIEWS_REQUIRED$"):
        test_contract_method_real_native_pg_owner_receipts_check_inbox(
            request, tmp_path, monkeypatch, False, True, False, False, False, scenario
        )


@pytest.mark.parametrize(
    "mutation", [None, "same-host", "same-native", "same-boot", "bool", "extra"]
)
def test_h03_process_receipt_requires_actual_replacement(mutation: str | None) -> None:
    compare = globals().get("h03_replaced_processes")
    assert callable(compare), "H03_PROCESS_RECEIPT_MISSING"
    old: dict[str, object] = {
        "boot": str(uuid4()),
        "host": [501, 2000, 701],
        "native": [502, 2001, 701],
    }
    new: dict[str, object] = {
        "boot": str(uuid4()),
        "host": [601, 3000, 801],
        "native": [602, 3001, 801],
    }
    if mutation == "same-host":
        new["host"] = old["host"]
    elif mutation == "same-native":
        new["native"] = old["native"]
    elif mutation == "same-boot":
        new["boot"] = old["boot"]
    elif mutation == "bool":
        new["host"] = [True, 3000, 801]
    elif mutation == "extra":
        new["capability"] = "PRIVATE_SENTINEL"
    if mutation is None:
        compare(old, new)
    else:
        with pytest.raises(AssertionError, match="^H03_PROCESS_REPLACEMENT_REFUSED$"):
            compare(old, new)


def test_h03_stock_container_plan_is_owned_and_contained(tmp_path: Path) -> None:
    build = globals().get("h03_container_argv")
    assert callable(build), "H03_CONTAINER_PLAN_MISSING"
    image = "sha256:" + "a" * 64
    for name in ("runtime", "state"):
        (tmp_path / name).mkdir(mode=0o700)
    argv = build(image, "b" * 32, tmp_path / "runtime", tmp_path / "state")
    assert argv[:3] == ["docker", "create", "--read-only"]
    assert argv[-1] == image
    for flag in ("--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges"):
        assert flag in argv
    assert "--entrypoint" not in argv and "/var/run/docker.sock" not in " ".join(argv)
    with pytest.raises(AssertionError, match="^H03_CONTAINER_PLAN_REFUSED$"):
        build(image, "b" * 32, Path("/home/kali/.hermes"), tmp_path / "state")


@pytest.mark.parametrize("mutation", [None, "task", "inbox-other", "no-consumption"])
def test_h03_census_allows_only_one_consumption(mutation: str | None) -> None:
    check = globals().get("h03_consumed_census")
    assert callable(check), "H03_CENSUS_CONTROL_MISSING"
    original: dict[str, object] = {
        "records": [{"id": "retained"}],
        "revision2": [],
        "runs": [{"id": "same"}],
        "tasks": [{"state": "SUCCEEDED"}],
        "inbox": [{"domain_result_consumed": False, "delivered": True}],
    }
    after = deepcopy(original)
    mapping(sequence(after["inbox"])[0])["domain_result_consumed"] = True
    if mutation == "task":
        mapping(sequence(after["tasks"])[0])["state"] = "BOUND"
    elif mutation == "inbox-other":
        mapping(sequence(after["inbox"])[0])["delivered"] = False
    elif mutation == "no-consumption":
        after = deepcopy(original)
    if mutation is None:
        check(canonical(original), canonical(after))
    else:
        with pytest.raises(AssertionError, match="^H03_CONSUMPTION_CENSUS_REFUSED$"):
            check(canonical(original), canonical(after))


@pytest.mark.parametrize("mutation", [None, "inventory", "uid", "dependency-manifest"])
def test_h03_static_installed_origin_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str | None
) -> None:
    handle = os.environ.get("OMNIS_H03_SOURCE_ARTIFACT")
    api_handle = os.environ.get("OMNIS_H03_SOURCE_API_ARTIFACT")
    if not handle or not api_handle:
        pytest.skip("Owned static artifacts not selected; no runtime effect")
    plan = mapping(json.loads(Path(handle).read_bytes()))
    if mutation == "inventory":
        mapping(sequence(plan["public_inventory"])[0])["sha256"] = "0" * 64
    elif mutation == "uid":
        plan["effective_uid_access"] = 1
    elif mutation == "dependency-manifest":
        plan["dependency_provenance_sha256"] = "0" * 64
    path = tmp_path / "static-plan.json"
    path.write_bytes(canonical(plan))
    path.chmod(0o600)
    # SOURCE-only fence controls, not review approvals or a launcher invocation.
    for key in ("OMNIS_H03_NORMATIVE_REVIEWED", "OMNIS_H03_INPUT_REVIEWED"):
        monkeypatch.setenv(key, sha(Path(__file__).read_bytes()))
    monkeypatch.setenv("OMNIS_H03_ARTIFACT", str(path))
    monkeypatch.setenv("OMNIS_H03_ARTIFACT_SHA", sha(path.read_bytes()))
    monkeypatch.setenv("OMNIS_H03_API_PREREQUISITES", api_handle)
    if mutation is None:
        actual, interpreter = h03_prerequisites()
        assert actual["image_id"] == plan["image_id"] and interpreter.is_file()
    else:
        with pytest.raises(AssertionError, match="^H03_INSTALLED_PREREQUISITE_REFUSED$"):
            h03_prerequisites()


@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "normal-absence-lf",
        "absence-extra-whitespace",
        "absence-unexpected-output",
        "create-warning",
        "create-cancelled",
        "never-started",
        "drain-failed",
        "stop-cancelled",
        "public-exit-failure",
        "engine-failure",
        "reader-unknown",
        "extra-mount",
        "host-pidns",
        "privileged",
        "extra-env",
        "network",
        "daemon-changed",
    ],
)
def test_h03_actual_lifecycle_source_seams(tmp_path: Path, mode: str) -> None:
    """Actual producer/acquisition/finalizer AST; substituted daemon/Host, not QA."""
    import ast
    from types import SimpleNamespace

    tree = ast.parse(
        inspect.getsource(test_contract_method_real_native_pg_owner_receipts_check_inbox)
    )
    test = cast(ast.FunctionDef, tree.body[0])
    run = next(n for n in test.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    body = next(n for n in run.body if isinstance(n, ast.Try))
    branch = next(
        n
        for n in body.body
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "h03"
    )
    # Keep all real acquisition statements, substituting only actual resource seams.
    helpers = [
        n
        for n in run.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in {"docker", "recover_cid", "inspect_owned", "retire_host"}
    ]
    directory, state_dir = tmp_path / "runtime", tmp_path / "h03-state"
    directory.mkdir(mode=0o700)
    (directory / "runtime.lock").touch(mode=0o600)
    cid_value, nonce = "c" * 64, "b" * 32
    image = "sha256:" + "a" * 64
    plan: dict[str, object] = {
        "image_id": image,
        "stock_cmd": ["/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host"],
    }
    config: dict[str, object] = {
        "Labels": {"org.omnis.h03.owner": nonce},
        "Cmd": plan["stock_cmd"],
        "Entrypoint": None,
        "User": str(os.getuid()) + ":" + str(os.getgid()),
        "Env": ["PUBLIC=stock"],
        "Volumes": None,
    }
    containment: dict[str, object] = {
        "ReadonlyRootfs": True,
        "NetworkMode": "none",
        "CapDrop": ["ALL"],
        "CapAdd": None,
        "SecurityOpt": ["no-new-privileges"],
        "PidMode": "",
        "Privileged": False,
        "PidsLimit": 64,
        "Memory": 805306368,
        "NanoCpus": 1000000000,
        "Tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=32m,mode=1777"},
        "PortBindings": {},
        "Devices": [],
        "VolumesFrom": None,
        "IpcMode": "private",
        "UTSMode": "",
        "UsernsMode": "",
        "CgroupnsMode": "private",
    }
    info: dict[str, object] = {
        "Id": cid_value,
        "Name": "/omnis-h03-" + nonce,
        "Image": image,
        "Config": config,
        "HostConfig": containment,
        "Mounts": [
            {
                "Type": "bind",
                "Source": str(path),
                "Destination": dst,
                "RW": True,
                "Mode": "",
                "Propagation": "rprivate",
            }
            for path, dst in ((directory, "/runtime"), (state_dir, "/state"))
        ],
        "State": {"Running": False, "ExitCode": 0, "Status": "created"},
    }
    if mode == "extra-mount":
        sequence(info["Mounts"]).append(
            {
                "Type": "bind",
                "Source": "/var/run/docker.sock",
                "Destination": "/var/run/docker.sock",
                "RW": True,
                "Mode": "",
                "Propagation": "rprivate",
            }
        )
    elif mode == "host-pidns":
        containment["PidMode"] = "host"
    elif mode == "privileged":
        containment["Privileged"] = True
    elif mode == "extra-env":
        config["Env"] = ["PUBLIC=stock", "HERMES_HOME=/operator"]
    elif mode == "network":
        containment["NetworkMode"] = "host"
    calls: list[str] = []
    proof: dict[str, object] = {}
    fence: dict[str, object] = {"unsettled": False}
    state: dict[str, object] = {
        "docker_unknown": False,
        "reader_unknown": mode == "reader-unknown",
        "cleanup_failed": False,
    }
    daemon = {"created": False, "removed": False, "inflight": False}
    namespace: dict[str, object] = dict(globals())

    class Runtime:
        writer: object = None

        async def connect(self) -> None:
            calls.append("connect")
            if mode == "never-started":
                raise RuntimeError("SYNTHETIC_NOT_READY")
            self.writer = object()

        async def drain(self) -> bool:
            calls.append("drain")
            return mode != "drain-failed"

        async def close(self) -> None:
            calls.append("close")
            self.writer = None

    runtime = Runtime()

    async def start_host() -> None:
        calls.append("start_host")
        if mode == "never-started":
            raise RuntimeError("SYNTHETIC_PRE_BOOT_FAILURE")
        mapping(info["State"]).update(Running=True, Status="running")
        runtime.writer = object()

    class Child:
        pid = 101
        returncode: int | None = None

        def __init__(self, argv: tuple[str, ...]) -> None:
            self.argv = argv

        async def communicate(self) -> tuple[bytes, bytes]:
            op = self.argv[1]
            calls.append(op)
            if op == "info":
                self.returncode = 0
                value = (
                    "changed-daemon"
                    if mode == "daemon-changed" and daemon["created"]
                    else "owned-daemon"
                )
                return (value + "\n").encode(), b""
            if op == "image":
                self.returncode = 0
                return json.dumps(
                    [{"Id": image, "Config": {**config, "Env": ["PUBLIC=stock"]}}]
                ).encode(), b""
            if op == "create":
                daemon["created"] = True
                path = tmp_path / ("h03-" + nonce + ".cid")
                path.write_text(cid_value + "\n")
                path.chmod(0o600)
                if mode == "create-cancelled":
                    daemon["inflight"] = True
                    raise asyncio.CancelledError
                self.returncode = 0
                return (
                    cid_value + "\n"
                ).encode(), b"PRIVATE_SYNTHETIC_WARNING" if mode == "create-warning" else b""
            if op == "stop":
                if mode == "stop-cancelled" and not daemon["inflight"]:
                    daemon["inflight"] = True
                    raise asyncio.CancelledError
                mapping(info["State"]).update(Running=False, Status="exited")
            if op == "rm":
                daemon["removed"] = True
            self.returncode = 0
            if op == "inspect":
                if daemon["removed"]:
                    self.returncode = 1
                    output = {
                        "normal-absence-lf": b"\n",
                        "absence-extra-whitespace": b" \n",
                        "absence-unexpected-output": b"UNEXPECTED_CONTAINER\n",
                    }.get(mode, b"")
                    return output, ("Error: No such object: " + cid_value + "\n").encode()
                return json.dumps([info]).encode(), b""
            return (cid_value + "\n").encode(), b""

        def kill(self) -> None:
            calls.append("direct-child-kill")
            self.returncode = -9

        async def wait(self) -> int | None:
            calls.append("direct-child-join")
            return self.returncode

    async def spawn(*args: str, **kwargs: object) -> Child:
        return Child(args)

    class PublicControl:
        lock_fd = None
        directory = tmp_path

        async def __aexit__(self, *args: object) -> None:
            calls.append("public-owner-exit")
            assert fence["unsettled"] is True, "H03_FENCE_RELEASED_BEFORE_PUBLIC_OWNER"
            if mode == "public-exit-failure":
                raise RuntimeError("SYNTHETIC_PUBLIC_OWNER_FAILURE")

    class Engine:
        async def dispose(self) -> None:
            calls.append("engine-dispose")
            assert fence["unsettled"] is True, "H03_FENCE_RELEASED_BEFORE_ENGINE"
            if mode == "engine-failure":
                raise RuntimeError("SYNTHETIC_ENGINE_FAILURE")

    namespace.update(
        asyncio=SimpleNamespace(
            create_subprocess_exec=spawn,
            subprocess=asyncio.subprocess,
            timeout=asyncio.timeout,
            wait_for=asyncio.wait_for,
            gather=asyncio.gather,
        ),
        cid="",
        nonce=nonce,
        directory=directory,
        state_dir=state_dir,
        tmp_path=tmp_path,
        h03=True,
        runtime=runtime,
        process_receipts=[],
        db_fence=fence,
        h03_plan=plan,
        h03_state=state,
        daemon_id="",
        image_config={},
        h03_deadline=time.monotonic() + 60,
        checkpoint=lambda **fields: proof.update(fields),
        start_host=start_host,
        done=asyncio.Event(),
        dispatch_waiters=[],
        heartbeat=None,
        public_control=PublicControl(),
        engine=Engine(),
        host=None,
        proof=proof,
    )
    unit = ast.AsyncFunctionDef(
        name="consumer",
        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        decorator_list=[],
        body=[
            *ast.parse("cid = ''\ndaemon_id = ''\nimage_config = {}\n").body,
            *helpers,
            ast.Try(body=branch.body, handlers=body.handlers, orelse=[], finalbody=body.finalbody),
        ],
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[unit], type_ignores=[])),
            "<actual-h03-consumer-seams>",
            "exec",
        ),
        namespace,
    )
    error: BaseException | None = None
    try:
        asyncio.run(cast(Callable[[], Coroutine[object, object, None]], namespace["consumer"])())
    except BaseException as exc:
        error = exc
    assert "engine-dispose" in calls, "H03_LATE_CLEANUP_SKIPPED"
    assert proof.get("h03_name") == "omnis-h03-" + nonce
    assert proof.get("h03_cidfile") == str(tmp_path / ("h03-" + nonce + ".cid"))
    negative = mode not in {"normal", "normal-absence-lf"}
    assert fence["unsettled"] is negative, "H03_UNSAFE_FENCE_TRANSITION"
    if mode not in {"daemon-changed"}:
        assert daemon["removed"], "H03_EXACT_RESOURCE_CLEANUP_SKIPPED"
        assert proof.get("h03_cid") == cid_value, "H03_EXACT_CID_NOT_RETAINED"
    if mode in {"extra-mount", "host-pidns", "privileged", "extra-env", "network"}:
        assert "start_host" not in calls, "H03_CONTAINMENT_FALSE_GREEN"
    if mode in {"create-warning", "create-cancelled", "never-started"}:
        assert "connect" not in calls, "H03_STOPPED_CLEANUP_REQUIRES_HOST"
    if mode in {"create-cancelled", "stop-cancelled"}:
        assert state["docker_unknown"] is True, "H03_ORIGINAL_UNKNOWN_NOT_LATCHED"
    if negative:
        assert proof.get("status") == "UNCERTAIN", "H03_UNCERTAINTY_NOT_CHECKPOINTED"
    else:
        assert error is None, "H03_NORMAL_SOURCE_CLEANUP_FAILED"


@pytest.mark.parametrize("valid_drain", [True, False])
def test_h03_settled_connection_retires_after_offline_readers(
    monkeypatch: pytest.MonkeyPatch, valid_drain: bool
) -> None:
    """Actual caller AST + SOURCE Host/client UDS; no native, DB or Docker launch."""
    import ast
    import tempfile

    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes/src"))
    from omnis_hermes.runtime_host import RuntimeHost

    tree = ast.parse(
        inspect.getsource(test_contract_method_real_native_pg_owner_receipts_check_inbox)
    )
    retire = next(
        n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "retire_host"
    )
    readers = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "h03_restart_readers"
    )
    start = next(
        i
        for i, n in enumerate(readers.body)
        if isinstance(n, ast.If) and "H03_REPLACEMENT_NATIVE_DRAIN_UNCERTAIN" in ast.unparse(n)
    )
    end = next(
        i
        for i, n in enumerate(readers.body)
        if isinstance(n, ast.If) and "H03_RESTART_CHANGED_DOMAIN_CENSUS" in ast.unparse(n)
    )
    settle = ast.AsyncFunctionDef(
        name="settle",
        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=readers.body[start:end],
        decorator_list=[],
    )

    async def run() -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="h03-") as name:
            directory = Path(name)
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            assert len(os.fsencode(directory / "runtime.sock")) < 108
            async with RuntimeHost(directory) as host:
                runtime = RuntimeClient(directory, generation=0, epoch=1)
                state: dict[str, object] = {"Running": True, "ExitCode": 0}
                flags = {"docker_unknown": False, "cleanup_failed": False}
                proof: dict[str, object] = {}

                async def inspect_owned() -> dict[str, object]:
                    return {"State": state}

                async def docker(*args: str) -> None:
                    assert args == ("stop", "--time=5", "source-only")
                    await host.__aexit__(None, None, None)
                    state["Running"] = False

                namespace: dict[str, object] = dict(globals())
                namespace.update(
                    runtime=runtime,
                    cid="source-only",
                    directory=directory,
                    inspect_owned=inspect_owned,
                    docker=docker,
                    h03_state=flags,
                    process_receipts=[],
                    checkpoint=lambda **fields: proof.update(fields),
                )
                exec(
                    compile(
                        ast.fix_missing_locations(
                            ast.Module(body=[settle, retire], type_ignores=[])
                        ),
                        "<actual-h03-settlement>",
                        "exec",
                    ),
                    namespace,
                )
                settle_call = cast(
                    Callable[[], Coroutine[object, object, None]], namespace["settle"]
                )
                retire_call = cast(
                    Callable[[], Coroutine[object, object, None]], namespace["retire_host"]
                )
                try:
                    await runtime.connect()
                    assert (await runtime.status())["drained"] is True
                    if not valid_drain:
                        runtime.capability = "invalid-synthetic-capability"
                        with pytest.raises(
                            AssertionError, match="^H03_REPLACEMENT_NATIVE_DRAIN_UNCERTAIN$"
                        ):
                            await settle_call()
                        assert "h03_last_retirement" not in proof
                        return
                    await settle_call()
                    # Same offline interval that lets the unchanged Host idle timer fire.
                    await asyncio.sleep(2.7)
                    await retire_call()
                    assert runtime.writer is None and not any(flags.values())
                    assert proof["h03_last_retirement"] == (
                        "HOST_EXIT0_NATIVE_DRAIN_ENDPOINTS_ABSENT_LOCK_FREE"
                    )
                    assert host.process is None and not host.clients
                finally:
                    await runtime.close()

    asyncio.run(run())


def test_h03_mount_roots_refuse_physical_alias(tmp_path: Path) -> None:
    runtime, state = tmp_path / "runtime", tmp_path / "state"
    runtime.mkdir(mode=0o700)
    state.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(runtime, target_is_directory=True)
    with pytest.raises(AssertionError, match="^H03_CONTAINER_PLAN_REFUSED$"):
        h03_container_argv("sha256:" + "a" * 64, "b" * 32, alias, state)


@pytest.mark.parametrize(
    "mode", ["normal", "denial", "timeout", "cancelled", "unknown", "bad-receipt"]
)
def test_h03_reader_actual_launch_latches_family_unknown(tmp_path: Path, mode: str) -> None:
    """Real nested reader producer; family/installed/DB seams are substituted."""
    import ast
    from types import SimpleNamespace

    tree = ast.parse(
        inspect.getsource(test_contract_method_real_native_pg_owner_receipts_check_inbox)
    )
    fn = next(
        n
        for n in cast(ast.FunctionDef, tree.body[0]).body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "restarted_cli"
    )
    fence: dict[str, object] = {"unsettled": False}
    state = {"reader_unknown": False, "docker_unknown": False, "cleanup_failed": False}
    proof: dict[str, object] = {}
    reached: list[str] = []

    async def family(
        fn: object, argv: list[str], env: object, log: Path, timeout: int, **kwargs: object
    ) -> int:
        assert state["reader_unknown"] and fence["unsettled"], "H03_READER_PRELAUNCH_FENCE_MISSING"
        reached.append("family")
        if mode == "cancelled":
            raise asyncio.CancelledError
        if mode == "timeout":
            raise TimeoutError
        code = 2 if mode == "denial" else 99 if mode == "unknown" else 0
        audit = log.with_name(log.name.removesuffix(".gate.log") + ".jsonl")
        rows = [
            {"status": "ORIGIN", "name": "INSTALLED", "pid": 101},
            {"status": "READY", "name": "managed-cli", "pid": 101},
            {"status": "EXIT", "name": str(code), "pid": 101},
        ]
        if mode == "bad-receipt":
            rows[-1]["name"] = "99"
        audit.write_text("\n".join(json.dumps(row) for row in rows))
        audit.with_suffix(".stdout").write_bytes(b"{}" if code == 0 else b"")
        audit.with_suffix(".stderr").write_bytes(
            b'{"status":"BLOCKED","reason":"NEEDS_RECONCILIATION"}' if code == 2 else b""
        )
        return code

    namespace: dict[str, object] = dict(globals())
    namespace.update(
        tmp_path=tmp_path,
        h03=True,
        h03_state=state,
        db_fence=fence,
        reader_python=Path(sys.executable),
        python=Path(sys.executable),
        dsn="SYNTHETIC_PRIVATE_DSN",
        seed=SimpleNamespace(root=tmp_path, environment=lambda dsn: {}),
        proof=proof,
        checkpoint=lambda **fields: proof.update(fields),
        asyncio=SimpleNamespace(to_thread=family),
    )
    wrapper = ast.parse(
        "async def consumer():\n"
        "    return await restarted_cli('readback', {}, reason=reader_reason)\n"
    ).body[0]
    namespace["reader_reason"] = "NEEDS_RECONCILIATION" if mode == "denial" else None
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[fn, wrapper], type_ignores=[])),
            "<actual-h03-reader-source>",
            "exec",
        ),
        namespace,
    )
    failed = False
    try:
        call = cast(Callable[[], Coroutine[object, object, object]], namespace["consumer"])
        asyncio.run(call())
    except AssertionError:
        failed = True
    uncertain = mode not in {"normal", "denial"}
    assert reached == ["family"]
    assert failed is uncertain
    assert state["reader_unknown"] is uncertain
    assert fence["unsettled"] is True  # Only complete run finalizer may clear it.


@pytest.mark.parametrize("mode", ["normal", "newline", "mode", "symlink", "hardlink", "content"])
def test_h03_actual_cidfile_recovery_is_strict(tmp_path: Path, mode: str) -> None:
    import ast

    tree = ast.parse(
        inspect.getsource(test_contract_method_real_native_pg_owner_receipts_check_inbox)
    )
    test = cast(ast.FunctionDef, tree.body[0])
    run = next(n for n in test.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    recover = next(
        n for n in run.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "recover_cid"
    )
    nonce, value = "b" * 32, "c" * 64
    path = tmp_path / ("h03-" + nonce + ".cid")
    path.write_text(value + ("\n" if mode == "newline" else "") if mode != "content" else "INVALID")
    path.chmod(0o644 if mode == "mode" else 0o600)
    if mode == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    elif mode == "hardlink":
        os.link(path, tmp_path / "alias")
    proof: dict[str, object] = {}
    attested: list[bool] = []

    async def inspect_owned() -> dict[str, object]:
        attested.append(True)
        return {}

    namespace: dict[str, object] = dict(globals())
    namespace.update(
        state_dir=tmp_path / "state",
        nonce=nonce,
        checkpoint=lambda **fields: proof.update(fields),
        inspect_owned=inspect_owned,
    )
    wrapper = ast.AsyncFunctionDef(
        name="consumer",
        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        decorator_list=[],
        body=[*ast.parse("cid = ''").body, recover, *ast.parse("await recover_cid()").body],
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
            "<actual-h03-cid-source>",
            "exec",
        ),
        namespace,
    )
    failed = False
    try:
        asyncio.run(cast(Callable[[], Coroutine[object, object, None]], namespace["consumer"])())
    except (AssertionError, OSError):
        failed = True
    assert failed is (mode not in {"normal", "newline"})
    assert bool(attested) is (not failed)
    if not failed:
        assert proof["h03_cid"] == value


def h03_consumed_census(before: bytes, after: bytes) -> None:
    expected = mapping(json.loads(before))
    inboxes = sequence(expected["inbox"])
    if len(inboxes) != 1 or mapping(inboxes[0])["domain_result_consumed"] is not False:
        raise AssertionError("H03_CONSUMPTION_CENSUS_REFUSED")
    mapping(inboxes[0])["domain_result_consumed"] = True
    if canonical(expected) != after:
        raise AssertionError("H03_CONSUMPTION_CENSUS_REFUSED")


def h03_replaced_processes(old: dict[str, object], new: dict[str, object]) -> None:
    """Host-visible PID/starttime/pidns, not namespace PID1 or Python identity."""
    from uuid import UUID

    for row in (old, new):
        if set(row) != {"boot", "host", "native"} or type(row["boot"]) is not str:
            raise AssertionError("H03_PROCESS_REPLACEMENT_REFUSED")
        try:
            if str(UUID(str(row["boot"]))) != row["boot"]:
                raise ValueError
        except ValueError:
            raise AssertionError("H03_PROCESS_REPLACEMENT_REFUSED") from None
        for name in ("host", "native"):
            values = row[name]
            if (
                type(values) is not list
                or len(values) != 3
                or any(type(v) is not int or v <= 0 for v in values)
            ):
                raise AssertionError("H03_PROCESS_REPLACEMENT_REFUSED")
        host, native = sequence(row["host"]), sequence(row["native"])
        if host[0] == native[0] or host[2] != native[2]:
            raise AssertionError("H03_PROCESS_REPLACEMENT_REFUSED")
    if any(old[k] == new[k] for k in ("boot", "host", "native")):
        raise AssertionError("H03_PROCESS_REPLACEMENT_REFUSED")
    if sequence(old["host"])[2] == sequence(new["host"])[2]:
        raise AssertionError("H03_PROCESS_REPLACEMENT_REFUSED")


def h03_container_argv(image: str, nonce: str, runtime: Path, state: Path) -> list[str]:
    scratch = Path("/home/kali/.hermes/cache/scratch")
    if (
        re.fullmatch(r"sha256:[a-f0-9]{64}", image) is None
        or re.fullmatch(r"[a-f0-9]{32}", nonce) is None
        or os.getuid() <= 0
        or any(
            not p.is_absolute()
            or p.resolve(strict=True) != p
            or not p.is_relative_to(scratch)
            or not stat.S_ISDIR(p.lstat().st_mode)
            or p.lstat().st_uid != os.getuid()
            or stat.S_IMODE(p.lstat().st_mode) != 0o700
            for p in (runtime, state)
        )
        or runtime.absolute() == state.absolute()
    ):
        raise AssertionError("H03_CONTAINER_PLAN_REFUSED")
    return [
        "docker",
        "create",
        "--read-only",
        "--network=none",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--memory=768m",
        "--cpus=1",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777",
        "--user=" + str(os.getuid()) + ":" + str(os.getgid()),
        "--name=omnis-h03-" + nonce,
        "--label=org.omnis.h03.owner=" + nonce,
        "--cidfile=" + str(state.parent / ("h03-" + nonce + ".cid")),
        "--mount=type=bind,src=" + str(runtime) + ",dst=/runtime",
        "--mount=type=bind,src=" + str(state) + ",dst=/state",
        image,
    ]


def h03_prerequisites() -> tuple[dict[str, object], Path]:
    """Static installed origin before acquiring the existing DB or OCI fixture."""
    digest = sha(Path(__file__).read_bytes())
    if any(
        os.environ.get(key) != digest
        for key in ("OMNIS_H03_NORMATIVE_REVIEWED", "OMNIS_H03_INPUT_REVIEWED")
    ):
        raise AssertionError("H03_EXACT_TWO_REVIEWS_REQUIRED")
    try:
        artifact = Path(os.environ["OMNIS_H03_ARTIFACT"])
        info = artifact.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
        ):
            raise ValueError
        raw = artifact.read_bytes()
        if sha(raw) != os.environ["OMNIS_H03_ARTIFACT_SHA"]:
            raise ValueError
        plan = mapping(json.loads(raw))
        root = Path(str(plan["root"])).resolve(strict=True)
        if not root.is_relative_to(Path("/home/kali/.hermes/cache/scratch")):
            raise ValueError
        if (
            plan["status"] != "PASS_STATIC_CURRENT_DISTRIBUTION"
            or plan["effective_uid_access"] is not True
            or plan.get("dependency_provenance_sha256")
            != sha((ROOT / "integrations/hermes/runtime-override/provenance.json").read_bytes())
            or plan["runtime_started"] is not False
            or plan["startup_autoload"] != "NONE"
            or type(plan["image_id"]) is not str
            or re.fullmatch(r"sha256:[a-f0-9]{64}", str(plan["image_id"])) is None
            or plan["stock_cmd"]
            != ["/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host"]
            or os.getuid() != 1000
            or os.getgid() != 1000
        ):
            raise ValueError
        upstream = ROOT / "integrations/hermes/upstream"
        expected: dict[str, str] = {}
        for manifest, source in (
            ("patch-manifest.json", "inert-source"),
            ("managed-patch-manifest.json", "managed-source"),
        ):
            for name in mapping(mapping(json.loads((upstream / manifest).read_bytes()))["files"]):
                expected["opt/hermes/source/" + name] = sha((upstream / source / name).read_bytes())
        for path in (ROOT / "integrations/hermes/src/omnis_hermes").glob("*.py"):
            expected["opt/hermes/venv/lib/python3.13/site-packages/omnis_hermes/" + path.name] = (
                sha(path.read_bytes())
            )
        rows = [mapping(row) for row in sequence(plan["public_inventory"])]
        if len(rows) != len(expected) or len(expected) != 34:
            raise ValueError
        if {str(row["path"]): row["sha256"] for row in rows} != expected or any(
            row["match"] is not True for row in rows
        ):
            raise ValueError
        _, current = historical_installed_plan(Path(os.environ["OMNIS_H03_API_PREREQUISITES"]))
        import zipfile

        with zipfile.ZipFile(str(current["wheel"])) as wheel:
            for name in wheel.namelist():
                if name.startswith("omnis/") and not name.endswith("/"):
                    if wheel.read(name) != (ROOT / "api/src" / name).read_bytes():
                        raise ValueError
        return plan, Path(str(current["python"]))
    except (OSError, ValueError, KeyError, AssertionError):
        raise AssertionError("H03_INSTALLED_PREREQUISITE_REFUSED") from None


class H03ExchangeObservation:
    """One SOURCE-owned exchange; exact code RAISE, no frames/locals/wire capture."""

    def __init__(
        self,
        original: Callable[
            [str, RuntimeAuthority | None, dict[str, object] | None],
            Coroutine[object, object, dict[str, object]],
        ],
        checkpoint: Callable[[dict[str, object]], None],
    ) -> None:
        import dis

        from omnis.supervisor import runtime_client as source

        if getattr(original, "__func__", None) is not RuntimeClient._exchange:
            raise AssertionError("H03_EXACT_CLIENT_REQUIRED")
        self.original, self.checkpoint = original, checkpoint
        self.used = False
        self.events: list[dict[str, object]] = []
        self.complete = True
        self.sites: dict[CodeType, dict[int, tuple[int | None, str]]] = {}
        self.names: dict[CodeType, str] = {}
        self.task: asyncio.Task[object] | None = None
        self.tool: int | None = None
        # Only fixed reasons from trusted source raise sites, never error.args/str.
        reasons = {
            "Runtime refused": "HOST_DENIED_CAUSE_UNKNOWN",
            "Runtime exchange unavailable": "EXCHANGE_NORMALIZED",
            "Expired runtime authority": "AUTHORITY_EXPIRED",
            "Runtime authority mismatch": "AUTHORITY_MISMATCH",
            "Runtime authority missing": "AUTHORITY_MISSING",
            "Runtime disconnected": "DISCONNECTED",
            "Runtime managed-task limit": "MANAGED_FRAME_LIMIT",
            "Runtime correlation mismatch": "CORRELATION_MISMATCH",
            "Runtime managed-task fence": "MANAGED_FENCE",
            "Invalid runtime state": "INVALID_STATE",
            "Invalid runtime readiness": "INVALID_READINESS",
            "Invalid runtime fence": "INVALID_FENCE",
            "Runtime stale fence": "STALE_FENCE",
            "Invalid runtime drain": "INVALID_DRAIN",
            "Missing bootstrap inventory": "MISSING_INVENTORY",
            "Missing ready bootstrap inventory": "MISSING_READY_INVENTORY",
            "Changed bootstrap inventory": "CHANGED_INVENTORY",
            "Invalid bootstrap inventory": "INVALID_INVENTORY",
            "Bootstrap inventory limit": "INVENTORY_LIMIT",
            "Invalid runtime message": "INVALID_MESSAGE",
            "Runtime message limit": "MESSAGE_LIMIT",
        }
        for fn in (
            RuntimeClient._exchange,
            source._object,
            source._unique,
            source.validate_bootstrap_inventory,
            source._inventory_name,
        ):
            self.names[fn.__code__] = fn.__qualname__
            sites: dict[int, tuple[int | None, str]] = {}
            literal = ""
            for instruction in dis.get_instructions(fn):
                if instruction.opname == "LOAD_CONST" and type(instruction.argval) is str:
                    literal = instruction.argval
                sites[instruction.offset] = (
                    instruction.positions.lineno if instruction.positions is not None else None,
                    reasons.get(literal, "UNCLASSIFIED")
                    if instruction.opname == "RAISE_VARARGS"
                    else "UNCLASSIFIED",
                )
            self.sites[fn.__code__] = sites

    def raised(self, code: object, offset: int, error: BaseException) -> object:
        from omnis.supervisor.runtime_client import RuntimeUnavailable

        try:
            if type(code) is not CodeType or not any(code is target for target in self.sites):
                return None
            if asyncio.current_task() is not self.task:
                return None
            if len(self.events) >= 31:  # Reserve END; total <=32 / <=8KiB.
                self.complete = False
                if self.tool is not None:
                    sys.monitoring.set_events(self.tool, 0)
                return None
            line, reason = self.sites[code].get(offset, (None, "UNCLASSIFIED"))
            classes = (
                RuntimeUnavailable,
                ValueError,
                OSError,
                TimeoutError,
                asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,
                ConnectionResetError,
                BrokenPipeError,
                PermissionError,
                asyncio.CancelledError,
            )
            self.events.append(
                {
                    "phase": "RAISE",
                    "code": self.names[code],
                    "offset": offset,
                    "line": line,
                    "exception": type(error).__name__ if type(error) in classes else "UNCLASSIFIED",
                    "reason": reason if type(error) is RuntimeUnavailable else "UNCLASSIFIED",
                }
            )
        except BaseException:
            self.complete = False  # Callback never changes the original exception.
            return None
        return None

    async def exchange(
        self,
        op: str,
        authority: RuntimeAuthority | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if op != "task_release" or self.used:
            return await self.original(op, authority, payload)
        self.used = True
        tool: int | None = None
        failed = False
        started = time.monotonic_ns()
        reply: dict[str, object] | None = None
        try:
            tool = next((i for i in range(6) if sys.monitoring.get_tool(i) is None), None)
            if tool is None:
                raise AssertionError("H03_MONITORING_UNAVAILABLE")
            sys.monitoring.use_tool_id(tool, "h03-release")
            self.tool = tool
            callback = self.raised
            sys.monitoring.register_callback(tool, sys.monitoring.events.RAISE, callback)
            if (
                sys.monitoring.register_callback(tool, sys.monitoring.events.RAISE, callback)
                is not callback
            ):
                raise AssertionError("H03_MONITORING_UNAVAILABLE")
            # RAISE is interpreter-wide (not a supported local event in 3.13).
            # Exact CodeType identity + original Task filter precede all capture.
            self.task = asyncio.current_task()
            sys.monitoring.set_events(tool, sys.monitoring.events.RAISE)
            # Timestamp at the ORIGINAL request boundary, after registration.
            started = time.monotonic_ns()
            self.events.append(
                {
                    "phase": "ENTER",
                    "elapsed_ms": 0,
                    "grant_remaining_ms": None
                    if authority is None
                    else (authority.deadline_ns - started) // 1_000_000,
                }
            )
            try:
                reply = await self.original(op, authority, payload)
            except BaseException:
                failed = True
                if not any(
                    row.get("phase") == "RAISE" and row.get("reason") != "EXCHANGE_NORMALIZED"
                    for row in self.events
                ):
                    self.complete = False
                raise
        except BaseException:
            if not self.events:
                self.complete = False
                raise AssertionError("H03_MONITORING_UNAVAILABLE") from None
            raise
        finally:
            try:
                if tool is not None and sys.monitoring.get_tool(tool) == "h03-release":
                    sys.monitoring.set_events(tool, 0)
                    sys.monitoring.register_callback(tool, sys.monitoring.events.RAISE, None)
                    sys.monitoring.free_tool_id(tool)
            except BaseException:
                self.complete = False
            ended = time.monotonic_ns()
            self.events.append(
                {
                    "phase": "END",
                    "elapsed_ms": (ended - started) // 1_000_000,
                    "grant_remaining_ms": None
                    if authority is None
                    else (authority.deadline_ns - ended) // 1_000_000,
                    "returned": reply is not None,
                    "correlation_valid": True
                    if reply is not None
                    or any(row.get("reason") == "HOST_DENIED_CAUSE_UNKNOWN" for row in self.events)
                    else None,
                    "ok": reply.get("ok") is True if reply is not None else None,
                    "writer_drained": True
                    if reply is not None
                    or any(row.get("reason") == "HOST_DENIED_CAUSE_UNKNOWN" for row in self.events)
                    else None,
                    "read_complete": True
                    if reply is not None
                    or any(row.get("reason") == "HOST_DENIED_CAUSE_UNKNOWN" for row in self.events)
                    else None,
                }
            )
            diagnostic: dict[str, object] = {
                "status": "COMPLETE" if self.complete else "INCOMPLETE",
                "events": self.events,
                "host_internal_cause": "UNKNOWN",
            }
            if len(canonical(diagnostic)) > 8192:
                self.complete = False
                diagnostic = {"status": "INCOMPLETE", "reason": "OBSERVER_LIMIT"}
            try:
                self.checkpoint(diagnostic)
            except BaseException:
                self.complete = False
                if not failed:
                    raise AssertionError("H03_DIAGNOSTIC_UNAVAILABLE") from None
        if not self.complete:
            raise AssertionError("H03_OBSERVATION_INCOMPLETE")
        assert reply is not None
        return reply


@pytest.mark.parametrize("mode", ["ready", "host-denied", "private-error", "expired"])
def test_h03_exchange_observation_actual_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """SOURCE: actual client/caller, fake IPC only; no PG/socket/native effects."""
    import ast

    from omnis.supervisor.runtime_client import RuntimeUnavailable

    observer = globals().get("H03ExchangeObservation")
    assert callable(observer), "H03_PRE_NORMALIZATION_OBSERVER_MISSING"
    client = RuntimeClient(tmp_path, generation=1, epoch=1)
    writes: list[bytes] = []
    records: list[dict[str, object]] = []

    class Writer:
        def write(self, raw: bytes) -> None:
            writes.append(raw)

        async def drain(self) -> None:
            if mode == "private-error":
                raise ValueError("PRIVATE_H03_MARKER")

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            pass

    class Reader:
        async def readuntil(self, separator: bytes) -> bytes:
            request = mapping(json.loads(writes[-1]))
            return canonical(
                {
                    "id": request["id"],
                    "boot": client.boot,
                    "ok": mode != "host-denied",
                    "state": "READY",
                    "assessment_ready": False,
                    "drained": False,
                    "generation": 1,
                    "epoch": 1,
                    "managed": {},
                    "bootstrap_inventory": {
                        "schema_version": 1,
                        "observation": "NATIVE_BOOTSTRAP",
                        "scope": "/state/active",
                        "registry": {
                            "status": "NOT_INITIALIZED",
                            "generation": None,
                            "count": None,
                            "entries": None,
                        },
                        "plugins": {"status": "NOT_INITIALIZED", "count": None, "entries": None},
                    },
                }
            )

    client.writer = cast(asyncio.StreamWriter, Writer())
    client.reader = cast(asyncio.StreamReader, Reader())

    tree = ast.parse(
        inspect.getsource(test_contract_method_real_native_pg_owner_receipts_check_inbox)
    )
    branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "h03"
        and any(isinstance(n, ast.Name) and n.id == "release_observer" for n in ast.walk(node))
    )
    namespace: dict[str, object] = {
        "h03": True,
        "runtime": client,
        "monkeypatch": monkeypatch,
        "H03ExchangeObservation": observer,
        "checkpoint": lambda **fields: records.append(fields),
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[])),
            "<actual-h03-exchange-caller>",
            "exec",
        ),
        namespace,
    )
    authority = RuntimeAuthority(
        1, 1, time.monotonic_ns() + (0 if mode == "expired" else 4_000_000_000)
    )
    caught: BaseException | None = None
    try:
        reply = asyncio.run(client._exchange("task_release", authority, {}))
    except RuntimeUnavailable as error:
        caught = error
    else:
        assert mode == "ready" and reply["managed"] == {}
    assert len(writes) == (0 if mode == "expired" else 1), "H03_SEND_COUNT_CHANGED"
    assert (caught is None) == (mode == "ready")
    diagnostic = mapping(records[-1]["h03_release_exchange"])
    rows = sequence(diagnostic["events"])
    assert mapping(rows[0])["phase"] == "ENTER" and mapping(rows[-1])["phase"] == "END"
    assert diagnostic["status"] == "COMPLETE"
    reasons = {mapping(row).get("reason") for row in rows}
    expected = {
        "host-denied": "HOST_DENIED_CAUSE_UNKNOWN",
        "private-error": "UNCLASSIFIED",
        "expired": "AUTHORITY_EXPIRED",
    }
    if mode in expected:
        assert expected[mode] in reasons, "H03_ORIGINAL_FAILURE_NOT_OBSERVED"
    assert b"PRIVATE_H03_MARKER" not in canonical(diagnostic), "H03_PRIVATE_DIAGNOSTIC_LEAK"
    assert len(rows) <= 32 and len(canonical(diagnostic)) <= 8192
    assert all(sys.monitoring.get_tool(tool) != "h03-release" for tool in range(6))


@pytest.mark.parametrize("control", ["registration", "missing", "budget", "callback"])
def test_h03_exchange_observation_refuses_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    from omnis.supervisor.runtime_client import RuntimeUnavailable

    client = RuntimeClient(tmp_path, generation=1, epoch=1)
    records: list[dict[str, object]] = []
    measured = H03ExchangeObservation(
        client._exchange, lambda diagnostic: records.append({"h03_release_exchange": diagnostic})
    )
    register = sys.monitoring.register_callback
    originals: list[BaseException] = []
    previous_callback: object = None
    # Structurally equal code clones must not pass an identity filter.
    assert (
        measured.raised(
            RuntimeClient._exchange.__code__.replace(), 0, RuntimeUnavailable("PRIVATE_H03_MARKER")
        )
        is None
    )
    assert measured.events == []

    def registration(tool: int, event: int, callback: object) -> object:
        nonlocal previous_callback
        if callback is None:
            return register(tool, event, None)
        if control == "registration":
            raise ValueError("PRIVATE_H03_MARKER")
        if control == "missing":
            return None
        actual = cast(Callable[[object, int, BaseException], object], callback)

        def inject(code: object, offset: int, error: BaseException) -> object:
            originals.append(error)
            if control == "budget":
                for _ in range(34):
                    actual(code, offset, error)
            else:
                # A callback-local decode failure, not a product exception.
                measured.names.clear()
                actual(code, offset, error)
            return None

        previous = register(tool, event, inject)
        result = previous_callback if previous is not None else None
        previous_callback = callback
        return result

    monkeypatch.setattr(sys.monitoring, "register_callback", registration)
    with pytest.raises((AssertionError, RuntimeUnavailable)) as caught:
        asyncio.run(measured.exchange("task_release", None, {}))
    if originals:
        assert caught.value is originals[0], "H03_CALLBACK_MASKED_ORIGINAL"
    diagnostic = mapping(records[-1]["h03_release_exchange"])
    assert diagnostic["status"] == "INCOMPLETE", "H03_MISSING_EVIDENCE_ACCEPTED"
    if control in {"registration", "missing"}:
        assert len(sequence(diagnostic["events"])) == 1, "H03_UNREGISTERED_BODY_ENTERED"
    assert len(sequence(diagnostic.get("events", []))) <= 32
    assert len(canonical(diagnostic)) <= 8192
    assert b"PRIVATE_H03_MARKER" not in canonical(diagnostic)
    assert all(sys.monitoring.get_tool(tool) != "h03-release" for tool in range(6))


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
        (False, True, False, False, False, "result-qualification"),
        (False, True, False, False, False, "historical-installed"),
        (False, True, False, False, False, "runtime-restart"),
        (False, True, False, False, False, "runtime-restart-no-final"),
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
        "result-qualification",
        "historical-installed",
        "runtime-restart",
        "runtime-restart-no-final",
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
    h03 = applicability in {"runtime-restart", "runtime-restart-no-final"}
    h03_plan: dict[str, object] = {}
    reader_python: Path | None = None
    db_fence: dict[str, object] = {}
    if h03:
        h03_plan, reader_python = h03_prerequisites()
        db_fence = mapping(request.getfixturevalue("historical_database_fence"))
    else:
        assert PIN.is_dir() and (PIN / "run_agent.py").is_file(), "SOURCE_PIN_REQUIRED"
        assert LIBRARIES.is_dir(), "SOURCE_LIBRARIES_REQUIRED"
    if applicability == "historical-installed":
        historical_installed_journey(request, tmp_path)
        return
    # Use the exact pinned interpreter spelling: a worktree .venv alias changes
    # sys.prefix/import paths and is correctly outside the native audit roots.
    python = Path("/home/kali/OmnisAI/api/.venv/bin/python")
    assert python.is_file(), "PINNED_PYTHON_REQUIRED"
    url = request.getfixturevalue("migrated_database_url")
    dsn = url.render_as_string(hide_password=False)
    if (
        applicability is not None
        and not h03
        and applicability
        not in {
            "mission-consumer",
            "result-qualification",
        }
    ):
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

    h03_state: dict[str, bool] = {
        "docker_unknown": False,
        "reader_unknown": False,
        "cleanup_failed": False,
    }

    async def restarted_cli(
        operation: str, back_request: dict[str, object], *, reason: str | None = None
    ) -> dict[str, object]:
        path = tmp_path / ("restart-request-" + uuid4().hex + ".json")
        path.write_bytes(canonical(back_request))
        path.chmod(0o600)
        audit = tmp_path / ("restart-observer-" + uuid4().hex + ".jsonl")
        audit.touch(mode=0o600)
        argv = [
            str(reader_python if h03 else python),
            "-I",
            "-B",
            "-c",
            RESTART_READER,
            "INSTALLED" if h03 else str(ROOT / "api/src"),
            str(audit),
            operation,
            "--request",
            str(path),
            "--catalog-root",
            str(seed.root),
        ]
        if h03:
            prior_unknown = h03_state["reader_unknown"]
            h03_state["reader_unknown"] = True
            db_fence["unsettled"] = True
            output_paths = [audit.with_suffix("." + suffix) for suffix in ("stdout", "stderr")]
            # Exec in the SAME managed family; only redirect private diagnostics.
            redirect = (
                "import os,sys; "
                "fds=[os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600) for p in sys.argv[1:3]]; "
                "os.dup2(fds[0],1); os.dup2(fds[1],2); "
                "[os.close(fd) for fd in fds]; os.execv(sys.argv[3],sys.argv[3:])"
            )
            try:
                reader_exit = await asyncio.to_thread(
                    historical_run_gate,
                    [
                        str(reader_python),
                        "-I",
                        "-B",
                        "-c",
                        redirect,
                        *map(str, output_paths),
                        *argv,
                    ],
                    seed.environment(dsn),
                    audit.with_suffix(".gate.log"),
                    15,
                    cwd=tmp_path,
                )
                # run_gate supplies the strict family receipt, not PID-only credit.
                events = [mapping(json.loads(line)) for line in audit.read_text().splitlines()]
                reader_pid = integer(events[0]["pid"], 1) if events else 0
                if reader_exit not in (0, 2) or events != [
                    {"status": "ORIGIN", "name": "INSTALLED", "pid": reader_pid},
                    {"status": "READY", "name": "managed-cli", "pid": reader_pid},
                    {"status": "EXIT", "name": str(reader_exit), "pid": reader_pid},
                ]:
                    raise AssertionError("H03_READER_FAMILY_OR_EXIT_UNCERTAIN")
                stdout, stderr = (p.read_bytes() for p in output_paths)
                h03_state["reader_unknown"] = prior_unknown
            except BaseException:
                checkpoint(status="UNCERTAIN", h03_reader_cleanup="NOT_SETTLED_DB_RETAINED")
                raise AssertionError("H03_READER_NOT_SETTLED") from None
        else:
            child = await asyncio.create_subprocess_exec(
                *argv,
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
            reader_pid = child.pid
            if child.returncode is None:
                raise AssertionError("RESTART_CLI_NOT_JOINED")
            reader_exit = child.returncode
        # Diagnostic bytes stay private, including if the CLI unexpectedly fails.
        for suffix, raw in (("stdout", stdout), ("stderr", stderr)):
            output = audit.with_suffix("." + suffix)
            output.write_bytes(raw)
            output.chmod(0o600)
        events = [json.loads(line) for line in audit.read_text().splitlines()]
        expected_exit = 0 if reason is None else 2
        if events != [
            *([{"status": "ORIGIN", "name": "INSTALLED", "pid": reader_pid}] if h03 else []),
            {"status": "READY", "name": "managed-cli", "pid": reader_pid},
            {"status": "EXIT", "name": str(expected_exit), "pid": reader_pid},
        ]:
            raise AssertionError("RESTART_EXECUTION_OR_OBSERVER_FAILURE")
        assert reader_pid != os.getpid()
        assert reader_exit == expected_exit, "RESTART_CLI_FAILED"
        if reason is None:
            require_empty_stderr(stderr)
        else:
            assert historical_cli_result(expected_exit, stdout, stderr) == {
                "status": "BLOCKED",
                "reason": reason,
            }
        checkpoint(
            restart_processes=[
                *sequence(proof.get("restart_processes", [])),
                {
                    "operation": operation,
                    "pid": reader_pid,
                    "exit": reader_exit,
                    "execution_attempts": 0,
                },
            ]
        )
        return historical_cli_result(expected_exit, stdout, stderr)

    async def run() -> None:
        from omnis.supervisor.native_tasks import control_task
        from omnis.transport.local_control import LocalControl

        engine = database_engine(dsn)
        service, supervisor = InstanceService(engine), uuid4()
        domain, inputs = ManagedAdmission(engine, seed.root), ContractInputs(engine, seed.root)
        runtime: PreparationPrerequisite | None = None
        host: RuntimeHost | None = None
        done = asyncio.Event()
        heartbeat: asyncio.Task[None] | None = None
        public_control: LocalControl | None = None
        dispatch_waiters: list[asyncio.Task[dict[str, object]]] = []
        cid = ""
        nonce = uuid4().hex
        host_pid = 0
        process_receipts: list[dict[str, object]] = []
        h03_deadline = time.monotonic() + 240

        daemon_id = ""
        image_config: dict[str, object] = {}

        async def docker(*args: str, expected_exit: int = 0) -> bytes:
            # A joined CLI/absence cannot settle an earlier unknown daemon request.
            mutation = args[0] in {"create", "start", "stop", "rm"}
            prior_unknown = h03_state["docker_unknown"]
            if mutation:
                h03_state["docker_unknown"] = True
                db_fence["unsettled"] = True
            label = "h03-docker-" + uuid4().hex
            try:
                if args[0] != "info" and daemon_id:
                    if (await docker("info", "--format={{.ID}}")).decode().strip() != daemon_id:
                        raise AssertionError("H03_DAEMON_IDENTITY_REFUSED")
                child = await asyncio.create_subprocess_exec(
                    "docker",
                    *args,
                    cwd=tmp_path,
                    env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    umask=0o077,
                )
                stdout = stderr = b""
                try:
                    async with asyncio.timeout(min(20, max(0.01, h03_deadline - time.monotonic()))):
                        stdout, stderr = await child.communicate()
                finally:
                    if child.returncode is None:
                        child.kill()
                        await asyncio.wait_for(child.wait(), 5)
                    for suffix, raw in (("stdout", stdout), ("stderr", stderr)):
                        path = tmp_path / (label + "." + suffix)
                        path.write_bytes(raw)
                        path.chmod(0o600)
                if child.returncode != expected_exit:
                    raise AssertionError("H03_DOCKER_OPERATION_UNCERTAIN")
                if expected_exit == 0:
                    require_empty_stderr(stderr)
                elif stderr != ("Error: No such object: " + cid + "\n").encode():
                    raise AssertionError("H03_CONTAINER_ABSENCE_UNCERTAIN")
                if mutation and (
                    re.fullmatch(rb"[a-f0-9]{64}\n", stdout) is None
                    or (args[0] != "create" and stdout != (cid + "\n").encode())
                ):
                    raise AssertionError("H03_DOCKER_ACK_UNCERTAIN")
                if args[0] != "info" and daemon_id:
                    if (await docker("info", "--format={{.ID}}")).decode().strip() != daemon_id:
                        raise AssertionError("H03_DAEMON_IDENTITY_REFUSED")
                checkpoint(
                    h03_last_docker={
                        "operation": args[0],
                        "pid": child.pid,
                        "exit": child.returncode,
                    }
                )
                if mutation:
                    h03_state["docker_unknown"] = prior_unknown
                return stdout
            except BaseException:
                h03_state["docker_unknown"] = True
                db_fence["unsettled"] = True
                checkpoint(status="UNCERTAIN", h03_docker_effect="NOT_SETTLED")
                raise

        async def inspect_owned(*, full: bool = False) -> dict[str, object]:
            rows = sequence(json.loads(await docker("inspect", cid)))
            if len(rows) != 1:
                raise AssertionError("H03_CONTAINER_OWNERSHIP_REFUSED")
            created = mapping(rows[0])
            config, containment = mapping(created["Config"]), mapping(created["HostConfig"])
            if (
                created["Id"] != cid
                or created["Image"] != h03_plan["image_id"]
                or created["Name"] != "/omnis-h03-" + nonce
                or mapping(config["Labels"]).get("org.omnis.h03.owner") != nonce
            ):
                raise AssertionError("H03_CONTAINER_OWNERSHIP_REFUSED")
            if full:
                h03_container_argv(str(h03_plan["image_id"]), nonce, directory, state_dir)
                mounts = [mapping(row) for row in sequence(created["Mounts"])]
                expected = {(str(directory), "/runtime"), (str(state_dir), "/state")}
                if (
                    config["Cmd"] != h03_plan["stock_cmd"]
                    or config["Entrypoint"] not in (None, [])
                    or config["User"] != str(os.getuid()) + ":" + str(os.getgid())
                    or config["Env"] != image_config["Env"]
                    or config["Volumes"] not in (None, {})
                    or containment["ReadonlyRootfs"] is not True
                    or containment["NetworkMode"] != "none"
                    or containment["PidMode"] != ""
                    or containment["Privileged"] is not False
                    or containment["CapDrop"] != ["ALL"]
                    or containment["CapAdd"] not in (None, [])
                    or containment["SecurityOpt"]
                    not in (["no-new-privileges"], ["no-new-privileges:true"])
                    or type(containment["PidsLimit"]) is not int
                    or containment["PidsLimit"] != 64
                    or type(containment["Memory"]) is not int
                    or containment["Memory"] != 805306368
                    or type(containment["NanoCpus"]) is not int
                    or containment["NanoCpus"] != 1000000000
                    or containment["Tmpfs"] != {"/tmp": "rw,noexec,nosuid,nodev,size=32m,mode=1777"}
                    or containment["PortBindings"] not in (None, {})
                    or containment["Devices"] not in (None, [])
                    or containment["VolumesFrom"] not in (None, [])
                    or containment["IpcMode"] != "private"
                    or containment["UTSMode"] != ""
                    or containment["UsernsMode"] != ""
                    or containment["CgroupnsMode"] != "private"
                    or len(mounts) != 2
                    or {(m["Source"], m["Destination"]) for m in mounts} != expected
                    or any(
                        m["Type"] != "bind"
                        or m["RW"] is not True
                        or m["Mode"] != ""
                        or m["Propagation"] != "rprivate"
                        for m in mounts
                    )
                ):
                    raise AssertionError("H03_CONTAINER_CONTAINMENT_REFUSED")
            return created

        async def recover_cid() -> None:
            nonlocal cid
            path = state_dir.parent / ("h03-" + nonce + ".cid")
            if os.path.lexists(path):
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    info = os.fstat(fd)
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or stat.S_IMODE(info.st_mode) != 0o600
                        or info.st_uid != os.getuid()
                        or info.st_nlink != 1
                    ):
                        raise AssertionError("H03_CIDFILE_OWNERSHIP_REFUSED")
                    raw = os.read(fd, 66)
                    if re.fullmatch(rb"[a-f0-9]{64}\n?", raw) is None:
                        raise AssertionError("H03_CIDFILE_CONTENT_REFUSED")
                    cid = raw.decode().strip()
                finally:
                    os.close(fd)
            else:
                # Registered exact name is a locator, not ownership authority.
                rows = sequence(json.loads(await docker("inspect", "omnis-h03-" + nonce)))
                if len(rows) != 1:
                    raise AssertionError("H03_CREATED_CID_UNCERTAIN")
                value = mapping(rows[0]).get("Id")
                if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
                    raise AssertionError("H03_CREATED_CID_UNCERTAIN")
                cid = value
            checkpoint(h03_cid=cid)
            await inspect_owned()

        def process_identity(pid: int, *, module: str, inner_pid: int | None = None) -> list[int]:
            proc = Path("/proc") / str(pid)
            before = (proc / "stat").read_bytes()
            command = (proc / "cmdline").read_bytes().split(b"\0")
            expected = [b"/opt/hermes/venv/bin/python", b"-I", b"-m", module.encode(), b""]
            if command != expected:
                raise AssertionError("H03_STOCK_PROCESS_ORIGIN_REFUSED")
            fields = before.rsplit(b")", 1)[1].split()
            start = int(fields[19])
            pidns = (proc / "ns/pid").stat().st_ino
            if inner_pid is not None:
                nspid = next(
                    line.split()[1:]
                    for line in (proc / "status").read_text().splitlines()
                    if line.startswith("NSpid:")
                )
                if int(nspid[-1]) != inner_pid:
                    raise AssertionError("H03_HOST_NOT_NAMESPACE_PID1")
            if (proc / "stat").read_bytes().rsplit(b")", 1)[1].split()[19] != fields[19]:
                raise AssertionError("H03_PROCESS_IDENTITY_CHANGED")
            return [pid, start, pidns]

        async def start_host() -> None:
            nonlocal host_pid
            assert cid and runtime is not None
            if any(os.path.lexists(directory / n) for n in ("runtime.boot", "runtime.sock")):
                raise AssertionError("H03_ENDPOINT_LEFTOVERS_REFUSED")
            await inspect_owned(full=True)
            await docker("start", cid)
            async with asyncio.timeout(10):
                while (
                    not (directory / "runtime.boot").is_file()
                    or not (directory / "runtime.sock").exists()
                ):
                    await asyncio.sleep(0.01)
            info = mapping(sequence(json.loads(await docker("inspect", cid)))[0])
            host_pid = integer(mapping(info["State"])["Pid"], 1)
            process_identity(host_pid, module="omnis_hermes.runtime_host", inner_pid=1)
            # Actual mounted installed bytes, not just the Docker archive.
            for raw in sequence(h03_plan["public_inventory"]):
                row = mapping(raw)
                path = Path("/proc") / str(host_pid) / "root" / str(row["path"])
                if sha(path.read_bytes()) != row["sha256"]:
                    raise AssertionError("H03_LIVE_INSTALLED_BYTES_REFUSED")
            await runtime.connect()

        def native_process_receipt() -> dict[str, object]:
            assert runtime is not None
            host_identity = process_identity(
                host_pid, module="omnis_hermes.runtime_host", inner_pid=1
            )
            children = (
                (Path("/proc") / str(host_pid) / "task" / str(host_pid) / "children")
                .read_text()
                .split()
            )
            if len(children) != 1:
                raise AssertionError("H03_NATIVE_FAMILY_UNOBSERVED")
            native_identity = process_identity(int(children[0]), module="tui_gateway.entry")
            receipt: dict[str, object] = {
                "boot": runtime.boot,
                "host": host_identity,
                "native": native_identity,
            }
            process_receipts.append(receipt)
            checkpoint(h03_processes=process_receipts)
            return receipt

        async def retire_host() -> None:
            assert runtime is not None and cid
            current = await inspect_owned()
            state = mapping(current["State"])
            if state["Running"] is True:
                try:
                    if runtime.writer is None:
                        await asyncio.wait_for(runtime.connect(), 5)
                    if not await asyncio.wait_for(runtime.drain(), 5):
                        raise AssertionError("H03_NATIVE_DRAIN_UNCERTAIN")
                except BaseException:
                    h03_state["cleanup_failed"] = True
                try:
                    await runtime.close()
                except BaseException:
                    h03_state["cleanup_failed"] = True
                await inspect_owned()
                await docker("stop", "--time=5", cid)
                state = mapping((await inspect_owned())["State"])
            if (
                state["Running"] is not False
                or type(state["ExitCode"]) is not int
                or state["ExitCode"] != 0
            ):
                raise AssertionError("H03_HOST_EXIT_UNCERTAIN")
            if any(os.path.lexists(directory / n) for n in ("runtime.boot", "runtime.sock")):
                raise AssertionError("H03_ENDPOINT_CLEANUP_UNCERTAIN")
            for row in process_receipts:
                for name in ("host", "native"):
                    identity = sequence(row[name])
                    p = Path("/proc") / str(identity[0]) / "stat"
                    if (
                        p.exists()
                        and int(p.read_bytes().rsplit(b")", 1)[1].split()[19]) == identity[1]
                    ):
                        raise AssertionError("H03_OLD_PROCESS_STILL_LIVE")
            import fcntl

            with (directory / "runtime.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock, fcntl.LOCK_UN)
            if h03_state["docker_unknown"] or h03_state["cleanup_failed"]:
                raise AssertionError("H03_RETIREMENT_NOT_SETTLED")
            checkpoint(h03_last_retirement="HOST_EXIT0_NATIVE_DRAIN_ENDPOINTS_ABSENT_LOCK_FREE")

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
            if h03:
                state_dir = tmp_path / "h03-state"
                state_dir.mkdir(mode=0o700)
                for name in (
                    "work",
                    "os-home",
                    "active",
                    "codex",
                    "tmp",
                    "managed-empty",
                    "xdg/config",
                    "xdg/cache",
                    "xdg/state",
                    "xdg/data",
                ):
                    (state_dir / name).mkdir(mode=0o700, parents=True, exist_ok=True)
                daemon_id = (await docker("info", "--format={{.ID}}")).decode().strip()
                if re.fullmatch(r"[A-Za-z0-9:-]{8,128}", daemon_id) is None:
                    raise AssertionError("H03_DAEMON_IDENTITY_REFUSED")
                image_rows = sequence(
                    json.loads(await docker("image", "inspect", str(h03_plan["image_id"])))
                )
                if len(image_rows) != 1 or mapping(image_rows[0])["Id"] != h03_plan["image_id"]:
                    raise AssertionError("H03_INSTALLED_IMAGE_ID_REFUSED")
                image_config = mapping(mapping(image_rows[0])["Config"])
                if (
                    image_config["Cmd"] != h03_plan["stock_cmd"]
                    or image_config["Entrypoint"] not in (None, [])
                    or image_config["Volumes"] not in (None, {})
                ):
                    raise AssertionError("H03_INSTALLED_IMAGE_CONFIGURATION_REFUSED")
                db_fence["unsettled"] = True
                checkpoint(
                    h03_scope="SOURCE_ORIGINAL_OWNER_INSTALLED_HOST_NATIVE_NOT_STOCK_SUPERVISOR_RECOVERY",
                    h03_nonce=nonce,
                    h03_state=str(state_dir),
                    h03_runtime=str(directory),
                    h03_name="omnis-h03-" + nonce,
                    h03_cidfile=str(state_dir.parent / ("h03-" + nonce + ".cid")),
                    h03_daemon=daemon_id,
                    h03_inverse="Attest registered exact CID/name; drain if ready, stop/rm exact owned CID. Retain unknown effects, state/logs/image.",
                )
                try:
                    cid_raw = await docker(
                        *h03_container_argv(str(h03_plan["image_id"]), nonce, directory, state_dir)[
                            1:
                        ]
                    )
                finally:
                    await recover_cid()
                if cid_raw != (cid + "\n").encode():
                    h03_state["docker_unknown"] = True
                    raise AssertionError("H03_CREATED_CID_UNCERTAIN")
                await inspect_owned(full=True)
                await start_host()
            else:
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
                runtime.boot = host.boot
            # Preparation double only; Host/native stock launch is never replaced.
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
                assert host is not None
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
                            "bootstrap": launch_bootstrap_checkpoint(observation),
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

            if (
                h03
                or applicability in {"mission-consumer", "result-qualification"}
                or (
                    applicability is not None
                    and applicability.startswith(("evidence-", "partial-requirement-"))
                )
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

            if h03:
                release_observer = H03ExchangeObservation(
                    runtime._exchange,
                    lambda diagnostic: checkpoint(h03_release_exchange=diagnostic),
                )
                monkeypatch.setattr(runtime, "_exchange", release_observer.exchange)

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

            async def h03_restart_readers(
                back_request: dict[str, object], back: dict[str, object]
            ) -> None:
                assert h03 and runtime is not None and public_control is not None
                negative = applicability == "runtime-restart-no-final"
                original_boot = runtime.boot
                before_census = await mission_census()
                before_markers = await markers()
                if negative:
                    assert back["release_started"] is True
                    assert back["results"] == back["checks"] == back["inbox"] == []
                    assert not any(
                        mapping(row)["kind"] == "native-task-receipt"
                        for row in sequence(back["records"])
                    )
                else:
                    assert len(sequence(back["results"])) == len(sequence(back["checks"])) == 1
                    assert before_markers["consumed"] == 0
                checkpoint(
                    h03_durable_before_restart=sha(canonical(back)),
                    h03_census_before_restart=sha(before_census),
                    h03_original_boot=original_boot,
                )
                # Host resource Stop is not Instance SHUTDOWN: the same owner
                # and epoch remain live for separately authorized fresh startup.
                await retire_host()
                await start_host()
                fresh = await runtime.launch_inert(service, supervisor)
                if fresh["state"] != "READY":
                    raise AssertionError("H03_NEW_NATIVE_NOT_READY")
                await runtime.renew(service, supervisor)
                replacement = native_process_receipt()
                h03_replaced_processes(process_receipts[0], replacement)
                assert runtime.boot != original_boot
                if not await runtime.drain():
                    raise AssertionError("H03_REPLACEMENT_NATIVE_DRAIN_UNCERTAIN")
                # No staged task exists in the replacement boot. Join it before
                # historical readers; original binding/manifest are untouched.
                # Retire the settled IPC stream before cold offline readers;
                # final retirement reconnects for its own Stop/status readback.
                await runtime.close()
                if await mission_census() != before_census:
                    raise AssertionError("H03_RESTART_CHANGED_DOMAIN_CENSUS")
                attempts: list[str] = []

                def deny(*args: object, **kwargs: object) -> object:
                    attempts.append("FORBIDDEN_EXECUTION")
                    checkpoint(h03_execution_attempts=attempts)
                    raise AssertionError("H03_HISTORICAL_READER_ATTEMPTED_EXECUTION")

                with monkeypatch.context() as receive_only:
                    for name in ("skill_catalog", "candidate_catalog"):
                        mod = importlib.import_module("omnis.modules.settings." + name)
                        defining = importlib.import_module(mod.evaluate_pure.__module__)
                        receive_only.setattr(defining, "evaluate_pure", deny)
                        receive_only.setattr(mod, "evaluate_pure", deny)
                    receive_only.setattr("omnis.modules.runs.pure_probe.evaluate_pure", deny)
                    receive_only.setattr("omnis.modules.tasks.module_registry.run_handler", deny)
                    receive_only.setattr(BuildSource, "build", deny)
                    receive_only.setattr(ManagedAdmission, "_build", deny)
                    receive_only.setattr(domain, "ingest_result", deny)
                    receive_only.setattr(domain, "reserve_dispatch", deny)
                    receive_only.setattr(service, "runtime_authority", deny)
                    for name in ("_exchange", "launch_inert", "renew", "managed", "receive"):
                        receive_only.setattr(runtime, name, deny)
                    if negative:
                        with pytest.raises(CatalogError, match="^TASK_INDETERMINATE$"):
                            await submit_task("receive", phase="AFTER_PROCESS_RESTART")
                        assert canonical(
                            await restarted_cli("readback", back_request)
                        ) == canonical(back)
                        await restarted_cli(
                            "reconcile", back_request, reason="NEEDS_RECONCILIATION"
                        )
                        with pytest.raises(CatalogError, match="^NEEDS_RECONCILIATION$"):
                            await domain.reconcile(back_request)
                        assert canonical(await domain.readback(back_request)) == canonical(back)
                        if (
                            await mission_census() != before_census
                            or await markers() != before_markers
                        ):
                            raise AssertionError("H03_PENDING_RESTART_DENIAL_WROTE_STATE")
                        checkpoint(
                            h03_public_denial="TASK_INDETERMINATE",
                            h03_installed_denial="NEEDS_RECONCILIATION",
                            h03_pending_census="UNCHANGED",
                        )
                    else:
                        assert (await submit_task("receive", phase="AFTER_PROCESS_RESTART"))[
                            "task_status"
                        ] == "SUCCEEDED"
                        assert canonical(
                            await restarted_cli("readback", back_request)
                        ) == canonical(back)
                        assert await markers() == before_markers
                        reconciled = await restarted_cli("reconcile", back_request)
                        expected = deepcopy(back)
                        mapping(sequence(expected["inbox"])[0])["domain_result_consumed"] = True
                        assert canonical(reconciled) == canonical(expected)
                        consumed_census = await mission_census()
                        h03_consumed_census(before_census, consumed_census)
                        for operation in ("reconcile", "readback"):
                            assert canonical(
                                await restarted_cli(operation, back_request)
                            ) == canonical(reconciled)
                            if await mission_census() != consumed_census:
                                raise AssertionError("H03_READER_REPLAY_CHANGED_CENSUS")
                        assert (await submit_task("receive", phase="AFTER_CONSUMPTION"))[
                            "task_status"
                        ] == "SUCCEEDED"
                        assert await markers() == {**before_markers, "consumed": 1}
                        checkpoint(
                            h03_single_consumption="EXACT_ONE_BIT_FIVE_TABLE_CENSUS",
                            h03_retained_refs="BYTE_EXACT_GRAPH_FINAL_CHECK_OUTCOMES_USAGE",
                        )
                    assert attempts == []
                done.set()
                assert heartbeat is not None
                await heartbeat
                await service.shutdown(uuid4(), status.generation, supervisor, epoch)
                checkpoint(
                    h03_execution_attempts=attempts,
                    h03_process_restart="READERS_COMPLETE_CLEANUP_PENDING",
                    status="H03_CLEANUP_PENDING",
                    h03_native_census="AUTHENTIC_RECEIPTS_NOT_IN_PROCESS_OBSERVER",
                )

            async with host if host is not None else nullcontext():
                await service.heartbeat(supervisor, epoch)
                if runtime.writer is None:
                    await runtime.connect()
                try:
                    ready = await runtime.launch_inert(service, supervisor)
                except BaseException as error:
                    checkpoint(
                        launch_client_exceptions=launch_exception_chain(error),
                        bootstrap_observation=launch_bootstrap_checkpoint(observation),
                    )
                    raise
                assert ready["state"] == "READY"
                await runtime.renew(service, supervisor)
                if h03:
                    native_process_receipt()
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
                    if applicability == "runtime-restart-no-final":
                        checkpoint(
                            h03_final_cut="AUTHENTIC_RESPONSE_BEFORE_DOMAIN_PERSIST",
                            h03_unpersisted_final_sha256=sha(canonical(final)),
                        )
                        raise CatalogError("TASK_INDETERMINATE")
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
                    if applicability == "runtime-restart-no-final":
                        pause.setattr(domain, "ingest_result", stop_before_first_persist)
                        with pytest.raises(CatalogError, match="^TASK_INDETERMINATE$"):
                            await submit_task("release")
                        assert seam_calls == 1
                        negative_request = seed.request(command_id=assignment["command_id"])
                        negative_back = await domain.readback(negative_request)
                        await h03_restart_readers(negative_request, negative_back)
                        return
                    if lost_reply:
                        assert host is not None
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
                if h03:
                    await h03_restart_readers(back_request, back)
                    return
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
            assert host is not None
            assert host.process is not None and host.process.returncode is not None
            assert not host._owned_pids()
            native_before = observation.read_bytes()
            if applicability == "result-qualification":
                from omnis.modules.settings import candidate_store as stored
                from omnis.modules.tasks import managed_store

                qualification_history = deepcopy(back)
                mission = next(
                    mapping(r) for r in sequence(back["records"]) if mapping(r)["kind"] == "mission"
                )
                # Only prerequisites: one M2 append and denominator create, no
                # replay/denial/overlap relaunch of their accepted consumers.
                appended = await inputs.append_mission(
                    seed.write(
                        schema_version=1,
                        context_ref=context["context_ref"],
                        mission_ref=stored.reference(mission),
                        criterion_id=str(uuid4()),
                    )
                )
                denominator_created = await inputs.create_denominator(
                    seed.write(
                        schema_version=1,
                        context_ref=context["context_ref"],
                        mission_ref=appended["mission_ref"],
                        input_ref=original["input_ref"],
                    )
                )
                qualification_request = seed.write(
                    schema_version=1,
                    context_ref=context["context_ref"],
                    result_ref=stored.reference(mapping(sequence(back["results"])[0])),
                    assignment_ref=stored.reference(mapping(sequence(back["briefs"])[0])),
                    mission_ref=appended["mission_ref"],
                    denominator_ref=denominator_created["denominator_ref"],
                )

                async def qualification_cli(
                    operation: str, value: dict[str, object], reason: str | None = None
                ) -> dict[str, object]:
                    path = tmp_path / ("qualification-command-" + uuid4().hex + ".json")
                    path.write_bytes(canonical(value))
                    path.chmod(0o600)
                    child = await asyncio.create_subprocess_exec(
                        str(python),
                        "-I",
                        "-B",
                        "-c",
                        "import sys;sys.path.insert(0,sys.argv[1]);"
                        "from omnis.modules.runs.contract_inputs import main;"
                        "from omnis.modules.runs.managed_admission import BuildSource,ManagedAdmission;"
                        "from omnis.modules.settings import skill_catalog,candidate_catalog;"
                        "from omnis.modules.tasks import module_registry;"
                        "from omnis.modules.settings.catalog_models import CatalogError;"
                        "blocked=lambda *a,**k:(_ for _ in ()).throw(CatalogError('QUALIFICATION_EXECUTED'));"
                        "BuildSource.build=blocked;ManagedAdmission._build=blocked;"
                        "skill_catalog.compile_catalog=blocked;skill_catalog.evaluate_pure=blocked;"
                        "candidate_catalog.evaluate_pure=blocked;module_registry.run_handler=blocked;"
                        "raise SystemExit(main(sys.argv[2:]))",
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
                        if (child.returncode, stdout, stderr) != (
                            2,
                            b"",
                            canonical({"status": "BLOCKED", "reason": reason}) + b"\n",
                        ):
                            raise AssertionError("QUALIFICATION_DENIAL_TUPLE_MISMATCH")
                        return {}
                    if child.returncode != 0:
                        raise AssertionError("QUALIFICATION_COMMAND_FAILED")
                    require_empty_stderr(stderr)
                    return mapping(json.loads(stdout))

                qualification_before_census = await mission_census()

                async def fail_qualification_receipt(*args: object, **kwargs: object) -> None:
                    raise CatalogError("TEST_RECEIPT_ROLLBACK")

                with monkeypatch.context() as rollback:
                    rollback.setattr(managed_store, "command_complete", fail_qualification_receipt)
                    with pytest.raises(CatalogError, match="^TEST_RECEIPT_ROLLBACK$"):
                        await inputs.create_qualification(qualification_request)
                if await mission_census() != qualification_before_census:
                    raise AssertionError("QUALIFICATION_ROLLBACK_CENSUS_CHANGED")
                with monkeypatch.context() as no_effects:
                    no_effects.setattr(BuildSource, "build", no_rerun)
                    no_effects.setattr("omnis.modules.tasks.module_registry.run_handler", no_rerun)
                    no_effects.setattr(
                        "omnis.modules.settings.skill_catalog.evaluate_pure", no_rerun
                    )
                    created = await qualification_cli("create-qualification", qualification_request)
                    assert created["created"] is True
                    read_request = {
                        k: qualification_request[k]
                        for k in ("schema_version", "owner_id", "command_id")
                    }
                    read = await qualification_cli("read-qualification", read_request)
                    qualification = mapping(read["qualification"])
                    q = mapping(qualification["payload"])
                    assert (
                        q["denominator_revision"] == 1
                        and mapping(q["evaluated_against_mission_ref"])["revision"] == 2
                    )
                    assert (
                        q["precondition_state_refs"] == []
                        and q["decision"] == "REVALIDATION_REQUIRED"
                    )
                    assert q["reason_codes"] == [
                        "COMPATIBILITY_PROOF_UNAVAILABLE",
                        "CURRENT_PRECONDITION_PROOF_UNAVAILABLE",
                    ]
                    evidence = mapping(read["evidence_manifest"])
                    assert q["evidence_manifest_ref"] == stored.reference(evidence)
                    assert len(sequence(mapping(evidence["payload"])["receipt_refs"])) == 3
                    assert len(sequence(mapping(evidence["payload"])["artifacts"])) == 2
                    after = await mission_census()
                    assert await qualification_cli(
                        "create-qualification", qualification_request
                    ) == {**created, "created": False}
                    if await mission_census() != after:
                        raise AssertionError("QUALIFICATION_REPLAY_CENSUS_CHANGED")
                    for operation, qualification_bad, reason in (
                        (
                            "create-qualification",
                            {**qualification_request, "owner_id": str(uuid4())},
                            "REF_UNAVAILABLE",
                        ),
                        (
                            "create-qualification",
                            {
                                **qualification_request,
                                "result_ref": {
                                    **mapping(qualification_request["result_ref"]),
                                    "digest": "0" * 64,
                                },
                            },
                            "REF_MISMATCH",
                        ),
                        (
                            "create-qualification",
                            {
                                **qualification_request,
                                "result_ref": {
                                    **mapping(qualification_request["result_ref"]),
                                    "revision": True,
                                },
                            },
                            "INVALID_REQUEST",
                        ),
                        (
                            "create-qualification",
                            {**qualification_request, "result_ref": appended["mission_ref"]},
                            "MANAGED_REJECTED",
                        ),
                        (
                            "create-qualification",
                            {**qualification_request, "mission_ref": stored.reference(mission)},
                            "COMMAND_CONFLICT",
                        ),
                        (
                            "create-qualification",
                            {**qualification_request, "decision": "ELIGIBLE"},
                            "MANAGED_REJECTED",
                        ),
                        (
                            "create-qualification",
                            {**qualification_request, "denominator_revision": 2},
                            "MANAGED_REJECTED",
                        ),
                        ("read-denominator", read_request, "COMMAND_CONFLICT"),
                    ):
                        await qualification_cli(operation, qualification_bad, reason)
                        if await mission_census() != after:
                            raise AssertionError("QUALIFICATION_DENIAL_CENSUS_CHANGED")
                    # Prepared only: same settled native fixture/common reader,
                    # transaction-local durable mutations, always rolled back.
                    qualification_run = str(prepared["run_id"])
                    authentic_graph = [
                        mapping(r)
                        for r in sequence((await domain.readback(back_request))["records"])
                    ]
                    for table, field in (
                        ("managed_task", "attempt_id"),
                        ("managed_task", "runtime_boot"),
                        ("managed_task", "native_child_id"),
                        ("managed_task", "native_session_id"),
                        ("managed_run", "runtime_boot"),
                        ("managed_run", "ticket"),
                        ("managed_run", "native_root_id"),
                    ):
                        async with engine.connect() as conn:
                            transaction = await conn.begin()
                            try:
                                await managed_store.lock(conn, seed.owner)
                                await conn.execute(
                                    sql(
                                        f"UPDATE public.{table} SET {field}=:value WHERE run_id=:run"
                                    ),
                                    {"value": str(uuid4()), "run": qualification_run},
                                )
                                tampered = await mission_snapshot(conn)
                                with pytest.raises(CatalogError, match="^METHOD_RECEIPT_MISMATCH$"):
                                    await domain._verify_graph(
                                        conn, seed.owner, qualification_run, authentic_graph
                                    )
                                if await mission_snapshot(conn) != tampered:
                                    raise AssertionError("QUALIFICATION_LINEAGE_DENIAL_WROTE")
                            finally:
                                await transaction.rollback()
                        if await mission_census() != after:
                            raise AssertionError("QUALIFICATION_LINEAGE_ROLLBACK_CHANGED")
                    # Available semantic material must refuse before any catalog
                    # access. Observers delegate the positive, not always-deny.
                    from sqlalchemy import event

                    lookup_attempts: list[str] = []
                    original_get = stored.get

                    async def observed_get(
                        connection: AsyncConnection, owner: str, reference: dict[str, object]
                    ) -> tuple[str, dict[str, object]]:
                        lookup_attempts.append("catalog.get")
                        return await original_get(connection, owner, reference)

                    def observed_sql(
                        connection: object,
                        cursor: object,
                        statement: str,
                        parameters: object,
                        context: object,
                        executemany: bool,
                    ) -> None:
                        if "catalog_reservation" in statement:
                            lookup_attempts.append("catalog.identity")

                    def sealed(
                        item: dict[str, object], body: dict[str, object]
                    ) -> dict[str, object]:
                        updated = {**item, "payload": body}
                        updated["digest"] = sha(
                            canonical({k: v for k, v in updated.items() if k != "digest"})
                        )
                        return updated

                    with monkeypatch.context() as local_guard:
                        async with engine.begin() as conn:
                            await managed_store.lock(conn, seed.owner)
                            local_guard.setattr(stored, "get", observed_get)
                            event.listen(
                                conn.sync_connection, "before_cursor_execute", observed_sql
                            )
                            try:
                                await domain._verify_graph(
                                    conn, seed.owner, qualification_run, authentic_graph
                                )
                                assert (
                                    "catalog.get" in lookup_attempts
                                    and "catalog.identity" in lookup_attempts
                                )
                                for attack, reason in (
                                    ("manifest-schema", "QUALIFICATION_INVALID"),
                                    ("receipt-digest", "COMMAND_CONFLICT"),
                                ):
                                    graph = deepcopy(authentic_graph)
                                    replacements: dict[bytes, dict[str, object]] = {}
                                    for kind in (
                                        "result-evidence-manifest",
                                        "result-qualification",
                                        "contract-input-command",
                                    ):
                                        for index, item in enumerate(graph):
                                            if item["kind"] != kind:
                                                continue
                                            body = mapping(item["payload"])
                                            if (
                                                attack == "manifest-schema"
                                                and item["kind"] == "result-evidence-manifest"
                                            ):
                                                artifacts = [
                                                    mapping(a) for a in sequence(body["artifacts"])
                                                ]
                                                artifacts[0]["schema_ref"] = {
                                                    **mapping(artifacts[0]["schema_ref"]),
                                                    "id": str(uuid4()),
                                                }
                                                body["artifacts"] = artifacts
                                                updated = sealed(item, body)
                                                replacements[canonical(stored.reference(item))] = (
                                                    stored.reference(updated)
                                                )
                                                graph[index] = updated
                                            elif (
                                                item["kind"] == "result-qualification"
                                                and attack == "manifest-schema"
                                            ):
                                                body["evidence_manifest_ref"] = replacements[
                                                    canonical(body["evidence_manifest_ref"])
                                                ]
                                                updated = sealed(item, body)
                                                replacements[canonical(stored.reference(item))] = (
                                                    stored.reference(updated)
                                                )
                                                graph[index] = updated
                                            elif (
                                                item["kind"] == "contract-input-command"
                                                and body.get("command_id")
                                                == qualification_request["command_id"]
                                            ):
                                                if attack == "receipt-digest":
                                                    body["request_digest"] = "0" * 64
                                                else:
                                                    body["result_refs"] = {
                                                        k: replacements.get(canonical(v), v)
                                                        for k, v in mapping(
                                                            body["result_refs"]
                                                        ).items()
                                                    }
                                                graph[index] = sealed(item, body)
                                    lookup_attempts.clear()
                                    with pytest.raises(CatalogError, match="^" + reason + "$"):
                                        await domain._verify_graph(
                                            conn, seed.owner, qualification_run, graph
                                        )
                                    assert lookup_attempts == []
                            finally:
                                event.remove(
                                    conn.sync_connection, "before_cursor_execute", observed_sql
                                )
                    if await mission_census() != after:
                        raise AssertionError("QUALIFICATION_LOCAL_DENIAL_CENSUS_CHANGED")
                    await qualification_cli("read-qualification", read_request)
                    back = await domain.readback(back_request)
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
                        assert canonical(back[field]) == canonical(qualification_history[field])
                    assert observation.read_bytes() == native_before and execution_attempts == []
                durable_markers = await markers()
                durable_census = await mission_census()
                checkpoint(
                    result_qualification="CREATE_READ_REPLAY_EIGHT_DENIALS",
                    qualification_ref=stored.reference(qualification),
                    evidence_manifest_ref=stored.reference(evidence),
                    qualification_decision="REVALIDATION_REQUIRED",
                    qualification_denominator_revision=1,
                    qualification_mission_revision=2,
                    qualification_census="FIVE_TABLE_ROLLBACK_REPLAY_DENIALS_EXACT",
                )
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
                denominator_request = seed.write(
                    schema_version=1,
                    context_ref=context["context_ref"],
                    mission_ref=stored.reference(m2),
                    input_ref=original["input_ref"],
                )
                denominator_census = await mission_census()
                with monkeypatch.context() as rollback:
                    rollback.setattr(managed_store, "command_complete", fail_receipt)
                    with pytest.raises(CatalogError, match="TEST_RECEIPT_ROLLBACK"):
                        await inputs.create_denominator(denominator_request)
                if await mission_census() != denominator_census:
                    raise AssertionError("DENOMINATOR_RECEIPT_ROLLBACK_CENSUS_CHANGED")
                denominator_created = await private_input_cli(
                    "create-denominator", denominator_request
                )
                assert denominator_created["created"] is True
                denominator_read_request = {
                    k: denominator_request[k] for k in ("schema_version", "owner_id", "command_id")
                }
                denominator_read = await private_input_cli(
                    "read-denominator", denominator_read_request
                )
                denominator_record = mapping(denominator_read["denominator"])
                denominator_body = mapping(denominator_record["payload"])
                assert denominator_record["revision"] == 1
                assert denominator_body["denominator_revision"] == 1
                assert mapping(denominator_body["mission_ref"])["revision"] == 2
                assert denominator_body["universe"] == "DECLARED_CONTRACT_INPUT"
                assert all(
                    denominator_body[k] == "UNKNOWN"
                    for k in ("identity_state", "applicability_state", "precondition_state")
                )
                denominator_after_create = await mission_census()
                assert (await private_input_cli("create-denominator", denominator_request)) == {
                    **denominator_created,
                    "created": False,
                }
                if await mission_census() != denominator_after_create:
                    raise AssertionError("DENOMINATOR_REPLAY_CENSUS_CHANGED")
                duplicate_request = {**denominator_request, "command_id": str(uuid4())}
                assert (await private_input_cli("create-denominator", duplicate_request)) == {
                    **denominator_created,
                    "created": False,
                }
                assert (
                    await private_input_cli(
                        "read-denominator",
                        {
                            k: duplicate_request[k]
                            for k in ("schema_version", "owner_id", "command_id")
                        },
                    )
                )["denominator"] == denominator_record
                denominator_census = await mission_census()
                for operation, bad, reason in (
                    (
                        "create-denominator",
                        {**denominator_request, "owner_id": str(uuid4())},
                        "REF_UNAVAILABLE",
                    ),
                    (
                        "create-denominator",
                        {**denominator_request, "mission_ref": stored.reference(mission)},
                        "COMMAND_CONFLICT",
                    ),
                    (
                        "create-denominator",
                        {
                            **denominator_request,
                            "input_ref": {**mapping(original["input_ref"]), "digest": "0" * 64},
                        },
                        "REF_MISMATCH",
                    ),
                    (
                        "create-denominator",
                        {
                            **denominator_request,
                            "input_ref": {**mapping(original["input_ref"]), "revision": True},
                        },
                        "INVALID_REQUEST",
                    ),
                    (
                        "create-denominator",
                        {**denominator_request, "input_ref": stored.reference(m2)},
                        "MANAGED_REJECTED",
                    ),
                    (
                        "create-denominator",
                        {**denominator_request, "purpose": "ASSESSMENT"},
                        "MANAGED_REJECTED",
                    ),
                    (
                        "create-denominator",
                        {**denominator_request, "denominator_revision": 2},
                        "MANAGED_REJECTED",
                    ),
                    ("read-mission", denominator_read_request, "COMMAND_CONFLICT"),
                ):
                    await private_input_cli(operation, bad, reason=reason)
                    if await mission_census() != denominator_census:
                        raise AssertionError("DENOMINATOR_DENIAL_CENSUS_CHANGED")
                async with engine.begin() as conn:
                    await conn.execute(
                        sql(
                            "CREATE TEMP TABLE managed_record (id uuid,owner_id uuid,run_id uuid,envelope jsonb) ON COMMIT DROP"
                        )
                    )
                    assert (
                        await managed_store.owned(
                            conn, seed.owner, denominator_created["denominator_ref"]
                        )
                    )[1] == denominator_record
                if await mission_census() != denominator_census:
                    raise AssertionError("DENOMINATOR_SHADOW_CENSUS_CHANGED")
                prior_back = back
                back = await domain.readback(back_request)
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
                    assert canonical(back[field]) == canonical(prior_back[field])
                durable_markers = await markers()
                durable_census = await mission_census()
                assert observation.read_bytes() == native_before
                checkpoint(
                    denominator_consumer="CREATE_READ_REPLAY_EIGHT_DENIAL_TUPLES",
                    denominator_revision=1,
                    denominator_mission_revision=2,
                    denominator_census="FIVE_TABLE_ROLLBACK_REPLAY_DENIALS_PUBLIC_SHADOW_EXACT",
                    denominator_unknown="IDENTITY_APPLICABILITY_CURRENT_PRECONDITIONS",
                )
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
        except BaseException:
            if h03:
                h03_state["cleanup_failed"] = True
                db_fence["unsettled"] = True
            raise
        finally:
            cleanup_failed = False
            resource_absent = False
            for waiter in dispatch_waiters:
                if not waiter.done():
                    if h03:
                        cleanup_failed = True
                    waiter.cancel()
            try:
                joined = await asyncio.gather(*dispatch_waiters, return_exceptions=True)
                if any(
                    isinstance(result, BaseException)
                    and not isinstance(result, asyncio.CancelledError)
                    for result in joined
                ):
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True
            done.set()
            try:
                if heartbeat is not None:
                    await heartbeat
            except BaseException:
                cleanup_failed = True
            if h03 and proof.get("h03_name"):
                if not cid:
                    try:
                        await recover_cid()
                    except BaseException:
                        cleanup_failed = True
                if cid:
                    try:
                        await retire_host()
                    except BaseException:
                        cleanup_failed = True
                    try:
                        owned = await inspect_owned()
                        if mapping(owned["State"])["Running"] is True:
                            await docker("stop", "--time=5", cid)
                            owned = await inspect_owned()
                        if mapping(owned["State"])["Running"] is not False:
                            raise AssertionError("H03_HOST_EXIT_UNCERTAIN")
                        await docker("rm", cid)
                        if await docker(
                            "inspect", "--format={{.Id}}", cid, expected_exit=1
                        ) not in (
                            b"",
                            b"\n",
                        ):
                            raise AssertionError("H03_CONTAINER_ABSENCE_UNCERTAIN")
                        resource_absent = True
                    except BaseException:
                        cleanup_failed = True
            try:
                if runtime is not None:
                    await runtime.close()
            except BaseException:
                cleanup_failed = True
            try:
                if public_control is not None:
                    await public_control.__aexit__(None, None, None)
                    assert public_control.lock_fd is None
                    assert not (public_control.directory / "control.sock").exists()
                    assert not (public_control.directory / "control.cap").exists()
                    checkpoint(public_control_cleanup="PASS")
            except BaseException:
                cleanup_failed = True
            try:
                await engine.dispose()
            except BaseException:
                cleanup_failed = True
            if h03:
                h03_state["cleanup_failed"] |= cleanup_failed
                if resource_absent and not any(h03_state.values()):
                    db_fence["unsettled"] = False
                    checkpoint(
                        h03_resource_cleanup="EXACT_CID_ABSENT_ENDPOINTS_ABSENT_PROCESSES_JOINED_STATE_RETAINED"
                    )
                    if proof.get("status") == "H03_CLEANUP_PENDING":
                        checkpoint(
                            status="PASS_SOURCE_OWNER_INSTALLED_HOST_NATIVE_SCOPED",
                            h03_process_restart="PASS_SCOPED_NOT_STOCK_SUPERVISOR_RECOVERY",
                        )
                elif db_fence.get("unsettled"):
                    checkpoint(status="UNCERTAIN", h03_resource_cleanup="NOT_SETTLED_DB_RETAINED")
                    raise AssertionError("H03_CLEANUP_NOT_SETTLED")
            elif cleanup_failed:
                raise AssertionError("NATIVE_CLEANUP_UNCERTAIN")
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
                    bootstrap_observation=launch_bootstrap_checkpoint(observation),
                )
        with observation.open("rb") as stream:
            observation_raw = stream.read(OBSERVATION_BYTES + 1)
        bootstrap_diagnostic = launch_bootstrap_diagnostic(observation_raw)
        assert set(sequence(bootstrap_diagnostic["issues"])) <= {"MISSING_PHASE_COMPLETION"}, (
            "NATIVE_OBSERVATION_INCOMPLETE_OR_UNKNOWN"
        )
        assert bootstrap_diagnostic["pre_ready_complete"] is True, (
            "NATIVE_PRE_READY_EVIDENCE_MISSING"
        )
        rows = [json.loads(line) for line in observation_raw.splitlines()]
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
