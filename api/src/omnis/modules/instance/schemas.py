"""Small typed DTOs shared by HTTP and local control, never ORM serialization."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omnis.modules.instance.stop_contract import ArmStopCommand, VersionOne
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.settings.provider_models import SettingsControl

# Existing 4s non-runtime work on each side of the 6s launch/refusal wait; not authority.
MODEL_TEST_PREPARE_WAIT_SECONDS = 4 + 6 + 4


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
    action: Literal[
        "stage",
        "release",
        "receive",
        "model_preflight",
        "model_configuration",
        "model_initialization",
        "model_test_prepare",
        "model_test_start",
        "model_test_send",
        "model_protocol_prepare",
        "model_protocol_validation",
    ]
    manifest_ref: dict[str, object]
    data_approval: dict[str, object] | None = Field(
        default=None, repr=False, exclude_if=lambda v: v is None
    )
    configuration: dict[str, object] | None = Field(
        default=None, repr=False, exclude_if=lambda v: v is None
    )
    provider_config_ref: dict[str, object] | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    settings_operation_id: str | None = Field(default=None, exclude_if=lambda v: v is None)
    initialization_id: str | None = Field(default=None, exclude_if=lambda v: v is None)
    protocol_id: str | None = Field(default=None, exclude_if=lambda v: v is None)
    protocol_caps: dict[str, object] | None = Field(default=None, exclude_if=lambda v: v is None)

    @field_validator("configuration", mode="before")
    @classmethod
    def configuration_types(cls, value: object) -> object:
        from omnis.policy.ready_model_configuration import exact_configuration_types

        exact_configuration_types(value)
        return value

    @model_validator(mode="after")
    def model_preflight(self) -> Self:
        from omnis.modules.settings.catalog_schema import canonical

        if self.action in {"model_test_prepare", "model_test_start"}:
            from omnis.modules.settings.candidate_catalog import uuid_string

            self.initialization_id = uuid_string(self.initialization_id)
            self.settings_operation_id = uuid_string(self.settings_operation_id)
            if any(
                v is not None
                for v in (
                    self.configuration,
                    self.provider_config_ref,
                    self.data_approval,
                    self.protocol_id,
                    self.protocol_caps,
                )
            ):
                raise ValueError("Preparation consumes saved native Settings only")
            if len(canonical(self.model_dump(mode="json"))) > 3600:
                raise ValueError("Preparation command too large")
            return self
        if self.action == "model_test_send":
            from omnis.modules.runs.model_dispatch import data_decision
            from omnis.modules.settings.candidate_catalog import uuid_string

            self.initialization_id = uuid_string(self.initialization_id)
            self.protocol_id = uuid_string(self.protocol_id)
            self.data_approval = data_decision(self.data_approval)
            if any(
                v is not None
                for v in (
                    self.settings_operation_id,
                    self.configuration,
                    self.provider_config_ref,
                    self.protocol_caps,
                )
            ):
                raise ValueError("Execution consumes its own saved configuration")
            if len(canonical(self.model_dump(mode="json"))) > 3600:
                raise ValueError("Execution command too large")
            return self
        if self.settings_operation_id is not None:
            raise ValueError("Settings reference only belongs to preparation")
        if self.action in {"model_protocol_prepare", "model_protocol_validation"}:
            from omnis.modules.runs.model_dispatch import data_decision
            from omnis.modules.settings.candidate_catalog import uuid_string
            from omnis.modules.tasks.managed_contract import exact, integer, ref

            if self.configuration is not None or self.initialization_id is not None:
                raise ValueError("Protocol consumes owned source only")
            self.protocol_id = uuid_string(self.protocol_id)
            self.provider_config_ref = ref(self.provider_config_ref, "provider-config")
            self.data_approval = data_decision(self.data_approval)
            self.protocol_caps = exact(
                self.protocol_caps, {"calls", "output_tokens", "wall_seconds"}
            )
            for key, maximum in (("calls", 1), ("output_tokens", 64), ("wall_seconds", 3)):
                integer(self.protocol_caps[key], 1, maximum)
            if len(canonical(self.model_dump(mode="json"))) > 3600:
                raise ValueError("Protocol command too large")
            return self
        if self.protocol_id is not None or self.protocol_caps is not None:
            raise ValueError("Protocol fields only belong to protocol commands")
        if self.action == "model_initialization":
            from omnis.modules.settings.candidate_catalog import uuid_string
            from omnis.modules.tasks.managed_contract import ref

            if self.configuration is not None or self.data_approval is not None:
                raise ValueError("Initialization consumes owned source, not caller configuration")
            self.provider_config_ref = ref(self.provider_config_ref, "provider-config")
            self.initialization_id = uuid_string(self.initialization_id)
            if len(canonical(self.model_dump(mode="json"))) > 3600:
                raise ValueError("Initialization command too large")
            return self
        if self.provider_config_ref is not None or self.initialization_id is not None:
            raise ValueError("Initialization fields only belong to initialization")
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
        | NativeTaskCommand
        | ModelTestControl
        | SettingsControl,
        Field(discriminator="op"),
    ]
