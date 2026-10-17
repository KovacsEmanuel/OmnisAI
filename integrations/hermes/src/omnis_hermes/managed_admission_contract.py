"""Exact, bounded managed cold-admission v1. No native import or authority by goal."""

from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit

from .native_preparation_contract import (
    bounded,
    canonical,
    digest,
    loads,
    obj,
    reference,
    sha,
    text,
    uuid,
)

PROTOCOL = "omnis-managed-admission-v1"
PROTOCOL_V2 = "omnis-managed-admission-v2"
PROTOCOL_V3 = "omnis-managed-admission-v3"
PROTOCOL_V4 = "omnis-managed-admission-v4"
OPS = frozenset(
    {
        "task_stage",
        "task_release",
        "task_status",
        "task_model_preflight",
        "task_model_initialize",
    }
)
RPC = {op: "omnis.managed." + op.removeprefix("task_") for op in OPS}
MAX_BYTES = 32768


PROTOCOL_V5 = "omnis-managed-admission-v5"
MODEL_TEST_REQUESTED = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}


def validate_model_prepare(value: object) -> dict[str, object]:
    """Separate DATA contract; the v1-v4 readers and their guards stay closed."""
    bounded(value)
    p = obj(value, {"protocol", "mode", "context", "records", "material"})
    if p["protocol"] != PROTOCOL_V5 or p["mode"] not in ("CREATE", "STATUS"):
        raise ValueError("Invalid model preparation")
    context = envelope(p["context"], "model-test-context")
    c = obj(context["payload"], {
        "version", "purpose", "owner_id", "run_id", "manifest_ref", "settings_operation_id",
        "authority", "runtime_boot", "preparation_id", "managed_run_ref", "task_id", "attempt_id",
        "batch_index", "brief_ref", "composition_ref", "source_manifest_ref", "preparation_receipt_ref",
        "original_selection_ref", "snapshot_ref", "selection_ref", "provider_config_ref", "procedure_ref",
        "package_refs", "material_digest", "resolved_index_digest", "requested", "effective",
        "account_status", "inference_status",
    })
    for field, kind in (("original_selection_ref", "execution-selection"),
                        ("source_manifest_ref", "launch-manifest"),
                        ("preparation_receipt_ref", "native-preparation-receipt"),
                        ("procedure_ref", "procedure")):
        reference(c[field], kind)
    if type(c) is not dict or c.get("purpose") != "MODEL_TEST_PREPARE":
        raise ValueError("Invalid preparation purpose")
    _integer(c.get("version"), 5, 5)
    _integer(c.get("batch_index"), 0, 0)
    _authority(c.get("authority"))
    for key in ("owner_id", "run_id", "preparation_id", "runtime_boot", "task_id", "attempt_id", "settings_operation_id"):
        uuid(c.get(key))
    if (c.get("requested") != MODEL_TEST_REQUESTED or c.get("effective") is not None
            or c.get("account_status") != "NOT_VERIFIED" or c.get("inference_status") != "HOLD"):
        raise ValueError("Preparation cannot assert account or inference authority")
    rows = p["records"]
    if type(rows) is not list or len(rows) != 7:
        raise ValueError("Invalid preparation records")
    kinds = {"managed_run_ref": "managed-run", "snapshot_ref": "run-snapshot",
             "selection_ref": "execution-selection", "provider_config_ref": "provider-config",
             "brief_ref": "task-brief", "composition_ref": "prompt-composition",
             "manifest_ref": "launch-manifest"}
    checked = {}
    for field, kind in kinds.items():
        pin = reference(c.get(field), kind)
        matches = [envelope(r, kind) for r in rows if type(r) is dict and r.get("kind") == kind]
        if len(matches) != 1 or ref(matches[0]) != pin:
            raise ValueError("Preparation reference mismatch")
        checked[field] = matches[0]["payload"]
    s = checked["selection_ref"]
    snapshot = checked["snapshot_ref"]
    config = checked["provider_config_ref"]
    reference(snapshot["profile_ref"], "profile")
    if (snapshot["dependency_closure_refs"] != [] or snapshot["dependency_artifact_refs"] != []
            or snapshot["assessment_selectable"] is not False or snapshot["effective"] is not None
            or snapshot["resolution"] != "PREPARATION_ONLY"):
        raise ValueError("Invalid preparation-only snapshot closure")
    if (s.get("snapshot_ref") != c["snapshot_ref"] or s.get("purpose") != c["purpose"]
            or s.get("requested") != MODEL_TEST_REQUESTED or s.get("effective") is not None
            or s.get("resolution") != "PREPARATION_ONLY"
            or s.get("selected_package_refs") != c.get("package_refs")
            or snapshot.get("execution_purpose") != c["purpose"]
            or snapshot.get("original_selection_ref") != c.get("original_selection_ref")
            or snapshot.get("preparation_receipt_ref") != c.get("preparation_receipt_ref")):
        raise ValueError("Invalid qualified selection/snapshot")
    expected_config = {"version": 2, "owner_id": c["owner_id"], "run_id": c["run_id"],
        "settings_operation_id": c["settings_operation_id"],
        "provenance": "NATIVE_SETTINGS_SAVED_SELECTION_READBACK_V2",
        "requested": MODEL_TEST_REQUESTED, "api_mode": "codex_responses",
        "reasoning_config": {"enabled": True, "effort": "xhigh"},
        "fallback": None, "auxiliary": False, "fast": False,
        "account_status": "NOT_VERIFIED", "inference_status": "HOLD"}
    if canonical(config) != canonical(expected_config) or len(canonical(config)) > 2048:
        raise ValueError("Invalid qualified configuration")
    from .native_preparation_contract import validate_payload

    validate_payload(p["material"])
    material = p["material"]["bundle"]["payload"]
    if (material["selection_ref"] != c.get("original_selection_ref")
            or material["snapshot_ref"] != snapshot.get("original_snapshot_ref")
            or material["candidate_snapshot_ref"] != snapshot.get("snapshot_ref")):
        raise ValueError("Original material lineage mismatch")
    for key in ("material_digest", "resolved_index_digest"):
        sha(c.get(key))
        if c[key] != snapshot.get(key) or c[key] != material[key]:
            raise ValueError("Material digest mismatch")
    if material["publication_ref"] != snapshot.get("publication_ref"):
        raise ValueError("Publication mismatch")
    if sorted((x["package_ref"] for x in material["packages"]), key=canonical) != sorted(c["package_refs"], key=canonical):
        raise ValueError("Package closure mismatch")
    brief, composition, manifest = (checked[k] for k in ("brief_ref", "composition_ref", "manifest_ref"))
    for key in ("run_id", "task_id", "attempt_id", "batch_index", "selection_ref"):
        if brief.get(key) != c[key]:
            raise ValueError("Brief identity mismatch")
    if (brief.get("purpose") != c["purpose"] or brief.get("allowed_capability_ids") != []
            or composition.get("purpose") != c["purpose"]
            or composition.get("brief_ref") != c["brief_ref"]
            or composition.get("preparation_receipt_ref") != c["preparation_receipt_ref"]
            or composition.get("package_refs") != c["package_refs"]
            or composition.get("text") != brief.get("objective")
            or sha(composition.get("text_digest")) != digest(composition["text"].encode())):
        raise ValueError("Composition mismatch")
    expected_entry = {k: c[k] for k in ("batch_index", "task_id", "attempt_id", "brief_ref", "composition_ref")}
    if (manifest != {"purpose": c["purpose"], "run_id": c["run_id"], "selection_ref": c["selection_ref"], "entries": [expected_entry]}
            or checked["managed_run_ref"].get("selection_ref") != c["selection_ref"]
            or c["managed_run_ref"]["id"] != c["run_id"]):
        raise ValueError("Indexed manifest mismatch")
    if len(canonical(p)) > MAX_BYTES:
        raise ValueError("Preparation payload limit")
    # Account for actual escaping and complete host/native envelopes before allocation.
    import json
    for frame in ({"jsonrpc": "2.0", "id": "f" * 36, "method": "omnis.managed.model_initialize", "params": p},
                  {"version": 1, "id": "f" * 36, "boot": "f" * 36, "capability": "f" * 64,
                   "generation": 2**63-1, "epoch": 2**63-1, "deadline_ns": 2**63-1,
                   "op": "task_model_initialize", "payload": p}):
        if len(json.dumps(frame, separators=(",", ":"), allow_nan=False).encode()) + 1 > 65536:
            raise ValueError("Preparation wire limit")
    return loads(canonical(p), MAX_BYTES)


