"""Immutable full request data at the shared Chat Completions sink.

Schema/pins and byte equality are data checks, NEVER model authority. The current
native owner is cold NO_MODEL; trusted turn/config/purpose and reserve/SENT/Stop
must exist independently before a managed client can be reached. No SDK imports,
config lookup, model selection, reservation or provider response is created here.
"""

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol, cast

from .model_projection import FIELDS as PROJECTION_FIELDS
from .model_projection import serialize_model_input
from .model_terminal import ManagedModelTerminal
from .native_preparation_contract import canonical, digest, loads, obj, reference, sha, text, uuid
from .prompt_bundle import integer

MAX_BYTES = 32768
FIELDS = {
    "projection",
    "projection_ref",
    "owner_id",
    "run_id",
    "binding_ref",
    "policy_digest",
    "dispatch",
}
DISPATCH_FIELDS = {
    "native_turn_ref",
    "provider_config_ref",
    "execution_selection_ref",
    "dispatch_attempt_id",
    "model_id",
    "fencing_epoch",
    "technical_caps",
}
SDK_FIELDS = {"messages", "model", "tools", "stream", "n", "max_completion_tokens", "timeout"}


class _SDKChat(Protocol):
    completions: object


class _SDKHTTP(Protocol):
    _auth: object
    follow_redirects: object
    event_hooks: object


class _SDKClient(Protocol):
    chat: _SDKChat
    max_retries: object
    _custom_headers: object
    _custom_query: object
    _api_key_provider: object
    _client: _SDKHTTP
    base_url: object
    _prepare_request: Callable[[object], object]


class _PreparedRequest(Protocol):
    content: object
    method: object
    url: object
    extensions: object


def reject() -> ManagedModelTerminal:
    return ManagedModelTerminal()


@dataclass(frozen=True, slots=True)
class FinalModelRequest:
    """Canonical data only. Constructing or parsing it cannot lift NO_MODEL."""

    raw: bytes

    def __post_init__(self) -> None:
        if type(self.raw) is not bytes or len(self.raw) > MAX_BYTES:
            raise reject()

    @property
    def dto_digest(self) -> str:
        return digest(self.raw)

    def sdk_kwargs(self) -> dict[str, object]:
        data = obj(loads(self.raw, MAX_BYTES), FIELDS)
        dispatch = obj(data["dispatch"], DISPATCH_FIELDS)
        caps = obj(dispatch["technical_caps"], {"calls", "output_tokens", "wall_seconds"})
        projection = obj(
            data["projection"], {"schema_version", "kind", "id", "revision", "payload", "digest"}
        )
        carrier = obj(projection["payload"], PROJECTION_FIELDS)
        model_input = obj(carrier["model_input"], {"messages", "tools"})
        return {
            "messages": model_input["messages"],
            "model": dispatch["model_id"],
            "max_completion_tokens": caps["output_tokens"],
            "n": 1,
            "stream": False,
            "tools": [],
            "timeout": float(cast(int, caps["wall_seconds"])),
        }

    def http_body(self) -> bytes:
        # Measured SDK2.24.0 field order/JSON encoding, not CanonicalJSON of the DTO.
        body = {k: v for k, v in self.sdk_kwargs().items() if k != "timeout"}
        return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()

    @property
    def http_digest(self) -> str:
        return digest(self.http_body())


