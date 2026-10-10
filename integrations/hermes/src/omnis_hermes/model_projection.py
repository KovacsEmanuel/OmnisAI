"""Stdlib-only ModelProjection v1 serialization. No native/provider side effects.

Trusted caller MUST obtain projection_ref/pins from backend readback, never from
model text. This guards the entire serialized carrier, not an SDK request whose
transport fields have not yet been mapped/guarded by B06m.
"""

from .managed_admission_contract import envelope, ref
from .native_preparation_contract import (
    canonical,
    digest,
    loads,
    obj,
    raw_text,
    reference,
    sha,
    uuid,
)
from .prompt_bundle import integer, sequence

FIELDS = {
    "version",
    "owner_id",
    "run_id",
    "manifest_ref",
    "runtime_binding_ref",
    "composition_ref",
    "brief_ref",
    "snapshot_ref",
    "selection_ref",
    "mission_ref",
    "focus_ref",
    "policy_ref",
    "scope_ref",
    "policy_digest",
    "approval_digest",
    "provenance",
    "model_input",
    "projection_digest",
}
REFS = {
    "manifest_ref": "launch-manifest",
    "runtime_binding_ref": "runtime-binding",
    "composition_ref": "prompt-composition",
    "brief_ref": "task-brief",
    "snapshot_ref": "run-snapshot",
    "selection_ref": "execution-selection",
    "mission_ref": "mission",
    "focus_ref": "focus",
    "policy_ref": "probe-policy",
    "scope_ref": "probe-scope",
}
HEADER = {
    "schema_version",
    "run_id",
    "task_id",
    "attempt_id",
    "snapshot_ref",
    "mission_revision",
    "focus_ref",
    "through_cursor",
    "brief_revision",
    "result_schema_ref",
}


def reject() -> ValueError:
    return ValueError("Invalid model projection")


def prose(value: object) -> str:
    if type(value) is not str or not 1 <= len(value.encode()) <= 8192:
        raise reject()
    return raw_text(value.encode())


def _content(model_input: object, payload: dict[str, object]) -> None:
    carrier = obj(model_input, {"messages", "tools"})
    if carrier["tools"] != []:
        raise reject()
    messages = sequence(carrier["messages"], 2, 2)
    contents = []
    for message, role in zip(messages, ("system", "user"), strict=True):
        item = obj(message, {"role", "content"})
        if item["role"] != role or type(item["content"]) is not str:
            raise reject()
        encoded_content = item["content"].encode()
        content = loads(encoded_content, 32768)
        if canonical(content) != encoded_content:
            raise reject()
        contents.append(content)
    system = obj(contents[0], {"instructions", "method"})
    instructions = sequence(system["instructions"], 3, 6)
    for index, raw in enumerate(instructions):
        item = obj(raw, {"source_ref", "kind", "text"})
        kind = ("base", "role")[index] if index < 2 else "skill"
        if item["kind"] != kind:
            raise reject()
        reference(item["source_ref"], "prompt-content" if index < 2 else "package")
        prose(item["text"])
    method = obj(system["method"], {"source_ref", "objective", "requirements", "steps"})
    reference(method["source_ref"], "bound-procedure")
    prose(method["objective"])
    for raw in sequence(method["requirements"], 1, 128):
        item = obj(raw, {"key", "description", "required", "step_ids"})
        prose(item["key"])
        prose(item["description"])
        if type(item["required"]) is not bool:
            raise reject()
        for identity in sequence(item["step_ids"]):
            prose(identity)
    for raw in sequence(method["steps"], 1, 128):
        item = obj(raw, {"id", "action_definition_ref"})
        prose(item["id"])
        reference(item["action_definition_ref"], "action_definition")
    user = obj(
        contents[1],
        {
            "header",
            "role",
            "objective_summary",
            "hypothesis",
            "priority_reason",
            "non_goals",
            "context",
            "input_ref",
            "records",
        },
    )
    header = obj(user["header"], HEADER)
    integer(header["schema_version"], 1, 1)
    integer(header["brief_revision"], 1, 1)
    for key in ("run_id", "task_id", "attempt_id", "through_cursor"):
        uuid(header[key])
    for key, pin in (
        ("snapshot_ref", "snapshot_ref"),
        ("mission_revision", "mission_ref"),
        ("focus_ref", "focus_ref"),
    ):
        if header[key] != payload[pin]:
            raise reject()
    reference(header["result_schema_ref"], "schema")
    if header["run_id"] != payload["run_id"] or user["role"] not in (
        "RECON",
        "INVESTIGATOR",
        "VALIDATOR",
        "RESEARCH",
    ):
        raise reject()
    for key in ("objective_summary", "hypothesis", "priority_reason"):
        prose(user[key])
    for value in sequence(user["non_goals"]):
        prose(value)
    contexts = sequence(user["context"], 2, 3)
    expected_context = [payload["mission_ref"], payload["focus_ref"]]
    if user["input_ref"] is not None:
        expected_context.append(reference(user["input_ref"], "contract-case-records"))
    if [
        obj(v, {"ref", "epistemic_state", "summary", "mandatory"})["ref"] for v in contexts
    ] != expected_context:
        raise reject()
    for raw in contexts:
        item = obj(raw, {"ref", "epistemic_state", "summary", "mandatory"})
        if (
            item["epistemic_state"] not in ("OBSERVED", "INFERRED", "CONTRADICTED")
            or type(item["mandatory"]) is not bool
        ):
            raise reject()
        prose(item["summary"])
    values = sequence(user["records"], 0, 128)
    if user["input_ref"] is None and values:
        raise reject()
    for index, raw in enumerate(values):
        item = obj(raw, {"index", "method", "path", "status"})
        integer(item["index"], index, index)
        integer(item["status"], 100, 599)
        if (
            item["method"] not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
            or item["path"] != "/[redacted]"
        ):
            raise reject()


