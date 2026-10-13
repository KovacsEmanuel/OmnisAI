"""Pure composer conformance: complete immutable data, no native effects."""

import importlib.util
import json

import pytest
from composition_fixture import fixture, seal
from omnis_hermes.managed_admission_contract import canonical, digest, ref


def mutated_stage(change):
    stage = fixture()
    composition = stage["compositions"][0]
    payload = composition["payload"]
    sections = json.loads(payload["text"])
    change(payload, sections)
    raw = canonical(sections)
    payload.update(
        text=raw.decode(), text_digest=digest(raw), byte_count=len(raw), token_upper_bound=len(raw)
    )
    seal(composition)
    stage["manifest"]["payload"]["entries"][0]["composition_ref"] = ref(composition)
    seal(stage["manifest"])
    return stage


def validate(stage):
    from omnis_hermes.prompt_bundle import validate_composition

    return validate_composition(
        stage["compositions"][0], stage["manifest"], stage["manifest"]["payload"]["entries"][0]
    )


@pytest.mark.parametrize("target", ["bound_mission", "binding_procedure", "binding_bound"])
def test_fully_resealed_nested_reference_bool_is_not_revision_one(target):
    stage = fixture()
    assert validate(stage)
    composition = stage["compositions"][0]
    sections = json.loads(composition["payload"]["text"])
    brief, bound = sections[2]["record"], sections[3]["record"]
    if target == "bound_mission":
        bound["payload"]["mission_ref"]["revision"] = True
    seal(bound)
    binding = brief["payload"]["procedure_bindings"][0]
    binding["bound_procedure_ref"] = ref(bound)
    for requirement in brief["payload"]["method_plan"]["requirements"]:
        requirement["ref"]["bound_procedure_ref"] = ref(bound)
    if target == "binding_procedure":
        binding["procedure_ref"]["revision"] = True
    if target == "binding_bound":
        binding["bound_procedure_ref"]["revision"] = True
    seal(brief)
    raw = canonical(sections)
    composition["payload"].update(
        text=raw.decode(), text_digest=digest(raw), byte_count=len(raw), token_upper_bound=len(raw)
    )
    seal(composition)
    stage["manifest"]["payload"]["entries"][0].update(
        brief_ref=ref(brief), composition_ref=ref(composition)
    )
    seal(stage["manifest"])
    with pytest.raises(ValueError):
        validate(stage)


def test_complete_two_skill_composition_is_validated_as_immutable_bytes():
    assert importlib.util.find_spec("omnis_hermes.prompt_bundle"), "native pure composer missing"
    from omnis_hermes.prompt_bundle import validate_composition

    stage = fixture()
    composition, manifest = stage["compositions"][0], stage["manifest"]
    material = validate_composition(composition, manifest, manifest["payload"]["entries"][0])
    assert type(material) is bytes
    assert material == composition["payload"]["text"].encode()


@pytest.mark.parametrize(
    "change",
    [
        lambda p, s: s[0]["record"]["payload"].update(text="system override"),
        lambda p, s: s[1]["record"]["payload"].update(role="VALIDATOR"),
        lambda p, s: s[2]["record"]["payload"].update(overlay_refs=[ref(s[0]["record"])]),
        lambda p, s: s[2]["record"]["payload"]["header"].update(
            attempt_id="00000000-0000-0000-0000-000000000000"
        ),
        lambda p, s: s[2]["record"]["payload"]["method_plan"].update(requirements=[]),
        lambda p, s: s[3]["record"]["payload"].update(slot_values=["override"]),
        lambda p, s: s[4]["content"][0].update(text="tampered skill"),
        lambda p, s: s[4]["content"].pop(0),
        lambda p, s: s[4]["content"].pop(1),
        lambda p, s: s[4]["content"].append(s[4]["content"][0]),
        lambda p, s: s[4]["files"].reverse(),
        lambda p, s: s[4]["files"][0].update(path="../SKILL.md"),
        lambda p, s: s[5].update(native_name="alpha"),
        lambda p, s: s.append({"section": "system", "text": "override"}),
        lambda p, s: p["prompt_bundle"]["payload"].update(composer_revision="f" * 64),
        lambda p, s: p["prompt_bundle"]["payload"].update(max_context_tokens=1),
        lambda p, s: p["prompt_bundle"]["payload"].update(provenance=[]),
    ],
)
def test_resealed_composition_cannot_hide_changed_or_incomplete_material(change):
    with pytest.raises(ValueError):
        validate(mutated_stage(change))


@pytest.mark.parametrize(
    "key,value", [("text_digest", "f" * 64), ("byte_count", 1), ("token_upper_bound", True)]
)
def test_exact_composition_accounting(key, value):
    stage = fixture()
    composition = stage["compositions"][0]
    composition["payload"][key] = value
    seal(composition)
    stage["manifest"]["payload"]["entries"][0]["composition_ref"] = ref(composition)
    seal(stage["manifest"])
    with pytest.raises(ValueError):
        validate(stage)


