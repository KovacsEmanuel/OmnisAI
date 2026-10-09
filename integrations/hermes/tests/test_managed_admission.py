"""Wire/source-unit evidence only; no fixture is promoted to native PASS."""

import copy
import importlib.util
from uuid import uuid4

import pytest
from omnis_hermes.native_preparation_contract import canonical, digest


def record(kind, payload):
    result = dict(schema_version=1, kind=kind, id=str(uuid4()), revision=1, payload=payload)
    return {**result, "digest": digest(canonical(result))}


def ref(record):
    return {k: record[k] for k in ("kind", "id", "revision", "digest")}


def manifest():
    return record(
        "launch-manifest",
        {
            "run_id": str(uuid4()),
            "selection_ref": ref(record("execution-selection", {})),
            "resolution": "NO_MODEL",
            "effective": None,
            "entries": [
                dict(
                    batch_index=i,
                    task_id=str(uuid4()),
                    attempt_id=str(uuid4()),
                    brief_ref=ref(record("task-brief", {})),
                    goal="identical bounded goal",
                )
                for i in range(2)
            ],
        },
    )


def test_stage_validates_envelope_and_no_model_before_any_native_import():
    assert importlib.util.find_spec("omnis_hermes.managed_admission_contract"), (
        "managed contract missing"
    )
    from omnis_hermes.managed_admission_contract import PROTOCOL, validate_stage

    source = manifest()
    assert validate_stage({"protocol": PROTOCOL, "manifest": source}) == source
    for field, value in [("effective", {}), ("resolution", "DEFAULT"), ("other", 1)]:
        bad = copy.deepcopy(source)
        bad["payload"][field] = value
        bad["digest"] = digest(canonical({k: v for k, v in bad.items() if k != "digest"}))
        with pytest.raises(ValueError):
            validate_stage({"protocol": PROTOCOL, "manifest": bad})
    source["payload"]["entries"][0]["goal"] = "tampered"
    with pytest.raises(ValueError):
        validate_stage({"protocol": PROTOCOL, "manifest": source})


@pytest.mark.asyncio
async def test_host_managed_operation_uses_existing_peer_and_current_fence():
    import time
    from pathlib import Path
    from types import SimpleNamespace

    from omnis_hermes.managed_admission_contract import PROTOCOL
    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(Path("/nonexistent"))
    calls = []
    source = manifest()
    staged = dict(
        protocol=PROTOCOL,
        status="STAGED",
        ticket=str(uuid4()),
        manifest_ref=ref(source),
        native_root_id="native-root",
        entries=[
            {
                **{k: v for k, v in e.items() if k != "goal"},
                "native_child_id": f"child-{i}",
                "native_session_id": f"session-{i}",
            }
            for i, e in enumerate(source["payload"]["entries"])
        ],
    )

    async def call(method, params, **kwargs):
        calls.append((method, params, kwargs))
        return copy.deepcopy(staged)

    host.peer = SimpleNamespace(call=call, failure=None)
    host.process = SimpleNamespace(returncode=None)
    host.state, host.epoch = "READY", 1
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    body = dict(
        version=1,
        id=str(uuid4()),
        boot=host.boot,
        capability=host.capability,
        generation=0,
        epoch=1,
        op="task_stage",
        deadline_ns=host.deadline_ns,
        payload=dict(protocol=PROTOCOL, manifest=source),
    )
    assert host._validate(body) == body
    assert await host._managed(body) == staged
    assert len(calls) == 1 and calls[0][2]["timeout"] <= 3.2
    binding = record(
        "runtime-binding",
        dict(
            runtime_boot=str(uuid4()),
            run_id=source["payload"]["run_id"],
            ticket=staged["ticket"],
            native_root_id=staged["native_root_id"],
            entries=staged["entries"],
            authority=dict(instance_id=str(uuid4()), owner=str(uuid4()), generation=0, epoch=1),
        ),
    )
    with pytest.raises(ValueError):
        await host._managed(
            {
                **body,
                "op": "task_release",
                "payload": dict(
                    protocol=PROTOCOL,
                    ticket=staged["ticket"],
                    manifest_ref=ref(source),
                    binding=binding,
                ),
            }
        )
    assert len(calls) == 1
    host.state = "STOPPED"
    with pytest.raises(ValueError):
        await host._managed(body)
    assert len(calls) == 1
