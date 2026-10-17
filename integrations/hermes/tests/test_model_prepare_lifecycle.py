"""Real lifecycle method AST with explicit child/schema doubles; no native imports."""

import ast
import concurrent.futures
import contextlib
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3] / "integrations/hermes/upstream/managed-source"


@pytest.fixture
def lifecycle(monkeypatch):
    def module(name, **values):
        m = ModuleType(name)
        m.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, m)

    children = []
    checks = []
    release = threading.Event()

    class Child:
        def __init__(self, **kwargs):
            self._subagent_id, self.session_id = str(uuid4()), str(uuid4())
            self._model_test_closed, self._model_test_ready = threading.Event(), threading.Event()
            self._model_test_failure = self._model_test_turn = self._model_test_future = None
            children.append(self)

        def close(self):
            self._model_test_closed.set()
            if self._model_test_future is not None:
                self._model_test_future.result(timeout=1)

    def conversation(child, text, task_id):
        child._model_test_turn = {"task_id": task_id, "turn_id": "SOURCE-turn"}
        child._model_test_ready.set()
        assert child._model_test_closed.wait(4), "SOURCE worker fuse"
        assert release.wait(4), "SOURCE finalizer fuse"

    def result(p, **kwargs):
        return {"status": "TURN_BOUND_PRE_CLIENT_HOLD" if kwargs else "UNKNOWN", **kwargs}

    module("agent")
    module("run_agent", AIAgent=Child)
    module("agent.agent_init", observe_model_test=lambda c: None)
    module("agent.cold_admission", configuration_snapshot=lambda p: checks.append(id(p)))
    module("agent.conversation_loop", run_conversation=conversation)
    module(
        "omnis_hermes.managed_admission_contract",
        ModelTestPreparation=lambda b: b,
        canonical=lambda p: json.dumps(p, sort_keys=True).encode(),
        preparation_result=result,
        validate_model_prepare=lambda p: p,
    )
    registry = SimpleNamespace(lock=threading.RLock(), records={})
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mtp-SOURCE")

    class Record:
        def __init__(self, *args, agent):
            self.agent, self.state, self.future = agent, args[1], None

    class Handle:
        def __init__(self, *args):
            self.subagent_id = args[1]

    tree = ast.parse((ROOT / "agent/subagent_lifecycle.py").read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SubagentLifecycleService"
    )
    names = {"prepare_model_test", "close_model_tests"}
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    scope = dict(
        _REGISTRY=registry,
        _EXECUTOR=pool,
        _Record=Record,
        SubagentHandle=Handle,
        SubagentState=SimpleNamespace(
            PENDING="PENDING",
            STARTING="STARTING",
            RUNNING="RUNNING",
            CANCEL_REQUESTED="CANCEL_REQUESTED",
        ),
        time=time,
        contextlib=contextlib,
        PUBLIC_CONTRACT_VERSION=1,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
            str(ROOT / "agent/subagent_lifecycle.py"),
            "exec",
        ),
        scope,
    )
    parent = SimpleNamespace(
        session_id="SOURCE-parent", _subagent_id=str(uuid4()), _parent_session_id=None
    )
    current = [parent]
    service = scope["SubagentLifecycleService"]()
    service._parent_agent_resolver = lambda: current[0]
    service._model_test_batches = {}
    service._capability = lambda *a: "SOURCE-capability"

    def payload():
        return {
            "mode": "CREATE",
            "context": {"payload": {"preparation_id": str(uuid4()), "task_id": str(uuid4())}},
            "records": [{"kind": "prompt-composition", "payload": {"text": "synthetic"}}],
        }

    try:
        yield SimpleNamespace(
            service=service,
            children=children,
            release=release,
            parent=parent,
            current=current,
            registry=registry,
            payload=payload,
            checks=checks,
        )
    finally:
        release.set()
        for child in children:
            child.close()
        pool.shutdown(wait=True, cancel_futures=True)
        assert not any(t.name.startswith("mtp-SOURCE") for t in threading.enumerate())


def test_one_held_or_unjoined_child_blocks_new_identity(lifecycle):
    x = lifecycle
    first = x.payload()
    assert x.service.prepare_model_test(first)["status"] == "TURN_BOUND_PRE_CLIENT_HOLD"
    assert x.children[0]._model_test_future.running()
    assert (
        x.service.prepare_model_test({**first, "mode": "STATUS"})["status"]
        == "TURN_BOUND_PRE_CLIENT_HOLD"
    )
    before = len(x.service._model_test_batches), len(x.registry.records)
    for closed in (False, True):
        if closed:
            x.children[0]._model_test_closed.set()
        with pytest.raises(ValueError, match="active|drain"):
            x.service.prepare_model_test(x.payload())
        assert (len(x.service._model_test_batches), len(x.registry.records)) == before
        assert len(x.children) == 1
    x.release.set()
    x.children[0].close()
    assert x.service.prepare_model_test(x.payload())["status"] == "TURN_BOUND_PRE_CLIENT_HOLD"
    assert len(x.children) == 2


