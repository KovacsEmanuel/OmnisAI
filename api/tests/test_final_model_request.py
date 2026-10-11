"""SOURCE schema/sink controls; no authentic turn/config/model grant is fabricated."""

import importlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from omnis.modules.settings.catalog_schema import canonical
from test_model_projection_denials import unit_projection as unit_projection

ROOT = Path(__file__).resolve().parents[2]


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes/src"))
    spec = importlib.util.find_spec("omnis_hermes.model_request")
    assert spec is not None, "complete immutable DTO consumer missing, not only carrier"
    return importlib.import_module("omnis_hermes.model_request")


def fixture_dto(projection):
    """Untrusted parser fixture, never persisted as native-turn/config/SENT or used as grant."""
    body = projection["payload"]

    def pin(kind):
        return {"kind": kind, "id": str(uuid4()), "revision": 1, "digest": "1" * 64}

    return {
        "projection": projection,
        "projection_ref": {k: projection[k] for k in ("kind", "id", "revision", "digest")},
        "owner_id": body["owner_id"],
        "run_id": body["run_id"],
        "binding_ref": body["runtime_binding_ref"],
        "policy_digest": body["policy_digest"],
        "dispatch": {
            "native_turn_ref": pin("native-turn"),
            "provider_config_ref": pin("provider-config"),
            "execution_selection_ref": body["selection_ref"],
            "dispatch_attempt_id": str(uuid4()),
            "model_id": "SYNTHETIC_SCHEMA_ONLY_NOT_EFFECTIVE_CONFIG",
            "fencing_epoch": 1,
            "technical_caps": {"calls": 1, "output_tokens": 64, "wall_seconds": 1},
        },
    }


def test_complete_dto_is_immutable_and_has_distinct_digest_preimages(unit_projection, monkeypatch):
    m = module(monkeypatch)
    raw = canonical(fixture_dto(unit_projection))
    frozen = m.parse_final_request(raw)
    before = frozen.sdk_kwargs()
    before["messages"][0]["content"] = "UNTRUSTED_ALIAS_MUTATION"
    assert frozen.sdk_kwargs()["messages"] == unit_projection["payload"]["model_input"]["messages"]
    assert frozen.raw == raw
    assert frozen.dto_digest != unit_projection["payload"]["projection_digest"]
    assert json.loads(frozen.http_body()) == {
        k: v for k, v in frozen.sdk_kwargs().items() if k != "timeout"
    }
    with pytest.raises(AttributeError):
        frozen.raw = b"{}"


@pytest.mark.parametrize(
    "field", ["extra_body", "extra_headers", "extra_query", "history", "metadata"]
)
def test_final_incoming_extension_refused_even_empty(unit_projection, monkeypatch, field):
    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    kwargs = frozen.sdk_kwargs()
    kwargs[field] = {}
    with pytest.raises(m.ManagedModelTerminal):
        m.consume_final_request(frozen.raw, kwargs)


def test_post_bypass_exact_copies_and_wire_body_guard(unit_projection, monkeypatch):
    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    before = frozen.sdk_kwargs()
    after = deepcopy(before)
    after["extra_body"] = {"messages": after["messages"], "tools": after["tools"]}
    after["messages"], after["tools"] = [], []
    assert m.consume_final_request(frozen.raw, after, post_bypass=True) == after
    after["extra_body"]["model"] = "UNAPPROVED_OVERRIDE"
    with pytest.raises(m.ManagedModelTerminal):
        m.consume_final_request(frozen.raw, after, post_bypass=True)
    assert m.validate_http_body(frozen.raw, frozen.http_body()) == frozen.http_digest
    with pytest.raises(m.ManagedModelTerminal):
        m.validate_http_body(frozen.raw, frozen.http_body() + b" ")


@pytest.mark.parametrize("value", [True, 0, 65537, "64"])
def test_final_caps_types_and_bounds_refused(unit_projection, monkeypatch, value):
    m = module(monkeypatch)
    data = fixture_dto(unit_projection)
    data["dispatch"]["technical_caps"]["output_tokens"] = value
    with pytest.raises(m.ManagedModelTerminal):
        m.parse_final_request(canonical(data))


def test_full_qualified_projection_nested_unknown_refused(unit_projection, monkeypatch):
    m = module(monkeypatch)
    data = fixture_dto(unit_projection)
    data["projection"]["payload"]["model_input"]["messages"][0]["unknown"] = "SYNTHETIC_FORBIDDEN"
    with pytest.raises(m.ManagedModelTerminal):
        m.parse_final_request(canonical(data))


