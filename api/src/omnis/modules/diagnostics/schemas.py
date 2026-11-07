"""Only finite metadata may cross the diagnostic boundary."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from omnis.core.errors import ErrorCode

MARKER = "OMNIS_UI_DIAGNOSTIC_V1"
PATH = "/api/v1/diagnostics/ui-events"
Uuid = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
Surface = Literal["dashboard", "engagement_setup", "engagement_overview", "brain_stream", "settings", "bootstrap"]
Site = Literal["navigation", "theme_toggle", "period_toggle", "calendar_choice", "inspector_open", "draft_save", "run_command", "stop_request", "stop_receipt_lookup", "command_receipt", "model_request", "provider_catalog_search", "provider_request", "http_read"]
Delivery = Literal["RECORDED", "RATE_LIMITED", "BUDGET_EXHAUSTED", "BUSY", "UNAVAILABLE", "BACKPRESSURED"]


class UiEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Annotated[int, Field(ge=1, le=1)]
    source: Literal["browser_untrusted"]
    event_id: Uuid
    surface: Surface
    site: Site
    action: Literal["OBSERVE", "REQUEST", "RESPONSE", "ERROR"]
    outcome: Literal["OBSERVED", "UNCONFIRMED", "REFUSED"]
    error_code: ErrorCode | Literal["API_UNAVAILABLE", "INVALID_RESPONSE"] | None
    correlation_id: Uuid | None
    run_id: Uuid | None
    command_id: Uuid | None

    @field_validator("error_code", mode="before")
    @classmethod
    def known_code(cls, value: object) -> object:
        if isinstance(value, str) and value in ErrorCode:
            return ErrorCode(value)
        return value


class UiRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    marker: Literal["OMNIS_UI_DIAGNOSTIC_V1"]
    source: Literal["browser_untrusted"]
    capture_id: Uuid
    received_at: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")]
    request_correlation_id: Uuid
    attempt: Annotated[int, Field(ge=1, le=256)]
    remaining: Annotated[int, Field(ge=0, le=255)]
    dropped_before: Annotated[int, Field(ge=0, le=255, description="Counted admitted-attempt drops; lock-busy losses are unknown.")]
    event: UiEvent

    @field_validator("received_at")
    @classmethod
    def real_time(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return value

    @model_validator(mode="after")
    def consistent_budget(self) -> "UiRecord":
        if self.attempt + self.remaining != 256 or self.dropped_before >= self.attempt:
            raise ValueError("Inconsistent capture budget")
        return self


class UiAck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    event_id: Uuid
    accepted: Literal[True]
    state: Delivery
