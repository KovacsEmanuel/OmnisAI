"""S01 ordered prompt composition adapted to inert canonical data.

No template evaluation, foreign runtime, model, tool or catalog discovery.
See upstream/composition-NOTICE.md for exact source and modifications.
"""

import base64
import binascii
import re
from datetime import datetime
from pathlib import Path
from typing import cast

from .managed_admission_contract import envelope, ref
from .native_preparation_contract import (
    bounded,
    canonical,
    digest,
    frontmatter,
    loads,
    obj,
    raw_text,
    reference,
    sha,
    text,
    uuid,
)

PROVENANCE = [
    {
        "repository": "https://github.com/usestrix/strix",
        "revision": "ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2",
        "path": "strix/agents/prompt.py",
        "source_digest": "2b30f1ecee988f9effed96c54af2baecd3a6506b6bcfdc5bd9a0f325cf540a33",
        "license_id": "Apache-2.0",
        "notice_paths": [
            "integrations/hermes/upstream/composition-NOTICE.md",
            "integrations/hermes/upstream/composition-LICENSE",
        ],
        "modification_note": "S01 adaptation: ordered base/role/assignment/method/selected-skill composition; first-party canonical JSON, strict immutable refs and fail-closed budgets. No Jinja, foreign runtime, implicit skills, model or tool execution.",
    }
]
BASE_TEXT = (
    "CONTRACT_PROBE. No provider, model, tools, targets, or domain reads. Return NO_MODEL only."
)
ROLE_TEXT = "SUPPORT-only cold admission probe; not an assessment."
CONTRACT_BASE_TEXT = (
    "CONTRACT_PROBE. Deterministic PURE method only; no provider, model, target or stock tools. "
    "Read only the bound assignment inputs."
)
CONTRACT_ROLE_TEXT = "SUPPORT-only native CONTRACT/PURE method; not an assessment."
# Explicit historical source allowlist; never reinterpret cold material as v4.
RECORDS_COMPOSER_REVISION = "55963352e1b855f51f379bdfb0cf0ff49b0004dacb40aad32ef85ea9f3b5828c"
LEGACY_COMPOSER_REVISION = "dfdd1ccad8ad93c13adb28bec45ac5d94d49f29ff53e8371cf6650107b67c11f"
CAPTURE_COMPOSER_REVISION = "70b0c25c4c844b4af292061987b961cabe6d4cc361f6cda79d8947eb11ccdd8a"
METHOD_COMPOSER_REVISION = "2cec176a5e622df2751e069b2a676c7e64578bea33b768aab63b09c78698f473"
COMPACT_COMPOSER_REVISION = "1d32db3dcd15ee65d9d479d0401675d255a856b36beaca1bde1093ed0fb0b00a"
CRITERIA_COMPOSER_REVISION = "717549a613365ec95c40276903a92bf9b603092232947e0ee79bf5e1745854ed"
PREDICATE_COMPOSER_REVISION = "4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850"
APPLICABILITY_COMPOSER_REVISION = "bcc1cdbf7b3546e1269e22875bbec2670504e73f25a3e198f65990fb56f31d99"
PRECONDITION_COMPOSER_REVISION = "065fda6c008f054909d144bf903e2097a6f3f39dbc9b437b0506c53e6eb24af8"
ROLES = {"RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH"}
BRIEF_FIELDS: set[str] = set(
    "header prompt_bundle_ref execution_selection_ref assessment_mode objective_summary non_goals role hypothesis operation_refs priority_reason done_when return_when context contradiction_refs prior_attempt_refs package_refs technique_refs procedure_refs procedure_bindings method_plan review_request criterion_bindings overlay_refs input_artifact_refs identities allowed_capability_ids limits deadline validation_reserve stop_conditions required_evidence".split()
)
LIMITS = {
    "max_attempts": 10,
    "max_actions": 300,
    "deadline_seconds": 1200,
    "max_output_bytes": 1048576,
    "max_fanout": 2,
}
PROCEDURE_FIELDS: set[str] = set(
    "schema_version key technique_ref verification_kind non_applicable_groups objective applicability_predicate_ids technologies input_schema_ref output_schema_ref preconditions method_requirements identity_requirements business_rule_refs requested_capabilities requested_effect_ceiling predicted_signal baseline probe control evidence_requirements oracle_ref slots false_positives invalidation_predicate_ids limits stop_reason_ids cleanup cleanup_not_needed_reason handoff_schema_ref outcomes".split()
)


def reject() -> ValueError:
    return ValueError("Invalid prompt composition")


