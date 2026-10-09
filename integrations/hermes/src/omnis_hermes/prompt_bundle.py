"""S01 ordered prompt composition adapted to inert canonical data.

No template evaluation, foreign runtime, model, tool or catalog discovery.
See upstream/composition-NOTICE.md for exact source and modifications.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import cast

from .managed_admission_contract import envelope, ref
from .native_preparation_contract import (
    bounded,
    canonical,
    digest,
    frontmatter,
    loads,
    obj,
    raw_text,
    reference,
    sha,
    text,
    uuid,
)

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
ROLES = {"RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH"}
BRIEF_FIELDS: set[str] = set(
    "header prompt_bundle_ref execution_selection_ref assessment_mode objective_summary non_goals role hypothesis operation_refs priority_reason done_when return_when context contradiction_refs prior_attempt_refs package_refs technique_refs procedure_refs procedure_bindings method_plan review_request criterion_bindings overlay_refs input_artifact_refs identities allowed_capability_ids limits deadline validation_reserve stop_conditions required_evidence".split()
)
LIMITS = {
    "max_attempts": 10,
    "max_actions": 300,
    "deadline_seconds": 1200,
    "max_output_bytes": 1048576,
    "max_fanout": 2,
}
PROCEDURE_FIELDS: set[str] = set(
    "schema_version key technique_ref verification_kind non_applicable_groups objective applicability_predicate_ids technologies input_schema_ref output_schema_ref preconditions method_requirements identity_requirements business_rule_refs requested_capabilities requested_effect_ceiling predicted_signal baseline probe control evidence_requirements oracle_ref slots false_positives invalidation_predicate_ids limits stop_reason_ids cleanup cleanup_not_needed_reason handoff_schema_ref outcomes".split()
)


def reject() -> ValueError:
    return ValueError("Invalid prompt composition")


def mapping(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise reject()
    return cast(dict[str, object], value)


def sequence(value: object, minimum: int = 0, maximum: int = 128) -> list[object]:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise reject()
    return cast(list[object], value)


def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise reject()
    return value


def authored(value: object) -> None:
    """Control-free authored data; only original LF/TAB are permitted."""
    if type(value) is str:
        raw_text(value.encode("utf-8"))
    elif type(value) is dict:
        for key, child in value.items():
            authored(key)
            authored(child)
    elif type(value) is list:
        for child in value:
            authored(child)


def key(value: object) -> str:
    result = text(value)
    if re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", result) is None:
        raise reject()
    return result


def prose(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 4096:
        raise reject()
    raw_text(value.encode("utf-8"))
    return value


def limits(value: object) -> dict[str, object]:
    result = obj(value, set(LIMITS))
    for name, maximum in LIMITS.items():
        integer(result[name], 1, maximum)
    return result


def refs(value: object, kind: str, minimum: int = 1, maximum: int = 128) -> list[object]:
    items = sequence(value, minimum, maximum)
    identities = set()
    for item in items:
        checked = reference(item, kind)
        if checked["id"] in identities:
            raise reject()
        identities.add(checked["id"])
    return items


def composer_revision() -> str:
    """Attest installed source, not an impossible self-referential literal."""
    return digest(Path(__file__).read_bytes())


def compose(
    prompt_bundle: object, preparation_receipt_ref: object, sections: object
) -> dict[str, object]:
    bounded(sections)
    authored(sections)
    raw = canonical(sections)
    result = {
        "prompt_bundle": envelope(prompt_bundle, "prompt-bundle"),
        "preparation_receipt_ref": reference(preparation_receipt_ref, "native-preparation-receipt"),
        "text": raw.decode("utf-8"),
        "text_digest": digest(raw),
        "byte_count": len(raw),
        "token_upper_bound": len(raw),
    }
    _material(result)
    return result


def _procedure(value: object) -> dict[str, object]:
    p = obj(value, PROCEDURE_FIELDS)
    integer(p["schema_version"], 1, 1)
    key(p["key"])
    if (
        p["verification_kind"] != "CONTRACT"
        or p["requested_effect_ceiling"] != "PURE"
        or p["oracle_ref"] is not None
    ):
        raise reject()
    for field in (
        "applicability_predicate_ids",
        "preconditions",
        "identity_requirements",
        "business_rule_refs",
        "requested_capabilities",
        "evidence_requirements",
        "slots",
        "invalidation_predicate_ids",
        "stop_reason_ids",
    ):
        if p[field] != []:
            raise reject()
    for field in ("objective", "predicted_signal"):
        prose(p[field])
    if p["cleanup_not_needed_reason"] is not None:
        prose(p["cleanup_not_needed_reason"])
    sequence(p["technologies"])
    for item in sequence(p["false_positives"]):
        prose(item)
    for item in sequence(p["non_applicable_groups"]):
        row = obj(item, {"group", "reason"})
        if row["group"] not in ("BASELINE", "CONTROL"):
            raise reject()
        prose(row["reason"])
    outcomes = sequence(p["outcomes"], 1)
    if "BLOCKED" not in outcomes or any(
        item
        not in (
            "SUCCEEDED",
            "INCONCLUSIVE",
            "BLOCKED",
            "FAILED",
            "CANCELLED",
            "NEEDS_RECONCILIATION",
        )
        for item in outcomes
    ):
        raise reject()
    reference(p["technique_ref"], "technique")
    for field in ("input_schema_ref", "output_schema_ref", "handoff_schema_ref"):
        reference(p[field], "schema")
    limits(p["limits"])
    step_ids = set()
    for group in ("baseline", "probe", "control", "cleanup"):
        for item in sequence(p[group]):
            step = obj(
                item,
                set(
                    "id action_definition_ref tool_ref parameter_schema_ref parameters input_bindings output_schema_ref".split()
                ),
            )
            step_id = key(step["id"])
            if step_id in step_ids:
                raise reject()
            step_ids.add(step_id)
            reference(step["action_definition_ref"], "action_definition")
            if step["tool_ref"] is not None:
                reference(step["tool_ref"], "tool")
            reference(step["parameter_schema_ref"], "schema")
            reference(step["output_schema_ref"], "schema")
            mapping(step["parameters"])
            binding_names = set()
            for binding in sequence(step["input_bindings"]):
                b = obj(binding, {"name", "source_ref", "selector"})
                name = key(b["name"])
                if name in binding_names:
                    raise reject()
                binding_names.add(name)
                if b["selector"] is not None:
                    key(b["selector"])
                source = mapping(b["source_ref"])
                if source.get("kind") == "STEP_OUTPUT":
                    obj(source, {"kind", "step_id", "output_name"})
                    key(source["step_id"])
                    key(source["output_name"])
                else:
                    reference(source)
    seen = set()
    for item in sequence(p["method_requirements"], 1):
        requirement = obj(
            item,
            set(
                "key description required applies_if step_ids artifact_schema_refs evidence_kinds".split()
            ),
        )
        name = key(requirement["key"])
        if (
            name in seen
            or type(requirement["required"]) is not bool
            or requirement["applies_if"] != []
            or requirement["evidence_kinds"] != []
        ):
            raise reject()
        seen.add(name)
        prose(requirement["description"])
        for required_step in sequence(requirement["step_ids"]):
            if key(required_step) not in step_ids:
                raise reject()
        refs(requirement["artifact_schema_refs"], "schema", 0)
    return p


def _brief(
    value: object, method: dict[str, object], bundle: dict[str, object]
) -> dict[str, object]:
    body = obj(value, BRIEF_FIELDS)
    role = text(body["role"])
    if (
        role not in ROLES
        or body["assessment_mode"] != "FULL_ASSESSMENT"
        or body["review_request"] is not None
    ):
        raise reject()
    for field in (
        "operation_refs",
        "done_when",
        "return_when",
        "contradiction_refs",
        "prior_attempt_refs",
        "criterion_bindings",
        "overlay_refs",
        "input_artifact_refs",
        "identities",
        "allowed_capability_ids",
        "stop_conditions",
        "required_evidence",
    ):
        if body[field] != []:
            raise reject()
    for field in ("objective_summary", "hypothesis", "priority_reason"):
        prose(body[field])
    if "SUPPORT" not in prose(body["priority_reason"]):
        raise reject()
    for item in sequence(body["non_goals"]):
        prose(item)
    if reference(body["prompt_bundle_ref"], "prompt-bundle") != ref(bundle):
        raise reject()
    reference(body["execution_selection_ref"], "execution-selection")
    refs(body["package_refs"], "package", 1, 2)
    refs(body["technique_refs"], "technique")
    refs(body["procedure_refs"], "procedure")
    header = obj(
        body["header"],
        set(
            "schema_version run_id task_id attempt_id snapshot_ref mission_revision focus_ref through_cursor brief_revision result_schema_ref".split()
        ),
    )
    integer(header["schema_version"], 1, 1)
    integer(header["brief_revision"], 1, 1)
    for field in ("run_id", "task_id", "attempt_id", "through_cursor"):
        uuid(header[field])
    for field, kind in (
        ("snapshot_ref", "run-snapshot"),
        ("mission_revision", "mission"),
        ("focus_ref", "focus"),
        ("result_schema_ref", "schema"),
    ):
        reference(header[field], kind)
    contexts = sequence(body["context"], 2, 2)
    for item, expected in zip(
        contexts, (header["mission_revision"], header["focus_ref"]), strict=True
    ):
        context = obj(item, {"ref", "epistemic_state", "summary", "mandatory"})
        if (
            reference(context["ref"]) != expected
            or context["epistemic_state"] != "OBSERVED"
            or context["mandatory"] is not True
        ):
            raise reject()
        prose(context["summary"])
    deadline = text(body["deadline"], 64)
    if not deadline.endswith("Z"):
        raise reject()
    datetime.fromisoformat(deadline)
    reserve = obj(body["validation_reserve"], {"actions", "seconds"})
    integer(reserve["actions"], 0, 0)
    integer(reserve["seconds"], 0, 0)
    bound = obj(
        method["payload"], {"procedure_ref", "slot_values", "resolved_procedure", "mission_ref"}
    )
    reference(bound["procedure_ref"], "procedure")
    reference(bound["mission_ref"], "mission")
    if bound["mission_ref"] != header["mission_revision"] or bound["slot_values"] != []:
        raise reject()
    p = _procedure(bound["resolved_procedure"])
    expected_binding = {
        "procedure_ref": bound["procedure_ref"],
        "slot_values": [],
        "bound_procedure_ref": ref(method),
    }
    bindings = sequence(body["procedure_bindings"], 1, 1)
    binding = obj(bindings[0], {"procedure_ref", "slot_values", "bound_procedure_ref"})
    reference(binding["procedure_ref"], "procedure")
    reference(binding["bound_procedure_ref"], "bound-procedure")
    if (
        canonical(bindings) != canonical([expected_binding])
        or body["procedure_refs"] != [bound["procedure_ref"]]
        or body["technique_refs"] != [p["technique_ref"]]
    ):
        raise reject()
    expected_requirements = [
        {
            "ref": {"bound_procedure_ref": ref(method), "requirement_key": mapping(r)["key"]},
            "applicability": "APPLIES",
            "applicability_basis_refs": [],
            "required": mapping(r)["required"],
        }
        for r in sequence(p["method_requirements"], 1)
    ]
    plan = obj(body["method_plan"], {"requirements"})
    if canonical(plan["requirements"]) != canonical(expected_requirements):
        raise reject()
    chosen_limits, method_limits = limits(body["limits"]), limits(p["limits"])
    if any(cast(int, chosen_limits[k]) > cast(int, method_limits[k]) for k in LIMITS):
        raise reject()
    return body


def _path(value: object) -> str:
    path = text(value, 256)
    parts = path.split("/")
    if any(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", p) is None for p in parts) or (
        len(parts) > 1
        and (
            parts[0] not in {"references", "templates", "assets", "scripts"} or "SKILL.md" in parts
        )
    ):
        raise reject()
    return path


def _skills(values: list[object], packages: object) -> None:
    refs(packages, "package", 1, 2)
    if len(values) != len(sequence(packages)):
        raise reject()
    names = set()
    total_bytes = total_files = methods = 0
    for item, package_ref in zip(values, sequence(packages), strict=True):
        skill = obj(item, {"section", "package_ref", "native_name", "files", "content"})
        if skill["section"] != "skill" or reference(skill["package_ref"], "package") != package_ref:
            raise reject()
        name = text(skill["native_name"], 64)
        if re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) is None or name in names:
            raise reject()
        names.add(name)
        files = sequence(skill["files"], 2, 16)
        paths = []
        declared = {}
        for item in files:
            file = obj(item, {"path", "sha256", "size"})
            path = _path(file["path"])
            size = integer(file["size"], 0, 8192)
            sha(file["sha256"])
            if path in declared:
                raise reject()
            declared[path] = file
            paths.append(path)
            total_bytes += size
            total_files += 1
        if (
            paths != sorted(paths, key=lambda p: p.encode("utf-8"))
            or not {"SKILL.md", "omnis.yaml"} <= set(paths)
            or digest(canonical(files)) != mapping(package_ref)["digest"]
        ):
            raise reject()
        included = set()
        for item in sequence(skill["content"], 1, 16):
            content = obj(item, {"path", "text"})
            path = _path(content["path"])
            if path in included or path not in declared or type(content["text"]) is not str:
                raise reject()
            raw = content["text"].encode("utf-8")
            raw_text(raw)
            if declared[path]["sha256"] != digest(raw) or declared[path]["size"] != len(raw):
                raise reject()
            if path == "SKILL.md":
                frontmatter(raw, name)
            else:
                # Exact selected technique.method_ref ownership is API-authoritative.
                # That mapping is not transmitted here; never invent a catalog read.
                if path == "omnis.yaml":
                    raise reject()
                methods += 1
            included.add(path)
        if "SKILL.md" not in included:
            raise reject()
    if not methods or total_files > 16 or total_bytes > 16384:
        raise reject()


def _material(payload: dict[str, object]) -> tuple[bytes, dict[str, object], dict[str, object]]:
    bounded(payload)
    authored(payload)
    bundle = envelope(payload["prompt_bundle"], "prompt-bundle")
    reference(payload["preparation_receipt_ref"], "native-preparation-receipt")
    b = obj(
        bundle["payload"],
        set(
            "base_ref role_refs composer_revision brief_schema result_schema package_refs max_context_bytes max_context_tokens tokenizer_revision provenance".split()
        ),
    )
    integer(b["brief_schema"], 1, 1)
    integer(b["result_schema"], 1, 1)
    if (
        b["composer_revision"] != composer_revision()
        or b["tokenizer_revision"] != "utf8-byte-upper-bound-v1"
        or b["provenance"] != PROVENANCE
    ):
        raise reject()
    maximum = min(
        integer(b["max_context_bytes"], 1, 65536), integer(b["max_context_tokens"], 1, 65536), 32768
    )
    if type(payload["text"]) is not str:
        raise reject()
    raw = payload["text"].encode("utf-8")
    sections = sequence(loads(raw, maximum), 5, 6)
    if (
        canonical(sections) != raw
        or sha(payload["text_digest"]) != digest(raw)
        or integer(payload["byte_count"], 1, maximum) != len(raw)
        or integer(payload["token_upper_bound"], 1, maximum) != len(raw)
    ):
        raise reject()
    authored(sections)
    checked = []
    for item, label, kind in zip(
        sections[:4],
        ("base", "role", "brief", "method"),
        ("prompt-content", "prompt-content", "task-brief", "bound-procedure"),
        strict=True,
    ):
        section = obj(item, {"section", "record"})
        if section["section"] != label:
            raise reject()
        checked.append(envelope(section["record"], kind))
    if len({record["id"] for record in [bundle, *checked]}) != len(checked) + 1:
        raise reject()
    base, role, brief, method = checked
    if obj(base["payload"], {"text"}) != {"text": BASE_TEXT} or reference(
        b["base_ref"], "prompt-content"
    ) != ref(base):
        raise reject()
    body = _brief(brief["payload"], method, bundle)
    if obj(role["payload"], {"role", "text"}) != {"role": body["role"], "text": ROLE_TEXT}:
        raise reject()
    roles = {}
    for item in sequence(b["role_refs"], 1, 4):
        row = obj(item, {"role", "content_ref"})
        name = text(row["role"])
        if name not in ROLES or name in roles:
            raise reject()
        roles[name] = reference(row["content_ref"], "prompt-content")
    if roles.get(cast(str, body["role"])) != ref(role) or b["package_refs"] != body["package_refs"]:
        raise reject()
    _skills(sections[4:], b["package_refs"])
    return raw, brief, body


def validate_composition(value: object, manifest: object, entry: object) -> bytes:
    composition = envelope(value, "prompt-composition")
    payload = obj(
        composition["payload"],
        {
            "prompt_bundle",
            "preparation_receipt_ref",
            "text",
            "text_digest",
            "byte_count",
            "token_upper_bound",
        },
    )
    raw, brief, body = _material(payload)
    launch = mapping(envelope(manifest, "launch-manifest")["payload"])
    e = obj(entry, {"batch_index", "task_id", "attempt_id", "brief_ref", "composition_ref", "goal"})
    header = mapping(body["header"])
    if (
        ref(composition) != reference(e["composition_ref"], "prompt-composition")
        or ref(brief) != reference(e["brief_ref"], "task-brief")
        or any(e[k] != header[k] for k in ("task_id", "attempt_id"))
        or launch.get("run_id") != header["run_id"]
        or launch.get("selection_ref") != body["execution_selection_ref"]
        or e["goal"] != body["objective_summary"]
    ):
        raise reject()
    return raw
