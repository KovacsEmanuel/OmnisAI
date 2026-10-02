"""Private Stop contracts, separate from the HTTP InstanceView projection."""

from json import dumps
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def canonical_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if type(value) is not str:
        raise ValueError("Canonical UUID required")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("Canonical UUID required")
    return parsed


def version_one(value: object) -> int:
    if type(value) is not int or value != 1:
        raise ValueError("Version 1 required")
    return value


def exact_json(value: object, depth: int = 0) -> bool:
    if depth > 16:
        return False
    if type(value) is dict:
        return all(type(key) is str and exact_json(item, depth + 1) for key, item in value.items())
    if type(value) is list:
        return all(exact_json(item, depth + 1) for item in value)
    return type(value) in (str, int, bool, type(None))


type CanonicalUUID = Annotated[UUID, BeforeValidator(canonical_uuid)]
type VersionOne = Annotated[Literal[1], BeforeValidator(version_one)]
type PositiveCounter = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


class StopBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    instance_id: CanonicalUUID
    command_id: CanonicalUUID
    finalize_command_id: CanonicalUUID
    generation: PositiveCounter
    owner_epoch: PositiveCounter
    daemon_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    inventory: dict[str, object]

    @field_validator("inventory", mode="before")
    @classmethod
    def inventory_shape(cls, value: object) -> object:
        if type(value) is not dict or not value or not exact_json(value):
            raise ValueError("Exact nonempty JSON inventory required")
        if len(dumps(value, separators=(",", ":")).encode()) > 8192:
            raise ValueError("Inventory too large")
        return value


class ArmStopCommand(StopBinding):
    op: Literal["arm_stop"]


class StopGrant(StopBinding):
    version: VersionOne
    state: Literal["STOP_PENDING", "STOP_UNCERTAIN"]
    owner_uuid: CanonicalUUID


def canonical_json(value: object) -> str:
    return dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
