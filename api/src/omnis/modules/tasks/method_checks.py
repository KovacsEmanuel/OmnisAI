"""Deterministic consumer of authenticated native CONTRACT/PURE receipts.

Trust boundary: the owner authenticates the native final, validates its manifest
and binding, and freezes/persists the exact result and qualified schema material
before calling here. Record digests verify integrity, NOT native authenticity.
This checker never executes a handler, evaluator, or native result builder.
"""

import re

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, schema, validate
from omnis.modules.tasks import managed_contract as contract

Data = dict[str, object]
RECEIPT = "METHOD_RECEIPT_MISMATCH"
CONFLICT = "RESULT_CONFLICT"
UNSUPPORTED = "METHOD_UNSUPPORTED"
STEP_IDS = ("parse-capture", "normalize-operations", "build-map")


def _exact(value: object, fields: set[str], reason: str) -> Data:
    try:
        return contract.exact(value, fields)
    except (CatalogError, TypeError, ValueError, RecursionError):
        raise CatalogError(reason) from None


def _record(value: object, kind: str, reason: str) -> Data:
    try:
        return contract.record(value, kind)
    except (CatalogError, TypeError, ValueError, RecursionError):
        raise CatalogError(reason) from None


def _refs(value: object, kind: str | None = None) -> list[Data]:
    return [contract.ref(r, kind) for r in contract.sequence(value)]


def _same(left: object, right: object, reason: str) -> None:
    if canonical(left) != canonical(right):
        raise CatalogError(reason)


def _binding(binding: object, brief: Data, execution: Data) -> Data:
    result = _record(binding, "runtime-binding", RECEIPT)
    body = _exact(
        result["payload"],
        {
            "runtime_boot",
            "run_id",
            "ticket",
            "native_root_id",
            "entries",
            "authority",
        },
        RECEIPT,
    )
    for key in ("runtime_boot", "run_id", "ticket"):
        uuid_string(body[key])
    contract.authority(body["authority"])
    root = contract.text(body["native_root_id"], 128)
    entries = contract.sequence(body["entries"])
    if len(entries) != 1:
        raise CatalogError(RECEIPT)
    entry = _exact(
        entries[0],
        {
            "batch_index",
            "task_id",
            "attempt_id",
            "brief_ref",
            "composition_ref",
            "native_child_id",
            "native_session_id",
        },
        RECEIPT,
    )
    contract.integer(entry["batch_index"], 0, 0)
    contract.ref(entry["composition_ref"], "prompt-composition")
    contract.ref(entry["brief_ref"], "task-brief")
    header = contract.mapping(contract.mapping(brief["payload"])["header"])
    for key in ("task_id", "attempt_id"):
        uuid_string(entry[key])
        _same(entry[key], header[key], RECEIPT)
    _same(body["run_id"], header["run_id"], RECEIPT)
    _same(entry["brief_ref"], records.reference(brief), RECEIPT)
    _same(execution["brief_ref"], records.reference(brief), RECEIPT)
    for key in ("native_child_id", "native_session_id"):
        contract.text(entry[key], 128)
        contract.text(execution[key], 128)
        _same(entry[key], execution[key], RECEIPT)
    if root == entry["native_child_id"]:
        raise CatalogError(RECEIPT)
    return result