def test_common_sink_consumes_explicit_dto_but_never_lifts_no_model(unit_projection, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes/tests"))
    from test_model_terminal import load

    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    observed = []
    actual = m.consume_final_request

    def spy(*args, **kwargs):
        observed.append(True)
        return actual(*args, **kwargs)

    monkeypatch.setattr(m, "consume_final_request", spy)
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    h = load("chat_completion_helpers.py", ["_dispatch_nonstreaming_api_request"], {})
    agent = SimpleNamespace(api_mode="chat_completions", provider="SOURCE_ONLY")

    def forbidden(*args, **kwargs):
        pytest.fail("NO_MODEL reached client/SDK")

    with pytest.raises(m.ManagedModelTerminal):
        h._dispatch_nonstreaming_api_request(
            agent, frozen.sdk_kwargs(), make_client=forbidden, final_request=frozen.raw
        )
    assert observed == [True]


def test_frozen_request_direct_constructor_refuses_mutable_bytes(monkeypatch):
    m = module(monkeypatch)
    with pytest.raises(m.ManagedModelTerminal):
        m.FinalModelRequest(bytearray(b"{}"))


def test_sdk_client_defaults_rechecked_after_original_prepare(unit_projection, monkeypatch):
    """SOURCE check-use double; callback installation is a denial, never a provider response."""
    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    completions = type("SourceCompletions", (), {"__module__": "openai.SOURCE_SHAPE_DOUBLE"})()
    http = SimpleNamespace(
        _auth=None, follow_redirects=False, event_hooks={"request": [], "response": []}
    )

    def mutate(request):
        http.event_hooks["request"].append(lambda request: None)

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
        max_retries=0,
        _custom_headers={},
        _custom_query={},
        _api_key_provider=None,
        _client=http,
        base_url="https://source-only.invalid/v1/",
        _prepare_request=mutate,
    )
    prepared = SimpleNamespace(
        content=frozen.http_body(),
        method="POST",
        url="https://source-only.invalid/v1/chat/completions",
        extensions={"timeout": {key: 1.0 for key in ("connect", "read", "write", "pool")}},
    )
    with m.final_sdk_guard(client, frozen.raw), pytest.raises(m.ManagedModelTerminal):
        client._prepare_request(prepared)


def test_http_timeout_extension_bool_does_not_equal_bound_float(unit_projection, monkeypatch):
    """SOURCE shape double only, not SDK/native/client authority evidence."""
    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    completions = type("SourceCompletions", (), {"__module__": "openai.SOURCE_SHAPE_DOUBLE"})()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
        max_retries=0,
        _custom_headers={},
        _custom_query={},
        _api_key_provider=None,
        _client=SimpleNamespace(
            _auth=None, follow_redirects=False, event_hooks={"request": [], "response": []}
        ),
        base_url="https://source-only.invalid/v1/",
        _prepare_request=lambda request: None,
    )
    prepared = SimpleNamespace(
        content=frozen.http_body(),
        method="POST",
        url="https://source-only.invalid/v1/chat/completions",
        extensions={"timeout": {"connect": True, "read": 1.0, "write": 1.0, "pool": 1.0}},
    )
    with m.final_sdk_guard(client, frozen.raw), pytest.raises(m.ManagedModelTerminal):
        client._prepare_request(prepared)


@pytest.mark.parametrize("channel", ["direct", "worker"])
def test_explicit_final_bytes_direct_worker_stay_no_model(unit_projection, monkeypatch, channel):
    """Actual function/class prefix and joined thread; NOT installed native lineage."""
    import contextlib
    import threading
    import time
    from unittest.mock import Mock

    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes/tests"))
    from test_model_terminal import load

    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    seen = []
    actual = m.consume_final_request

    def observe(*args, **kwargs):
        seen.append(True)
        return actual(*args, **kwargs)

    monkeypatch.setattr(m, "consume_final_request", observe)
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    h = load(
        "chat_completion_helpers.py", ["_dispatch_nonstreaming_api_request", "direct_api_call"], {}
    )
    h.threading, h.contextlib, h.time, h.logger = threading, contextlib, time, Mock()
    h._context_thread_target = lambda cb: cb
    agent = SimpleNamespace(
        api_mode="chat_completions",
        provider="SOURCE_ONLY",
        _interrupt_requested=False,
        _active_request_abort=None,
        _touch_activity=lambda *args: None,
    )
    request = None
    try:
        with pytest.raises(m.ManagedModelTerminal):
            if channel == "direct":
                h.direct_api_call(agent, frozen.sdk_kwargs(), final_request=frozen.raw)
            else:
                cls = load(
                    "chat_completion_nonstream.py", ["_NonStreamRequest"], {"h": h}
                )._NonStreamRequest
                request = cls.__new__(cls)
                request.agent, request.api_kwargs, request.final_request = (
                    agent,
                    frozen.sdk_kwargs(),
                    frozen.raw,
                )
                request.result = {"response": None, "error": None, "terminal": None}
                request.clients = SimpleNamespace(close_once=lambda *args: None)
                request.cancelled, request.codex_retired, request.codex_token = False, False, None
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
                request._make_client = lambda *args, **kwargs: pytest.fail(
                    "NO_MODEL client reached"
                )
                request.run()
        assert seen == ([] if channel == "direct" else [True])
    finally:
        if request is not None and request.thread is not None:
            request.thread.join(timeout=2)
            assert not request.thread.is_alive()


