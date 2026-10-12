"""Bounded native CONTRACT/PURE transformations.

Provenance: adapted from api/src/omnis/modules/tasks/module_registry.py at
abac977cf841429a65b4304d9c7abf01233dd3d5 (first-party OmnisAI). The same three
algorithms are retained; strict JSON/grammar validation replaces API DTO imports.
No API/runtime/provider/catalog import and no package code loading.
"""

import re
from typing import cast

from .native_preparation_contract import bounded, canonical, loads, obj
from .prompt_bundle import mapping, sequence

Data = dict[str, object]

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
PATH = {"type": "string", "maxLength": 240, "pattern": r"^/[^\\\s]*$"}
STATUS = {"type": "integer", "minimum": 100, "maximum": 599}
METHOD = {"type": "string", "enum": METHODS}


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _array(item: object, maximum: int = 128) -> dict[str, object]:
    return {"type": "array", "maxItems": maximum, "items": item}


RECORDS_SCHEMA = _object(
    {"records": _array(_object({"method": METHOD, "path": PATH, "status": STATUS}))}
)
OPERATIONS_SCHEMA = _object(
    {
        "operations": _array(
            _object(
                {
                    "method": METHOD,
                    "path": PATH,
                    "statuses": {**_array(STATUS), "minItems": 1},
                }
            )
        )
    }
)
SURFACE_SCHEMA = _object(
    {
        "surface_map": _array(
            _object(
                {
                    "path": PATH,
                    "methods": {**_array(METHOD, 7), "uniqueItems": True},
                    "operation_count": {"type": "integer", "minimum": 1, "maximum": 7},
                }
            )
        )
    }
)
OPERATIONS_OUTPUT_SCHEMA = _object(
    {
        "operations": _array(
            _object(
                {
                    "method": METHOD,
                    "path": PATH,
                    "statuses": {**_array(STATUS), "minItems": 1, "uniqueItems": True},
                }
            )
        )
    }
)
OUTPUT_SCHEMAS = {
    "parse-capture": RECORDS_SCHEMA,
    "normalize-operations": OPERATIONS_OUTPUT_SCHEMA,
    "build-map": SURFACE_SCHEMA,
}

STEP_HANDLERS = {
    "parse-capture": "contract.parse-capture",
    "normalize-operations": "contract.normalize-operations",
    "build-map": "contract.build-map",
}


def validate_value(schema: dict[str, object], value: object) -> None:
    # Installed native dependency only; host wire validation stays stdlib-only.
    from jsonschema import Draft202012Validator

    bounded(value)  # Reject bool-as-int, floats, overdeep/oversized values before JSON Schema.
    if not Draft202012Validator(schema).is_valid(value):
        raise ValueError("INVALID_PURE_INPUT")
    # JSON Schema's integer type already excludes bool. Python regex fullmatch
    # also rejects the final-LF exception in JSON Schema's '$' expression.
    if type(value) is dict:
        for collection in ("records", "operations", "surface_map"):
            for row in value.get(collection, []):
                if re.fullmatch(cast(str, PATH["pattern"]), row["path"]) is None:
                    raise ValueError("INVALID_PURE_INPUT")


def run_handler(handler: str, input_object: object) -> object:
    """The three installed algorithms; handler selection never comes from prose."""
    if handler == "contract.parse-capture":
        validate_value(_object({"capture": {"type": "string", "maxLength": 65536}}), input_object)
        capture = obj(input_object, {"capture"})
        parsed = loads(cast(str, capture["capture"]), 65536)
        value = {"records": parsed}
        validate_value(RECORDS_SCHEMA, value)
        return value
    if handler == "contract.normalize-operations":
        validate_value(RECORDS_SCHEMA, input_object)
        grouped: dict[tuple[str, str], set[int]] = {}
        for raw in sequence(mapping(input_object)["records"]):
            row = mapping(raw)
            grouped.setdefault((cast(str, row["path"]), cast(str, row["method"])), set()).add(
                cast(int, row["status"])
            )
        return {
            "operations": [
                {"method": method, "path": path, "statuses": sorted(statuses)}
                for (path, method), statuses in sorted(grouped.items())
            ]
        }
    if handler == "contract.build-map":
        validate_value(OPERATIONS_SCHEMA, input_object)
        methods_by_path: dict[str, set[str]] = {}
        for raw in sequence(mapping(input_object)["operations"]):
            operation = mapping(raw)
            methods_by_path.setdefault(cast(str, operation["path"]), set()).add(
                cast(str, operation["method"])
            )
        return {
            "surface_map": [
                {
                    "path": path,
                    "methods": sorted(methods),
                    "operation_count": len(methods),
                }
                for path, methods in sorted(methods_by_path.items())
            ]
        }
    raise ValueError("UNKNOWN_HANDLER")