def parse_final_request(raw: object) -> FinalModelRequest:
    """Validate all request data; refs remain untrusted until the domain owner resolves them."""
    try:
        if type(raw) is not bytes or len(raw) > MAX_BYTES:
            raise reject()
        data = obj(loads(raw, MAX_BYTES), FIELDS)
        if canonical(data) != raw:
            raise reject()
        carrier = serialize_model_input(
            data["projection"],
            projection_ref=data["projection_ref"],
            owner_id=uuid(data["owner_id"]),
            run_id=uuid(data["run_id"]),
            binding_ref=data["binding_ref"],
            policy_digest=sha(data["policy_digest"]),
        )
        dispatch = obj(data["dispatch"], DISPATCH_FIELDS)
        reference(dispatch["native_turn_ref"], "native-turn")
        reference(dispatch["provider_config_ref"], "provider-config")
        selection = reference(dispatch["execution_selection_ref"], "execution-selection")
        projection = obj(
            data["projection"], {"schema_version", "kind", "id", "revision", "payload", "digest"}
        )
        payload = cast(dict[str, object], projection["payload"])
        if selection != payload["selection_ref"] or digest(carrier) != payload["projection_digest"]:
            raise reject()
        uuid(dispatch["dispatch_attempt_id"])
        integer(dispatch["fencing_epoch"], 1, 2**63 - 1)
        model = dispatch["model_id"]
        if type(model) is not str or not 1 <= len(model.encode()) <= 256:
            raise reject()
        caps = obj(dispatch["technical_caps"], {"calls", "output_tokens", "wall_seconds"})
        integer(caps["calls"], 1, 1)
        integer(caps["output_tokens"], 1, 65536)
        integer(caps["wall_seconds"], 1, 1200)
        result = FinalModelRequest(raw)
        if len(result.http_body()) > MAX_BYTES:
            raise reject()
        return result
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise reject() from None


def consume_final_request(
    raw: object, observed: object, *, post_bypass: bool = False
) -> dict[str, object]:
    """Default-deny the complete kwargs; rebuild only from frozen bytes, never mutable aliases."""
    try:
        final = parse_final_request(raw)
        expected = final.sdk_kwargs()
        fields = SDK_FIELDS | ({"extra_body"} if post_bypass else set())
        actual = obj(observed, fields)
        if post_bypass:
            copied = {"messages": expected["messages"], "tools": expected["tools"]}
            expected = {**expected, "messages": [], "tools": [], "extra_body": copied}
        # canonical() disallows floats, so timeout is checked separately, with exact type.
        timeout = actual["timeout"]
        if type(timeout) is not float or timeout != expected["timeout"]:
            raise reject()
        if canonical({k: v for k, v in actual.items() if k != "timeout"}) != canonical(
            {k: v for k, v in expected.items() if k != "timeout"}
        ):
            raise reject()
        return expected
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise reject() from None


def validate_http_body(raw: object, actual_body: object) -> str:
    final = parse_final_request(raw)
    if (
        type(actual_body) is not bytes
        or len(actual_body) > MAX_BYTES
        or actual_body != final.http_body()
    ):
        raise reject()
    return digest(actual_body)


def _sdk_defaults(bound: _SDKClient) -> tuple[_SDKHTTP, str]:
    try:
        completions = bound.chat.completions
        if not type(completions).__module__.startswith("openai."):
            raise reject()
        if type(bound.max_retries) is not int or bound.max_retries != 0:
            raise reject()
        for value in (bound._custom_headers, bound._custom_query):
            if value is not None and (type(value) is not dict or value):
                raise reject()
        if bound._api_key_provider is not None:
            raise reject()
        http = bound._client
        if http._auth is not None or http.follow_redirects is not False:
            raise reject()
        hooks = http.event_hooks
        if type(hooks) is not dict or hooks != {"request": [], "response": []}:
            raise reject()
        if not callable(bound._prepare_request):
            raise reject()
        endpoint = str(bound.base_url).rstrip("/") + "/chat/completions"
        return http, endpoint
    except (ValueError, TypeError, AttributeError):
        raise reject() from None


