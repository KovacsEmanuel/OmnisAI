"""C03 unit evidence on real graph/value producers; NOT PG/native lifecycle proof."""

import asyncio
import base64
from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from fixtures.b06b_publication.consumer import mapping, sequence
from omnis.modules.runs.managed_admission import BuildSource, ManagedAdmission, validate_request
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError, Manifest, Procedure
from omnis.modules.settings.catalog_schema import canonical, dto, load_json
from omnis.modules.tasks import managed_composition
from omnis.modules.tasks import managed_contract as contract
from test_managed_composition import inputs
from test_managed_contract import ref


def request() -> dict[str, object]:
    return {
        "schema_version": 2,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "selection_ref": ref("execution-selection"),
        "preparation_command_id": str(uuid4()),
        "task_count": 1,
        "context_ref": ref("contract-input-context"),
        "slot_values": [{"slot_name": "capture", "refs": [ref("contract-case-input")]}],
    }


def capture_source() -> BuildSource:
    """Unit-only catalog identities; source bytes/compiler/graph are real."""
    selection, bindings, packages, original = inputs()
    body = original.model_dump(mode="json")
    body["key"] = "map-capture"
    body["slots"] = [
        {"name": "capture", "expected_kind": "contract-case-input", "min_items": 1, "max_items": 1}
    ]
    mapping(sequence(body["probe"])[0])["input_bindings"] = [
        {
            "name": "capture",
            "source_ref": {"kind": "CASE_SLOT_REF", "name": "capture"},
            "selector": "capture",
        }
    ]
    body["method_requirements"] = [
        *sequence(body["method_requirements"]),
        {**mapping(sequence(body["method_requirements"])[0]), "key": "additional"},
    ]
    procedure = dto(canonical(body), Procedure)
    files = {
        str(mapping(f)["path"]): base64.b64decode(str(mapping(f)["content_b64"]))
        for f in sequence(packages[0]["files"])
    }
    for binding in bindings:
        if binding["entity_kind"] == "schema":
            binding["ref"] = {
                **mapping(binding["ref"]),
                "digest": mapping(packages[0]["package_ref"])["digest"],
            }
    return BuildSource(
        selection,
        ref("native-preparation-receipt"),
        mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        "b06b-publish-contract",
        "RECON",
        procedure.limits,
        packages,
        files,
        dto(files["omnis.yaml"], Manifest),
    )