def mapping(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise reject()
    return cast(dict[str, object], value)


def sequence(value: object, minimum: int = 0, maximum: int = 128) -> list[object]:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise reject()
    return cast(list[object], value)


def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise reject()
    return value


def authored(value: object) -> None:
    """Control-free authored data; only original LF/TAB are permitted."""
    if type(value) is str:
        raw_text(value.encode("utf-8"))
    elif type(value) is dict:
        for key, child in value.items():
            authored(key)
            authored(child)
    elif type(value) is list:
        for child in value:
            authored(child)


def key(value: object) -> str:
    result = text(value)
    if re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", result) is None:
        raise reject()
    return result


def prose(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 4096:
        raise reject()
    raw_text(value.encode("utf-8"))
    return value


def limits(value: object) -> dict[str, object]:
    result = obj(value, set(LIMITS))
    for name, maximum in LIMITS.items():
        integer(result[name], 1, maximum)
    return result


def refs(value: object, kind: str, minimum: int = 1, maximum: int = 128) -> list[object]:
    items = sequence(value, minimum, maximum)
    identities = set()
    for item in items:
        checked = reference(item, kind)
        if checked["id"] in identities:
            raise reject()
        identities.add(checked["id"])
    return items


def composer_revision() -> str:
    """Attest installed source, not an impossible self-referential literal."""
    return digest(Path(__file__).read_bytes())


def compose(
    prompt_bundle: object,
    preparation_receipt_ref: object,
    sections: object,
    *,
    version: int | None = None,
) -> dict[str, object]:
    bounded(sections)
    authored(sections)
    raw = canonical(sections)
    result = {
        "prompt_bundle": envelope(prompt_bundle, "prompt-bundle"),
        "preparation_receipt_ref": reference(preparation_receipt_ref, "native-preparation-receipt"),
        "text": raw.decode("utf-8"),
        "text_digest": digest(raw),
        "byte_count": len(raw),
        "token_upper_bound": len(raw),
    }
    _material(result, version)
    return result


def requirement_conditions(procedure: object, input_ref: object) -> None:
    p = mapping(procedure)
    source = reference(input_ref, "contract-case-records")
    condition_groups = [
        p["preconditions"],
        *[mapping(r)["applies_if"] for r in sequence(p["method_requirements"], 1)],
    ]
    for group in condition_groups:
        conditions = sequence(group)
        if not conditions:
            continue
        if p["key"] != "map-records" or len(conditions) != 1:
            raise reject()
        condition = obj(conditions[0], {"predicate_id", "input_refs", "expected", "on_missing"})
        refs(condition["input_refs"], "contract-case-records", 1, 1)
        if (
            condition["predicate_id"] != "contract.records-nonempty"
            or type(condition["expected"]) is not bool
            or condition["on_missing"] not in ("BLOCKED", "INCONCLUSIVE")
            or canonical(condition["input_refs"]) != canonical([source])
        ):
            raise reject()


def invalidation_declaration(procedure: object) -> None:
    p = mapping(procedure)
    ids = sequence(p["invalidation_predicate_ids"])
    if ids and (
        type(p["key"]) is not str
        or p["key"] != "map-records"
        or len(ids) != 1
        or type(ids[0]) is not str
        or ids[0] != "contract.records-empty"
    ):
        raise reject()


def require_not_invalidated(procedure: object, original: object = None) -> None:
    """Finite admission guard, not external freshness or ResultQualification."""
    p = mapping(procedure)
    invalidation_declaration(p)
    if not p["invalidation_predicate_ids"]:
        return
    if original is None:
        raise ValueError("PROCEDURE_INVALIDATION_UNKNOWN")
    source = mapping(sequence(mapping(sequence(p["probe"])[0])["input_bindings"])[0])["source_ref"]
    available = envelope(original, "contract-case-records")
    if canonical(ref(available)) != canonical(reference(source, "contract-case-records")):
        raise reject()
    payload = mapping(available["payload"])
    if canonical(reference(payload["schema_ref"], "schema")) != canonical(
        reference(p["input_schema_ref"], "schema")
    ):
        raise reject()
    value = obj(payload["value"], {"records"})
    if not sequence(value["records"]):
        raise ValueError("PROCEDURE_INVALIDATED")


def require_preconditions(procedure: object, original: object = None) -> None:
    """Independent finite preflight from retained constructor-owned material."""
    p = mapping(procedure)
    conditions = sequence(p["preconditions"])
    if not conditions:
        return
    source = mapping(sequence(mapping(sequence(p["probe"])[0])["input_bindings"])[0])["source_ref"]
    requirement_conditions(p, source)
    condition = mapping(conditions[0])
    if original is None:
        raise ValueError("PROCEDURE_PRECONDITION_UNKNOWN_" + text(condition["on_missing"]))
    available = envelope(original, "contract-case-records")
    if canonical(ref(available)) != canonical(source):
        raise reject()
    value = obj(mapping(available["payload"])["value"], {"records"})
    if (len(sequence(value["records"])) != 0) is not condition["expected"]:
        raise ValueError("PROCEDURE_PRECONDITION_FALSE")


def method_plan(bound: object, original: object = None) -> list[dict[str, object]]:
    b = envelope(bound, "bound-procedure")
    p = mapping(mapping(b["payload"])["resolved_procedure"])
    conditional = any(mapping(r)["applies_if"] for r in sequence(p["method_requirements"], 1))
    available = None
    if conditional:
        input_ref = mapping(sequence(mapping(sequence(p["probe"])[0])["input_bindings"])[0])[
            "source_ref"
        ]
        requirement_conditions(p, input_ref)
        if original is not None:
            available = envelope(original, "contract-case-records")
            if canonical(ref(available)) != canonical(input_ref):
                raise reject()
    rows: list[dict[str, object]] = []
    for raw in sequence(p["method_requirements"], 1):
        r = mapping(raw)
        state, basis = "APPLIES", []
        if r["applies_if"]:
            if available is None:
                state = "UNKNOWN"
            else:
                value = obj(mapping(available["payload"])["value"], {"records"})
                present = len(sequence(value["records"])) != 0
                condition = mapping(sequence(r["applies_if"])[0])
                state = "APPLIES" if present is condition["expected"] else "NOT_APPLICABLE"
                basis = [ref(available)]
        rows.append(
            {
                "ref": {"bound_procedure_ref": ref(b), "requirement_key": r["key"]},
                "applicability": state,
                "applicability_basis_refs": basis,
                "required": r["required"],
            }
        )
    return rows


def _procedure(value: object, *, capture_bound: bool = False) -> dict[str, object]:
    p = obj(value, PROCEDURE_FIELDS)
    invalidation_declaration(p)
    integer(p["schema_version"], 1, 1)
    key(p["key"])
    if (
        p["verification_kind"] != "CONTRACT"
        or p["requested_effect_ceiling"] != "PURE"
        or p["oracle_ref"] is not None
    ):
        raise reject()
    for field in (
        "applicability_predicate_ids",
        "identity_requirements",
        "business_rule_refs",
        "requested_capabilities",
        "evidence_requirements",
        "slots",
        "stop_reason_ids",
    ):
        if p[field] != []:
            raise reject()
    for field in ("objective", "predicted_signal"):
        prose(p[field])
    if p["cleanup_not_needed_reason"] is not None:
        prose(p["cleanup_not_needed_reason"])
    sequence(p["technologies"])
    for item in sequence(p["false_positives"]):
        prose(item)
    for item in sequence(p["non_applicable_groups"]):
        row = obj(item, {"group", "reason"})
        if row["group"] not in ("BASELINE", "CONTROL"):
            raise reject()
        prose(row["reason"])
    outcomes = sequence(p["outcomes"], 1)
    if "BLOCKED" not in outcomes or any(
        item
        not in (
            "SUCCEEDED",
            "INCONCLUSIVE",
            "BLOCKED",
            "FAILED",
            "CANCELLED",
            "NEEDS_RECONCILIATION",
        )
        for item in outcomes
    ):
        raise reject()
    reference(p["technique_ref"], "technique")
    for field in ("input_schema_ref", "output_schema_ref", "handoff_schema_ref"):
        reference(p[field], "schema")
    limits(p["limits"])
    step_ids = set()
    for group in ("baseline", "probe", "control", "cleanup"):
        for item in sequence(p[group]):
            step = obj(
                item,
                set(
                    "id action_definition_ref tool_ref parameter_schema_ref parameters input_bindings output_schema_ref".split()
                ),
            )
            step_id = key(step["id"])
            if step_id in step_ids:
                raise reject()
            step_ids.add(step_id)
            reference(step["action_definition_ref"], "action_definition")
            if step["tool_ref"] is not None:
                reference(step["tool_ref"], "tool")
            reference(step["parameter_schema_ref"], "schema")
            reference(step["output_schema_ref"], "schema")
            mapping(step["parameters"])
            binding_names = set()
            for binding in sequence(step["input_bindings"]):
                b = obj(binding, {"name", "source_ref", "selector"})
                name = key(b["name"])
                if name in binding_names:
                    raise reject()
                binding_names.add(name)
                if b["selector"] is not None:
                    key(b["selector"])
                source = mapping(b["source_ref"])
                if source.get("kind") == "STEP_OUTPUT":
                    obj(source, {"kind", "step_id", "output_name"})
                    key(source["step_id"])
                    key(source["output_name"])
                else:
                    reference(source)
                    if (
                        source["kind"] in ("contract-case-input", "contract-case-records")
                        and not capture_bound
                    ):
                        raise reject()
    seen = set()
    for item in sequence(p["method_requirements"], 1):
        requirement = obj(
            item,
            set(
                "key description required applies_if step_ids artifact_schema_refs evidence_kinds".split()
            ),
        )
        name = key(requirement["key"])
        if (
            name in seen
            or type(requirement["required"]) is not bool
            or requirement["evidence_kinds"] != []
        ):
            raise reject()
        seen.add(name)
        prose(requirement["description"])
        for required_step in sequence(requirement["step_ids"]):
            if key(required_step) not in step_ids:
                raise reject()
        refs(requirement["artifact_schema_refs"], "schema", 0)
    return p


# Fixed trusted registry, bound through the published records requirements.
RECORD_PREDICATES = {
    "normalize-records": ("normalize-operations", "OUTPUT"),
    "build-surface-map": ("build-map", "OUTPUT"),
    "preserve-input-context": ("normalize-operations", "INPUT"),
}


def predicate_closure(procedure: object) -> dict[str, dict[str, object]]:
    p = mapping(procedure)
    if not {"key", "input_schema_ref", "probe", "method_requirements"} <= set(p):
        raise reject()
    if key(p["key"]) != "map-records":
        raise reject()
    reference(p["input_schema_ref"], "schema")
    steps: dict[str, dict[str, object]] = {}
    for raw in sequence(p["probe"]):
        row = mapping(raw)
        if not {"id", "output_schema_ref"} <= set(row):
            raise reject()
        name = key(row["id"])
        reference(row["output_schema_ref"], "schema")
        if name in steps:
            raise reject()
        steps[name] = row
    if list(steps) != ["normalize-operations", "build-map"]:
        raise reject()
    requirements = [mapping(r) for r in sequence(p["method_requirements"])]
    for row in requirements:
        if set(row) != {
            "key",
            "description",
            "required",
            "applies_if",
            "step_ids",
            "artifact_schema_refs",
            "evidence_kinds",
        }:
            raise reject()
        key(row["key"])
        for step_id in sequence(row["step_ids"]):
            key(step_id)
        for schema_ref in sequence(row["artifact_schema_refs"]):
            reference(schema_ref, "schema")
    if [r["key"] for r in requirements] != list(RECORD_PREDICATES):
        raise reject()
    result: dict[str, dict[str, object]] = {}
    for requirement in requirements:
        name = key(requirement["key"])
        step, source = RECORD_PREDICATES[name]
        schema = p["input_schema_ref"] if source == "INPUT" else steps[step]["output_schema_ref"]
        if (
            requirement["step_ids"] != [step]
            or requirement["artifact_schema_refs"] != [schema]
            or requirement["evidence_kinds"] != []
            or type(requirement["required"]) is not bool
            or requirement["required"] is not (source == "OUTPUT")
        ):
            raise reject()
        result[name] = requirement
    return result


def validate_predicates(
    body: object,
    bound: object,
    *,
    prompt_bundle: object = None,
    composition_version: object = None,
) -> None:
    b = mapping(body)
    for field in ("done_when", "return_when"):
        seen: set[bytes] = set()
        for raw in sequence(b[field]):
            row = obj(raw, {"bound_procedure_ref", "predicate_id"})
            reference(row["bound_procedure_ref"], "bound-procedure")
            key(row["predicate_id"])
            if canonical(row) in seen:
                raise reject()
            seen.add(canonical(row))
    r = envelope(bound, "bound-procedure")
    required = False
    if prompt_bundle is not None:
        bundle = envelope(prompt_bundle, "prompt-bundle")
        if canonical(reference(b["prompt_bundle_ref"], "prompt-bundle")) != canonical(ref(bundle)):
            raise reject()
        version = integer(composition_version, 1, 4)
        pin = mapping(bundle["payload"])["composer_revision"]
        revisions = {
            composer_revision(),
            PRECONDITION_COMPOSER_REVISION,
            PREDICATE_COMPOSER_REVISION,
            APPLICABILITY_COMPOSER_REVISION,
            CRITERIA_COMPOSER_REVISION,
            COMPACT_COMPOSER_REVISION,
            METHOD_COMPOSER_REVISION,
        }
        if version <= 3:
            revisions.add(RECORDS_COMPOSER_REVISION)
        if version <= 2:
            revisions.add(CAPTURE_COMPOSER_REVISION)
        if version == 1:
            revisions.add(LEGACY_COMPOSER_REVISION)
        if type(pin) is not str or pin not in revisions:
            raise reject()
        procedure = mapping(mapping(r["payload"])["resolved_procedure"])
        if procedure["invalidation_predicate_ids"] and (version != 4 or pin != composer_revision()):
            raise reject()
        required = (
            version == 4
            and pin
            in {
                composer_revision(),
                PRECONDITION_COMPOSER_REVISION,
                PREDICATE_COMPOSER_REVISION,
                APPLICABILITY_COMPOSER_REVISION,
            }
            and procedure["key"] == "map-records"
        )
        if (b["done_when"] or b["return_when"]) and (
            version != 4
            or pin
            not in {
                composer_revision(),
                PRECONDITION_COMPOSER_REVISION,
                PREDICATE_COMPOSER_REVISION,
                APPLICABILITY_COMPOSER_REVISION,
            }
        ):
            raise reject()
    if not b["done_when"] and not b["return_when"] and not required:
        return  # Structural-only calls confer no completion; consumers supply the retained bundle.

    closure = predicate_closure(mapping(r["payload"])["resolved_procedure"])
    for field in ("done_when", "return_when"):
        for raw in sequence(b[field]):
            row = mapping(raw)
            if (
                canonical(row["bound_procedure_ref"]) != canonical(ref(r))
                or row["predicate_id"] not in closure
            ):
                raise reject()
    if [mapping(r)["predicate_id"] for r in sequence(b["done_when"])] != list(closure) or not b[
        "return_when"
    ]:
        raise reject()


def _brief(
    value: object,
    method: dict[str, object],
    bundle: dict[str, object],
    capture: dict[str, object] | None = None,
    composition_version: int = 1,
) -> dict[str, object]:
    body = obj(value, BRIEF_FIELDS)
    role = text(body["role"])
    if (
        role not in ROLES
        or body["assessment_mode"] != "FULL_ASSESSMENT"
        or body["review_request"] is not None
    ):
        raise reject()
    for field in (
        "operation_refs",
        "contradiction_refs",
        "prior_attempt_refs",
        "overlay_refs",
        "identities",
        "allowed_capability_ids",
        "stop_conditions",
        "required_evidence",
    ):
        if body[field] != []:
            raise reject()
    for field in ("objective_summary", "hypothesis", "priority_reason"):
        prose(body[field])
    if not sequence(body["criterion_bindings"], 0, 16) and "SUPPORT" not in prose(
        body["priority_reason"]
    ):
        raise reject()
    for item in sequence(body["non_goals"]):
        prose(item)
    if reference(body["prompt_bundle_ref"], "prompt-bundle") != ref(bundle):
        raise reject()
    reference(body["execution_selection_ref"], "execution-selection")
    refs(body["package_refs"], "package", 1, 2)
    refs(body["technique_refs"], "technique")
    refs(body["procedure_refs"], "procedure")
    header = obj(
        body["header"],
        set(
            "schema_version run_id task_id attempt_id snapshot_ref mission_revision focus_ref through_cursor brief_revision result_schema_ref".split()
        ),
    )
    integer(header["schema_version"], 1, 1)
    integer(header["brief_revision"], 1, 1)
    for field in ("run_id", "task_id", "attempt_id", "through_cursor"):
        uuid(header[field])
    for field, kind in (
        ("snapshot_ref", "run-snapshot"),
        ("mission_revision", "mission"),
        ("focus_ref", "focus"),
        ("result_schema_ref", "schema"),
    ):
        reference(header[field], kind)
    input_name, input_kind = _input_contract(1 if capture is None else capture["version"])
    input_refs = [] if capture is None else [ref(envelope(capture["input"], input_kind))]
    refs(body["input_artifact_refs"], input_kind, len(input_refs), len(input_refs))
    if canonical(body["input_artifact_refs"]) != canonical(input_refs):
        raise reject()
    contexts = sequence(body["context"], 2 + len(input_refs), 2 + len(input_refs))
    for item, expected in zip(
        contexts,
        [header["mission_revision"], header["focus_ref"], *input_refs],
        strict=True,
    ):
        context = obj(item, {"ref", "epistemic_state", "summary", "mandatory"})
        if (
            reference(context["ref"]) != expected
            or context["epistemic_state"] != "OBSERVED"
            or context["mandatory"] is not True
        ):
            raise reject()
        prose(context["summary"])
    deadline = text(body["deadline"], 64)
    if not deadline.endswith("Z"):
        raise reject()
    datetime.fromisoformat(deadline)
    reserve = obj(body["validation_reserve"], {"actions", "seconds"})
    integer(reserve["actions"], 0, 0)
    integer(reserve["seconds"], 0, 0)
    bound = obj(
        method["payload"],
        {"procedure_ref", "slot_values", "resolved_procedure", "mission_ref"},
    )
    reference(bound["procedure_ref"], "procedure")
    validate_predicates(body, method, prompt_bundle=bundle, composition_version=composition_version)
    if (body["done_when"] or body["return_when"]) and mapping(bundle["payload"])[
        "composer_revision"
    ] not in {
        composer_revision(),
        PRECONDITION_COMPOSER_REVISION,
        PREDICATE_COMPOSER_REVISION,
        APPLICABILITY_COMPOSER_REVISION,
    }:
        raise reject()
    reference(bound["mission_ref"], "mission")
    slots = [] if capture is None else [{"slot_name": input_name, "refs": input_refs}]
    if bound["mission_ref"] != header["mission_revision"] or canonical(
        bound["slot_values"]
    ) != canonical(slots):
        raise reject()
    p = _procedure(bound["resolved_procedure"], capture_bound=capture is not None)
    if p["preconditions"] and (
        composition_version != 4
        or mapping(bundle["payload"])["composer_revision"]
        not in {composer_revision(), PRECONDITION_COMPOSER_REVISION}
    ):
        raise reject()
    require_preconditions(p, None if capture is None else capture["input"])
    if p["invalidation_predicate_ids"] and (
        composition_version != 4
        or mapping(bundle["payload"])["composer_revision"] != composer_revision()
    ):
        raise reject()
    require_not_invalidated(p, None if capture is None else capture["input"])
    expected_binding = {
        "procedure_ref": bound["procedure_ref"],
        "slot_values": slots,
        "bound_procedure_ref": ref(method),
    }
    bindings = sequence(body["procedure_bindings"], 1, 1)
    binding = obj(bindings[0], {"procedure_ref", "slot_values", "bound_procedure_ref"})
    reference(binding["procedure_ref"], "procedure")
    reference(binding["bound_procedure_ref"], "bound-procedure")
    if (
        canonical(bindings) != canonical([expected_binding])
        or body["procedure_refs"] != [bound["procedure_ref"]]
        or body["technique_refs"] != [p["technique_ref"]]
    ):
        raise reject()
    if any(mapping(r)["applies_if"] for r in sequence(p["method_requirements"])) and mapping(
        bundle["payload"]
    )["composer_revision"] not in {
        composer_revision(),
        PRECONDITION_COMPOSER_REVISION,
        APPLICABILITY_COMPOSER_REVISION,
    }:
        raise reject()
    expected_requirements = method_plan(method, None if capture is None else capture["input"])
    if any(r["applicability"] == "UNKNOWN" for r in expected_requirements):
        raise reject()
    plan = obj(body["method_plan"], {"requirements"})
    if canonical(plan["requirements"]) != canonical(expected_requirements):
        raise reject()
    seen_criteria = set()
    for raw in sequence(body["criterion_bindings"], 0, 16):
        row = obj(raw, {"criterion_id", "bound_procedure_ref", "step_ids", "outcome_rule_ref"})
        criterion_id = uuid(row["criterion_id"])
        bound_ref = reference(row["bound_procedure_ref"], "bound-procedure")
        rule_ref = reference(row["outcome_rule_ref"], "criterion-outcome-rule")
        integer(bound_ref["revision"], 1, 1)
        integer(rule_ref["revision"], 1, 1)
        steps = [key(s) for s in sequence(row["step_ids"], 1)]
        if (
            criterion_id in seen_criteria
            or bound_ref != ref(method)
            or steps != [mapping(s)["id"] for s in sequence(p["probe"])]
        ):
            raise reject()
        seen_criteria.add(criterion_id)
    chosen_limits, method_limits = limits(body["limits"]), limits(p["limits"])
    if any(cast(int, chosen_limits[k]) > cast(int, method_limits[k]) for k in LIMITS):
        raise reject()
    if capture is not None:
        _capture_assignment(capture, body, bound, p)
    return body


def _case_ref(value: object, kind: str) -> dict[str, object]:
    result = reference(value, kind)
    integer(result["revision"], 1, 2147483646)
    return result


def _input_contract(version: object) -> tuple[str, str]:
    checked = integer(version, 1, 2)
    return (
        ("records", "contract-case-records") if checked == 2 else ("capture", "contract-case-input")
    )


def _records_value(schema: dict[str, object], value: object) -> None:
    """Independent installed-handler language check; never executes a PURE step."""
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    pattern = r"^/[^\\\s]*$"
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["records"],
        "properties": {
            "records": {
                "type": "array",
                "maxItems": 128,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["method", "path", "status"],
                    "properties": {
                        "method": {"type": "string", "enum": methods},
                        "path": {
                            "type": "string",
                            "maxLength": 240,
                            "pattern": pattern,
                        },
                        "status": {"type": "integer", "minimum": 100, "maximum": 599},
                    },
                },
            }
        },
    }
    if canonical(schema) != canonical(expected) or len(canonical(value)) > 8192:
        raise reject()
    for raw in sequence(obj(value, {"records"})["records"], 0, 128):
        item = obj(raw, {"method", "path", "status"})
        if type(item["method"]) is not str or item["method"] not in methods:
            raise reject()
        path = item["path"]
        if type(path) is not str or len(path) > 240 or re.fullmatch(pattern, path) is None:
            raise reject()
        raw_text(path.encode("utf-8"))
        integer(item["status"], 100, 599)


