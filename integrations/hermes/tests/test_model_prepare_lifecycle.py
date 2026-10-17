"""Real lifecycle method AST with explicit child/schema doubles; no native imports."""

import ast
import asyncio
import concurrent.futures
import contextlib
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from omnis_hermes import managed_admission_contract as contract
from omnis_hermes.runtime_host import RuntimeHost
from omnis_hermes.runtime_protocol import NativePeer, encode

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
            self._model_test_failure = self._model_test_turn = self._model_test_record = None
            children.append(self)

        def close(self):
            self._model_test_closed.set()
            if self._model_test_record is not None and self._model_test_record.future is not None:
                self._model_test_record.future.result(timeout=1)

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
        ref=lambda c: {
            "kind": "model-test-context",
            "id": c["payload"]["preparation_id"],
            "revision": 1,
            "digest": "a" * 64,
        },
    )
    registry = SimpleNamespace(lock=threading.RLock(), records={})
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mtp-SOURCE")

    class Record:
        def __init__(self, *args, agent):
            self.agent, self.state, self.future = agent, args[1], None
            self.model_test_submit_started = False

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
            "protocol": contract.PROTOCOL_V5,
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
    assert x.children[0]._model_test_record.future.running()
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
    assert x.children[0]._model_test_record is None
    assert next(iter(x.service._model_test_batches.values()))["record"] is None


@pytest.mark.parametrize("exit_path", ["EOF", "Stop"])
def test_native_owner_exit_revokes_and_joins_held_child(lifecycle, monkeypatch, exit_path):
    x = lifecycle
    p = x.payload()
    x.service.prepare_model_test(p)
    child = x.children[0]
    assert child._model_test_record.future.running()
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
    assert child._model_test_closed.is_set() and child._model_test_record.future.done()
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
    assert child._model_test_closed.is_set() and not child._model_test_record.future.done()
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


@pytest.mark.parametrize("held", [False, True])
def test_post_submit_cut_owner_joins_single_retained_future(lifecycle, held):
    x = lifecycle
    tree = ast.parse((ROOT / "run_agent.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AIAgent")
    cls.bases = []
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "close"]
    scope = {}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
            "SOURCE-close",
            "exec",
        ),
        scope,
    )

    class Cut(BaseException):
        pass

    primary = Cut("SOURCE post-submit interruption")
    cut = []

    def interrupt(frame, event, arg):
        if event == "line" and frame.f_code is x.service.prepare_model_test.__func__.__code__:
            record = frame.f_locals.get("record")
            if not cut and record is not None and record.future is not None:
                child = record.agent
                child._model_test_preparation = object()
                type(child).close = scope["AIAgent"].close
                cut.append(record)
                raise primary
        return interrupt

    if not held:
        x.release.set()
    sys.settrace(interrupt)
    try:
        with pytest.raises(Cut) as caught:
            x.service.prepare_model_test(x.payload())
    finally:
        sys.settrace(None)
    assert caught.value is primary and cut
    record = cut[0]
    assert record.agent._model_test_closed.is_set()
    if held:
        with pytest.raises(ValueError, match="drain uncertain"):
            x.service.close_model_tests()
        assert not record.future.done()
    else:
        x.service.close_model_tests()
        assert record.future.done(), "product owner must join before test finalizer"


def test_submit_started_without_future_publication_stays_uncertain(lifecycle, monkeypatch):
    x = lifecycle
    scope = x.service.prepare_model_test.__func__.__globals__
    submit = scope["_EXECUTOR"].submit

    class Cut(BaseException):
        pass

    primary = Cut("SOURCE submit returned before publication")

    def interrupted_submit(fn):
        submit(fn)
        raise primary

    monkeypatch.setitem(scope, "_EXECUTOR", SimpleNamespace(submit=interrupted_submit))
    with pytest.raises(Cut) as caught:
        x.service.prepare_model_test(x.payload())
    assert caught.value is primary
    record = next(iter(x.registry.records.values()))
    assert record.model_test_submit_started and record.future is None
    assert record.agent._model_test_closed.is_set()
    with pytest.raises(ValueError, match="active|drain"):
        x.service.prepare_model_test(x.payload())
    with pytest.raises(ValueError, match="drain uncertain"):
        x.service.close_model_tests()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "held", "unknown", "missing-owner"])
