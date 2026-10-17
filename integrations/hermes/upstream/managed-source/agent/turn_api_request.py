"""Per-attempt request assembly for the conversation turn's retry loop: re-apply the
reasoning echo pad and prompt-cache decoration for the CURRENT provider (a fallback may
differ from the primary), build ``api_kwargs``, run the surrogate/ASCII chokepoints, Codex
preflight, OpenRouter cache bypass, Copilot ``x-initiator``, the LLM request middleware,
the ``pre_api_request`` hook and the debug dump. Nothing here imports
``agent.conversation_loop`` at module level.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from agent.message_sanitization import sanitize_outbound_kwargs, strip_images_for_rejecting_model
from utils import env_var_enabled

logger = logging.getLogger("agent.conversation_loop")


@dataclass
class ApiRequestBuild:
    """Always ``action == "fallthrough"``; the fields are the request-local values the caller
    rebinds for the attempt."""

    action: str
    api_messages: Any
    _moa_prepared_request: Any
    tools_for_api: Any
    api_kwargs: Any
    _original_api_kwargs: Any
    _llm_middleware_trace: Any


def _set_extra_header(api_kwargs: Any, key: str, value: str) -> None:
    """Copy-on-write header set (the dict may be shared with the transport's defaults)."""
    _xh = dict(api_kwargs.get("extra_headers") or {})
    _xh[key] = value
    api_kwargs["extra_headers"] = _xh


def _fire_pre_api_request_hook(
    agent: Any, api_kwargs: Any, api_messages: Any, _llm_middleware_trace: Any, *, messages: Any,
    original_user_message: Any, approx_tokens: Any, total_chars: Any, retry_count: Any,
    api_call_count: Any, api_request_id: Any, api_start_time: Any, effective_task_id: Any,
    turn_id: Any,
) -> None:
    from agent.conversation_loop import _system_prompt_for_hooks

    try:
        from hermes_cli.lifecycle import has_hook, invoke_hook as _invoke_hook
        if has_hook("pre_api_request"):
            request_messages = api_kwargs.get("messages")
            if not isinstance(request_messages, list):
                request_messages = api_kwargs.get("input")
            if not isinstance(request_messages, list):
                request_messages = api_messages
            # Shallow copies: plugins may retain the lists; deepcopy is costly.
            # ``request_messages``/``conversation_history`` are raw langfuse passthroughs.
            # Anthropic (``system``) and Responses/Codex (``instructions``) move the system
            # prompt out of messages; pass it for observability.
            _invoke_hook(
                "pre_api_request",
                task_id=effective_task_id,
                turn_id=turn_id,
                api_request_id=api_request_id,
                session_id=agent.session_id or "",
                user_message=original_user_message,
                conversation_history=list(messages),
                platform=agent.platform or "",
                model=agent.model,
                provider=agent.provider,
                base_url=agent.base_url,
                api_mode=agent.api_mode,
                api_call_count=api_call_count,
                retry_count=retry_count,
                request_messages=list(request_messages) if isinstance(request_messages, list) else [],
                system_prompt=_system_prompt_for_hooks(api_kwargs, request_messages),
                message_count=len(api_messages),
                tool_count=len(agent.tools or []),
                approx_input_tokens=approx_tokens,
                request_char_count=total_chars,
                max_tokens=agent.max_tokens,
                started_at=api_start_time,
                middleware_trace=list(_llm_middleware_trace),
                request=agent._api_request_payload_for_hook(api_kwargs),
            )
    except Exception:
        pass


def build_api_request(
    agent: Any, *, api_messages: Any, _moa_prepared_request: Any, tools_for_api: Any,
    system_message: Any, messages: Any, original_user_message: Any, approx_tokens: Any,
    total_chars: Any, retry_count: Any, api_call_count: Any, api_request_id: Any,
    api_start_time: Any, effective_task_id: Any, turn_id: Any,
) -> ApiRequestBuild:
    """Assemble the attempt's request in the original order (every mutation happens BEFORE
    middleware/hooks/debug dumps observe the payload)."""
    from omnis_hermes.model_terminal import require_model_authority
    require_model_authority(agent)
    from agent.conversation_loop import (
        _moa_client_consumes_prepared_request, _redecorate_prompt_cache_for_provider,
    )

    agent._reset_stream_delivery_tracking()
    # Per-attempt first-chunk timestamp so a stale value never leaks into post_api_request.
    agent._last_api_first_chunk_at = None
    # api_messages was built for the primary; a fallback (DeepSeek / Kimi / MiMo) may
    # require reasoning_content — re-apply the echo-back pad (idempotent) and re-render
    # the prompt-cache decoration for the current provider.
    agent._reapply_reasoning_echo_for_provider(api_messages)
    api_messages, _moa_prepared_request, tools_for_api = (
        _redecorate_prompt_cache_for_provider(
            agent, api_messages, system_message=system_message, moa_prepared=_moa_prepared_request,
            tools_for_api=tools_for_api,
        )
    )
    # A model that rejected image content gets text only; history keeps the images.
    strip_images_for_rejecting_model(agent, api_messages)
    if tools_for_api == agent.tools:
        api_kwargs = agent._build_api_kwargs(api_messages)
    else:
        api_kwargs = agent._build_api_kwargs(api_messages, tools_for_api=tools_for_api)
    # Messages were scrubbed above; this walk covers the rest of the payload (tool descriptions,
    # extra_body, kwargs strings) — see sanitize_outbound_kwargs for the #50959 rationale.
    sanitize_outbound_kwargs(agent, api_kwargs)
    if agent.api_mode == "codex_responses":
        api_kwargs = agent._get_transport().preflight_kwargs(
            api_kwargs, allow_stream=False, is_github_responses=agent._is_copilot_url(),
            sanitize_harmony_tokens=agent._is_codex_backend(),
        )
    # OpenRouter caching replays identical responses, even empty ones; an empty-response
    # retry must bypass the cache.
    if agent._empty_content_retries > 0 and agent._is_openrouter_url():
        _set_extra_header(api_kwargs, "X-OpenRouter-Cache", "false")
    # Copilot x-initiator: first call of a user turn is "user" (billed premium);
    # tool-loop follow-ups keep the default "agent".
    if getattr(agent, "_is_user_initiated_turn", False) and agent._is_copilot_url():
        _set_extra_header(api_kwargs, "x-initiator", "user")
        agent._is_user_initiated_turn = False
    try:
        from hermes_cli.middleware import apply_llm_request_middleware

        _llm_request_mw = apply_llm_request_middleware(
            api_kwargs, task_id=effective_task_id, turn_id=turn_id, api_request_id=api_request_id,
            session_id=agent.session_id or "", platform=agent.platform or "", model=agent.model,
            provider=agent.provider, base_url=agent.base_url, api_mode=agent.api_mode,
            api_call_count=api_call_count,
        )
        api_kwargs = _llm_request_mw.payload
        _original_api_kwargs = _llm_request_mw.original_payload
        _llm_middleware_trace = _llm_request_mw.trace
    except Exception:
        _original_api_kwargs = dict(api_kwargs)
        _llm_middleware_trace = []

    _fire_pre_api_request_hook(
        agent, api_kwargs, api_messages, _llm_middleware_trace, messages=messages,
        original_user_message=original_user_message, approx_tokens=approx_tokens,
        total_chars=total_chars, retry_count=retry_count, api_call_count=api_call_count,
        api_request_id=api_request_id, api_start_time=api_start_time,
        effective_task_id=effective_task_id, turn_id=turn_id,
    )

    if env_var_enabled("HERMES_DUMP_REQUESTS"):
        agent._dump_api_request_debug(api_kwargs, reason="preflight")

    # Private to the in-process MoA facade; added after middleware/hooks/debug dumps so
    # none serializes it into the provider payload. Re-read the live client:
    # rotation/fallback/cleanup rebuild agent.client between attempts; a native OpenAI
    # client rejects this key (TypeError).
    if _moa_prepared_request is not None and agent.provider == "moa":
        if _moa_client_consumes_prepared_request(agent.client):
            api_kwargs["_moa_prepared_request"] = _moa_prepared_request
        else:
            logger.warning(
                "MoA client replaced mid-turn (client=%s); sending the "
                "prepared prompt without the MoA handshake",
                type(agent.client).__name__,
            )
    return ApiRequestBuild(
        "fallthrough", api_messages, _moa_prepared_request, tools_for_api, api_kwargs,
        _original_api_kwargs, _llm_middleware_trace,
    )


def run_model_test_request(agent):
    """One constructor-owned native Responses request, no stock retry/fallback loop."""
    import os
    import time
    import socket
    import threading
    from contextlib import suppress
    from datetime import datetime, timezone
    import httpx
    from openai import OpenAI
    from omnis_hermes.model_request import CodexFinalRequest, CODEX_URL
    from omnis_hermes.managed_admission_contract import canonical, ref
    from omnis_hermes.native_preparation_contract import loads
    from agent.transports.codex import ResponsesApiTransport
    from agent.codex_headers import codex_cloudflare_headers

    final = agent._model_test_dispatch
    if type(final) is not CodexFinalRequest or not agent._model_test_execution:
        raise ValueError("Constructor-owned execution required")
    from omnis_hermes.model_terminal import require_model_authority
    require_model_authority(agent, final_request=final)
    p = loads(final.raw, 32768)
    d = p["dispatch"]["payload"]
    result = {"protocol": p["protocol"], "context_ref": p["context_ref"],
        "dispatch_ref": ref(p["dispatch"]), "status": "UNKNOWN", "receipt": None}
    physical = {"headers": 0, "request": None, "wire_digest": None, "socket": None}
    expiry = datetime.fromisoformat(d["deadline"])
    if expiry.utcoffset() != timezone.utc.utcoffset(expiry):
        raise ValueError("Invalid execution deadline")
    remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
    deadline = time.monotonic() + min(300.0, remaining)
    retired = threading.Event()

    def abort():
        retired.set()
        sock = physical["socket"]
        if sock is not None:
            # shutdown wakes a blocked read without releasing another thread's TLS FD.
            with suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)

    def guard():
        agent._model_test_lifeline._owner_alive()
        if retired.is_set() or agent._model_test_closed.is_set() or time.monotonic() >= deadline:
            raise ValueError("Execution authority revoked")
        if agent._model_test_dispatch is not final or agent._api_call_count != 0:
            raise ValueError("Execution authority changed")

    def before_send(request):
        guard()
        if request.method != "POST" or str(request.url) != CODEX_URL or request.headers["host"] != "chatgpt.com":
            raise ValueError("Finite Codex endpoint required")
        physical["wire_digest"] = final.validate_wire(request.content)
        physical["request"] = request
        request.extensions["trace"] = trace

    def trace(event, info):
        if event in ("connection.connect_tcp.complete", "connection.connect_unix_socket.complete"):
            # Keep an owned descriptor across SSL wrap_socket's detach/handshake.
            physical["socket"] = info["return_value"].get_extra_info("socket").dup()
            guard()
        if event.endswith(".started"):
            guard()
            # httpcore forwards this exact kwargs dict to connect/start_tls.
            if "timeout" in info:
                info["timeout"] = max(0.001, deadline - time.monotonic())
        if event.endswith(".send_request_headers.started"):
            request = physical["request"]
            if request is None or physical["headers"] != 0:
                raise ValueError("Repeated physical request denied")
            final.validate_wire(request.content)
            physical["headers"] = 1

    client = None
    timer = None
    try:
        guard()
        if os.environ.get("HERMES_HOME") != "/state/provider":
            raise ValueError("Dedicated product home required")
        from hermes_cli.auth_codex import _read_codex_tokens, _codex_access_token_is_expiring
        # Management family was joined before this native family. No refresh,
        # external login adoption, credential pool, discovery, quota or aux calls.
        tokens = _read_codex_tokens()["tokens"]
        token = tokens["access_token"]
        if _codex_access_token_is_expiring(token, 300):
            raise ValueError("Operator authentication refresh required")
        guard()
        projection = p["projection"]["payload"]
        kwargs = ResponsesApiTransport().build_kwargs(
            model="gpt-6.1-sol", messages=projection["model_input"]["messages"], tools=[],
            **{"provider": "openai-codex", "base_url": CODEX_URL.rsplit("/", 1)[0],
                "is_codex_backend": True, "reasoning_config": {"enabled": True, "effort": "xhigh"},
                "replay_encrypted_reasoning": False, "timeout": 300.0},
        )
        kwargs = final.consume_native(kwargs)  # after ALL native transformations
        kwargs["timeout"] = max(0.001, deadline - time.monotonic())
        transport = httpx.HTTPTransport(uds="/runtime/auth-egress.sock", retries=0, trust_env=False)
        http = httpx.Client(transport=transport, trust_env=False, follow_redirects=False,
            timeout=kwargs["timeout"], event_hooks={"request": [before_send]})
        client = OpenAI(api_key=token, base_url=CODEX_URL.rsplit("/", 1)[0], max_retries=0,
            timeout=kwargs["timeout"], http_client=http,
            default_headers=codex_cloudflare_headers(token, base_url=CODEX_URL.rsplit("/", 1)[0]))
        agent._model_test_client = client
        agent._model_test_abort = abort
        timer = threading.Timer(max(0.0, deadline - time.monotonic()), abort)
        timer.daemon = True
        timer.start()
        guard()
        terminal = None
        output_items = []
        with client.responses.create(**kwargs) as stream:
            for event in stream:
                guard()
                if event.type == "response.output_item.done":
                    item = event.item.model_dump(mode="json")
                    if len(canonical(output_items + [item])) > 32768:
                        raise ValueError("Provider output requires reconciliation")
                    output_items.append(item)
                if event.type in ("response.completed", "response.incomplete", "response.failed"):
                    if terminal is not None:
                        raise ValueError("Duplicate terminal response")
                    terminal = event.response
                    break
        if terminal is None or physical["headers"] != 1:
            raise ValueError("Provider outcome unknown")
        usage = terminal.usage
        # The pin assembles output_item.done because Codex terminal.output may be null.
        if terminal.output is not None and type(terminal.output) is not list:
            raise ValueError("Malformed provider output")
        items = output_items or terminal.output or []
        if type(items) is not list:
            raise ValueError("Malformed provider output")
        parts = []
        for item in items:
            item = item if type(item) is dict else item.model_dump(mode="json")
            if item.get("type") == "reasoning":
                continue
            if item.get("type") != "message" or type(item.get("content")) is not list:
                raise ValueError("Unclassified provider output")
            for part in item["content"]:
                field = {"output_text": "text", "refusal": "refusal"}.get(part.get("type"))
                if field is None or type(part.get(field)) is not str:
                    raise ValueError("Unclassified provider content")
                parts.append(part[field])
        output = "".join(parts)
        if type(output) is not str or len(output.encode()) > 8192:
            raise ValueError("Provider output requires reconciliation")
        result["status"] = "COMPLETE"
        result["receipt"] = {"provider_response_id": terminal.id, "model": terminal.model,
            "effort": getattr(terminal.reasoning, "effort", None), "status": terminal.status,
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "reasoning_tokens": getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", None),
            "output_text": output, "wire_digest": physical["wire_digest"]}
    except Exception:
        # SENT remains consumed even if this process cannot recover a receipt.
        result = {**result, "status": "UNKNOWN", "receipt": None}
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        if client is not None:
            try:
                client.close()
            except Exception:
                result = {**result, "status": "UNKNOWN", "receipt": None}
        if physical["socket"] is not None:
            with suppress(OSError):
                physical["socket"].close()
        agent._api_call_count = physical["headers"]
        agent._model_test_result = result
