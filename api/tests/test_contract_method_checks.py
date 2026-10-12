"""SOURCE-only receipt consumer tests, NOT native authentication/persistence proof.

Source identities and native state holders are synthetic. Execution records are
produced by the real native run_contract/BoundContractTools, without replacement
emitters or mocked PURE outputs. The owning caller must authenticate the final.
"""

import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast
from uuid import uuid4

import pytest

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json, load_yaml

Data = dict[str, object]
ROOT = Path(__file__).resolve().parents[2]


def obj(value: object) -> Data:
    assert isinstance(value, dict)
    return value


def rows(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


class NativeFixture(Protocol):
    def __call__(self, records: bool = False, value: object = None) -> Data: ...


Check = Callable[
    [object, object, object, object, object, object, list[Data], dict[str, Data], str], Data
]


@dataclass
class Case:
    brief: Data
    bound: Data
    binding: Data
    execution: Data
    checker: Data
    original: Data
    actions: list[Data]
    schemas: dict[str, Data]
    owner_id: str
    prompt_bundle: Data
    stage: Data

    def check(self, *, receive_only: bool = False) -> Data:
        try:
            module = importlib.import_module("omnis.modules.tasks.method_checks")
        except ModuleNotFoundError:
            pytest.fail("receipt-backed MethodCheck checker missing")
        checker = getattr(module, "check_execution", None)
        assert callable(checker), "receipt-backed check_execution missing"
        return obj(
            checker(
                self.brief,
                self.bound,
                self.binding,
                self.execution,
                self.checker,
                self.original,
                self.actions,
                self.schemas,
                self.owner_id,
                prompt_bundle=self.prompt_bundle,
                composition_version=4,
                receive_only=receive_only,
            )
        )


def reseal_assignment(stage: Data, sections: list[object], bundle: Data) -> None:
    """Typed facade for the existing test-only native reseal helper."""
    reseal = cast(
        Callable[[Data, list[object], Data], None],
        importlib.import_module("test_prompt_bundle").reseal_graph,
    )
    reseal(stage, sections, bundle)


def native_case(
    version: int = 2,
    empty: bool = False,
    criterion_ids: list[str] | None = None,
    predicates: bool = False,
    composer_pin: str | None = None,
    compact: bool = False,
) -> Case:
    """Real native producer on synthetic state; not constructor/owner authority."""
    paths = [
        str(ROOT / "integrations/hermes/src"),
        str(ROOT / "integrations/hermes/tests"),
        str(ROOT / "integrations/hermes/upstream/managed-source"),
    ]
    sys.path[:0] = paths
    try:
        fixture = cast(
            NativeFixture, importlib.import_module("test_contract_method").method_fixture
        )
        reseal = reseal_assignment
        native = importlib.import_module("agent.contract_execution")
        cold = importlib.import_module("agent.cold_admission")
        cold_state = cast(Callable[[str, str, None], object], cold.ColdState)
        contract_state = cast(
            Callable[[str, str, str, object, bytes, bytes, object], object], native.ContractState
        )
        run = cast(Callable[[object, bytes, Callable[[], bool]], Data], native.run_contract)
        value: Data = {
            "records": []
            if empty
            else [
                {"method": "POST", "path": "/synthetic-z", "status": 201},
                {"method": "GET", "path": "/synthetic-a", "status": 404},
                {"method": "GET", "path": "/synthetic-a", "status": 200},
            ]
        }
        stage = fixture(
            records=version == 2,
            value=value if version == 2 else canonical(value["records"]).decode(),
        )
        composition = obj(rows(stage["compositions"])[0])
        payload = obj(composition["payload"])
        sections = rows(load_json(cast(str, payload["text"])))
        brief, bound = (obj(obj(s)["record"]) for s in sections[2:4])
        original = obj(obj(sections[4])["input"])
        procedure = obj(obj(bound["payload"])["resolved_procedure"])
        steps = [obj(s) for s in rows(procedure["probe"])]
        actions: list[Data] = []
        schemas: dict[str, Data] = {}
        for step in steps:
            action = records.envelope(
                "action_definition",
                {
                    "handler_id": "contract." + cast(str, step["id"]),
                    "execution_class": "PURE",
                    "allowed_capability_ids": [],
                    "dispatch_permitted": False,
                },
            )
            actions.append(action)
            step["action_definition_ref"] = records.reference(action)
            schema_name = {
                "parse-capture": "records",
                "normalize-operations": "operations",
                "build-map": "surface_map",
            }[cast(str, step["id"])]
            path = (
                ROOT
                / "skills/records-mapping-contract/templates/schemas"
                / (schema_name + ".schema.json")
            )
            schemas[canonical(step["output_schema_ref"]).decode()] = obj(
                load_json(path.read_bytes())
            )
        material_schema = obj(obj(sections[4])["schema"])
        schemas[canonical(procedure["input_schema_ref"]).decode()] = obj(
            material_schema["document"]
        )
        if version == 2:
            # Published first-party obligations, including optional original preservation.
            template = obj(
                load_yaml(
                    (
                        ROOT
                        / "skills/records-mapping-contract/templates/procedures"
                        / "map-records.yaml"
                    ).read_bytes()
                )
            )
            requirements = [obj(r) for r in rows(template["method_requirements"])]
            schema_pins = {
                "records": procedure["input_schema_ref"],
                "operations": steps[0]["output_schema_ref"],
                "surface_map": steps[1]["output_schema_ref"],
            }
            for requirement in requirements:
                requirement["artifact_schema_refs"] = [
                    schema_pins[cast(str, obj(r)["key"])]
                    for r in rows(requirement["artifact_schema_refs"])
                ]
            procedure["method_requirements"] = requirements
            obj(brief["payload"])["method_plan"] = {
                "requirements": [
                    {
                        "ref": {
                            "bound_procedure_ref": records.reference(bound),
                            "requirement_key": r["key"],
                        },
                        "required": r["required"],
                        "applicability": "APPLIES",
                        "applicability_basis_refs": [],
                    }
                    for r in requirements
                ]
            }
        if predicates:
            obj(brief["payload"])["done_when"] = [
                {"bound_procedure_ref": records.reference(bound), "predicate_id": obj(r)["key"]}
                for r in rows(procedure["method_requirements"])
            ]
            obj(brief["payload"])["return_when"] = [
                {
                    "bound_procedure_ref": records.reference(bound),
                    "predicate_id": "build-surface-map",
                }
            ]
        bundle = obj(payload["prompt_bundle"])
        from omnis_hermes.prompt_bundle import CRITERIA_COMPOSER_REVISION, composer_revision

        obj(bundle["payload"])["composer_revision"] = composer_pin or (
            composer_revision() if predicates else CRITERIA_COMPOSER_REVISION
        )
        reseal(stage, sections, bundle)
        if criterion_ids:
            rule = records.reference(records.envelope("criterion-outcome-rule", {}))
            obj(brief["payload"])["criterion_bindings"] = [
                {
                    "criterion_id": i,
                    "bound_procedure_ref": records.reference(bound),
                    "step_ids": [s["id"] for s in steps],
                    "outcome_rule_ref": rule,
                }
                for i in criterion_ids
            ]
            reseal(stage, sections, obj(payload["prompt_bundle"]))
        manifest = obj(stage["manifest"])
        if compact:
            from omnis.modules.tasks import managed_composition

            retained_bundle = obj(payload["prompt_bundle"])
            base, role = (obj(obj(s)["record"]) for s in sections[:2])
            material = obj(sections[4])
            composition = managed_composition.compose(
                retained_bundle,
                base,
                role,
                brief,
                bound,
                obj(payload["preparation_receipt_ref"]),
                [obj(s) for s in sections[5:]],
                case_input=material,
                method_execution=True,
            )
            manifest = records.envelope("launch-manifest", obj(manifest["payload"]))
            obj(rows(obj(manifest["payload"])["entries"])[0])["composition_ref"] = (
                records.reference(composition)
            )
            manifest["digest"] = sha256(
                canonical({k: v for k, v in manifest.items() if k != "digest"})
            ).hexdigest()
            stage = managed_composition.stage_payload(
                manifest,
                [
                    retained_bundle,
                    base,
                    role,
                    brief,
                    bound,
                    obj(material["context"]),
                    original,
                    composition,
                    manifest,
                ],
            )
        manifest_body = obj(manifest["payload"])
        root_id, root_session, child_id, session_id = (str(uuid4()) for _ in range(4))
        entry = {k: v for k, v in obj(rows(manifest_body["entries"])[0]).items() if k != "goal"}
        entry.update(native_child_id=child_id, native_session_id=session_id)
        binding = records.envelope(
            "runtime-binding",
            {
                "runtime_boot": str(uuid4()),
                "run_id": manifest_body["run_id"],
                "ticket": str(uuid4()),
                "native_root_id": root_id,
                "entries": [entry],
                "authority": {
                    "instance_id": str(uuid4()),
                    "owner": obj(original["payload"])["owner_id"],
                    "epoch": 1,
                    "generation": 0,
                },
            },
        )
        root = SimpleNamespace(
            session_id=root_session,
            _subagent_id=root_id,
            _cold_state=cold_state(root_session, root_id, None),
        )
        state = contract_state(
            session_id,
            child_id,
            root_session,
            root,
            canonical(stage),
            canonical(manifest),
            obj(brief["payload"])["deadline"],
        )
        child = SimpleNamespace(
            _contract_state=state,
            session_id=session_id,
            _subagent_id=child_id,
            _parent_session_id=root_session,
        )
        execution = run(child, canonical(binding), lambda: True)
        from omnis.modules.tasks.method_checker_identity import descriptor

        checker = records.envelope("method-checker", descriptor())
        return Case(
            brief,
            bound,
            binding,
            execution,
            checker,
            original,
            actions,
            schemas,
            str(obj(original["payload"])["owner_id"]),
            obj(payload["prompt_bundle"]),
            stage,
        )
    finally:
        del sys.path[: len(paths)]


def test_real_receipts_complete_all_three_published_requirements() -> None:
    case = native_case()
    check = case.check()
    records.checked(check)
    assert check["kind"] == "method-check"
    body = obj(check["payload"])
    result = obj(rows(case.execution["records"])[0])
    assert body["status"] == "COMPLETE"
    assert body["brief_ref"] == records.reference(case.brief)
    assert body["task_result_ref"] == records.reference(result)
    assert body["checker_ref"] == records.reference(case.checker)
    assert body["gap_refs"] == []
    checked = rows(body["checked_results"])
    assert len(checked) == 3
    assert checked == obj(result["payload"])["method_results"]
    assert obj(checked[-1])["artifact_refs"] == [records.reference(case.original)]
    assert all(obj(row)["state"] == "DONE" for row in checked)


def rebind_mutation(case: Case) -> None:
    """Reseal hostile mutations, not execution evidence. Preserve all record IDs."""
    replacements: dict[bytes, Data] = {}

    def rewrite(value: object) -> object:
        if isinstance(value, dict):
            if set(value) == {"kind", "id", "revision", "digest"}:
                replacement = replacements.get(canonical(value))
                if replacement is not None:
                    return replacement
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    published = [obj(r) for r in rows(case.execution["records"])]
    ordered = [
        case.original,
        *case.actions,
        case.bound,
        case.brief,
        case.binding,
        *[r for r in published if r["kind"] == "contract-artifact"],
        *[r for r in published if r["kind"] == "contract-tool-receipt"],
        *[r for r in published if r["kind"] == "task-result"],
    ]
    for record in ordered:
        previous = canonical(records.reference(record))
        record["payload"] = rewrite(record["payload"])
        record["digest"] = sha256(
            canonical({k: v for k, v in record.items() if k != "digest"})
        ).hexdigest()
        replacements[previous] = records.reference(record)
    case.execution["brief_ref"] = records.reference(case.brief)


@pytest.mark.parametrize("position", ["input", "operations", "surface_map"])
def test_missing_qualified_schema_cannot_complete(position: str) -> None:
    case = native_case()
    procedure = obj(obj(case.bound["payload"])["resolved_procedure"])
    key = (
        procedure["input_schema_ref"]
        if position == "input"
        else obj(rows(procedure["probe"])[0 if position == "operations" else 1])[
            "output_schema_ref"
        ]
    )
    del case.schemas[canonical(key).decode()]
    with pytest.raises(CatalogError, match="^METHOD_SCHEMA_UNAVAILABLE$"):
        case.check()


@pytest.mark.parametrize(
    "attack", ["invalid-output", "bool-output", "external-schema", "schema-type"]
)
def test_schema_validation_checks_actual_output_without_recomputation(attack: str) -> None:
    case = native_case()
    artifact = next(
        obj(r) for r in rows(case.execution["records"]) if obj(r)["kind"] == "contract-artifact"
    )
    if attack == "invalid-output":
        obj(artifact["payload"])["value"] = {"operations": "not-an-array"}
    elif attack == "bool-output":
        obj(rows(obj(obj(artifact["payload"])["value"])["operations"])[0])["statuses"] = [True]
    else:
        schema_key = canonical(obj(artifact["payload"])["schema_ref"]).decode()
        case.schemas[schema_key] = (
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$ref": "https://forbidden.invalid/schema",
            }
            if attack == "external-schema"
            else {"type": 7}
        )
    rebind_mutation(case)
    reason = (
        "METHOD_SCHEMA_UNAVAILABLE"
        if attack in ("external-schema", "schema-type")
        else "METHOD_SCHEMA_MISMATCH"
    )
    with pytest.raises(CatalogError, match="^" + reason + "$"):
        case.check()