@dataclass(frozen=True, slots=True)
class ModelTestPreparation:
    raw: bytes

    def payload(self):
        if type(self.raw) is not bytes:
            raise ValueError("Immutable preparation required")
        p = validate_model_prepare(loads(self.raw, MAX_BYTES))
        if p["mode"] != "CREATE" or canonical(p) != self.raw:
            raise ValueError("Canonical preparation CREATE required")
        return p

    def __post_init__(self):
        self.payload()


def preparation_result(payload, *, native_root_id=None, native_child_id=None,
                       native_session_id=None, native_turn=None):
    p = validate_model_prepare(payload)
    c = p["context"]["payload"]
    result = {"protocol": PROTOCOL_V5, "context_ref": ref(p["context"]),
              "runtime_boot": c["runtime_boot"], "authority": c["authority"],
              "status": "UNKNOWN" if native_turn is None else "TURN_BOUND_PRE_CLIENT_HOLD",
              "native_root_id": native_root_id, "native_child_id": native_child_id,
              "native_session_id": native_session_id, "native_turn": native_turn,
              "observed_configuration_ref": c["provider_config_ref"],
              "client_status": "DEFERRED_NO_CREDENTIAL", "model_calls": 0,
              "inference_status": "HOLD", "account_status": "NOT_VERIFIED"}
    return validate_preparation_result(result, p)


