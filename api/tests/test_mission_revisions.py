"""Finite M2 SOURCE controls; SQL doubles are not PostgreSQL/native evidence."""

import importlib
import subprocess
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import ModuleType, SimpleNamespace, TracebackType
from typing import Protocol, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs.contract_inputs import ContractInputs, validate_request
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract
from test_c04_criteria import criteria_graph

Data = dict[str, object]


class OutcomeFunction(Protocol):
    def __call__(
        self,
        brief: object,
        result: object,
        check: object,
        graph: list[Data],
        *,
        receive_only: bool = False,
    ) -> list[Data]: ...


def revisions() -> ModuleType:
    try:
        return importlib.import_module("omnis.modules.tasks.mission_revisions")
    except ModuleNotFoundError:
        pytest.fail("finite M2 consumer missing")


def additive(mission: Data) -> Data:
    value = deepcopy(mission)
    body = contract.mapping(value["payload"])
    criterion = {
        "id": str(uuid4()),
        "description": "Independent retained-data obligation.",
        "kind": "FUNCTIONAL",
        "oracle_ref": None,
    }
    body["criteria"] = [*contract.sequence(body["criteria"]), criterion]
    body["done_when"] = [
        *contract.sequence(body["done_when"]),
        {"criterion_id": criterion["id"], "required": True},
    ]
    body["basis_refs"] = [*contract.sequence(body["basis_refs"]), records.reference(mission)]
    value.update(payload=body, revision=2)
    value["digest"] = sha256(
        canonical({k: v for k, v in value.items() if k != "digest"})
    ).hexdigest()
    return value


def test_m2_record_exact_revision_schema_and_graph_identity() -> None:
    graph = criteria_graph([str(uuid4())])
    m1 = next(r for r in graph if r["kind"] == "mission")
    m2 = additive(m1)
    assert contract.record(m2, "mission") == m2
    module = revisions()
    assert module.resolve([*graph, m2], records.reference(m1)) == m1
    assert module.resolve([m2, *graph], records.reference(m2)) == m2
    assert module.legacy_index([m2, *graph])[m1["id"]] == m1
    with pytest.raises(CatalogError):
        module.legacy_index([*graph, m2, m2])
    for revision in (True, 3, "2"):
        wrong = {**m2, "revision": revision}
        wrong["digest"] = sha256(
            canonical({k: v for k, v in wrong.items() if k != "digest"})
        ).hexdigest()
        with pytest.raises(CatalogError):
            contract.record(wrong)


def test_current_checker_closure_pins_its_new_revision_resolver() -> None:
    from omnis.modules.tasks.method_checker_identity import SOURCES

    assert "tasks/mission_revisions.py" in SOURCES


def test_private_append_request_only_consumes_exact_predecessor_ref() -> None:
    m1 = next(r for r in criteria_graph() if r["kind"] == "mission")
    request = {
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "context_ref": records.reference(records.envelope("contract-input-context", {})),
        "mission_ref": records.reference(m1),
        "criterion_id": str(uuid4()),
    }
    assert validate_request("append-mission", request) == request
    for bad in (
        {**request, "schema_version": True},
        {**request, "mission": m1},
        {**request, "mission_ref": {**records.reference(m1), "revision": True}},
        {**request, "criterion_id": True},
    ):
        with pytest.raises(CatalogError):
            validate_request("append-mission", bad)


class Result:
    def __init__(self, rows: Sequence[object]) -> None:
        self.rows = list(rows)

    def mappings(self) -> "Result":
        return self

    def scalars(self) -> "Result":
        return self

    def all(self) -> list[object]:
        return self.rows

    def one_or_none(self) -> object:
        assert len(self.rows) <= 1
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self) -> object:
        return self.one_or_none()