def material(
    source: BuildSource, capture: str = "GET /synthetic HTTP/1.1"
) -> tuple[list[dict[str, object]], dict[str, object]]:
    from omnis.modules.tasks.contract_case_input import material_section, produce_input

    prefix = source.build(context_only=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = mapping(run["payload"])
    schema_ref, raw, path = source.input_schema()
    context = records.envelope(
        "contract-input-context",
        {
            "version": 1,
            "namespace": "RUN",
            "owner_id": str(uuid4()),
            "basis_ref": records.reference(run),
            "snapshot_ref": body["snapshot_ref"],
            "procedure_ref": source.procedure_ref,
            "schema_ref": schema_ref,
            "selection_ref": body["selection_ref"],
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
        },
    )
    item = produce_input(context, {"capture": capture}, raw, str(uuid4()))
    return [*prefix, context, item], material_section(
        context, item, schema_ref, raw, schema_path=path
    )


def capture_graph(capture: str = "GET /synthetic HTTP/1.1") -> list[dict[str, object]]:
    source = capture_source()
    prefix, section = material(source, capture)
    before = canonical(prefix)
    graph = source.build(prefix=prefix, case_input=section)
    assert canonical(graph[: len(prefix)]) == before
    return graph


def test_schema2_only_accepts_capture_refs_and_one_task() -> None:
    good = request()
    assert validate_request("prepare-composed", good) == good
    for change in [
        {"schema_version": True},
        {"schema_version": 1},
        {"task_count": 2},
        {"task_count": True},
        {"input": {"capture": "not a ref"}},
        {"slot_values": []},
        {"slot_values": sequence(good["slot_values"]) * 2},
        {"slot_values": [{"slot_name": "other", "refs": [ref("contract-case-input")]}]},
        {"slot_values": [{"slot_name": "capture", "refs": [ref("package")]}]},
        {"slot_values": [{"slot_name": "capture", "refs": []}]},
    ]:
        with pytest.raises(CatalogError):
            validate_request("prepare-composed", {**good, **mapping(change)})
    with pytest.raises(CatalogError):
        validate_request("prepare", good)


def test_context_prefix_has_no_assignment_and_real_metadata() -> None:
    prefix = capture_source().build(context_only=True)
    kinds = {str(r["kind"]) for r in prefix}
    assert {"managed-run", "mission", "focus", "managed-cursor", "prompt-bundle"} <= kinds
    assert not {"task-brief", "bound-procedure", "launch-manifest", "prompt-composition"} & kinds
    prompt = next(r for r in prefix if r["kind"] == "prompt-bundle")
    assert "brief_ref" not in mapping(prompt["payload"])
    assert mapping(next(r for r in prefix if r["kind"] == "managed-run")["payload"])[
        "prompt_bundle_ref"
    ] == records.reference(prompt)


def test_persistent_input_private_command_contract() -> None:
    from omnis.modules.runs.contract_inputs import validate_request as validate

    req = request()
    context = {
        k: v
        for k, v in req.items()
        if k in {"owner_id", "command_id", "selection_ref", "preparation_command_id"}
    }
    context["schema_version"] = 1
    assert validate("create-context", context) == context
    with pytest.raises(CatalogError):
        validate("create-context", {**context, "task_count": 1})
    inp = {
        "schema_version": 1,
        "owner_id": req["owner_id"],
        "command_id": str(uuid4()),
        "context_ref": req["context_ref"],
        "input": {"capture": "synthetic"},
    }
    assert validate("create-input", inp) == inp
    for key in ["provenance", "namespace", "schema_ref", "context"]:
        with pytest.raises(CatalogError):
            validate("create-input", {**inp, key: {}})


def test_run_input_cannot_fall_back_to_catalog_eval_record() -> None:
    owner, run = str(uuid4()), str(uuid4())
    graph = [records.envelope("unit-reference-holder", {"input_ref": ref("contract-case-input")})]
    with patch("omnis.modules.runs.managed_admission.catalog.get", new_callable=AsyncMock) as get:
        with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
            asyncio.run(
                ManagedAdmission(Mock(spec=AsyncEngine))._verify_graph(
                    Mock(spec=AsyncConnection), owner, run, graph
                )
            )
        get.assert_not_called()


def test_capture_graph_consumes_value_retains_prefix_and_all_requirements() -> None:
    graph = capture_graph()
    brief = next(r for r in graph if r["kind"] == "task-brief")
    bound = next(r for r in graph if r["kind"] == "bound-procedure")
    item = next(r for r in graph if r["kind"] == "contract-case-input")
    body = mapping(brief["payload"])
    resolved = mapping(mapping(bound["payload"])["resolved_procedure"])
    assert body["input_artifact_refs"] == [records.reference(item)]
    assert mapping(sequence(body["context"])[2])["ref"] == records.reference(item)
    assert len(sequence(mapping(body["method_plan"])["requirements"])) == 2
    assert resolved["slots"] == []
    assert mapping(sequence(mapping(sequence(resolved["probe"])[0])["input_bindings"])[0])[
        "source_ref"
    ] == records.reference(item)
    payload = managed_composition.stage_payload(graph[-1], graph)
    composition = mapping(sequence(payload["compositions"])[0])
    sections = sequence(load_json(str(mapping(composition["payload"])["text"])))
    assert mapping(sections[4])["input"] == item
    assert mapping(mapping(item["payload"])["value"])["capture"] == "GET /synthetic HTTP/1.1"
    assert mapping(graph[-1]["payload"])["composition_version"] == 2
    assert mapping(contract.blocked_result(brief)["payload"])["consumed_input_refs"] == []


def test_independent_capture_bundles_preserve_base_role_text_and_old_bytes() -> None:
    first = capture_graph("one\nUnicode λ")
    before = canonical(first)
    second = capture_graph("two\tUnicode ă")

    def sections(graph: list[dict[str, object]]) -> list[object]:
        return sequence(
            load_json(
                str(
                    mapping(next(r for r in graph if r["kind"] == "prompt-composition")["payload"])[
                        "text"
                    ]
                )
            )
        )

    left, right = sections(first), sections(second)
    for i in (0, 1):
        assert (
            mapping(mapping(left[i])["record"])["payload"]
            == mapping(mapping(right[i])["record"])["payload"]
        )
    assert (
        mapping(mapping(left[4])["input"])["payload"]
        != mapping(mapping(right[4])["input"])["payload"]
    )
    assert canonical(first) == before


@pytest.mark.parametrize("kind", ["contract-input-context", "contract-case-input"])
def test_graph_rejects_local_eval_namespace_and_foreign_owner(kind: str) -> None:
    owner, run = str(uuid4()), str(uuid4())
    item = records.envelope(
        kind, {"version": 1, "namespace": "PACKAGE_EVAL", "owner_id": str(uuid4())}
    )
    with pytest.raises(CatalogError):
        asyncio.run(
            ManagedAdmission(Mock(spec=AsyncEngine))._verify_graph(
                Mock(spec=AsyncConnection), owner, run, [item]
            )
        )


@pytest.mark.parametrize("mutation", ["key", "forward", "foreign", "selector", "extra-slot"])
def test_capture_producer_rejects_native_incompatible_bindings(mutation: str) -> None:
    from dataclasses import replace

    source = capture_source()
    prefix, section = material(source)
    body = deepcopy(source.procedure.model_dump(mode="json"))
    step = mapping(sequence(body["probe"])[1])
    binding = mapping(sequence(step["input_bindings"])[0])
    if mutation == "key":
        body["key"] = "different"
    elif mutation == "forward":
        mapping(binding["source_ref"])["step_id"] = mapping(sequence(body["probe"])[2])["id"]
    elif mutation == "foreign":
        mapping(binding["source_ref"])["step_id"] = "other-attempt"
    elif mutation == "selector":
        binding["selector"] = "capture"
    else:
        body["slots"] = sequence(body["slots"]) * 2
    with pytest.raises(CatalogError):
        replace(source, procedure=dto(canonical(body), Procedure)).build(
            prefix=prefix, case_input=section
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "input-missing",
        "context-missing",
        "schema-path",
        "schema-bytes",
        "namespace",
        "owner",
        "schema-bool",
        "input-bool",
    ],
)
def test_capture_composition_rejects_material_tampering(mutation: str) -> None:
    graph = capture_graph()
    manifest = graph[-1]
    if mutation in {"input-missing", "context-missing"}:
        kind = "contract-case-input" if mutation == "input-missing" else "contract-input-context"
        with pytest.raises(CatalogError):
            managed_composition.stage_payload(manifest, [r for r in graph if r["kind"] != kind])
        return
    composed = next(r for r in graph if r["kind"] == "prompt-composition")
    body = deepcopy(mapping(composed["payload"]))
    sections = sequence(load_json(str(body["text"])))
    section = mapping(sections[4])
    if mutation == "schema-path":
        mapping(section["schema"])["path"] = "templates/empty.schema.json"
    elif mutation == "schema-bytes":
        mapping(section["schema"])["source_b64"] = base64.b64encode(b"{}").decode()
    elif mutation == "schema-bool":
        mapping(mapping(section["schema"])["ref"])["revision"] = True
    elif mutation == "input-bool":
        mapping(section["input"])["revision"] = True
    else:
        context_body = mapping(mapping(section["context"])["payload"])
        context_body["namespace" if mutation == "namespace" else "owner_id"] = (
            "PACKAGE_EVAL" if mutation == "namespace" else str(uuid4())
        )
        section["context"] = records.envelope("contract-input-context", context_body)
    from hashlib import sha256

    raw = canonical(sections)
    body.update(
        text=raw.decode(),
        text_digest=sha256(raw).hexdigest(),
        byte_count=len(raw),
        token_upper_bound=len(raw),
    )
    with pytest.raises(CatalogError):
        managed_composition.validate(records.envelope("prompt-composition", body))