def test_aggregate_bytes_are_bounded_before_complete() -> None:
    case = native_case()
    obj(obj(case.brief["payload"])["limits"])["max_output_bytes"] = 1
    rebind_mutation(case)
    with pytest.raises(CatalogError, match="^METHOD_OUTPUT_LIMIT$"):
        case.check()


@pytest.mark.parametrize("version,empty", [(1, False), (2, True)])
def test_capture_and_empty_records_use_actual_native_receipts(version: int, empty: bool) -> None:
    case = native_case(version, empty)
    assert obj(case.check()["payload"])["status"] == "COMPLETE"


@pytest.mark.parametrize(
    "attack",
    [
        "missing",
        "duplicate",
        "wrong-child",
        "wrong-session",
        "binding-ref",
        "sequence-bool",
        "sequence-order",
        "step-id",
        "header-bool",
        "header-task",
        "input-foreign",
        "input-extra",
        "output-foreign",
        "output-bool",
        "action-bool",
        "action-foreign",
        "read-output",
        "read-operation",
        "artifact-header",
        "artifact-schema",
        "digest",
        "extra-record",
        "extra-field",
    ],
)
def test_receipt_chain_refuses_malformed_or_foreign_evidence(attack: str) -> None:
    case = native_case()
    published = rows(case.execution["records"])
    receipt = obj(published[2])
    payload = obj(receipt["payload"])
    artifact = next(obj(r) for r in published if obj(r)["kind"] == "contract-artifact")
    if attack == "missing":
        published.pop(2)
    elif attack == "duplicate":
        published[2] = published[1]
    elif attack == "wrong-child":
        payload["native_child_id"] = "foreign-child"
    elif attack == "wrong-session":
        payload["native_session_id"] = "foreign-session"
    elif attack == "binding-ref":
        obj(payload["binding_ref"])["digest"] = "f" * 64
    elif attack == "sequence-bool":
        payload["sequence"] = True
    elif attack == "sequence-order":
        payload["sequence"] = 2
    elif attack == "step-id":
        payload["step_id"] = "build-map"
    elif attack == "header-bool":
        obj(payload["header"])["brief_revision"] = True
    elif attack == "header-task":
        obj(payload["header"])["task_id"] = str(uuid4())
    elif attack == "input-foreign":
        payload["input_refs"] = [case.checker]
    elif attack == "input-extra":
        payload["input_refs"] = [records.reference(case.original), case.checker]
    elif attack == "output-foreign":
        payload["output_ref"] = case.checker
    elif attack == "output-bool":
        obj(payload["output_ref"])["revision"] = True
    elif attack == "action-bool":
        obj(payload["action_definition_ref"])["revision"] = True
    elif attack == "action-foreign":
        payload["action_definition_ref"] = records.reference(case.actions[-1])
    elif attack == "read-output":
        obj(obj(published[1])["payload"])["output_ref"] = records.reference(artifact)
    elif attack == "read-operation":
        obj(obj(published[1])["payload"])["operation"] = "PURE_ACTION"
    elif attack == "artifact-header":
        obj(obj(artifact["payload"])["header"])["attempt_id"] = str(uuid4())
    elif attack == "artifact-schema":
        obj(artifact["payload"])["schema_ref"] = obj(case.original["payload"])["schema_ref"]
    elif attack == "extra-record":
        published.append(case.original)
    elif attack == "extra-field":
        payload["authentic"] = True  # DTO assertions are never provenance.
    elif attack != "digest":
        raise AssertionError(attack)
    rebind_mutation(case)
    if attack == "digest":
        receipt["digest"] = "0" * 64
    with pytest.raises(CatalogError):
        case.check()


