"""Strict cold-child wire contract. Validation precedes all replay lookup."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string, valid_ref
from omnis.modules.settings.catalog_models import CatalogError, Limits, Precondition, Procedure
from omnis.modules.settings.catalog_schema import bounded, canonical, load_json
from omnis.modules.settings.publication_models import clean_text
from omnis.modules.settings.skill_catalog import HANDLERS, read_file

PROTOCOL = "omnis-managed-admission-v1"

BRIEF_FIELDS = set(
    "header prompt_bundle_ref execution_selection_ref assessment_mode objective_summary non_goals role hypothesis operation_refs priority_reason done_when return_when context contradiction_refs prior_attempt_refs package_refs technique_refs procedure_refs procedure_bindings method_plan review_request criterion_bindings overlay_refs input_artifact_refs identities allowed_capability_ids limits deadline validation_reserve stop_conditions required_evidence".split()
)
RESULT_EMPTY = "observation_refs evidence_refs candidate_claims controls contradiction_refs next_clues consumed_input_refs criterion_results action_refs effect_refs cleanup_refs".split()


# Installed, source-pinned predicates for the existing records method. These
# names are not package functions: each must bind to this exact requirement and
# its resolved step/schema closure. Other procedure forms remain unsupported.
RECORD_PREDICATES = {
    "normalize-records": ("normalize-operations", "OUTPUT"),
    "build-surface-map": ("build-map", "OUTPUT"),
    "preserve-input-context": ("normalize-operations", "INPUT"),
}


def predicate_key(value: object) -> str:
    import re

    result = text(value, 128)
    if re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", result) is None:
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    return result


def requirement_conditions(procedure: object, input_ref: object = None) -> None:
    """Finite installed input predicate; no expression/package-code evaluation."""
    p = mapping(procedure)
    source = (
        {"kind": "CASE_SLOT_REF", "name": "records"}
        if input_ref is None
        else ref(input_ref, "contract-case-records")
    )
    condition_groups = [
        p["preconditions"],
        *[mapping(r)["applies_if"] for r in sequence(p["method_requirements"])],
    ]
    for group in condition_groups:
        conditions = sequence(group)
        if not conditions:
            continue
        if p["key"] != "map-records" or len(conditions) != 1:
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        condition = exact(conditions[0], {"predicate_id", "input_refs", "expected", "on_missing"})
        if (
            condition["predicate_id"] != "contract.records-nonempty"
            or type(condition["expected"]) is not bool
            or condition["on_missing"] not in ("BLOCKED", "INCONCLUSIVE")
            or canonical(condition["input_refs"]) != canonical([source])
        ):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")


def invalidation_declaration(procedure: object) -> None:
    """One installed predicate on the existing records input, not a registry."""
    p = mapping(procedure)
    ids = sequence(p["invalidation_predicate_ids"])
    if ids and (
        type(p["key"]) is not str
        or p["key"] != "map-records"
        or len(ids) != 1
        or type(ids[0]) is not str
        or ids[0] != "contract.records-empty"
    ):
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")


def require_not_invalidated(procedure: object, original: object = None) -> None:
    """Admission guard only; no external auth/input freshness qualification."""
    p = mapping(procedure)
    invalidation_declaration(p)
    if not p["invalidation_predicate_ids"]:
        return
    if original is None:
        raise CatalogError("PROCEDURE_INVALIDATION_UNKNOWN")
    source = mapping(sequence(mapping(sequence(p["probe"])[0])["input_bindings"])[0])["source_ref"]
    available = record(original, "contract-case-records")
    if canonical(records.reference(available)) != canonical(ref(source, "contract-case-records")):
        raise CatalogError("REF_MISMATCH")
    payload = mapping(available["payload"])
    if canonical(ref(payload["schema_ref"], "schema")) != canonical(
        ref(p["input_schema_ref"], "schema")
    ):
        raise CatalogError("REF_MISMATCH")
    value = exact(payload["value"], {"records"})
    if not sequence(value["records"]):
        raise CatalogError("PROCEDURE_INVALIDATED")


def require_preconditions(procedure: object, original: object = None) -> None:
    """Refuse false/UNKNOWN before admission; never turn a precondition into N/A."""
    p = mapping(procedure)
    conditions = sequence(p["preconditions"])
    if not conditions:
        return
    source = mapping(sequence(mapping(sequence(p["probe"])[0])["input_bindings"])[0])["source_ref"]
    requirement_conditions(p, source)
    condition = mapping(conditions[0])
    if original is None:
        raise CatalogError("PROCEDURE_PRECONDITION_UNKNOWN_" + text(condition["on_missing"]))
    available = record(original, "contract-case-records")
    if canonical(records.reference(available)) != canonical(source):
        raise CatalogError("REF_MISMATCH")
    value = exact(mapping(available["payload"])["value"], {"records"})
    if (len(sequence(value["records"])) != 0) is not condition["expected"]:
        raise CatalogError("PROCEDURE_PRECONDITION_FALSE")


def compile_method_plan(bound: object, original: object = None) -> list[dict[str, object]]:
    """Compile all obligations from the exact bound procedure and retained input."""
    b = record(bound, "bound-procedure")
    p = mapping(mapping(b["payload"])["resolved_procedure"])
    available = None
    if any(mapping(r)["applies_if"] for r in sequence(p["method_requirements"])):
        input_ref = mapping(sequence(mapping(sequence(p["probe"])[0])["input_bindings"])[0])[
            "source_ref"
        ]
        requirement_conditions(p, input_ref)
        available = None if original is None else record(original, "contract-case-records")
        if available is not None and canonical(records.reference(available)) != canonical(
            input_ref
        ):
            raise CatalogError("REF_MISMATCH")
    rows: list[dict[str, object]] = []
    for raw in sequence(p["method_requirements"]):
        r = mapping(raw)
        state, basis = "APPLIES", []
        if r["applies_if"]:
            if available is None:
                state = "UNKNOWN"
            else:
                value = exact(mapping(available["payload"])["value"], {"records"})
                present = len(sequence(value["records"])) != 0
                condition = mapping(sequence(r["applies_if"])[0])
                state = "APPLIES" if present is condition["expected"] else "NOT_APPLICABLE"
                basis = [records.reference(available)]
        rows.append(
            {
                "ref": {"bound_procedure_ref": records.reference(b), "requirement_key": r["key"]},
                "applicability": state,
                "applicability_basis_refs": basis,
                "required": r["required"],
            }
        )
    return rows


def evidence_declaration(procedure: object) -> None:
    """Finite inert proof: authenticated PURE output artifacts, never input refs."""
    p = mapping(procedure)
    requirements = [mapping(r) for r in sequence(p["method_requirements"])]
    declared = sequence(p["evidence_requirements"])
    bearing = [r for r in requirements if sequence(r["evidence_kinds"])]
    if not bearing and not declared:
        return
    if p["key"] != "map-records" or (declared and not bearing):
        raise CatalogError("METHOD_UNSUPPORTED")
    steps = [mapping(s) for s in sequence(p["probe"])]
    for requirement in bearing:
        matches = [s for s in steps if requirement["step_ids"] == [s["id"]]]
        if (
            any(type(kind) is not str for kind in sequence(requirement["evidence_kinds"]))
            or requirement["evidence_kinds"] != ["contract-artifact"]
            or requirement["key"] not in ("normalize-records", "build-surface-map")
            or len(matches) != 1
            or requirement["artifact_schema_refs"] != [matches[0]["output_schema_ref"]]
        ):
            raise CatalogError("METHOD_UNSUPPORTED")
    if len(declared) > 1:
        raise CatalogError("METHOD_UNSUPPORTED")
    for raw in declared:
        row = exact(raw, {"kind", "minimum", "mandatory"})
        if (
            type(row["kind"]) is not str
            or row["kind"] != "contract-artifact"
            or type(row["mandatory"]) is not bool
        ):
            raise CatalogError("METHOD_UNSUPPORTED")
        integer(row["minimum"], 1, 128)


def evidence_outputs(
    procedure: object, artifacts: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Select verified same-attempt outputs; caller validates receipts/bytes first."""
    p = mapping(procedure)
    evidence_declaration(p)
    schemas = [
        s
        for raw in sequence(p["method_requirements"])
        if (r := mapping(raw))["evidence_kinds"]
        for s in sequence(r["artifact_schema_refs"])
    ]
    return [
        records.reference(a)
        for a in artifacts
        if p["evidence_requirements"] or mapping(a["payload"])["schema_ref"] in schemas
    ]


