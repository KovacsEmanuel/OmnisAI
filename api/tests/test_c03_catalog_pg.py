"""Real PG qualification. NOT_RUN until parent's attested DB runner."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from fixtures.b06a.consumer import mapping, sequence
from fixtures.b06b_publication.consumer import Seed
from fixtures.c03_capture import capture_seed
from omnis.core.db import database_engine
from omnis.modules.settings.candidate_catalog import CandidateCatalog, payload
from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.catalog_schema import canonical


@pytest.mark.asyncio
async def test_capture_admission_qualification_publish_replay(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url: URL = request.getfixturevalue("migrated_database_url")
    database_url = url.render_as_string(hide_password=False)
    engine = database_engine(database_url)
    source = capture_seed(tmp_path / "qualified", extra_requirement=True)
    service = CandidateCatalog(engine, source.catalog_root)
    publication = PublicationCatalog(engine, source.catalog_root)
    seed = Seed(
        source.directory, source.package, source.profile, source.catalog_root, source.owner_id
    )
    try:
        captured = await service.dispatch("capture", source.capture_request())
        source_refs = {
            "draft_ref": captured["draft_ref"],
            "source_draft_refs": captured["source_draft_refs"],
        }
        review = await service.dispatch("review", source.write_request(**source_refs))
        assert review["status"] == "STATIC_PASS"
        frozen = await service.dispatch(
            "freeze",
            source.write_request(
                **source_refs, technical_review_ref=review["technical_review_ref"]
            ),
        )
        value = {"capture": '[{"method":"GET","path":"/c03-pg","status":200}]'}
        admission_request = source.write_request(
            schema_version=2, snapshot_ref=frozen["snapshot_ref"], value=value
        )
        admitted = await service.dispatch("admit-evaluation-capture", admission_request)
        assert await service.dispatch("admit-evaluation-capture", admission_request) == admitted
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text("SELECT kind, envelope FROM catalog_record WHERE owner_id=:owner"),
                    {"owner": source.owner_id},
                )
            ).all()
        kinds = [row.kind for row in rows]
        assert (
            kinds.count("evaluation-admission")
            == kinds.count("contract-input-context")
            == kinds.count("contract-case-input")
            == 1
        )
        assert "managed-run" not in kinds
        assert payload(mapping(admitted["context"]))["namespace"] == "PACKAGE_EVAL"
        assert payload(mapping(admitted["input"]))["value"] == value
        with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
            await service.dispatch(
                "admit-evaluation-capture", {**admission_request, "value": {"capture": "[]"}}
            )
        with pytest.raises(CatalogError):
            await service.dispatch(
                "evaluate",
                source.write_request(
                    schema_version=2,
                    owner_id=str(uuid4()),
                    snapshot_ref=frozen["snapshot_ref"],
                    input_ref=admitted["input_ref"],
                    evaluation_kind="PURE",
                ),
            )
        with pytest.raises(CatalogError, match="UNBOUND_SLOT"):
            await service.dispatch(
                "evaluate",
                source.write_request(
                    snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input=value
                ),
            )
        receipts = {}
        commands = []
        for kind in ("STATIC", "PURE"):
            command = source.write_request(
                schema_version=2,
                snapshot_ref=frozen["snapshot_ref"],
                input_ref=admitted["input_ref"],
                evaluation_kind=kind,
            )
            commands.append(command)
            receipts[kind] = await service.dispatch("evaluate", command)
            assert receipts[kind]["status"] == kind + "_PASS"
        output = sequence(receipts["PURE"]["outputs"])[-1]
        assert isinstance(output, str)
        assert json.loads(output) == {
            "surface_map": [{"path": "/c03-pg", "methods": ["GET"], "operation_count": 1}]
        }
        head = await publication.dispatch("head", source.request(draft_ref=captured["draft_ref"]))
        body = payload(mapping(frozen["snapshot"]))
        selected = source.write_request(
            **source_refs,
            snapshot_ref=frozen["snapshot_ref"],
            technical_review_ref=review["technical_review_ref"],
            static_evaluation_ref=receipts["STATIC"]["evaluation_ref"],
            pure_evaluation_ref=receipts["PURE"]["evaluation_ref"],
            material_digest=body["material_digest"],
            resolved_index_digest=body["resolved_index_digest"],
            dependency_closure_digest=digest(canonical(body["dependency_closure_refs"])),
            expected_head_generation=head["generation"],
        )
        result, transcript = await asyncio.to_thread(seed.confirm, selected, database_url)
        assert result.returncode == 0, transcript
        confirmation = json.loads(result.stdout)
        published = await publication.dispatch(
            "publish",
            {
                **selected,
                "command_id": str(uuid4()),
                "confirmation_ref": confirmation["confirmation_ref"],
            },
        )
        assert published["state"] == "PUBLISHED"

        def no_evaluator(*args: object, **kwargs: object) -> object:
            raise AssertionError("readback/replay reran evaluator")

        monkeypatch.setattr("omnis.modules.settings.candidate_catalog.evaluate_pure", no_evaluator)
        for kind, command in zip(("STATIC", "PURE"), commands, strict=True):
            assert (
                await CandidateCatalog(engine, source.catalog_root).dispatch("evaluate", command)
                == receipts[kind]
            )
        assert (
            await CandidateCatalog(engine, source.catalog_root).dispatch(
                "admit-evaluation-capture", admission_request
            )
            == admitted
        )
        back = await publication.dispatch(
            "readback", source.request(publication_ref=published["publication_ref"])
        )
        assert back["state"] == "PUBLISHED"
    finally:
        await engine.dispose()