def _capture_material(value: object, skills: list[object]) -> dict[str, object]:
    """Bounded synthetic input only; no source lookup, normalization or execution."""
    material = obj(value, {"section", "version", "context", "input", "schema"})
    version = integer(material["version"], 1, 2)
    name, kind = _input_contract(version)
    if material["section"] != "case-input":
        raise reject()
    context = envelope(material["context"], "contract-input-context")
    input_record = envelope(material["input"], kind)
    if len(canonical(input_record)) > 8192:
        raise reject()
    c = obj(
        context["payload"],
        set(
            "version namespace owner_id basis_ref snapshot_ref procedure_ref schema_ref selection_ref mission_ref focus_ref".split()
        ),
    )
    v = obj(
        input_record["payload"],
        set("version value schema_ref owner_id context_ref provenance".split()),
    )
    for body in (c, v):
        uuid(body["owner_id"])
        _case_ref(body["schema_ref"], "schema")
    integer(c["version"], version, version)
    integer(v["version"], 1, 1)
    if c["namespace"] != "RUN" or c["owner_id"] != v["owner_id"]:
        raise reject()
    for field, ref_kind in (
        ("basis_ref", "managed-run"),
        ("snapshot_ref", "run-snapshot"),
        ("procedure_ref", "procedure"),
        ("selection_ref", "execution-selection"),
        ("mission_ref", "mission"),
        ("focus_ref", "focus"),
    ):
        _case_ref(c[field], ref_kind)
    if _case_ref(v["context_ref"], "contract-input-context") != ref(context):
        raise reject()
    provenance = obj(
        v["provenance"],
        {"producer_key", "producer_revision", "command_id", "source_kind"},
    )
    uuid(provenance["command_id"])
    if {k: provenance[k] for k in ("producer_key", "producer_revision", "source_kind")} != {
        "producer_key": kind,
        "producer_revision": kind + "-v1",
        "source_kind": "SYNTHETIC",
    }:
        raise reject()
    s = obj(material["schema"], {"ref", "document", "path", "source_b64"})
    sr = _case_ref(s["ref"], "schema")
    if sr != c["schema_ref"] or sr != v["schema_ref"]:
        raise reject()
    path = _path(s["path"])
    try:
        raw = base64.b64decode(text(s["source_b64"], 10924), validate=True)
    except (ValueError, binascii.Error):
        raise reject() from None
    if base64.b64encode(raw).decode("ascii") != s["source_b64"]:
        raise reject()
    if not 1 <= len(raw) <= 8192 or raw_text(raw).startswith("\ufeff"):
        raise reject()
    schema = obj(
        s["document"],
        {"$schema", "type", "additionalProperties", "required", "properties"},
    )
    if (
        canonical(loads(raw, 8192)) != canonical(schema)
        or schema["$schema"] != "https://json-schema.org/draft/2020-12/schema"
        or schema["type"] != "object"
        or schema["additionalProperties"] is not False
        or schema["required"] != [name]
    ):
        raise reject()
    if version == 2:
        _records_value(schema, v["value"])
    else:
        prop = mapping(obj(schema["properties"], {"capture"})["capture"])
        obj(
            prop,
            {"type", "maxLength"} | ({"minLength"} if "minLength" in prop else set()),
        )
        maximum = integer(prop["maxLength"], 1, 65536)
        minimum = integer(prop.get("minLength", 0), 0, maximum)
        capture = obj(v["value"], {"capture"})["capture"]
        if (
            prop["type"] != "string"
            or type(capture) is not str
            or not minimum <= len(capture) <= maximum
            or len(capture.encode("utf-8")) > 4096
            or len(canonical(v["value"])) > 8192
        ):
            raise reject()
        raw_text(capture.encode("utf-8"))
    candidates = [
        mapping(k) for k in skills if mapping(mapping(k)["package_ref"])["digest"] == sr["digest"]
    ]
    if len(candidates) != 1:
        raise reject()
    files = [mapping(f) for f in sequence(candidates[0]["files"]) if mapping(f)["path"] == path]
    if (
        len(files) != 1
        or files[0]["sha256"] != digest(raw)
        or type(files[0]["size"]) is not int
        or files[0]["size"] != len(raw)
    ):
        raise reject()
    if context["id"] == input_record["id"]:
        raise reject()
    return material


