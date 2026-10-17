"""Internal accounting only, never a model admission or a send permission.

The caller owns the READ COMMITTED transaction and acquires InstanceControl,
lease and Stop barriers before this ledger. It must commit SENT before bytes.
All durable data uses immutable managed_record envelopes. No local ledger cache.
"""

from datetime import UTC, datetime

import psycopg
from sqlalchemy import text as sql
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import exact, integer, mapping, record, ref, text
from omnis.policy.model_dispatch_contract import (
    PURPOSES,
    REQUEST_FIELDS,
    decimal_string,
    monitoring,
    require_live_deadline,
    scope_ref,
    utc,
    validate_caps,
    validate_limits,
    validate_request,
)


def validate_usage(value: object) -> dict[str, object]:
    from omnis.modules.settings.candidate_catalog import uuid_string

    result = exact(
        {"cost_observed": None, "cost_estimate": None, **mapping(value)},
        {
            "receipt_id",
            "usage_state",
            "output_tokens",
            "provider_receipt_ref",
            "cost_observed",
            "cost_estimate",
        },
    )
    uuid_string(result["receipt_id"])
    state = text(result["usage_state"], 10)
    if state == "UNKNOWN":
        if result["output_tokens"] is not None or result["cost_observed"] is not None:
            raise CatalogError("MODEL_USAGE_INVALID")
    elif state in {"PARTIAL", "KNOWN"}:
        integer(result["output_tokens"], 0)
    else:
        raise CatalogError("MODEL_USAGE_INVALID")
    if result["provider_receipt_ref"] is not None:
        ref(result["provider_receipt_ref"], "provider-receipt")
    decimal_string(result["cost_observed"])
    decimal_string(result["cost_estimate"])
    return result


def reduce_history(
    dispatch: object, reservation: object, history: list[dict[str, object]]
) -> dict[str, object]:
    """Reconstruct one immutable allocation; this pure reducer never authorizes I/O."""
    dispatch_record = record(dispatch, "model-dispatch")
    allocation = record(reservation, "model-reservation")
    body = exact(
        dispatch_record["payload"],
        REQUEST_FIELDS | {"reservation_ref", "usage_state", "provider_receipt_ref"},
    )
    allocated = exact(allocation["payload"], {"budget_ref", "request"})
    ref(allocated["budget_ref"], "model-budget")
    req = validate_request(
        allocated["request"],
        trusted_purpose=text(body["purpose"]),
        hermes=body["native_turn_ref"] is not None,
    )
    if (
        canonical({k: body[k] for k in REQUEST_FIELDS}) != canonical(req)
        or body["reservation_ref"] != records.reference(allocation)
        or body["usage_state"] != "UNKNOWN"
        or body["provider_receipt_ref"] is not None
    ):
        raise CatalogError("MODEL_ALLOCATION_MISMATCH")
    state, usage_state = "RESERVED", "UNKNOWN"
    caps = mapping(req["technical_caps"])
    tokens = 0 if monitoring(caps) else integer(caps["output_tokens"], 1)
    observed = 0
    ordered = sorted(history, key=lambda h: integer(mapping(record(h)["payload"])["sequence"], 1))
    seen_receipts: set[str] = set()
    for sequence, item in enumerate(ordered, 1):
        kind = text(item["kind"])
        fields = {"dispatch_ref", "sequence", "state", "created_at"}
        if kind == "model-usage-receipt":
            fields.add("usage")
        elif kind != "model-dispatch-transition":
            raise CatalogError("MODEL_HISTORY_INVALID")
        event = exact(item["payload"], fields)
        utc(event["created_at"])
        if (
            event["dispatch_ref"] != records.reference(dispatch_record)
            or integer(event["sequence"], 1) != sequence
        ):
            raise CatalogError("MODEL_HISTORY_INVALID")
        if kind == "model-dispatch-transition":
            if state != "RESERVED" or event["state"] not in {"SENT", "RELEASED"}:
                raise CatalogError("MODEL_TRANSITION_DENIED")
            state = text(event["state"])
            continue
        value = validate_usage(event["usage"])
        identity = text(value["receipt_id"])
        if state != "SENT" or identity in seen_receipts:
            raise CatalogError("MODEL_TRANSITION_DENIED")
        seen_receipts.add(identity)
        next_usage = text(value["usage_state"])
        if usage_state == "PARTIAL" and next_usage == "UNKNOWN":
            raise CatalogError("MODEL_USAGE_REGRESSION")
        if next_usage != "UNKNOWN":
            next_observed = integer(value["output_tokens"], 0)
            if next_observed < observed:
                raise CatalogError("MODEL_USAGE_REGRESSION")
            observed = next_observed
        usage_state = next_usage
        state = "SETTLED" if usage_state == "KNOWN" else "SENT"
        if event["state"] != state:
            raise CatalogError("MODEL_HISTORY_INVALID")
    return {
        "dispatch": dispatch_record,
        "reservation": allocation,
        "history": ordered,
        "state": state,
        "usage_state": usage_state,
        "purpose": req["purpose"],
        "charged_calls": 0 if state == "RELEASED" else 1,
        "charged_output_tokens": 0
        if state == "RELEASED"
        else observed
        if state == "SETTLED"
        else None
        if monitoring(caps) and usage_state == "UNKNOWN"
        else max(tokens, observed),
    }


