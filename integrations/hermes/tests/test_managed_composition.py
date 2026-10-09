"""Versioned managed wire: legacy exactness and complete v2 material."""

import copy
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from composition_fixture import fixture, record, seal
from omnis_hermes import managed_admission_contract as contract
from omnis_hermes.runtime_host import RuntimeHost


def staged(payload):
    manifest = payload["manifest"]
    return dict(
        protocol=payload["protocol"],
        status="STAGED",
        ticket=str(uuid4()),
        manifest_ref=contract.ref(manifest),
        native_root_id="cold-root",
        entries=[
            {
                **{k: v for k, v in e.items() if k != "goal"},
                "native_child_id": f"child-{i}",
                "native_session_id": f"session-{i}",
            }
            for i, e in enumerate(manifest["payload"]["entries"])
        ],
    )


def test_v2_stage_response_release_status_and_legacy_are_distinct():
    stage = fixture()
    assert contract.validate_stage(stage) == stage["manifest"]
    response = staged(stage)
    assert contract.validate_response(response) == response
    status = {k: response[k] for k in ("protocol", "ticket", "manifest_ref")}
    assert contract.validate_status(status) == status
    binding = record(
        "runtime-binding",
        dict(
            runtime_boot=str(uuid4()),
            run_id=stage["manifest"]["payload"]["run_id"],
            ticket=response["ticket"],
            native_root_id=response["native_root_id"],
            entries=response["entries"],
            authority=dict(instance_id=str(uuid4()), owner=str(uuid4()), epoch=1, generation=0),
        ),
    )
    assert contract.validate_release({**status, "binding": binding})["binding"] == binding
    for wrong in (
        {**stage, "protocol": contract.PROTOCOL},
        {k: v for k, v in stage.items() if k != "compositions"},
        {**response, "protocol": contract.PROTOCOL},
        {**status, "protocol": "v3"},
        {**status, "binding": binding, "protocol": contract.PROTOCOL},
    ):
        checker = (
            contract.validate_stage
            if "manifest" in wrong
            else contract.validate_release
            if "binding" in wrong
            else contract.validate_response
            if "status" in wrong
            else contract.validate_status
        )
        with pytest.raises(ValueError):
            checker(wrong)


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong_ref", "overflow", "version_bool"])
def test_v2_rejects_incomplete_or_misbound_material(mutation):
    stage = fixture()
    if mutation == "missing":
        stage["compositions"] = []
    elif mutation == "extra":
        stage["compositions"] *= 2
    elif mutation == "wrong_ref":
        stage["manifest"]["payload"]["entries"][0]["composition_ref"]["digest"] = "f" * 64
        seal(stage["manifest"])
    elif mutation == "overflow":
        stage["compositions"][0]["payload"]["text"] += " " * 32768
    else:
        stage["manifest"]["payload"]["composition_version"] = True
        seal(stage["manifest"])
    with pytest.raises(ValueError):
        contract.validate_stage(stage)


@pytest.mark.asyncio
async def test_existing_host_v2_owner_and_response_protocol_equality():
    from test_managed_admission import manifest

    host = RuntimeHost(Path("/nonexistent"))
    payload = fixture()
    response = staged(payload)
    calls = []

    async def call(method, params, **kwargs):
        calls.append((method, params))
        return copy.deepcopy(response)

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
        payload=payload,
    )
    assert await host._managed(body) == response
    legacy = {"protocol": contract.PROTOCOL, "manifest": manifest()}
    response = staged(legacy)
    assert await host._managed({**body, "payload": legacy}) == response
    status = {k: response[k] for k in ("protocol", "ticket", "manifest_ref")}
    response["protocol"] = "omnis-managed-admission-v2"
    for row in response["entries"]:
        row["composition_ref"] = contract.ref(payload["compositions"][0])
    with pytest.raises(ValueError):
        await host._managed({**body, "op": "task_status", "payload": status})
    assert len(calls) == 3
