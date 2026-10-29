"""Physical contracts for additive API-key Settings tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnis.core.schema import AuthoritySpec

MODEL_RETIRE_GUARD = """BEGIN
        IF OLD.removed_registry_revision IS NOT NULL OR NEW.removed_registry_revision IS NULL
            OR (NEW.instance_id, NEW.entry_id, NEW.connection_id, NEW.model)
                IS DISTINCT FROM (OLD.instance_id, OLD.entry_id, OLD.connection_id, OLD.model) THEN
            RAISE EXCEPTION 'model identity and retirement are immutable';
        END IF;
        RETURN NEW;
        END;"""

PROVIDER_TABLES: dict[str, AuthoritySpec] = {
    "provider_model_registry_revision": (
        {
            "instance_id": ("uuid", True, None),
            "revision": ("bigint", True, None),
        },
        {
            (
                "provider_model_registry_revision_pkey",
                "p",
                "PRIMARY KEY (instance_id, revision)",
                True,
                True,
            ),
            (
                "provider_model_registry_revision_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "provider_model_registry_revision_revision_check",
                "c",
                "CHECK ((revision >= 1))",
                True,
                True,
            ),
        },
    ),
    "provider_model_entry": (
        {
            "instance_id": ("uuid", True, None),
            "entry_id": ("uuid", True, None),
            "connection_id": ("uuid", True, None),
            "model": ("text", True, None),
            "removed_registry_revision": ("bigint", False, None),
        },
        {
            ("provider_model_entry_pkey", "p", "PRIMARY KEY (instance_id, entry_id)", True, True),
            (
                "provider_model_entry_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "provider_model_removed_registry_fk",
                "f",
                "FOREIGN KEY (instance_id, removed_registry_revision) REFERENCES provider_model_registry_revision(instance_id, revision)",
                True,
                True,
            ),
            (
                "provider_model_entry_instance_id_entry_id_connection_id_key",
                "u",
                "UNIQUE (instance_id, entry_id, connection_id)",
                True,
                True,
            ),
            (
                "provider_model_entry_model_check",
                "c",
                "CHECK ((model ~ '^[!-~]{1,255}[!-~]?$'::text))",
                True,
                True,
            ),
        },
    ),
    "provider_model_entry_revision": (
        {
            "instance_id": ("uuid", True, None),
            "entry_id": ("uuid", True, None),
            "revision": ("bigint", True, None),
            "connection_id": ("uuid", True, None),
            "connection_revision": ("bigint", True, None),
            "registry_revision": ("bigint", True, None),
            "output_tokens": ("integer", True, None),
        },
        {
            (
                "provider_model_entry_revision_pkey",
                "p",
                "PRIMARY KEY (instance_id, entry_id, revision)",
                True,
                True,
            ),
            (
                "provider_model_entry_registry_key",
                "u",
                "UNIQUE (instance_id, entry_id, registry_revision)",
                True,
                True,
            ),
            (
                "provider_model_entry_identity_fk",
                "f",
                "FOREIGN KEY (instance_id, entry_id, connection_id) REFERENCES provider_model_entry(instance_id, entry_id, connection_id)",
                True,
                True,
            ),
            (
                "provider_model_entry_connection_fk",
                "f",
                "FOREIGN KEY (instance_id, connection_id, connection_revision) REFERENCES provider_connection_revision(instance_id, connection_id, revision)",
                True,
                True,
            ),
            (
                "provider_model_entry_registry_fk",
                "f",
                "FOREIGN KEY (instance_id, registry_revision) REFERENCES provider_model_registry_revision(instance_id, revision)",
                True,
                True,
            ),
            (
                "provider_model_entry_revision_revision_check",
                "c",
                "CHECK ((revision >= 1))",
                True,
                True,
            ),
            (
                "provider_model_entry_revision_connection_revision_check",
                "c",
                "CHECK ((connection_revision >= 1))",
                True,
                True,
            ),
            (
                "provider_model_entry_revision_registry_revision_check",
                "c",
                "CHECK ((registry_revision >= 1))",
                True,
                True,
            ),
            (
                "provider_model_entry_revision_output_tokens_check",
                "c",
                "CHECK (((output_tokens >= 1) AND (output_tokens <= 65536)))",
                True,
                True,
            ),
        },
    ),
    "provider_model_command": (
        {
            "instance_id": ("uuid", True, None),
            "command_id": ("uuid", True, None),
            "request_digest": ("text", True, None),
            "result": ("jsonb", True, None),
        },
        {
            (
                "provider_model_command_pkey",
                "p",
                "PRIMARY KEY (instance_id, command_id)",
                True,
                True,
            ),
            (
                "provider_model_command_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "provider_model_command_request_digest_check",
                "c",
                "CHECK ((request_digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
            (
                "provider_model_command_result_check",
                "c",
                "CHECK ((jsonb_typeof(result) = 'object'::text))",
                True,
                True,
            ),
        },
    ),
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
