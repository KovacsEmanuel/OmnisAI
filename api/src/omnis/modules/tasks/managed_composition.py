"""Final inert prompt material. No native import or runtime installation required.

The native consumer independently validates these bytes. This producer grants no
model, tool, target, or method-execution authority.
"""

import base64
import binascii
from collections.abc import Sequence
from hashlib import sha256
from typing import TYPE_CHECKING

from omnis.modules.runs import native_preparation_models as preparation
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import (
    CandidateRef,
    CatalogError,
    LocalRef,
    Manifest,
    Procedure,
    Recipe,
)
from omnis.modules.settings.catalog_schema import canonical, dto, load_json
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.managed_contract import (
    exact,
    integer,
    mapping,
    record,
    ref,
    sequence,
    text,
)

if TYPE_CHECKING:
    from omnis.policy.model_projection import SyntheticApproval

PROTOCOL = "omnis-managed-admission-v2"
# Exact native composer source; parity test binds this to the installed producer.
LEGACY_COMPOSER_REVISION = "dfdd1ccad8ad93c13adb28bec45ac5d94d49f29ff53e8371cf6650107b67c11f"
CAPTURE_COMPOSER_REVISION = "70b0c25c4c844b4af292061987b961cabe6d4cc361f6cda79d8947eb11ccdd8a"
RECORDS_COMPOSER_REVISION = "55963352e1b855f51f379bdfb0cf0ff49b0004dacb40aad32ef85ea9f3b5828c"
COMPOSER_REVISION = "2cec176a5e622df2751e069b2a676c7e64578bea33b768aab63b09c78698f473"
PROVENANCE = [
    {
        "repository": "https://github.com/usestrix/strix",
        "revision": "ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2",
        "path": "strix/agents/prompt.py",
        "source_digest": "2b30f1ecee988f9effed96c54af2baecd3a6506b6bcfdc5bd9a0f325cf540a33",
        "license_id": "Apache-2.0",
        "notice_paths": [
            "integrations/hermes/upstream/composition-NOTICE.md",
            "integrations/hermes/upstream/composition-LICENSE",
        ],
        "modification_note": "S01 adaptation: ordered base/role/assignment/method/selected-skill composition; first-party canonical JSON, strict immutable refs and fail-closed budgets. No Jinja, foreign runtime, implicit skills, model or tool execution.",
    }
]
BASE_TEXT = (
    "CONTRACT_PROBE. No provider, model, tools, targets, or domain reads. Return NO_MODEL only."
)
ROLE_TEXT = "SUPPORT-only cold admission probe; not an assessment."
CONTRACT_BASE_TEXT = "CONTRACT_PROBE. Deterministic PURE method only; no provider, model, target or stock tools. Read only the bound assignment inputs."
CONTRACT_ROLE_TEXT = "SUPPORT-only native CONTRACT/PURE method; not an assessment."


def prompt_settings() -> dict[str, object]:
    preparation.sha(COMPOSER_REVISION)
    return {"composer_revision": COMPOSER_REVISION, "provenance": PROVENANCE}


def require_recipe(recipe: Recipe, procedure: Procedure, package: str) -> None:
    if len(recipe.technique_refs) != 1:
        raise CatalogError("UNSUPPORTED_RECIPE")
    selected = recipe.technique_refs[0]
    source = procedure.technique_ref
    if (
        not isinstance(selected, CandidateRef)
        or not isinstance(source, LocalRef)
        or selected.package_key != package
        or selected.entity_kind != source.entity_kind
        or selected.key != source.key
    ):
        raise CatalogError("UNSUPPORTED_RECIPE")


