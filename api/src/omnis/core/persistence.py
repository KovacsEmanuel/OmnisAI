"""Validate dynamic driver values before they acquire concrete authority types."""

from collections.abc import Mapping
from datetime import datetime

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError


class DatabaseContractError(SQLAlchemyError):
    """Persisted data is incompatible; never expose the rejected value."""


class DatabaseRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


_INTEGER: TypeAdapter[int] = TypeAdapter(int)
_DATETIME: TypeAdapter[datetime] = TypeAdapter(datetime)


def read_record[T: DatabaseRecord](model: type[T], value: object) -> T:
    # Strict Pydantic models require a concrete dict, not the driver's RowMapping.
    # Normalize only the container; every field still undergoes strict validation.
    if isinstance(value, Mapping):
        value = dict(value)
    try:
        return model.model_validate(value)
    except ValidationError:
        raise DatabaseContractError("Persisted authority violates its type contract") from None


def read_integer(value: object) -> int:
    try:
        return _INTEGER.validate_python(value, strict=True)
    except ValidationError:
        raise DatabaseContractError("Persisted authority requires an integer") from None


def read_datetime(value: object) -> datetime:
    try:
        return _DATETIME.validate_python(value, strict=True)
    except ValidationError:
        raise DatabaseContractError("Persisted authority requires a timestamp") from None