def _capture_assignment(
    material: dict[str, object],
    brief: dict[str, object],
    bound: dict[str, object],
    p: dict[str, object],
) -> None:
    c = mapping(mapping(material["context"])["payload"])
    h = mapping(brief["header"])
    if mapping(c["basis_ref"])["id"] != h["run_id"] or any(
        c[k] != expected
        for k, expected in (
            ("snapshot_ref", h["snapshot_ref"]),
            ("selection_ref", brief["execution_selection_ref"]),
            ("mission_ref", h["mission_revision"]),
            ("focus_ref", h["focus_ref"]),
            ("procedure_ref", bound["procedure_ref"]),
            ("schema_ref", p["input_schema_ref"]),
        )
    ):
        raise reject()
    version = integer(material["version"], 1, 2)
    name, kind = _input_contract(version)
    if p["key"] != ("map-records" if version == 2 else "map-capture") or any(
        p[g] != [] for g in ("baseline", "control", "cleanup")
    ):
        raise reject()
    count = 2 if version == 2 else 3
    steps = sequence(p["probe"], count, count)
    expected: list[dict[str, object]] = [
        {
            "name": name,
            "source_ref": ref(envelope(material["input"], kind)),
            "selector": name,
        }
    ]
    if canonical(mapping(steps[0])["input_bindings"]) != canonical(expected):
        raise reject()
    for i, name in enumerate(("operations",) if version == 2 else ("records", "operations"), 1):
        expected = [
            {
                "name": name,
                "source_ref": {
                    "kind": "STEP_OUTPUT",
                    "step_id": mapping(steps[i - 1])["id"],
                    "output_name": name,
                },
                "selector": None,
            }
        ]
        if canonical(mapping(steps[i])["input_bindings"]) != canonical(expected):
            raise reject()


