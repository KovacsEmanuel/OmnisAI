"""Projection product denials; SQL doubles are NOT persistent/native QA."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_projection import ModelProjections
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks import managed_composition, managed_store
from omnis.modules.tasks.managed_contract import sequence
from omnis.policy.model_projection import POLICY_DIGEST, SyntheticApproval
from test_model_projection import source_graph, text_digests

MARKER = "SYNTHETIC_FORBIDDEN_SENTINEL_B06C"


def mapping(value: object) -> dict[str, object]:
    # Product mapping() deliberately returns a copy. Adversarial fixture edits
    # must instead modify the exact retained tree being serialized below.
    assert type(value) is dict
    return cast(dict[str, object], value)


def approval_for(
    owner: str, launch: dict[str, object], composition: dict[str, object]
) -> SyntheticApproval:
    return SyntheticApproval(
        owner,
        str(mapping(launch["payload"])["run_id"]),
        canonical(records.reference(composition)),
        text_digests(composition),
        (),
    )


@pytest.fixture
def unit_projection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Actual service/producer; only SQL/unchanged catalog resolver doubled."""
    owner, graph, launch, composition = source_graph(tmp_path, "/" + MARKER + "?q=" + MARKER)
    approval = approval_for(owner, launch, composition)
    binding = next(r for r in graph if r["kind"] == "runtime-binding")
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    monkeypatch.setattr(managed, "_verify_graph", AsyncMock())
    monkeypatch.setattr(
        managed_store,
        "state",
        AsyncMock(
            return_value={
                "run_id": approval.run_id,
                "binding_id": binding["id"],
            }
        ),
    )
    monkeypatch.setattr(managed_store, "graph", AsyncMock(return_value=graph))

    async def get(_: object, o: str, r: str, pin: object) -> dict[str, object]:
        if (o, r) != (owner, approval.run_id):
            raise CatalogError("REF_UNAVAILABLE")
        matches = [v for v in graph if records.reference(v) == pin]
        if len(matches) != 1:
            raise CatalogError("REF_MISMATCH")
        return matches[0]

    monkeypatch.setattr(managed_store, "get", get)
    result = asyncio.run(
        ModelProjections(managed).prepare(
            AsyncMock(spec=AsyncConnection),
            owner,
            records.reference(launch),
            records.reference(binding),
            records.reference(composition),
            approval,
        )
    )
    assert MARKER.encode() not in canonical(result)
    return result