def evidence_minimum(
    procedure: object, verified_outputs: list[dict[str, object]]
) -> tuple[list[str], bool]:
    """Count only outputs already verified against the exact authenticated chain."""
    p = mapping(procedure)
    evidence_declaration(p)
    gaps: list[str] = []
    complete = True
    for raw in sequence(p["evidence_requirements"]):
        row = mapping(raw)
        minimum = integer(row["minimum"], 1, 128)
        if len(verified_outputs) < minimum:
            gaps.append(
                f"EVIDENCE_MINIMUM: contract-artifact ({len(verified_outputs)}/{minimum}); coverage gap."
            )
            complete = complete and not row["mandatory"]
    return gaps, complete


def required_evidence(bound: object) -> list[dict[str, object]]:
    b = record(bound, "bound-procedure")
    p = mapping(mapping(b["payload"])["resolved_procedure"])
    evidence_declaration(p)
    return [
        {"bound_procedure_ref": records.reference(b), "requirement_key": r["key"]}
        for raw in sequence(p["method_requirements"])
        if (r := mapping(raw))["required"] and r["evidence_kinds"]
    ]


def predicate_closure(procedure: object) -> dict[str, dict[str, object]]:
    p = mapping(procedure)
    if not {"key", "input_schema_ref", "probe", "method_requirements"} <= set(p):
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    if predicate_key(p["key"]) != "map-records":
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    ref(p["input_schema_ref"], "schema")
    steps: dict[str, dict[str, object]] = {}
    for raw in sequence(p["probe"]):
        row = mapping(raw)
        if not {"id", "output_schema_ref"} <= set(row):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        name = predicate_key(row["id"])
        ref(row["output_schema_ref"], "schema")
        if name in steps:
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        steps[name] = row
    if list(steps) != ["normalize-operations", "build-map"]:
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
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
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        predicate_key(row["key"])
        for step_id in sequence(row["step_ids"]):
            predicate_key(step_id)
        for schema_ref in sequence(row["artifact_schema_refs"]):
            ref(schema_ref, "schema")
    if [r["key"] for r in requirements] != list(RECORD_PREDICATES):
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    result: dict[str, dict[str, object]] = {}
    for requirement in requirements:
        name = text(requirement["key"], 128)
        step, source = RECORD_PREDICATES[name]
        schema = p["input_schema_ref"] if source == "INPUT" else steps[step]["output_schema_ref"]
        step_ids = [step]
        schemas = [schema]
        if name == "normalize-records" and requirement["step_ids"] == list(steps):
            step_ids = list(steps)
            schemas = [s["output_schema_ref"] for s in steps.values()]
            if len({canonical(s) for s in schemas}) != 2:
                raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        if (
            requirement["step_ids"] != step_ids
            or requirement["artifact_schema_refs"] != schemas
            or type(requirement["required"]) is not bool
        ):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        result[name] = requirement
    evidence_declaration(p)
    return result


