"""Transport-independent instance state; no framework or runtime imports."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ControlCode(StrEnum):
    SUPERVISOR_OWNED = "SUPERVISOR_OWNED"
    LEASE_LOST = "LEASE_LOST"
    INSTANCE_SHUTTING_DOWN = "INSTANCE_SHUTTING_DOWN"
    SHUTDOWN_INCOMPLETE = "SHUTDOWN_INCOMPLETE"
    RESTART_REQUIRED = "RESTART_REQUIRED"
    COMMAND_CONFLICT = "COMMAND_CONFLICT"
    GENERATION_CONFLICT = "GENERATION_CONFLICT"
    ALREADY_OPEN = "ALREADY_OPEN"


class ControlConflict(Exception):
    def __init__(self, code: ControlCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class InstanceStatus:
    instance_id: UUID
    generation: int
    admission_open: bool
    shutdown_command_id: UUID | None
    quiesced_generation: int | None
    supervisor_epoch: int
    supervisor_ready: bool
    shutdown_finalized: bool
    assessment_ready: bool = False
    dashboard_ready: bool = False
