"""Physical contracts for additive API-key Settings tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnis.core.schema import AuthoritySpec

PROVIDER_TABLES: dict[str, AuthoritySpec] = {
    "provider_connection_revision": (
        {
            "instance_id": ("uuid", True, None),
            "connection_id": ("uuid", True, None),
            "provider": ("text", True, None),
            "revision": ("bigint", True, None),
            "enabled": ("boolean", True, None),
            "secret_id": ("uuid", True, None),
            "credential_revision": ("bigint", True, None),
        },
        {
            (
                "provider_connection_revision_pkey",
                "p",
                "PRIMARY KEY (instance_id, connection_id, revision)",
                True,
                True,
            ),
            (
                "provider_connection_revision_instance_id_provider_revision_key",
                "u",
                "UNIQUE (instance_id, provider, revision)",
                True,
                True,
            ),
            (
                "provider_connection_revision_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "provider_connection_revision_provider_check",
                "c",
                "CHECK ((provider = ANY (ARRAY['openrouter'::text, 'orcarouter'::text])))",
                True,
                True,
            ),
            (
                "provider_connection_revision_revision_check",
                "c",
                "CHECK ((revision >= 1))",
                True,
                True,
            ),
            (
                "provider_connection_revision_credential_revision_check",
                "c",
                "CHECK ((credential_revision >= 1))",
                True,
                True,
            ),
        },
    ),
    "provider_selection_revision": (
        {
            "instance_id": ("uuid", True, None),
            "selection_id": ("uuid", True, None),
            "revision": ("bigint", True, None),
            "payload": ("jsonb", True, None),
        },
        {
            (
                "provider_selection_revision_pkey",
                "p",
                "PRIMARY KEY (instance_id, selection_id)",
                True,
                True,
            ),
            (
                "provider_selection_revision_instance_id_revision_key",
                "u",
                "UNIQUE (instance_id, revision)",
                True,
                True,
            ),
            (
                "provider_selection_revision_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "provider_selection_revision_revision_check",
                "c",
                "CHECK ((revision >= 1))",
                True,
                True,
            ),
            (
                "provider_selection_revision_payload_check",
                "c",
                "CHECK ((jsonb_typeof(payload) = 'object'::text))",
                True,
                True,
            ),
        },
    ),
    "provider_settings_command": (
        {
            "instance_id": ("uuid", True, None),
            "command_id": ("uuid", True, None),
            "request_digest": ("text", True, None),
            "result": ("jsonb", True, None),
        },
        {
            (
                "provider_settings_command_pkey",
                "p",
                "PRIMARY KEY (instance_id, command_id)",
                True,
                True,
            ),
            (
                "provider_settings_command_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "provider_settings_command_request_digest_check",
                "c",
                "CHECK ((request_digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
            (
                "provider_settings_command_result_check",
                "c",
                "CHECK ((jsonb_typeof(result) = 'object'::text))",
                True,
                True,
            ),
        },
    ),
}