def _path(value: object) -> str:
    path = text(value, 256)
    parts = path.split("/")
    if any(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", p) is None for p in parts) or (
        len(parts) > 1
        and (
            parts[0] not in {"references", "templates", "assets", "scripts"} or "SKILL.md" in parts
        )
    ):
        raise reject()
    return path


def _skills(values: list[object], packages: object) -> None:
    refs(packages, "package", 1, 2)
    if len(values) != len(sequence(packages)):
        raise reject()
    names = set()
    total_bytes = total_files = methods = 0
    for item, package_ref in zip(values, sequence(packages), strict=True):
        skill = obj(item, {"section", "package_ref", "native_name", "files", "content"})
        if skill["section"] != "skill" or reference(skill["package_ref"], "package") != package_ref:
            raise reject()
        name = text(skill["native_name"], 64)
        if re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) is None or name in names:
            raise reject()
        names.add(name)
        files = sequence(skill["files"], 2, 16)
        paths = []
        declared = {}
        for item in files:
            file = obj(item, {"path", "sha256", "size"})
            path = _path(file["path"])
            size = integer(file["size"], 0, 8192)
            sha(file["sha256"])
            if path in declared:
                raise reject()
            declared[path] = file
            paths.append(path)
            total_bytes += size
            total_files += 1
        if (
            paths != sorted(paths, key=lambda p: p.encode("utf-8"))
            or not {"SKILL.md", "omnis.yaml"} <= set(paths)
            or digest(canonical(files)) != mapping(package_ref)["digest"]
        ):
            raise reject()
        included = set()
        for item in sequence(skill["content"], 1, 16):
            content = obj(item, {"path", "text"})
            path = _path(content["path"])
            if path in included or path not in declared or type(content["text"]) is not str:
                raise reject()
            raw = content["text"].encode("utf-8")
            raw_text(raw)
            if declared[path]["sha256"] != digest(raw) or declared[path]["size"] != len(raw):
                raise reject()
            if path == "SKILL.md":
                frontmatter(raw, name)
            else:
                # Exact selected technique.method_ref ownership is API-authoritative.
                # That mapping is not transmitted here; never invent a catalog read.
                if path == "omnis.yaml":
                    raise reject()
                methods += 1
            included.add(path)
        if "SKILL.md" not in included:
            raise reject()
    if not methods or total_files > 16 or total_bytes > 16384:
        raise reject()