def require_capacity(
    limits: object, states: list[dict[str, object]], purpose: str, caps: object
) -> None:
    ceiling = validate_limits(limits)
    if purpose not in PURPOSES:
        raise CatalogError("MODEL_PURPOSE_MISMATCH")
    requested = validate_caps(caps)
    if monitoring(ceiling) != monitoring(requested):
        raise CatalogError("MODEL_CAP_INVALID")
    for name, charged in (("calls", "charged_calls"), ("output_tokens", "charged_output_tokens")):
        if name == "output_tokens" and monitoring(ceiling):
            continue
        total = sum(integer(s[charged], 0) for s in states)
        ordinary = sum(integer(s[charged], 0) for s in states if s["purpose"] != "VALIDATION")
        amount = integer(requested[name], 1)
        maximum = integer(ceiling[name], 1)
        carveout = integer(ceiling["validation_" + name], 0)
        if total + amount > maximum or (
            purpose != "VALIDATION" and ordinary + amount > maximum - carveout
        ):
            raise CatalogError("MODEL_BUDGET_EXHAUSTED")


# PostgreSQL functions below never commit, send, authenticate a native turn, or
# grant a projection. Syntax + owner/pin resolution are accounting prerequisites
# only; trusted admission must resolve the effective binding/projection itself.


def validate_transaction_mode(isolation: object, autocommit: object) -> None:
    if isolation != "READ COMMITTED" or autocommit is not False:
        raise CatalogError("MODEL_ISOLATION_REQUIRED")


async def _transaction(connection: AsyncConnection, owner: str) -> None:
    uuid_string(owner)
    try:
        active = connection.in_transaction()
    except InvalidRequestError:
        active = False
    if not active:
        raise CatalogError("MODEL_TRANSACTION_REQUIRED")
    # Transaction locks under a stale REPEATABLE READ snapshot do not serialize
    # capacity reads. Do not accept that isolation level or AUTOCOMMIT.
    driver = (await connection.get_raw_connection()).driver_connection
    if not isinstance(driver, psycopg.AsyncConnection):
        raise CatalogError("MODEL_ISOLATION_REQUIRED")
    validate_transaction_mode(await connection.get_isolation_level(), driver.autocommit)
    await store.lock(connection, owner)


async def _scope_lock(connection: AsyncConnection, owner: str, run: str) -> None:
    await records.lock(connection, "model-budget:" + owner + ":" + run)


async def _resolved(
    connection: AsyncConnection, owner: str, run: str, reference: object
) -> dict[str, object]:
    checked = ref(reference)
    try:
        return await store.get(connection, owner, run, checked)
    except CatalogError as error:
        if error.reason != "REF_UNAVAILABLE":
            raise
        # Provider/config and execution-selection may be catalog records, but
        # native owner/turn/projection must belong to this exact managed run.
        if checked["kind"] not in {"provider-config", "execution-selection"}:
            raise
        _, item = await records.get(connection, owner, checked)
        return record(item, text(checked["kind"]))


async def _budget(
    connection: AsyncConnection, owner: str, reference: object
) -> tuple[str, dict[str, object]]:
    run, item = await store.owned(connection, owner, ref(reference, "model-budget"))
    body = exact(item["payload"], {"owner_id", "scope_ref", "limits"})
    scope = scope_ref(body["scope_ref"])
    if body["owner_id"] != owner or scope["id"] != run:
        raise CatalogError("MODEL_SCOPE_MISMATCH")
    await store.get(connection, owner, run, scope)
    validate_limits(body["limits"])
    await _scope_lock(connection, owner, run)
    return run, item


def _state_from_graph(
    dispatch: dict[str, object], graph: list[dict[str, object]]
) -> dict[str, object]:
    reservation_ref = ref(mapping(dispatch["payload"])["reservation_ref"], "model-reservation")
    allocations = [r for r in graph if r["id"] == reservation_ref["id"]]
    if len(allocations) != 1:
        raise CatalogError("MODEL_ALLOCATION_MISMATCH")
    history = []
    for item in graph:
        if item["kind"] in {"model-dispatch-transition", "model-usage-receipt"}:
            target = ref(mapping(item["payload"])["dispatch_ref"], "model-dispatch")
            if target["id"] == dispatch["id"]:
                history.append(item)
    return reduce_history(dispatch, allocations[0], history)