@contextmanager
def final_sdk_guard(client: object, raw: object) -> Iterator[None]:
    """Request-local pin2.24 SDK prepare boundary, with client extensions/retries default-denied."""
    final = parse_final_request(raw)
    bound = cast(_SDKClient, client)
    http, endpoint = _sdk_defaults(bound)
    original = bound._prepare_request

    def guarded(request: object) -> None:
        prepared = cast(_PreparedRequest, request)
        try:
            original(request)
        finally:
            current_http, current_endpoint = _sdk_defaults(bound)
            if current_http is not http or current_endpoint != endpoint:
                raise reject()
            validate_http_body(final.raw, prepared.content)
            if prepared.method != "POST" or str(prepared.url) != endpoint:
                raise reject()
            timeout = final.sdk_kwargs()["timeout"]
            extensions = prepared.extensions
            if type(extensions) is not dict or extensions != {
                "timeout": {key: timeout for key in ("connect", "read", "write", "pool")}
            }:
                raise reject()
            values = extensions["timeout"]
            if type(values) is not dict or any(
                type(value) is not float for value in values.values()
            ):
                raise reject()

    bound._prepare_request = guarded
    try:
        yield
    finally:
        bound._prepare_request = original


CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"
SYNTHETIC_INSTRUCTION = "Respond briefly to this synthetic model test. Use no tools."
MONITOR = {
    "calls": 1,
    "output_tokens": None,
    "wall_seconds": 300,
    "output_policy": "MONITOR_SUBSCRIPTION",
}
EXECUTION_FIELDS = {
    "protocol",
    "mode",
    "context_ref",
    "binding",
    "turn",
    "projection",
    "dispatch",
    "sent",
}


def execution_packet(value: object) -> dict[str, object]:
    """Finite DATA; the native registry supplies authority separately."""
    from .managed_admission_contract import envelope, ref

    p = obj(value, EXECUTION_FIELDS)
    if p["protocol"] != "omnis-managed-admission-v6" or p["mode"] not in ("SEND", "RECEIVE"):
        raise reject()
    context = reference(p["context_ref"], "model-test-context")
    binding = envelope(p["binding"], "runtime-binding")
    turn = envelope(p["turn"], "native-turn")
    projection = envelope(p["projection"], "model-projection")
    dispatch = envelope(p["dispatch"], "model-dispatch")
    sent = envelope(p["sent"], "model-dispatch-transition")
    b = obj(
        binding["payload"],
        {
            "version",
            "context_ref",
            "runtime_boot",
            "authority",
            "native_root_id",
            "native_child_id",
            "native_session_id",
            "native_turn",
        },
    )
    t = cast(dict[str, object], turn["payload"])
    if (
        b["version"] != 6
        or b["context_ref"] != context
        or any(
            b[k] != t[k]
            for k in (
                "context_ref",
                "runtime_boot",
                "authority",
                "native_root_id",
                "native_child_id",
                "native_session_id",
                "native_turn",
            )
        )
    ):
        raise reject()
    v = obj(
        projection["payload"],
        {
            "version",
            "owner_id",
            "run_id",
            "context_ref",
            "composition_ref",
            "binding_ref",
            "selection_ref",
            "model_input",
            "approved_text_digests",
            "projection_digest",
            "output_policy",
        },
    )
    if (
        v["version"] != 2
        or v["context_ref"] != context
        or v["binding_ref"] != ref(binding)
        or v["output_policy"] != "MONITOR_SUBSCRIPTION"
    ):
        raise reject()
    uuid(v["owner_id"])
    uuid(v["run_id"])
    reference(v["composition_ref"], "prompt-composition")
    reference(v["selection_ref"], "execution-selection")
    model_input = obj(v["model_input"], {"messages", "tools"})
    if (
        model_input["tools"] != []
        or type(model_input["messages"]) is not list
        or len(model_input["messages"]) != 2
    ):
        raise reject()
    texts = []
    for raw, role in zip(model_input["messages"], ("system", "user"), strict=True):
        message = obj(raw, {"role", "content"})
        if message["role"] != role:
            raise reject()
        texts.append(text(message["content"], 8192))
    if (
        texts[0] != SYNTHETIC_INSTRUCTION
        or v["approved_text_digests"] != sorted({digest(t.encode()) for t in texts})
        or v["projection_digest"] != digest(canonical(model_input))
    ):
        raise reject()
    d = obj(
        dispatch["payload"],
        {
            "run_or_job_ref",
            "dispatch_attempt_id",
            "native_turn_ref",
            "dispatch_owner_ref",
            "purpose",
            "provider_config_ref",
            "model_id",
            "execution_selection_ref",
            "projection_ref",
            "projection_digest",
            "fencing_epoch",
            "deadline",
            "technical_caps",
            "reservation_ref",
            "usage_state",
            "provider_receipt_ref",
        },
    )
    if (
        d["native_turn_ref"] != ref(turn)
        or d["dispatch_owner_ref"] != ref(binding)
        or d["purpose"] != "SETTINGS_TEST"
        or d["model_id"] != "gpt-6.1-sol"
        or d["execution_selection_ref"] != v["selection_ref"]
        or d["projection_ref"] != ref(projection)
        or d["projection_digest"] != v["projection_digest"]
        or d["technical_caps"] != MONITOR
        or d["usage_state"] != "UNKNOWN"
        or d["provider_receipt_ref"] is not None
    ):
        raise reject()
    caps = obj(d["technical_caps"], set(MONITOR))
    integer(caps["calls"], 1, 1)
    integer(caps["wall_seconds"], 300, 300)
    reference(d["provider_config_ref"], "provider-config")
    reference(d["reservation_ref"], "model-reservation")
    integer(d["fencing_epoch"], 1, 2**63 - 1)
    uuid(d["dispatch_attempt_id"])
    if reference(d["run_or_job_ref"], "managed-run")["id"] != v["run_id"]:
        raise reject()
    e = obj(sent["payload"], {"dispatch_ref", "sequence", "state", "created_at"})
    if (
        e["dispatch_ref"] != ref(dispatch)
        or type(e["sequence"]) is not int
        or e["sequence"] != 1
        or e["state"] != "SENT"
    ):
        raise reject()
    if len(canonical(p)) > MAX_BYTES:
        raise reject()
    return cast(dict[str, object], loads(canonical(p), MAX_BYTES))