def validate_preparation_result(value, payload):
    p = validate_model_prepare(payload)
    v = obj(value, {"protocol", "context_ref", "runtime_boot", "authority", "status",
                   "native_root_id", "native_child_id", "native_session_id", "native_turn",
                   "observed_configuration_ref", "client_status", "model_calls",
                   "inference_status", "account_status"})
    c = p["context"]["payload"]
    if (v["protocol"] != PROTOCOL_V5 or v["context_ref"] != ref(p["context"])
            or canonical(v["authority"]) != canonical(c["authority"])
            or v["runtime_boot"] != c["runtime_boot"]
            or v["observed_configuration_ref"] != c["provider_config_ref"]
            or v["inference_status"] != "HOLD" or v["account_status"] != "NOT_VERIFIED"
            or v["client_status"] != "DEFERRED_NO_CREDENTIAL"):
        raise ValueError("Invalid preparation observation bindings")
    _integer(v["model_calls"], 0, 0)
    if v["status"] == "UNKNOWN":
        if any(v[k] is not None for k in ("native_root_id", "native_child_id", "native_session_id", "native_turn")):
            raise ValueError("Unknown preparation has identities")
    elif v["status"] == "TURN_BOUND_PRE_CLIENT_HOLD":
        uuid(v["native_root_id"])
        uuid(v["native_child_id"])
        text(v["native_session_id"], 128)
        turn = obj(v["native_turn"], {"task_id", "turn_id"})
        if turn["task_id"] != c["task_id"]:
            raise ValueError("Wrong preparation turn task")
        text(turn["turn_id"], 256)
    else:
        raise ValueError("Invalid preparation status")
    return loads(canonical(v), MAX_BYTES)


def validate_model_preflight(value: object) -> bytes:
    from .model_admission import validate_preflight

    return validate_preflight(value)


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
    unique = (
        ["task_id", "attempt_id", "brief_ref"]
        + (["composition_ref"] if composed else [])
        + (["native_child_id", "native_session_id"] if native else [])
    )
    if any(len({canonical(e[k]) for e in value}) != len(value) for k in unique):
        raise ValueError("Duplicate managed identity")
    return cast(list[dict[str, object]], value)


def wire(value: object, fields: set[str]) -> dict[str, object]:
    bounded(value)
    value = obj(value, fields | {"protocol"})
    if (
        value["protocol"] not in (PROTOCOL, PROTOCOL_V2, PROTOCOL_V3, PROTOCOL_V4)
        or len(canonical(value)) > MAX_BYTES
    ):
        raise ValueError("Invalid managed protocol")
    return value


