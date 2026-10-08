"""Freeze/eval request admission and real durable denial controls."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from fixtures.b06a_durable.consumer import copy_seed, envelope, freeze, readback, scratch_directory
from omnis.core.db import database_engine
from omnis.modules.settings.candidate_catalog import CandidateCatalog, validate_request
from omnis.modules.settings.catalog_models import CatalogError


@pytest.mark.parametrize("operation", ["freeze", "evaluate", "readback"])
def test_candidate_tracer_freeze_operation_admission(operation: str) -> None:
    ref = {"kind": "candidate-snapshot", "id": str(uuid4()), "revision": 1, "digest": "0" * 64}
    request: dict[str, object] = {"schema_version": 1, "owner_id": str(uuid4())}
    if operation != "readback":
        request["command_id"] = str(uuid4())
    if operation == "freeze":
        request.update(draft_ref=ref, source_draft_refs=[ref], technical_review_ref=ref)
    else:
        request["snapshot_ref"] = ref
    if operation == "evaluate":
        request.update(evaluation_kind="PURE", input={"invalid": "bounded synthetic"})
    assert validate_request(operation, request) == request


@pytest.mark.asyncio
async def test_candidate_tracer_freeze_blocked_eval_and_state(migrated_database_url: URL) -> None:
    seed = copy_seed(scratch_directory() / "dev-a-eval")
    url = migrated_database_url.render_as_string(hide_password=False)
    frozen = freeze(seed, url)
    engine = database_engine(url)
    catalog = CandidateCatalog(engine, seed.catalog_root)
    bad = seed.write_request(
        snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input={"invalid": "synthetic"}
    )
    try:
        for _ in range(2):
            with pytest.raises(CatalogError, match="SCHEMA_VALIDATION"):
                await catalog.dispatch("evaluate", bad)
        back = readback(seed, url, frozen)
        evaluations = back["evaluations"]
        assert isinstance(evaluations, list) and len(evaluations) == 1
        evaluation = evaluations[0]
        assert isinstance(evaluation, dict)
        receipt = envelope(
            evaluation, {k: evaluation[k] for k in ("kind", "id", "revision", "digest")}
        )
        assert receipt["status"] == "BLOCKED" and receipt["input_ref"]
        async with engine.connect() as connection:
            inputs = (
                (
                    await connection.execute(
                        text("SELECT envelope FROM catalog_record WHERE kind='evaluation-input'")
                    )
                )
                .scalars()
                .all()
            )
        assert len(inputs) == 1 and inputs[0]["payload"]["input"] == bad["input"]
        assert seed.invoke("evaluate", bad, url).stdout == ""
        snapshot = frozen["snapshot"]
        assert isinstance(snapshot, dict) and isinstance(snapshot["payload"], dict)
        with pytest.raises(CatalogError, match="CANDIDATE_FROZEN"):
            await catalog.dispatch(
                "reject",
                seed.write_request(
                    draft_ref=snapshot["payload"]["draft_ref"],
                    source_draft_refs=snapshot["payload"]["source_draft_refs"],
                ),
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_candidate_tracer_freeze_stale_and_finalize_windows(
    migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fixtures.b06a_durable.consumer import freeze_request, reviewed
    from omnis.modules.settings import candidate_catalog as module
    from omnis.modules.settings import candidate_material as material
    from omnis.modules.settings import candidate_store as store

    seed = copy_seed(scratch_directory() / "dev-a-fail-windows")
    url = migrated_database_url.render_as_string(hide_password=False)
    captured, review = reviewed(seed, url)
    engine = database_engine(url)
    catalog = CandidateCatalog(engine, seed.catalog_root)
    req = freeze_request(seed, captured, review)
    actual_put = store.put
    actual_finalize = material.finalize
    try:
        # Fail before and after the real filesystem commit; DB must cite neither.
        for window in ("before", "after"):

            def fail_before(
                root: Path, namespace: str, identity: str, material: dict[str, bytes]
            ) -> Path:
                raise CatalogError("INJECTED_FINALIZE")

            async def fail_after(
                connection: object, owner: str, group: str, record: dict[str, object]
            ) -> None:
                raise CatalogError("INJECTED_DB_FINALIZE")

            with monkeypatch.context() as patcher:
                if window == "before":
                    patcher.setattr(module, "finalize", fail_before)
                else:
                    patcher.setattr(store, "put", fail_after)
                with pytest.raises(CatalogError, match="INJECTED_"):
                    await catalog.dispatch("freeze", req)
            async with engine.connect() as connection:
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM catalog_record WHERE kind='candidate-snapshot'")
                    )
                    == 0
                )
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM catalog_command WHERE command_id=:command"),
                        {"command": req["command_id"]},
                    )
                    == 0
                )
        assert store.put is actual_put and material.finalize is actual_finalize
        frozen = await catalog.dispatch("freeze", req)
        assert await catalog.dispatch("freeze", req) == frozen
        # A successful retry allocates a new namespace; never adopts the orphan.
        assert len(list((seed.catalog_root / "candidates").iterdir())) == 2
        changed = seed.package / "NOTICE.md"
        changed.write_bytes(changed.read_bytes() + b"\nnew material\n")
        newer = await catalog.dispatch("capture", seed.capture_request())
        stale = seed.write_request(
            draft_ref=newer["draft_ref"],
            source_draft_refs=newer["source_draft_refs"],
            technical_review_ref=review["technical_review_ref"],
        )
        with pytest.raises(CatalogError, match="TECHNICAL_REVIEW_MISMATCH"):
            await catalog.dispatch("freeze", stale)
        assert readback(seed, url, frozen)["snapshot"] == frozen["snapshot"]
    finally:
        await engine.dispose()
