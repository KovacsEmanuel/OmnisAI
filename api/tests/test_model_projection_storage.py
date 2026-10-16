"""Storage error regression on the real projection service with driver failure double."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs.managed_admission import BuildSource, ManagedAdmission
from omnis.modules.runs.model_projection import ModelProjections
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition, managed_store
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.contract_case_input import material_section, produce_input
from omnis.modules.tasks.managed_contract import sequence
from test_managed_contract import authority, stage
from test_model_projection import source_graph
from test_model_projection_denials import MARKER, approval_for, mapping


def test_storage_failure_does_not_expose_driver_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    owner, graph, launch, composition = source_graph(tmp_path)
    approval = approval_for(owner, launch, composition)
    binding = next(r for r in graph if r["kind"] == "runtime-binding")
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    monkeypatch.setattr(managed_store, "state", AsyncMock(side_effect=SQLAlchemyError(MARKER)))
    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED") as error:
        asyncio.run(
            ModelProjections(managed).prepare(
                AsyncMock(spec=AsyncConnection),
                owner,
                records.reference(launch),
                records.reference(binding),
                records.reference(composition),
                approval,
            )
        )
    assert MARKER not in str(error.value) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    [
        "owner",
        "run",
        "binding-digest",
        "composition-digest",
        "composition-revision-bool",
        "entry-goal",
        "duplicate-composition",
        "poisoned-composition",
        "selection",
        "qualification",
        "unclassified",
        "known-secret",
        "stored-projection",
    ],
)
async def test_service_revalidates_after_success_without_losing_denials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    """Real producer/stage/DATA; SQL and catalog qualification are doubles, not PG."""
    owner, graph, launch, composition = source_graph(tmp_path)
    approval = approval_for(owner, launch, composition)
    binding = next(r for r in graph if r["kind"] == "runtime-binding")
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    connection = AsyncMock(spec=AsyncConnection)
    verify_graph = AsyncMock()
    stage = Mock(wraps=managed_composition.stage_payload)
    monkeypatch.setattr(managed, "_verify_graph", verify_graph)
    monkeypatch.setattr(managed_composition, "stage_payload", stage)
    monkeypatch.setattr(
        managed_store,
        "state",
        AsyncMock(return_value={"run_id": approval.run_id, "binding_id": binding["id"]}),
    )
    monkeypatch.setattr(managed_store, "graph", AsyncMock(side_effect=lambda *_: list(graph)))

    async def get(_: object, o: str, r: str, pin: object) -> dict[str, object]:
        if (o, r) != (owner, approval.run_id):
            raise CatalogError("REF_UNAVAILABLE")
        matches = [v for v in graph if records.reference(v) == pin]
        if len(matches) != 1:
            raise CatalogError("REF_MISMATCH")
        return matches[0]

    monkeypatch.setattr(managed_store, "get", get)
    service = ModelProjections(managed)
    projected = await service.prepare(
        connection,
        owner,
        records.reference(launch),
        records.reference(binding),
        records.reference(composition),
        approval,
    )
    assert canonical(mapping(projected["payload"])["model_input"]) == canonical(
        managed_composition.project_model_input(composition, approval)
    )
    graph.append(projected)
    original_graph = deepcopy(graph)
    denied_approval = approval
    binding_pin, composition_pin = records.reference(binding), records.reference(composition)
    changed: dict[str, object] | None = None
    if attack in {"owner", "run"}:
        denied_approval = replace(
            approval,
            owner_id=str(uuid4()) if attack == "owner" else approval.owner_id,
            run_id=str(uuid4()) if attack == "run" else approval.run_id,
        )
    elif attack == "binding-digest":
        binding_pin["digest"] = "0" * 64
    elif attack == "composition-digest":
        composition_pin["digest"] = "0" * 64
    elif attack == "composition-revision-bool":
        composition_pin["revision"] = True
    elif attack == "entry-goal":
        entries = mapping(launch["payload"])["entries"]
        assert isinstance(entries, list)
        mapping(entries[0])["goal"] = "different valid goal"
        changed = launch
    elif attack == "duplicate-composition":
        graph.append(deepcopy(composition))
    elif attack == "poisoned-composition":
        mapping(composition["payload"])["byte_count"] = 1
        changed = composition
    elif attack == "selection":
        changed = next(r for r in graph if r["kind"] == "managed-run")
        mapping(mapping(changed["payload"])["selection_ref"])["digest"] = "0" * 64
    elif attack == "qualification":
        verify_graph.side_effect = CatalogError("REF_UNAVAILABLE")
    elif attack == "unclassified":
        denied_approval = replace(approval, approved_text_digests=frozenset())
    elif attack == "known-secret":
        brief = next(r for r in graph if r["kind"] == "task-brief")
        secret = str(mapping(brief["payload"])["objective_summary"])
        assert secret
        denied_approval = replace(approval, known_secrets=(secret,))
    elif attack == "stored-projection":
        mapping(projected["payload"])["projection_digest"] = "0" * 64
        changed = projected
    if changed is not None:
        changed["digest"] = sha256(
            canonical({k: v for k, v in changed.items() if k != "digest"})
        ).hexdigest()
        records.checked(changed)  # The attack is resealed, not a stale outer digest.
    if attack == "poisoned-composition":
        # Untrusted public callers still require full composer validation.
        with pytest.raises(CatalogError, match="^MODEL_PROJECTION_REJECTED$"):
            managed_composition.project_model_input(
                composition,
                replace(approval, composition_ref=canonical(records.reference(composition))),
            )
    connection.execute.reset_mock()
    stage.reset_mock()
    with pytest.raises(CatalogError, match="^MODEL_PROJECTION_REJECTED$"):
        await service.prepare(
            connection,
            owner,
            records.reference(launch),
            binding_pin,
            composition_pin,
            denied_approval,
        )
    if attack in {"entry-goal", "poisoned-composition", "duplicate-composition", "selection"}:
        stage.assert_called_once()  # Reach the actual composed boundary, not an earlier double.
    if attack in {"poisoned-composition", "stored-projection"}:
        with pytest.raises(CatalogError, match="^MODEL_PROJECTION_REJECTED$"):
            await service.read(
                connection, owner, approval.run_id, records.reference(projected), approval
            )
    assert not any(str(c.args[0]).startswith("INSERT") for c in connection.execute.call_args_list)
    graph[:] = original_graph
    verify_graph.side_effect = None
    before = verify_graph.await_count
    restored = await service.read(
        connection, owner, approval.run_id, records.reference(original_graph[-1]), approval
    )
    assert canonical(restored) == canonical(original_graph[-1])
    assert verify_graph.await_count == before + 1


@pytest.mark.asyncio
@pytest.mark.parametrize("inline", [True, False], ids=["inline-v4", "compact-v4"])
async def test_service_preserves_v4_projection_ineligibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline: bool
) -> None:
    """Genuine stage-valid v4; SQL and graph qualification remain SOURCE doubles."""
    sources: list[BuildSource] = []
    owner, _, _, _ = source_graph(tmp_path, source_out=sources)
    source = sources[0]
    prefix = source.build(context_only=True, method_execution=True)
    run = next(r for r in prefix if r["kind"] == "managed-run")
    body = mapping(run["payload"])
    schema, raw, schema_path = source.input_schema()
    context = records.envelope(
        "contract-input-context",
        {
            "version": 2,
            "namespace": "RUN",
            "owner_id": owner,
            "basis_ref": records.reference(run),
            "procedure_ref": source.procedure_ref,
            "schema_ref": schema,
            **{k: body[k] for k in ("snapshot_ref", "selection_ref", "mission_ref", "focus_ref")},
        },
    )
    item = produce_input(
        context,
        {"records": [{"method": "GET", "path": "/synthetic", "status": 200}]},
        raw,
        str(uuid4()),
    )
    section = material_section(context, item, schema, raw, schema_path=schema_path)
    graph = source.build(prefix=[*prefix, context, item], case_input=section, method_execution=True)
    compact = next(r for r in graph if r["kind"] == "prompt-composition")
    pool = managed_composition.composition_pool(compact["payload"], graph)
    expanded = records.envelope(
        "prompt-composition", managed_composition.expanded_payload(compact["payload"], pool)
    )
    composition = expanded if inline else compact
    original_manifest = next(r for r in graph if r["kind"] == "launch-manifest")
    manifest_body = deepcopy(mapping(original_manifest["payload"]))
    mapping(sequence(manifest_body["entries"])[0])["composition_ref"] = records.reference(
        composition
    )
    manifest = records.envelope("launch-manifest", manifest_body)
    graph = [r for r in graph if r["kind"] not in ("prompt-composition", "launch-manifest")]
    graph.extend([composition, manifest])
    staged = stage(manifest)
    staged["protocol"] = contract.manifest_protocol(manifest)
    for entry, wanted in zip(
        sequence(staged["entries"]), sequence(manifest_body["entries"]), strict=True
    ):
        mapping(entry)["composition_ref"] = mapping(wanted)["composition_ref"]
    binding = contract.binding_record(manifest, staged, str(uuid4()), authority())
    graph.append(binding)
    approval = replace(
        approval_for(owner, manifest, expanded),
        composition_ref=canonical(records.reference(composition)),
    )
    # Reach the actual eligibility frontier, not a stale digest/invalid stage.
    assert managed_composition.stage_payload(manifest, graph)["compositions"] == [composition]
    with pytest.raises(CatalogError, match="^MODEL_PROJECTION_REJECTED$"):
        managed_composition.project_model_input(composition, approval)
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    connection = AsyncMock(spec=AsyncConnection)
    verify_graph = AsyncMock()
    stage_call = Mock(wraps=managed_composition.stage_payload)
    monkeypatch.setattr(managed, "_verify_graph", verify_graph)
    monkeypatch.setattr(managed_composition, "stage_payload", stage_call)
    monkeypatch.setattr(
        managed_store,
        "state",
        AsyncMock(return_value={"run_id": approval.run_id, "binding_id": binding["id"]}),
    )
    monkeypatch.setattr(managed_store, "graph", AsyncMock(return_value=graph))

    async def get(_: object, actual_owner: str, actual_run: str, pin: object) -> dict[str, object]:
        assert (actual_owner, actual_run) == (owner, approval.run_id)
        matches = [r for r in graph if records.reference(r) == pin]
        assert len(matches) == 1
        return matches[0]

    monkeypatch.setattr(managed_store, "get", get)
    with pytest.raises(CatalogError, match="^MODEL_PROJECTION_REJECTED$"):
        await ModelProjections(managed).prepare(
            connection,
            owner,
            records.reference(manifest),
            records.reference(binding),
            records.reference(composition),
            approval,
        )
    stage_call.assert_called_once_with(manifest, graph)
    verify_graph.assert_awaited_once()
    assert not any(str(c.args[0]).startswith("INSERT") for c in connection.execute.call_args_list)