@pytest.mark.parametrize(
    "bad", ["\ufeffcapture", "bad\rtext", "bad\x80text", "λ" * 2049, "x" * 4097]
)
def test_capture_input_byte_and_control_denials(bad: str) -> None:
    with pytest.raises(CatalogError):
        capture_graph(bad)


def test_legacy_assignment_rejects_new_input_kind_without_slot_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_managed_composition import graph as legacy_graph

    graph = legacy_graph(monkeypatch)
    brief = next(r for r in graph if r["kind"] == "task-brief")
    bound = next(r for r in graph if r["kind"] == "bound-procedure")
    body = deepcopy(mapping(bound["payload"]))
    procedure = mapping(body["resolved_procedure"])
    first = mapping(sequence(procedure["probe"])[0])
    first["input_bindings"] = [
        {"name": "capture", "source_ref": ref("contract-case-input"), "selector": "capture"}
    ]
    changed = records.envelope("bound-procedure", body)
    brief_body = deepcopy(mapping(brief["payload"]))
    new_ref = records.reference(changed)
    mapping(sequence(brief_body["procedure_bindings"])[0])["bound_procedure_ref"] = new_ref
    for requirement in sequence(mapping(brief_body["method_plan"])["requirements"]):
        mapping(mapping(requirement)["ref"])["bound_procedure_ref"] = new_ref
    with pytest.raises(CatalogError):
        contract.validate_assignment(records.envelope("task-brief", brief_body), changed)