class SQLDouble:
    """Exact query-shape double; not PG constraints/transactions/native proof."""

    def __init__(self, owner: str, run: str, graph: list[Data]) -> None:
        self.owner, self.run, self.graph = owner, run, deepcopy(graph)
        self.writes: list[str] = []
        self.locked = False

    def begin(self) -> "SQLDouble":
        return self

    async def __aenter__(self) -> "SQLDouble":
        return self

    async def __aexit__(
        self,
        typ: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    async def execute(self, statement: object, args: Data) -> Result:
        query = str(statement)
        if "pg_advisory_xact_lock" in query:
            self.locked = True
            return Result([])
        if "INSERT INTO" in query:
            assert self.locked
            item = contract.mapping(
                importlib.import_module("omnis.modules.settings.catalog_schema").load_json(
                    args["body"]
                )
            )
            self.graph.append(item)
            self.writes.append(query)
            return Result([])
        owned = args.get("owner", self.owner) == self.owner
        if "contract-input-command" in query:
            return Result(
                [
                    r
                    for r in self.graph
                    if owned
                    and r["kind"] == "contract-input-command"
                    and contract.mapping(r["payload"])["command_id"] == args["command"]
                ]
            )
        matches = [
            r
            for r in self.graph
            if owned
            and ("id" not in args or r["id"] == args["id"])
            and ("revision" not in args or r["revision"] == args["revision"])
        ]
        if "UNION ALL" not in query:
            matches = [
                r
                for r in matches
                if r["revision"] == (2 if "FROM public.managed_mission_revision" in query else 1)
            ]
        if "SELECT run_id" in query:
            return Result([self.run] if matches else [])
        if "SELECT owner_id,run_id,envelope" in query:
            return Result(
                [{"owner_id": self.owner, "run_id": self.run, "envelope": r} for r in matches]
            )
        if "SELECT envelope" in query:
            return Result(matches)
        raise AssertionError(query)


@pytest.mark.asyncio
async def test_owner_command_store_read_graph_replay_and_new_work_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.tasks import managed_store as store

    graph = criteria_graph([str(uuid4())])
    context = next(r for r in graph if r["kind"] == "contract-input-context")
    context["payload"] = {**contract.mapping(context["payload"]), "version": 2}
    context["digest"] = sha256(
        canonical({k: v for k, v in context.items() if k != "digest"})
    ).hexdigest()
    body = contract.mapping(context["payload"])
    owner = cast(str, body["owner_id"])
    run = cast(str, contract.ref(body["basis_ref"])["id"])
    conn = SQLDouble(owner, run, graph)
    inputs = ContractInputs(cast(AsyncEngine, conn))

    async def qualified_source(*args: object) -> SimpleNamespace:
        assert conn.locked
        return SimpleNamespace(
            procedure=SimpleNamespace(key="map-records", verification_kind="CONTRACT")
        )

    monkeypatch.setattr(inputs, "current_source", qualified_source)
    request = {
        "schema_version": 1,
        "owner_id": owner,
        "command_id": str(uuid4()),
        "context_ref": records.reference(context),
        "mission_ref": body["mission_ref"],
        "criterion_id": str(uuid4()),
    }
    action = getattr(inputs, "append_mission", None)
    assert callable(action), "owner-locked append/read consumer missing"
    before = canonical(conn.graph)
    append = cast(Callable[[object], Awaitable[Data]], action)
    result = await append(request)
    assert result["created"] is True and len(conn.writes) == 2
    m1 = await store.get(cast(AsyncConnection, conn), owner, run, request["mission_ref"])
    m2 = await store.get(cast(AsyncConnection, conn), owner, run, result["mission_ref"])
    assert m1["id"] == m2["id"] and m2["revision"] == 2
    assert canonical(conn.graph[:-2]) == before
    assert (await store.by_id(cast(AsyncConnection, conn), owner, run, m1["id"])) == m1
    assert (await append(request))["created"] is False
    read = await inputs.read(
        "read-mission", {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    )
    assert read["mission"] == m2 and read["predecessor"] == m1
    retained = await store.graph(cast(AsyncConnection, conn), owner, run)
    assert len([r for r in retained if r["kind"] == "mission"]) == 2
    for attack in (
        {**request, "criterion_id": str(uuid4())},
        {**request, "owner_id": str(uuid4())},
        {**request, "mission_ref": {**contract.ref(request["mission_ref"]), "digest": "0" * 64}},
        {**request, "criterion_id": True},
    ):
        with pytest.raises(CatalogError):
            await append(attack)
        assert len(conn.writes) == 2
    with pytest.raises(CatalogError, match="MISSION_REVISION_NEW_WORK_UNSUPPORTED"):
        await inputs.create_input(
            {
                "schema_version": 2,
                "owner_id": owner,
                "command_id": str(uuid4()),
                "context_ref": request["context_ref"],
                "input": {"records": []},
            }
        )
    request_new = {
        "composition_version": 4,
        "schema_version": 3,
        "context_ref": request["context_ref"],
    }
    with pytest.raises(CatalogError, match="MISSION_REVISION_NEW_WORK_UNSUPPORTED"):
        await ManagedAdmission(cast(AsyncEngine, conn))._build(
            cast(AsyncConnection, conn), owner, request_new
        )
    assert len(conn.writes) == 2


@pytest.mark.asyncio
async def test_managed_graph_verification_resolves_both_revisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.runs.managed_admission import ManagedAdmission

    graph = criteria_graph([str(uuid4())])
    m1 = next(r for r in graph if r["kind"] == "mission")
    run = next(r for r in graph if r["kind"] == "managed-run")
    domain = ManagedAdmission(cast(AsyncEngine, None))

    class QualifiedCatalogDouble:
        async def execute(self, *args: object) -> Result:
            return Result(["qualified"])

    async def retained_composition(*args: object) -> None:
        return None

    async def retained_catalog(*args: object) -> tuple[str, Data]:
        return "qualified", {}

    monkeypatch.setattr(domain, "_verify_compositions", retained_composition)
    monkeypatch.setattr(records, "get", retained_catalog)
    context = next(r for r in graph if r["kind"] == "contract-input-context")
    await domain._verify_graph(
        cast(AsyncConnection, QualifiedCatalogDouble()),
        cast(str, contract.mapping(context["payload"])["owner_id"]),
        cast(str, run["id"]),
        [*graph, additive(m1)],
    )


@pytest.mark.parametrize("state", ["complete", "incomplete", "unknown"])
def test_exact_pre_m2_checker_receive_only_reconstructs_supported_states(state: str) -> None:
    from omnis.modules.tasks import method_checker_identity as identity
    from test_contract_method_checks import native_case

    case = native_case(
        predicates=True,
        return_predicate="normalize-records" if state == "incomplete" else "build-surface-map",
    )
    if state == "unknown":
        case.schemas = {}
    old = {
        **identity.descriptor(),
        "code_digest": "833b5690ada0c2669114dc7fc3755300d96116b773f9eb0c412fba024fac8fd9",
    }
    case.checker = records.envelope("method-checker", old)
    received = contract.mapping(case.check(receive_only=True)["payload"])
    assert received["status"] == state.upper()
    with pytest.raises(CatalogError):
        identity.verify(
            case.checker,
            pin="1042abaf48dae5e14a7fee5c879b68fb57313f7e53698a43becf5a57e7a52338",
            receive_only=False,
            zero_predicates=False,
        )
    with pytest.raises(CatalogError):
        identity.verify(case.checker, pin="0" * 64, receive_only=True, zero_predicates=False)


def test_exact_pre_m2_rule_is_receive_only_and_payload_unchanged() -> None:
    from omnis.modules.tasks import criterion_checks

    graph = criteria_graph([str(uuid4())])
    brief, bound, mission, run, rule = [
        next(r for r in graph if r["kind"] == k)
        for k in (
            "task-brief",
            "bound-procedure",
            "mission",
            "managed-run",
            "criterion-outcome-rule",
        )
    ]
    descriptor = {
        **contract.mapping(rule["payload"]),
        "code_digest": "9de1b7a9741df5ce97b44079ac0c1843583a8e1fd1c76b6096e37dc2e2870efb",
    }
    old_rule = {**rule, "payload": descriptor}
    old_rule["digest"] = sha256(
        canonical({k: v for k, v in old_rule.items() if k != "digest"})
    ).hexdigest()
    old_ref, new_ref = records.reference(rule), records.reference(old_rule)

    def replace(value: object) -> object:
        if value == old_ref:
            return new_ref
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        return value

    brief = contract.mapping(replace(brief))
    run = contract.mapping(replace(run))
    for item in (brief, run):
        item["digest"] = sha256(
            canonical({k: v for k, v in item.items() if k != "digest"})
        ).hexdigest()
    criterion_checks.validate_assignment(brief, bound, mission, run, [old_rule], receive_only=True)
    with pytest.raises(CatalogError, match="CRITERION_RULE_UNAVAILABLE"):
        criterion_checks.validate_assignment(brief, bound, mission, run, [old_rule])


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["m2", "old-checker"])
async def test_m2_stage_refuses_before_composition_or_native(
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.tasks import managed_composition

    graph = criteria_graph()
    m1 = next(r for r in graph if r["kind"] == "mission")
    run = next(r for r in graph if r["kind"] == "managed-run")
    manifest = next(r for r in graph if r["kind"] == "launch-manifest")
    if attack == "m2":
        graph.append(additive(m1))
    else:
        checker = next(r for r in graph if r["kind"] == "method-checker")
        checker["payload"] = {
            **contract.mapping(checker["payload"]),
            "code_digest": "833b5690ada0c2669114dc7fc3755300d96116b773f9eb0c412fba024fac8fd9",
        }
        checker["digest"] = sha256(
            canonical({k: v for k, v in checker.items() if k != "digest"})
        ).hexdigest()
    conn = SQLDouble(str(uuid4()), cast(str, run["id"]), graph)
    domain = ManagedAdmission(cast(AsyncEngine, conn))

    async def load(*args: object) -> Data:
        return manifest

    async def verify(*args: object, **kwargs: object) -> None:
        return None

    def forbidden(*args: object) -> Data:
        raise AssertionError("M2 reached composition/native path")

    monkeypatch.setattr(domain, "load_manifest", load)
    monkeypatch.setattr(domain, "_verify_graph", verify)
    monkeypatch.setattr(managed_composition, "stage_payload", forbidden)
    expected = (
        "MISSION_REVISION_NEW_WORK_UNSUPPORTED" if attack == "m2" else "METHOD_CHECKER_UNAVAILABLE"
    )
    with pytest.raises(CatalogError, match=expected):
        await domain.stage_payload(
            cast(AsyncConnection, conn), conn.owner, records.reference(manifest)
        )


@pytest.mark.parametrize(
    "attack",
    [
        "summary",
        "mode",
        "old-criterion",
        "old-done",
        "snapshot",
        "predecessor",
        "bool-required",
        "too-many",
        "foreign-kind",
    ],
)
def test_additive_pair_rejects_material_changes_and_bad_types(attack: str) -> None:
    module = revisions()
    m1 = next(r for r in criteria_graph() if r["kind"] == "mission")
    m2 = additive(m1)
    body = contract.mapping(m2["payload"])
    if attack == "summary":
        body["summary"] = "A different objective."
    elif attack == "mode":
        body["assessment_mode"] = "FOCUSED_TEST"
    elif attack == "old-criterion":
        criteria = contract.sequence(body["criteria"])
        criteria[0] = {**contract.mapping(criteria[0]), "description": "Changed."}
        body["criteria"] = criteria
    elif attack == "old-done":
        body["done_when"] = contract.sequence(body["done_when"])[1:]
    elif attack == "snapshot":
        body["snapshot_ref"] = {**contract.ref(body["snapshot_ref"]), "id": str(uuid4())}
    elif attack == "predecessor":
        body["basis_refs"] = [records.reference(m2)]
    elif attack == "bool-required":
        body["done_when"] = [
            {"criterion_id": contract.mapping(c)["id"], "required": 1}
            for c in contract.sequence(body["criteria"])
        ]
    elif attack == "too-many":
        body["gaps"] = ["gap"] * 129
    else:
        m2["kind"] = "focus"
    m2["payload"] = body
    m2["digest"] = sha256(canonical({k: v for k, v in m2.items() if k != "digest"})).hexdigest()
    with pytest.raises(CatalogError):
        module.validate_pair(m1, m2)


def test_retained_builder_rejects_m2_and_old_checker_before_new_assignment() -> None:
    from omnis.modules.tasks.method_checker_identity import SEMANTICS
    from test_c03_managed_capture import capture_source

    graph = criteria_graph()
    m1 = next(r for r in graph if r["kind"] == "mission")
    source = capture_source()
    with pytest.raises(CatalogError, match="MISSION_REVISION_NEW_WORK_UNSUPPORTED"):
        source.build(prefix=[*graph, additive(m1)], method_execution=True)
    old = deepcopy(graph)
    checker = next(r for r in old if r["kind"] == "method-checker")
    checker["payload"] = {
        "key": "managed.contract-pure.v2",
        "semantics": SEMANTICS,
        "code_digest": "833b5690ada0c2669114dc7fc3755300d96116b773f9eb0c412fba024fac8fd9",
    }
    checker["digest"] = sha256(
        canonical({k: v for k, v in checker.items() if k != "digest"})
    ).hexdigest()
    with pytest.raises(CatalogError, match="METHOD_CHECKER_UNAVAILABLE"):
        source.build(prefix=old, method_execution=True)


@pytest.mark.parametrize("state", ["COMPLETE", "INCOMPLETE", "UNKNOWN"])
def test_old_outcome_algorithm_reconstructs_byte_exact_m1_after_m2(state: str) -> None:
    """Synthetic schema-valid result/check, only a finite rule semantic proof."""
    from omnis.modules.tasks import criterion_checks

    root = Path(__file__).resolve().parents[2]
    raw = subprocess.check_output(
        [
            "git",
            "show",
            "c29d397365dc67b89c8fb79bccfafccffa303a51:api/src/omnis/modules/tasks/criterion_checks.py",
        ],
        cwd=root,
    )
    assert (
        sha256(raw).hexdigest()
        == "9de1b7a9741df5ce97b44079ac0c1843583a8e1fd1c76b6096e37dc2e2870efb"
    )
    namespace: dict[str, object] = {"__file__": criterion_checks.__file__}
    exec(compile(raw, "retained-criterion-rule", "exec"), namespace)
    old = cast(OutcomeFunction, namespace["outcome_payloads"])
    graph = criteria_graph([str(uuid4())])
    brief = next(r for r in graph if r["kind"] == "task-brief")
    m1 = next(r for r in graph if r["kind"] == "mission")
    body = contract.mapping(brief["payload"])
    result_body = contract.mapping(contract.blocked_result(brief)["payload"])
    result_body["criterion_results"] = [
        {
            "criterion_id": b["criterion_id"],
            "bound_procedure_ref": b["bound_procedure_ref"],
            "control_step_ids": [],
            "evidence_refs": [],
            "proposed_outcome": "BLOCKED",
            "gaps": [],
        }
        for b in (contract.mapping(r) for r in contract.sequence(body["criterion_bindings"]))
    ]
    result = records.envelope("task-result", result_body)
    check = records.envelope(
        "method-check",
        {
            "brief_ref": records.reference(brief),
            "task_result_ref": records.reference(result),
            "status": state,
        },
    )
    expected = old(brief, result, check, graph, receive_only=True)
    revised = [*graph, additive(m1)]
    with pytest.raises(CatalogError, match="CRITERION_ALLOCATION_MISMATCH"):
        old(brief, result, check, revised, receive_only=True)
    assert canonical(
        criterion_checks.outcome_payloads(brief, result, check, revised, receive_only=True)
    ) == canonical(expected)
    assert canonical(
        criterion_checks.outcome_payloads(
            brief, result, check, [revised[-1], *graph], receive_only=True
        )
    ) == canonical(expected)
    for bad in ([*revised, revised[-1]], [*revised, graph[0]]):
        with pytest.raises(CatalogError):
            criterion_checks.outcome_payloads(brief, result, check, bad, receive_only=True)
