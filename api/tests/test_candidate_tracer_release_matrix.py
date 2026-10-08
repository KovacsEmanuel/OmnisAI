"""Missing source-template controls and durable qualified procedure identities.

External RELEASE rows are owned by Dev A's actual fixture contract, not invented
here. STATIC/PURE slot templates do not establish runtime case/Task binding.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy.engine import URL

from conftest import connect_test_database
from fixtures.b06a.consumer import (
    CatalogSeed,
    blocked,
    mapping,
    procedure,
    sequence,
    write_yaml,
    yaml_object,
)
from fixtures.b06a_durable.consumer import (
    canonical,
    copy_seed,
    envelope,
    freeze_request,
    package_digest,
    readback,
    scratch_directory,
)
from omnis.modules.settings.catalog_models import CatalogError, StepOutputRef
from omnis.modules.settings.skill_catalog import compile_catalog, evaluate_pure


def source_seed(directory: Path) -> CatalogSeed:
    copied = copy_seed(directory)
    return CatalogSeed(copied.directory, copied.package, copied.profile)


@pytest.mark.parametrize(("minimum", "maximum"), [(0, 1), (1, 1), (0, 4), (2, 4)])
def test_candidate_tracer_static_slot_collection_cardinality(
    ipc_directory: Path,
    minimum: int,
    maximum: int,
) -> None:
    seed = source_seed(ipc_directory / "slot-cardinality")
    compile_catalog((seed.package,), seed.profile)
    path, document = procedure(seed)
    document["slots"] = [
        {
            "name": "rules",
            "expected_kind": "business_rule",
            "min_items": minimum,
            "max_items": maximum,
        }
    ]
    document["business_rule_refs"] = [{"kind": "CASE_SLOT_REF", "name": "rules"}]
    write_yaml(path, document)
    compiled = compile_catalog((seed.package,), seed.profile)
    assert len(compiled.slots) == 1
    assert (compiled.slots[0].min_items, compiled.slots[0].max_items) == (minimum, maximum)
    assert compiled.resolution == "NO_MODEL"
    golden = mapping(json.loads((seed.directory / "golden.json").read_bytes()))
    with pytest.raises(CatalogError, match="^UNBOUND_SLOT$"):
        evaluate_pure(compiled, golden["input"])
    # Actual stored compiler fields; do not assume outputs/handler_key/bindings fields.
    assert len(compiled.steps) == 3
    for step in compiled.steps[1:]:
        assert len(step.bindings) == 1
        assert isinstance(step.bindings[0].source_ref, StepOutputRef)
        assert step.bindings[0].selector is None


@pytest.mark.parametrize("attack", ["missing", "duplicate", "wrong_kind", "reversed"])
def test_candidate_tracer_static_slot_declaration_matrix(ipc_directory: Path, attack: str) -> None:
    seed = source_seed(ipc_directory / "slot-denial")
    seed.compile()  # Same source CLI positive, then exact denial.
    path, document = procedure(seed)
    slot = {"name": "rules", "expected_kind": "business_rule", "min_items": 1, "max_items": 1}
    document["slots"] = [slot]
    document["business_rule_refs"] = [{"kind": "CASE_SLOT_REF", "name": "rules"}]
    reason = "SLOT_DECLARATION"
    if attack == "missing":
        document["slots"] = []
    elif attack == "duplicate":
        document["slots"] = [slot, dict(slot)]
    elif attack == "wrong_kind":
        slot["expected_kind"] = "identity"
    else:
        slot.update(min_items=2, max_items=1)
    write_yaml(path, document)
    assert blocked(seed.cli("compile")) == reason


@pytest.mark.parametrize(
    ("attack", "reason"),
    [
        ("local", "INVALID_DTO"),
        ("missing_package", "MISSING_REF"),
        ("wrong_package_key", "MISSING_REF"),
        ("wrong_kind", "REF_TYPE"),
    ],
)
def test_candidate_tracer_static_profile_namespace_matrix(
    ipc_directory: Path,
    attack: str,
    reason: str,
) -> None:
    seed = source_seed(ipc_directory / "profile-namespace")
    seed.compile()
    profile = yaml_object(seed.profile)
    recipe = mapping(sequence(profile["agent_recipes"])[0])
    refs = [mapping(item) for item in sequence(recipe["procedure_refs"])]
    if attack == "local":
        refs[0].pop("package_key")
        refs[0]["kind"] = "LOCAL"
    elif attack == "missing_package":
        refs[0]["package_key"] = "absent"
    elif attack == "wrong_kind":
        refs[0]["entity_kind"] = "schema"
    else:
        recipe["package_refs"] = [
            {
                "kind": "CANDIDATE",
                "package_key": "recon-mapping-contract",
                "entity_kind": "package",
                "key": "absent",
            }
        ]
    recipe["procedure_refs"] = refs
    profile["agent_recipes"] = [recipe]
    write_yaml(seed.profile, profile)
    assert blocked(seed.cli("compile")) == reason


def renamed(value: object, package: str) -> object:
    if isinstance(value, list):
        return [renamed(item, package) for item in value]
    if isinstance(value, dict):
        return {str(key): renamed(item, package) for key, item in value.items()}
    if value == "recon-mapping-contract":
        return package
    if value == "map-capture":
        return "inspect"
    return value


def inspect_package(seed: CatalogSeed, key: str) -> None:
    write_yaml(seed.manifest, mapping(renamed(yaml_object(seed.manifest), key)))
    path, document = procedure(seed)
    write_yaml(path, mapping(renamed(document, key)))
    write_yaml(seed.profile, mapping(renamed(yaml_object(seed.profile), key)))
    skill = seed.package / "SKILL.md"
    original = skill.read_text()
    assert "name: recon-mapping-contract" in original
    skill.write_text(original.replace("name: recon-mapping-contract", f"name: {key}", 1))


def test_candidate_tracer_durable_alpha_beta_inspect_procedure_ids(
    migrated_database_url: URL,
) -> None:
    alpha = copy_seed(scratch_directory() / "qualified-alpha-beta")
    beta = copy_seed(alpha.directory / "beta-source")
    source_alpha = CatalogSeed(alpha.directory, alpha.package, alpha.profile)
    source_beta = CatalogSeed(beta.directory, beta.package, beta.profile)
    inspect_package(source_alpha, "alpha")
    inspect_package(source_beta, "beta")
    profile = yaml_object(alpha.profile)
    recipe = mapping(sequence(profile["agent_recipes"])[0])
    recipe["package_refs"] = [
        *sequence(recipe["package_refs"]),
        {"kind": "CANDIDATE", "package_key": "beta", "entity_kind": "package", "key": "beta"},
    ]
    profile["agent_recipes"] = [recipe]
    write_yaml(alpha.profile, profile)
    url = migrated_database_url.render_as_string(hide_password=False)
    captured = alpha.success(
        "capture",
        alpha.write_request(
            author_kind="OPERATOR",
            packages=[str(alpha.package), str(beta.package)],
            profile=str(alpha.profile),
        ),
        url,
    )
    review = alpha.success(
        "review",
        alpha.write_request(
            draft_ref=captured["draft_ref"],
            source_draft_refs=captured["source_draft_refs"],
        ),
        url,
    )
    refs = [mapping(item) for item in sequence(review["candidate_refs"])]
    with connect_test_database(migrated_database_url, autocommit=True) as observer:
        rows = observer.execute(
            "SELECT package_key, id::text FROM catalog_identity "
            "WHERE owner_id=%s AND entity_kind='procedure' AND entity_key='inspect' "
            "ORDER BY package_key",
            (alpha.owner_id,),
        ).fetchall()
        assert len(rows) == 2 and [row[0] for row in rows] == ["alpha", "beta"]
        assert rows[0][1] != rows[1][1]
    digests = {"alpha": package_digest(alpha.package), "beta": package_digest(beta.package)}
    for package, identity in rows:
        found = [ref for ref in refs if ref["id"] == identity]
        assert len(found) == 1
        assert found[0]["kind"] == "procedure" and found[0]["revision"] == 1
        assert found[0]["digest"] == digests[str(package)]
    frozen = alpha.success("freeze", freeze_request(alpha, captured, review), url)
    payload = envelope(frozen["snapshot"], frozen["snapshot_ref"])
    assert payload["candidate_refs"] == review["candidate_refs"]
    back = readback(alpha, url, frozen)
    assert '"kind":"LOCAL"' not in canonical(back["resolved_index"]).decode()
    assert '"kind":"CANDIDATE"' not in canonical(back["resolved_index"]).decode()
    assert back["publication"] == "UNPUBLISHED" and back["assessment_selectable"] is False
