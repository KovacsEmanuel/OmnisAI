"""Small typed DTOs shared by HTTP and local control, never ORM serialization."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class ControlRequest(StrictBody):
    version: Literal[1]
    capability: str = Field(min_length=64, max_length=64, repr=False)
    command: Annotated[StatusCommand | PairingCommand | LifecycleCommand, Field(discriminator="op")]