async def create_budget(
    connection: AsyncConnection, owner: str, scope_ref: object, limits: object
) -> dict[str, object]:
    """Create/replay the sole immutable allocation ceiling for an existing run."""
    from omnis.policy.model_dispatch_contract import scope_ref as validate_scope

    scope = validate_scope(scope_ref)
    checked = validate_limits(limits)
    await _transaction(connection, owner)
    run, _ = await store.owned(connection, owner, scope)
    if scope["id"] != run:
        raise CatalogError("MODEL_SCOPE_MISMATCH")
    await _scope_lock(connection, owner, run)
    graph = await store.graph(connection, owner, run)
    found = [r for r in graph if r["kind"] == "model-budget"]
    payload: dict[str, object] = {"owner_id": owner, "scope_ref": scope, "limits": checked}
    if found:
        if len(found) != 1 or canonical(found[0]["payload"]) != canonical(payload):
            raise CatalogError("MODEL_BUDGET_CONFLICT")
        return found[0]
    item = records.envelope("model-budget", payload)
    await store.put(connection, owner, run, item)
    return item


async def reserve(
    connection: AsyncConnection,
    owner: str,
    budget_ref: object,
    request: object,
    *,
    trusted_purpose: str,
    hermes: bool = True,
) -> dict[str, object]:
    req = validate_request(request, trusted_purpose=trusted_purpose, hermes=hermes)
    await _transaction(connection, owner)
    run, budget = await _budget(connection, owner, budget_ref)
    body = mapping(budget["payload"])
    if req["run_or_job_ref"] != body["scope_ref"]:
        raise CatalogError("MODEL_SCOPE_MISMATCH")
    for field in (
        "dispatch_owner_ref",
        "provider_config_ref",
        "projection_ref",
        "native_turn_ref",
        "execution_selection_ref",
    ):
        if req[field] is not None:
            resolved = await _resolved(connection, owner, run, req[field])
            if (
                field == "projection_ref"
                and mapping(resolved["payload"]).get("projection_digest")
                != req["projection_digest"]
            ):
                raise CatalogError("MODEL_PROJECTION_MISMATCH")
    graph = await store.graph(connection, owner, run)
    dispatches = [r for r in graph if r["kind"] == "model-dispatch"]
    states = [_state_from_graph(d, graph) for d in dispatches]
    allocation_refs: set[str] = set()
    for state in states:
        allocation = mapping(state["reservation"])
        if allocation["id"] in allocation_refs or mapping(allocation["payload"])[
            "budget_ref"
        ] != records.reference(budget):
            raise CatalogError("MODEL_ALLOCATION_MISMATCH")
        allocation_refs.add(text(allocation["id"]))
    if allocation_refs != {text(r["id"]) for r in graph if r["kind"] == "model-reservation"}:
        raise CatalogError("MODEL_ALLOCATION_MISMATCH")
    found = [
        d
        for d in dispatches
        if mapping(d["payload"])["dispatch_attempt_id"] == req["dispatch_attempt_id"]
    ]
    if found:
        if len(found) != 1 or canonical(
            {k: mapping(found[0]["payload"])[k] for k in REQUEST_FIELDS}
        ) != canonical(req):
            raise CatalogError("MODEL_ATTEMPT_CONFLICT")
        return found[0]  # Receipt replay only: mark_sent never reissues SENT.
    require_live_deadline(req)
    require_capacity(body["limits"], states, trusted_purpose, req["technical_caps"])
    allocation = records.envelope(
        "model-reservation", {"budget_ref": records.reference(budget), "request": req}
    )
    dispatch = records.envelope(
        "model-dispatch",
        {
            **req,
            "reservation_ref": records.reference(allocation),
            "usage_state": "UNKNOWN",
            "provider_receipt_ref": None,
        },
    )
    await store.put(connection, owner, run, allocation)
    await store.put(connection, owner, run, dispatch)
    return dispatch


async def _read(
    connection: AsyncConnection, owner: str, dispatch_ref: object
) -> tuple[str, dict[str, object]]:
    run, dispatch = await store.owned(connection, owner, ref(dispatch_ref, "model-dispatch"))
    allocation = await store.get(
        connection,
        owner,
        run,
        ref(mapping(dispatch["payload"])["reservation_ref"], "model-reservation"),
    )
    budget_run, budget = await _budget(
        connection, owner, mapping(allocation["payload"])["budget_ref"]
    )
    if (
        budget_run != run
        or mapping(dispatch["payload"])["run_or_job_ref"] != mapping(budget["payload"])["scope_ref"]
    ):
        raise CatalogError("MODEL_SCOPE_MISMATCH")
    return run, _state_from_graph(dispatch, await store.graph(connection, owner, run))