def validate_stage(value: object) -> dict[str, object]:
    composed = type(value) is dict and value.get("protocol") in (
        PROTOCOL_V2,
        PROTOCOL_V3,
        PROTOCOL_V4,
    )
    compact = type(value) is dict and "record_pool" in value
    value = wire(
        value,
        ({"manifest", "compositions"} | ({"record_pool"} if compact else set()))
        if composed
        else {"manifest"},
    )
    if compact and value["protocol"] != PROTOCOL_V4:
        raise ValueError("Invalid compact assignment protocol")
    result = envelope(value["manifest"], "launch-manifest")
    fields = {"run_id", "selection_ref", "resolution", "effective", "entries"}
    if composed:
        fields.add("composition_version")
    payload = obj(result["payload"], fields)
    if composed and (
        type(payload["composition_version"]) is not int
        or payload["composition_version"]
        not in (
            (4,)
            if value["protocol"] == PROTOCOL_V4
            else (3,)
            if value["protocol"] == PROTOCOL_V3
            else (1, 2)
        )
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
        from .prompt_bundle import compact_refs, composition_pool, validate_composition

        compositions = value["compositions"]
        if type(compositions) is not list or len(compositions) != len(rows):
            raise ValueError("Incomplete compositions")
        if len(rows) != 2 and any(
            type(c) is dict
            and type(c.get("payload")) is dict
            and c["payload"].get("format") == "record-refs-v2"
            for c in compositions
        ):
            raise ValueError("Shared material requires batch2")
        if value["protocol"] == PROTOCOL_V4 and len(rows) == 2:
            bodies = [envelope(c, "prompt-composition")["payload"] for c in compositions]
            if not compact or any(
                type(b) is not dict or b.get("format") != "record-refs-v2" for b in bodies
            ):
                raise ValueError("Batch2 shared material required")
            from .prompt_bundle import mapping, sequence

            common = [
                [
                    mapping(b)["prompt_bundle_ref"],
                    mapping(b)["preparation_receipt_ref"],
                    *[sequence(mapping(b)["sections"])[i] for i in (0, 1, 3, 4)],
                ]
                for b in bodies
            ]
            if canonical(common[0]) != canonical(common[1]):
                raise ValueError("Batch2 common material mismatch")
        if compact:
            wanted: dict[str, dict[str, object]] = {}
            for composition in compositions:
                for pin in compact_refs(envelope(composition, "prompt-composition")["payload"]):
                    identity = str(pin["id"])
                    if identity in wanted and canonical(wanted[identity]) != canonical(pin):
                        raise ValueError("Conflicting compact refs")
                    wanted[identity] = pin
            pool = value["record_pool"]
            if type(pool) is not list or len(pool) != len(wanted):
                raise ValueError("Incomplete compact union")
            for item, pin in zip(pool, wanted.values(), strict=True):
                if canonical(ref(envelope(item, str(pin["kind"])))) != canonical(pin):
                    raise ValueError("Invalid compact union")
        for composition, entry in zip(compositions, rows, strict=True):
            body = envelope(composition, "prompt-composition")["payload"]
            if type(body) is not dict or compact != ("format" in body):
                raise ValueError("Invalid compact assignment shape")
            raw = validate_composition(
                composition,
                result,
                entry,
                record_pool=(composition_pool(body, value["record_pool"]) if compact else None),
            )
            if value["protocol"] == PROTOCOL_V4 and len(rows) == 2:
                from .contract_method import assignment_material

                assignment_material(raw)
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
        payload["entries"],
        native=True,
        composed=value["protocol"] in (PROTOCOL_V2, PROTOCOL_V3, PROTOCOL_V4),
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
    success = value.get("protocol") == PROTOCOL_V4 and value.get("status") in (
        "SUCCEEDED",
        "INCONCLUSIVE",
    )
    final = value.get("status") == "BLOCKED" or success
    keys = {"status", "ticket", "manifest_ref", "native_root_id", "entries"}
    if final:
        keys |= {"reason", "binding_ref"}
    if success:
        keys.add("executions")
    value = wire(value, keys)
    validate_status({k: value[k] for k in ("protocol", "ticket", "manifest_ref")})
    if final:
        if value["reason"] != ("CONTRACT_PURE" if success else "NO_MODEL"):
            raise ValueError("Invalid native refusal")
        reference(value["binding_ref"], "runtime-binding")
    elif value["status"] != "STAGED":
        raise ValueError("Invalid native stage")
    text(value["native_root_id"])
    rows = entries(
        value["entries"],
        native=True,
        composed=value["protocol"] in (PROTOCOL_V2, PROTOCOL_V3, PROTOCOL_V4),
    )
    if value["protocol"] == PROTOCOL_V4 and final and not success:
        raise ValueError("Invalid CONTRACT response")
    if success:
        executions = value["executions"]
        if type(executions) is not list or len(executions) != len(rows):
            raise ValueError("Invalid CONTRACT executions")
        for emitted, row in zip(executions, rows, strict=True):
            execution = obj(
                emitted,
                {"native_child_id", "native_session_id", "brief_ref", "records"},
            )
            if any(
                execution[k] != row[k]
                for k in ("native_child_id", "native_session_id", "brief_ref")
            ):
                raise ValueError("Invalid CONTRACT native execution binding")
            records = execution["records"]
            if type(records) is not list or len(records) not in (4, 6, 8):
                raise ValueError("Invalid CONTRACT records")
            kinds = [
                obj(r, {"schema_version", "kind", "id", "revision", "payload", "digest"})["kind"]
                for r in records
            ]
            steps = (len(records) - 2) // 2
            if (
                kinds
                != ["task-result"]
                + ["contract-tool-receipt"] * (steps + 1)
                + ["contract-artifact"] * steps
            ):
                raise ValueError("Invalid CONTRACT record order")
            if len(
                {envelope(r, cast(str, k))["id"] for r, k in zip(records, kinds, strict=True)}
            ) != len(records):
                raise ValueError("Duplicate CONTRACT records")
            from .contract_method import RESULT_EMPTY

            result = obj(
                records[0]["payload"],
                {
                    "header",
                    "status",
                    "method_results",
                    "method_review",
                    "gaps",
                    "usage",
                    *RESULT_EMPTY,
                },
            )
            if (
                result["status"] != value["status"]
                or result["method_review"] is not None
                or (value["status"] == "INCONCLUSIVE" and not result["gaps"])
                or result["usage"]
                != {"state": "KNOWN", "model_calls": 0, "target_actions": 0, "cost": "0"}
            ):
                raise ValueError("Invalid CONTRACT TaskResult")
            from .prompt_bundle import prose
            from .prompt_bundle import sequence as items

            for gap in items(result["gaps"]):
                prose(gap)
            header = _result_header(result["header"])
            if any(header[k] != row[k] for k in ("task_id", "attempt_id")):
                raise ValueError("Invalid CONTRACT result assignment")
            _criterion_results(result["criterion_results"])
            for sequence, record in enumerate(records[1 : steps + 2]):
                receipt = obj(
                    record["payload"],
                    {
                        "header",
                        "binding_ref",
                        "native_child_id",
                        "native_session_id",
                        "sequence",
                        "operation",
                        "step_id",
                        "action_definition_ref",
                        "input_refs",
                        "output_ref",
                    },
                )
                if (
                    receipt["header"] != result["header"]
                    or receipt["binding_ref"] != value["binding_ref"]
                    or any(
                        receipt[k] != execution[k] for k in ("native_child_id", "native_session_id")
                    )
                    or type(receipt["sequence"]) is not int
                    or receipt["sequence"] != sequence
                    or receipt["operation"] != ("READ_INPUT" if sequence == 0 else "PURE_ACTION")
                ):
                    raise ValueError("Invalid CONTRACT receipt")
                if sequence == 0:
                    if (
                        receipt["step_id"] is not None
                        or receipt["action_definition_ref"] is not None
                    ):
                        raise ValueError("Invalid CONTRACT input read")
                else:
                    text(receipt["step_id"])
                    reference(receipt["action_definition_ref"], "action_definition")
                if type(receipt["input_refs"]) is not list or len(receipt["input_refs"]) != 1:
                    raise ValueError("Invalid CONTRACT input refs")
                reference(receipt["input_refs"][0])
                reference(receipt["output_ref"])
            for record in records[steps + 2 :]:
                artifact = obj(record["payload"], {"header", "schema_ref", "value"})
                reference(artifact["schema_ref"], "schema")
                if artifact["header"] != result["header"]:
                    raise ValueError("Invalid CONTRACT artifact header")
    return value


def _result_header(value: object) -> dict[str, object]:
    header = obj(
        value,
        set(
            "schema_version run_id task_id attempt_id snapshot_ref mission_revision focus_ref through_cursor brief_revision result_schema_ref".split()
        ),
    )
    _integer(header["schema_version"], 1, 1)
    _integer(header["brief_revision"], 1, 1)
    for name in ("run_id", "task_id", "attempt_id", "through_cursor"):
        uuid(header[name])
    for name, kind in (
        ("snapshot_ref", "run-snapshot"),
        ("mission_revision", "mission"),
        ("focus_ref", "focus"),
        ("result_schema_ref", "schema"),
    ):
        reference(header[name], kind)
    return header


def _criterion_results(value: object) -> None:
    from .prompt_bundle import key, prose, sequence

    seen = set()
    for raw in sequence(value, 0, 16):
        row = obj(
            raw,
            {
                "criterion_id",
                "bound_procedure_ref",
                "control_step_ids",
                "evidence_refs",
                "proposed_outcome",
                "gaps",
            },
        )
        criterion_id = uuid(row["criterion_id"])
        bound = reference(row["bound_procedure_ref"], "bound-procedure")
        _integer(bound["revision"], 1, 1)
        pair = canonical([criterion_id, bound])
        if pair in seen or text(row["proposed_outcome"], 16) not in (
            "PASS",
            "FAIL",
            "BLOCKED",
            "INCONCLUSIVE",
        ):
            raise ValueError("Invalid criterion result")
        seen.add(pair)
        controls = [key(s) for s in sequence(row["control_step_ids"])]
        evidence = [reference(r) for r in sequence(row["evidence_refs"])]
        if len(set(controls)) != len(controls) or len({canonical(r) for r in evidence}) != len(
            evidence
        ):
            raise ValueError("Invalid criterion result")
        for gap in sequence(row["gaps"]):
            prose(gap)


_INITIALIZATION_FIELDS = {
    "version",
    "mode",
    "initialization_id",
    "intent_ref",
    "owner_id",
    "run_id",
    "manifest_ref",
    "runtime_boot",
    "authority",
    "provider_config",
    "producer_receipt",
    "initialization_data",
    "source_byte_digest",
    "initialization_data_digest",
}
_CONFIGURATION_FIELDS = {
    "provider",
    "model_id",
    "base_url",
    "api_mode",
    "reasoning_config",
    "max_tokens",
    "capabilities",
    "technical_caps",
    "native_config",
}
_INITIALIZATION_BINDINGS = {
    "protocol",
    "version",
    "initialization_id",
    "intent_ref",
    "owner_id",
    "run_id",
    "manifest_ref",
    "runtime_boot",
    "authority",
    "source_byte_digest",
    "initialization_data_digest",
}


def _exact_data(value: object, depth: int = 0) -> None:
    # Check BEFORE canonical serialization: subclasses must not be laundered.
    if depth > 16:
        raise ValueError("Invalid initialization DATA")
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise ValueError("Invalid initialization key")
            _exact_data(key, depth + 1)
            _exact_data(child, depth + 1)
    elif type(value) is str:
        if any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in "\u2028\u2029" for c in value):
            raise ValueError("Invalid initialization string")
    elif type(value) not in (int, bool, type(None)):
        raise ValueError("Invalid initialization type")


