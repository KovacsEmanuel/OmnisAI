"""Small typed DTOs shared by HTTP and local control, never ORM serialization."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class ControlRequest(StrictBody):
    version: VersionOne
    capability: str = Field(min_length=64, max_length=64, repr=False)
    command: Annotated[
        StatusCommand | PairingCommand | LifecycleCommand | ArmStopCommand | NativePrepareCommand,
        Field(discriminator="op"),
    ]