async def readback(
    connection: AsyncConnection, owner: str, dispatch_ref: object
) -> dict[str, object]:
    await _transaction(connection, owner)
    _, result = await _read(connection, owner, dispatch_ref)
    return result


def _history(state: dict[str, object]) -> list[dict[str, object]]:
    from omnis.modules.tasks.managed_contract import sequence

    return [record(item) for item in sequence(state["history"])]


def _event(
    dispatch_ref: object,
    history: list[dict[str, object]],
    state: str,
    usage: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "dispatch_ref": ref(dispatch_ref, "model-dispatch"),
        "sequence": len(history) + 1,
        "state": state,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if usage is not None:
        payload["usage"] = usage
    return records.envelope(
        "model-dispatch-transition" if usage is None else "model-usage-receipt", payload
    )


async def _transition(
    connection: AsyncConnection, owner: str, dispatch_ref: object, target: str
) -> dict[str, object]:
    await _transaction(connection, owner)
    run, state = await _read(connection, owner, dispatch_ref)
    if state["state"] != "RESERVED":
        raise CatalogError("MODEL_TRANSITION_DENIED")
    if target == "SENT":
        require_live_deadline(mapping(mapping(state["dispatch"])["payload"]))
    history = _history(state)
    event = _event(dispatch_ref, history, target)
    reduce_history(state["dispatch"], state["reservation"], [*history, event])
    await store.put(connection, owner, run, event)
    return event


async def mark_sent(
    connection: AsyncConnection, owner: str, dispatch_ref: object
) -> dict[str, object]:
    """Append single-use send intent; this function is NOT admission or transport."""
    return await _transition(connection, owner, dispatch_ref, "SENT")


async def release(
    connection: AsyncConnection, owner: str, dispatch_ref: object
) -> dict[str, object]:
    return await _transition(connection, owner, dispatch_ref, "RELEASED")


def receipt_replay(
    dispatch_ref: object, usage: object, graph: list[dict[str, object]]
) -> dict[str, object] | None:
    target = ref(dispatch_ref, "model-dispatch")
    value = validate_usage(usage)
    replay: dict[str, object] | None = None
    provider = value["provider_receipt_ref"]
    for item in graph:
        if item["kind"] != "model-usage-receipt":
            continue
        event = record(item, "model-usage-receipt")
        body = mapping(event["payload"])
        prior = validate_usage(body["usage"])
        same_dispatch = body["dispatch_ref"] == target
        if prior["receipt_id"] == value["receipt_id"]:
            if not same_dispatch or canonical(prior) != canonical(value) or replay is not None:
                raise CatalogError("MODEL_RECEIPT_CONFLICT")
            replay = event
        prior_provider = prior["provider_receipt_ref"]
        if (
            provider is not None
            and prior_provider is not None
            and ref(provider)["id"] == ref(prior_provider)["id"]
            and not same_dispatch
        ):
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
    return replay


async def settle(
    connection: AsyncConnection, owner: str, dispatch_ref: object, usage: object
) -> dict[str, object]:
    value = validate_usage(usage)
    await _transaction(connection, owner)
    run, state = await _read(connection, owner, dispatch_ref)
    history = _history(state)
    # Receipt identity is owner-wide; _transaction holds that lock until append.
    provider = value["provider_receipt_ref"]
    matches = (
        (
            await connection.execute(
                sql(
                    "SELECT envelope FROM managed_record WHERE owner_id=:owner "
                    "AND envelope->>'kind'='model-usage-receipt' "
                    "AND (envelope->'payload'->'usage'->>'receipt_id'=:receipt "
                    "OR envelope->'payload'->'usage'->'provider_receipt_ref'->>'id' "
                    "= CAST(:provider AS text))"
                ),
                {
                    "owner": owner,
                    "receipt": value["receipt_id"],
                    "provider": None if provider is None else ref(provider)["id"],
                },
            )
        )
        .scalars()
        .all()
    )
    replay = receipt_replay(dispatch_ref, value, [record(item) for item in matches])
    if replay is not None:
        return replay
    if state["state"] != "SENT":
        raise CatalogError("MODEL_TRANSITION_DENIED")
    if value["provider_receipt_ref"] is not None:
        await _resolved(connection, owner, run, value["provider_receipt_ref"])
    target = "SETTLED" if value["usage_state"] == "KNOWN" else "SENT"
    event = _event(dispatch_ref, history, target, value)
    reduce_history(state["dispatch"], state["reservation"], [*history, event])
    await store.put(connection, owner, run, event)
    return event