@dataclass(frozen=True, slots=True)
class CodexFinalRequest:
    raw: bytes

    def __post_init__(self) -> None:
        if (
            type(self.raw) is not bytes
            or canonical(execution_packet(loads(self.raw, MAX_BYTES))) != self.raw
        ):
            raise reject()

    def expected_body(self) -> dict[str, object]:
        p = execution_packet(loads(self.raw, MAX_BYTES))
        projection = cast(dict[str, object], cast(dict[str, object], p["projection"])["payload"])
        model_input = cast(dict[str, object], projection["model_input"])
        messages = cast(list[dict[str, object]], model_input["messages"])
        instruction, objective = str(messages[0]["content"]), str(messages[1]["content"])
        # Pin0.21.5 ResponsesApiTransport._content_cache_key, no session/history/tools.
        cache = "pck_" + digest(("\0" + instruction + "\0").encode())[:24]
        return {
            "model": "gpt-6.1-sol",
            "instructions": instruction,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": objective}]}],
            "store": False,
            "prompt_cache_key": cache,
            "reasoning": {"effort": "xhigh", "summary": "auto"},
            "include": [],
            "stream": True,
        }

    def consume_native(self, value: object) -> dict[str, object]:
        expected = self.expected_body()
        body = {k: v for k, v in expected.items() if k != "stream"}
        cache = str(body["prompt_cache_key"])
        kwargs = {**body, "timeout": 300.0, "extra_headers": {"x-client-request-id": cache}}
        actual = obj(value, set(kwargs))
        if (
            type(actual["timeout"]) is not float
            or actual["timeout"] != 300.0
            or canonical({k: v for k, v in actual.items() if k != "timeout"})
            != canonical({k: v for k, v in kwargs.items() if k != "timeout"})
        ):
            raise reject()
        return {**kwargs, "stream": True}

    def validate_wire(self, raw: bytes) -> str:
        if (
            type(raw) is not bytes
            or len(raw) > MAX_BYTES
            or canonical(loads(raw, MAX_BYTES)) != canonical(self.expected_body())
        ):
            raise reject()
        return digest(raw)
