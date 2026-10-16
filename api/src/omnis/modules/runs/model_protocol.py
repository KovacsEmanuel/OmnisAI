"""Finite NO_MODEL accounting consumer; no separate owner, store or live grant."""

import json
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs.model_dispatch import ModelDispatch
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import (
    exact,
    integer,
    mapping,
    record,
    ref,
    sequence,
    text,
)
from omnis.policy import budgets
from omnis.policy.model_dispatch_contract import require_live_deadline
from omnis.supervisor.runtime_client import FrozenPreflight

PROVENANCE = "SYNTHETIC_PROTOCOL_NO_MODEL"
PURPOSE = {"model_protocol_prepare": "PREPARE", "model_protocol_validation": "VALIDATION"}
LIMITS = {
    "calls": 2,
    "output_tokens": 128,
    "validation_calls": 1,
    "validation_output_tokens": 64,
    "cost_limit": None,
}


def admitted_caps(command: NativeTaskCommand, config: dict[str, object]) -> dict[str, object]:
    requested = mapping(command.protocol_caps)
    source = mapping(config["technical_caps"])
    for key, maximum in (("calls", 1), ("output_tokens", 64), ("wall_seconds", 3)):
        amount = integer(requested[key], 1, maximum)
        if amount > integer(source[key], 1):
            raise CatalogError("MODEL_PROTOCOL_CAP_REJECTED")
    if integer(requested["output_tokens"], 1) > integer(config["max_tokens"], 1):
        raise CatalogError("MODEL_PROTOCOL_CAP_REJECTED")
    return requested


async def replay(
    conn: AsyncConnection,
    command: NativeTaskCommand,
) -> dict[str, object] | None:
    await budgets._transaction(conn, command.owner_id)
    return await store.command_replay(
        conn,
        command.owner_id,
        text(command.protocol_id),
        command.action,
        command.model_dump(mode="json"),
    )


async def reserve(
    conn: AsyncConnection,
    consumer: ModelDispatch,
    command: NativeTaskCommand,
    prepared: dict[str, object],
    config: dict[str, object],
    frozen: FrozenPreflight,
) -> dict[str, object]:
    payload = mapping(prepared["payload"])
    run = text(payload["run_id"])
    caps = admitted_caps(command, config)
    remaining = (frozen.deadline_ns - time.monotonic_ns()) / 1_000_000_000
    deadline = (datetime.now(UTC) + timedelta(seconds=remaining)).isoformat()
    binding = mapping(payload["binding"])
    context = mapping(payload["model_context"])
    descriptor = records.envelope(
        "model-dispatch-owner",
        {
            "version": 1,
            "provenance": PROVENANCE,
            "owner_id": command.owner_id,
            "run_id": run,
            "manifest_ref": command.manifest_ref,
            "binding_ref": records.reference(binding),
            "authority": mapping(binding["payload"])["authority"],
            "runtime_boot": frozen.boot,
            "purpose": PURPOSE[command.action],
            "provider_config_ref": command.provider_config_ref,
            "execution_selection_ref": context["selection_ref"],
            "prepared": prepared,
            "requested_caps": command.protocol_caps,
            "admitted_caps": caps,
            "request_id": frozen.request_id,
            "body_digest": frozen.body_digest,
            "frame_digest": frozen.frame_digest,
            "body": frozen.body.decode(),
            "deadline": deadline,
            "deadline_ns": frozen.deadline_ns,
        },
    )
    graph = await store.graph(conn, command.owner_id, run)
    runs = [r for r in graph if r["kind"] == "managed-run" and r["id"] == run]
    if len(runs) != 1:
        raise CatalogError("MODEL_SCOPE_MISMATCH")
    budget = await budgets.create_budget(conn, command.owner_id, records.reference(runs[0]), LIMITS)
    await store.put(conn, command.owner_id, run, descriptor)
    dispatch = await budgets.reserve(
        conn,
        command.owner_id,
        records.reference(budget),
        {
            "run_or_job_ref": records.reference(runs[0]),
            "dispatch_attempt_id": command.protocol_id,
            "native_turn_ref": None,
            "dispatch_owner_ref": records.reference(descriptor),
            "purpose": PURPOSE[command.action],
            "provider_config_ref": command.provider_config_ref,
            "model_id": config["model_id"],
            "execution_selection_ref": context["selection_ref"],
            "projection_ref": payload["projection_ref"],
            "projection_digest": mapping(mapping(payload["projection"])["payload"])[
                "projection_digest"
            ],
            "fencing_epoch": command.expected_epoch,
            "deadline": deadline,
            "technical_caps": caps,
        },
        trusted_purpose=PURPOSE[command.action],
        hermes=False,
    )
    result: dict[str, object] = {
        "descriptor_ref": records.reference(descriptor),
        "dispatch_ref": records.reference(dispatch),
    }
    await store.command_complete(
        conn,
        command.owner_id,
        run,
        text(command.protocol_id),
        command.action,
        command.model_dump(mode="json"),
        result,
    )
    return result