def adapter(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    import importlib

    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    return importlib.import_module("omnis_hermes.model_projection")


@pytest.mark.parametrize(
    "field", ["objective_summary", "hypothesis", "priority_reason", "non_goals", "context"]
)
def test_source_unknown_sensitive_prose_cannot_self_classify(
    tmp_path: Path, field: str, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    owner, _, launch, original = source_graph(tmp_path)
    body = deepcopy(mapping(original["payload"]))
    sections = [mapping(s) for s in sequence(load_json(str(body["text"])))]
    brief = deepcopy(mapping(mapping(sections[2]["record"])["payload"]))
    if field == "non_goals":
        brief[field] = [MARKER]
    elif field == "context":
        mapping(sequence(brief["context"])[0])["summary"] = MARKER
    elif field == "priority_reason":
        brief[field] = "SUPPORT " + MARKER
    else:
        brief[field] = MARKER
    sections[2]["record"] = records.envelope("task-brief", brief)
    raw = canonical(sections)
    body.update(
        text=raw.decode(),
        text_digest=sha256(raw).hexdigest(),
        byte_count=len(raw),
        token_upper_bound=len(raw),
    )
    changed = records.envelope("prompt-composition", body)
    approval = replace(
        approval_for(owner, launch, original), composition_ref=canonical(records.reference(changed))
    )
    # Source itself remains a valid cold composition. The projection refuses at
    # classification, not at an invalid QA-driver assignment/frame.
    managed_composition.validate(changed)
    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED") as error:
        managed_composition.project_model_input(changed, approval)
    assert str(error.value) == "MODEL_PROJECTION_REJECTED"
    output = capsys.readouterr()
    assert MARKER not in output.out + output.err + caplog.text


@pytest.mark.parametrize("surface", ["base", "role", "skill", "method", "context", "brief"])
def test_known_secret_is_denied_across_all_emitted_text_surfaces(
    tmp_path: Path, surface: str
) -> None:
    owner, _, launch, composition = source_graph(tmp_path)
    approval = approval_for(owner, launch, composition)
    positive = managed_composition.project_model_input(composition, approval)
    messages = [mapping(v) for v in sequence(positive["messages"])]
    system, user = [mapping(load_json(str(v["content"]))) for v in messages]
    instructions = [mapping(v) for v in sequence(system["instructions"])]
    values = {
        "base": instructions[0]["text"],
        "role": instructions[1]["text"],
        "skill": instructions[2]["text"],
        "method": mapping(system["method"])["objective"],
        "context": mapping(sequence(user["context"])[0])["summary"],
        "brief": user["objective_summary"],
    }
    secret = str(values[surface])
    assert secret
    denied = replace(approval, known_secrets=(secret,))
    assert secret not in repr(denied)
    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED"):
        managed_composition.project_model_input(composition, denied)


@pytest.mark.parametrize("pin", ["owner", "run", "id", "revision", "digest", "kind"])
def test_source_scope_and_stale_ref_are_denied(tmp_path: Path, pin: str) -> None:
    from uuid import uuid4

    owner, _, launch, composition = source_graph(tmp_path)
    approval = approval_for(owner, launch, composition)
    changed = dict(records.reference(composition))
    if pin == "owner":
        # Input context is real; the caller cannot borrow it across owners.
        approval = replace(approval, owner_id=str(uuid4()))
    elif pin == "run":
        approval = replace(approval, run_id=str(uuid4()))
    else:
        changed[pin] = {
            "id": str(uuid4()),
            "revision": 2,
            "digest": "0" * 64,
            "kind": "task-brief",
        }[pin]
        if pin == "kind":
            with pytest.raises(CatalogError):
                replace(approval, composition_ref=canonical(changed))
            return
        approval = replace(approval, composition_ref=canonical(changed))
    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED"):
        managed_composition.project_model_input(composition, approval)


@pytest.mark.parametrize(
    "attack",
    [
        "extra_body",
        "headers",
        "cookies",
        "storageState",
        "stack_trace",
        "evidence_bytes",
        "screenshot",
        "option_labels",
        "tool_results",
        "error",
        "log",
        "history",
    ],
)
def test_whole_serialized_input_refuses_unknown_marker_channels(
    unit_projection: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    import importlib

    module = adapter(monkeypatch)
    assert isinstance(module, type(importlib))
    body = mapping(unit_projection["payload"])
    pins = {
        "projection_ref": records.reference(unit_projection),
        "owner_id": body["owner_id"],
        "run_id": body["run_id"],
        "binding_ref": body["runtime_binding_ref"],
        "policy_digest": POLICY_DIGEST,
    }
    good = module.serialize_model_input(unit_projection, **pins)
    assert module.validate_serialized_input(good, unit_projection, **pins) == good
    malicious = mapping(load_json(good))
    malicious[attack] = MARKER
    with pytest.raises(ValueError, match="Invalid model projection") as error:
        module.validate_serialized_input(canonical(malicious), unit_projection, **pins)
    assert str(error.value) == "Invalid model projection"
    output = capsys.readouterr()
    assert MARKER not in output.out + output.err + caplog.text


@pytest.mark.parametrize(
    "attack",
    [
        "top-extra",
        "input-extra",
        "instruction-extra",
        "method-extra",
        "context-extra",
        "header-extra",
        "record-extra",
        "unredacted-path",
        "foreign-snapshot",
        "tools",
        "float",
        "duplicate",
        "newline",
        "oversized",
    ],
)
def test_serializer_checks_projection_shape_and_canonical_bytes_even_if_resigned(
    unit_projection: dict[str, object], monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    import importlib

    module = adapter(monkeypatch)
    assert isinstance(module, type(importlib))
    body = deepcopy(mapping(unit_projection["payload"]))
    carrier = mapping(body["model_input"])
    messages = [mapping(v) for v in sequence(carrier["messages"])]
    system = mapping(load_json(str(messages[0]["content"])))
    user = mapping(load_json(str(messages[1]["content"])))
    if attack == "top-extra":
        body["body"] = MARKER
    elif attack == "input-extra":
        carrier["body"] = MARKER
    elif attack == "instruction-extra":
        mapping(sequence(system["instructions"])[0])["body"] = MARKER
    elif attack == "method-extra":
        mapping(system["method"])["parameters"] = {"body": MARKER}
    elif attack == "context-extra":
        mapping(sequence(user["context"])[0])["body"] = MARKER
    elif attack == "header-extra":
        mapping(user["header"])["native_turn_id"] = MARKER
    elif attack == "record-extra":
        mapping(sequence(user["records"])[0])["query_values"] = MARKER
    elif attack == "unredacted-path":
        mapping(sequence(user["records"])[0])["path"] = "/" + MARKER
    elif attack == "foreign-snapshot":
        mapping(mapping(user["header"])["snapshot_ref"])["digest"] = "0" * 64
    elif attack == "tools":
        carrier["tools"] = [{"description": MARKER}]
    messages[0]["content"], messages[1]["content"] = (
        canonical(system).decode(),
        canonical(user).decode(),
    )
    body["projection_digest"] = sha256(canonical(carrier)).hexdigest()
    value = records.envelope("model-projection", body)
    pins = {
        "projection_ref": records.reference(value),
        "owner_id": body["owner_id"],
        "run_id": body["run_id"],
        "binding_ref": body["runtime_binding_ref"],
        "policy_digest": POLICY_DIGEST,
    }
    if attack in {"float", "duplicate", "newline", "oversized"}:
        good = module.serialize_model_input(value, **pins)
        altered = {
            "float": b'{"messages":1.5,"tools":[]}',
            "duplicate": b'{"tools":[],"tools":[]}',
            "newline": good + b"\n",
            "oversized": b" " * 32769,
        }[attack]
        with pytest.raises(ValueError, match="Invalid model projection"):
            module.validate_serialized_input(altered, value, **pins)
    else:
        with pytest.raises(ValueError, match="Invalid model projection"):
            module.serialize_model_input(value, **pins)


@pytest.mark.parametrize(
    "location",
    ["snapshot_ref", "mission_revision", "focus_ref", "context-0", "context-1", "context-2"],
)
def test_nested_ref_requires_literal_integer_revision(
    unit_projection: dict[str, object], monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    module = adapter(monkeypatch)
    body = deepcopy(mapping(unit_projection["payload"]))

    def pins(value: dict[str, object]) -> dict[str, object]:
        payload = mapping(value["payload"])
        return {
            "projection_ref": records.reference(value),
            "owner_id": payload["owner_id"],
            "run_id": payload["run_id"],
            "binding_ref": payload["runtime_binding_ref"],
            "policy_digest": POLICY_DIGEST,
        }

    positive = module.serialize_model_input(unit_projection, **pins(unit_projection))
    assert (
        module.validate_serialized_input(positive, unit_projection, **pins(unit_projection))
        == positive
    )
    carrier = mapping(body["model_input"])
    message = mapping(sequence(carrier["messages"])[1])
    user = mapping(load_json(str(message["content"])))
    if location.startswith("context-"):
        target = mapping(mapping(sequence(user["context"])[int(location[-1])])["ref"])
    else:
        target = mapping(mapping(user["header"])[location])
    assert type(target["revision"]) is int and target["revision"] == 1
    target["revision"] = True
    message["content"] = canonical(user).decode()
    body["projection_digest"] = sha256(canonical(carrier)).hexdigest()
    resigned = records.envelope("model-projection", body)
    # Mutate exact serialized retained bytes and re-sign, so this tests nested
    # schema enforcement independently of a stale outer projection digest.
    invalid_bytes = canonical(carrier)
    with pytest.raises(ValueError, match="Invalid model projection"):
        module.serialize_model_input(resigned, **pins(resigned))
    with pytest.raises(ValueError, match="Invalid model projection"):
        module.validate_serialized_input(invalid_bytes, resigned, **pins(resigned))