async def test_existing_private_rpc_close_returns_only_real_join_evidence(
    lifecycle, monkeypatch, tmp_path, fault
):
    x = lifecycle
    p = x.payload()
    x.service.prepare_model_test(p)
    batch = next(iter(x.service._model_test_batches.values()))
    agent_tree = ast.parse((ROOT / "run_agent.py").read_text())
    agent_class = next(
        n for n in agent_tree.body if isinstance(n, ast.ClassDef) and n.name == "AIAgent"
    )
    close_method = next(
        n for n in agent_class.body if isinstance(n, ast.FunctionDef) and n.name == "close"
    )
    close_scope = {}
    exec(
        compile(ast.Module(body=[close_method], type_ignores=[]), "SOURCE-native-close", "exec"),
        close_scope,
    )
    batch["child"]._model_test_preparation = object()
    type(batch["child"]).close = close_scope["close"]
    close = {"protocol": contract.PROTOCOL_V5, "mode": "CLOSE", "context_ref": batch["context_ref"]}
    if fault == "unknown":
        close["context_ref"] = {**batch["context_ref"], "id": str(uuid4())}
    if fault != "held":
        x.release.set()
    module = sys.modules["omnis_hermes.managed_admission_contract"]
    for name in ("OwnedInitialization", "initialization_result", "validate_initialization"):
        monkeypatch.setattr(module, name, getattr(contract, name), raising=False)
    tree = ast.parse((ROOT / "agent/managed_admission_rpc.py").read_text())
    initialize = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_initialize"
    )
    scope = {
        "_LOCK": threading.RLock(),
        "_SERVICE": None if fault == "missing-owner" else x.service,
        "_ROOT": x.parent,
    }
    exec(
        compile(
            ast.Module(body=[initialize], type_ignores=[]), "SOURCE-private-initialize", "exec"
        ),
        scope,
    )
    host = RuntimeHost(tmp_path)
    host.state, host.namespace_owned = "READY", True
    host.model_preparation_close = contract.canonical(close)
    process = Mock(pid=12345, returncode=None, wait=AsyncMock(return_value=0))
    process.stdout, process.stderr = asyncio.StreamReader(), asyncio.StreamReader()
    process.stderr.feed_eof()
    effects = []

    class Pipe:
        def write(self, raw):
            frame = json.loads(raw)
            assert host.state == "STOPPING" and frame["params"] == close
            assert frame["method"] == contract.RPC["task_model_initialize"]
            effects.append("native-close")
            reply = {"jsonrpc": "2.0", "id": frame["id"]}
            try:
                reply["result"] = scope["_initialize"](frame["params"])
            except ValueError:
                reply["error"] = {"code": -32603, "message": "Native preparation drain uncertain"}
            process.stdout.feed_data(encode(reply))

        async def drain(self):
            pass

        def close(self):
            effects.append("retire")

        async def wait_closed(self):
            pass

    process.stdin = Pipe()
    host.process, host.peer = process, NativePeer(process, timeout=0.8)
    monkeypatch.setattr(host, "_owned_pids", lambda: set())

    def physical_absence(*args):
        if fault is None:
            assert batch["child"]._model_test_closed.is_set() and batch["record"].future.done()
            assert host.model_close_evidence is not None
        else:
            assert host.model_close_uncertain and host.model_close_evidence is None
        effects.append("physical-kill")
        process.returncode = 0

    import os

    monkeypatch.setattr(os, "killpg", physical_absence)
    try:
        await host.stop()
        assert effects == ["native-close", "physical-kill", "retire"]
        assert host.state == ("STOPPED" if fault is None else "UNCERTAIN")
        if fault is None:
            assert host.model_close_evidence is not None
            result = json.loads(host.model_close_evidence)
            assert contract.validate_model_close_result(result, close) == result
            # EOF/signal fallback is idempotent and still observes the same settled Future.
            assert x.service.close_model_tests(batch["context_ref"]) == result
        else:
            await host.stop()
            assert host.state == "UNCERTAIN" and effects.count("native-close") == 1
    finally:
        await host.peer.close()
    assert len(x.children) == 1
