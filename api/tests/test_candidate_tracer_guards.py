"""Dev A own guard controls, real PostgreSQL and source capture only."""

import asyncio
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from omnis.core.db import database_engine, schema_reason_on
from omnis.modules.settings.candidate_catalog import CandidateCatalog
from omnis.modules.settings.catalog_models import CatalogError

ROOT = Path(__file__).resolve().parents[2]


def command(owner: str, **fields: object) -> dict[str, object]:
    return {"schema_version": 1, "owner_id": owner, "command_id": str(uuid4()), **fields}


@pytest.mark.asyncio
async def test_candidate_tracer_current_schema_is_ready(migrated_database_url: URL) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        async with engine.connect() as connection:
            columns = (
                await connection.execute(
                    text(
                        "SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_name LIKE 'catalog_%' ORDER BY table_name,ordinal_position"
                    )
                )
            ).all()
            constraints = (
                await connection.execute(
                    text(
                        "SELECT conrelid::regclass::text,conname,contype,pg_get_constraintdef(oid),convalidated,conenforced FROM pg_constraint WHERE conrelid::regclass::text LIKE 'catalog_%' ORDER BY conrelid::regclass::text,conname"
                    )
                )
            ).all()
            print(
                "CATALOG_SCHEMA",
                json.dumps(
                    {
                        "columns": [list(r) for r in columns],
                        "constraints": [list(r) for r in constraints],
                    }
                ),
            )
            assert await schema_reason_on(connection) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_candidate_tracer_review_denial_commits_reservations(
    migrated_database_url: URL, tmp_path: Path
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    owner = str(uuid4())
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    # Break a semantic cross-file contract while preserving parseable identity templates.
    path = package / "SKILL.md"
    path.write_text(
        path.read_text().replace("name: omnis-recon-mapping-contract", "name: incorrect")
    )
    # Use the actual existing name rather than assuming replacement succeeded.
    original = path.read_text()
    lines = original.splitlines(keepends=True)
    path.write_text(
        "".join("name: incorrect\n" if line.startswith("name:") else line for line in lines)
    )
    catalog = CandidateCatalog(engine, tmp_path / "catalog")
    try:
        captured = await catalog.dispatch(
            "capture",
            command(
                owner,
                author_kind="IMPORT",
                packages=[str(package)],
                profile=str(ROOT / "profiles/recon-mapping-contract.yaml"),
            ),
        )
        request = command(
            owner, draft_ref=captured["draft_ref"], source_draft_refs=captured["source_draft_refs"]
        )
        with pytest.raises(CatalogError, match="NATIVE_SKILL_MISMATCH"):
            await catalog.dispatch("review", request)
        with pytest.raises(CatalogError, match="NATIVE_SKILL_MISMATCH"):
            await catalog.dispatch("review", request)
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM catalog_reservation")) > 0
            rows = (
                (
                    await connection.execute(
                        text("SELECT envelope FROM catalog_record WHERE kind='technical-review'")
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1 and rows[0]["payload"]["status"] == "BLOCKED"
        async with engine.begin() as connection:
            with pytest.raises(DBAPIError):
                await connection.execute(text("DELETE FROM catalog_reservation"))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_candidate_tracer_concurrent_capture_exact_refs_and_tamper(
    migrated_database_url: URL, tmp_path: Path
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    owner = str(uuid4())
    catalog = CandidateCatalog(engine, tmp_path / "catalog")
    capture = command(
        owner,
        author_kind="OPERATOR",
        packages=[str(ROOT / "skills/recon-mapping-contract")],
        profile=str(ROOT / "profiles/recon-mapping-contract.yaml"),
    )
    try:
        first, second = await asyncio.gather(
            catalog.dispatch("capture", capture), catalog.dispatch("capture", capture)
        )
        assert first == second
        review = command(
            owner, draft_ref=first["draft_ref"], source_draft_refs=first["source_draft_refs"]
        )
        await catalog.dispatch("review", review)
        invalid = json.loads(json.dumps(review))
        invalid["draft_ref"]["revision"] = True
        with pytest.raises(CatalogError, match="INVALID_REQUEST"):
            await catalog.dispatch("review", invalid)
        missing = {**review, "command_id": str(uuid4()), "source_draft_refs": []}
        with pytest.raises(CatalogError, match="INVALID_REQUEST"):
            await catalog.dispatch("review", missing)
        foreign = {**review, "owner_id": str(uuid4()), "command_id": str(uuid4())}
        with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
            await catalog.dispatch("review", foreign)
        group = next((tmp_path / "catalog/drafts").iterdir())
        target = group / "profile.yaml"
        os.chmod(target, 0o600)
        with pytest.raises(CatalogError, match="FROZEN_MATERIAL_WRITABLE"):
            await catalog.dispatch("review", {**review, "command_id": str(uuid4())})
        os.chmod(target, 0o400)
        assert await catalog.dispatch("review", review)
    finally:
        await engine.dispose()
