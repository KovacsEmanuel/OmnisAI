"""Owned two-package input; real existing catalog qualification, no receipt forgery."""

from hashlib import sha256

from fixtures.b06b_publication.consumer import (
    Qualified,
    Seed,
    canonical,
    envelope,
    mapping,
    new_seed,
    sequence,
)


class TwoSkillSeed(Seed):
    def capture(self, author: str = "OPERATOR") -> dict[str, object]:
        return self.write(
            author_kind=author,
            packages=[str(self.package), str(self.directory / "composition-support")],
            profile=str(self.profile),
        )


def new_two_skill_seed() -> TwoSkillSeed:
    original = new_seed()
    seed = TwoSkillSeed(
        original.directory, original.package, original.profile, original.root, original.owner
    )
    support = seed.directory / "composition-support"
    (support / "templates").mkdir(parents=True)
    skill = b"---\nname: composition-support\ndescription: Inert composition support\nversion: 0.1.0\nprovenance: Omnis first-party synthetic input.\n---\nRetain exact assignment; no execution or authority.\n"
    (support / "SKILL.md").write_bytes(skill)
    (support / "NOTICE.md").write_text(
        "Omnis first-party synthetic C05 input. No upstream skill copied.\n"
    )
    (support / "templates/empty.schema.json").write_bytes(
        (seed.package / "templates/empty.schema.json").read_bytes()
    )
    from omnis.modules.settings.catalog_schema import load_json

    base = mapping(load_json((seed.package / "omnis.yaml").read_bytes()))
    schema = {"kind": "LOCAL", "entity_kind": "schema", "key": "empty"}
    manifest = {
        **base,
        "package_key": "composition-support",
        "native_name": "composition-support",
        "techniques": [],
        "procedures": [],
        "input_schema_ref": schema,
        "output_schema_ref": schema,
        "support_files": ["NOTICE.md", "templates/empty.schema.json"],
        "file_bindings": [
            {"entity_kind": "schema", "key": "empty", "path": "templates/empty.schema.json"}
        ],
        "provenance": [
            {
                "repository": "OmnisAI",
                "revision": "6858e4ea7bb9e260425249e764df7b69cfc0a0d1",
                "path": "SKILL.md",
                "source_digest": sha256(skill).hexdigest(),
                "license_id": "LicenseRef-Omnis-FirstParty",
                "notice_paths": ["NOTICE.md"],
                "modification_note": "New synthetic composition support input authored from scratch.",
            }
        ],
    }
    (support / "omnis.yaml").write_bytes(canonical(manifest))
    profile = mapping(load_json(seed.profile.read_bytes()))
    recipe = mapping(sequence(profile["agent_recipes"])[0])
    recipe["package_refs"] = [
        *sequence(recipe["package_refs"]),
        {
            "kind": "CANDIDATE",
            "package_key": "composition-support",
            "entity_kind": "package",
            "key": "composition-support",
        },
    ]
    # Keep the whole prepare/CLI/binding probe inside its synthetic deadline.
    recipe["limits"] = {**mapping(recipe["limits"]), "deadline_seconds": 300}
    profile["agent_recipes"] = [recipe]
    seed.profile.write_bytes(canonical(profile))
    procedure_path = seed.package / "templates/procedures/publication-map.yaml"
    procedure = mapping(load_json(procedure_path.read_bytes()))
    procedure["limits"] = {**mapping(procedure["limits"]), "deadline_seconds": 300}
    procedure_path.write_bytes(canonical(procedure))
    return seed


def qualify_two(seed: TwoSkillSeed, database_url: str) -> Qualified:
    capture_command = seed.capture()
    captured = seed.success("capture", capture_command, database_url, candidate=True)
    selected = {
        "draft_ref": captured["draft_ref"],
        "source_draft_refs": captured["source_draft_refs"],
    }
    reviewed = seed.success("review", seed.write(**selected), database_url, candidate=True)
    frozen = seed.success(
        "freeze",
        seed.write(**selected, technical_review_ref=reviewed["technical_review_ref"]),
        database_url,
        candidate=True,
    )
    body = envelope(frozen["snapshot"], frozen["snapshot_ref"])
    evaluations = []
    from omnis.modules.settings.catalog_schema import load_json

    for kind in ("STATIC", "PURE"):
        result = seed.success(
            "evaluate",
            seed.write(
                snapshot_ref=frozen["snapshot_ref"],
                evaluation_kind=kind,
                input=None
                if kind == "STATIC"
                else load_json((seed.directory / "input.json").read_bytes()),
            ),
            database_url,
            candidate=True,
        )
        assert result["status"] == kind + "_PASS"
        evaluations.append(result)
    head = seed.success("head", seed.request(draft_ref=captured["draft_ref"]), database_url)
    selection = {
        **selected,
        "expected_head_generation": head["generation"],
        "snapshot_ref": frozen["snapshot_ref"],
        "technical_review_ref": reviewed["technical_review_ref"],
        "static_evaluation_ref": evaluations[0]["evaluation_ref"],
        "pure_evaluation_ref": evaluations[1]["evaluation_ref"],
        "material_digest": body["material_digest"],
        "resolved_index_digest": body["resolved_index_digest"],
        "dependency_closure_digest": sha256(canonical(body["dependency_closure_refs"])).hexdigest(),
    }
    return Qualified(
        seed, captured, capture_command, reviewed, frozen, evaluations[0], evaluations[1], selection
    )