@pytest.mark.parametrize("channel", ["sink", "direct", "worker"])
def test_unbound_managed_dto_cannot_use_stock_route_without_inert_env(
    unit_projection, monkeypatch, channel
):
    """Untrusted SOURCE negative, not a warm agent/turn/config authority fixture."""
    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes/tests"))
    from test_model_terminal import load

    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    attempted = []

    class ReachedStockRoute(Exception):
        pass

    def client(*args, **kwargs):
        attempted.append("client")
        raise ReachedStockRoute()  # record before refusing; no provider response

    h = load(
        "chat_completion_helpers.py",
        ["_dispatch_nonstreaming_api_request", "direct_api_call"],
        {"_check_stale_giveup": client, "_RequestClientRegistry": client},
    )
    agent = SimpleNamespace(
        api_mode="chat_completions",
        provider="UNTRUSTED_NEGATIVE_NOT_NATIVE_CONFIGURATION",
        _touch_activity=client,
        _cold_state=None,
        native_turn_ref=json.loads(frozen.raw)["dispatch"]["native_turn_ref"],
    )
    monkeypatch.delenv("HERMES_OMNIS_INERT", raising=False)

    def call():
        if channel == "sink":
            return h._dispatch_nonstreaming_api_request(
                agent, frozen.sdk_kwargs(), make_client=client, final_request=frozen.raw
            )
        if channel == "direct":
            return h.direct_api_call(agent, frozen.sdk_kwargs(), final_request=frozen.raw)
        cls = load(
            "chat_completion_nonstream.py", ["_NonStreamRequest"], {"h": h}
        )._NonStreamRequest
        return cls(agent, frozen.sdk_kwargs(), final_request=frozen.raw)

    with pytest.raises(m.ManagedModelTerminal):
        call()
    assert attempted == [], "DATA-only refs reached stock client/setup without native authority"


@pytest.mark.parametrize("platform", ["cli", "cron"])
def test_public_worker_wrapper_keeps_unbound_denial_terminal_with_stale_breaker(
    unit_projection, monkeypatch, platform
):
    """Actual wrapper/breaker/error-owner SOURCE, not a native-turn/config grant."""
    import contextlib
    import inspect

    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes/tests"))
    from test_model_terminal import load

    m = module(monkeypatch)
    frozen = m.parse_final_request(canonical(fixture_dto(unit_projection)))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("recovery-or-client")
        raise AssertionError("managed denial reached stock recovery/setup")

    h = load(
        "chat_completion_helpers.py",
        [
            "_stale_streak",
            "_check_stale_giveup",
            "should_use_direct_api_call",
            "interruptible_api_call",
            "direct_api_call",
        ],
        {"env_int": lambda name, default: default, "contextlib": contextlib},
    )
    agent = SimpleNamespace(
        api_mode="chat_completions",
        provider="UNTRUSTED_SOURCE_NEGATIVE",
        platform=platform,
        _cold_state=None,
        _consecutive_stale_streams=5,
    )
    monkeypatch.delenv("HERMES_OMNIS_INERT", raising=False)
    with pytest.raises(m.ManagedModelTerminal) as denied:
        h.interruptible_api_call(agent, frozen.sdk_kwargs(), final_request=frozen.raw)
    handler = load(
        "turn_api_error.py",
        ["handle_api_error"],
        {"ApiErrorVerdict": SimpleNamespace, "recover_before_classification": forbidden},
    )
    args = {
        key: None
        for key in inspect.signature(handler.handle_api_error).parameters
        if key != "agent"
    }
    args["api_error"] = denied.value
    verdict = handler.handle_api_error(SimpleNamespace(thinking_callback=None), **args)
    assert verdict.action == "return" and verdict.result["failure_retryable"] is False
    assert verdict.result["model_admission_reason"] == "NO_MODEL" and calls == []
    # The identical stock nonmanaged caller retains the real stale breaker.
    with pytest.raises(RuntimeError, match="Provider has been unresponsive"):
        h.interruptible_api_call(agent, {}, final_request=None)
