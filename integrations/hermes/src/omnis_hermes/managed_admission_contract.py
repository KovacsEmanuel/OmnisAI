"""Exact, bounded managed cold-admission v1. No native import or authority by goal."""

from typing import cast

from .native_preparation_contract import bounded, canonical, digest, obj, reference, text, uuid

PROTOCOL = "omnis-managed-admission-v1"
PROTOCOL_V2 = "omnis-managed-admission-v2"
PROTOCOL_V3 = "omnis-managed-admission-v3"
OPS = frozenset({"task_stage", "task_release", "task_status"})
RPC = {op: "omnis.managed." + op.removeprefix("task_") for op in OPS}
MAX_BYTES = 32768


def envelope(value: object, kind: str) -> dict[str, object]:
    bounded(value)
    value = obj(value, {"schema_version", "kind", "id", "revision", "payload", "digest"})
    reference({k: value[k] for k in ("kind", "id", "revision", "digest")}, kind)
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["revision"] != 1
        or len(canonical(value)) > MAX_BYTES
        or digest(canonical({k: v for k, v in value.items() if k != "digest"})) != value["digest"]
    ):
        raise ValueError("Invalid managed envelope")
    return value


def ref(value: dict[str, object]) -> dict[str, object]:
    return {k: value[k] for k in ("kind", "id", "revision", "digest")}


def entries(value: object, *, native: bool, composed: bool = False) -> list[dict[str, object]]:
    if type(value) is not list or not 1 <= len(value) <= 2:
        raise ValueError("Invalid managed entries")
    fields = {"batch_index", "task_id", "attempt_id", "brief_ref"}
    if composed:
        fields.add("composition_ref")
    fields |= {"native_child_id", "native_session_id"} if native else {"goal"}
    for i, entry in enumerate(value):
        entry = obj(entry, fields)
        if type(entry["batch_index"]) is not int or entry["batch_index"] != i:
            raise ValueError("Invalid managed index")
        uuid(entry["task_id"])
        uuid(entry["attempt_id"])
        reference(entry["brief_ref"], "task-brief")
        if composed:
            reference(entry["composition_ref"], "prompt-composition")
        if native:
            text(entry["native_child_id"])
            text(entry["native_session_id"])
        else:
            text(entry["goal"], 4096)
    unique = ["task_id", "attempt_id"] + (
        ["native_child_id", "native_session_id"] if native else []
    )
    if any(len({e[k] for e in value}) != len(value) for k in unique):
        raise ValueError("Duplicate managed identity")
    return cast(list[dict[str, object]], value)


def wire(value: object, fields: set[str]) -> dict[str, object]:
    bounded(value)
    value = obj(value, fields | {"protocol"})
    if (
        value["protocol"] not in (PROTOCOL, PROTOCOL_V2, PROTOCOL_V3)
        or len(canonical(value)) > MAX_BYTES
    ):
        raise ValueError("Invalid managed protocol")
    return value


def validate_stage(value: object) -> dict[str, object]:
    composed = type(value) is dict and value.get("protocol") in (PROTOCOL_V2, PROTOCOL_V3)
    value = wire(value, {"manifest", "compositions"} if composed else {"manifest"})
    result = envelope(value["manifest"], "launch-manifest")
    fields = {"run_id", "selection_ref", "resolution", "effective", "entries"}
    if composed:
        fields.add("composition_version")
    payload = obj(result["payload"], fields)
    if composed and (
        type(payload["composition_version"]) is not int
        or payload["composition_version"]
        not in ((3,) if value["protocol"] == PROTOCOL_V3 else (1, 2))
    ):
        raise ValueError("Invalid composition version")
    uuid(payload["run_id"])
    reference(payload["selection_ref"], "execution-selection")
    if payload["resolution"] != "NO_MODEL" or payload["effective"] is not None:
        raise ValueError("Only NO_MODEL admission is supported")
    rows = entries(payload["entries"], native=False, composed=composed)
    if composed and payload["composition_version"] in (2, 3) and len(rows) != 1:
        raise ValueError("Case input composition requires one attempt")
    if composed:
        from .prompt_bundle import validate_composition

        compositions = value["compositions"]
        if type(compositions) is not list or len(compositions) != len(rows):
            raise ValueError("Incomplete compositions")
        for composition, entry in zip(compositions, rows, strict=True):
            validate_composition(composition, result, entry)
    return result


def validate_status(value: object) -> dict[str, object]:
    value = wire(value, {"ticket", "manifest_ref"})
    uuid(value["ticket"])
    reference(value["manifest_ref"], "launch-manifest")
    return value


def validate_release(value: object) -> dict[str, object]:
    value = wire(value, {"ticket", "manifest_ref", "binding"})
    validate_status({k: v for k, v in value.items() if k != "binding"})
    binding = envelope(value["binding"], "runtime-binding")
    payload = obj(
        binding["payload"],
        {"runtime_boot", "run_id", "ticket", "native_root_id", "entries", "authority"},
    )
    for k in ("runtime_boot", "run_id", "ticket"):
        uuid(payload[k])
    text(payload["native_root_id"])
    entries(
        payload["entries"], native=True, composed=value["protocol"] in (PROTOCOL_V2, PROTOCOL_V3)
    )
    authority = obj(payload["authority"], {"instance_id", "owner", "epoch", "generation"})
    uuid(authority["instance_id"])
    uuid(authority["owner"])
    for key, minimum in (("epoch", 1), ("generation", 0)):
        fence = authority[key]
        if type(fence) is not int or not minimum <= fence < 2**63:
            raise ValueError("Invalid managed fence")
    if payload["ticket"] != value["ticket"]:
        raise ValueError("Managed ticket mismatch")
    return value


def validate_response(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError("Invalid managed response")
    final = value.get("status") == "BLOCKED"
    keys = {"status", "ticket", "manifest_ref", "native_root_id", "entries"}
    if final:
        keys |= {"reason", "binding_ref"}
    value = wire(value, keys)
    validate_status({k: value[k] for k in ("protocol", "ticket", "manifest_ref")})
    if final:
        if value["reason"] != "NO_MODEL":
            raise ValueError("Invalid native refusal")
        reference(value["binding_ref"], "runtime-binding")
    elif value["status"] != "STAGED":
        raise ValueError("Invalid native stage")
    text(value["native_root_id"])
    entries(value["entries"], native=True, composed=value["protocol"] in (PROTOCOL_V2, PROTOCOL_V3))
    return value