def _material(
    payload: dict[str, object], version: int | None = None
) -> tuple[bytes, dict[str, object], dict[str, object]]:
    bounded(payload)
    authored(payload)
    bundle = envelope(payload["prompt_bundle"], "prompt-bundle")
    reference(payload["preparation_receipt_ref"], "native-preparation-receipt")
    b = obj(
        bundle["payload"],
        set(
            "base_ref role_refs composer_revision brief_schema result_schema package_refs max_context_bytes max_context_tokens tokenizer_revision provenance".split()
        ),
    )
    integer(b["brief_schema"], 1, 1)
    integer(b["result_schema"], 1, 1)
    if b["tokenizer_revision"] != "utf8-byte-upper-bound-v1" or b["provenance"] != PROVENANCE:
        raise reject()
    maximum = min(
        integer(b["max_context_bytes"], 1, 65536),
        integer(b["max_context_tokens"], 1, 65536),
        32768,
    )
    if type(payload["text"]) is not str:
        raise reject()
    raw = payload["text"].encode("utf-8")
    sections = sequence(loads(raw, maximum), 5, 7)
    has_capture = mapping(sections[4]).get("section") == "case-input"
    actual_version = 1 + integer(mapping(sections[4])["version"], 1, 2) if has_capture else 1
    contract_method = version == 4
    if contract_method:
        if not has_capture:
            raise reject()
        actual_version = 4
    revisions = {
        composer_revision(),
        PRECONDITION_COMPOSER_REVISION,
        PREDICATE_COMPOSER_REVISION,
        APPLICABILITY_COMPOSER_REVISION,
        METHOD_COMPOSER_REVISION,
        COMPACT_COMPOSER_REVISION,
        CRITERIA_COMPOSER_REVISION,
    }
    if actual_version <= 3:
        revisions.add(RECORDS_COMPOSER_REVISION)
    if actual_version <= 2:
        revisions.add(CAPTURE_COMPOSER_REVISION)
    if actual_version == 1:
        revisions.add(LEGACY_COMPOSER_REVISION)
    if (version is not None and version != actual_version) or b[
        "composer_revision"
    ] not in revisions:
        raise reject()
    if (
        canonical(sections) != raw
        or sha(payload["text_digest"]) != digest(raw)
        or integer(payload["byte_count"], 1, maximum) != len(raw)
        or integer(payload["token_upper_bound"], 1, maximum) != len(raw)
    ):
        raise reject()
    authored(sections)
    checked = []
    for item, label, kind in zip(
        sections[:4],
        ("base", "role", "brief", "method"),
        ("prompt-content", "prompt-content", "task-brief", "bound-procedure"),
        strict=True,
    ):
        section = obj(item, {"section", "record"})
        if section["section"] != label:
            raise reject()
        checked.append(envelope(section["record"], kind))
    if len({record["id"] for record in [bundle, *checked]}) != len(checked) + 1:
        raise reject()
    base, role, brief, method = checked
    if obj(base["payload"], {"text"}) != {
        "text": CONTRACT_BASE_TEXT if contract_method else BASE_TEXT
    } or reference(b["base_ref"], "prompt-content") != ref(base):
        raise reject()
    skill_sections = sections[5:] if has_capture else sections[4:]
    _skills(skill_sections, b["package_refs"])
    capture = _capture_material(sections[4], skill_sections) if has_capture else None
    if capture is not None and {mapping(capture[k])["id"] for k in ("context", "input")} & {
        r["id"] for r in [bundle, *checked]
    }:
        raise reject()
    body = _brief(brief["payload"], method, bundle, capture, actual_version)
    if body["criterion_bindings"] and (
        not contract_method
        or b["composer_revision"]
        not in {
            composer_revision(),
            PRECONDITION_COMPOSER_REVISION,
            PREDICATE_COMPOSER_REVISION,
            APPLICABILITY_COMPOSER_REVISION,
            CRITERIA_COMPOSER_REVISION,
        }
    ):
        raise reject()
    if obj(role["payload"], {"role", "text"}) != {
        "role": body["role"],
        "text": CONTRACT_ROLE_TEXT if contract_method else ROLE_TEXT,
    }:
        raise reject()
    roles = {}
    for item in sequence(b["role_refs"], 1, 4):
        row = obj(item, {"role", "content_ref"})
        name = text(row["role"])
        if name not in ROLES or name in roles:
            raise reject()
        roles[name] = reference(row["content_ref"], "prompt-content")
    if roles.get(cast(str, body["role"])) != ref(role) or b["package_refs"] != body["package_refs"]:
        raise reject()
    return raw, brief, body