@pytest.mark.parametrize(
    "change", ["resolver", "root-id", "root-session", "child-id", "child-session"]
)
def test_live_replay_requires_original_root_and_pinned_identities(lifecycle, change):
    x = lifecycle
    p = x.payload()
    x.service.prepare_model_test(p)
    child = x.children[0]
    if change == "resolver":
        x.current[0] = SimpleNamespace(**vars(x.parent))
    elif change == "root-id":
        x.parent._subagent_id = str(uuid4())
    elif change == "root-session":
        x.parent.session_id = "changed"
    elif change == "child-id":
        child._subagent_id = str(uuid4())
    else:
        child.session_id = "changed"
    with pytest.raises(ValueError, match="root|identity|parent"):
        x.service.prepare_model_test({**p, "mode": "STATUS"})
    assert len(x.children) == 1


def test_replay_rechecks_cold_configuration(lifecycle):
    x = lifecycle
    p = x.payload()
    x.service.prepare_model_test(p)
    before = len(x.checks)
    assert (
        x.service.prepare_model_test({**p, "mode": "STATUS"})["status"]
        == "TURN_BOUND_PRE_CLIENT_HOLD"
    )
    assert len(x.checks) == before + 1


def test_constructor_cut_closes_unpublished_child_and_preserves_primary(lifecycle):
    x = lifecycle

    class Cut(BaseException):
        pass

    primary = Cut("SOURCE original cut")

    def cut(*args):
        raise primary

    x.service._capability = cut
    with pytest.raises(Cut) as caught:
        x.service.prepare_model_test(x.payload())
    assert caught.value is primary
    assert x.children[0]._model_test_closed.is_set()
    assert x.children[0]._model_test_future is None
    assert next(iter(x.service._model_test_batches.values()))["record"] is None


@pytest.mark.parametrize("exit_path", ["EOF", "Stop"])
def test_native_owner_exit_revokes_and_joins_held_child(lifecycle, monkeypatch, exit_path):
    x = lifecycle
    p = x.payload()
    x.service.prepare_model_test(p)
    child = x.children[0]
    assert child._model_test_future.running()
    x.release.set()
    entry = ROOT / "tui_gateway/entry.py"
    assert entry.is_file(), "Native EOF/Stop entry cleanup is missing"
    tree = ast.parse(entry.read_text())
    helper = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_close_model_test_preparations"
    )
    rpc = ModuleType("agent.managed_admission_rpc")
    rpc.close_preparations = x.service.close_model_tests
    monkeypatch.setitem(sys.modules, rpc.__name__, rpc)
    scope = {"sys": sys}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
            str(entry),
            "exec",
        ),
        scope,
    )
    caller = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name == ("_log_exit" if exit_path == "EOF" else "_log_signal")
    )
    # Exercise the real cleanup prefix, stopping before unrelated stock log/signal effects.
    statement = next(
        n for n in caller.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[statement], type_ignores=[])),
            str(entry),
            "exec",
        ),
        scope,
    )
    assert child._model_test_closed.is_set() and child._model_test_future.done()
    assert x.service.prepare_model_test({**p, "mode": "STATUS"})["status"] == "UNKNOWN"
    with pytest.raises(ValueError, match="stopping"):
        x.service.prepare_model_test(x.payload())
    assert len(x.children) == 1


def test_unsettled_exit_keeps_unknown_and_blocks_new_children(lifecycle):
    x = lifecycle
    p = x.payload()
    x.service.prepare_model_test(p)
    with pytest.raises(ValueError, match="drain uncertain"):
        x.service.close_model_tests()
    child = x.children[0]
    assert child._model_test_closed.is_set() and not child._model_test_future.done()
    assert x.service.prepare_model_test({**p, "mode": "STATUS"})["status"] == "UNKNOWN"
    with pytest.raises(ValueError, match="stopping"):
        x.service.prepare_model_test(x.payload())
    assert len(x.children) == 1


def test_cleanup_does_not_touch_ordinary_cold_service():
    tree = ast.parse((ROOT / "agent/managed_admission_rpc.py").read_text())
    close = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "close_preparations"
    )

    def forbidden():
        pytest.fail("ordinary cold service cleanup changed")

    scope = {
        "_LOCK": threading.RLock(),
        "_SERVICE": SimpleNamespace(_model_test_batches={}, close_model_tests=forbidden),
    }
    exec(compile(ast.Module(body=[close], type_ignores=[]), "SOURCE-native-close", "exec"), scope)
    scope["close_preparations"]()


def test_other_active_native_child_counts_against_prepare_cap(lifecycle):
    x = lifecycle
    x.registry.records["other"] = SimpleNamespace(agent=object(), future=None, state="RUNNING")
    with pytest.raises(ValueError, match="active|drain"):
        x.service.prepare_model_test(x.payload())
    assert not x.children and not x.service._model_test_batches