def test_composition_one_historical_revision_is_not_reinterpreted_as_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    selection, bindings, packages, procedure = inputs()
    monkeypatch.setattr(
        managed_composition, "COMPOSER_REVISION", managed_composition.LEGACY_COMPOSER_REVISION
    )
    graph = contract.build_records(
        selection,
        ref("native-preparation-receipt"),
        mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        "b06b-publish-contract",
        "RECON",
        1,
        datetime.now(UTC),
        composition_packages=packages,
    )
    before = canonical(graph)
    monkeypatch.setattr(
        managed_composition,
        "COMPOSER_REVISION",
        "c2c9e4688e150308bd0c65b2df5b5a8ba39c532cde7ba7de807aa02201cc2079",
    )
    payload = managed_composition.stage_payload(graph[-1], graph)
    assert mapping(graph[-1]["payload"])["composition_version"] == 1
    assert mapping(
        mapping(mapping(sequence(payload["compositions"])[0])["payload"])["prompt_bundle"]
    )["payload"]
    assert canonical(graph) == before


def test_private_input_producer_uses_real_records_and_command_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQL result doubles only. NOT a durability/transaction/qualification oracle."""
    from omnis.modules.runs.contract_inputs import ContractInputs

    source = capture_source()
    owner, command = str(uuid4()), str(uuid4())
    engine = Mock(spec=AsyncEngine)
    connection = AsyncMock(spec=AsyncConnection)
    transaction = AsyncMock()
    transaction.__aenter__.return_value = connection
    engine.begin.return_value = transaction
    empty = Mock()
    empty.scalars.return_value.all.return_value = []
    empty.scalar_one_or_none.return_value = "schema"
    connection.execute.return_value = empty
    monkeypatch.setattr(ManagedAdmission, "_source", AsyncMock(return_value=source))
    # All external refs here are unit-only identities from capture_source, not catalog proof.
    monkeypatch.setattr("omnis.modules.runs.managed_admission.catalog.get", AsyncMock())
    result = asyncio.run(
        ContractInputs(engine).create_context(
            {
                "schema_version": 1,
                "owner_id": owner,
                "command_id": command,
                "selection_ref": records.reference(source.selection),
                "preparation_command_id": str(uuid4()),
            }
        )
    )
    assert result["created"] is True
    inserts = [
        call for call in connection.execute.call_args_list if str(call.args[0]).startswith("INSERT")
    ]
    assert inserts and all("INSERT INTO managed_record" in str(call.args[0]) for call in inserts)
    retained = [mapping(load_json(call.args[1]["body"])) for call in inserts]
    assert {str(r["kind"]) for r in retained} >= {
        "managed-run",
        "contract-input-context",
        "contract-input-command",
        "mission",
        "focus",
        "prompt-bundle",
        "managed-cursor",
    }
    assert not {"launch-manifest", "task-brief", "bound-procedure"} & {
        str(r["kind"]) for r in retained
    }
    context = next(r for r in retained if r["kind"] == "contract-input-context")
    assert result["context_ref"] == records.reference(context)
    assert mapping(context["payload"])["owner_id"] == owner