def expanded_payload(body: object, record_pool: object = None) -> dict[str, object]:
    """Expand only exact retained records, before constructor or domain access."""
    source = mapping(body)
    if "format" not in source:
        if record_pool is not None:
            raise reject()
        return source
    obj(
        source,
        {
            "format",
            "prompt_bundle_ref",
            "preparation_receipt_ref",
            "sections",
            "text_digest",
            "byte_count",
            "token_upper_bound",
        },
    )
    if source["format"] != "record-refs-v1":
        raise reject()
    parts = sequence(source["sections"], 6, 7)
    wanted = [reference(source["prompt_bundle_ref"], "prompt-bundle")]
    for part, label, kind in zip(
        parts[:4],
        ("base", "role", "brief", "method"),
        ("prompt-content", "prompt-content", "task-brief", "bound-procedure"),
        strict=True,
    ):
        item = obj(part, {"section", "record_ref"})
        if item["section"] != label:
            raise reject()
        wanted.append(reference(item["record_ref"], kind))
    material = obj(parts[4], {"section", "version", "context_ref", "input_ref", "schema"})
    if material["section"] != "case-input":
        raise reject()
    version = integer(material["version"], 1, 2)
    wanted.extend(
        [
            reference(material["context_ref"], "contract-input-context"),
            reference(
                material["input_ref"],
                "contract-case-records" if version == 2 else "contract-case-input",
            ),
        ]
    )
    pool = [
        envelope(r, cast(str, pin["kind"]))
        for r, pin in zip(sequence(record_pool, 7, 7), wanted, strict=True)
    ]
    if len({r["id"] for r in pool}) != 7 or [canonical(ref(r)) for r in pool] != [
        canonical(r) for r in wanted
    ]:
        raise reject()
    sections: list[object] = [
        {"section": mapping(part)["section"], "record": item}
        for part, item in zip(parts[:4], pool[1:5], strict=True)
    ]
    sections.extend(
        [
            {
                **{k: v for k, v in material.items() if k not in {"context_ref", "input_ref"}},
                "context": pool[5],
                "input": pool[6],
            },
            *parts[5:],
        ]
    )
    bounded(sections)
    raw = canonical(sections)
    if len(raw) > 32768:
        raise reject()
    return {
        "prompt_bundle": pool[0],
        "text": raw.decode("utf-8"),
        **{
            k: source[k]
            for k in (
                "preparation_receipt_ref",
                "text_digest",
                "byte_count",
                "token_upper_bound",
            )
        },
    }


