"""Strict ledger wire validation; authentication belongs to admission, not JSON."""

import re
from datetime import UTC, datetime, timedelta

from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks.managed_contract import exact, integer, ref, text

PURPOSES = frozenset(
    {
        "PREPARE",
        "RECON",
        "INVESTIGATE",
        "VALIDATION",
        "METHOD_REVIEW",
        "RESEARCH",
        "DECISION",
        "MAINTENANCE",
        "SETTINGS_TEST",
    }
)
SCOPE_KINDS = frozenset({"managed-run"})
REQUEST_FIELDS: set[str] = set(
    "run_or_job_ref dispatch_attempt_id native_turn_ref dispatch_owner_ref purpose provider_config_ref model_id execution_selection_ref projection_ref projection_digest fencing_epoch deadline technical_caps".split()
)


def scope_ref(value: object) -> dict[str, object]:
    result = ref(value)
    if result["kind"] not in SCOPE_KINDS:
        raise CatalogError("MODEL_SCOPE_INVALID")
    return result


def decimal_string(value: object) -> str | None:
    if value is None:
        return None
    result = text(value, 100)
    if re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?", result) is None:
        raise CatalogError("MODEL_COST_INVALID")
    return result


def utc(value: object) -> datetime:
    source = text(value, 40)
    if (
        re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)",
            source,
        )
        is None
    ):
        raise CatalogError("MODEL_DEADLINE_INVALID")
    try:
        result = datetime.fromisoformat(source)
    except ValueError:
        raise CatalogError("MODEL_DEADLINE_INVALID") from None
    if result.utcoffset() != timedelta(0):
        raise CatalogError("MODEL_DEADLINE_INVALID")
    return result


def monitoring(value: object) -> bool:
    return type(value) is dict and value.get("output_policy") == "MONITOR_SUBSCRIPTION"


def validate_caps(value: object) -> dict[str, object]:
    monitor = monitoring(value)
    caps = exact(
        value,
        {"calls", "output_tokens", "wall_seconds"} | ({"output_policy"} if monitor else set()),
    )
    integer(caps["calls"], 1, 1)
    integer(caps["wall_seconds"], 1, 300 if monitor else 1200)
    if monitor:
        if caps["output_tokens"] is not None:
            raise CatalogError("MODEL_CAP_INVALID")
    else:
        integer(caps["output_tokens"], 1, 65536)
    return caps


def validate_limits(value: object) -> dict[str, object]:
    fields = {
        "calls",
        "output_tokens",
        "validation_calls",
        "validation_output_tokens",
        "cost_limit",
    }
    monitor = monitoring(value)
    result = exact(value, fields | ({"output_policy"} if monitor else set()))
    calls = integer(result["calls"], 1, 200 if monitor else 2**63 - 1)
    integer(result["validation_calls"], 0, calls)
    if monitor:
        if result["output_tokens"] is not None or result["validation_output_tokens"] is not None:
            raise CatalogError("MODEL_CAP_INVALID")
    else:
        tokens = integer(result["output_tokens"], 1)
        integer(result["validation_output_tokens"], 0, tokens)
    if decimal_string(result["cost_limit"]) is not None:
        raise CatalogError("MODEL_FINANCIAL_LIMIT_BLOCKED")
    return result


def validate_request(
    value: object, *, trusted_purpose: str, hermes: bool = True
) -> dict[str, object]:
    result = exact(value, REQUEST_FIELDS)
    purpose = text(result["purpose"], 32)
    if trusted_purpose not in PURPOSES or purpose != trusted_purpose or type(hermes) is not bool:
        raise CatalogError("MODEL_PURPOSE_MISMATCH")
    scope_ref(result["run_or_job_ref"])
    uuid_string(result["dispatch_attempt_id"])
    if hermes:
        ref(result["native_turn_ref"], "native-turn")
        ref(result["dispatch_owner_ref"], "runtime-binding")
    else:
        if result["native_turn_ref"] is not None:
            raise CatalogError("MODEL_TURN_INVALID")
        ref(result["dispatch_owner_ref"], "model-dispatch-owner")
    ref(result["provider_config_ref"], "provider-config")
    text(result["model_id"], 256)
    # No Settings/Jev job producer is implemented in this ledger slice.
    ref(result["execution_selection_ref"], "execution-selection")
    ref(result["projection_ref"], "model-projection")
    # B06c binds the serialized model_input independently of its record envelope.
    projection_digest = result["projection_digest"]
    if (
        type(projection_digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", projection_digest) is None
    ):
        raise CatalogError("MODEL_PROJECTION_MISMATCH")
    integer(result["fencing_epoch"], 1)
    utc(result["deadline"])
    caps = validate_caps(result["technical_caps"])
    if monitoring(caps) and (
        not hermes or purpose != "SETTINGS_TEST" or result["model_id"] != "gpt-6.1-sol"
    ):
        raise CatalogError("MODEL_CAP_INVALID")
    return result


def require_live_deadline(request: dict[str, object]) -> None:
    if utc(request["deadline"]) <= datetime.now(UTC):
        raise CatalogError("MODEL_DEADLINE_EXPIRED")
