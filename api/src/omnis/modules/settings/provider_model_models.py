"""Bounded configured models; independent of historical Settings/role DTOs."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from omnis.modules.settings.provider_key_models import (
    Identity,
    KeyDTO,
    ModelSelection,
    PositiveRevision,
    Revision,
)

REGISTRY_FRAME_LIMIT = 65536


class ModelEntry(ModelSelection):
    entry_id: Identity
    revision: PositiveRevision


class SaveModel(KeyDTO):
    entry_id: Identity
    expected_revision: Revision
    model: str = Field(min_length=1, max_length=256, pattern=r"^[!-~]+$")
    output_tokens: int = Field(strict=True, ge=1, le=65536)


class SaveModels(KeyDTO):
    action: Literal["save_models"]
    command_id: Identity
    expected_registry_revision: Revision
    connection_id: Identity
    connection_revision: PositiveRevision
    models: list[SaveModel] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({item.entry_id for item in self.models}) != len(self.models) or len(
            {item.model for item in self.models}
        ) != len(self.models):
            raise ValueError("Duplicate configured model")
        return self


class ReadModels(KeyDTO):
    action: Literal["read"]
    command_id: Identity | None = None
    registry_revision: Revision | None = None
    after: Identity | None = None

    @model_validator(mode="after")
    def context(self) -> Self:
        if self.command_id is not None and (
            self.registry_revision is not None or self.after is not None
        ):
            raise ValueError("Receipt read cannot be paged")
        if self.after is not None and self.registry_revision is None:
            raise ValueError("Page requires registry revision")
        return self


class ModelRegistryControl(KeyDTO):
    op: Literal["provider_models"]
    request: Annotated[SaveModels | ReadModels, Field(discriminator="action")]

    def wire(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def wire_bytes(self) -> bytes:
        return self.model_dump_json().encode()


class RegistryState(KeyDTO):
    revision: Revision
    entries: list[ModelEntry] = Field(max_length=64)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({item.entry_id for item in self.entries}) != len(self.entries) or len(
            {(item.connection_id, item.model) for item in self.entries}
        ) != len(self.entries):
            raise ValueError("Duplicate configured model")
        if self.revision == 0 and self.entries:
            raise ValueError("Invalid registry revision")
        return self


class ModelRegistryView(KeyDTO):
    schema_version: Literal[1] = 1
    command_id: Identity | None
    registry_revision: Revision
    after: Identity | None
    next_after: Identity | None
    total: int = Field(strict=True, ge=0, le=64)
    entries: list[ModelEntry] = Field(max_length=16)

    @model_validator(mode="after")
    def page(self) -> Self:
        ids = [item.entry_id for item in self.entries]
        if ids != sorted(set(ids)) or len(
            {(item.connection_id, item.model) for item in self.entries}
        ) != len(ids):
            raise ValueError("Invalid registry page")
        if self.total < len(ids) or (self.total > 0 and self.registry_revision == 0):
            raise ValueError("Invalid registry total")
        if self.after is None:
            if len(ids) != min(16, self.total) or (self.total > 16) != (
                self.next_after is not None
            ):
                raise ValueError("Incomplete registry page")
        elif not ids or ids[0] <= self.after:
            raise ValueError("Invalid registry cursor")
        if self.next_after is not None and (
            len(ids) != 16 or self.next_after != ids[-1] or self.total <= len(ids)
        ):
            raise ValueError("Invalid continuation")
        if len(self.model_dump_json().encode()) > REGISTRY_FRAME_LIMIT:
            raise ValueError("Registry response too large")
        return self
