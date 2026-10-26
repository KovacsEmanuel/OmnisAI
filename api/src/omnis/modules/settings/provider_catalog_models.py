"""Connection-scoped bounded catalog DTOs; no provider IO on local reads/search."""

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from omnis.modules.settings.provider_key_models import Identity, KeyDTO, PositiveRevision, Provider

type CatalogReason = Literal[
    "SCHEMA_UNSUPPORTED",
    "CONTINUATION_UNSUPPORTED",
    "TOTAL_MISMATCH",
    "CATALOG_LIMIT",
    "METADATA_UNAVAILABLE",
    "CANCELLED_OR_STOPPED",
    "OWNER_LOST",
    "CONNECTION_STALE",
    "ROW_UNSUPPORTED",
]


class CatalogModel(KeyDTO):
    model: str = Field(min_length=1, max_length=256, pattern=r"^[!-~]+$")
    name: str | None = Field(default=None, max_length=128)
    max_output_tokens: int | None = Field(default=None, strict=True, ge=1, le=65536)
    supports_max_tokens: bool | None = None
    reason: CatalogReason | None = None

    @field_validator("name")
    @classmethod
    def unicode_name(cls, value: str | None) -> str | None:
        if value is not None:
            value.encode("utf-8")
        return value


class CatalogContext(KeyDTO):
    connection_id: Identity
    connection_revision: PositiveRevision


class RefreshCatalog(CatalogContext):
    action: Literal["refresh"]
    command_id: Identity


class SearchCatalog(CatalogContext):
    action: Literal["search"]
    catalog_command_id: Identity | None = None
    query: str = Field(default="", max_length=256)
    offset: int = Field(default=0, strict=True, ge=0, le=8192, multiple_of=16)

    @field_validator("query")
    @classmethod
    def unicode(cls, value: str) -> str:
        value.encode("utf-8")
        return value

    @model_validator(mode="after")
    def context(self) -> Self:
        if self.offset and self.catalog_command_id is None:
            raise ValueError("Page requires catalog context")
        return self


class CancelCatalog(CatalogContext):
    action: Literal["cancel"]
    command_id: Identity
    catalog_command_id: Identity


class CatalogControl(KeyDTO):
    op: Literal["provider_catalog"]
    request: Annotated[
        RefreshCatalog | SearchCatalog | CancelCatalog, Field(discriminator="action")
    ]

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if len(self.model_dump_json().encode()) > 3600:
            raise ValueError("Catalog command too large")
        return self


class CatalogView(CatalogContext):
    schema_version: Literal[1] = 1
    provider: Provider
    catalog_command_id: Identity | None
    state: Literal["NOT_REQUESTED", "PENDING", "READY", "PARTIAL", "FAILED", "STALE"]
    reason: CatalogReason | None = None
    query: str = Field(max_length=256)
    offset: int = Field(strict=True, ge=0, le=8192, multiple_of=16)
    next_offset: int | None = Field(default=None, strict=True, ge=16, le=8192, multiple_of=16)
    total: int = Field(strict=True, ge=0, le=8192)
    entries: list[CatalogModel] = Field(max_length=16)

    @model_validator(mode="after")
    def page(self) -> Self:
        if self.state in {"NOT_REQUESTED", "PENDING", "READY"}:
            if self.reason is not None:
                raise ValueError("Unexpected catalog failure")
        elif self.reason is None:
            raise ValueError("Catalog failure requires a reason")
        if self.state == "NOT_REQUESTED":
            if self.catalog_command_id is not None:
                raise ValueError("Unexpected catalog command")
        elif self.state != "STALE" and self.catalog_command_id is None:
            raise ValueError("Catalog command required")
        ids = [item.model for item in self.entries]
        if ids != sorted(ids):
            raise ValueError("Catalog page order")
        if len(self.entries) != min(16, max(0, self.total - self.offset)):
            raise ValueError("Incomplete local page")
        expected = self.offset + 16 if self.offset + len(self.entries) < self.total else None
        if self.next_offset != expected or len({x.model for x in self.entries}) != len(
            self.entries
        ):
            raise ValueError("Invalid catalog continuation")
        if self.state in {"NOT_REQUESTED", "PENDING", "FAILED", "STALE"} and self.total:
            raise ValueError("Unavailable catalog cannot be eligible")
        return self