def _procedure(bound: Data, original: Data, actions: list[Data]) -> tuple[Data, list[Data]]:
    procedure = contract.mapping(contract.mapping(bound["payload"])["resolved_procedure"])
    version = 2 if original["kind"] == "contract-case-records" else 1
    contract.validate_capture_procedure(procedure, records.reference(original), version=version)
    if (
        procedure["verification_kind"] != "CONTRACT"
        or procedure["requested_effect_ceiling"] != "PURE"
    ):
        raise CatalogError(UNSUPPORTED)
    for key in (
        "preconditions",
        "applicability_predicate_ids",
        "invalidation_predicate_ids",
        "requested_capabilities",
        "identity_requirements",
        "business_rule_refs",
        "evidence_requirements",
        "stop_reason_ids",
    ):
        if procedure[key] != []:
            raise CatalogError(UNSUPPORTED)
    if procedure["oracle_ref"] is not None or "SUCCEEDED" not in contract.sequence(
        procedure["outcomes"]
    ):
        raise CatalogError(UNSUPPORTED)
    steps = [contract.mapping(s) for s in contract.sequence(procedure["probe"])]
    if [s["id"] for s in steps] != list(STEP_IDS[version - 1 :]):
        raise CatalogError(UNSUPPORTED)
    action_records = [_record(a, "action_definition", RECEIPT) for a in actions]
    if len({contract.text(a["id"]) for a in action_records}) != len(action_records):
        raise CatalogError(RECEIPT)
    output_schemas: set[bytes] = set()
    for step in steps:
        if step["tool_ref"] is not None or step["parameters"] != {}:
            raise CatalogError(UNSUPPORTED)
        action_ref = contract.ref(step["action_definition_ref"], "action_definition")
        matches = [
            a for a in action_records if canonical(records.reference(a)) == canonical(action_ref)
        ]
        if len(matches) != 1:
            raise CatalogError(RECEIPT)
        _same(
            matches[0]["payload"],
            {
                "handler_id": "contract." + contract.text(step["id"], 128),
                "execution_class": "PURE",
                "allowed_capability_ids": [],
                "dispatch_permitted": False,
            },
            RECEIPT,
        )
        schema_ref = contract.ref(step["output_schema_ref"], "schema")
        if canonical(schema_ref) in output_schemas:
            raise CatalogError(UNSUPPORTED)
        output_schemas.add(canonical(schema_ref))
    return procedure, steps


def _input(original: Data, body: Data, procedure: Data, owner_id: str) -> None:
    payload = _exact(
        original["payload"],
        {
            "version",
            "value",
            "schema_ref",
            "owner_id",
            "context_ref",
            "provenance",
        },
        RECEIPT,
    )
    contract.integer(payload["version"], 1, 1)
    contract.ref(payload["schema_ref"], "schema")
    contract.ref(payload["context_ref"], "contract-input-context")
    uuid_string(payload["owner_id"])
    _same(payload["schema_ref"], procedure["input_schema_ref"], RECEIPT)
    # Catalog ownership and the supervisor's lease owner are separate domains.
    _same(payload["owner_id"], owner_id, RECEIPT)
    _same(body["input_artifact_refs"], [records.reference(original)], RECEIPT)
    provenance = _exact(
        payload["provenance"],
        {
            "producer_key",
            "producer_revision",
            "command_id",
            "source_kind",
        },
        RECEIPT,
    )
    uuid_string(provenance["command_id"])
    _same(
        provenance,
        {
            "producer_key": original["kind"],
            "producer_revision": contract.text(original["kind"]) + "-v1",
            "command_id": provenance["command_id"],
            "source_kind": "SYNTHETIC",
        },
        RECEIPT,
    )
    if len(canonical(original)) > 8192:
        raise CatalogError("METHOD_OUTPUT_LIMIT")


def _receipts(
    raw_records: object,
    original: Data,
    brief: Data,
    binding: Data,
    execution: Data,
    steps: list[Data],
) -> tuple[Data, list[Data], list[Data]]:
    published = contract.sequence(raw_records)
    count = len(steps)
    if len(published) != 2 + count * 2:
        raise CatalogError(RECEIPT)
    result = _record(published[0], "task-result", CONFLICT)
    receipts = [_record(r, "contract-tool-receipt", RECEIPT) for r in published[1 : count + 2]]
    artifacts = [_record(a, "contract-artifact", RECEIPT) for a in published[count + 2 :]]
    identities = [contract.text(r["id"]) for r in [result, *receipts, *artifacts, original]]
    if len(set(identities)) != len(identities):
        raise CatalogError(RECEIPT)
    header = contract.mapping(brief["payload"])["header"]
    previous = records.reference(original)
    for index, receipt in enumerate(receipts):
        body = _exact(
            receipt["payload"],
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
            RECEIPT,
        )
        contract.integer(body["sequence"], index, index)
        contract.ref(body["binding_ref"], "runtime-binding")
        _refs(body["input_refs"])
        contract.ref(body["output_ref"])
        expected: Data = {
            "header": header,
            "binding_ref": records.reference(binding),
            "native_child_id": execution["native_child_id"],
            "native_session_id": execution["native_session_id"],
            "sequence": index,
            "operation": "READ_INPUT" if index == 0 else "PURE_ACTION",
            "step_id": None if index == 0 else steps[index - 1]["id"],
            "action_definition_ref": None
            if index == 0
            else steps[index - 1]["action_definition_ref"],
            "input_refs": [previous],
            "output_ref": previous if index == 0 else records.reference(artifacts[index - 1]),
        }
        if index:
            contract.ref(body["action_definition_ref"], "action_definition")
        _same(body, expected, RECEIPT)
        previous = contract.ref(body["output_ref"])
    for artifact, step in zip(artifacts, steps, strict=True):
        body = _exact(artifact["payload"], {"header", "schema_ref", "value"}, RECEIPT)
        contract.ref(body["schema_ref"], "schema")
        _same(body["header"], header, RECEIPT)
        _same(body["schema_ref"], step["output_schema_ref"], RECEIPT)
    return result, receipts, artifacts


