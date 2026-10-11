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
from .native_preparation_contract import canonical, digest, loads, obj, reference, sha, uuid
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
