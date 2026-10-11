"""Small typed DTOs shared by HTTP and local control, never ORM serialization."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omnis.modules.instance.stop_contract import ArmStopCommand, VersionOne


class InstanceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instance_id: UUID
    generation: int
    admission_open: bool
    shutdown_command_id: UUID | None
    quiesced_generation: int | None
    supervisor_epoch: int
    supervisor_ready: bool
    shutdown_finalized: bool
    assessment_ready: bool
    dashboard_ready: bool


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatusCommand(StrictBody):
    op: Literal["status"]


class PairingCommand(StrictBody):
    op: Literal["pairing"]
    instance_id: UUID
    issuance_id: UUID
    digest: str = Field(pattern=r"^[0-9a-f]{64}$", repr=False)


class LifecycleCommand(StrictBody):
    op: Literal["open", "shutdown", "finalize"]
    instance_id: UUID
    command_id: UUID
    expected_generation: int = Field(ge=0, le=9223372036854775806, strict=True)


class NativePrepareCommand(StrictBody):
    op: Literal["native_prepare"]
    schema_version: VersionOne
    owner_id: str
    command_id: str
    instance_id: str
    expected_generation: int = Field(ge=0, le=9223372036854775807, strict=True)
    expected_epoch: int = Field(ge=1, le=9223372036854775807, strict=True)
    selection_ref: dict[str, object]

    @field_validator("owner_id", "command_id", "instance_id", mode="before")
    @classmethod
    def identity(cls, value: object) -> str:
        from omnis.modules.settings.candidate_catalog import uuid_string

        return uuid_string(value)

    @field_validator("selection_ref", mode="before")
    @classmethod
    def selection(cls, value: object) -> dict[str, object]:
        from omnis.modules.settings.candidate_catalog import valid_ref

        ref = valid_ref(value)
        if ref["kind"] != "execution-selection":
            raise ValueError("Invalid selection")
        return ref


class NativeTaskCommand(StrictBody):
    op: Literal["native_task"]
    schema_version: VersionOne
    owner_id: str
    command_id: str
    instance_id: str
    expected_generation: int = Field(ge=0, le=9223372036854775807, strict=True)
    expected_epoch: int = Field(ge=1, le=9223372036854775807, strict=True)
    action: Literal["stage", "release", "receive", "model_preflight", "model_configuration"]
    manifest_ref: dict[str, object]
    data_approval: dict[str, object] | None = Field(default=None, repr=False)
    configuration: dict[str, object] | None = Field(
        default=None, repr=False, exclude_if=lambda v: v is None
    )

    @field_validator("configuration", mode="before")
    @classmethod
    def configuration_types(cls, value: object) -> object:
        from omnis.policy.ready_model_configuration import exact_configuration_types

        exact_configuration_types(value)
        return value

    @model_validator(mode="after")
    def model_preflight(self) -> Self:
        from omnis.modules.settings.catalog_schema import canonical

        if self.action == "model_configuration":
            from omnis.policy.ready_model_configuration import validate_ready_source

            if self.data_approval is not None:
                raise ValueError("Configuration decision is not a data approval")
            self.configuration = validate_ready_source(self.configuration)
            if len(canonical(self.model_dump(mode="json"))) > 3600:
                raise ValueError("Configuration command too large")
            return self
        if self.configuration is not None:
            raise ValueError("Configuration only belongs to its owner command")
        if self.action == "model_preflight":
            from omnis.modules.runs.model_dispatch import data_decision

            self.data_approval = data_decision(self.data_approval)
            # Leave framing/capability space inside the unchanged 4096-byte IPC.
            if len(canonical(self.model_dump(mode="json"))) > 3600:
                raise ValueError("Model preflight command too large")
        elif self.data_approval is not None:
            raise ValueError("Data decision only belongs to model preflight")
        return self

    @field_validator("owner_id", "command_id", "instance_id", mode="before")
    @classmethod
    def identity(cls, value: object) -> str:
        from omnis.modules.settings.candidate_catalog import uuid_string

        return uuid_string(value)

    @field_validator("manifest_ref", mode="before")
    @classmethod
    def manifest(cls, value: object) -> dict[str, object]:
        from omnis.modules.settings.candidate_catalog import valid_ref

        ref = valid_ref(value)
        if ref["kind"] != "launch-manifest":
            raise ValueError("Invalid launch manifest")
        return ref


class ControlRequest(StrictBody):
    version: VersionOne
    capability: str = Field(min_length=64, max_length=64, repr=False)
    command: Annotated[
        StatusCommand
        | PairingCommand
        | LifecycleCommand
        | ArmStopCommand
        | NativePrepareCommand
        | NativeTaskCommand,
        Field(discriminator="op"),
    ]