@pytest.mark.parametrize(
    "attack",
    [
        "wrong-state",
        "false-na",
        "omitted",
        "optional-omitted",
        "duplicate",
        "extra-basis",
        "missing-basis",
        "extra-artifact",
        "wrong-artifact",
        "extra-action",
        "read-as-action",
        "consumed-input",
        "unknown-usage",
        "bool-usage",
        "gaps",
        "review",
        "status",
        "header",
        "extra-field",
        "reason-type",
    ],
)
def test_result_claims_cannot_substitute_for_exact_published_requirements(attack: str) -> None:
    case = native_case()
    result = obj(rows(case.execution["records"])[0])
    body = obj(result["payload"])
    methods = rows(body["method_results"])
    first = obj(methods[0])
    if attack == "wrong-state":
        first["state"] = "NOT_RUN"
    elif attack == "false-na":
        obj(methods[-1])["state"] = "NOT_APPLICABLE"
    elif attack == "omitted":
        body["method_results"] = []
    elif attack == "optional-omitted":
        methods.pop()
    elif attack == "duplicate":
        methods[-1] = methods[0]
    elif attack == "extra-basis":
        rows(first["basis_refs"]).append(case.checker)
    elif attack == "missing-basis":
        first["basis_refs"] = []
    elif attack == "extra-artifact":
        rows(first["artifact_refs"]).append(records.reference(case.original))
    elif attack == "wrong-artifact":
        first["artifact_refs"] = obj(methods[1])["artifact_refs"]
    elif attack == "extra-action":
        rows(body["action_refs"]).append(case.checker)
    elif attack == "read-as-action":
        body["action_refs"] = [records.reference(obj(rows(case.execution["records"])[1]))]
    elif attack == "consumed-input":
        body["consumed_input_refs"] = []
    elif attack == "unknown-usage":
        obj(body["usage"])["state"] = "UNKNOWN"
    elif attack == "bool-usage":
        obj(body["usage"])["model_calls"] = False
    elif attack == "gaps":
        body["gaps"] = ["not complete"]
    elif attack == "review":
        body["method_review"] = {}
    elif attack == "status":
        body["status"] = "BLOCKED"
    elif attack == "header":
        obj(body["header"])["run_id"] = str(uuid4())
    elif attack == "extra-field":
        body["complete"] = True
    elif attack == "reason-type":
        first["reason"] = True
    else:
        raise AssertionError(attack)
    rebind_mutation(case)
    with pytest.raises(CatalogError):
        case.check()