def _integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid initialization integer")
    return value


def _authority(value: object) -> dict[str, object]:
    result = obj(value, {"instance_id", "owner", "epoch", "generation"})
    uuid(result["instance_id"])
    uuid(result["owner"])
    _integer(result["epoch"], 1, 2**63 - 1)
    _integer(result["generation"], 0, 2**63 - 1)
    return result


def _configuration(value: object) -> dict[str, object]:
    _exact_data(value)
    config = obj(value, _CONFIGURATION_FIELDS | {"version", "decision_id"})
    _integer(config["version"], 1, 1)
    uuid(config["decision_id"])
    for key in ("provider", "model_id"):
        v = text(config[key], 256)
        if v != v.strip():
            raise ValueError("Invalid configuration identity")
    url = text(config["base_url"], 1024)
    try:
        route = urlsplit(url)
        port = route.port
    except ValueError:
        raise ValueError("Invalid configuration URL") from None
    if (
        url != url.strip()
        or any(ord(c) < 33 for c in url)
        or route.scheme != "https"
        or not route.hostname
        or route.username is not None
        or route.password is not None
        or "?" in url
        or "#" in url
        or route.netloc.endswith(":")
        or (port is not None and not 1 <= port <= 65535)
        or config["api_mode"] != "chat_completions"
    ):
        raise ValueError("Invalid configuration route")
    reasoning = config["reasoning_config"]
    if reasoning is not None:
        reasoning = obj(reasoning, {"enabled", "effort"})
        if type(reasoning["enabled"]) is not bool:
            raise ValueError("Invalid reasoning flag")
        if reasoning["effort"] is not None:
            text(reasoning["effort"], 64)
    caps = obj(config["technical_caps"], {"calls", "output_tokens", "wall_seconds"})
    _integer(caps["calls"], 1, 1)
    output = _integer(caps["output_tokens"], 1, 65536)
    _integer(caps["wall_seconds"], 1, 1200)
    _integer(config["max_tokens"], 1, output)
    capabilities = config["capabilities"]
    if (
        type(capabilities) is not dict
        or len(capabilities) > 16
        or any(
            type(k) is not str or not k or len(k) > 64 or type(v) is not bool
            for k, v in capabilities.items()
        )
    ):
        raise ValueError("Invalid capabilities")
    native = obj(
        config["native_config"],
        {"reasoning_echo", "prompt_caching", "context_length", "compression"},
    )
    if type(native["reasoning_echo"]) is not bool or type(native["prompt_caching"]) is not bool:
        raise ValueError("Invalid native policy")
    _integer(native["context_length"], 1024, 900000)
    compression = obj(native["compression"], {"enabled"})
    if type(compression["enabled"]) is not bool or len(canonical(config)) > 2048:
        raise ValueError("Invalid compression/configuration bound")
    return config


