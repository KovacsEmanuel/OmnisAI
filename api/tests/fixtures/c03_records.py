"""New first-party source and real private CLI qualification, no receipt substitutes."""

import shutil
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fixtures.b06b_publication.consumer import Qualified, Seed, canonical, mapping

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = "records-mapping-contract"
PATHS = (
    "SKILL.md",
    "omnis.yaml",
    "NOTICE.md",
    "references/methodology.md",
    "templates/procedures/map-records.yaml",
    "templates/schemas/records.schema.json",
    "templates/schemas/operations.schema.json",
    "templates/schemas/surface_map.schema.json",
    "templates/schemas/empty.schema.json",
)
EVALUATION_VALUE = {
    "records": [
        {"method": "POST", "path": "/evaluation-z", "status": 201},
        {"method": "GET", "path": "/evaluation-a", "status": 404},
        {"method": "GET", "path": "/evaluation-a", "status": 200},
        {"method": "POST", "path": "/evaluation-z", "status": 201},
    ]
}


def records_seed(directory: Path) -> Seed:
    directory.mkdir(parents=True, mode=0o700)
    package = directory / PACKAGE
    for name in PATHS:
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "skills" / PACKAGE / name, target)
    profile = directory / "profile.yaml"
    shutil.copyfile(ROOT / "profiles" / (PACKAGE + ".yaml"), profile)
    return Seed(directory, package, profile, directory / "catalog", str(uuid4()))


def qualify_records(directory: Path, database_url: str) -> tuple[Qualified, dict[str, object]]:
    seed = records_seed(directory)
    capture_command = seed.capture()
    captured = seed.success("capture", capture_command, database_url, candidate=True)
    refs = {k: captured[k] for k in ("draft_ref", "source_draft_refs")}
    review = seed.success("review", seed.write(**refs), database_url, candidate=True)
    frozen = seed.success(
        "freeze",
        seed.write(**refs, technical_review_ref=review["technical_review_ref"]),
        database_url,
        candidate=True,
    )
    admitted = seed.success(
        "admit-evaluation-records",
        seed.write(schema_version=3, snapshot_ref=frozen["snapshot_ref"], value=EVALUATION_VALUE),
        database_url,
        candidate=True,
    )
    evaluations = [
        seed.success(
            "evaluate",
            seed.write(
                schema_version=3,
                snapshot_ref=frozen["snapshot_ref"],
                input_ref=admitted["input_ref"],
                evaluation_kind=kind,
            ),
            database_url,
            candidate=True,
        )
        for kind in ("STATIC", "PURE")
    ]
    assert [e["status"] for e in evaluations] == ["STATIC_PASS", "PURE_PASS"]
    head = seed.success("head", seed.request(draft_ref=captured["draft_ref"]), database_url)
    body = mapping(mapping(frozen["snapshot"])["payload"])
    selection = {
        **refs,
        "expected_head_generation": head["generation"],
        "snapshot_ref": frozen["snapshot_ref"],
        "technical_review_ref": review["technical_review_ref"],
        "static_evaluation_ref": evaluations[0]["evaluation_ref"],
        "pure_evaluation_ref": evaluations[1]["evaluation_ref"],
        "material_digest": body["material_digest"],
        "resolved_index_digest": body["resolved_index_digest"],
        "dependency_closure_digest": sha256(canonical(body["dependency_closure_refs"])).hexdigest(),
    }
    return Qualified(
        seed, captured, capture_command, review, frozen, evaluations[0], evaluations[1], selection
    ), admitted
