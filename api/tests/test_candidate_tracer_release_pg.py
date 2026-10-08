"""Qualified RELEASE closure through the real durable CLI and attested PostgreSQL.

Eight bounded PG scenarios plus one pure producer/oracle control. Collection and
pure checks are not PG execution. No Publish or assessment selectability claim.
"""

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from fixtures.b06a_durable.releases import (
    PURE_INPUT,
    ROOT,
    Harness,
    binding,
    canonical,
    check_release,
    checked_record,
    external,
    fixture_connection,
    install_fixture,
    mapping,
    package_digest,
    payload,
    seed,
    select_profile,
    select_schema,
    sequence,
    sha,
    write_yaml,
    yaml_document,
)
from omnis.modules.settings import candidate_catalog, skill_catalog
from omnis.modules.settings.candidate_material import private_root
from omnis.modules.settings.candidate_resolution import ReleasePackage
from omnis.modules.settings.candidate_store import reference
from omnis.modules.settings.catalog_models import CatalogError


@pytest.fixture(autouse=True)
def exact_consumer_origin() -> None:
    installed = os.environ.get("OMNIS_B06A_QA_MODULE")
    expected = (
        Path(installed)
        if installed
        else ROOT / "api/src/omnis/modules/settings/candidate_catalog.py"
    )
    assert Path(candidate_catalog.__file__).resolve() == expected.resolve()
    assert Path(skill_catalog.__file__).resolve().parent == expected.resolve().parent
    if installed:
        assert not expected.resolve().is_relative_to(ROOT / "api/src")


def harness(directory: Path, root: Path, owner: str | None = None) -> Harness:
    python = os.environ.get("OMNIS_B06A_QA_PYTHON")
    module = os.environ.get("OMNIS_B06A_QA_MODULE")
    assert bool(python) == bool(module), "installed CLI interpreter/origin must be paired"
    return Harness(
        directory,
        root,
        owner if owner is not None else str(uuid4()),
        Path(python) if python else None,
        Path(module) if module else None,
    )


def blocked_result(
    h: Harness,
    url: URL,
    operation: str,
    request: dict[str, object],
    reason: str,
) -> dict[str, object]:
    # dispatch() raises a sanitized denial AFTER persisting the bounded BLOCKED
    # review/receipt. The CLI never returns this as a successful response.
    h.denied(operation, request, url, reason)
    h.denied(operation, request, url, reason)  # Exact replay still denies.
    with fixture_connection(url) as connection:
        row = connection.execute(
            "SELECT result FROM catalog_command WHERE owner_id=%s AND command_id=%s",
            (h.owner, request["command_id"]),
        ).fetchone()
        assert row is not None
        result = mapping(row[0])
        assert (result["status"], result["reason"]) == ("BLOCKED", reason)
        return result


