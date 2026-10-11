"""Model-data preflight at the existing native cold lifecycle boundary.

No provider/client imports, callbacks, model grant or native-turn fabrication.
The only supported lifecycle is cold NO_MODEL; the complete SDK/send boundary
is deliberately not credited by this carrier consumer.
"""

from . import managed_admission_contract as managed
from .model_context import validate_context
from .model_projection import serialize_model_input, validate_serialized_input
from .native_preparation_contract import canonical, digest, loads, obj, reference, text, uuid
from .prompt_bundle import mapping

POLICY_DIGEST = "f2e74cd2b523f5f9eb22505bccd4adf8a41369f7b47fe2ca8d20ec08b8f1f379"
FIELDS = {
    "ticket",
    "manifest_ref",
    "binding",
    "owner_id",
    "run_id",
    "projection",
    "projection_ref",
    "policy_digest",
    "model_context",
    "model_context_digest",
}
RESULT_FIELDS = {
    "protocol",
    "status",
    "reason",
    "manifest_ref",
    "binding_ref",
    "projection_ref",
    "projection_digest",
    "native_turn",
    "model_calls",
    "model_context",
    "model_context_digest",
}


def validate_preflight(value: object) -> bytes:
    """Rebuild and independently gate the exact qualified carrier before native use."""
    payload = managed.wire(value, FIELDS)
    if payload["protocol"] not in (managed.PROTOCOL_V2, managed.PROTOCOL_V3):
        raise ValueError("Model preflight requires composed assignment")
    managed.validate_release(
        {key: payload[key] for key in ("protocol", "ticket", "manifest_ref", "binding")}
    )
    binding = managed.envelope(payload["binding"], "runtime-binding")
    body = mapping(binding["payload"])
    if uuid(payload["run_id"]) != body["run_id"] or payload["policy_digest"] != POLICY_DIGEST:
        raise ValueError("Invalid model preflight pins")
    raw = serialize_model_input(
        payload["projection"],
        projection_ref=payload["projection_ref"],
        owner_id=uuid(payload["owner_id"]),
        run_id=uuid(payload["run_id"]),
        binding_ref=managed.ref(binding),
        policy_digest=POLICY_DIGEST,
    )
    raw = validate_serialized_input(
        raw,
        payload["projection"],
        projection_ref=payload["projection_ref"],
        owner_id=uuid(payload["owner_id"]),
        run_id=uuid(payload["run_id"]),
        binding_ref=managed.ref(binding),
        policy_digest=POLICY_DIGEST,
    )
    projection = mapping(mapping(payload["projection"])["payload"])
    if projection["manifest_ref"] != payload["manifest_ref"]:
        raise ValueError("Invalid model preflight assignment")
    rows = managed.entries(body["entries"], native=True, composed=True)
    selected = [r for r in rows if r["composition_ref"] == projection["composition_ref"]]
    if len(selected) != 1:
        raise ValueError("Invalid model preflight assignment")
    messages = mapping(loads(raw, 32768))["messages"]
    if type(messages) is not list or len(messages) != 2:
        raise ValueError("Invalid model preflight carrier")
    content = mapping(loads(str(mapping(messages[1])["content"]).encode(), 32768))
    header = mapping(content["header"])
    if any(header[k] != selected[0][k] for k in ("task_id", "attempt_id")):
        raise ValueError("Invalid model preflight identity")
    context = validate_context(payload["model_context"], payload)
    if digest(canonical(context)) != payload["model_context_digest"]:
        raise ValueError("Invalid qualified context digest")
    return raw


def _result(payload: dict[str, object], raw: bytes) -> dict[str, object]:
    return {
        "protocol": payload["protocol"],
        "status": "BLOCKED",
        "reason": "NO_MODEL",
        "manifest_ref": reference(payload["manifest_ref"], "launch-manifest"),
        "binding_ref": managed.ref(mapping(payload["binding"])),
        "projection_ref": reference(payload["projection_ref"], "model-projection"),
        "projection_digest": digest(raw),
        "native_turn": None,
        "model_calls": 0,
        "model_context": payload["model_context"],
        "model_context_digest": payload["model_context_digest"],
    }


def cold_preflight(
    value: object,
    *,
    native_root_id: object,
    native_entries: object,
) -> dict[str, object]:
    """Native lifecycle calls this under its original-root/registry fence."""
    payload = mapping(loads(canonical(value), 32768))
    raw = validate_preflight(payload)
    body = mapping(mapping(payload["binding"])["payload"])
    rows = managed.entries(native_entries, native=True, composed=True)
    if body["native_root_id"] != text(native_root_id) or canonical(rows) != canonical(
        body["entries"]
    ):
        raise ValueError("Invalid native model lineage")
    # A cold identity is not a turn. Never mint native-turn or reserve model here.
    return _result(payload, raw)


def validate_preflight_result(value: object, payload: dict[str, object]) -> dict[str, object]:
    result = obj(value, RESULT_FIELDS)
    expected = _result(payload, validate_preflight(payload))
    if type(result["model_calls"]) is not int or canonical(result) != canonical(expected):
        raise ValueError("Invalid native model preflight result")
    return result
