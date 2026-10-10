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


def test_persistent_producer_uses_exact_managed_owner_and_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQL/engine doubles only; NOT a PostgreSQL durability or installed oracle."""
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.tasks import managed_store

    module_spec = importlib.util.find_spec("omnis.modules.runs.model_projection")
    assert module_spec is not None, "persistent projection producer/reader missing"
    module = importlib.import_module("omnis.modules.runs.model_projection")
    policy = importlib.import_module("omnis.policy.model_projection")
    owner, graph, launch, composition = source_graph(tmp_path)
    run_id = str(mapping(launch["payload"])["run_id"])
    bound = next(r for r in graph if r["kind"] == "runtime-binding")
    approval = policy.SyntheticApproval(
        owner_id=owner,
        run_id=run_id,
        composition_ref=canonical(records.reference(composition)),
        approved_text_digests=text_digests(composition),
        known_secrets=(),
    )
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    connection = AsyncMock(spec=AsyncConnection)
    verify_graph = AsyncMock()
    monkeypatch.setattr(managed, "_verify_graph", verify_graph)
    monkeypatch.setattr(
        managed_store,
        "state",
        AsyncMock(
            return_value={
                "run_id": run_id,
                "binding_id": bound["id"],
                "command_id": str(uuid4()),
            }
        ),
    )
    monkeypatch.setattr(managed_store, "graph", AsyncMock(side_effect=lambda *_: list(graph)))

    async def get(
        _: object, actual_owner: str, actual_run: str, reference: object
    ) -> dict[str, object]:
        assert actual_owner == owner and actual_run == run_id
        matches = [r for r in graph if records.reference(r) == reference]
        assert len(matches) == 1
        return matches[0]

    monkeypatch.setattr(managed_store, "get", get)

    async def exercise() -> None:
        service = module.ModelProjections(managed)
        projected = mapping(
            await service.prepare(
                connection,
                owner,
                records.reference(launch),
                records.reference(bound),
                records.reference(composition),
                approval,
            )
        )
        inserts = [
            call
            for call in connection.execute.call_args_list
            if str(call.args[0]).startswith("INSERT")
        ]
        assert len(inserts) == 1
        assert "INSERT INTO managed_record" in str(inserts[0].args[0])
        payload = mapping(inserts[0].args[1])
        assert payload["owner"] == owner and payload["run"] == run_id
        assert load_json(str(payload["body"])) == projected
        graph.append(projected)
        read = mapping(
            await service.read(connection, owner, run_id, records.reference(projected), approval)
        )
        assert read == projected
        # Actual independent adapter serialization, not a regex over a dict.
        monkeypatch.syspath_prepend(
            str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
        )
        spec = importlib.util.find_spec("omnis_hermes.model_projection")
        assert spec is not None, "independent Hermes model-input bytes gate missing"
        adapter = importlib.import_module("omnis_hermes.model_projection")
        pins = {
            "projection_ref": records.reference(read),
            "owner_id": owner,
            "run_id": run_id,
            "binding_ref": records.reference(bound),
            "policy_digest": policy.POLICY_DIGEST,
        }
        serialized = adapter.serialize_model_input(read, **pins)
        assert serialized == canonical(mapping(read["payload"])["model_input"])
        assert sha256(serialized).hexdigest() == mapping(read["payload"])["projection_digest"]
        assert adapter.validate_serialized_input(serialized, read, **pins) == serialized
        assert b"private=value" not in serialized
        sent: list[bytes] = []
        sent.append(adapter.validate_serialized_input(serialized, read, **pins))
        # Sink has no provider; this is inert carrier proof, NOT full SDK/pre-send/G02-live.
        assert sent == [serialized]
        tampered = mapping(load_json(serialized))
        tampered["extra_body"] = {"headers": "SYNTHETIC_FORBIDDEN_SENTINEL"}
        with pytest.raises(ValueError, match="Invalid model projection"):
            adapter.validate_serialized_input(canonical(tampered), read, **pins)
        assert len(sent) == 1
        again = await service.prepare(
            connection,
            owner,
            records.reference(launch),
            records.reference(bound),
            records.reference(composition),
            approval,
        )
        assert again == projected
        assert (
            len(
                [
                    c
                    for c in connection.execute.call_args_list
                    if str(c.args[0]).startswith("INSERT")
                ]
            )
            == 1
        )
        verify_graph.assert_awaited()

    asyncio.run(exercise())
