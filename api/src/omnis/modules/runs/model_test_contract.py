"""T1's owned V2 records; RUN has no admitted producer here."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from omnis.modules.settings.provider_key_models import (
    Identity,
    KeyDTO,
    ModelSelection,
    PositiveRevision,
    Provider,
    SelectionView,
)
from omnis.modules.settings.provider_key_service import ConnectionRevision

SYSTEM: Literal["Respond only with OMNIS_MODEL_TEST_OK. Use no tools."] = (
    "Respond only with OMNIS_MODEL_TEST_OK. Use no tools."
)
USER: Literal["This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK."] = (
    "This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK."
)
ACK = "OMNIS_MODEL_TEST_OK"
ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "orcarouter": "https://api.orcarouter.ai/v1",
}
type Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type State = Literal["PENDING", "RUNNING", "STOPPING", "FINISHED", "NEEDS_RECONCILIATION"]
type ResultState = Literal["NOT_SENT", "COMPLETED", "INCOMPLETE", "FAILED", "UNKNOWN"]


class Ref(KeyDTO):
    instance_id: Identity
    kind: str
    id: Identity
    revision: Literal[1] = 1
    digest: Digest


class Capabilities(KeyDTO):
    selection_revision: PositiveRevision
    choice: ModelSelection
    connection: ConnectionRevision
    max_output_tokens: int = Field(strict=True, ge=1, le=65536)
    fetched_at: datetime


class Snapshot(KeyDTO):
    schema_version: Literal[2] = 2
    selection: SelectionView
    connection: ConnectionRevision
    capabilities_ref: Ref
    data_policy: Literal["FIXED_SYNTHETIC_ONLY"] = "FIXED_SYNTHETIC_ONLY"
    endpoint: str


class Projection(KeyDTO):
    system: Literal["Respond only with OMNIS_MODEL_TEST_OK. Use no tools."] = SYSTEM
    user: Literal["This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK."] = USER
    model: str
    output_tokens: int = Field(strict=True, ge=1, le=65536)

    def request_body(self) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": self.user},
            ],
            "max_tokens": self.output_tokens,
            "stream": False,
            "provider": {"allow_fallbacks": False, "require_parameters": True},
        }


class Operation(KeyDTO):
    schema_version: Literal[1] = 1
    instance_id: Identity
    operation_id: Identity
    command_id: Identity
    payload_digest: Digest
    config_snapshot_ref: Ref
    input_projection_ref: Ref
    purpose: Literal["SETTINGS_TEST"] = "SETTINGS_TEST"
    execution_owner_id: Identity
    generation: int = Field(strict=True, ge=0)
    owner_epoch: PositiveRevision
    cancel_epoch: PositiveRevision
    deadline: datetime
    state_revision: PositiveRevision
    state: State
    finish_reason: Literal["COMPLETED", "FAILED", "CANCELLED", "DEADLINE", "OWNER_LOST"] | None
    outcome_ref: Ref | None


class Caps(KeyDTO):
    calls: Literal[1] = 1
    input_bytes: Literal[32768] = 32768
    output_tokens: int = Field(strict=True, ge=1, le=65536)
    wall_seconds: Literal[300] = 300


class Dispatch(KeyDTO):
    schema_version: Literal[2] = 2
    scope_kind: Literal["SYSTEM_OPERATION"] = "SYSTEM_OPERATION"
    scope_ref: Ref
    dispatch_attempt_id: Identity
    dispatch_owner_ref: Ref
    purpose: Literal["SETTINGS_TEST"] = "SETTINGS_TEST"
    config_snapshot_ref: Ref
    projection_ref: Ref
    projection_digest: Digest
    reservation_ref: Ref
    instance_generation: int = Field(strict=True, ge=0)
    owner_epoch: PositiveRevision
    cancel_epoch: PositiveRevision
    deadline: datetime
    technical_caps: Caps
    accounting_policy: Literal["FINITE_TEST"] = "FINITE_TEST"


class Outcome(KeyDTO):
    schema_version: Literal[2] = 2
    operation_or_run_ref: Ref
    dispatch_ref: Ref
    requested: Ref
    observed_router: Provider | None = None
    observed_model: str | None = None
    observed_parameters: dict[str, str] | None = None
    provider_response_id: str | None = None
    unobserved_reason: Literal["NOT_REPORTED"] = "NOT_REPORTED"
    provider_status: str | None = None
    result_state: ResultState
    output_ref: Ref | None = None
    output_state: Literal["COMPLETE", "TRUNCATED", "ABSENT"] = "ABSENT"
    captured_bytes: int = Field(default=0, ge=0)
    reason_code: str | None = None
    usage_state: Literal["KNOWN", "PARTIAL", "UNKNOWN"] = "UNKNOWN"
    input_tokens: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    output_tokens: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    reasoning_tokens: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    cost_observed: str | None = None
    cost_estimate: str | None = None
    currency: str | None = None
    price_basis: str | None = None
    price_revision: str | None = None
    recorded_at: datetime


class ModelTestView(KeyDTO):
    schema_version: Literal[2] = 2
    operation_id: Identity | None = None
    state: State | None = None
    state_revision: PositiveRevision | None = None
    finish_reason: str | None = None
    selection_revision: PositiveRevision | None = None
    metadata_state: Literal["NOT_REQUESTED", "PENDING", "READY", "FAILED"] = "NOT_REQUESTED"
    metadata_command_id: Identity | None = None
    reason: str | None = None
    requested_provider: Provider | None = None
    requested_model: str | None = None
    requested_output_tokens: int | None = Field(default=None, ge=1, le=65536)
    observed_model: str | None = None
    provider_status: str | None = None
    result_state: ResultState | None = None
    output_state: Literal["COMPLETE", "TRUNCATED", "ABSENT"] = "ABSENT"
    response_text: str | None = None
    usage_state: Literal["KNOWN", "PARTIAL", "UNKNOWN"] = "UNKNOWN"
    input_tokens: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    output_tokens: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    reasoning_tokens: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    cost_observed: str | None = None
    system_message: str = SYSTEM
    user_message: str = USER
    calls_limit: Literal[1] = 1
    wall_seconds: Literal[300] = 300