def assignment(stage_raw: bytes) -> tuple[Data, Data, Data]:
    """Validate/freeze all assignment material before allocating native identity."""
    from .managed_admission_contract import MAX_BYTES, PROTOCOL_V4, validate_stage

    if type(stage_raw) is not bytes:
        raise ValueError("Immutable assignment required")
    stage = mapping(loads(stage_raw, MAX_BYTES))
    validate_stage(stage)
    if stage["protocol"] != PROTOCOL_V4 or canonical(stage) != stage_raw:
        raise ValueError("CONTRACT v4 assignment required")
    composition = mapping(sequence(stage["compositions"])[0])
    from .prompt_bundle import validate_composition

    manifest = mapping(stage["manifest"])
    entry = sequence(mapping(manifest["payload"])["entries"])[0]
    raw = validate_composition(composition, manifest, entry, record_pool=stage.get("record_pool"))
    sections = sequence(loads(raw, MAX_BYTES))
    brief, bound = (mapping(mapping(s)["record"]) for s in sections[2:4])
    material = mapping(sections[4])
    procedure = mapping(mapping(bound["payload"])["resolved_procedure"])
    expected = list(STEP_HANDLERS) if material["version"] == 1 else list(STEP_HANDLERS)[1:]
    steps = [mapping(s) for s in sequence(procedure["probe"])]
    if (
        [s["id"] for s in steps] != expected
        or any(s["tool_ref"] is not None or s["parameters"] != {} for s in steps)
        or cast(int, mapping(mapping(brief["payload"])["limits"])["max_actions"]) < len(steps)
        or "SUCCEEDED" not in sequence(procedure["outcomes"])
    ):
        raise ValueError("Unsupported CONTRACT method")
    # Refs are retained from the trusted frozen bound procedure, not inferred
    # from goal/skill text, an action key, or an arbitrary tool argument.
    if len({canonical(s["output_schema_ref"]) for s in steps}) != len(steps):
        raise ValueError("Ambiguous output schemas")
    schemas = [s["output_schema_ref"] for s in steps] + [procedure["input_schema_ref"]]
    if any(
        r not in schemas
        for req in sequence(procedure["method_requirements"])
        for r in sequence(mapping(req)["artifact_schema_refs"])
    ):
        raise ValueError("Unsupported required artifact schema")
    return brief, bound, material


def record(kind: str, payload: object) -> Data:
    from uuid import uuid4

    from .managed_admission_contract import envelope
    from .native_preparation_contract import digest

    body = dict(schema_version=1, kind=kind, id=str(uuid4()), revision=1, payload=payload)
    return envelope({**body, "digest": digest(canonical(body))}, kind)


RESULT_EMPTY = "observation_refs evidence_refs candidate_claims controls contradiction_refs next_clues consumed_input_refs criterion_results action_refs effect_refs cleanup_refs".split()


