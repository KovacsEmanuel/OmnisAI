"""Typed read contracts for the existing instance authority tables."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from omnis.core.persistence import DatabaseRecord

type CommandKind = Literal["OPEN", "SHUTDOWN", "FINALIZE"]


class InstanceRecord(DatabaseRecord):
    id: int
    instance_id: UUID
    admission_open: bool
    shutdown_command_id: UUID | None
    generation: int
    quiesced_generation: int | None
    quiesced_at: datetime | None


class LeaseRecord(DatabaseRecord):
    id: int
    owner: UUID | None
    epoch: int
    expires_at: datetime | None


class CommandRecord(DatabaseRecord):
    command_id: UUID
    kind: CommandKind
    expected_generation: int
    result_generation: int
    owner_epoch: int