def validate_initialization(value: object) -> dict[str, object]:
    """Validate DATA, not origin/dispatch authority. Private owner/Host grants remain required."""
    if type(value) is dict and value.get("protocol") == PROTOCOL_V5:
        return validate_model_prepare(value)
    _exact_data(value)
    value = wire(value, _INITIALIZATION_FIELDS)
    if value["protocol"] != PROTOCOL_V3 or value["mode"] not in ("CREATE", "STATUS"):
        raise ValueError("Invalid initialization protocol/mode")
    _integer(value["version"], 1, 1)
    for key in ("initialization_id", "owner_id", "run_id", "runtime_boot"):
        uuid(value[key])
    reference(value["intent_ref"], "native-initialization-intent")
    reference(value["manifest_ref"], "launch-manifest")
    _authority(value["authority"])
    source = envelope(value["provider_config"], "provider-config")
    body = obj(
        source["payload"],
        {
            "version",
            "owner_id",
            "run_id",
            "manifest_ref",
            "authority",
            "configuration",
            "provenance",
            "status",
            "inference_authorized",
        },
    )
    _integer(body["version"], 1, 1)
    _authority(body["authority"])
    reference(body["manifest_ref"], "launch-manifest")
    if (
        any(body[k] != value[k] for k in ("owner_id", "run_id", "manifest_ref", "authority"))
        or body["provenance"] != "PRIVATE_OWNER_CONFIGURATION_COMMAND_V1"
        or body["status"] != "READY"
        or body["inference_authorized"] is not False
    ):
        raise ValueError("Invalid initialization source bindings")
    config = _configuration(body["configuration"])
    receipt = envelope(value["producer_receipt"], "contract-input-command")
    command = obj(
        receipt["payload"],
        {
            "version",
            "owner_id",
            "command_id",
            "operation",
            "request_digest",
            "result_refs",
        },
    )
    _integer(command["version"], 1, 1)
    uuid(command["owner_id"])
    uuid(command["command_id"])
    sha(command["request_digest"])
    refs = obj(command["result_refs"], {"provider_config_ref"})
    reference(refs["provider_config_ref"], "provider-config")
    request = {
        "manifest_ref": value["manifest_ref"],
        "configuration": config,
        "authority": value["authority"],
    }
    if (
        command["owner_id"] != value["owner_id"]
        or command["command_id"] != config["decision_id"]
        or command["operation"] != "model_configuration"
        or refs["provider_config_ref"] != ref(source)
        or command["request_digest"] != digest(canonical(request))
    ):
        raise ValueError("Invalid initialization producer receipt")
    raw = value["initialization_data"]
    if type(raw) is not str:
        raise ValueError("Invalid initialization bytes")
    parsed = loads(raw, 2048)
    if (
        canonical(parsed) != raw.encode("utf-8")
        or canonical(parsed) != canonical({k: config[k] for k in _CONFIGURATION_FIELDS})
        or sha(value["source_byte_digest"]) != digest(canonical(source))
        or sha(value["initialization_data_digest"]) != digest(raw.encode("utf-8"))
    ):
        raise ValueError("Invalid initialization digests/bytes")
    # Every return is detached, including nested refs, source and receipt.
    return cast(dict[str, object], loads(canonical(value), MAX_BYTES))