def _results(
    result: Data,
    brief: Data,
    procedure: Data,
    receipts: list[Data],
    artifacts: list[Data],
    original: Data,
) -> list[object]:
    body = _exact(
        result["payload"],
        {
            "header",
            "status",
            "method_results",
            "method_review",
            "gaps",
            "usage",
            *contract.RESULT_EMPTY,
        },
        CONFLICT,
    )
    brief_body = contract.mapping(brief["payload"])
    _same(body["header"], brief_body["header"], CONFLICT)
    if body["status"] != "SUCCEEDED" or body["method_review"] is not None or body["gaps"] != []:
        raise CatalogError(CONFLICT)
    _same(
        body["usage"],
        {"state": "KNOWN", "model_calls": 0, "target_actions": 0, "cost": "0"},
        CONFLICT,
    )
    for field in contract.RESULT_EMPTY:
        expected = (
            [records.reference(original)]
            if field == "consumed_input_refs"
            else [records.reference(r) for r in receipts[1:]]
            if field == "action_refs"
            else []
        )
        _same(body[field], expected, CONFLICT)
    plan = contract.sequence(contract.mapping(brief_body["method_plan"])["requirements"])
    requirements = contract.sequence(procedure["method_requirements"])
    results = contract.sequence(body["method_results"])
    if len(results) != len(plan) or len(results) != len(requirements):
        raise CatalogError(CONFLICT)
    known_steps = [contract.mapping(r["payload"])["step_id"] for r in receipts[1:]]
    known_schemas = [contract.mapping(a["payload"])["schema_ref"] for a in [original, *artifacts]]
    for raw, raw_plan, raw_requirement in zip(results, plan, requirements, strict=True):
        row = _exact(raw, {"ref", "state", "basis_refs", "artifact_refs", "reason"}, CONFLICT)
        requirement = contract.mapping(raw_requirement)
        if requirement["applies_if"] != [] or requirement["evidence_kinds"] != []:
            raise CatalogError(UNSUPPORTED)
        steps = contract.sequence(requirement["step_ids"])
        schemas = _refs(requirement["artifact_schema_refs"], "schema")
        if (
            len({canonical(s) for s in steps}) != len(steps)
            or any(s not in known_steps for s in steps)
            or len({canonical(s) for s in schemas}) != len(schemas)
            or any(canonical(s) not in [canonical(k) for k in known_schemas] for s in schemas)
        ):
            raise CatalogError(UNSUPPORTED)
        _same(row["ref"], contract.mapping(raw_plan)["ref"], CONFLICT)
        if row["state"] != "DONE":
            raise CatalogError(CONFLICT)
        contract.text(row["reason"])
        _refs(row["basis_refs"], "contract-tool-receipt")
        _refs(row["artifact_refs"])
        _same(
            row["basis_refs"],
            [
                records.reference(r)
                for r in receipts[1:]
                if contract.mapping(r["payload"])["step_id"] in steps
            ],
            CONFLICT,
        )
        _same(
            row["artifact_refs"],
            [
                records.reference(a)
                for a in [original, *artifacts]
                if canonical(contract.mapping(a["payload"])["schema_ref"])
                in [canonical(s) for s in schemas]
            ],
            CONFLICT,
        )
    return results


def _lexical(document: object, value: object) -> None:
    """Match the native full-string grammar, not JSON Schema's final-LF '$'."""
    if not isinstance(document, dict):
        return
    if "pattern" in document and isinstance(value, str):
        if re.fullmatch(contract.text(document["pattern"]), value) is None:
            raise CatalogError("METHOD_SCHEMA_MISMATCH")
    properties = document.get("properties")
    if isinstance(properties, dict) and isinstance(value, dict):
        for key, definition in properties.items():
            if key in value:
                _lexical(definition, value[key])
    if "items" in document and isinstance(value, list):
        for child in value:
            _lexical(document["items"], child)


