"""API-key Settings only; legacy native Settings DTOs remain unchanged."""

import json
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

type Revision = Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]
type PositiveRevision = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]
type Identity = Annotated[str, Field(pattern=r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")]
type Provider = Literal["openrouter", "orcarouter"]
type ModelRole = Literal["default", "brain", "recon", "investigator", "validator"]
MODEL_ROLES: tuple[ModelRole, ...] = ("default", "brain", "recon", "investigator", "validator")


class KeyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class SaveConnection(KeyDTO):
    action: Literal["save_connection"]
    command_id: Identity
    connection_id: Identity
    expected_revision: Revision
    provider: Provider
    secret: SecretStr = Field(repr=False)

    @field_validator("secret", mode="before")
    @classmethod
    def bounded_secret(cls, value: object) -> object:
        from omnis.modules.settings.provider_vault import _secret

        return _secret(value)


class RevokeConnection(KeyDTO):
    action: Literal["revoke_connection"]
    command_id: Identity
    connection_id: Identity
    expected_revision: PositiveRevision


class ModelSelection(KeyDTO):
    connection_id: Identity
    connection_revision: PositiveRevision
    model: str = Field(min_length=1, max_length=256, pattern=r"^[!-~]+$")
    output_tokens: int = Field(strict=True, ge=1, le=65536)


class SaveSelection(KeyDTO):
    action: Literal["save_selection"]
    command_id: Identity
    expected_revision: Revision
    default: ModelSelection
    brain: ModelSelection | None
    investigator: ModelSelection | None
    validator: ModelSelection | None


class ReadSettings(KeyDTO):
    action: Literal["read"]
    command_id: Identity | None = None


class SaveSelectionV2(KeyDTO):
    action: Literal["save_selection_v2"]
    command_id: Identity
    expected_revision: Revision
    default: ModelSelection
    brain: ModelSelection | None
    investigator: ModelSelection | None
    validator: ModelSelection | None
    recon: ModelSelection | None


type SettingsRequest = Annotated[
    SaveConnection | RevokeConnection | SaveSelection | SaveSelectionV2 | ReadSettings,
    Field(discriminator="action"),
]


class KeySettingsControl(KeyDTO):
    op: Literal["provider_settings"]
    request: SettingsRequest

    def wire(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        if isinstance(self.request, SaveConnection):
            payload["request"]["secret"] = self.request.secret.get_secret_value()
        return payload

    def wire_bytes(self) -> bytes:
        return json.dumps(self.wire(), separators=(",", ":"), allow_nan=False).encode()

    @model_validator(mode="after")
    def size(self) -> Self:
        if len(self.wire_bytes()) > 3600:
            raise ValueError("Settings command too large")
        return self


class ConnectionView(KeyDTO):
    connection_id: Identity
    provider: Provider
    revision: PositiveRevision
    enabled: bool
    credential_present: bool


class SelectionView(KeyDTO):
    selection_id: Identity
    revision: PositiveRevision
    default: ModelSelection
    brain: ModelSelection | None
    investigator: ModelSelection | None
    validator: ModelSelection | None


class SelectionViewV2(SelectionView):
    schema_version: Literal[2]
    recon: ModelSelection | None


class KeySettingsView(KeyDTO):
    schema_version: Literal[2] = 2
    command_id: Identity | None
    vault_status: Literal["LOCKED", "UNLOCKED", "UNCONFIGURED"]
    connections: list[ConnectionView] = Field(max_length=2)
    selection: SelectionView | SelectionViewV2 | None
    reachable: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"

    @model_validator(mode="after")
    def size(self) -> Self:
        if len(self.model_dump_json().encode()) > 4096:
            raise ValueError("Settings response too large")
        return self
