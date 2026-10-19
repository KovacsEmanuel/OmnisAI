"""The public test never accepts prompts, model settings or private references."""

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omnis.modules.settings.candidate_catalog import valid_ref


class ModelTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: str
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value: object) -> object:
        if value is not True:
            raise ValueError("Explicit consent required")
        return value

    @model_validator(mode="after")
    def identity(self) -> Self:
        if str(UUID(self.operation_id)) != self.operation_id:
            raise ValueError("Canonical operation required")
        return self


class ModelTestControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["model_test"]
    action: Literal["start", "read", "provision"]

    operation_id: str | None = None
    selection_ref: dict[str, object] | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.operation_id is not None and str(UUID(self.operation_id)) != self.operation_id:
            raise ValueError("Canonical identity required")
        if self.action == "provision":
            if self.operation_id is not None:
                raise ValueError("Private provisioning only")
            if valid_ref(self.selection_ref)["kind"] != "execution-selection":
                raise ValueError("Published selection required")
        elif self.selection_ref is not None:
            raise ValueError("No browser refs")
        elif self.action == "start" and self.operation_id is None:
            raise ValueError("Operation required")
        return self


class ModelTestView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    operation_id: str | None
    status: Literal["AVAILABLE", "UNAVAILABLE", "PENDING", "COMPLETE", "UNKNOWN", "ERROR"]
    reason: str | None
    system_message: str
    user_message: str
    requested_provider: Literal["openai-codex"] = "openai-codex"
    requested_model: Literal["gpt-6.1-sol"] = "gpt-6.1-sol"
    requested_effort: Literal["xhigh"] = "xhigh"
    observed_model: str | None = None
    observed_effort: str | None = None
    response_text: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    calls_limit: Literal[1] = 1
    wall_seconds: Literal[300] = 300