def selected_skills(
    packages: list[dict[str, object]],
    package_refs: object,
    technique_ref: object,
    bindings: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Select SKILL and only the bound technique's method from retained bytes."""
    requested = sequence(package_refs)
    if not 1 <= len(requested) <= 2 or len(packages) != len(requested):
        raise CatalogError("COMPOSITION_REJECTED")
    matches = [b for b in bindings if b["entity_kind"] == "technique" and b["ref"] == technique_ref]
    if len(matches) != 1:
        raise CatalogError("COMPOSITION_REJECTED")
    binding = matches[0]
    result: list[dict[str, object]] = []
    found_method = False
    total = count = 0
    for reference in requested:
        ref(reference, "package")
        chosen = [p for p in packages if p["package_ref"] == reference]
        if len(chosen) != 1:
            raise CatalogError("COMPOSITION_REJECTED")
        package = chosen[0]
        files: dict[str, bytes] = {}
        listing: list[dict[str, object]] = []
        for raw_file in sequence(package["files"]):
            item = exact(raw_file, {"path", "sha256", "size", "content_b64"})
            path = preparation.path_name(item["path"])
            try:
                raw = base64.b64decode(text(item["content_b64"], 16384), validate=True)
            except (ValueError, binascii.Error):
                raise CatalogError("COMPOSITION_REJECTED") from None
            preparation.document(raw)
            if (
                path in files
                or item["sha256"] != sha256(raw).hexdigest()
                or integer(item["size"], 0, 8192) != len(raw)
            ):
                raise CatalogError("COMPOSITION_REJECTED")
            files[path] = raw
            listing.append({k: item[k] for k in ("path", "sha256", "size")})
            total += len(raw)
            count += 1
        if (
            total > 16384
            or count > 16
            or sha256(canonical(listing)).hexdigest() != mapping(reference)["digest"]
        ):
            raise CatalogError("COMPOSITION_REJECTED")
        if "omnis.yaml" not in files or "SKILL.md" not in files:
            raise CatalogError("COMPOSITION_REJECTED")
        manifest = dto(files["omnis.yaml"], Manifest)
        if (
            package["package_key"] != manifest.package_key
            or package["native_name"] != manifest.native_name
        ):
            raise CatalogError("COMPOSITION_REJECTED")
        preparation.frontmatter(files["SKILL.md"], manifest.native_name)
        selected = ["SKILL.md"]
        if manifest.package_key == binding["package_key"]:
            methods = [t.method_ref for t in manifest.techniques if t.key == binding["key"]]
            if len(methods) != 1 or methods[0] not in files:
                raise CatalogError("COMPOSITION_REJECTED")
            selected.append(methods[0])
            found_method = True
        result.append(
            {
                "section": "skill",
                "package_ref": reference,
                "native_name": manifest.native_name,
                "files": listing,
                "content": [{"path": p, "text": preparation.document(files[p])} for p in selected],
            }
        )
    if not found_method:
        raise CatalogError("COMPOSITION_REJECTED")
    validate_skills(result, requested)
    return result


def validate_skills(skills: Sequence[object], package_refs: object) -> None:
    requested = sequence(package_refs)
    if not 1 <= len(skills) <= 2 or [mapping(s).get("package_ref") for s in skills] != requested:
        raise CatalogError("COMPOSITION_REJECTED")
    names: set[str] = set()
    refs: set[bytes] = set()
    count = total = 0
    for raw in skills:
        skill = exact(raw, {"section", "package_ref", "native_name", "files", "content"})
        reference = ref(skill["package_ref"], "package")
        name = preparation.native_name(skill["native_name"])
        if skill["section"] != "skill" or name in names or canonical(reference) in refs:
            raise CatalogError("COMPOSITION_REJECTED")
        names.add(name)
        refs.add(canonical(reference))
        listing = sequence(skill["files"])
        declared: dict[str, dict[str, object]] = {}
        for file in listing:
            item = exact(file, {"path", "sha256", "size"})
            path = preparation.path_name(item["path"])
            preparation.sha(item["sha256"])
            total += integer(item["size"], 0, 8192)
            count += 1
            if path in declared:
                raise CatalogError("COMPOSITION_REJECTED")
            declared[path] = item
        if (
            list(declared) != sorted(declared, key=lambda p: p.encode())
            or sha256(canonical(listing)).hexdigest() != reference["digest"]
        ):
            raise CatalogError("COMPOSITION_REJECTED")
        seen: set[str] = set()
        for content in sequence(skill["content"]):
            item = exact(content, {"path", "text"})
            path = preparation.path_name(item["path"])
            raw_text = text(item["text"], 8192).encode()
            preparation.document(raw_text)
            if (
                path in seen
                or path not in declared
                or declared[path]["sha256"] != sha256(raw_text).hexdigest()
                or declared[path]["size"] != len(raw_text)
            ):
                raise CatalogError("COMPOSITION_REJECTED")
            if path == "SKILL.md":
                preparation.frontmatter(raw_text, name)
            seen.add(path)
        if "SKILL.md" not in seen or not 1 <= len(seen) <= 2:
            raise CatalogError("COMPOSITION_REJECTED")
    if total > 16384 or count > 16:
        raise CatalogError("COMPOSITION_REJECTED")


def compose(
    bundle: dict[str, object],
    base: dict[str, object],
    role: dict[str, object],
    brief: dict[str, object],
    bound: dict[str, object],
    preparation_ref: dict[str, object],
    skills: list[dict[str, object]],
    *,
    case_input: dict[str, object] | None = None,
    method_execution: bool = False,
) -> dict[str, object]:
    sections = [
        {"section": "base", "record": base},
        {"section": "role", "record": role},
        {"section": "brief", "record": brief},
        {"section": "method", "record": bound},
        *([] if case_input is None else [case_input]),
        *skills,
    ]
    raw = canonical(sections)
    result = records.envelope(
        "prompt-composition",
        {
            "prompt_bundle": bundle,
            "preparation_receipt_ref": preparation_ref,
            "text": raw.decode(),
            "text_digest": sha256(raw).hexdigest(),
            "byte_count": len(raw),
            "token_upper_bound": len(raw),
        },
    )
    validate(result, version=4 if method_execution else None)
    return result


def _authored_text(value: object) -> None:
    if isinstance(value, str):
        if value.startswith("\ufeff") or any(
            (ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) <= 159 for c in value
        ):
            raise CatalogError("COMPOSITION_REJECTED")
    elif isinstance(value, dict):
        for key, child in value.items():
            _authored_text(key)
            _authored_text(child)
    elif isinstance(value, list):
        for child in value:
            _authored_text(child)


def validate(
    value: object, entry: object = None, manifest: object = None, *, version: int | None = None
) -> dict[str, object]:
    result = record(value, "prompt-composition")
    body = exact(
        result["payload"],
        {
            "prompt_bundle",
            "preparation_receipt_ref",
            "text",
            "text_digest",
            "byte_count",
            "token_upper_bound",
        },
    )
    ref(body["preparation_receipt_ref"], "native-preparation-receipt")
    bundle = record(body["prompt_bundle"], "prompt-bundle")
    metadata = exact(
        bundle["payload"],
        {
            "base_ref",
            "role_refs",
            "composer_revision",
            "brief_schema",
            "result_schema",
            "package_refs",
            "max_context_bytes",
            "max_context_tokens",
            "tokenizer_revision",
            "provenance",
        },
    )
    if (
        metadata["composer_revision"]
        not in {
            COMPOSER_REVISION,
            RECORDS_COMPOSER_REVISION,
            CAPTURE_COMPOSER_REVISION,
            LEGACY_COMPOSER_REVISION,
        }
        or metadata["provenance"] != PROVENANCE
        or metadata["tokenizer_revision"] != "utf8-byte-upper-bound-v1"
    ):
        raise CatalogError("COMPOSITION_REJECTED")
    integer(metadata["brief_schema"], 1, 1)
    integer(metadata["result_schema"], 1, 1)
    raw = text(body["text"], 65536).encode()
    sections = sequence(load_json(raw))
    _authored_text(sections)
    if canonical(sections) != raw or body["text_digest"] != sha256(raw).hexdigest():
        raise CatalogError("COMPOSITION_REJECTED")
    if integer(body["byte_count"], 1) != len(raw) or integer(body["token_upper_bound"], 1) != len(
        raw
    ):
        raise CatalogError("COMPOSITION_REJECTED")
    if len(raw) > integer(metadata["max_context_bytes"], 1024, 262144) or len(raw) > integer(
        metadata["max_context_tokens"], 256, 65536
    ):
        raise CatalogError("CONTEXT_OVERFLOW")
    has_input = len(sections) > 4 and mapping(sections[4]).get("section") == "case-input"
    method_execution = version == 4 or (
        manifest is not None
        and mapping(mapping(manifest)["payload"]).get("composition_version") == 4
    )
    if method_execution and not has_input:
        raise CatalogError("COMPOSITION_REJECTED")
    version = (
        4
        if method_execution
        else 1 + integer(mapping(sections[4])["version"], 1, 2)
        if has_input
        else 1
    )
    revisions = {COMPOSER_REVISION}
    if version <= 3:
        revisions.add(RECORDS_COMPOSER_REVISION)
    if version <= 2:
        revisions.add(CAPTURE_COMPOSER_REVISION)
    if version == 1:
        revisions.add(LEGACY_COMPOSER_REVISION)
    if metadata["composer_revision"] not in revisions or not 5 + int(has_input) <= len(
        sections
    ) <= 6 + int(has_input):
        raise CatalogError("COMPOSITION_REJECTED")
    nested = []
    for section, name, kind in zip(
        sections[:4],
        ("base", "role", "brief", "method"),
        ("prompt-content", "prompt-content", "task-brief", "bound-procedure"),
        strict=True,
    ):
        part = exact(section, {"section", "record"})
        if part["section"] != name:
            raise CatalogError("COMPOSITION_REJECTED")
        nested.append(record(part["record"], kind))
    base, role, brief, bound = nested
    brief_body = mapping(contract.validate_brief(brief)["payload"])
    contract.validate_assignment(brief, bound)
    skill_start = 5 if has_input else 4
    validate_skills(sections[skill_start:], metadata["package_refs"])
    if has_input:
        validate_case_section(sections[4], brief, bound, sections[skill_start:])
    elif brief_body["input_artifact_refs"] != []:
        raise CatalogError("COMPOSITION_REJECTED")
    procedure = mapping(mapping(bound["payload"])["resolved_procedure"])
    # Native preflight requires nonempty prose at these method positions.
    # Refuse the same source bytes before persistence, never strip or repair them.
    for field in ("objective", "predicted_signal"):
        text(procedure[field])
    if procedure["cleanup_not_needed_reason"] is not None:
        text(procedure["cleanup_not_needed_reason"])
    for value in sequence(procedure["false_positives"]):
        text(value)
    for group in sequence(procedure["non_applicable_groups"]):
        text(mapping(group)["reason"])
    for requirement in sequence(procedure["method_requirements"]):
        text(mapping(requirement)["description"])
    method_count = sum(
        mapping(content)["path"] != "SKILL.md"
        for skill in sections[skill_start:]
        for content in sequence(mapping(skill)["content"])
    )
    if brief_body["technique_refs"] != [procedure["technique_ref"]] or method_count != 1:
        raise CatalogError("COMPOSITION_REJECTED")
    if (
        base["payload"] != {"text": CONTRACT_BASE_TEXT if method_execution else BASE_TEXT}
        or role["payload"]
        != {
            "role": brief_body["role"],
            "text": CONTRACT_ROLE_TEXT if method_execution else ROLE_TEXT,
        }
        or metadata["base_ref"] != records.reference(base)
        or metadata["role_refs"]
        != [{"role": brief_body["role"], "content_ref": records.reference(role)}]
        or brief_body["prompt_bundle_ref"] != records.reference(bundle)
        or metadata["package_refs"] != brief_body["package_refs"]
    ):
        raise CatalogError("COMPOSITION_REJECTED")
    if entry is not None:
        expected = mapping(entry)
        header = mapping(brief_body["header"])
        if (
            expected["brief_ref"] != records.reference(brief)
            or expected["composition_ref"] != records.reference(result)
            or expected["task_id"] != header["task_id"]
            or expected["attempt_id"] != header["attempt_id"]
            or expected["goal"] != brief_body["objective_summary"]
        ):
            raise CatalogError("COMPOSITION_REJECTED")
        source = mapping(mapping(manifest)["payload"])
        if (
            source.get("composition_version") != version
            or header["run_id"] != source["run_id"]
            or brief_body["execution_selection_ref"] != source["selection_ref"]
        ):
            raise CatalogError("COMPOSITION_REJECTED")
    return result


def validate_case_section(
    value: object, brief: dict[str, object], bound: dict[str, object], skills: list[object]
) -> None:
    from omnis.modules.tasks.contract_case_input import (
        input_contract,
        validate_material,
        validate_slot_values,
    )

    section = mapping(value)
    context = mapping(mapping(section["context"])["payload"])
    validate_material(section, namespace="RUN", owner_id=text(context["owner_id"]))
    body = mapping(brief["payload"])
    header = mapping(body["header"])
    bound_body = mapping(bound["payload"])
    validate_slot_values(bound_body["slot_values"], section)
    name, kind = input_contract(section["version"])
    source = ref(records.reference(mapping(section["input"])), kind)
    if any(
        context[key] != expected
        for key, expected in (
            ("snapshot_ref", header["snapshot_ref"]),
            ("selection_ref", body["execution_selection_ref"]),
            ("mission_ref", header["mission_revision"]),
            ("focus_ref", header["focus_ref"]),
            ("procedure_ref", bound_body["procedure_ref"]),
        )
    ):
        raise CatalogError("COMPOSITION_REJECTED")
    if ref(context["basis_ref"], "managed-run")["id"] != header["run_id"] or body[
        "input_artifact_refs"
    ] != [source]:
        raise CatalogError("COMPOSITION_REJECTED")
    procedure = mapping(bound_body["resolved_procedure"])
    schema = mapping(section["schema"])
    if procedure["input_schema_ref"] != schema["ref"] or procedure["slots"] != []:
        raise CatalogError("COMPOSITION_REJECTED")
    probes = sequence(procedure["probe"])
    expected = [{"name": name, "source_ref": source, "selector": name}]
    if not probes or mapping(probes[0])["input_bindings"] != expected:
        raise CatalogError("COMPOSITION_REJECTED")
    # Bind original schema bytes to the selected package listing, not a reserialization.
    raw = base64.b64decode(text(schema["source_b64"], 16384), validate=True)
    matches = [
        mapping(f)
        for s in skills
        if mapping(mapping(s)["package_ref"])["digest"] == ref(schema["ref"], "schema")["digest"]
        for f in sequence(mapping(s)["files"])
        if mapping(f)["path"] == schema["path"]
    ]
    if (
        len(matches) != 1
        or matches[0]["sha256"] != sha256(raw).hexdigest()
        or matches[0]["size"] != len(raw)
    ):
        raise CatalogError("COMPOSITION_REJECTED")


def stage_payload(manifest: object, graph: list[dict[str, object]]) -> dict[str, object]:
    checked = contract.validate_manifest(manifest)
    if contract.manifest_protocol(checked) == contract.PROTOCOL:
        return {"protocol": contract.PROTOCOL, "manifest": checked}
    local = {text(r["id"]): record(r) for r in graph}
    if len(local) != len(graph):
        raise CatalogError("COMPOSITION_REJECTED")
    compositions = []
    for raw in sequence(mapping(checked["payload"])["entries"]):
        entry = mapping(raw)
        reference = ref(entry["composition_ref"], "prompt-composition")
        composition = local.get(text(reference["id"]))
        if composition is None:
            raise CatalogError("COMPOSITION_REJECTED")
        validated = validate(composition, entry, checked)
        body = mapping(validated["payload"])
        nested = [mapping(s)["record"] for s in sequence(load_json(text(body["text"], 65536)))[:4]]
        sections = sequence(load_json(text(body["text"], 65536)))
        if mapping(checked["payload"])["composition_version"] in (2, 3, 4):
            nested.extend([mapping(sections[4])["context"], mapping(sections[4])["input"]])
        for value in [body["prompt_bundle"], *nested]:
            item = mapping(value)
            if local.get(text(item["id"])) != item:
                raise CatalogError("COMPOSITION_REJECTED")
        compositions.append(validated)
    result: dict[str, object] = {
        "protocol": contract.manifest_protocol(checked),
        "manifest": checked,
        "compositions": compositions,
    }
    if len(canonical(result)) > 32768:
        raise CatalogError("CONTEXT_OVERFLOW")
    return result


def project_model_input(composition: object, approval: "SyntheticApproval") -> dict[str, object]:
    """Separate allowlisted data producer. Never changes the cold composition."""
    from omnis.policy.model_projection import projection_input, reject

    try:
        return projection_input(validate(composition), approval)
    except (CatalogError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise reject() from None