@dataclass(frozen=True, slots=True)
class OwnedInitialization:
    """Immutable qualified DATA carrier. Its Python type is not model/turn authority."""

    raw: bytes

    def __post_init__(self) -> None:
        if type(self.raw) is not bytes:
            raise ValueError("Immutable initialization bytes required")
        value = validate_initialization(loads(self.raw, MAX_BYTES))
        if value["mode"] != "CREATE" or canonical(value) != self.raw:
            raise ValueError("Canonical CREATE carrier required")

    def payload(self) -> dict[str, object]:
        if type(self.raw) is not bytes:
            raise ValueError("Immutable initialization bytes required")
        value = validate_initialization(loads(self.raw, MAX_BYTES))
        if value["mode"] != "CREATE" or canonical(value) != self.raw:
            raise ValueError("Canonical CREATE carrier required")
        return value


def initialization_result(
    payload: object,
    *,
    observation: object = None,
    native_session_id: object = None,
    native_instance_id: object = None,
) -> dict[str, object]:
    """Pure wire assembly only; native RPC supplies its actual live observation."""
    p = validate_initialization(payload)
    source = envelope(p["provider_config"], "provider-config")
    receipt = envelope(p["producer_receipt"], "contract-input-command")
    result: dict[str, object] = {k: p[k] for k in _INITIALIZATION_BINDINGS}
    result.update(
        provider_config_ref=ref(source),
        producer_receipt_ref=ref(receipt),
        status="UNKNOWN",
        native_session_id=None,
        native_instance_id=None,
        observed_configuration=None,
        observed_configuration_digest=None,
        client_status="DEFERRED_NO_CREDENTIAL",
        native_turn=None,
        inference_status="HOLD",
        model_calls=0,
    )
    if observation is not None:
        result.update(
            status="CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM",
            native_session_id=native_session_id,
            native_instance_id=native_instance_id,
            observed_configuration=observation,
            observed_configuration_digest=digest(canonical(observation)),
        )
    elif native_session_id is not None or native_instance_id is not None:
        raise ValueError("Unknown initialization cannot carry identities")
    return validate_initialization_result(result, p)


