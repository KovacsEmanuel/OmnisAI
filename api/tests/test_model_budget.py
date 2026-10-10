"""Offline contract/state tests; no database fixtures or ledger doubles."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omnis.modules.settings.candidate_store import envelope, reference
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping
from omnis.policy import budgets as ledger
from omnis.policy import model_dispatch_contract as contract


def ref(kind: str) -> dict[str, object]:
    return reference(envelope(kind, {}))


def limits() -> dict[str, object]:
    return {
        "calls": 3,
        "output_tokens": 30,
        "validation_calls": 1,
        "validation_output_tokens": 10,
        "cost_limit": None,
    }


def request() -> dict[str, object]:
    projection = ref("model-projection")
    return {
        "run_or_job_ref": ref("managed-run"),
        "dispatch_attempt_id": str(uuid4()),
        "native_turn_ref": ref("native-turn"),
        "dispatch_owner_ref": ref("runtime-binding"),
        "purpose": "RECON",
        "provider_config_ref": ref("provider-config"),
        "model_id": "bounded-test-model",
        "execution_selection_ref": ref("execution-selection"),
        "projection_ref": projection,
        "projection_digest": projection["digest"],
        "fencing_epoch": 1,
        "deadline": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "technical_caps": {"calls": 1, "output_tokens": 10, "wall_seconds": 30},
    }


def test_exact_dispatch_contract_and_trusted_purpose() -> None:
    value = request()
    assert contract.validate_request(value, trusted_purpose="RECON") == value
    for field, bad in [
        ("native_turn_ref", None),
        ("fencing_epoch", True),
        ("deadline", "2026-10-10T12:00:00+03:00"),
        ("dispatch_attempt_id", "not-a-uuid"),
        ("projection_digest", "not-a-digest"),
        ("execution_selection_ref", None),
        ("purpose", "VALIDATION"),
        ("projection_ref", ref("evidence")),
    ]:
        invalid = {**value, field: bad}
        with pytest.raises(CatalogError):
            contract.validate_request(invalid, trusted_purpose="RECON")
    with pytest.raises(CatalogError):
        contract.validate_request({**value, "unknown": 1}, trusted_purpose="RECON")
    for key, invalid_cap in [
        ("calls", True),
        ("calls", 2),
        ("output_tokens", 0),
        ("output_tokens", 65537),
        ("wall_seconds", 1201),
    ]:
        invalid = deepcopy(value)
        caps = mapping(invalid["technical_caps"])
        caps[key] = invalid_cap
        invalid["technical_caps"] = caps
        with pytest.raises(CatalogError):
            contract.validate_request(invalid, trusted_purpose="RECON")
    assert contract.validate_limits(limits()) == limits()
    for changes in [
        {"calls": True},
        {"validation_calls": 4},
        {"cost_limit": "0.01"},
        {"cost_limit": "1.0"},
        {"other": 1},
    ]:
        with pytest.raises(CatalogError):
            contract.validate_limits({**limits(), **mapping(changes)})


def test_projection_payload_digest_is_not_the_envelope_digest() -> None:
    # B06c hashes CanonicalJSON(model_input), not its RecordEnvelope.
    value = request()
    value["projection_digest"] = "a" * 64
    assert value["projection_digest"] != mapping(value["projection_ref"])["digest"]
    assert contract.validate_request(value, trusted_purpose="RECON") == value
    for malformed in (None, True, "A" * 64, "a" * 63):
        with pytest.raises(CatalogError, match="MODEL_PROJECTION_MISMATCH"):
            contract.validate_request(
                {**value, "projection_digest": malformed}, trusted_purpose="RECON"
            )


def allocation() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    req = request()
    budget = envelope(
        "model-budget",
        {"owner_id": str(uuid4()), "scope_ref": req["run_or_job_ref"], "limits": limits()},
    )
    reservation = envelope("model-reservation", {"budget_ref": reference(budget), "request": req})
    dispatch = envelope(
        "model-dispatch",
        {
            **req,
            "reservation_ref": reference(reservation),
            "usage_state": "UNKNOWN",
            "provider_receipt_ref": None,
        },
    )
    return budget, reservation, dispatch


def event(dispatch: dict[str, object], sequence: int, state: str) -> dict[str, object]:
    return envelope(
        "model-dispatch-transition",
        {
            "dispatch_ref": reference(dispatch),
            "sequence": sequence,
            "state": state,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )


def usage(state: str = "KNOWN", tokens: int | None = 2) -> dict[str, object]:
    return {
        "receipt_id": str(uuid4()),
        "usage_state": state,
        "output_tokens": tokens,
        "provider_receipt_ref": None,
        "cost_observed": None,
        "cost_estimate": None,
    }


def receipt(
    dispatch: dict[str, object], sequence: int, value: dict[str, object]
) -> dict[str, object]:
    return envelope(
        "model-usage-receipt",
        {
            "dispatch_ref": reference(dispatch),
            "sequence": sequence,
            "state": "SETTLED" if value["usage_state"] == "KNOWN" else "SENT",
            "created_at": datetime.now(UTC).isoformat(),
            "usage": value,
        },
    )


def test_append_only_lifecycle_and_conservative_capacity() -> None:
    budget, reservation, dispatch = allocation()
    allocation_before = canonical(reservation)
    initial = ledger.reduce_history(dispatch, reservation, [])
    assert initial["state"] == "RESERVED"
    assert initial["charged_calls"] == 1 and initial["charged_output_tokens"] == 10
    sent = event(dispatch, 1, "SENT")
    unknown = receipt(dispatch, 2, usage("UNKNOWN", None))
    partial = receipt(dispatch, 3, usage("PARTIAL", 2))
    known = receipt(dispatch, 4, usage("KNOWN", 3))
    for history in [[sent], [sent, unknown], [sent, unknown, partial]]:
        state = ledger.reduce_history(dispatch, reservation, history)
        assert state["state"] == "SENT" and state["charged_output_tokens"] == 10
    settled = ledger.reduce_history(dispatch, reservation, [sent, unknown, partial, known])
    assert settled["state"] == "SETTLED" and settled["charged_calls"] == 1
    assert settled["charged_output_tokens"] == 3
    released = ledger.reduce_history(dispatch, reservation, [event(dispatch, 1, "RELEASED")])
    assert released["charged_calls"] == released["charged_output_tokens"] == 0
    zero = ledger.reduce_history(
        dispatch, reservation, [sent, receipt(dispatch, 2, usage("KNOWN", 0))]
    )
    assert zero["charged_calls"] == 1
    for history in [
        [sent, event(dispatch, 2, "SENT")],
        [sent, event(dispatch, 2, "RELEASED")],
        [known],
        [event(dispatch, 2, "SENT")],
        [sent, partial],
        [sent, unknown, partial, receipt(dispatch, 4, usage("UNKNOWN", None))],
        [sent, unknown, partial, receipt(dispatch, 4, usage("KNOWN", 1))],
    ]:
        with pytest.raises(CatalogError):
            ledger.reduce_history(dispatch, reservation, history)
    ledger.require_capacity(
        limits(), [initial], "RECON", {"calls": 1, "output_tokens": 10, "wall_seconds": 30}
    )
    with pytest.raises(CatalogError, match="MODEL_BUDGET_EXHAUSTED"):
        ledger.require_capacity(
            limits(),
            [initial, initial],
            "RECON",
            {"calls": 1, "output_tokens": 1, "wall_seconds": 30},
        )
    ledger.require_capacity(
        limits(),
        [initial, initial],
        "VALIDATION",
        {"calls": 1, "output_tokens": 10, "wall_seconds": 30},
    )
    with pytest.raises(CatalogError):
        ledger.require_capacity(
            limits(),
            [initial, initial, initial],
            "VALIDATION",
            {"calls": 1, "output_tokens": 1, "wall_seconds": 30},
        )
    assert canonical(reservation) == allocation_before


@pytest.mark.asyncio
async def test_all_storage_operations_refuse_unstarted_real_connection() -> None:
    from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

    # Real, unstarted SQLAlchemy connection: no network, DB, or ledger double.
    engine = create_async_engine("postgresql+psycopg://unused/unused")
    connection = AsyncConnection(engine)
    owner = str(uuid4())
    budget, _, dispatch = allocation()
    try:
        operations: list[Callable[[], Awaitable[dict[str, object]]]] = [
            lambda: ledger.create_budget(connection, owner, request()["run_or_job_ref"], limits()),
            lambda: ledger.reserve(
                connection, owner, reference(budget), request(), trusted_purpose="RECON"
            ),
            lambda: ledger.mark_sent(connection, owner, reference(dispatch)),
            lambda: ledger.release(connection, owner, reference(dispatch)),
            lambda: ledger.settle(connection, owner, reference(dispatch), usage()),
            lambda: ledger.readback(connection, owner, reference(dispatch)),
        ]
        for operation in operations:
            with pytest.raises(CatalogError, match="MODEL_TRANSACTION_REQUIRED"):
                await operation()
    finally:
        await engine.dispose()


def test_usage_validation_rejects_aliases_and_cost_conflation() -> None:
    for changes in [
        {"output_tokens": True},
        {"output_tokens": -1},
        {"usage_state": "unknown"},
        {"cost_observed": "0.00"},
        {"cost_estimate": "1e2"},
        {"cost_observed": "-1"},
        {"cost_limit": "1"},
        {"provider_receipt_ref": ref("model-projection")},
    ]:
        with pytest.raises(CatalogError):
            ledger.validate_usage({**usage(), **mapping(changes)})
    value = {**usage(), "cost_observed": "0", "cost_estimate": "1.25"}
    assert ledger.validate_usage(value) == value
    for value in [usage("UNKNOWN", 0), {**usage("UNKNOWN", None), "cost_observed": "0"}]:
        with pytest.raises(CatalogError):
            ledger.validate_usage(value)


@pytest.mark.parametrize(
    "isolation,autocommit",
    [
        ("READ COMMITTED", True),
        ("REPEATABLE READ", False),
        ("SERIALIZABLE", False),
        ("AUTOCOMMIT", False),
        ("READ COMMITTED", 0),
    ],
)
def test_transaction_mode_rejects_nontransactional_or_stale_snapshots(
    isolation: str, autocommit: object
) -> None:
    ledger.validate_transaction_mode("READ COMMITTED", False)
    with pytest.raises(CatalogError, match="MODEL_ISOLATION_REQUIRED"):
        ledger.validate_transaction_mode(isolation, autocommit)


def test_receipt_identity_cannot_reconcile_two_dispatches() -> None:
    _, _, dispatch = allocation()
    _, _, other = allocation()
    value = usage("PARTIAL", 1)
    value["provider_receipt_ref"] = ref("provider-receipt")
    prior = receipt(dispatch, 2, value)
    assert ledger.receipt_replay(reference(dispatch), value, [prior]) == prior
    assert ledger.receipt_replay(reference(dispatch), usage(), [prior]) is None
    for target, conflicting in [
        (reference(other), value),
        (reference(dispatch), {**value, "output_tokens": 2}),
        (reference(other), {**value, "receipt_id": str(uuid4())}),
    ]:
        with pytest.raises(CatalogError, match="MODEL_RECEIPT_CONFLICT"):
            ledger.receipt_replay(target, conflicting, [prior])


def test_deadline_is_rechecked_and_unsupported_jobs_remain_denied() -> None:
    current = request()
    contract.require_live_deadline(current)
    expired = {**current, "deadline": "2000-01-01T00:00:00Z"}
    with pytest.raises(CatalogError, match="MODEL_DEADLINE_EXPIRED"):
        contract.require_live_deadline(expired)
    for kind in ("model-job", "run-snapshot", "task-brief"):
        with pytest.raises(CatalogError, match="MODEL_SCOPE_INVALID"):
            contract.validate_request(
                {**current, "run_or_job_ref": ref(kind)}, trusted_purpose="RECON"
            )


def test_pg_restart_reader_program_compiles_without_running() -> None:
    from test_model_budget_pg import READBACK_SCRIPT

    compile(READBACK_SCRIPT, "<fresh-ledger-readback>", "exec")


def test_usage_optional_costs_and_overrun_remain_explicit() -> None:
    value = usage("KNOWN", 20)
    del value["cost_estimate"]
    del value["cost_observed"]
    assert ledger.validate_usage(value) == {**value, "cost_observed": None, "cost_estimate": None}
    _, reservation, dispatch = allocation()
    state = ledger.reduce_history(
        dispatch, reservation, [event(dispatch, 1, "SENT"), receipt(dispatch, 2, value)]
    )
    assert state["charged_calls"] == 1 and state["charged_output_tokens"] == 20
    with pytest.raises(CatalogError, match="MODEL_BUDGET_EXHAUSTED"):
        ledger.require_capacity(
            limits(), [state], "RECON", {"calls": 1, "output_tokens": 1, "wall_seconds": 1}
        )
