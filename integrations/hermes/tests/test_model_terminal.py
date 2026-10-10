"""Pinned function-prefix tests: protocol transport only, NOT SDK/native/live proof."""

import ast
import contextlib
import inspect
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "upstream/managed-source/agent"


def load(name, names, namespace):
    module = ModuleType("omnis_native_prefix")
    module.__dict__.update(namespace)
    tree = ast.parse((SOURCE / name).read_text())
    nodes = [
        n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names
    ]
    assert {n.name for n in nodes} == set(names)
    exec(
        "from __future__ import annotations\n" + "\n".join(ast.unparse(n) for n in nodes),
        module.__dict__,
    )
    return module


@pytest.mark.parametrize("channel", ["sink", "direct", "worker"])
def test_managed_veto_survives_direct_worker_and_cancel(channel, monkeypatch):
    calls = []
    response = object()

    def make_client(*args, **kwargs):
        calls.append("client")
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: calls.append("protocol-transport") or response,
                )
            )
        )

    class Inline:
        def __init__(self, *args):
            self.lock = threading.Lock()
            self.stale = True
            self.abort_hook = object()

        def make_client(self, *args, **kwargs):
            return make_client(*args, **kwargs)

        def start_watchdogs(self):
            pass

        def stop_watchdogs(self):
            pass

        def pop_client(self):
            return None

        def mark_done(self):
            pass

    h = load(
        "chat_completion_helpers.py",
        ["_dispatch_nonstreaming_api_request", "direct_api_call"],
        {
            "bypass_chat_sdk_request_transform": lambda value, client: value,
            "_InlineRequest": Inline,
            "_check_stale_giveup": lambda agent: None,
            "_resolve_direct_stale_timeout": lambda *args: 10,
            "_inline_nonstream_hard_timeout": lambda _: None,
            "_reset_stale_streak": lambda agent: None,
            "time": time,
        },
    )
    h.threading, h.contextlib, h.logger = threading, contextlib, Mock()
    h._context_thread_target = lambda function: function
    cls = load("chat_completion_nonstream.py", ["_NonStreamRequest"], {"h": h})._NonStreamRequest
    agent = SimpleNamespace(
        api_mode="chat_completions",
        provider="SOURCE_PROTOCOL_ONLY",
        _interrupt_requested=False,
        _touch_activity=lambda *args: None,
        _active_request_abort=None,
    )
    kwargs = {"model": "SOURCE_PROTOCOL_ONLY", "messages": [], "stream": False}

    def call():
        if channel == "sink":
            return h._dispatch_nonstreaming_api_request(
                agent, dict(kwargs), make_client=make_client
            )
        if channel == "direct":
            return h.direct_api_call(agent, dict(kwargs))
        request = cls.__new__(cls)
        request.agent, request.api_kwargs = agent, dict(kwargs)
        request.result = {"response": None, "error": None, "terminal": None}
        request.clients = SimpleNamespace(close_once=lambda *_: None)
        request.cancelled, request.codex_retired, request.codex_token = True, False, None
        request.codex_watchdog_state = None
        request.wd = SimpleNamespace(
            codex=False,
            ttfb_enabled=False,
            progress_timeout=0,
            idle_enabled=False,
            stale_timeout=10,
        )
        request.call_start = time.time()
        request._emit_wait_notice = lambda *args, **kwargs: None
        request._make_client = make_client
        try:
            return request.run()
        finally:
            if request.thread is not None:
                request.thread.join(timeout=2)
                assert not request.thread.is_alive(), "source worker did not drain"

    # Valid control on the same function/channel. This stand-in proves protocol
    # routing only; it is deliberately NOT an authorized native model positive.
    monkeypatch.delenv("HERMES_OMNIS_INERT", raising=False)
    assert call() is response
    assert calls == ["client", "protocol-transport"]
    calls.clear()
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    agent._interrupt_requested = True
    error = None
    try:
        call()
    except Exception as caught:
        error = caught
    assert calls == [], "managed request reached client/transport before admission"
    from omnis_hermes.model_terminal import ManagedModelTerminal

    assert isinstance(error, ManagedModelTerminal), "veto lost/reclassified by direct/worker"


