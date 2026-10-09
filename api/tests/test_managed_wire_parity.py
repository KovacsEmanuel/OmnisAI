"""Producer/native wire parity; PG uses an explicitly non-native RuntimeDouble."""

import asyncio
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text as sql
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from fixtures.b06b_publication.consumer import (
    PACKAGE,
    Seed,
    confirmed,
    mapping,
    new_seed,
    publish_request,
    qualify,
    sequence,
)
from fixtures.b06b_pure_probe.consumer import Probe
from omnis.modules.runs.native_preparation_models import prepare_packages
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_material import capture
from omnis.modules.settings.catalog_models import CatalogError, Procedure
from omnis.modules.settings.catalog_schema import canonical, dto
from omnis.modules.settings.skill_catalog import compile_catalog
from omnis.modules.tasks import managed_contract as contract
from test_managed_contract import manifest, ref

GOALS = [
    pytest.param(" Same inert support goal ", True, id="ascii-preserved"),
    pytest.param("é" * 2048, True, id="utf8-4096"),
    pytest.param("é" * 2049, False, id="utf8-4098"),
    pytest.param("é" * 2100, False, id="utf8-4200"),
    pytest.param("Same inert\nsupport goal", False, id="newline"),
]


@pytest.fixture
def native(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    # Test-only import; ordinary API startup must not import the runtime package.
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "integrations/hermes/src"))
    return importlib.import_module("omnis_hermes.managed_admission_contract")


def author_goal(seed: Seed, goal: str) -> Procedure:
    path = seed.package / "templates/procedures/publication-map.yaml"
    body = mapping(json.loads(path.read_bytes()))
    body["objective"] = goal
    # JSON is valid YAML. Quote controls/separators without expanding every
    # multibyte character and tripping the earlier native 8192-byte file cap.
    raw = canonical(body).decode("utf-8")
    for codepoint in (*range(127, 160), 0x2028, 0x2029):
        raw = raw.replace(chr(codepoint), f"\\u{codepoint:04x}")
    path.write_text(raw, encoding="utf-8")
    assert len(path.read_bytes()) <= 8192
    procedure = dto(path.read_bytes(), Procedure)
    assert procedure.objective == goal
    return procedure


def source_graph(seed: Seed, procedure: Procedure) -> list[dict[str, object]]:
    compiled = compile_catalog((seed.package,), seed.profile)
    material, sources, _ = capture([str(seed.package)], str(seed.profile))
    package_ref = {**ref("package"), "digest": sources[0]["package_digest"]}
    assert len(prepare_packages(material, [(package_ref, sources[0])])) == 1
    bindings: list[dict[str, object]] = [
        {
            "package_key": item.package_key,
            "entity_kind": item.entity_kind,
            "key": item.key,
            "ref": ref(item.entity_kind),
        }
        for item in compiled.refs
    ]
    return contract.build_records(
        records.envelope(
            "execution-selection",
            {"snapshot_ref": ref("run-snapshot"), "selected_package_refs": [package_ref]},
        ),
        ref("native-preparation-receipt"),
        mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        PACKAGE,
        "RECON",
        1,
        datetime.now(UTC),
    )


def test_source_newline_refused_before_graph_returns() -> None:
    seed = new_seed()
    procedure = author_goal(seed, "Same inert\nsupport goal")
    # Source compiler/package preparation must accept the quoted authored bytes;
    # the denial belongs only to managed goal emission, not general methodology.
    with pytest.raises(CatalogError, match="MANAGED_REJECTED"):
        source_graph(seed, procedure)


@pytest.mark.parametrize("goal,accepted", GOALS)
def test_authored_source_goal_parity(goal: str, accepted: bool, native: ModuleType) -> None:
    seed = new_seed()
    procedure = author_goal(seed, goal)
    if not accepted:
        with pytest.raises(CatalogError, match="MANAGED_REJECTED"):
            source_graph(seed, procedure)
        return
    graph = source_graph(seed, procedure)
    emitted = graph[-1]
    assert contract.validate_manifest(emitted) == emitted
    assert native.validate_stage({"protocol": contract.PROTOCOL, "manifest": emitted}) == emitted
    assert mapping(sequence(mapping(emitted["payload"])["entries"])[0])["goal"] == goal
    brief = next(r for r in graph if r["kind"] == "task-brief")
    assert mapping(brief["payload"])["objective_summary"] == goal


@pytest.mark.parametrize(
    "goal,accepted",
    [
        *GOALS,
        pytest.param("", False, id="empty"),
        pytest.param('"' * 4096, True, id="escaped-json-4096"),
        pytest.param("e\u0301", True, id="no-normalization"),
        *[
            pytest.param(f"inert{chr(c)}goal", False, id=f"control-{c:04x}")
            for c in (*range(32), *range(127, 160), 0x2028, 0x2029)
        ],
    ],
)
def test_same_resealed_manifest_api_native_parity(
    goal: str, accepted: bool, native: ModuleType
) -> None:
    body = mapping(manifest()["payload"])
    for raw in sequence(body["entries"]):
        mapping(raw)["goal"] = goal
    emitted = records.envelope("launch-manifest", body)
    wire = {"protocol": contract.PROTOCOL, "manifest": emitted}
    if accepted:
        assert contract.validate_manifest(emitted) == emitted
        assert native.validate_stage(wire) == emitted
        assert len(canonical(wire)) <= 32768
    else:
        with pytest.raises(CatalogError):
            contract.validate_manifest(emitted)
        with pytest.raises(ValueError):
            native.validate_stage(wire)