@pytest.mark.parametrize(
    "attack",
    [
        "child",
        "session",
        "run",
        "task",
        "attempt",
        "entry-bool",
        "brief-bool",
        "extra-entry",
        "owner",
        "input-context-bool",
        "input-schema-bool",
        "action-missing",
        "action-handler",
        "action-dispatch",
        "action-class",
        "action-capability",
        "checker-bool",
        "predicate-done",
        "predicate-return",
        "step-parameters",
        "step-tool",
    ],
)
def test_assignment_input_and_installed_action_pins_are_required(attack: str) -> None:
    case = native_case()
    binding_body = obj(case.binding["payload"])
    entry = obj(rows(binding_body["entries"])[0])
    input_body = obj(case.original["payload"])
    procedure = obj(obj(case.bound["payload"])["resolved_procedure"])
    if attack in ("child", "session"):
        case.execution["native_child_id" if attack == "child" else "native_session_id"] = "foreign"
    elif attack == "run":
        binding_body["run_id"] = str(uuid4())
    elif attack in ("task", "attempt"):
        entry[attack + "_id"] = str(uuid4())
    elif attack == "entry-bool":
        entry["batch_index"] = False
    elif attack == "brief-bool":
        obj(entry["brief_ref"])["revision"] = True
    elif attack == "extra-entry":
        rows(binding_body["entries"]).append(entry.copy())
    elif attack == "owner":
        input_body["owner_id"] = str(uuid4())
    elif attack in ("input-context-bool", "input-schema-bool"):
        obj(input_body["context_ref" if attack == "input-context-bool" else "schema_ref"])[
            "revision"
        ] = True
    elif attack == "action-missing":
        case.actions = []
    elif attack.startswith("action-"):
        field, value = {
            "action-handler": ("handler_id", "contract.build-map"),
            "action-dispatch": ("dispatch_permitted", 0),
            "action-class": ("execution_class", "TARGET_IO"),
            "action-capability": ("allowed_capability_ids", ["network"]),
        }[attack]
        obj(case.actions[0]["payload"])[field] = value
    elif attack == "checker-bool":
        case.checker["revision"] = True
    elif attack.startswith("predicate-"):
        obj(case.brief["payload"])["done_when" if attack == "predicate-done" else "return_when"] = [
            {"bound_procedure_ref": records.reference(case.bound), "predicate_id": "unimplemented"}
        ]
    elif attack == "step-parameters":
        obj(rows(procedure["probe"])[0])["parameters"] = {"override": True}
    elif attack == "step-tool":
        obj(rows(procedure["probe"])[0])["tool_ref"] = case.checker
    else:
        raise AssertionError(attack)
    rebind_mutation(case)
    with pytest.raises(CatalogError):
        case.check()