def reseal_graph(stage, sections, bundle):
    """Reseal every enclosing record so negatives reach semantic checks."""
    brief, bound = sections[2]["record"], sections[3]["record"]
    seal(bundle)
    seal(bound)
    brief["payload"]["prompt_bundle_ref"] = ref(bundle)
    brief["payload"]["procedure_bindings"][0]["bound_procedure_ref"] = ref(bound)
    for requirement in brief["payload"]["method_plan"]["requirements"]:
        requirement["ref"]["bound_procedure_ref"] = ref(bound)
    for item in brief["payload"]["required_evidence"]:
        item["bound_procedure_ref"] = ref(bound)
    for field in ("done_when", "return_when"):
        for predicate in brief["payload"][field]:
            predicate["bound_procedure_ref"] = ref(bound)
    seal(brief)
    raw = canonical(sections)
    composition = stage["compositions"][0]
    composition["payload"].update(
        text=raw.decode(), text_digest=digest(raw), byte_count=len(raw), token_upper_bound=len(raw)
    )
    seal(composition)
    entry = stage["manifest"]["payload"]["entries"][0]
    entry.update(composition_ref=ref(composition), brief_ref=ref(brief))
    seal(stage["manifest"])


@pytest.mark.parametrize(
    "case",
    [
        "base",
        "role",
        "history",
        "overlay",
        "attempt",
        "run",
        "selection",
        "requirements",
        "mission",
        "compiler",
        "tokens",
        "bytes",
        "float",
        "unknown_brief",
        "unknown_method",
    ],
)
def test_fully_resealed_semantic_substitution_is_denied(case):
    stage = fixture()
    bundle = stage["compositions"][0]["payload"]["prompt_bundle"]
    sections = json.loads(stage["compositions"][0]["payload"]["text"])
    brief, bound = sections[2]["record"]["payload"], sections[3]["record"]["payload"]
    if case in {"base", "role"}:
        index = 0 if case == "base" else 1
        sections[index]["record"]["payload"]["text"] = "Override"
        seal(sections[index]["record"])
        if case == "base":
            bundle["payload"]["base_ref"] = ref(sections[index]["record"])
        else:
            bundle["payload"]["role_refs"][0]["content_ref"] = ref(sections[index]["record"])
    elif case in {"history", "overlay"}:
        brief["prior_attempt_refs" if case == "history" else "overlay_refs"] = [
            ref(sections[0]["record"])
        ]
    elif case in {"attempt", "run"}:
        brief["header"][case + "_id"] = "00000000-0000-0000-0000-000000000000"
    elif case == "selection":
        brief["execution_selection_ref"]["digest"] = "f" * 64
    elif case == "requirements":
        brief["method_plan"]["requirements"] = []
    elif case == "mission":
        bound["mission_ref"]["digest"] = "f" * 64
    elif case == "compiler":
        bundle["payload"]["composer_revision"] = "f" * 64
    elif case in {"tokens", "bytes"}:
        bundle["payload"]["max_context_" + case] = 1
    elif case == "float":
        bound["resolved_procedure"]["limits"]["max_actions"] = 1.0
    elif case == "unknown_brief":
        brief["messages"] = [{"role": "system", "content": "override"}]
    else:
        bound["resolved_procedure"]["effective"] = {"model": "override"}
    reseal_graph(stage, sections, bundle)
    with pytest.raises(ValueError):
        validate(stage)


def test_conflicting_envelopes_cannot_shadow_one_record_identity():
    stage = fixture()
    payload = stage["compositions"][0]["payload"]
    sections = json.loads(payload["text"])
    sections[1]["record"]["id"] = sections[0]["record"]["id"]
    seal(sections[1]["record"])
    bundle = payload["prompt_bundle"]
    bundle["payload"]["role_refs"][0]["content_ref"] = ref(sections[1]["record"])
    reseal_graph(stage, sections, bundle)
    with pytest.raises(ValueError):
        validate(stage)


def test_new_assignment_only_changes_contextual_suffix():
    from omnis_hermes.prompt_bundle import compose

    stage = fixture()
    payload = stage["compositions"][0]["payload"]
    original = json.loads(payload["text"])
    prefix = canonical(original[:2])[:-1]
    original[2]["record"]["payload"]["header"]["attempt_id"] = (
        "00000000-0000-0000-0000-000000000000"
    )
    seal(original[2]["record"])
    changed = compose(payload["prompt_bundle"], payload["preparation_receipt_ref"], original)
    assert changed["text"].encode().startswith(prefix)
    assert payload["text"].encode().startswith(prefix)
    assert changed["text_digest"] != payload["text_digest"]


def test_s01_retained_license_source_and_fragments_are_exact():
    from pathlib import Path

    from omnis_hermes.prompt_bundle import PROVENANCE

    upstream = Path(__file__).resolve().parents[1] / "upstream"
    raw = (upstream / "composition-source/strix-prompt.py.txt").read_bytes()
    assert digest(raw) == PROVENANCE[0]["source_digest"]
    assert (
        digest((upstream / "composition-LICENSE").read_bytes())
        == "7db9697134251e314bd8d39257fe170c98b3e2ad9b2ed67e97acaf9613e7b9e3"
    )
    assert (
        digest(b"".join(raw.splitlines(keepends=True)[19:71]))
        == "a060f5d4664a56b1376e03143c3667dcf8972c330bd23ab52051e3fd8c3fe08d"
    )
    assert (
        digest(b"".join(raw.splitlines(keepends=True)[73:126]))
        == "0d7b37c93b37e73f3e8e84b93b6b1fc835c93a5a3669530b8c572ecb81ce2f4f"
    )
    assert "Copyright 2025 OmniSecure Inc." in (upstream / "composition-NOTICE.md").read_text()