def validate_composition(
    value: object, manifest: object, entry: object, *, record_pool: object = None
) -> bytes:
    composition = envelope(value, "prompt-composition")
    launch = mapping(envelope(manifest, "launch-manifest")["payload"])
    if "format" in mapping(composition["payload"]) and launch.get("composition_version") != 4:
        raise reject()
    payload = obj(
        expanded_payload(composition["payload"], record_pool),
        {
            "prompt_bundle",
            "preparation_receipt_ref",
            "text",
            "text_digest",
            "byte_count",
            "token_upper_bound",
        },
    )
    launch = mapping(envelope(manifest, "launch-manifest")["payload"])
    version = integer(launch.get("composition_version"), 1, 4)
    raw, brief, body = _material(payload, version)
    if "format" in mapping(composition["payload"]) and mapping(
        mapping(payload["prompt_bundle"])["payload"]
    )["composer_revision"] not in {
        composer_revision(),
        PRECONDITION_COMPOSER_REVISION,
        PREDICATE_COMPOSER_REVISION,
        APPLICABILITY_COMPOSER_REVISION,
        COMPACT_COMPOSER_REVISION,
        CRITERIA_COMPOSER_REVISION,
    }:
        raise reject()
    e = obj(
        entry,
        {
            "batch_index",
            "task_id",
            "attempt_id",
            "brief_ref",
            "composition_ref",
            "goal",
        },
    )
    header = mapping(body["header"])
    if (
        ref(composition) != reference(e["composition_ref"], "prompt-composition")
        or ref(brief) != reference(e["brief_ref"], "task-brief")
        or any(e[k] != header[k] for k in ("task_id", "attempt_id"))
        or launch.get("run_id") != header["run_id"]
        or launch.get("selection_ref") != body["execution_selection_ref"]
        or e["goal"] != body["objective_summary"]
    ):
        raise reject()
    return raw