def test_checker_replay_does_not_call_native_or_api_execution_sinks() -> None:
    from types import FrameType

    case = native_case()
    before = canonical(
        [
            case.brief,
            case.bound,
            case.binding,
            case.execution,
            case.original,
            case.actions,
            case.schemas,
        ]
    )
    calls: list[str] = []
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, arg: object) -> None:
        if event == "call" and frame.f_code.co_name in {
            "run_handler",
            "evaluate_pure",
            "task_result",
            "run_contract",
            "_read_bound_input",
        }:
            calls.append(frame.f_code.co_name)
            raise AssertionError("Checker re-executed a method or emitter")

    sys.setprofile(observe)
    try:
        first, second = case.check(), case.check()
    finally:
        sys.setprofile(previous)
    assert calls == []
    assert first["payload"] == second["payload"]
    assert (
        canonical(
            [
                case.brief,
                case.bound,
                case.binding,
                case.execution,
                case.original,
                case.actions,
                case.schemas,
            ]
        )
        == before
    )


@pytest.mark.parametrize(
    "attack", ["brief-actions", "procedure-actions", "graph-id", "path-final-lf"]
)
def test_native_eligibility_and_output_grammar_are_not_weakened(attack: str) -> None:
    case = native_case()
    procedure = obj(obj(case.bound["payload"])["resolved_procedure"])
    artifact = next(
        obj(r) for r in rows(case.execution["records"]) if obj(r)["kind"] == "contract-artifact"
    )
    if attack == "brief-actions":
        obj(obj(case.brief["payload"])["limits"])["max_actions"] = 1
    elif attack == "procedure-actions":
        obj(procedure["limits"])["max_actions"] = 1
    elif attack == "graph-id":
        obj(rows(case.execution["records"])[0])["id"] = case.brief["id"]
    else:
        obj(rows(obj(obj(artifact["payload"])["value"])["operations"])[0])["path"] = "/x\n"
    rebind_mutation(case)
    with pytest.raises(CatalogError):
        case.check()