def predicate_values(
    brief: Data,
    bound: Data,
    original: Data,
    receipts: list[Data],
    artifacts: list[Data],
    *,
    prompt_bundle: Data,
) -> dict[str, bool]:
    from .managed_admission_contract import ref
    from .prompt_bundle import RECORD_PREDICATES, predicate_closure, validate_predicates

    body = mapping(brief["payload"])
    validate_predicates(body, bound, prompt_bundle=prompt_bundle, composition_version=4)
    if not body["done_when"] and not body["return_when"]:
        return {}
    procedure = mapping(mapping(bound["payload"])["resolved_procedure"])
    closure = predicate_closure(procedure)
    header = body["header"]
    steps = {mapping(s)["id"]: mapping(s) for s in sequence(procedure["probe"])}
    values: dict[str, bool] = {}
    for name, requirement in closure.items():
        step_id, source = RECORD_PREDICATES[name]
        step = steps[step_id]
        matches = [r for r in receipts if mapping(r["payload"])["step_id"] == step_id]
        outputs = [
            a for a in artifacts if mapping(a["payload"])["schema_ref"] == step["output_schema_ref"]
        ]
        satisfied = len(matches) == 1 and len(outputs) == 1
        if satisfied:
            receipt, artifact = mapping(matches[0]["payload"]), mapping(outputs[0]["payload"])
            validate_value(OUTPUT_SCHEMAS[step_id], artifact["value"])
            satisfied = (
                receipt["header"] == header
                and artifact["header"] == header
                and receipt["operation"] == "PURE_ACTION"
                and receipt["action_definition_ref"] == step["action_definition_ref"]
                and receipt["output_ref"] == ref(outputs[0])
            )
        if source == "INPUT":
            reads = [r for r in receipts if mapping(r["payload"])["operation"] == "READ_INPUT"]
            satisfied = satisfied and len(reads) == 1
            if satisfied:
                read = mapping(reads[0]["payload"])
                satisfied = (
                    read["header"] == header
                    and read["input_refs"] == [ref(original)]
                    and read["output_ref"] == ref(original)
                    and mapping(original["payload"])["schema_ref"]
                    == sequence(requirement["artifact_schema_refs"])[0]
                )
        values[name] = satisfied
    return values


def task_result(
    brief: Data,
    bound: Data,
    original: Data,
    receipts: list[Data],
    artifacts: list[Data],
    *,
    prompt_bundle: Data,
) -> Data:
    from .managed_admission_contract import ref

    body = mapping(brief["payload"])
    values = predicate_values(
        brief, bound, original, receipts, artifacts, prompt_bundle=prompt_bundle
    )
    # A return predicate can permit handoff, but never bypass every done predicate.
    if values:
        if not any(
            values[cast(str, mapping(r)["predicate_id"])] for r in sequence(body["return_when"])
        ):
            raise ValueError("BOUND_RETURN_UNSATISFIED")
        if not all(
            values[cast(str, mapping(r)["predicate_id"])] for r in sequence(body["done_when"])
        ):
            raise ValueError("BOUND_DONE_UNSATISFIED")
    requirements = sequence(
        mapping(mapping(bound["payload"])["resolved_procedure"])["method_requirements"]
    )
    plan = sequence(mapping(body["method_plan"])["requirements"])
    rows: list[Data] = []
    for raw_plan, raw_requirement in zip(plan, requirements, strict=True):
        planned, requirement = mapping(raw_plan), mapping(raw_requirement)
        step_ids = sequence(requirement["step_ids"])
        schemas = sequence(requirement["artifact_schema_refs"])
        basis = [ref(r) for r in receipts if mapping(r["payload"])["step_id"] in step_ids]
        outputs = [ref(a) for a in artifacts if mapping(a["payload"])["schema_ref"] in schemas]
        if mapping(original["payload"])["schema_ref"] in schemas:
            outputs.insert(0, ref(original))
        rows.append(
            dict(
                ref=planned["ref"],
                state="DONE",
                basis_refs=basis,
                artifact_refs=outputs,
                reason="Bound CONTRACT/PURE method completed.",
            )
        )
    result: Data = {
        "header": body["header"],
        "status": "SUCCEEDED",
        "method_results": rows,
        "method_review": None,
        **{k: [] for k in RESULT_EMPTY},
        "gaps": [],
        "usage": {"state": "KNOWN", "model_calls": 0, "target_actions": 0, "cost": "0"},
    }
    result["action_refs"] = [
        ref(r) for r in receipts if mapping(r["payload"])["operation"] == "PURE_ACTION"
    ]
    result["consumed_input_refs"] = [ref(original)]
    result["criterion_results"] = [
        {
            "criterion_id": mapping(b)["criterion_id"],
            "bound_procedure_ref": mapping(b)["bound_procedure_ref"],
            "control_step_ids": [],
            "evidence_refs": [],
            "proposed_outcome": "BLOCKED",
            "gaps": ["ORACLE_UNAVAILABLE", "CONTROLS_UNAVAILABLE"],
        }
        for b in sequence(body["criterion_bindings"])
    ]
    return record("task-result", result)
