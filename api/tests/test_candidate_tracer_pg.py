"""Dev A vertical tracer: exact captured bytes and definitive PostgreSQL identities."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine

ROOT = Path(__file__).resolve().parents[2]


def request(owner: str, **fields: object) -> dict[str, object]:
    return {"schema_version": 1, "owner_id": owner, "command_id": str(uuid4()), **fields}


@pytest.mark.asyncio
async def test_capture_reservations_survive_rejection(
    migrated_database_url: URL, tmp_path: Path
) -> None:
    assert importlib.util.find_spec("omnis.modules.settings.candidate_catalog") is not None, (
        "durable candidate consumer is absent"
    )
    from omnis.modules.settings.candidate_catalog import CandidateCatalog

    package = tmp_path / "source"
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    profile = tmp_path / "profile.yaml"
    shutil.copyfile(ROOT / "profiles/recon-mapping-contract.yaml", profile)
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    catalog = CandidateCatalog(engine, tmp_path / "catalog")
    owner = str(uuid4())
    capture_request = request(
        owner, author_kind="AI", packages=[str(package)], profile=str(profile)
    )
    try:
        captured = await catalog.dispatch("capture", capture_request)
        assert await catalog.dispatch("capture", capture_request) == captured
        assert isinstance(captured["source_draft_refs"], list)
        assert len(captured["source_draft_refs"]) == 2
        async with engine.connect() as connection:
            rows = (
                (await connection.execute(text("SELECT envelope FROM catalog_record")))
                .scalars()
                .all()
            )
        assert len(rows) == 2
        for row in rows:
            preimage = {key: value for key, value in row.items() if key != "digest"}
            raw = json.dumps(
                preimage, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
            assert row["digest"] == hashlib.sha256(raw).hexdigest()
        source_refs = {
            "draft_ref": captured["draft_ref"],
            "source_draft_refs": captured["source_draft_refs"],
        }
        shutil.rmtree(package)
        profile.unlink()
        review_request = request(owner, **source_refs)
        reviewed = await catalog.dispatch("review", review_request)
        assert reviewed["status"] == "STATIC_PASS"
        assert reviewed["candidate_refs"]
        assert await catalog.dispatch("review", review_request) == reviewed
        rejected = await catalog.dispatch("reject", request(owner, **source_refs))
        assert rejected["state"] == "REJECTED"
        async with engine.connect() as connection:
            before = (
                await connection.execute(
                    text("SELECT id, revision, digest FROM catalog_reservation ORDER BY id")
                )
            ).all()
        assert before
        shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
        (package / "NOTICE.md").write_text("Changed synthetic notice\n")
        shutil.copyfile(ROOT / "profiles/recon-mapping-contract.yaml", profile)
        changed = await catalog.dispatch(
            "capture",
            request(owner, author_kind="OPERATOR", packages=[str(package)], profile=str(profile)),
        )
        await catalog.dispatch(
            "review",
            request(
                owner,
                draft_ref=changed["draft_ref"],
                source_draft_refs=changed["source_draft_refs"],
            ),
        )
        async with engine.connect() as connection:
            after = (
                await connection.execute(
                    text(
                        "SELECT id, revision, digest FROM catalog_reservation ORDER BY id, revision"
                    )
                )
            ).all()
        assert all(row in after for row in before)
        assert any(row.revision == 2 for row in after)
        env = {
            **os.environ,
            "OMNIS_DATABASE_URL": migrated_database_url.render_as_string(hide_password=False),
        }
        wire = tmp_path / "request.json"
        wire.write_text(json.dumps(capture_request))
        # A fresh process must replay without reopening the now changed workspace.
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "omnis.modules.settings.candidate_catalog",
                "capture",
                "--request",
                str(wire),
                "--catalog-root",
                str(tmp_path / "catalog"),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0 and result.stderr == ""
        assert json.loads(result.stdout) == captured
    finally:
        await engine.dispose()