def serialize_model_input(
    projection: object,
    *,
    projection_ref: object,
    owner_id: str,
    run_id: str,
    binding_ref: object,
    policy_digest: str,
) -> bytes:
    """Return verified canonical carrier bytes; NO_MODEL is not lifted here."""
    try:
        value = envelope(projection, "model-projection")
        pin = reference(projection_ref, "model-projection")
        body = obj(value["payload"], FIELDS)
        if ref(value) != pin or (body["owner_id"], body["run_id"]) != (
            uuid(owner_id),
            uuid(run_id),
        ):
            raise reject()
        integer(body["version"], 1, 1)
        for key, kind in REFS.items():
            reference(body[key], kind)
        if body["runtime_binding_ref"] != reference(binding_ref, "runtime-binding") or body[
            "policy_digest"
        ] != sha(policy_digest):
            raise reject()
        sha(body["approval_digest"])
        provenance = obj(body["provenance"], {"producer_revision", "source_kind"})
        if provenance != {"producer_revision": "model-projection-v1", "source_kind": "SYNTHETIC"}:
            raise reject()
        _content(body["model_input"], body)
        raw = canonical(body["model_input"])
        if len(raw) > 32768 or digest(raw) != sha(body["projection_digest"]):
            raise reject()
        return raw
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise reject() from None


def validate_serialized_input(
    raw: bytes,
    projection: object,
    *,
    projection_ref: object,
    owner_id: str,
    run_id: str,
    binding_ref: object,
    policy_digest: str,
) -> bytes:
    """Inspect the actual whole serialized carrier, with no ignored extra field."""
    try:
        if type(raw) is not bytes or len(raw) > 32768:
            raise reject()
        actual = loads(raw, 32768)
        expected = serialize_model_input(
            projection,
            projection_ref=projection_ref,
            owner_id=owner_id,
            run_id=run_id,
            binding_ref=binding_ref,
            policy_digest=policy_digest,
        )
        if canonical(actual) != raw or raw != expected:
            raise reject()
        return raw
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise reject() from None