def test_full_stage_payload_overflow_refused(native: ModuleType) -> None:
    body = mapping(manifest()["payload"])
    for raw in sequence(body["entries"]):
        mapping(raw)["goal"] = "🙂" * 4096
    emitted = records.envelope("launch-manifest", body)
    wire = {"protocol": contract.PROTOCOL, "manifest": emitted}
    assert len(canonical(wire)) > 32768
    with pytest.raises(CatalogError, match="MANAGED_REJECTED"):
        contract.validate_manifest(emitted)
    with pytest.raises(ValueError):
        native.validate_stage(wire)


def test_methodological_multiline_is_not_wire_goal_grammar(native: ModuleType) -> None:
    seed = new_seed()
    procedure = author_goal(seed, "Inert goal")
    body = procedure.model_dump()
    requirements = [r.model_dump() for r in procedure.method_requirements]
    requirements[0]["description"] = "First line\nSecond line"
    body["method_requirements"] = tuple(requirements)
    procedure = Procedure.model_validate(body)
    graph = source_graph(seed, procedure)
    bound = next(r for r in graph if r["kind"] == "bound-procedure")
    resolved = mapping(mapping(bound["payload"])["resolved_procedure"])
    assert (
        mapping(sequence(resolved["method_requirements"])[0])["description"]
        == requirements[0]["description"]
    )
    assert (
        native.validate_stage({"protocol": contract.PROTOCOL, "manifest": graph[-1]}) == graph[-1]
    )


async def managed_ledger(engine: AsyncEngine) -> bytes:
    state: dict[str, object] = {}
    async with engine.connect() as connection:
        for table in ("managed_record", "managed_run", "managed_task", "managed_inbox"):
            rows = await connection.execute(
                sql(f"SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text")
            )
            state[table] = list(rows.scalars())
    return canonical(state)


@pytest.mark.parametrize("goal,accepted", GOALS)
def test_pg_qualified_goal_prepare_before_reservation(
    migrated_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
    native: ModuleType,
    goal: str,
    accepted: bool,
) -> None:
    """Real publication/selection/PG; preparation IPC is a labeled RuntimeDouble."""
    from omnis.core.db import database_engine
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.runs.native_preparation import NativePreparation
    from omnis.modules.tasks import managed_store
    from omnis.supervisor.runtime_client import RuntimeClient
    from test_b06b_pure_probe_pg import Published
    from test_native_preparation import command, worker_fixture

    dsn = migrated_database_url.render_as_string(hide_password=False)
    seed = new_seed()
    # Edit only owned copied sources BEFORE all qualification/publication.
    author_goal(seed, goal)
    q = qualify(seed, dsn)
    publication = seed.success("publish", publish_request(q, confirmed(q, dsn)), dsn)
    snapshot = seed.success(
        "snapshot", seed.write(publication_ref=publication["publication_ref"]), dsn
    )
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    p = Published(q, probe, migrated_database_url, snapshot)
    _, selected = p.selected()

    async def run() -> None:
        engine = database_engine(dsn)
        service, owner = InstanceService(engine), uuid4()

        class RuntimeDouble(RuntimeClient):
            calls = 0

            async def prepare(
                self,
                service: InstanceService,
                supervisor_owner: object,
                bundle_ref: dict[str, object],
                bundle: dict[str, object],
            ) -> dict[str, object]:
                self.calls += 1
                return {"preparation": worker_fixture(bundle)}

        try:
            epoch = await service.acquire(owner)
            status = await service.owned_status(owner, epoch)
            runtime = RuntimeDouble(seed.directory, generation=status.generation, epoch=epoch)
            runtime.boot = str(uuid4())
            prep = NativePrepareCommand.model_validate(
                {
                    **command(),
                    "owner_id": seed.owner,
                    "instance_id": str(status.instance_id),
                    "expected_epoch": epoch,
                    "expected_generation": status.generation,
                    "selection_ref": selected["selection_ref"],
                }
            )
            prepared = await NativePreparation(
                engine, seed.root, service, owner, epoch, runtime
            ).prepare(prep)
            assert prepared["preparation_status"] == "PREPARED" and runtime.calls == 1
            managed = ManagedAdmission(engine, seed.root)
            request = seed.write(
                selection_ref=selected["selection_ref"],
                preparation_command_id=prep.command_id,
                task_count=1,
            )
            before = await managed_ledger(engine)
            reserve = AsyncMock(side_effect=AssertionError("prepare must not reserve dispatch"))
            dispatch = AsyncMock(side_effect=AssertionError("prepare must not issue task_stage"))
            monkeypatch.setattr(managed, "reserve_dispatch", reserve)
            monkeypatch.setattr(runtime, "managed", dispatch)
            if accepted:
                result = await managed.prepare(request)
                emitted = result["manifest"]
                assert (
                    native.validate_stage({"protocol": contract.PROTOCOL, "manifest": emitted})
                    == emitted
                )
                assert (
                    mapping(sequence(mapping(mapping(emitted)["payload"])["entries"])[0])["goal"]
                    == goal
                )
                assert await managed_ledger(engine) != before
                read = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
                assert (await managed.readback(read))["manifest"] == emitted
                committed = await managed_ledger(engine)
                assert (await managed.prepare(request))["created"] is False
                assert await managed_ledger(engine) == committed
            else:
                put = AsyncMock(wraps=managed_store.put)
                monkeypatch.setattr(managed_store, "put", put)
                for _ in range(2):
                    with pytest.raises(CatalogError, match="MANAGED_REJECTED"):
                        await managed.prepare(request)
                    assert await managed_ledger(engine) == before
                put.assert_not_awaited()
            reserve.assert_not_awaited()
            dispatch.assert_not_awaited()
            assert runtime.calls == 1
        finally:
            await engine.dispose()

    asyncio.run(run())
