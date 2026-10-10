"""Real source/compiler/composition; unit Ref identities, NOT installed/PG QA."""

import base64
import importlib
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from fixtures.c03_records import records_seed
from omnis.modules.runs.managed_admission import BuildSource
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_material import capture
from omnis.modules.settings.catalog_models import Manifest, Procedure
from omnis.modules.settings.catalog_schema import canonical, dto, load_json
from omnis.modules.settings.skill_catalog import compile_catalog
from omnis.modules.tasks import managed_composition
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.contract_case_input import material_section, produce_input
from omnis.modules.tasks.managed_contract import mapping, sequence
from test_managed_contract import authority, ref, stage


def source_graph(
    tmp_path: Path, path: str = "/synthetic/orders/123?private=value"
) -> tuple[str, list[dict[str, object]], dict[str, object], dict[str, object]]:
    seed = records_seed(tmp_path / uuid4().hex)
    compiled = compile_catalog((seed.package,), seed.profile)
    material, sources, _ = capture([str(seed.package)], str(seed.profile))
    from omnis.modules.runs.native_preparation_models import prepare_packages

    package_ref = {**ref("package"), "digest": sources[0]["package_digest"]}
    pairs = [(package_ref, s) for s in sources if s["source_kind"] == "package"]
    packages = prepare_packages(material, pairs)
    bindings: list[dict[str, object]] = [
        {
            "package_key": r.package_key,
            "entity_kind": r.entity_kind,
            "key": r.key,
            "ref": {**ref(r.entity_kind), "digest": package_ref["digest"]},
        }
        for r in compiled.refs
    ]
    selection = records.envelope(
        "execution-selection",
        {
            "snapshot_ref": ref("run-snapshot"),
            "selected_package_refs": [package_ref],
        },
    )
    files = {
        str(mapping(f)["path"]): base64.b64decode(str(mapping(f)["content_b64"]))
        for f in sequence(packages[0]["files"])
    }
    manifest = dto(files["omnis.yaml"], Manifest)
    procedure = dto(files[manifest.procedures[0]], Procedure)
    source = BuildSource(
        selection,
        ref("native-preparation-receipt"),
        mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        manifest.package_key,
        "RECON",
        procedure.limits,
        packages,
        files,
        manifest,
    )
    prefix = source.build(context_only=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = mapping(run["payload"])
    owner = str(uuid4())
    schema_ref, raw, schema_path = source.input_schema()
    context = records.envelope(
        "contract-input-context",
        {
            "version": 2,
            "namespace": "RUN",
            "owner_id": owner,
            "basis_ref": records.reference(run),
            "snapshot_ref": body["snapshot_ref"],
            "procedure_ref": source.procedure_ref,
            "schema_ref": schema_ref,
            "selection_ref": body["selection_ref"],
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
        },
    )
    item = produce_input(
        context, {"records": [{"method": "GET", "path": path, "status": 200}]}, raw, str(uuid4())
    )
    section = material_section(context, item, schema_ref, raw, schema_path=schema_path)
    graph = source.build(prefix=[*prefix, context, item], case_input=section)
    launch = graph[-1]
    staged = stage(launch)
    staged["protocol"] = contract.manifest_protocol(launch)
    for entry, wanted in zip(
        sequence(staged["entries"]), sequence(mapping(launch["payload"])["entries"]), strict=True
    ):
        mapping(entry)["composition_ref"] = mapping(wanted)["composition_ref"]
    binding = contract.binding_record(launch, staged, str(uuid4()), authority())
    graph.append(binding)
    composition = next(r for r in graph if r["kind"] == "prompt-composition")
    return owner, graph, launch, composition


def text_digests(value: object) -> frozenset[str]:
    """Test-operator classification of THIS synthetic seed, never production autoapproval."""
    found: set[str] = set()

    def visit(v: object) -> None:
        if isinstance(v, str):
            found.add(sha256(v.encode()).hexdigest())
        elif isinstance(v, dict):
            for child in v.values():
                visit(child)
        elif isinstance(v, list):
            for child in v:
                visit(child)

    visit(load_json(str(mapping(mapping(value)["payload"])["text"])))
    return frozenset(found)


def test_real_composition_projects_classified_synthetic_records(tmp_path: Path) -> None:
    producer = getattr(managed_composition, "project_model_input", None)
    assert callable(producer), "actual composition -> ModelProjection producer missing"
    policy = importlib.import_module("omnis.policy.model_projection")
    owner, graph, launch, composition = source_graph(tmp_path)
    before = canonical(graph)
    approval = policy.SyntheticApproval(
        owner_id=owner,
        run_id=str(mapping(launch["payload"])["run_id"]),
        composition_ref=canonical(records.reference(composition)),
        approved_text_digests=text_digests(composition),
        known_secrets=(),
    )
    projected = mapping(producer(composition, approval))
    raw = canonical(projected)
    assert b"/synthetic" not in raw and b"private=value" not in raw
    messages = sequence(projected["messages"])
    user = mapping(load_json(str(mapping(messages[1])["content"])))
    assert user["records"] == [{"index": 0, "method": "GET", "path": "/[redacted]", "status": 200}]
    assert user["input_ref"] == records.reference(
        next(r for r in graph if r["kind"] == "contract-case-records")
    )
    brief = next(r for r in graph if r["kind"] == "task-brief")
    assert user["header"] == mapping(brief["payload"])["header"]
    assert projected["tools"] == []
    assert canonical(graph) == before


def test_producer_denies_unclassified_text(tmp_path: Path) -> None:
    producer = getattr(managed_composition, "project_model_input", None)
    assert callable(producer), "actual composition -> ModelProjection producer missing"
    policy = importlib.import_module("omnis.policy.model_projection")
    owner, _, launch, composition = source_graph(tmp_path)
    approval = policy.SyntheticApproval(
        owner_id=owner,
        run_id=str(mapping(launch["payload"])["run_id"]),
        composition_ref=canonical(records.reference(composition)),
        approved_text_digests=frozenset(),
        known_secrets=(),
    )
    from omnis.modules.settings.catalog_models import CatalogError

    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED"):
        producer(composition, approval)