def test_refusal_reason_is_sanitized_and_names_the_failed_boundary() -> None:
    for attack, reason in (
        ("sequence-bool", "METHOD_RECEIPT_MISMATCH"),
        ("output-bool", "METHOD_RECEIPT_MISMATCH"),
        ("basis-bool", "RESULT_CONFLICT"),
        ("reason-type", "RESULT_CONFLICT"),
    ):
        case = native_case()
        result = obj(rows(case.execution["records"])[0])
        receipt = obj(rows(case.execution["records"])[2])
        if attack == "sequence-bool":
            obj(receipt["payload"])["sequence"] = True
        elif attack == "output-bool":
            obj(obj(receipt["payload"])["output_ref"])["revision"] = True
        elif attack == "basis-bool":
            method = obj(rows(obj(result["payload"])["method_results"])[0])
            obj(rows(method["basis_refs"])[0])["revision"] = True
        else:
            obj(rows(obj(result["payload"])["method_results"])[0])["reason"] = True
        rebind_mutation(case)
        with pytest.raises(CatalogError, match="^" + reason + "$"):
            case.check()


def test_aggregate_limit_accepts_exact_bytes_and_refuses_one_byte_less() -> None:
    case = native_case()
    actual_bytes = len(canonical(case.execution["records"]))
    obj(obj(case.brief["payload"])["limits"])["max_output_bytes"] = actual_bytes
    rebind_mutation(case)
    assert obj(case.check()["payload"])["status"] == "COMPLETE"
    obj(obj(case.brief["payload"])["limits"])["max_output_bytes"] = actual_bytes - 1
    rebind_mutation(case)
    with pytest.raises(CatalogError, match="^METHOD_OUTPUT_LIMIT$"):
        case.check()