async def qualified(
    conn: AsyncConnection,
    consumer: ModelDispatch,
    command: NativeTaskCommand,
    references: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    await budgets._transaction(conn, command.owner_id)
    run, descriptor = await store.owned(conn, command.owner_id, references["descriptor_ref"])
    body = exact(
        record(descriptor, "model-dispatch-owner")["payload"],
        {
            "version",
            "provenance",
            "owner_id",
            "run_id",
            "manifest_ref",
            "binding_ref",
            "authority",
            "runtime_boot",
            "purpose",
            "provider_config_ref",
            "execution_selection_ref",
            "prepared",
            "requested_caps",
            "admitted_caps",
            "request_id",
            "body_digest",
            "frame_digest",
            "body",
            "deadline",
            "deadline_ns",
        },
    )
    from omnis.modules.runs.native_preparation_models import sha
    from omnis.modules.settings.candidate_catalog import uuid_string
    from omnis.policy.model_dispatch_contract import utc

    integer(body["version"], 1, 1)
    integer(body["deadline_ns"], 1)
    uuid_string(body["request_id"])
    uuid_string(body["runtime_boot"])
    sha(body["body_digest"])
    sha(body["frame_digest"])
    utc(body["deadline"])
    for key, kind in (
        ("manifest_ref", "launch-manifest"),
        ("binding_ref", "runtime-binding"),
        ("provider_config_ref", "provider-config"),
        ("execution_selection_ref", "execution-selection"),
    ):
        ref(body[key], kind)
    for key in ("requested_caps", "admitted_caps"):
        caps = exact(body[key], {"calls", "output_tokens", "wall_seconds"})
        for field, maximum in (("calls", 1), ("output_tokens", 64), ("wall_seconds", 3)):
            integer(caps[field], 1, maximum)
    prepared = mapping(body["prepared"])
    payload = mapping(prepared["payload"])
    if (
        body["provenance"] != PROVENANCE
        or body["owner_id"] != command.owner_id
        or body["run_id"] != run
        or body["manifest_ref"] != command.manifest_ref
        or body["provider_config_ref"] != command.provider_config_ref
        or body["purpose"] != PURPOSE[command.action]
        or canonical(body["requested_caps"]) != canonical(command.protocol_caps)
    ):
        raise CatalogError("MODEL_PROTOCOL_REJECTED")
    current = await consumer.read(
        conn,
        command.owner_id,
        run,
        body["binding_ref"],
        prepared["approval_ref"],
        payload["projection_ref"],
    )
    config = await consumer.read_configuration(
        conn,
        command.owner_id,
        command.manifest_ref,
        command.provider_config_ref,
        mapping(body["authority"]),
    )
    actual_body = json.dumps(
        mapping(current["payload"]), separators=(",", ":"), allow_nan=False
    ).encode()
    if (
        canonical(current) != canonical(prepared)
        or actual_body.decode() != body["body"]
        or sha256(actual_body).hexdigest() != body["body_digest"]
        or admitted_caps(command, config) != body["admitted_caps"]
    ):
        raise CatalogError("MODEL_PROTOCOL_REJECTED")
    state = await budgets.readback(conn, command.owner_id, references["dispatch_ref"])
    dispatch = mapping(mapping(state["dispatch"])["payload"])
    if (
        dispatch["dispatch_owner_ref"] != records.reference(descriptor)
        or dispatch["dispatch_attempt_id"] != command.protocol_id
        or dispatch["provider_config_ref"] != command.provider_config_ref
        or dispatch["model_id"] != config["model_id"]
        or dispatch["purpose"] != body["purpose"]
        or dispatch["fencing_epoch"] != command.expected_epoch
        or dispatch["projection_ref"] != payload["projection_ref"]
        or dispatch["projection_digest"]
        != mapping(mapping(payload["projection"])["payload"])["projection_digest"]
        or dispatch["execution_selection_ref"] != mapping(payload["model_context"])["selection_ref"]
        or body["execution_selection_ref"] != dispatch["execution_selection_ref"]
        or body["runtime_boot"] != mapping(mapping(payload["binding"])["payload"])["runtime_boot"]
        or canonical(body["authority"])
        != canonical(mapping(mapping(payload["binding"])["payload"])["authority"])
        or dispatch["deadline"] != body["deadline"]
        or dispatch["technical_caps"] != body["admitted_caps"]
        or dispatch["native_turn_ref"] is not None
    ):
        raise CatalogError("MODEL_PROTOCOL_REJECTED")
    return body, state


async def mark_sent(
    conn: AsyncConnection,
    consumer: ModelDispatch,
    command: NativeTaskCommand,
    references: dict[str, object],
    frozen: FrozenPreflight,
) -> None:
    body, _ = await qualified(conn, consumer, command, references)
    require_live_deadline(body)
    if (
        body["request_id"] != frozen.request_id
        or body["body_digest"] != frozen.body_digest
        or body["frame_digest"] != frozen.frame_digest
        or body["deadline_ns"] != frozen.deadline_ns
        or body["runtime_boot"] != frozen.boot
    ):
        raise CatalogError("MODEL_PROTOCOL_REJECTED")
    await budgets.mark_sent(conn, command.owner_id, references["dispatch_ref"])


async def settle(
    conn: AsyncConnection,
    consumer: ModelDispatch,
    command: NativeTaskCommand,
    references: dict[str, object],
    result: object,
) -> dict[str, object]:
    body, _ = await qualified(conn, consumer, command, references)
    prepared = mapping(body["prepared"])
    # qualified just performed the same read and canonical equality in this T2.
    # No retained token/cache or public validation bypass crosses this call.
    accepted = await consumer._persist_configuration(conn, command.owner_id, prepared, result)
    run = text(body["run_id"])
    receipt_payload = {
        "provenance": PROVENANCE,
        "dispatch_ref": references["dispatch_ref"],
        "request_id": body["request_id"],
        "body_digest": body["body_digest"],
        "frame_digest": body["frame_digest"],
        "admitted_caps": body["admitted_caps"],
        "model_admission": accepted,
    }
    graph = await store.graph(conn, command.owner_id, run)
    found = [
        r
        for r in graph
        if r["kind"] == "model-protocol-receipt"
        and mapping(r["payload"])["dispatch_ref"] == references["dispatch_ref"]
    ]
    if found:
        if len(found) != 1 or canonical(found[0]["payload"]) != canonical(receipt_payload):
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
    else:
        await store.put(
            conn, command.owner_id, run, records.envelope("model-protocol-receipt", receipt_payload)
        )
    await budgets.settle(
        conn,
        command.owner_id,
        references["dispatch_ref"],
        {
            "receipt_id": body["request_id"],
            "usage_state": "KNOWN",
            "output_tokens": 0,
            "provider_receipt_ref": None,
            "cost_observed": None,
            "cost_estimate": None,
        },
    )
    state = await budgets.readback(conn, command.owner_id, references["dispatch_ref"])
    return await _readback(conn, consumer, command, references, body, state)


def validate_readback(value: object, command: NativeTaskCommand) -> dict[str, object]:
    from omnis.modules.runs.native_preparation_models import sha
    from omnis.modules.settings.candidate_catalog import uuid_string
    from omnis.modules.tasks.managed_contract import exact, ref

    body = exact(
        value,
        {
            "provenance",
            "descriptor_ref",
            "dispatch_ref",
            "request_id",
            "body_digest",
            "frame_digest",
            "purpose",
            "requested_caps",
            "admitted_caps",
            "state",
            "usage_state",
            "protocol_calls",
            "model_calls",
            "output_tokens",
            "cost_observed",
            "cost_estimate",
            "provider_receipt_ref",
        },
    )
    ref(body["descriptor_ref"], "model-dispatch-owner")
    ref(body["dispatch_ref"], "model-dispatch")
    uuid_string(body["request_id"])
    sha(body["body_digest"])
    sha(body["frame_digest"])
    integer(body["model_calls"], 0, 0)
    integer(body["protocol_calls"], 0, 1)
    state = text(body["state"])
    usage = text(body["usage_state"])
    if (
        body["provenance"] != PROVENANCE
        or body["purpose"] != PURPOSE[command.action]
        or canonical(body["requested_caps"]) != canonical(command.protocol_caps)
        or canonical(body["admitted_caps"]) != canonical(command.protocol_caps)
        or state not in {"RESERVED", "SENT", "RELEASED", "SETTLED"}
        or usage != ("KNOWN" if state == "SETTLED" else "UNKNOWN")
        or body["protocol_calls"] != (0 if state == "RELEASED" else 1)
        or any(
            body[k] is not None for k in ("cost_observed", "cost_estimate", "provider_receipt_ref")
        )
    ):
        raise CatalogError("MODEL_PROTOCOL_REJECTED")
    if state == "SETTLED":
        integer(body["output_tokens"], 0, 0)
    elif body["output_tokens"] is not None:
        raise CatalogError("MODEL_PROTOCOL_REJECTED")
    return body


async def readback(
    conn: AsyncConnection,
    consumer: ModelDispatch,
    command: NativeTaskCommand,
    references: dict[str, object],
) -> dict[str, object]:
    body, state = await qualified(conn, consumer, command, references)
    return await _readback(conn, consumer, command, references, body, state)


async def _readback(
    conn: AsyncConnection,
    consumer: ModelDispatch,
    command: NativeTaskCommand,
    references: dict[str, object],
    body: dict[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    """Receipt/usage/schema checks after qualification within this same call/T2."""
    graph = await store.graph(conn, command.owner_id, text(body["run_id"]))
    receipts = [
        r
        for r in graph
        if r["kind"] == "model-protocol-receipt"
        and mapping(r["payload"])["dispatch_ref"] == references["dispatch_ref"]
    ]
    if state["state"] == "SETTLED":
        usage = [
            mapping(mapping(item)["payload"])["usage"]
            for item in sequence(state["history"])
            if mapping(item)["kind"] == "model-usage-receipt"
        ]
        expected_usage = {
            "receipt_id": body["request_id"],
            "usage_state": "KNOWN",
            "output_tokens": 0,
            "provider_receipt_ref": None,
            "cost_observed": None,
            "cost_estimate": None,
        }
        if canonical(usage) != canonical([expected_usage]):
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
        if len(receipts) != 1:
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
        receipt = exact(
            record(receipts[0], "model-protocol-receipt")["payload"],
            {
                "provenance",
                "dispatch_ref",
                "request_id",
                "body_digest",
                "frame_digest",
                "admitted_caps",
                "model_admission",
            },
        )
        ref(receipt["dispatch_ref"], "model-dispatch")
        admission = mapping(receipt["model_admission"])
        ref(admission["configuration_receipt_ref"], "model-configuration-receipt")
        native = {
            k: v
            for k, v in admission.items()
            if k not in {"data_approval_ref", "configuration_receipt_ref"}
        }
        accepted = consumer.accept_preflight(native, mapping(body["prepared"]))
        if canonical(
            {k: v for k, v in admission.items() if k != "configuration_receipt_ref"}
        ) != canonical(accepted) or any(
            receipt[k] != body[k]
            for k in ("provenance", "request_id", "body_digest", "frame_digest", "admitted_caps")
        ):
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
        from omnis.policy.model_configuration import configuration_payload

        configuration = await store.get(
            conn, command.owner_id, text(body["run_id"]), admission["configuration_receipt_ref"]
        )
        expected_configuration = configuration_payload(
            mapping(mapping(body["prepared"])["payload"]), accepted["source_configuration"]
        )
        if canonical(record(configuration, "model-configuration-receipt")["payload"]) != canonical(
            expected_configuration
        ):
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
    elif receipts:
        raise CatalogError("MODEL_RECEIPT_CONFLICT")
    return {
        "provenance": PROVENANCE,
        **references,
        "request_id": body["request_id"],
        "body_digest": body["body_digest"],
        "frame_digest": body["frame_digest"],
        "purpose": body["purpose"],
        "requested_caps": body["requested_caps"],
        "admitted_caps": body["admitted_caps"],
        "state": state["state"],
        "usage_state": state["usage_state"],
        "protocol_calls": state["charged_calls"],
        "model_calls": 0,
        "output_tokens": state["charged_output_tokens"]
        if state["usage_state"] == "KNOWN"
        else None,
        "cost_observed": None,
        "cost_estimate": None,
        "provider_receipt_ref": None,
    }