def capture_review(
    h: Harness,
    url: URL,
    package: Path,
    profile: Path,
    *,
    reason: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    captured = h.success(
        "capture",
        h.request(author_kind="OPERATOR", packages=[str(package)], profile=str(profile)),
        url,
    )
    review_request = h.request(
        draft_ref=captured["draft_ref"], source_draft_refs=captured["source_draft_refs"]
    )
    if reason is None:
        reviewed = h.success("review", review_request, url)
        assert (reviewed["status"], reviewed["reason"]) == ("STATIC_PASS", None)
    else:
        reviewed = blocked_result(h, url, "review", review_request, reason)
    if reason is not None:
        denied_freeze = h.request(
            draft_ref=captured["draft_ref"],
            source_draft_refs=captured["source_draft_refs"],
            technical_review_ref=reviewed["technical_review_ref"],
        )
        h.denied("freeze", denied_freeze, url, "TECHNICAL_REVIEW_MISMATCH")
        with fixture_connection(url) as connection:
            group = connection.execute(
                "SELECT group_id FROM catalog_record WHERE id=%s",
                (mapping(captured["draft_ref"])["id"],),
            ).fetchone()
            assert group is not None
            assert connection.execute(
                "SELECT count(*) FROM catalog_record WHERE group_id=%s AND kind='candidate-snapshot'",
                (group[0],),
            ).fetchone() == (0,)
            stored = connection.execute(
                "SELECT envelope FROM catalog_record WHERE id=%s",
                (mapping(reviewed["technical_review_ref"])["id"],),
            ).fetchone()
            assert stored is not None
            body = payload(canonical(stored[0]))
            assert (body["status"], body["reason"]) == ("BLOCKED", reason)
    return captured, reviewed


def journey(
    h: Harness,
    url: URL,
    package: Path,
    profile: Path,
    releases: tuple[ReleasePackage, ...],
    closure: list[dict[str, object]],
    *,
    remove_sources: Path | None = None,
    blocked_input: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    expected_material = sha(
        canonical(
            {
                "packages": [
                    {
                        "package_key": yaml_document(package / "omnis.yaml")["package_key"],
                        "digest": package_digest(package),
                    }
                ],
                "profile_sha256": sha(profile.read_bytes()),
            }
        )
    )
    capture_request = h.request(
        author_kind="OPERATOR", packages=[str(package)], profile=str(profile)
    )
    captured = h.success("capture", capture_request, url)
    assert captured["material_digest"] == expected_material
    if remove_sources is not None:
        shutil.rmtree(remove_sources)
    assert h.success("capture", capture_request, url) == captured
    review_request = h.request(
        draft_ref=captured["draft_ref"], source_draft_refs=captured["source_draft_refs"]
    )
    reviewed = h.success("review", review_request, url)
    assert (reviewed["status"], reviewed["reason"]) == ("STATIC_PASS", None)
    assert h.success("review", review_request, url) == reviewed
    freeze_request = h.request(
        draft_ref=captured["draft_ref"],
        source_draft_refs=captured["source_draft_refs"],
        technical_review_ref=reviewed["technical_review_ref"],
    )
    frozen = h.success("freeze", freeze_request, url)
    assert h.success("freeze", freeze_request, url) == frozen
    body = payload(canonical(frozen["snapshot"]))
    assert body["dependency_closure_refs"] == sorted(closure, key=canonical)
    assert body["candidate_refs"] == reviewed["candidate_refs"]
    assert body["material_digest"] == captured["material_digest"]
    assert body["resolved_index_digest"] == reviewed["resolved_index_digest"]
    requests = []
    results = []
    for kind in ("STATIC", "PURE"):
        request = h.request(
            snapshot_ref=frozen["snapshot_ref"],
            evaluation_kind=kind,
            input=PURE_INPUT if kind == "PURE" else None,
        )
        result = h.success("evaluate", request, url)
        assert (result["status"], result["reason"]) == (kind + "_PASS", None)
        receipt = payload(canonical(result["evaluation"]))
        assert receipt["resolution"] == "NO_MODEL" and receipt["effective"] is None
        assert receipt["dependency_closure_refs"] == body["dependency_closure_refs"]
        assert receipt["dependency_closure_digest"] == sha(canonical(closure))
        assert receipt["material_digest"] == body["material_digest"]
        assert receipt["resolved_index_digest"] == body["resolved_index_digest"]
        assert (receipt["input_ref"] is None) == (kind == "STATIC")
        assert (
            result["outputs"] == sequence(payload(releases[0].qualification_json)["outputs"])
            if kind == "PURE"
            else result["outputs"] == []
        )
        assert h.success("evaluate", request, url) == result
        requests.append(request)
        results.append(result)
    if blocked_input:
        invalid_request = h.request(
            snapshot_ref=frozen["snapshot_ref"], evaluation_kind="PURE", input={}
        )
        invalid = blocked_result(h, url, "evaluate", invalid_request, "SCHEMA_VALIDATION")
        assert invalid["outputs"] == []
        invalid_receipt = payload(canonical(invalid["evaluation"]))
        assert invalid_receipt["input_ref"] is not None
        assert invalid_receipt["dependency_closure_refs"] == body["dependency_closure_refs"]
        results.append(invalid)
    back = h.success("readback", h.read_request(frozen["snapshot_ref"]), url)
    assert back["snapshot"] == frozen["snapshot"]
    assert back["publication"] == "UNPUBLISHED" and back["assessment_selectable"] is False
    index = mapping(back["resolved_index"])
    assert index["dependency_closure_refs"] == sorted(closure, key=canonical)
    assert index["dependency_artifact_refs"] == sorted(
        [reference(checked_record(r.artifact_json)) for r in releases], key=canonical
    )
    assert sha(canonical(index)) == body["resolved_index_digest"]
    expected_receipts = {canonical(result["evaluation"]) for result in results}
    assert {canonical(value) for value in sequence(back["evaluations"])} == expected_receipts
    # Fresh real connections corroborate input and receipts, not only CLI projections.
    with fixture_connection(url) as connection:
        for result in results:
            record = checked_record(canonical(result["evaluation"]))
            row = connection.execute(
                "SELECT envelope FROM catalog_record WHERE id=%s", (record["id"],)
            ).fetchone()
            assert row is not None and row[0] == record
            receipt = mapping(record["payload"])
            receipt_dir = h.catalog_root / "receipts" / str(record["id"])
            assert (receipt_dir / "receipt.json").read_bytes() == canonical(record)
            if receipt["input_ref"] is not None:
                input_ref = mapping(receipt["input_ref"])
                row = connection.execute(
                    "SELECT envelope FROM catalog_record WHERE id=%s", (input_ref["id"],)
                ).fetchone()
                assert row is not None
                input_record = checked_record(canonical(row[0]))
                assert reference(input_record) == input_ref
                assert mapping(input_record["payload"])["input"] == (
                    PURE_INPUT if result["status"] == "PURE_PASS" else {}
                )
                assert (receipt_dir / "input.json").read_bytes() == canonical(input_record)
                if result["outputs"]:
                    assert (receipt_dir / "outputs.json").read_bytes() == canonical(
                        result["outputs"]
                    )
                else:
                    assert not (receipt_dir / "outputs.json").exists()
    assert len(sequence(back["evaluations"])) == len(results), (
        "replay duplicated persistent receipts"
    )
    return frozen, requests[1]


def test_candidate_tracer_release_producer_checks_real_material(ipc_directory: Path) -> None:
    root = private_root(ipc_directory / "catalog")
    package, profile = seed(ipc_directory / "sources", "producer-control")
    release = external(root, package, profile)
    check_release(release)
    local, local_profile = seed(ipc_directory / "sources", "producer-consumer")
    select_schema(local, release)
    compiled = skill_catalog.compile_catalog((local,), local_profile, dependencies=(release,))
    expected = [
        binding(release, "schema", "capture"),
        binding(release, "package", "producer-control"),
    ]
    assert list(compiled.dependency_closure_refs) == sorted(expected, key=canonical)
    # An independent oracle must reject changed bytes and self-inconsistent envelopes.
    path = (
        root
        / "candidates"
        / str(checked_record(release.artifact_json)["id"])
        / "resolved-index.json"
    )
    original = path.read_bytes()
    path.chmod(0o600)
    path.write_bytes(b"{}")
    path.chmod(0o400)
    with pytest.raises(AssertionError):
        check_release(release)
    path.chmod(0o600)
    path.write_bytes(original)
    path.chmod(0o400)
    check_release(release)
    broken = mapping(json.loads(release.artifact_json))
    broken["digest"] = "0" * 64
    with pytest.raises(AssertionError):
        check_release(replace(release, artifact_json=canonical(broken)))


def test_candidate_tracer_release_pg_package_profile_restart(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "external")
    release = external(root, package, profile)
    install_fixture(migrated_database_url, h.owner, (release,))
    local, local_profile = seed(sources, "consumer")
    select_schema(local, release)
    select_profile(local_profile, release)
    closure = [
        binding(release, k, v)
        for k, v in (
            ("package", "external"),
            ("schema", "capture"),
            ("technique", "capture-mapping"),
            ("procedure", "map-capture"),
        )
    ]
    journey(
        h,
        migrated_database_url,
        local,
        local_profile,
        (release,),
        sorted(closure, key=canonical),
        remove_sources=sources,
        blocked_input=True,
    )
    assert not sources.exists()


def test_candidate_tracer_release_pg_diamond_exact_transitive_pins(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    pd, fd = seed(sources, "diamond-d")
    d = external(root, pd, fd)
    pb, fb = seed(sources, "diamond-b")
    select_schema(pb, d)
    b = external(root, pb, fb, (d,))
    pc, fc = seed(sources, "diamond-c")
    select_schema(pc, d)
    c = external(root, pc, fc, (d,))
    pa, fa = seed(sources, "diamond-a")
    select_schema(pa, b)
    select_schema(pa, c, "output_schema_ref")
    a = external(root, pa, fa, (b, c, d))
    inventory = (a, b, c, d)
    install_fixture(migrated_database_url, h.owner, tuple(reversed(inventory)))
    local, profile = seed(sources, "diamond-consumer")
    select_schema(local, a)
    compiled = skill_catalog.compile_catalog((local,), profile, dependencies=inventory)
    reverse = skill_catalog.compile_catalog(
        (local,), profile, dependencies=tuple(reversed(inventory))
    )
    assert compiled.resolved_index_digest == reverse.resolved_index_digest
    closure = [
        binding(r, "package", key)
        for r, key in ((a, "diamond-a"), (b, "diamond-b"), (c, "diamond-c"), (d, "diamond-d"))
    ]
    closure += [
        binding(a, "schema", "capture"),
        binding(b, "schema", "capture"),
        binding(c, "schema", "surface_map"),
        binding(d, "schema", "capture"),
    ]
    assert list(compiled.dependency_closure_refs) == sorted(closure, key=canonical)
    assert len(closure) == len({canonical(r) for r in closure}) == 8
    journey(
        h,
        migrated_database_url,
        local,
        profile,
        inventory,
        sorted(closure, key=canonical),
        remove_sources=sources,
    )


def test_candidate_tracer_release_pg_profile_only_transitive_qualification(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    pb, fb = seed(sources, "profile-dependency")
    b = external(root, pb, fb)
    pa, fa = seed(sources, "profile-qualified")
    select_profile(fa, b)
    a = external(root, pa, fa, (b,))
    install_fixture(migrated_database_url, h.owner, (a, b))
    local, profile = seed(sources, "profile-transitive-consumer")
    select_schema(local, a)
    closure = [
        binding(a, "package", "profile-qualified"),
        binding(a, "schema", "capture"),
        binding(b, "package", "profile-dependency"),
        binding(b, "technique", "capture-mapping"),
        binding(b, "procedure", "map-capture"),
    ]
    journey(
        h,
        migrated_database_url,
        local,
        profile,
        (a, b),
        sorted(closure, key=canonical),
        remove_sources=sources,
    )


def test_candidate_tracer_release_pg_absent_and_exact_selector_denials(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "pin-external")
    release = external(root, package, profile)
    local, profile = seed(sources, "pin-consumer")
    select_schema(local, release)
    capture_review(h, migrated_database_url, local, profile, reason="DEPENDENCY_UNAVAILABLE")
    install_fixture(migrated_database_url, h.owner, (release,))
    capture_review(h, migrated_database_url, local, profile)
    original = binding(release, "schema", "capture")
    for field, value in (
        ("id", str(uuid4())),
        ("revision", 2),
        ("digest", "0" * 64),
        ("kind", "procedure"),
    ):
        document = yaml_document(local / "omnis.yaml")
        document["input_schema_ref"] = {"kind": "RELEASE", "ref": {**original, field: value}}
        write_yaml(local / "omnis.yaml", document)
        capture_review(h, migrated_database_url, local, profile, reason="DEPENDENCY_UNAVAILABLE")
    document["input_schema_ref"] = {
        "kind": "RELEASE",
        "ref": binding(release, "procedure", "map-capture"),
    }
    write_yaml(local / "omnis.yaml", document)
    capture_review(h, migrated_database_url, local, profile, reason="REF_TYPE")
    select_schema(local, release)
    capture_review(h, migrated_database_url, local, profile)


def test_candidate_tracer_release_pg_owner_and_package_binding_denials(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    foreign = harness(ipc_directory / "foreign-cli", root)
    local_h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "foreign-external")
    release = external(root, package, profile)
    install_fixture(migrated_database_url, foreign.owner, (release,))
    positive, positive_profile = seed(sources, "foreign-control")
    select_schema(positive, release)
    capture_review(foreign, migrated_database_url, positive, positive_profile)
    local, local_profile = seed(sources, "owner-consumer")
    select_schema(local, release)
    capture_review(
        local_h, migrated_database_url, local, local_profile, reason="DEPENDENCY_UNAVAILABLE"
    )
    package, profile = seed(sources, "misbound-external")
    misbound = external(root, package, profile)
    install_fixture(
        migrated_database_url,
        local_h.owner,
        (misbound,),
        identity_package="not-the-artifact-package",
    )
    select_schema(local, misbound)
    capture_review(local_h, migrated_database_url, local, local_profile, reason="RELEASE_MISMATCH")


def test_candidate_tracer_release_pg_profile_requires_selected_package(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "profile-external")
    release = external(root, package, profile)
    install_fixture(migrated_database_url, h.owner, (release,))
    local, profile = seed(sources, "profile-consumer")
    select_profile(profile, release)
    positive = yaml_document(profile)
    capture_review(h, migrated_database_url, local, profile)
    recipe = mapping(sequence(positive["agent_recipes"])[0])
    recipe["package_refs"] = sequence(recipe["package_refs"])[:1]
    write_yaml(profile, {**positive, "agent_recipes": [recipe]})
    capture_review(h, migrated_database_url, local, profile, reason="PROFILE_PACKAGE_MISMATCH")
    select_profile(profile, release)
    capture_review(h, migrated_database_url, local, profile)


def test_candidate_tracer_release_pg_compatibility_shadow_and_path_stage(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "boundary-external")
    release = external(root, package, profile)
    install_fixture(migrated_database_url, h.owner, (release,))
    local, profile = seed(sources, "boundary-consumer")
    select_schema(local, release)
    capture_review(h, migrated_database_url, local, profile)
    document = yaml_document(local / "omnis.yaml")
    compatibility = mapping(document["compatibility"])
    literal = "0" * 40
    compatibility["hermes_revision"] = literal
    write_yaml(local / "omnis.yaml", {**document, "compatibility": compatibility})
    encoded = mapping(yaml_document(local / "omnis.yaml")["compatibility"])["hermes_revision"]
    assert type(encoded) is str and encoded == literal
    capture_review(h, migrated_database_url, local, profile, reason="INCOMPATIBLE_HERMES")
    write_yaml(local / "omnis.yaml", document)
    capture_review(h, migrated_database_url, local, profile)
    # Same package key is not repaired/renamed by the resolver.
    shadow, shadow_profile = seed(sources / "shadow", "boundary-external")
    select_schema(shadow, release)
    capture_review(h, migrated_database_url, shadow, shadow_profile, reason="PACKAGE_SHADOW")
    path_package, path_profile = seed(sources, "path-external")
    path_release = external(root, path_package, path_profile)
    record = checked_record(path_release.artifact_json)
    data = mapping(record["payload"])
    listed_sources = [mapping(s) for s in sequence(data["sources"])]
    files = [mapping(f) for f in sequence(listed_sources[0]["files"])]
    files[0]["path"] = "../outside"
    listed_sources[0]["files"] = files
    record["payload"] = {**data, "sources": listed_sources}
    record["digest"] = sha(canonical({k: v for k, v in record.items() if k != "digest"}))
    unsafe = replace(path_release, artifact_json=canonical(record))
    install_fixture(migrated_database_url, h.owner, (unsafe,))
    select_schema(local, unsafe)
    capture_review(h, migrated_database_url, local, profile, reason="INVALID_PATH")


def test_candidate_tracer_release_pg_declared_cycle_refuses_at_exact_loader(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "cycle-external")
    release = external(root, package, profile)
    local, profile = seed(sources, "cycle-consumer")
    select_schema(local, release)
    skill_catalog.compile_catalog((local,), profile, dependencies=(release,))
    record = checked_record(release.artifact_json)
    record["payload"] = {
        **mapping(record["payload"]),
        "dependency_artifact_refs": [reference(record)],
    }
    record["digest"] = sha(canonical({k: v for k, v in record.items() if k != "digest"}))
    cyclic = replace(release, artifact_json=canonical(record))
    # Source compiler detects graph-by-ID. Immutable PG loader rejects the old
    # self edge's digest first; claiming durable DEPENDENCY_CYCLE would be false.
    with pytest.raises(CatalogError, match="DEPENDENCY_CYCLE"):
        skill_catalog.compile_catalog((local,), profile, dependencies=(cyclic,))
    install_fixture(migrated_database_url, h.owner, (cyclic,))
    capture_review(h, migrated_database_url, local, profile, reason="RELEASE_MISMATCH")


def test_candidate_tracer_release_pg_frozen_external_missing_or_tampered(
    migrated_database_url: URL,
    ipc_directory: Path,
) -> None:
    root = private_root(ipc_directory / "catalog")
    sources = ipc_directory / "sources"
    h = harness(ipc_directory / "cli", root)
    package, profile = seed(sources, "material-external")
    release = external(root, package, profile)
    install_fixture(migrated_database_url, h.owner, (release,))
    local, profile = seed(sources, "material-consumer")
    select_schema(local, release)
    closure = sorted(
        [binding(release, "schema", "capture"), binding(release, "package", "material-external")],
        key=canonical,
    )
    frozen, pure_request = journey(
        h, migrated_database_url, local, profile, (release,), closure, remove_sources=sources
    )
    path = (
        root
        / "candidates"
        / str(checked_record(release.artifact_json)["id"])
        / "resolved-index.json"
    )
    original = path.read_bytes()
    # Move outside the expected namespace, then restore exact modes before probe.
    moved = ipc_directory / "retained-index.json"
    path.parent.chmod(0o700)
    path.rename(moved)
    path.parent.chmod(0o500)
    h.denied(
        "readback",
        h.read_request(frozen["snapshot_ref"]),
        migrated_database_url,
        "FROZEN_MATERIAL_MISMATCH",
    )
    h.denied("evaluate", pure_request, migrated_database_url, "FROZEN_MATERIAL_MISMATCH")
    path.parent.chmod(0o700)
    moved.rename(path)
    path.parent.chmod(0o500)
    assert (
        h.success("readback", h.read_request(frozen["snapshot_ref"]), migrated_database_url)[
            "snapshot"
        ]
        == frozen["snapshot"]
    )
    path.chmod(0o600)
    path.write_bytes(b"{}")
    path.chmod(0o400)
    h.denied(
        "readback",
        h.read_request(frozen["snapshot_ref"]),
        migrated_database_url,
        "FROZEN_MATERIAL_MISMATCH",
    )
    h.denied("evaluate", pure_request, migrated_database_url, "FROZEN_MATERIAL_MISMATCH")
    path.chmod(0o600)
    path.write_bytes(original)
    path.chmod(0o400)
    check_release(release)
    assert h.success("evaluate", pure_request, migrated_database_url)["status"] == "PURE_PASS"
    back = h.success("readback", h.read_request(frozen["snapshot_ref"]), migrated_database_url)
    assert back["publication"] == "UNPUBLISHED" and back["assessment_selectable"] is False
    assert len(sequence(back["evaluations"])) == 2