def validate_initialization_result(value: object, payload: object) -> dict[str, object]:
    if type(payload) is dict and payload.get("protocol") == PROTOCOL_V5:
        return validate_preparation_result(value, payload)
    p = validate_initialization(payload)
    _exact_data(value)
    value = wire(
        value,
        (_INITIALIZATION_BINDINGS - {"protocol"})
        | {
            "provider_config_ref",
            "producer_receipt_ref",
            "status",
            "native_session_id",
            "native_instance_id",
            "observed_configuration",
            "observed_configuration_digest",
            "client_status",
            "native_turn",
            "inference_status",
            "model_calls",
        },
    )
    _integer(value["version"], 1, 1)
    _integer(value["model_calls"], 0, 0)
    _authority(value["authority"])
    reference(value["intent_ref"], "native-initialization-intent")
    reference(value["manifest_ref"], "launch-manifest")
    reference(value["provider_config_ref"], "provider-config")
    reference(value["producer_receipt_ref"], "contract-input-command")
    if (
        any(value[k] != p[k] for k in _INITIALIZATION_BINDINGS)
        or value["provider_config_ref"] != ref(envelope(p["provider_config"], "provider-config"))
        or value["producer_receipt_ref"]
        != ref(envelope(p["producer_receipt"], "contract-input-command"))
        or value["client_status"] != "DEFERRED_NO_CREDENTIAL"
        or value["native_turn"] is not None
        or value["inference_status"] != "HOLD"
    ):
        raise ValueError("Invalid initialization observation binding")
    if value["status"] == "UNKNOWN":
        if any(
            value[k] is not None
            for k in (
                "native_session_id",
                "native_instance_id",
                "observed_configuration",
                "observed_configuration_digest",
            )
        ):
            raise ValueError("Unknown initialization cannot claim native success")
    elif value["status"] == "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM":
        text(value["native_session_id"])
        uuid(value["native_instance_id"])
        observed = obj(value["observed_configuration"], _CONFIGURATION_FIELDS)
        # Validate every leaf (strict bool/int distinction) as well as exact source equality.
        _configuration(
            {
                **observed,
                "version": 1,
                "decision_id": cast(
                    dict[str, object],
                    cast(
                        dict[str, object],
                        envelope(p["provider_config"], "provider-config")["payload"],
                    )["configuration"],
                )["decision_id"],
            }
        )
        if canonical(observed) != cast(str, p["initialization_data"]).encode("utf-8") or sha(
            value["observed_configuration_digest"]
        ) != digest(canonical(observed)):
            raise ValueError("Native observation differs from qualified configuration")
    else:
        raise ValueError("Invalid initialization status")
    return cast(dict[str, object], loads(canonical(value), MAX_BYTES))
