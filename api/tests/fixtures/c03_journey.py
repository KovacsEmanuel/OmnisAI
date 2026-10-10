"""C03 real private CLI qualification/publication fixture, never a receipt substitute."""

from hashlib import sha256
from pathlib import Path

from fixtures.b06a.consumer import mapping, sequence, write_yaml, yaml_object
from fixtures.b06b_publication.consumer import (
    Qualified,
    Seed,
    canonical,
    confirmed,
    publish_request,
)
from fixtures.c03_capture import capture_seed


def qualify_capture(directory: Path, database_url: str) -> tuple[Qualified, dict[str, object]]:
    source = capture_seed(directory, extra_requirement=True)
    # Author a new compact fixture before capture/qualification. No retained
    # bytes or semantic requirements are truncated, and product caps are fixed.
    for name in ("capture", "records", "operations", "surface_map", "empty"):
        schema_path = source.package / f"templates/schemas/{name}.schema.json"
        schema_path.write_bytes(canonical(yaml_object(schema_path)))
    procedure_path = source.package / "templates/procedures/map-capture.yaml"
    procedure = yaml_object(procedure_path)
    mapping(procedure["limits"])["deadline_seconds"] = 300
    write_yaml(procedure_path, procedure)
    profile = yaml_object(source.profile)
    recipe = mapping(sequence(profile["agent_recipes"])[0])
    mapping(recipe["limits"])["deadline_seconds"] = 300
    write_yaml(source.profile, profile)
    seed = Seed(
        source.directory, source.package, source.profile, source.catalog_root, source.owner_id
    )
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
        "admit-evaluation-capture",
        seed.write(
            schema_version=2,
            snapshot_ref=frozen["snapshot_ref"],
            value={"capture": '[{"method":"GET","path":"/evaluation-only","status":200}]'},
        ),
        database_url,
        candidate=True,
    )
    evaluations = [
        seed.success(
            "evaluate",
            seed.write(
                schema_version=2,
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
    qualified = Qualified(
        seed, captured, capture_command, review, frozen, evaluations[0], evaluations[1], selection
    )
    return qualified, admitted


def publish_capture(
    qualified: Qualified, database_url: str
) -> tuple[dict[str, object], dict[str, object]]:
    seed = qualified.seed
    published = seed.success(
        "publish", publish_request(qualified, confirmed(qualified, database_url)), database_url
    )
    snapshot = seed.success(
        "snapshot", seed.write(publication_ref=published["publication_ref"]), database_url
    )
    return published, snapshot