def _schemas(original: Data, artifacts: list[Data], schemas: dict[str, Data]) -> None:
    for item in [original, *artifacts]:
        body = contract.mapping(item["payload"])
        schema_ref = contract.ref(body["schema_ref"], "schema")
        try:
            key = canonical(schema_ref).decode()
            if type(schemas) is not dict or key not in schemas:
                raise CatalogError("METHOD_SCHEMA_UNAVAILABLE")
            document = contract.mapping(schemas[key])
            raw = schema(canonical(document))  # Supported, bounded, no external resolution.
        except (CatalogError, TypeError, ValueError, RecursionError):
            raise CatalogError("METHOD_SCHEMA_UNAVAILABLE") from None
        try:
            validate(raw, body["value"])
            _lexical(document, body["value"])
        except (CatalogError, TypeError, ValueError, RecursionError):
            raise CatalogError("METHOD_SCHEMA_MISMATCH") from None


def check_execution(
    brief: object,
    bound: object,
    binding: object,
    execution: object,
    checker_ref: object,
    input_record: object,
    actions: list[dict[str, object]],
    schemas: dict[str, dict[str, object]],
    owner_id: str,
) -> dict[str, object]:
    """Return COMPLETE only for the exact receipt chain; malformed/unknown refuses.

    Caller owns native authentication, qualification and persistence. This pure
    function validates retained record references and never creates execution
    evidence. Nonempty bound predicates are deliberately unsupported.
    """
    try:
        checked_brief = contract.validate_brief(brief)
        contract.validate_assignment(checked_brief, bound)
        checked_bound = _record(bound, "bound-procedure", RECEIPT)
        checked_execution = _exact(
            execution,
            {
                "native_child_id",
                "native_session_id",
                "brief_ref",
                "records",
            },
            RECEIPT,
        )
        try:
            contract.ref(checked_execution["brief_ref"], "task-brief")
            checked_binding = _binding(binding, checked_brief, checked_execution)
            original = contract.record(input_record)
            if original["kind"] not in ("contract-case-input", "contract-case-records"):
                raise CatalogError(RECEIPT)
        except CatalogError:
            raise CatalogError(RECEIPT) from None
        procedure, steps = _procedure(checked_bound, original, actions)
        body = contract.mapping(checked_brief["payload"])
        try:
            _input(original, body, procedure, uuid_string(owner_id))
            result, receipts, artifacts = _receipts(
                checked_execution["records"],
                original,
                checked_brief,
                checked_binding,
                checked_execution,
                steps,
            )
        except CatalogError as error:
            if error.reason in (CONFLICT, "METHOD_OUTPUT_LIMIT"):
                raise
            raise CatalogError(RECEIPT) from None
        identities = [
            contract.text(r["id"])
            for r in [
                checked_brief,
                checked_bound,
                checked_binding,
                original,
                *actions,
                result,
                *receipts,
                *artifacts,
            ]
        ]
        if len(set(identities)) != len(identities):
            raise CatalogError(RECEIPT)
        for limits in (body["limits"], procedure["limits"]):
            if contract.integer(contract.mapping(limits)["max_actions"], 1, 300) < len(steps):
                raise CatalogError("METHOD_ACTION_LIMIT")
        maximum = min(
            contract.integer(contract.mapping(body["limits"])["max_output_bytes"], 1, 1048576),
            contract.integer(contract.mapping(procedure["limits"])["max_output_bytes"], 1, 1048576),
        )
        if (
            len(canonical(checked_execution["records"])) > maximum
            or len(canonical(checked_execution)) > 32768
        ):
            raise CatalogError("METHOD_OUTPUT_LIMIT")
        _schemas(original, artifacts, schemas)
        try:
            checked_results = _results(
                result, checked_brief, procedure, receipts, artifacts, original
            )
        except CatalogError as error:
            if error.reason == UNSUPPORTED:
                raise
            raise CatalogError(CONFLICT) from None
        return records.envelope(
            "method-check",
            {
                "brief_ref": records.reference(checked_brief),
                "task_result_ref": records.reference(result),
                "checker_ref": contract.ref(checker_ref, "method-checker"),
                "status": "COMPLETE",
                "checked_results": checked_results,
                "gap_refs": [],
                "reason": "Exact bound CONTRACT/PURE receipts and published requirements checked.",
            },
        )
    except CatalogError:
        raise
    except (KeyError, TypeError, ValueError, RecursionError):
        raise CatalogError(CONFLICT) from None