def test_final_execution_ceiling_is_independent_of_published_output_budget() -> None:
    case = native_case()
    procedure = obj(obj(case.bound["payload"])["resolved_procedure"])
    obj(obj(case.brief["payload"])["limits"])["max_output_bytes"] = 1048576
    obj(procedure["limits"])["max_output_bytes"] = 1048576
    artifact = next(
        obj(r) for r in rows(case.execution["records"]) if obj(r)["kind"] == "contract-artifact"
    )
    obj(artifact["payload"])["value"] = {
        "operations": [
            {"method": "GET", "path": "/" + "x" * 239, "statuses": [200]} for _ in range(128)
        ]
    }
    rebind_mutation(case)
    assert 32768 < len(canonical(case.execution)) < 1048576
    with pytest.raises(CatalogError, match="^METHOD_OUTPUT_LIMIT$"):
        case.check()


@pytest.mark.parametrize(
    "field",
    [
        "observation_refs",
        "evidence_refs",
        "candidate_claims",
        "controls",
        "contradiction_refs",
        "next_clues",
        "criterion_results",
        "effect_refs",
        "cleanup_refs",
    ],
)
def test_contract_success_never_invents_other_effect_or_evidence_refs(field: str) -> None:
    case = native_case()
    obj(obj(rows(case.execution["records"])[0])["payload"])[field] = [case.checker]
    rebind_mutation(case)
    with pytest.raises(CatalogError, match="^RESULT_CONFLICT$"):
        case.check()
