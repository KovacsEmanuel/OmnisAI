"""Finite Settings DTOs. Saved request is not provider compatibility evidence."""

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ProviderSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    provider: Literal["openai-codex"]
    model: Literal["gpt-6.1-sol"]
    effort: Literal["xhigh"]


class ProviderCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: str
    action: Literal["read", "save"]
    selection: ProviderSelection | None

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if str(UUID(self.operation_id)) != self.operation_id:
            raise ValueError("Invalid operation identity")
        if (self.action == "save") != (self.selection is not None):
            raise ValueError("Selection only belongs to save")
        if len(self.model_dump_json().encode()) > 3600:
            raise ValueError("Settings command too large")
        return self


class ProviderView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: str
    status: Literal["PENDING", "CONFIRMED", "INDETERMINATE", "BUSY", "UNAVAILABLE"]
    selection: ProviderSelection | None
    configured: bool
    authenticated: Literal["NOT_VERIFIED"]
    reachable: Literal["NOT_VERIFIED"]
    inference_ready: Literal[False]

    @field_validator("inference_ready", mode="before")
    @classmethod
    def no_inference(cls, value: object) -> object:
        if value is not False:
            raise ValueError("Inference not verified")
        return value

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if str(UUID(self.operation_id)) != self.operation_id:
            raise ValueError("Invalid operation identity")
        if self.configured != (self.status == "CONFIRMED" and self.selection is not None):
            raise ValueError("Invalid configuration readiness")
        if self.status != "CONFIRMED" and self.selection is not None:
            raise ValueError("Unconfirmed configuration")
        if len(self.model_dump_json().encode()) > 4096:
            raise ValueError("Settings response too large")
        return self


class SettingsControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["settings"]
    command: ProviderCommand | None
    operation_id: str

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if str(UUID(self.operation_id)) != self.operation_id:
            raise ValueError("Invalid operation identity")
        if self.command is not None and self.command.operation_id != self.operation_id:
            raise ValueError("Operation mismatch")
        if len(self.model_dump_json().encode()) > 3600:
            raise ValueError("Settings control too large")
        return self