def test_retry_owner_returns_terminal_before_rate_guard_or_recovery(monkeypatch):
    calls = []

    def phase(*args, **kwargs):
        calls.append("phase")
        raise AssertionError("managed model entered rate/request/recovery phase")

    loop = load(
        "conversation_loop.py",
        ["_run_api_retry_loop"],
        {
            "_run_phase": phase,
            "nous_rate_limit_guard": object(),
        },
    )
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    result = loop._run_api_retry_loop(
        SimpleNamespace(), SimpleNamespace(retry_count=0, max_retries=3)
    )
    assert calls == []
    assert result["completed"] is False and result["failed"] is True
    assert result["failure_retryable"] is False and result["api_calls"] == 0
    assert result["messages"] == []


def test_recovery_entrypoint_cannot_recover_managed_denial(monkeypatch):
    calls = []

    def recover(*args, **kwargs):
        calls.append("credential-recovery")
        raise AssertionError("managed recovery attempted")

    module = load(
        "turn_api_error.py",
        ["handle_api_error"],
        {
            "ApiErrorVerdict": SimpleNamespace,
            "recover_before_classification": recover,
        },
    )
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    args = {
        name: None
        for name in inspect.signature(module.handle_api_error).parameters
        if name != "agent"
    }
    args["api_error"] = RuntimeError("SYNTHETIC_PRIVATE_ERROR")
    verdict = module.handle_api_error(SimpleNamespace(thinking_callback=None), **args)
    assert calls == [] and verdict.action == "return"
    assert verdict.result["failure_retryable"] is False
    assert "SYNTHETIC_PRIVATE_ERROR" not in str(verdict.result)


@pytest.mark.parametrize(
    "filename,name",
    [
        ("conversation_loop.py", "_run_conversation_turn"),
        ("turn_api_request.py", "build_api_request"),
        ("turn_api_call.py", "perform_api_call"),
        ("chat_completion_helpers.py", "interruptible_streaming_api_call"),
        ("chat_completion_helpers.py", "handle_max_iterations"),
        ("auxiliary_client.py", "_plan_aux_call"),
    ],
)
def test_inert_entrypoints_deny_before_context_hooks_or_aux_resolution(filename, name, monkeypatch):
    import sys

    from omnis_hermes.model_terminal import ManagedModelTerminal

    calls = []

    class ReachedOriginalBody(Exception):
        pass

    def body(*args, **kwargs):
        calls.append("original-body")
        raise ReachedOriginalBody()

    namespace = {
        "_decode_inline_moa_turn": body,
        "_should_stream": body,
        "_check_stale_giveup": body,
        "_normalize_main_runtime": body,
    }
    agent_module = ModuleType("agent")
    conversation = ModuleType("agent.conversation_loop")
    conversation.__dict__.update(
        _moa_client_consumes_prepared_request=body, _redecorate_prompt_cache_for_provider=body
    )
    monkeypatch.setitem(sys.modules, "agent", agent_module)
    monkeypatch.setitem(sys.modules, "agent.conversation_loop", conversation)
    function = load(filename, [name], namespace).__dict__[name]
    args = {key: None for key in inspect.signature(function).parameters}
    if "agent" in args:
        args["agent"] = SimpleNamespace(
            _reset_stream_delivery_tracking=body,
            _interrupt_requested=False,
            api_mode="chat_completions",
            max_iterations=1,
            suppress_status_output=False,
            _safe_print=body,
        )
    monkeypatch.delenv("HERMES_OMNIS_INERT", raising=False)
    with pytest.raises(ReachedOriginalBody):
        function(**args)
    assert calls == ["original-body"]
    calls.clear()
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    if name == "_run_conversation_turn":
        assert function(**args)["failure_retryable"] is False
    else:
        with pytest.raises(ManagedModelTerminal):
            function(**args)
    assert calls == []