def validate_predicates(
    body: object, bound: object, *, prompt_bundle: object = None, composition_version: object = None
) -> None:
    b = mapping(body)
    for field in ("done_when", "return_when"):
        seen: set[bytes] = set()
        for raw in sequence(b[field]):
            row = exact(raw, {"bound_procedure_ref", "predicate_id"})
            ref(row["bound_procedure_ref"], "bound-procedure")
            predicate_key(row["predicate_id"])
            if canonical(row) in seen:
                raise CatalogError("BOUND_PREDICATE_COLLISION")
            seen.add(canonical(row))
    r = record(bound, "bound-procedure")
    required = False
    if prompt_bundle is not None:
        from omnis.modules.tasks.managed_composition import (
            APPLICABILITY_COMPOSER_REVISION,
            CAPTURE_COMPOSER_REVISION,
            COMPACT_COMPOSER_REVISION,
            COMPOSER_REVISION,
            CRITERIA_COMPOSER_REVISION,
            EVIDENCE_COMPOSER_REVISION,
            INVALIDATION_COMPOSER_REVISION,
            LEGACY_COMPOSER_REVISION,
            METHOD_COMPOSER_REVISION,
            PRECONDITION_COMPOSER_REVISION,
            PREDICATE_COMPOSER_REVISION,
            RECORDS_COMPOSER_REVISION,
        )

        bundle = record(prompt_bundle, "prompt-bundle")
        if canonical(ref(b["prompt_bundle_ref"], "prompt-bundle")) != canonical(
            records.reference(bundle)
        ):
            raise CatalogError("BOUND_PREDICATE_GAP")
        version = integer(composition_version, 1, 4)
        pin = mapping(bundle["payload"])["composer_revision"]
        revisions = {
            APPLICABILITY_COMPOSER_REVISION,
            EVIDENCE_COMPOSER_REVISION,
            INVALIDATION_COMPOSER_REVISION,
            PRECONDITION_COMPOSER_REVISION,
            COMPOSER_REVISION,
            PREDICATE_COMPOSER_REVISION,
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
            raise CatalogError("BOUND_PREDICATE_GAP")
        procedure = mapping(mapping(r["payload"])["resolved_procedure"])
        if procedure["invalidation_predicate_ids"] and (
            version != 4
            or pin
            not in {COMPOSER_REVISION, EVIDENCE_COMPOSER_REVISION, INVALIDATION_COMPOSER_REVISION}
        ):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        if pin not in {COMPOSER_REVISION, EVIDENCE_COMPOSER_REVISION} and (
            procedure["evidence_requirements"]
            or any(mapping(r)["evidence_kinds"] for r in sequence(procedure["method_requirements"]))
            or (
                procedure["key"] == "map-records"
                and any(
                    mapping(r)["required"]
                    is not (RECORD_PREDICATES[text(mapping(r)["key"])][1] == "OUTPUT")
                    for r in sequence(procedure["method_requirements"])
                    if mapping(r)["key"] in RECORD_PREDICATES
                )
            )
        ):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        if (
            pin != COMPOSER_REVISION
            and procedure["key"] == "map-records"
            and any(
                mapping(req)["step_ids"]
                != [RECORD_PREDICATES[predicate_key(mapping(req)["key"])][0]]
                for req in sequence(procedure["method_requirements"])
                if mapping(req)["key"] in RECORD_PREDICATES
            )
        ):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        required = (
            version == 4
            and pin
            in {
                COMPOSER_REVISION,
                EVIDENCE_COMPOSER_REVISION,
                INVALIDATION_COMPOSER_REVISION,
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
                COMPOSER_REVISION,
                EVIDENCE_COMPOSER_REVISION,
                INVALIDATION_COMPOSER_REVISION,
                PRECONDITION_COMPOSER_REVISION,
                PREDICATE_COMPOSER_REVISION,
                APPLICABILITY_COMPOSER_REVISION,
            }
        ):
            raise CatalogError("BOUND_PREDICATE_GAP")
    if not b["done_when"] and not b["return_when"] and not required:
        return  # Structural-only calls confer no completion; consumers supply the retained bundle.

    closure = predicate_closure(mapping(r["payload"])["resolved_procedure"])
    for field in ("done_when", "return_when"):
        for raw in sequence(b[field]):
            row = mapping(raw)
            if (
                canonical(row["bound_procedure_ref"]) != canonical(records.reference(r))
                or row["predicate_id"] not in closure
            ):
                raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    expected_done = (
        [name for name, requirement in closure.items() if requirement["required"]]
        if prompt_bundle is not None and pin in {COMPOSER_REVISION, EVIDENCE_COMPOSER_REVISION}
        else list(closure)
    )
    if [mapping(r)["predicate_id"] for r in sequence(b["done_when"])] != expected_done:
        raise CatalogError("BOUND_PREDICATE_GAP")
    if not b["return_when"]:
        raise CatalogError("BOUND_PREDICATE_GAP")


def capture_slot_values(value: object, *, version: int = 1) -> list[dict[str, object]]:
    from omnis.modules.tasks.contract_case_input import input_contract

    name, kind = input_contract(version)
    slots = sequence(value)
    if len(slots) != 1:
        raise CatalogError("MANAGED_REJECTED")
    slot = exact(slots[0], {"slot_name", "refs"})
    refs = sequence(slot["refs"])
    if slot["slot_name"] != name or len(refs) != 1:
        raise CatalogError("MANAGED_REJECTED")
    return [{"slot_name": name, "refs": [ref(refs[0], kind)]}]


def validate_capture_procedure(
    value: object, input_ref: object = None, *, version: int = 1
) -> None:
    from omnis.modules.tasks.contract_case_input import input_contract, require_slots

    name, kind = input_contract(version)
    body = mapping(value)
    if body["key"] != ("map-records" if version == 2 else "map-capture") or any(
        body[group] != [] for group in ("baseline", "control", "cleanup")
    ):
        raise CatalogError("UNSUPPORTED_PROCEDURE")
    steps = sequence(body["probe"])
    count = 2 if version == 2 else 3
    if len(steps) != count or len({text(mapping(s)["id"]) for s in steps}) != count:
        raise CatalogError("UNSUPPORTED_PROCEDURE")
    if input_ref is None:
        require_slots(body["slots"], version=version)
        source: object = {"kind": "CASE_SLOT_REF", "name": name}
    else:
        source = ref(input_ref, kind)
        if body["slots"] != []:
            raise CatalogError("UNSUPPORTED_PROCEDURE")
    if mapping(steps[0])["input_bindings"] != [
        {"name": name, "source_ref": source, "selector": name}
    ]:
        raise CatalogError("UNSUPPORTED_PROCEDURE")
    for index, name in enumerate(("operations",) if version == 2 else ("records", "operations"), 1):
        expected = [
            {
                "name": name,
                "source_ref": {
                    "kind": "STEP_OUTPUT",
                    "step_id": mapping(steps[index - 1])["id"],
                    "output_name": name,
                },
                "selector": None,
            }
        ]
        if mapping(steps[index])["input_bindings"] != expected:
            raise CatalogError("UNSUPPORTED_PROCEDURE")


def resolve_local(value: object, package: str, bindings: list[dict[str, object]]) -> object:
    if isinstance(value, dict):
        if value.get("kind") == "LOCAL":
            local = exact(value, {"kind", "entity_kind", "key"})
            found = [
                b
                for b in bindings
                if b.get("package_key") == package
                and b.get("entity_kind") == local["entity_kind"]
                and b.get("key") == local["key"]
            ]
            if len(found) != 1:
                raise CatalogError("UNRESOLVED_PROCEDURE_REF")
            return ref(found[0]["ref"])
        if value.get("kind") in {"RELEASE", "CASE_SLOT_REF"}:
            raise CatalogError("UNSUPPORTED_PROCEDURE")
        return {k: resolve_local(v, package, bindings) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_local(v, package, bindings) for v in value]
    return value


def build_records(
    selection: dict[str, object],
    preparation_ref: dict[str, object],
    procedure_ref: dict[str, object],
    procedure: Procedure,
    bindings: list[dict[str, object]],
    package: str,
    role: str,
    count: int,
    now: datetime,
    recipe_limits: Limits | None = None,
    *,
    composition_packages: list[dict[str, object]] | None = None,
    context_only: bool = False,
    prefix: list[dict[str, object]] | None = None,
    case_input: dict[str, object] | None = None,
    method_execution: bool = False,
    criterion_ids: object = None,
    return_predicate_id: object = None,
) -> list[dict[str, object]]:
    """Backend-only synthetic CONTRACT_PROBE, never an assessment or grant."""
    integer(count, 1, 2)
    if prefix is not None:
        from omnis.modules.tasks.mission_revisions import require_no_revision

        require_no_revision(prefix)
        if method_execution is True:
            from omnis.modules.tasks.method_checker_identity import verify

            checkers = [r for r in prefix if r["kind"] == "method-checker"]
            bundles = [r for r in prefix if r["kind"] == "prompt-bundle"]
            if len(checkers) != 1 or len(bundles) != 1:
                raise CatalogError("METHOD_CHECKER_UNAVAILABLE")
            verify(
                checkers[0],
                pin=text(mapping(bundles[0]["payload"])["composer_revision"]),
                receive_only=False,
                zero_predicates=False,
            )
    if return_predicate_id is not None and (
        not method_execution
        or context_only
        or case_input is None
        or predicate_key(return_predicate_id) not in RECORD_PREDICATES
    ):
        raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    from omnis.modules.tasks import criterion_checks

    allocated = [] if criterion_ids is None else criterion_checks.allocation(criterion_ids)
    if allocated and (not method_execution or prefix is not None or not context_only):
        raise CatalogError("CRITERION_ALLOCATION_MISMATCH")
    if type(method_execution) is not bool or (method_execution and composition_packages is None):
        raise CatalogError("MANAGED_REJECTED")
    if (
        role not in {"RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH"}
        or procedure.verification_kind != "CONTRACT"
        or (procedure.slots and not context_only and case_input is None)
        or any(type(condition) is not Precondition for condition in procedure.preconditions)
        or procedure.requested_capabilities
        or procedure.identity_requirements
        or procedure.business_rule_refs
        or procedure.applicability_predicate_ids
        or procedure.stop_reason_ids
        or procedure.oracle_ref is not None
        or not 1 <= len(procedure.method_requirements) <= 128
        or "BLOCKED" not in procedure.outcomes
    ):
        raise CatalogError("UNSUPPORTED_PROCEDURE")
    evidence_declaration(procedure.model_dump(mode="json"))
    requirement_conditions(procedure.model_dump(mode="json"))
    invalidation_declaration(procedure.model_dump(mode="json"))
    if len({r.key for r in procedure.method_requirements}) != len(procedure.method_requirements):
        raise CatalogError("UNSUPPORTED_PROCEDURE")
    source = mapping(selection["payload"])
    graph: list[dict[str, object]] = [] if prefix is None else [record(r) for r in prefix]

    def add(kind: str, body: dict[str, object]) -> dict[str, object]:
        item = records.envelope(kind, body)
        record(item, kind)
        graph.append(item)
        return records.reference(item)

    local_bindings = list(bindings)
    if prefix is None:
        # Core installed action descriptors are local records, not catalog writes.
        local_bindings = list(bindings)
        for handler in HANDLERS:
            action = add(
                "action_definition",
                {
                    "handler_id": handler,
                    "execution_class": "PURE",
                    "allowed_capability_ids": [],
                    "dispatch_permitted": False,
                },
            )
            local_bindings.append(
                {
                    "package_key": package,
                    "entity_kind": "action_definition",
                    "key": handler,
                    "ref": action,
                }
            )
        policy = add(
            "probe-policy",
            {
                "purpose": "CONTRACT_PROBE",
                "target_actions": 0,
                "model_calls": 0,
                "allowed_capability_ids": [],
            },
        )
        scope = add(
            "probe-scope",
            {
                "target_operation_refs": [],
                "description": "Synthetic managed-admission contract only; no target access.",
            },
        )
        rule = add(
            "focus-selection-rule", {"key": "contract-probe.no-target", "operation_refs": []}
        )
        criterion = str(uuid4())
        rule_ref = (
            add(
                "criterion-outcome-rule",
                criterion_checks.rule_payload(procedure_ref, procedure.model_dump(mode="json")),
            )
            if allocated
            else None
        )
        mission = add(
            "mission",
            {
                "snapshot_ref": source["snapshot_ref"],
                "assessment_mode": "FULL_ASSESSMENT",
                "summary": procedure.objective,
                "criteria": [
                    {
                        "id": criterion_id,
                        "description": "Execute the bound deterministic CONTRACT/PURE method."
                        if method_execution
                        else "Record a native NO_MODEL refusal without executing the method.",
                        "kind": "FUNCTIONAL",
                        "oracle_ref": None,
                    }
                    for criterion_id in (allocated or [criterion])
                ],
                "non_goals": [
                    "No assessment, provider or target traffic."
                    if method_execution
                    else "No assessment, method success, provider or target traffic."
                ],
                "required_operation_refs": [],
                "basis_refs": [records.reference(selection), preparation_ref],
                "gaps": [] if method_execution else ["NO_MODEL; method execution unavailable."],
                "done_when": [
                    {"criterion_id": i, "required": True} for i in (allocated or [criterion])
                ],
            },
        )
        focus = add(
            "focus",
            {
                "mission_ref": mission,
                "state": "RESOLVED" if method_execution else "BLOCKED",
                "selection_rule_ref": rule,
                "bootstrap_budget_ref": None,
                "test_operation_refs": [],
                "support_operation_refs": [],
                "discovery_bootstrap": {"seed_refs": [], "max_actions": 0, "deadline_seconds": 0},
                "excluded_operation_refs": [],
                "scope_ref": scope,
                "policy_ref": policy,
                "reason": "CONTRACT_PROBE NO_MODEL; no target operations admitted.",
            },
        )
        code_digest = sha256(read_file(Path(__file__))).hexdigest()
        from omnis.modules.tasks.method_checker_identity import descriptor

        checker_payload: dict[str, object] = (
            descriptor()
            if method_execution
            else {
                "key": "managed.no-model",
                "code_digest": code_digest,
                "semantics": "All method requirements NOT_RUN; INCOMPLETE. Schema acceptance is not method completion.",
            }
        )
        checker = add("method-checker", checker_payload)
        base = add(
            "prompt-content",
            {
                "text": "CONTRACT_PROBE. Deterministic PURE method only; no provider, model, target or stock tools. Read only the bound assignment inputs."
                if method_execution
                else "CONTRACT_PROBE. No provider, model, tools, targets, or domain reads. Return NO_MODEL only."
            },
        )
        role_ref = add(
            "prompt-content",
            {
                "role": role,
                "text": "SUPPORT-only native CONTRACT/PURE method; not an assessment."
                if method_execution
                else "SUPPORT-only cold admission probe; not an assessment.",
            },
        )
        prompt = add(
            "prompt-bundle",
            {
                "base_ref": base,
                "role_refs": [{"role": role, "content_ref": role_ref}],
                "composer_revision": code_digest,
                "brief_schema": 1,
                "result_schema": 1,
                "package_refs": source["selected_package_refs"],
                "max_context_bytes": 65536,
                "max_context_tokens": 65536,
                "tokenizer_revision": "utf8-byte-upper-bound-v1",
                "provenance": [],
                **({} if composition_packages is None else _composition_settings()),
            },
        )
        run = add(
            "managed-run",
            {
                "purpose": "CONTRACT_PROBE",
                "snapshot_ref": source["snapshot_ref"],
                "selection_ref": records.reference(selection),
                "mission_ref": mission,
                "focus_ref": focus,
                "policy_ref": policy,
                "scope_ref": scope,
                "prompt_bundle_ref": prompt,
                "method_check_ref": checker,
                "preparation_receipt_ref": preparation_ref,
                "method_review_policy": {
                    "mode": "CHECK_ONLY",
                    "required_for_roles": [],
                    "reviewer_recipe_key": None,
                    "max_rework_rounds": 0,
                },
                **(
                    {"allocated_criterion_ids": allocated, "criterion_outcome_rule_ref": rule_ref}
                    if allocated
                    else {}
                ),
            },
        )
        cursor = add(
            "managed-cursor",
            {"run_id": run["id"], "mission_ref": mission, "focus_ref": focus, "sequence": 1},
        )
    else:

        def retained(kind: str) -> dict[str, object]:
            matches = [r for r in graph if r["kind"] == kind]
            if len(matches) != 1:
                raise CatalogError("REF_UNAVAILABLE")
            return records.reference(matches[0])

        run, mission, focus, prompt, cursor = (
            retained(k)
            for k in ("managed-run", "mission", "focus", "prompt-bundle", "managed-cursor")
        )
        run_body = mapping(next(r for r in graph if r["id"] == run["id"])["payload"])
        allocated = (
            criterion_checks.allocation(run_body["allocated_criterion_ids"])
            if "allocated_criterion_ids" in run_body
            else []
        )
        rule_ref = (
            ref(run_body["criterion_outcome_rule_ref"], "criterion-outcome-rule")
            if allocated
            else None
        )
        if allocated and not method_execution:
            raise CatalogError("CRITERION_ALLOCATION_MISMATCH")
        if (
            run_body["selection_ref"] != records.reference(selection)
            or run_body["preparation_receipt_ref"] != preparation_ref
        ):
            raise CatalogError("REF_MISMATCH")
        metadata = mapping(next(r for r in graph if r["id"] == prompt["id"])["payload"])
        base = ref(metadata["base_ref"], "prompt-content")
        role_ref = ref(mapping(sequence(metadata["role_refs"])[0])["content_ref"], "prompt-content")
        for action in (r for r in graph if r["kind"] == "action_definition"):
            local_bindings.append(
                {
                    "package_key": package,
                    "entity_kind": "action_definition",
                    "key": mapping(action["payload"])["handler_id"],
                    "ref": records.reference(action),
                }
            )
    case_version = 2 if procedure.key == "map-records" else 1
    if context_only:
        validate_capture_procedure(procedure.model_dump(mode="json"), version=case_version)
        return graph
    authored = procedure.model_dump(mode="json")
    slot_values: list[dict[str, object]] = []
    input_refs: list[object] = []
    if case_input is not None:
        from omnis.modules.tasks.contract_case_input import (
            first_binding,
            input_contract,
            require_slots,
            validate_material,
        )
        from omnis.modules.tasks.contract_case_input import slot_values as material_slots

        owner = text(mapping(mapping(case_input["context"])["payload"])["owner_id"])
        validate_material(case_input, namespace="RUN", owner_id=owner)
        if case_input["version"] != case_version:
            raise CatalogError("REF_MISMATCH")
        require_slots(authored["slots"], version=case_version)
        validate_capture_procedure(authored, version=case_version)
        integer(count, 1, 1)
        if prefix is None or composition_packages is None:
            raise CatalogError("MANAGED_REJECTED")
        context = mapping(mapping(case_input["context"])["payload"])
        if any(
            context[key] != expected
            for key, expected in (
                ("basis_ref", run),
                ("snapshot_ref", source["snapshot_ref"]),
                ("selection_ref", records.reference(selection)),
                ("procedure_ref", procedure_ref),
                ("mission_ref", mission),
                ("focus_ref", focus),
            )
        ):
            raise CatalogError("REF_MISMATCH")
        slot_values = material_slots(case_input)
        input_refs = sequence(slot_values[0]["refs"])
        probe_steps = sequence(authored["probe"])
        expected = [first_binding(case_version)]
        if not probe_steps or mapping(probe_steps[0])["input_bindings"] != expected:
            raise CatalogError("UNSUPPORTED_PROCEDURE")
        first = mapping(probe_steps[0])
        input_name, _ = input_contract(case_version)
        first["input_bindings"] = [
            {"name": input_name, "source_ref": input_refs[0], "selector": input_name}
        ]
        authored["probe"] = [first, *probe_steps[1:]]
        authored["method_requirements"] = [
            {
                **mapping(raw_requirement),
                "applies_if": [
                    {**mapping(raw_condition), "input_refs": list(input_refs)}
                    for raw_condition in sequence(mapping(raw_requirement)["applies_if"])
                ],
            }
            for raw_requirement in sequence(authored["method_requirements"])
        ]
        authored["preconditions"] = [
            {**mapping(condition), "input_refs": list(input_refs)}
            for condition in sequence(authored["preconditions"])
        ]
        authored["slots"] = []
    resolved = mapping(resolve_local(authored, package, local_bindings))
    if resolved["invalidation_predicate_ids"]:
        from omnis.modules.tasks.managed_composition import COMPOSER_REVISION

        retained_prompt = next(r for r in graph if r["id"] == prompt["id"])
        if (
            not method_execution
            or mapping(retained_prompt["payload"])["composer_revision"] != COMPOSER_REVISION
        ):
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
    require_preconditions(resolved, None if case_input is None else case_input["input"])
    require_not_invalidated(resolved, None if case_input is None else case_input["input"])
    if (
        case_input is not None
        and resolved["input_schema_ref"] != mapping(case_input["schema"])["ref"]
    ):
        raise CatalogError("REF_MISMATCH")
    entries: list[dict[str, object]] = []
    for index in range(count):
        task_id, attempt_id = str(uuid4()), str(uuid4())
        bound = add(
            "bound-procedure",
            {
                "procedure_ref": procedure_ref,
                "slot_values": slot_values,
                "resolved_procedure": resolved,
                "mission_ref": mission,
            },
        )
        prompt_record = next(r for r in graph if r["id"] == prompt["id"])
        from omnis.modules.tasks.managed_composition import COMPOSER_REVISION

        predicates_enabled = (
            method_execution
            and case_version == 2
            and mapping(prompt_record["payload"])["composer_revision"] == COMPOSER_REVISION
        )
        predicate_names = (
            [
                name
                for name, requirement in predicate_closure(resolved).items()
                if requirement["required"]
            ]
            if predicates_enabled
            else []
        )
        if return_predicate_id is not None and not predicates_enabled:
            raise CatalogError("BOUND_PREDICATE_UNAVAILABLE")
        requirements = compile_method_plan(
            graph[-1], None if case_input is None else case_input["input"]
        )
        # Exact per-assignment result schema: no success/evidence can be injected.
        header: dict[str, object] = {
            "schema_version": 1,
            "run_id": run["id"],
            "task_id": task_id,
            "attempt_id": attempt_id,
            "snapshot_ref": source["snapshot_ref"],
            "mission_revision": mission,
            "focus_ref": focus,
            "through_cursor": cursor["id"],
            "brief_revision": 1,
        }
        criterion_bindings: list[dict[str, object]] = [
            {
                "criterion_id": i,
                "bound_procedure_ref": bound,
                "step_ids": [mapping(s)["id"] for s in sequence(resolved["probe"])],
                "outcome_rule_ref": rule_ref,
            }
            for i in allocated
        ]
        result_schema = add(
            "schema",
            result_json_schema(
                header,
                requirements,
                method_execution=method_execution,
                criterion_bindings=criterion_bindings,
            ),
        )
        header = {**header, "result_schema_ref": result_schema}
        brief = add(
            "task-brief",
            {
                "header": header,
                "prompt_bundle_ref": prompt,
                "execution_selection_ref": records.reference(selection),
                "assessment_mode": "FULL_ASSESSMENT",
                "objective_summary": procedure.objective,
                "non_goals": [
                    "No assessment, target/model access, or functional PASS."
                    if allocated
                    else "No assessment, target/model access, or CriterionOutcome."
                ],
                "role": role,
                "hypothesis": "Native child executes only bound deterministic PURE steps."
                if method_execution
                else "Native admission refuses NO_MODEL before any method step.",
                "operation_refs": [],
                "priority_reason": "CRITERIA: explicit backend allocation; no oracle or controls available."
                if allocated
                else "SUPPORT: synthetic CONTRACT_PROBE lifecycle; zero target operations and no criterion assignment.",
                "done_when": [
                    {"bound_procedure_ref": bound, "predicate_id": name} for name in predicate_names
                ],
                "return_when": [
                    {
                        "bound_procedure_ref": bound,
                        "predicate_id": return_predicate_id or "build-surface-map",
                    }
                ]
                if predicates_enabled
                else [],
                "context": [
                    {
                        "ref": mission,
                        "epistemic_state": "OBSERVED",
                        "summary": "Backend synthetic contract-probe mission, not model interpretation.",
                        "mandatory": True,
                    },
                    {
                        "ref": focus,
                        "epistemic_state": "OBSERVED",
                        "summary": "Blocked; no domain access permitted.",
                        "mandatory": True,
                    },
                ]
                + (
                    []
                    if not input_refs
                    else [
                        {
                            "ref": input_refs[0],
                            "epistemic_state": "OBSERVED",
                            "summary": "Backend synthetic CONTRACT records input; untrusted data, not execution evidence."
                            if case_version == 2
                            else "Backend synthetic CONTRACT capture input; untrusted data, not execution evidence.",
                            "mandatory": True,
                        }
                    ]
                ),
                "contradiction_refs": [],
                "prior_attempt_refs": [],
                "package_refs": source["selected_package_refs"],
                "technique_refs": [resolved["technique_ref"]],
                "procedure_refs": [procedure_ref],
                "procedure_bindings": [
                    {
                        "procedure_ref": procedure_ref,
                        "slot_values": slot_values,
                        "bound_procedure_ref": bound,
                    }
                ],
                "method_plan": {"requirements": requirements},
                "review_request": None,
                "criterion_bindings": criterion_bindings,
                "overlay_refs": [],
                "input_artifact_refs": input_refs,
                "identities": [],
                "allowed_capability_ids": [],
                "limits": {
                    key: min(value, (recipe_limits or procedure.limits).model_dump()[key])
                    for key, value in procedure.limits.model_dump().items()
                },
                "deadline": (
                    now.astimezone(UTC)
                    + timedelta(
                        seconds=min(
                            procedure.limits.deadline_seconds,
                            (recipe_limits or procedure.limits).deadline_seconds,
                        )
                    )
                )
                .isoformat()
                .replace("+00:00", "Z"),
                "validation_reserve": {"actions": 0, "seconds": 0},
                "stop_conditions": [],
                "required_evidence": [
                    {"bound_procedure_ref": bound, "requirement_key": r.key}
                    for r in procedure.method_requirements
                    if r.required and r.evidence_kinds
                ],
            },
        )
        validate_brief(graph[-1])
        if len(canonical(graph[-1])) > 65536:
            raise CatalogError("CONTEXT_OVERFLOW")
        composition: dict[str, object] = {}
        if composition_packages is not None:
            from omnis.modules.tasks import managed_composition

            by_id = {text(r["id"]): r for r in graph}
            composed = managed_composition.compose(
                by_id[text(prompt["id"])],
                by_id[text(base["id"])],
                by_id[text(role_ref["id"])],
                by_id[text(brief["id"])],
                by_id[text(bound["id"])],
                preparation_ref,
                managed_composition.selected_skills(
                    composition_packages,
                    source["selected_package_refs"],
                    resolved["technique_ref"],
                    bindings,
                ),
                case_input=case_input,
                method_execution=method_execution,
            )
            graph.append(composed)
            composition = {"composition_ref": records.reference(composed)}
        entries.append(
            {
                "batch_index": index,
                "task_id": task_id,
                "attempt_id": attempt_id,
                "brief_ref": brief,
                "goal": procedure.objective,
                **composition,
            }
        )
    add(
        "launch-manifest",
        {
            "run_id": run["id"],
            "selection_ref": records.reference(selection),
            "resolution": "NO_MODEL",
            "effective": None,
            "entries": entries,
            **(
                {}
                if composition_packages is None
                else {
                    "composition_version": 4
                    if method_execution
                    else case_version + 1
                    if case_input is not None
                    else 1
                }
            ),
        },
    )
    validate_manifest(graph[-1])
    if composition_packages is not None:
        from omnis.modules.tasks import managed_composition

        managed_composition.stage_payload(graph[-1], graph)
    return graph


def _composition_settings() -> dict[str, object]:
    from omnis.modules.tasks.managed_composition import prompt_settings

    return prompt_settings()


def result_json_schema(
    header: dict[str, object],
    requirements: list[dict[str, object]],
    *,
    method_execution: bool = False,
    criterion_bindings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    def strict_object(properties: dict[str, object]) -> dict[str, object]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    header_schema = strict_object({k: {"const": v} for k, v in header.items()})
    header_properties = mapping(header_schema["properties"])
    header_properties["result_schema_ref"] = strict_object(
        {
            "kind": {"const": "schema"},
            "id": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
            "revision": {"type": "integer", "const": 1},
            "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        }
    )
    header_schema = strict_object(header_properties)
    properties: dict[str, object] = {
        "header": header_schema,
        "status": {"const": "BLOCKED"},
        "method_results": {
            "const": [
                {
                    "ref": r["ref"],
                    "state": "NOT_RUN",
                    "basis_refs": [],
                    "artifact_refs": [],
                    "reason": "NO_MODEL: native cold admission refused before method execution.",
                }
                for r in requirements
            ]
        },
        "method_review": {"type": "null"},
        **{k: {"type": "array", "maxItems": 0} for k in RESULT_EMPTY},
        "gaps": {"const": ["NO_MODEL; every published method requirement remains unexecuted."]},
        "usage": {"const": {"state": "KNOWN", "model_calls": 0, "target_actions": 0, "cost": "0"}},
    }
    definitions: dict[str, object] = {}
    if method_execution:
        reference_schema = strict_object(
            {
                "kind": {"type": "string"},
                "id": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
                "revision": {"type": "integer", "const": 1},
                "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            }
        )
        # Compact local definition names avoid repeating long schema paths in
        # the schema and its escaped prompt-composition copy.
        definitions["ref"] = reference_schema
        header_properties["result_schema_ref"] = {
            "$ref": "#/$defs/ref",
            "properties": {"kind": {"const": "schema"}},
        }
        definitions["r"] = {"type": "array", "items": {"$ref": "#/$defs/ref"}, "maxItems": 128}
        ref_array = {"$ref": "#/$defs/r"}
        definitions["m"] = strict_object(
            {
                "ref": {"type": "object"},
                "state": {"enum": ["DONE", "PARTIAL", "NOT_RUN", "NOT_APPLICABLE"]},
                "basis_refs": ref_array,
                "artifact_refs": ref_array,
                "reason": {"type": "string", "minLength": 1, "maxLength": 4096},
            }
        )
        # Share representation only. Prefix constraints retain every exact
        # requirement/bound identity, field/type rule and collection limit.
        bound_definitions: dict[bytes, str] = {}
        prefix_items: list[dict[str, object]] = []
        for requirement in requirements:
            required_ref = exact(requirement["ref"], {"bound_procedure_ref", "requirement_key"})
            bound_ref = ref(required_ref["bound_procedure_ref"], "bound-procedure")
            name = bound_definitions.get(canonical(bound_ref))
            if name is None:
                name = f"b{len(bound_definitions)}"
                bound_definitions[canonical(bound_ref)] = name
                definitions[name] = strict_object(
                    {
                        "bound_procedure_ref": {"const": bound_ref},
                        "requirement_key": {"type": "string"},
                    }
                )
            prefix_items.append(
                {
                    "$ref": "#/$defs/m",
                    "properties": {
                        "state": {"const": "NOT_APPLICABLE"}
                        if requirement["applicability"] == "NOT_APPLICABLE"
                        else {"enum": ["DONE", "PARTIAL", "NOT_RUN"]},
                        "ref": {
                            "$ref": "#/$defs/" + name,
                            "properties": {
                                "requirement_key": {
                                    "const": text(required_ref["requirement_key"], 128)
                                }
                            },
                        },
                    },
                }
            )
        properties.update(
            {
                "status": {"enum": ["SUCCEEDED", "INCONCLUSIVE"]},
                "method_results": {
                    "type": "array",
                    "minItems": len(requirements),
                    "maxItems": len(requirements),
                    "prefixItems": prefix_items,
                },
                "consumed_input_refs": ref_array,
                "action_refs": ref_array,
                "evidence_refs": {**ref_array, "uniqueItems": True},
                "gaps": {
                    "type": "array",
                    "maxItems": 128,
                    "items": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
            }
        )
    if criterion_bindings:
        if not method_execution:
            raise CatalogError("CRITERION_BINDING_MISMATCH")
        from omnis.modules.tasks.criterion_checks import bindings

        criteria = bindings(criterion_bindings)
        properties["criterion_results"] = {
            "type": "array",
            "minItems": len(criteria),
            "maxItems": len(criteria),
            "prefixItems": [
                strict_object(
                    {
                        "criterion_id": {"const": b["criterion_id"]},
                        "bound_procedure_ref": {"const": b["bound_procedure_ref"]},
                        "control_step_ids": {"const": []},
                        "evidence_refs": {"const": []},
                        "proposed_outcome": {"enum": ["PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"]},
                        "gaps": {
                            "type": "array",
                            "maxItems": 128,
                            "items": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                    }
                )
                for b in criteria
            ],
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **strict_object(properties),
        **({"$defs": definitions} if method_execution else {}),
    }


def validate_brief(value: object) -> dict[str, object]:
    result = record(value, "task-brief")
    body = exact(result["payload"], BRIEF_FIELDS)
    if (
        body["role"] not in {"RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH"}
        or body["assessment_mode"] != "FULL_ASSESSMENT"
        or body["review_request"] is not None
    ):
        raise CatalogError("MANAGED_REJECTED")
    for key in (
        "operation_refs",
        "contradiction_refs",
        "prior_attempt_refs",
        "overlay_refs",
        "identities",
        "allowed_capability_ids",
        "stop_conditions",
    ):
        if sequence(body[key]) != []:
            raise CatalogError("MANAGED_REJECTED")
    for key in ("objective_summary", "hypothesis", "priority_reason"):
        text(body[key])
    from omnis.modules.tasks.criterion_checks import bindings as checked_bindings

    criteria = checked_bindings(body["criterion_bindings"])
    if not criteria and "SUPPORT" not in text(body["priority_reason"]):
        raise CatalogError("MANAGED_REJECTED")
    for item in sequence(body["non_goals"]):
        text(item)
    for key, kind in (
        ("prompt_bundle_ref", "prompt-bundle"),
        ("execution_selection_ref", "execution-selection"),
    ):
        ref(body[key], kind)
    for key, kind in (
        ("package_refs", "package"),
        ("technique_refs", "technique"),
        ("procedure_refs", "procedure"),
    ):
        refs = sequence(body[key])
        if not 1 <= len(refs) <= 128 or len({canonical(r) for r in refs}) != len(refs):
            raise CatalogError("MANAGED_REJECTED")
        for item in refs:
            ref(item, kind)
    from pydantic import ValidationError

    try:
        Limits.model_validate(body["limits"])
        deadline = text(body["deadline"], 64)
        if not deadline.endswith("Z"):
            raise ValueError("UTC required")
        datetime.fromisoformat(deadline)
    except (ValidationError, ValueError):
        raise CatalogError("MANAGED_REJECTED") from None
    reserve = exact(body["validation_reserve"], {"actions", "seconds"})
    integer(reserve["actions"], 0, 0)
    integer(reserve["seconds"], 0, 0)
    contexts = sequence(body["context"])
    inputs = sequence(body["input_artifact_refs"])
    case_version = 1
    if inputs:
        if len(inputs) != 1:
            raise CatalogError("MANAGED_REJECTED")
        case_version = 2 if ref(inputs[0])["kind"] == "contract-case-records" else 1
        ref(inputs[0], "contract-case-records" if case_version == 2 else "contract-case-input")
    if len(contexts) != (3 if inputs else 2):
        raise CatalogError("MANAGED_REJECTED")
    for item in contexts:
        context = exact(item, {"ref", "epistemic_state", "summary", "mandatory"})
        ref(context["ref"])
        text(context["summary"])
        if context["epistemic_state"] != "OBSERVED" or context["mandatory"] is not True:
            raise CatalogError("MANAGED_REJECTED")
    bindings = sequence(body["procedure_bindings"])
    if len(bindings) != 1:
        raise CatalogError("MANAGED_REJECTED")
    binding = exact(bindings[0], {"procedure_ref", "slot_values", "bound_procedure_ref"})
    ref(binding["procedure_ref"], "procedure")
    bound = ref(binding["bound_procedure_ref"], "bound-procedure")
    slots = capture_slot_values(binding["slot_values"], version=case_version) if inputs else []
    if (
        binding["slot_values"] != slots
        or (inputs and slots[0]["refs"] != inputs)
        or body["procedure_refs"] != [binding["procedure_ref"]]
    ):
        raise CatalogError("MANAGED_REJECTED")
    header = exact(
        body["header"],
        set(
            "schema_version run_id task_id attempt_id snapshot_ref mission_revision focus_ref through_cursor brief_revision result_schema_ref".split()
        ),
    )
    integer(header["schema_version"], 1, 1)
    integer(header["brief_revision"], 1, 1)
    for key in ("run_id", "task_id", "attempt_id", "through_cursor"):
        uuid_string(header[key])
    for key, kind in (
        ("snapshot_ref", "run-snapshot"),
        ("mission_revision", "mission"),
        ("focus_ref", "focus"),
        ("result_schema_ref", "schema"),
    ):
        ref(header[key], kind)
    rows = sequence(exact(body["method_plan"], {"requirements"})["requirements"])
    if not 1 <= len(rows) <= 128:
        raise CatalogError("MANAGED_REJECTED")
    seen: set[bytes] = set()
    for raw in rows:
        row = exact(raw, {"ref", "applicability", "applicability_basis_refs", "required"})
        requirement = exact(row["ref"], {"bound_procedure_ref", "requirement_key"})
        if canonical(requirement["bound_procedure_ref"]) != canonical(bound):
            raise CatalogError("MANAGED_REJECTED")
        ref(requirement["bound_procedure_ref"], "bound-procedure")
        text(requirement["requirement_key"], 128)
        if (
            canonical(requirement) in seen
            or type(row["required"]) is not bool
            or row["applicability"] not in ("APPLIES", "NOT_APPLICABLE", "UNKNOWN")
        ):
            raise CatalogError("MANAGED_REJECTED")
        for basis in sequence(row["applicability_basis_refs"]):
            ref(basis, "contract-case-records")
        seen.add(canonical(requirement))
    return result


def receive_disposition(
    instance: dict[str, object],
    lease: dict[str, object],
    fence: object,
    now: datetime,
    *,
    held: bool,
) -> str:
    """Receive-only classification under instance→lease→managed locks."""
    historical = authority(fence)
    expiry = lease.get("expires_at")
    current = (
        str(instance.get("instance_id")) == historical["instance_id"]
        and instance.get("generation") == historical["generation"]
        and instance.get("shutdown_command_id") is None
        and instance.get("admission_open") is True
        and str(lease.get("owner")) == historical["owner"]
        and lease.get("epoch") == historical["epoch"]
        and isinstance(expiry, datetime)
        and expiry.tzinfo is not None
        and now.tzinfo is not None
        and expiry > now
    )
    return "RECEIVED" if current and not held else "HELD_FOR_RECONCILIATION"


def require_unexpired(brief: object, now: datetime) -> None:
    """Admission only: caller supplies current DB time after its owner lock."""
    body = mapping(validate_brief(brief)["payload"])
    if now.tzinfo is None:
        raise CatalogError("STORAGE_INCOMPATIBLE")
    if datetime.fromisoformat(text(body["deadline"])) <= now:
        raise CatalogError("BRIEF_EXPIRED")


def validate_cursor(header: object, cursor: object, run: object) -> None:
    """Resolve the cold snapshot token, not a fabricated or cross-scope UUID.

    Sequence 1 is the single immutable initial snapshot of this cold run. This
    does not implement a general event stream or claim an updated result cursor.
    """
    checked_header = mapping(header)
    checked_cursor = record(cursor, "managed-cursor")
    checked_run = record(run, "managed-run")
    body = exact(checked_cursor["payload"], {"run_id", "mission_ref", "focus_ref", "sequence"})
    run_body = mapping(checked_run["payload"])
    integer(body["sequence"], 1, 1)
    if (
        checked_header["through_cursor"] != checked_cursor["id"]
        or body["run_id"] != checked_run["id"]
        or checked_header["run_id"] != checked_run["id"]
        or canonical(body["mission_ref"]) != canonical(checked_header["mission_revision"])
        or canonical(body["mission_ref"]) != canonical(run_body["mission_ref"])
        or canonical(body["focus_ref"]) != canonical(checked_header["focus_ref"])
        or canonical(body["focus_ref"]) != canonical(run_body["focus_ref"])
    ):
        raise CatalogError("CURSOR_MISMATCH")


def validate_assignment(
    brief: object,
    bound: object,
    *,
    prompt_bundle: object = None,
    composition_version: object = None,
) -> None:
    body = mapping(validate_brief(brief)["payload"])
    bound_record = record(bound, "bound-procedure")
    bound_body = exact(
        bound_record["payload"],
        {"procedure_ref", "slot_values", "resolved_procedure", "mission_ref"},
    )
    bound_ref = records.reference(bound_record)
    expected_binding = {
        "procedure_ref": bound_body["procedure_ref"],
        "slot_values": bound_body["slot_values"],
        "bound_procedure_ref": bound_ref,
    }
    if canonical(body["procedure_bindings"]) != canonical([expected_binding]) or canonical(
        bound_body["mission_ref"]
    ) != canonical(mapping(body["header"])["mission_revision"]):
        raise CatalogError("ASSIGNMENT_MISMATCH")
    procedure = mapping(bound_body["resolved_procedure"])
    invalidation_declaration(procedure)
    from omnis.modules.tasks.criterion_checks import bindings

    known_steps = [mapping(s)["id"] for s in sequence(procedure["probe"])]
    for criterion in bindings(body["criterion_bindings"]):
        if criterion["bound_procedure_ref"] != bound_ref or criterion["step_ids"] != known_steps:
            raise CatalogError("CRITERION_BINDING_MISMATCH")

    def contains_case_ref(value: object) -> bool:
        if isinstance(value, dict):
            return value.get("kind") in {"contract-case-input", "contract-case-records"} or any(
                contains_case_ref(v) for v in value.values()
            )
        return isinstance(value, list) and any(contains_case_ref(v) for v in value)

    if not bound_body["slot_values"] and contains_case_ref(procedure):
        raise CatalogError("ASSIGNMENT_MISMATCH")
    if bound_body["slot_values"]:
        version = 2 if procedure["key"] == "map-records" else 1
        slots = capture_slot_values(bound_body["slot_values"], version=version)
        validate_capture_procedure(procedure, sequence(slots[0]["refs"])[0], version=version)
    validate_predicates(
        body, bound_record, prompt_bundle=prompt_bundle, composition_version=composition_version
    )
    if canonical(body["required_evidence"]) != canonical(required_evidence(bound_record)):
        raise CatalogError("ASSIGNMENT_MISMATCH")
    requirements = sequence(procedure["method_requirements"])
    expected = compile_method_plan(bound_record)
    if any(mapping(r)["applies_if"] for r in requirements):
        requirement_conditions(procedure, sequence(body["input_artifact_refs"])[0])
        for row, published in zip(
            expected, sequence(mapping(body["method_plan"])["requirements"]), strict=True
        ):
            candidate = mapping(published)
            if row["applicability"] == "UNKNOWN":
                if (
                    candidate["applicability"] not in ("APPLIES", "NOT_APPLICABLE")
                    or candidate["applicability_basis_refs"] != body["input_artifact_refs"]
                ):
                    raise CatalogError("ASSIGNMENT_MISMATCH")
                row["applicability"] = candidate["applicability"]
                row["applicability_basis_refs"] = candidate["applicability_basis_refs"]
    if canonical(mapping(body["method_plan"])["requirements"]) != canonical(expected):
        raise CatalogError("ASSIGNMENT_MISMATCH")
    header = mapping(body["header"])
    if [mapping(c)["ref"] for c in sequence(body["context"])] != [
        header["mission_revision"],
        header["focus_ref"],
        *sequence(body["input_artifact_refs"]),
    ]:
        raise CatalogError("ASSIGNMENT_MISMATCH")


def validate_result_header(value: object) -> dict[str, object]:
    header = exact(
        value,
        set(
            "schema_version run_id task_id attempt_id snapshot_ref mission_revision focus_ref through_cursor brief_revision result_schema_ref".split()
        ),
    )
    integer(header["schema_version"], 1, 1)
    integer(header["brief_revision"], 1, 1)
    for key in ("run_id", "task_id", "attempt_id", "through_cursor"):
        uuid_string(header[key])
    for key, kind in (
        ("snapshot_ref", "run-snapshot"),
        ("mission_revision", "mission"),
        ("focus_ref", "focus"),
        ("result_schema_ref", "schema"),
    ):
        ref(header[key], kind)
    return header


def blocked_result(brief: object) -> dict[str, object]:
    body = mapping(validate_brief(brief)["payload"])
    rows = sequence(mapping(body["method_plan"])["requirements"])
    return records.envelope(
        "task-result",
        {
            "header": body["header"],
            "status": "BLOCKED",
            "method_results": [
                {
                    "ref": mapping(r)["ref"],
                    "state": "NOT_RUN",
                    "basis_refs": [],
                    "artifact_refs": [],
                    "reason": "NO_MODEL: native cold admission refused before method execution.",
                }
                for r in rows
            ],
            "method_review": None,
            **{k: [] for k in RESULT_EMPTY},
            "gaps": ["NO_MODEL; every published method requirement remains unexecuted."],
            "usage": {"state": "KNOWN", "model_calls": 0, "target_actions": 0, "cost": "0"},
        },
    )


def method_check(brief: object, result: object, checker_ref: object) -> dict[str, object]:
    brief_record = validate_brief(brief)
    result_record = record(result, "task-result")
    expected = blocked_result(brief_record)
    if canonical(result_record["payload"]) != canonical(expected["payload"]):
        raise CatalogError("RESULT_CONFLICT")
    method_results = sequence(mapping(result_record["payload"])["method_results"])
    return records.envelope(
        "method-check",
        {
            "brief_ref": records.reference(brief_record),
            "task_result_ref": records.reference(result_record),
            "checker_ref": ref(checker_ref, "method-checker"),
            "status": "INCOMPLETE",
            "checked_results": method_results,
            "gap_refs": [mapping(r)["ref"] for r in method_results],
            "reason": "Native NO_MODEL proves no method step ran. Contract validation is not method completion.",
        },
    )


def mapping(value: object) -> dict[str, object]:
    if type(value) is not dict or any(type(k) is not str for k in value):
        raise CatalogError("MANAGED_REJECTED")
    return dict(value)


def sequence(value: object) -> list[object]:
    if type(value) is not list:
        raise CatalogError("MANAGED_REJECTED")
    return list(value)


def text(value: object, maximum: int = 4096) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise CatalogError("MANAGED_REJECTED")
    clean_text(value)
    return value


def integer(value: object, minimum: int, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CatalogError("MANAGED_REJECTED")
    return value


def exact(value: object, fields: set[str]) -> dict[str, object]:
    result = mapping(value)
    if set(result) != fields:
        raise CatalogError("MANAGED_REJECTED")
    bounded(result)
    clean_text(result)
    if len(canonical(result)) > 1048576:
        raise CatalogError("MANAGED_REJECTED")
    return mapping(load_json(canonical(result)))


def ref(value: object, kind: str | None = None) -> dict[str, object]:
    result = valid_ref(value)
    if kind is not None and result["kind"] != kind:
        raise CatalogError("MANAGED_REJECTED")
    return result


def record(value: object, kind: str | None = None) -> dict[str, object]:
    result = records.checked(value)
    integer(result["schema_version"], 1, 1)
    revision = integer(result["revision"], 1, 2 if result["kind"] == "mission" else 1)
    ref(records.reference(result), kind)
    bounded(result)
    clean_text(result)
    if revision == 2:
        from omnis.modules.tasks.mission_revisions import payload

        payload(result["payload"])
    return mapping(load_json(canonical(result)))


def authority(value: object) -> dict[str, object]:
    result = exact(value, {"instance_id", "owner", "epoch", "generation"})
    uuid_string(result["instance_id"])
    uuid_string(result["owner"])
    integer(result["epoch"], 1)
    integer(result["generation"], 0)
    return result


def validate_manifest(value: object) -> dict[str, object]:
    result = record(value, "launch-manifest")
    # Match the native stage payload budget, including its protocol wrapper.
    # Keep this pure producer check independent of optional runtime imports.
    if len(canonical({"protocol": PROTOCOL, "manifest": result})) > 32768:
        raise CatalogError("MANAGED_REJECTED")
    composed = "composition_version" in mapping(result["payload"])
    body = exact(
        result["payload"],
        {"run_id", "selection_ref", "resolution", "effective", "entries"}
        | ({"composition_version"} if composed else set()),
    )
    if composed:
        integer(body["composition_version"], 1, 4)
    uuid_string(body["run_id"])
    ref(body["selection_ref"], "execution-selection")
    if body["resolution"] != "NO_MODEL" or body["effective"] is not None:
        raise CatalogError("MANAGED_REJECTED")
    entries = sequence(body["entries"])
    if not 1 <= len(entries) <= (1 if body.get("composition_version") in (2, 3, 4) else 2):
        raise CatalogError("MANAGED_REJECTED")
    identities: set[str] = set()
    for index, raw in enumerate(entries):
        entry = exact(
            raw,
            {"batch_index", "task_id", "attempt_id", "brief_ref", "goal"}
            | ({"composition_ref"} if composed else set()),
        )
        if composed:
            ref(entry["composition_ref"], "prompt-composition")
        integer(entry["batch_index"], index, index)
        ids = [uuid_string(entry[k]) for k in ("task_id", "attempt_id")]
        ids.append(uuid_string(ref(entry["brief_ref"], "task-brief")["id"]))
        for identity in ids:
            if identity in identities:
                raise CatalogError("MANAGED_REJECTED")
            identities.add(identity)
        # Native text(goal, 4096) is byte-bounded and single-line. Do not apply
        # this grammar to unrelated methodological text or alter source bytes.
        goal = text(entry["goal"])
        if len(goal.encode("utf-8")) > 4096 or any(
            ord(c) < 32 or 127 <= ord(c) <= 159 or c in "\u2028\u2029" for c in goal
        ):
            raise CatalogError("MANAGED_REJECTED")
    return result


def manifest_protocol(value: object) -> str:
    body = mapping(validate_manifest(value)["payload"])
    if body.get("composition_version") == 4:
        return "omnis-managed-admission-v4"
    if body.get("composition_version") == 3:
        return "omnis-managed-admission-v3"
    return "omnis-managed-admission-v2" if "composition_version" in body else PROTOCOL


def validate_stage(value: object, manifest: object) -> dict[str, object]:
    source = validate_manifest(manifest)
    result = exact(
        value, {"protocol", "status", "ticket", "manifest_ref", "native_root_id", "entries"}
    )
    if result["protocol"] != manifest_protocol(source) or result["status"] != "STAGED":
        raise CatalogError("MANAGED_REJECTED")
    uuid_string(result["ticket"])
    if ref(result["manifest_ref"], "launch-manifest") != records.reference(source):
        raise CatalogError("MANAGED_REJECTED")
    root = text(result["native_root_id"], 128)
    entries = sequence(result["entries"])
    expected = sequence(mapping(source["payload"])["entries"])
    if len(entries) != len(expected):
        raise CatalogError("MANAGED_REJECTED")
    children = {root}
    sessions: set[str] = set()
    for raw, wanted in zip(entries, expected, strict=True):
        entry = exact(
            raw,
            {
                "batch_index",
                "task_id",
                "attempt_id",
                "brief_ref",
                "native_child_id",
                "native_session_id",
            }
            | (
                {"composition_ref"}
                if "composition_version" in mapping(source["payload"])
                else set()
            ),
        )
        projection = {
            k: v for k, v in entry.items() if k not in {"native_child_id", "native_session_id"}
        }
        if canonical(projection) != canonical(
            {k: v for k, v in mapping(wanted).items() if k != "goal"}
        ):
            raise CatalogError("MANAGED_REJECTED")
        child, session = text(entry["native_child_id"], 128), text(entry["native_session_id"], 128)
        if child in children or session in sessions:
            raise CatalogError("MANAGED_REJECTED")
        children.add(child)
        sessions.add(session)
    return result


def binding_record(
    manifest: object, stage: object, runtime_boot: object, fence: object
) -> dict[str, object]:
    source = validate_manifest(manifest)
    staged = validate_stage(stage, source)
    return records.envelope(
        "runtime-binding",
        {
            "runtime_boot": uuid_string(runtime_boot),
            "run_id": mapping(source["payload"])["run_id"],
            "ticket": staged["ticket"],
            "native_root_id": staged["native_root_id"],
            "entries": staged["entries"],
            "authority": authority(fence),
        },
    )


def validate_binding(value: object, manifest: object) -> dict[str, object]:
    result = record(value, "runtime-binding")
    body = exact(
        result["payload"],
        {"runtime_boot", "run_id", "ticket", "native_root_id", "entries", "authority"},
    )
    staged = {
        "protocol": manifest_protocol(manifest),
        "status": "STAGED",
        "manifest_ref": records.reference(validate_manifest(manifest)),
        **{k: body[k] for k in ("ticket", "native_root_id", "entries")},
    }
    expected = binding_record(manifest, staged, body["runtime_boot"], body["authority"])
    if canonical(expected["payload"]) != canonical(body):
        raise CatalogError("MANAGED_REJECTED")
    return result


def validate_final(value: object, manifest: object, binding: object) -> dict[str, object]:
    bound = validate_binding(binding, manifest)
    method_execution = manifest_protocol(manifest) == "omnis-managed-admission-v4"
    result = exact(
        value,
        {
            "protocol",
            "status",
            "reason",
            "ticket",
            "manifest_ref",
            "binding_ref",
            "native_root_id",
            "entries",
        }
        | ({"executions"} if method_execution else set()),
    )
    if result["status"] not in (
        ("SUCCEEDED", "INCONCLUSIVE") if method_execution else ("BLOCKED",)
    ) or result["reason"] != ("CONTRACT_PURE" if method_execution else "NO_MODEL"):
        raise CatalogError("MANAGED_REJECTED")
    stage = validate_stage(
        {
            k: ("STAGED" if k == "status" else v)
            for k, v in result.items()
            if k not in {"reason", "binding_ref", "executions"}
        },
        manifest,
    )
    if ref(result["binding_ref"], "runtime-binding") != records.reference(bound):
        raise CatalogError("MANAGED_REJECTED")
    body = mapping(bound["payload"])
    if any(
        canonical(stage[k]) != canonical(body[k]) for k in ("ticket", "native_root_id", "entries")
    ):
        raise CatalogError("MANAGED_REJECTED")
    if method_execution:
        if len(canonical(result)) > 32768:
            raise CatalogError("RESULT_OVERFLOW")
        executions = sequence(result["executions"])
        entries = sequence(body["entries"])
        if len(executions) != len(entries):
            raise CatalogError("RESULT_CONFLICT")
        for raw, native in zip(executions, entries, strict=True):
            execution = exact(raw, {"native_child_id", "native_session_id", "brief_ref", "records"})
            entry = mapping(native)
            if any(
                canonical(execution[k]) != canonical(entry[k])
                for k in ("native_child_id", "native_session_id", "brief_ref")
            ):
                raise CatalogError("LINEAGE_MISMATCH")
            ref(execution["brief_ref"], "task-brief")
            output = [record(r) for r in sequence(execution["records"])]
            if len(output) not in (4, 6, 8) or len({text(r["id"]) for r in output}) != len(output):
                raise CatalogError("RESULT_CONFLICT")
            if mapping(output[0]["payload"])["status"] != result["status"]:
                raise CatalogError("RESULT_CONFLICT")
            steps = (len(output) - 2) // 2
            if [r["kind"] for r in output] != ["task-result"] + ["contract-tool-receipt"] * (
                steps + 1
            ) + ["contract-artifact"] * steps:
                raise CatalogError("RESULT_CONFLICT")
    return result
