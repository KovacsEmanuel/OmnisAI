"""SOURCE CLI/storage doubles; real graph/receipt producers, not native/PG authority."""

import asyncio
import importlib
import json
import os
import sys
from collections.abc import Callable
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace, TracebackType
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.coverage import denominator
from omnis.modules.runs import contract_inputs
from omnis.modules.runs.managed_admission import BuildSource, ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import Manifest, Procedure
from omnis.modules.settings.catalog_schema import canonical, dto, load_json
from omnis.modules.tasks import managed_composition
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.contract_case_input import material_section
from test_contract_denominator import DenominatorSQLDouble
from test_mission_revisions import Result

Data = dict[str, object]
ROOT = Path(__file__).resolve().parents[2]


class QualificationSQLDouble(DenominatorSQLDouble):
    """SOURCE rollback semantics; no claim about PG locking/constraints."""

    async def __aenter__(self) -> "QualificationSQLDouble":
        self.before = deepcopy(self.graph)
        self.before_writes = list(self.writes)
        return self

    async def __aexit__(
        self,
        typ: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if error is not None:
            self.graph = self.before
            self.writes = self.before_writes
        return False

    async def execute(self, statement: object, args: Data | None = None) -> Result:
        query = str(statement)
        if "catalog_reservation" in query and "SELECT i.entity_kind" in query:
            assert args is not None and args["owner"] == self.owner
            return Result([args["kind"]])
        return await super().execute(statement, args)


def source_fixture(monkeypatch: pytest.MonkeyPatch) -> tuple[QualificationSQLDouble, Data]:
    """No Host/process/DB. Real assignment, run_contract and checker on synthetic state."""
    from fixtures.c03_records import PATHS
    from fixtures.c03_records import ROOT as SEED_ROOT
    from omnis.modules.tasks import mission_revisions

    template = SEED_ROOT / "skills/records-mapping-contract"
    procedure = dto((template / "templates/procedures/map-records.yaml").read_bytes(), Procedure)
    from tempfile import TemporaryDirectory

    from fixtures.c03_records import records_seed
    from omnis.modules.runs.native_preparation_models import prepare_packages
    from omnis.modules.settings.candidate_material import capture
    from omnis.modules.settings.skill_catalog import compile_catalog
    from test_managed_contract import ref

    with TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
        seed = records_seed(Path(directory) / "seed")
        compiled = compile_catalog((seed.package,), seed.profile)
        retained, sources, _ = capture([str(seed.package)], str(seed.profile))
        pairs = [
            ({**ref("package"), "digest": s["package_digest"]}, s)
            for s in sources
            if s["source_kind"] == "package"
        ]
        packages = prepare_packages(retained, pairs)
    bindings: list[Data] = [
        {
            "package_key": r.package_key,
            "entity_kind": r.entity_kind,
            "key": r.key,
            "ref": {**ref(r.entity_kind), "digest": pairs[0][0]["digest"]},
        }
        for r in compiled.refs
    ]
    selection = records.envelope(
        "execution-selection",
        {"snapshot_ref": ref("run-snapshot"), "selected_package_refs": [p[0] for p in pairs]},
    )
    files = {p: (template / p).read_bytes() for p in PATHS}
    source = BuildSource(
        selection,
        ref("native-preparation-receipt"),
        contract.ref(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        "records-mapping-contract",
        "RECON",
        procedure.limits,
        packages,
        files,
        dto(files["omnis.yaml"], Manifest),
    )
    prefix = source.build(context_only=True, method_execution=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = contract.mapping(run["payload"])
    schema_ref, raw, schema_path = source.input_schema()
    owner = str(uuid4())
    context = records.envelope(
        "contract-input-context",
        {
            "version": 2,
            "namespace": "RUN",
            "owner_id": owner,
            "basis_ref": records.reference(run),
            "procedure_ref": source.procedure_ref,
            "schema_ref": schema_ref,
            **{k: body[k] for k in ("snapshot_ref", "selection_ref", "mission_ref", "focus_ref")},
        },
    )
    from omnis.modules.tasks.contract_case_input import produce_input

    original = produce_input(
        context,
        {"records": [{"method": "GET", "path": "/synthetic", "status": 200}]},
        raw,
        str(uuid4()),
    )
    ctx = contract.mapping(context["payload"])
    prefix.extend([context, original])
    m1 = next(r for r in prefix if r["kind"] == "mission")
    m2 = mission_revisions.append(m1, str(uuid4()))
    conn = QualificationSQLDouble(owner, contract.text(run["id"]), prefix)
    denom_request = {
        "schema_version": 1,
        "owner_id": owner,
        "command_id": str(uuid4()),
        "context_ref": records.reference(context),
        "mission_ref": records.reference(m2),
        "input_ref": records.reference(original),
    }
    section = material_section(context, original, ctx["schema_ref"], raw, schema_path=schema_path)
    graph = source.build(prefix=prefix, case_input=section, method_execution=True)
    manifest = next(r for r in graph if r["kind"] == "launch-manifest")
    brief = next(r for r in graph if r["kind"] == "task-brief")
    entry = contract.mapping(contract.sequence(contract.mapping(manifest["payload"])["entries"])[0])
    entry = {k: v for k, v in entry.items() if k != "goal"}
    root_id, child_id, root_session, session = (str(uuid4()) for _ in range(4))
    entry.update(native_child_id=child_id, native_session_id=session)
    binding = records.envelope(
        "runtime-binding",
        {
            "runtime_boot": str(uuid4()),
            "run_id": conn.run,
            "ticket": str(uuid4()),
            "native_root_id": root_id,
            "entries": [entry],
            "authority": {
                "instance_id": str(uuid4()),
                "owner": conn.owner,
                "epoch": 1,
                "generation": 0,
            },
        },
    )
    sys.path[:0] = [
        str(ROOT / "integrations/hermes/src"),
        str(ROOT / "integrations/hermes/upstream/managed-source"),
    ]
    cold = importlib.import_module("agent.cold_admission")
    native = importlib.import_module("agent.contract_execution")
    ColdState = cast(Callable[[str, str, None], object], cold.ColdState)
    ContractState = cast(
        Callable[[str, str, str, object, bytes, bytes, object], object], native.ContractState
    )
    run_contract = cast(Callable[[object, bytes, Callable[[], bool]], Data], native.run_contract)

    root = SimpleNamespace(
        session_id=root_session,
        _subagent_id=root_id,
        _cold_state=ColdState(root_session, root_id, None),
    )
    state = ContractState(
        session,
        child_id,
        root_session,
        root,
        canonical(managed_composition.stage_payload(manifest, graph)),
        canonical(manifest),
        contract.mapping(brief["payload"])["deadline"],
    )
    child = SimpleNamespace(
        _contract_state=state,
        session_id=session,
        _subagent_id=child_id,
        _parent_session_id=root_session,
    )
    execution = contract.mapping(run_contract(child, canonical(binding), lambda: True))
    del sys.path[:2]
    final = records.envelope(
        "native-task-receipt",
        {
            "protocol": "omnis-managed-admission-v4",
            "status": "SUCCEEDED",
            "reason": "CONTRACT_PURE",
            "ticket": contract.mapping(binding["payload"])["ticket"],
            "manifest_ref": records.reference(manifest),
            "binding_ref": records.reference(binding),
            "native_root_id": root_id,
            "entries": [entry],
            "executions": [execution],
        },
    )
    graph.extend(
        [binding, final, *[contract.record(r) for r in contract.sequence(execution["records"])], m2]
    )
    conn = QualificationSQLDouble(conn.owner, conn.run, graph)
    engine = cast(AsyncEngine, conn)

    async def material(*args: object) -> tuple[bytes, list[Data], str]:
        return raw, [], "templates/schemas/records.schema.json"

    async def schemas(*args: object) -> dict[str, Data]:
        return {
            canonical(contract.ref(b["ref"])).decode(): contract.mapping(load_json(files[f.path]))
            for b in bindings
            if b["entity_kind"] == "schema"
            for f in source.manifest.file_bindings
            if f.entity_kind == "schema" and f.key == b["key"]
        }

    async def catalog_get(*args: object) -> tuple[str, Data]:
        return "source-only-external-catalog", records.envelope("source-external", {})

    async def compositions(*args: object) -> None:
        # Retained publication/transport material is doubled, not recompiled on read.
        return None

    monkeypatch.setattr(denominator, "retained_material", material)
    monkeypatch.setattr(ManagedAdmission, "_method_schemas", schemas)
    monkeypatch.setattr(ManagedAdmission, "_verify_compositions", compositions)
    monkeypatch.setattr(records, "get", catalog_get)
    monkeypatch.setattr(contract_inputs, "database_engine", lambda url: engine)
    monkeypatch.setenv("OMNIS_DATABASE_URL", "source-double-not-a-dsn")
    domain = ManagedAdmission(engine)
    result = contract.record(contract.sequence(execution["records"])[0], "task-result")
    checker_ref = contract.mapping(next(r for r in graph if r["kind"] == "managed-run")["payload"])[
        "method_check_ref"
    ]
    checked = asyncio.run(
        domain._result_check(
            cast(AsyncConnection, conn),
            conn.owner,
            conn.run,
            brief,
            result,
            contract.ref(checker_ref),
            graph=graph,
        )
    )
    assert contract.mapping(checked["payload"])["status"] == "COMPLETE"
    conn.graph.append(checked)
    # Projection of prepare/commit_binding/ingest_result/check_result SQL rows.
    # UUID columns use the actual driver's UUID type; native identifiers are text.
    from uuid import UUID

    bound = contract.mapping(contract.validate_binding(binding, manifest)["payload"])
    conn.state = {
        "owner_id": UUID(conn.owner),
        "run_id": UUID(conn.run),
        "release_started": True,
        "manifest_id": UUID(contract.text(manifest["id"])),
        "binding_id": UUID(contract.text(binding["id"])),
        "final_id": UUID(contract.text(final["id"])),
        "runtime_boot": UUID(contract.text(bound["runtime_boot"])),
        "ticket": UUID(contract.text(bound["ticket"])),
        "native_root_id": bound["native_root_id"],
    }
    conn.tasks = [
        {
            "run_id": UUID(conn.run),
            "task_id": UUID(contract.text(entry["task_id"])),
            "attempt_id": UUID(contract.text(entry["attempt_id"])),
            "batch_index": entry["batch_index"],
            "brief_id": UUID(contract.text(brief["id"])),
            "result_id": UUID(contract.text(result["id"])),
            "check_id": UUID(contract.text(checked["id"])),
            "runtime_boot": UUID(contract.text(bound["runtime_boot"])),
            "native_child_id": entry["native_child_id"],
            "native_session_id": entry["native_session_id"],
        }
    ]
    produced = asyncio.run(contract_inputs.ContractInputs(engine).create_denominator(denom_request))
    mission_revisions.validate_graph(conn.graph)
    request: Data = {
        "schema_version": 1,
        "owner_id": conn.owner,
        "command_id": str(uuid4()),
        "context_ref": records.reference(context),
        "result_ref": records.reference(result),
        "assignment_ref": records.reference(brief),
        "mission_ref": records.reference(m2),
        "denominator_ref": produced["denominator_ref"],
    }
    return conn, request


def cli(
    operation: str,
    value: Data,
    path: Path,
    capsys: pytest.CaptureFixture[str],
    reason: str | None = None,
) -> Data:
    path.write_bytes(canonical(value))
    code = contract_inputs.main([operation, "--request", str(path)])
    output = capsys.readouterr()
    if reason is not None:
        assert (code, output.out, output.err) == (
            2,
            "",
            canonical({"status": "BLOCKED", "reason": reason}).decode() + "\n",
        )
        return {}
    assert code == 0, output.err
    assert output.err == ""
    return contract.mapping(json.loads(output.out))


def test_cli_qualification_create_read_replay_keeps_history_no_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    conn, request = source_fixture(monkeypatch)
    before = deepcopy(conn.graph)
    attempts: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        attempts.append("execution")
        raise AssertionError("QUALIFICATION_EXECUTED")

    monkeypatch.setattr(BuildSource, "build", forbidden)
    monkeypatch.setattr("omnis.modules.tasks.module_registry.run_handler", forbidden)
    monkeypatch.setattr("omnis.modules.settings.skill_catalog.evaluate_pure", forbidden)
    monkeypatch.setattr("omnis.modules.settings.skill_catalog.compile_catalog", forbidden)
    monkeypatch.setattr("omnis.modules.settings.candidate_catalog.evaluate_pure", forbidden)
    path = tmp_path / "request.json"
    created = cli("create-qualification", request, path, capsys)
    assert created["created"] is True
    read_request = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    back = cli("read-qualification", read_request, path, capsys)
    qualification = contract.record(back["qualification"], "result-qualification")
    body = contract.mapping(qualification["payload"])
    assert body["result_ref"] == request["result_ref"]
    assert body["assignment_ref"] == request["assignment_ref"]
    assert body["evaluated_against_mission_ref"] == request["mission_ref"]
    assert body["denominator_revision"] == 1
    assert contract.ref(body["evaluated_against_mission_ref"])["revision"] == 2
    assert body["precondition_state_refs"] == []
    assert body["decision"] == "REVALIDATION_REQUIRED"
    assert body["reason_codes"] == [
        "COMPATIBILITY_PROOF_UNAVAILABLE",
        "CURRENT_PRECONDITION_PROOF_UNAVAILABLE",
    ]
    manifest = contract.record(back["evidence_manifest"], "result-evidence-manifest")
    assert body["evidence_manifest_ref"] == records.reference(manifest)
    material = contract.mapping(manifest["payload"])
    assert len(contract.sequence(material["receipt_refs"])) == 3
    assert len(contract.sequence(material["artifacts"])) == 2
    assert material["result_ref"] == request["result_ref"]
    after = canonical(conn.graph)
    assert cli("create-qualification", request, path, capsys) == {**created, "created": False}
    assert canonical(conn.graph) == after
    assert [
        r
        for r in conn.graph
        if r["kind"]
        not in {"result-qualification", "result-evidence-manifest", "contract-input-command"}
    ] == [r for r in before if r["kind"] != "contract-input-command"]
    assert attempts == []


@pytest.mark.parametrize(
    "table,field,value",
    [
        ("task", "task_id", str(uuid4())),
        ("task", "attempt_id", str(uuid4())),
        ("task", "run_id", str(uuid4())),
        ("task", "batch_index", True),
        ("task", "batch_index", 0.0),
        ("task", "runtime_boot", str(uuid4())),
        ("task", "native_child_id", str(uuid4())),
        ("task", "native_session_id", str(uuid4())),
        ("task", "result_id", str(uuid4())),
        ("task", "runtime_boot", None),
        ("run", "owner_id", str(uuid4())),
        ("run", "run_id", str(uuid4())),
        ("run", "runtime_boot", str(uuid4())),
        ("run", "ticket", str(uuid4())),
        ("run", "native_root_id", str(uuid4())),
        ("run", "release_started", 1),
    ],
)
def test_qualification_durable_lineage_denies_create_read_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    table: str,
    field: str,
    value: object,
) -> None:
    conn, request = source_fixture(monkeypatch)
    path = tmp_path / "request.json"
    created = cli("create-qualification", request, path, capsys)
    read_request = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    cli("read-qualification", read_request, path, capsys)
    assert cli("create-qualification", request, path, capsys) == {**created, "created": False}
    assert conn.state is not None
    target = conn.tasks[0] if table == "task" else conn.state
    target[field] = value
    attempts: list[str] = []
    original_execute = conn.execute

    async def observed_execute(statement: object, args: Data | None = None) -> Result:
        if str(statement).startswith(("INSERT", "UPDATE", "DELETE")):
            attempts.append("write")
        return await original_execute(statement, args)

    monkeypatch.setattr(conn, "execute", observed_execute)
    before = canonical(conn.graph), list(conn.writes), deepcopy(conn.state), deepcopy(conn.tasks)
    for operation, bad in (
        ("create-qualification", {**request, "command_id": str(uuid4())}),
        ("read-qualification", read_request),
        ("create-qualification", request),
    ):
        cli(operation, bad, path, capsys, "METHOD_RECEIPT_MISMATCH")
        assert (canonical(conn.graph), conn.writes, conn.state, conn.tasks) == before
        assert attempts == []


def reseal_graph(conn: QualificationSQLDouble, kind: str, body: Data) -> None:
    """Adversarial fully resealed payload and dependent refs, not broken selfdigest."""
    replacements: dict[bytes, Data] = {}

    def replace(value: object) -> object:
        if isinstance(value, dict):
            found = replacements.get(canonical(value))
            return found if found is not None else {k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        return value

    for index, record in enumerate(conn.graph):
        if record["kind"] == kind:
            updated = {**record, "payload": body}
            updated["digest"] = sha256(
                canonical({k: v for k, v in updated.items() if k != "digest"})
            ).hexdigest()
            replacements[canonical(records.reference(record))] = records.reference(updated)
            conn.graph[index] = updated
            break
    for _ in conn.graph:
        changed = False
        for index, record in enumerate(conn.graph):
            updated_body = contract.mapping(replace(record["payload"]))
            if canonical(updated_body) != canonical(record["payload"]):
                updated = {**record, "payload": updated_body}
                updated["digest"] = sha256(
                    canonical({k: v for k, v in updated.items() if k != "digest"})
                ).hexdigest()
                replacements[canonical(records.reference(record))] = records.reference(updated)
                conn.graph[index] = updated
                changed = True
        if not changed:
            break


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("owner", "REF_UNAVAILABLE"),
        ("foreign-result", "REF_UNAVAILABLE"),
        ("digest", "REF_MISMATCH"),
        ("bool-ref", "INVALID_REQUEST"),
        ("bool-schema", "MANAGED_REJECTED"),
        ("wrong-kind", "MANAGED_REJECTED"),
        ("decision", "MANAGED_REJECTED"),
        ("manifest", "MANAGED_REJECTED"),
        ("revision", "MANAGED_REJECTED"),
        ("conflict", "COMMAND_CONFLICT"),
        ("wrong-read", "COMMAND_CONFLICT"),
    ],
)
def test_cli_qualification_request_denials_preserve_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    attack: str,
    reason: str,
) -> None:
    conn, request = source_fixture(monkeypatch)
    path = tmp_path / "request.json"
    cli("create-qualification", request, path, capsys)
    bad = deepcopy(request)
    operation = "create-qualification"
    if attack == "owner":
        bad["owner_id"] = str(uuid4())
    elif attack == "foreign-result":
        bad["result_ref"] = {**contract.ref(bad["result_ref"]), "id": str(uuid4())}
    elif attack in {"digest", "bool-ref", "wrong-kind"}:
        key, value = {
            "digest": ("digest", "0" * 64),
            "bool-ref": ("revision", True),
            "wrong-kind": ("kind", "method-check"),
        }[attack]
        bad["result_ref"] = {**contract.ref(bad["result_ref"]), key: value}
    elif attack == "bool-schema":
        bad["schema_version"] = True
    elif attack in {"decision", "manifest", "revision"}:
        key, value = {
            "decision": ("decision", "ELIGIBLE"),
            "manifest": ("evidence_manifest_ref", request["result_ref"]),
            "revision": ("denominator_revision", 1),
        }[attack]
        bad[key] = value
    elif attack == "conflict":
        bad["mission_ref"] = next(
            records.reference(r)
            for r in conn.graph
            if r["kind"] == "mission" and r["revision"] == 1
        )
    else:
        operation = "read-denominator"
        bad = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    before = (
        canonical(conn.graph),
        list(conn.writes),
        deepcopy(conn.tasks),
        deepcopy(conn.state),
        deepcopy(conn.inbox),
    )
    cli(operation, bad, path, capsys, reason)
    assert (canonical(conn.graph), conn.writes, conn.tasks, conn.state, conn.inbox) == before


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("decision", "QUALIFICATION_INVALID"),
        ("revision-bool", "MANAGED_REJECTED"),
        ("preconditions", "QUALIFICATION_INVALID"),
        ("missing-field", "MANAGED_REJECTED"),
        ("manifest-artifacts", "QUALIFICATION_INVALID"),
        ("manifest-value", "QUALIFICATION_INVALID"),
        ("manifest-receipts", "QUALIFICATION_INVALID"),
        ("provenance", "QUALIFICATION_INVALID"),
        ("receipt-digest", "COMMAND_CONFLICT"),
        ("receipt-operation", "COMMAND_CONFLICT"),
        ("receipt-owner", "COMMAND_CONFLICT"),
        ("receipt-refs", "COMMAND_CONFLICT"),
        ("manifest-schema", "QUALIFICATION_INVALID"),
        ("orphan-provenance", "QUALIFICATION_INVALID"),
        ("orphan-manifest", "QUALIFICATION_INVALID"),
        ("orphan-receipt", "COMMAND_CONFLICT"),
        ("disguised-orphan-receipt", "COMMAND_CONFLICT"),
    ],
)
def test_cli_qualification_rejects_resealed_semantic_tamper_on_read_and_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    attack: str,
    reason: str,
) -> None:
    conn, request = source_fixture(monkeypatch)
    lookups: list[str] = []
    write_attempts: list[str] = []
    original_get, original_execute = records.get, conn.execute

    async def observed_get(
        connection: AsyncConnection, owner: str, reference: Data
    ) -> tuple[str, Data]:
        lookups.append("catalog.get")
        return await original_get(connection, owner, reference)

    async def observed_execute(statement: object, args: Data | None = None) -> Result:
        if "catalog_reservation" in str(statement):
            lookups.append("catalog.identity")
        if str(statement).startswith(("INSERT", "UPDATE", "DELETE")):
            write_attempts.append("write")
        return await original_execute(statement, args)

    monkeypatch.setattr(records, "get", observed_get)
    monkeypatch.setattr(conn, "execute", observed_execute)
    path = tmp_path / "request.json"
    cli("create-qualification", request, path, capsys)
    read_request = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    cli("read-qualification", read_request, path, capsys)
    cli("create-qualification", request, path, capsys)
    assert "catalog.get" in lookups and "catalog.identity" in lookups
    assert write_attempts
    lookups.clear()
    write_attempts.clear()
    kind = "result-evidence-manifest" if attack.startswith("manifest-") else "result-qualification"
    if attack.startswith("receipt-"):
        index = next(
            i
            for i, r in enumerate(conn.graph)
            if r["kind"] == "contract-input-command"
            and contract.mapping(r["payload"])["command_id"] == request["command_id"]
        )
        item = conn.graph[index]
        body = contract.mapping(item["payload"])
        if attack == "receipt-digest":
            body["request_digest"] = "0" * 64
        elif attack == "receipt-operation":
            body["operation"] = "create-denominator"
        elif attack == "receipt-owner":
            body["owner_id"] = str(uuid4())
        else:
            body["result_refs"] = {
                **contract.mapping(body["result_refs"]),
                "context_ref": request["result_ref"],
            }
        item = {**item, "payload": body}
        item["digest"] = sha256(
            canonical({k: v for k, v in item.items() if k != "digest"})
        ).hexdigest()
        conn.graph[index] = item
    elif attack == "disguised-orphan-receipt":
        conn.graph = [
            r
            for r in conn.graph
            if r["kind"] not in {"result-qualification", "result-evidence-manifest"}
        ]
        for index, item in enumerate(conn.graph):
            if (
                item["kind"] == "contract-input-command"
                and contract.mapping(item["payload"])["command_id"] == request["command_id"]
            ):
                item = {
                    **item,
                    "payload": {
                        **contract.mapping(item["payload"]),
                        "operation": "create-denominator",
                    },
                }
                item["digest"] = sha256(
                    canonical({k: v for k, v in item.items() if k != "digest"})
                ).hexdigest()
                conn.graph[index] = item
    elif attack == "orphan-receipt":
        receipt = next(
            r
            for r in conn.graph
            if r["kind"] == "contract-input-command"
            and contract.mapping(r["payload"])["command_id"] == request["command_id"]
        )
        conn.graph.append(
            records.envelope(
                "contract-input-command",
                {**contract.mapping(receipt["payload"]), "command_id": str(uuid4())},
            )
        )
    else:
        body = contract.mapping(next(r for r in conn.graph if r["kind"] == kind)["payload"])
        if attack == "decision":
            body["decision"] = "ELIGIBLE"
        elif attack == "revision-bool":
            body["denominator_revision"] = True
        elif attack == "preconditions":
            body["precondition_state_refs"] = [request["result_ref"]]
        elif attack == "missing-field":
            del body["precondition_state_refs"]
        elif attack == "provenance":
            body["provenance"] = {
                **contract.mapping(body["provenance"]),
                "producer_revision": "external-v1",
            }
        elif attack == "orphan-provenance":
            body["provenance"] = {
                **contract.mapping(body["provenance"]),
                "command_id": str(uuid4()),
            }
        elif attack == "orphan-manifest":
            orphan = next(r for r in conn.graph if r["kind"] == "result-evidence-manifest")
            conn.graph.append(
                records.envelope("result-evidence-manifest", contract.mapping(orphan["payload"]))
            )
        elif attack == "manifest-artifacts":
            body["artifacts"] = []
        elif attack == "manifest-receipts":
            body["receipt_refs"] = []
        else:
            rows = contract.sequence(body["artifacts"])
            row = contract.mapping(rows[0])
            rows[0] = (
                {**row, "schema_ref": {**contract.ref(row["schema_ref"]), "id": str(uuid4())}}
                if attack == "manifest-schema"
                else {**row, "value_digest": "0" * 64}
            )
            body["artifacts"] = rows
        reseal_graph(conn, kind, body)
    before = canonical(conn.graph), list(conn.writes)
    # All service paths plus the common retained reader must refuse locally.
    # The observer delegates real positive lookups and records before any raise.
    for operation, value in (
        ("read-qualification", read_request),
        ("create-qualification", request),
        ("create-qualification", {**request, "command_id": str(uuid4())}),
    ):
        cli(operation, value, path, capsys, reason)
        assert lookups == []
    from omnis.modules.settings.catalog_models import CatalogError

    with pytest.raises(CatalogError, match="^" + reason + "$"):
        asyncio.run(
            ManagedAdmission(cast(AsyncEngine, conn))._verify_graph(
                cast(AsyncConnection, conn), conn.owner, conn.run, conn.graph
            )
        )
    assert lookups == [] and write_attempts == []
    assert (canonical(conn.graph), conn.writes) == before


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("owner", "REF_UNAVAILABLE"),
        ("namespace", "REF_UNAVAILABLE"),
        ("run-digest", "REF_MISMATCH"),
    ],
)
def test_qualification_foreign_owner_refuses_before_external_lookup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    attack: str,
    reason: str,
) -> None:
    conn, request = source_fixture(monkeypatch)
    path = tmp_path / "request.json"
    cli("create-qualification", request, path, capsys)
    body = contract.mapping(
        next(r for r in conn.graph if r["kind"] == "result-qualification")["payload"]
    )
    if attack == "owner":
        body["owner_id"] = str(uuid4())
    elif attack == "namespace":
        body["namespace"] = "PACKAGE_EVAL"
    else:
        body["run_ref"] = {**contract.ref(body["run_ref"]), "digest": "0" * 64}
    reseal_graph(conn, "result-qualification", body)
    lookups: list[str] = []

    async def forbidden(*args: object) -> tuple[str, Data]:
        lookups.append("external")
        raise AssertionError("FOREIGN_QUALIFICATION_LOOKUP")

    monkeypatch.setattr(records, "get", forbidden)
    cli(
        "read-qualification",
        {k: request[k] for k in ("schema_version", "owner_id", "command_id")},
        path,
        capsys,
        reason,
    )
    assert lookups == []


def test_qualification_receipt_failure_rolls_back_both_records(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.modules.tasks import managed_store

    conn, request = source_fixture(monkeypatch)
    before = canonical(conn.graph), list(conn.writes)

    async def fail_receipt(*args: object) -> None:
        raise CatalogError("TEST_RECEIPT_ROLLBACK")

    monkeypatch.setattr(managed_store, "command_complete", fail_receipt)
    cli("create-qualification", request, tmp_path / "request.json", capsys, "TEST_RECEIPT_ROLLBACK")
    assert (canonical(conn.graph), conn.writes) == before
