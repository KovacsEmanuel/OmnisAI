"""Focused pure regressions; durable PostgreSQL proof belongs to lifecycle tests."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fixtures.b06b_publication.consumer import SOURCE
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError, Procedure
from omnis.modules.settings.catalog_schema import dto
from omnis.modules.settings.skill_catalog import compile_catalog
from omnis.modules.tasks import managed_contract as contract
from test_managed_contract import ref


def build_graph() -> list[dict[str, object]]:
    procedure = dto(
        (SOURCE / "b06b-publish-contract/templates/procedures/publication-map.yaml").read_bytes(),
        Procedure,
    )
    compiled = compile_catalog((SOURCE / "b06b-publish-contract",), SOURCE / "profile.yaml")
    bindings: list[dict[str, object]] = [
        {
            "package_key": q.package_key,
            "entity_kind": q.entity_kind,
            "key": q.key,
            "ref": ref(q.entity_kind),
        }
        for q in compiled.refs
    ]
    return contract.build_records(
        records.envelope(
            "execution-selection",
            {
                "snapshot_ref": ref("run-snapshot"),
                "selected_package_refs": [ref("package")],
            },
        ),
        ref("native-preparation-receipt"),
        contract.ref(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
        procedure,
        bindings,
        "b06b-publish-contract",
        "RECON",
        2,
        datetime(2026, 10, 9, tzinfo=UTC),
    )


def test_through_cursor_resolves_to_scoped_record() -> None:
    graph = build_graph()
    cursors = [r for r in graph if r["kind"] == "managed-cursor"]
    assert len(cursors) == 1, "through_cursor must resolve to a persisted scoped record"
    run = next(r for r in graph if r["kind"] == "managed-run")
    cursor = cursors[0]
    assert graph.index(cursor) > graph.index(run)
    for brief in (r for r in graph if r["kind"] == "task-brief"):
        header = contract.mapping(contract.mapping(brief["payload"])["header"])
        assert header["through_cursor"] == cursor["id"]
        assert cursor["payload"] == {
            "run_id": run["id"],
            "mission_ref": header["mission_revision"],
            "focus_ref": header["focus_ref"],
            "sequence": 1,
        }
        contract.validate_cursor(header, cursor, run)
        for key, value in (
            ("run_id", ref("managed-run")["id"]),
            ("mission_ref", ref("mission")),
            ("focus_ref", ref("focus")),
            ("sequence", True),
            ("sequence", 2),
        ):
            bad = deepcopy(cursor)
            payload = {**contract.mapping(bad["payload"]), key: value}
            from omnis.modules.settings.candidate_material import digest
            from omnis.modules.settings.catalog_schema import canonical

            bad = {**bad, "payload": payload}
            bad["digest"] = digest(canonical({k: v for k, v in bad.items() if k != "digest"}))
            with pytest.raises(CatalogError):
                contract.validate_cursor(header, bad, run)
        with pytest.raises(CatalogError):
            contract.validate_cursor(
                {**header, "through_cursor": ref("managed-cursor")["id"]}, cursor, run
            )


@pytest.mark.parametrize("unsafe", ["hardlink", "symlink"])
def test_checker_provenance_rejects_unsafe_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe: str,
) -> None:
    original = tmp_path / "source.py"
    original.write_bytes(b"# provenance-only fixture\n")
    source = tmp_path / "alias.py"
    if unsafe == "hardlink":
        source.hardlink_to(original)
    else:
        source.symlink_to(original)
    monkeypatch.setattr(contract, "__file__", str(source))
    with pytest.raises(CatalogError, match="UNSAFE_FILE"):
        build_graph()


def test_immutable_deadline_denies_at_db_time_not_historical_validation() -> None:
    brief = next(r for r in build_graph() if r["kind"] == "task-brief")
    deadline = datetime.fromisoformat(str(contract.mapping(brief["payload"])["deadline"]))
    assert hasattr(contract, "require_unexpired"), "dispatch deadline admission is missing"
    contract.require_unexpired(brief, deadline - timedelta(microseconds=1))
    for now in (deadline, deadline + timedelta(days=1)):
        with pytest.raises(CatalogError, match="BRIEF_EXPIRED"):
            contract.require_unexpired(brief, now)
    # Replay/readback validates retained bytes, not today's dispatch authority.
    assert contract.validate_brief(brief) == brief


def test_migration_uses_normative_queued_state(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    from alembic import op

    statements: list[str] = []
    monkeypatch.setattr(op, "execute", statements.append)
    path = Path(__file__).parents[1] / "src/omnis/migrations/versions/0011_managed_tasks.py"
    spec = importlib.util.spec_from_file_location("managed_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()
    assert "state IN ('QUEUED','BOUND','BLOCKED')" in statements[0]
    assert "RESERVED" not in statements[0]


def test_receive_disposition_uses_current_control_without_granting_authority() -> None:
    from uuid import UUID

    from test_managed_contract import authority

    fence = authority()
    now = datetime(2026, 10, 9, tzinfo=UTC)
    instance = {
        "instance_id": UUID(str(fence["instance_id"])),
        "generation": 0,
        "admission_open": True,
        "shutdown_command_id": None,
    }
    lease = {
        "owner": UUID(str(fence["owner"])),
        "epoch": 1,
        "expires_at": now + timedelta(seconds=5),
    }
    assert hasattr(contract, "receive_disposition"), "receive classification must fence Stop"
    assert contract.receive_disposition(instance, lease, fence, now, held=False) == "RECEIVED"
    assert (
        contract.receive_disposition(instance, lease, fence, now, held=True)
        == "HELD_FOR_RECONCILIATION"
    )
    for changed in (
        {**instance, "admission_open": False},
        {**instance, "generation": 1},
        {**instance, "shutdown_command_id": "stopped"},
        {**instance, "instance_id": None},
    ):
        assert (
            contract.receive_disposition(changed, lease, fence, now, held=False)
            == "HELD_FOR_RECONCILIATION"
        )
    for changed in (
        {**lease, "owner": None},
        {**lease, "epoch": 2},
        {**lease, "expires_at": now},
        {**lease, "expires_at": None},
    ):
        assert (
            contract.receive_disposition(instance, changed, fence, now, held=False)
            == "HELD_FOR_RECONCILIATION"
        )
