"""Pinned physical PostgreSQL 18 contracts for the additive ModelTest consumer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnis.core.schema import AuthoritySpec

RELAY_AUTHORITY_GUARD = """BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM 1 FROM public.instance_control WHERE instance_id=NEW.instance_id FOR UPDATE;
        IF NEW.state <> 'ACTIVE' OR NEW.operation_serial <> (
            SELECT COALESCE(max(operation_serial),0)+1 FROM public.model_relay_authority
            WHERE instance_id=NEW.instance_id
        ) THEN
            RAISE EXCEPTION 'relay serial must extend the admitted prefix';
        END IF;
    ELSIF OLD.state <> 'ACTIVE' OR NEW.state <> 'DRAINED'
        OR (to_jsonb(NEW)-'state') IS DISTINCT FROM (to_jsonb(OLD)-'state') THEN
        RAISE EXCEPTION 'original relay authority is immutable';
    END IF;
    RETURN NEW;
END;"""

RELAY_TABLES: dict[str, AuthoritySpec] = {
    "model_relay_authority": (
        {
            "instance_id": ("uuid", True, None),
            "kind": ("text", True, None),
            "id": ("uuid", True, None),
            "execution_owner_id": ("uuid", True, None),
            "generation": ("bigint", True, None),
            "owner_epoch": ("bigint", True, None),
            "cancel_epoch": ("bigint", True, None),
            "deadline": ("text", True, None),
            "provider": ("text", True, None),
            "operation_serial": ("bigint", True, None),
            "state": ("text", True, None),
        },
        {
            ("model_relay_authority_pkey", "p", "PRIMARY KEY (instance_id, kind, id)", True, True),
            (
                "model_relay_authority_instance_id_operation_serial_key",
                "u",
                "UNIQUE (instance_id, operation_serial)",
                True,
                True,
            ),
            (
                "model_relay_authority_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "model_relay_authority_kind_check",
                "c",
                "CHECK ((kind = ANY (ARRAY['MODEL_DISPATCH'::text, 'METADATA_COMMAND'::text])))",
                True,
                True,
            ),
            (
                "model_relay_authority_generation_check",
                "c",
                "CHECK ((generation >= 0))",
                True,
                True,
            ),
            (
                "model_relay_authority_owner_epoch_check",
                "c",
                "CHECK ((owner_epoch > 0))",
                True,
                True,
            ),
            (
                "model_relay_authority_cancel_epoch_check",
                "c",
                "CHECK ((cancel_epoch > 0))",
                True,
                True,
            ),
            (
                "model_relay_authority_operation_serial_check",
                "c",
                "CHECK ((operation_serial > 0))",
                True,
                True,
            ),
            (
                "model_relay_authority_provider_check",
                "c",
                "CHECK ((provider = ANY (ARRAY['openrouter'::text, 'orcarouter'::text])))",
                True,
                True,
            ),
            (
                "model_relay_authority_state_check",
                "c",
                "CHECK ((state = ANY (ARRAY['ACTIVE'::text, 'DRAINED'::text])))",
                True,
                True,
            ),
            (
                "model_relay_authority_deadline_check",
                "c",
                "CHECK (((length(deadline) <= 32) AND (deadline ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?[+]00:00$'::text) AND isfinite((deadline)::timestamp with time zone)))",
                True,
                True,
            ),
        },
    ),
}

MODEL_TABLES: dict[str, AuthoritySpec] = {
    "model_command_v2": (
        {
            "action": ("text", True, None),
            "command_id": ("uuid", True, None),
            "created_at": ("timestamp with time zone", True, "clock_timestamp()"),
            "instance_id": ("uuid", True, None),
            "operation_id": ("uuid", False, None),
            "request_digest": ("text", True, None),
        },
        {
            (
                "model_command_v2_action_check",
                "c",
                "CHECK ((action = ANY (ARRAY['start'::text, 'cancel'::text, 'refresh'::text])))",
                True,
                True,
            ),
            (
                "model_command_v2_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            ("model_command_v2_pkey", "p", "PRIMARY KEY (instance_id, command_id)", True, True),
            (
                "model_command_v2_request_digest_check",
                "c",
                "CHECK ((request_digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
        },
    ),
    "model_dispatch_event_v2": (
        {
            "created_at": ("timestamp with time zone", True, "clock_timestamp()"),
            "dispatch_attempt_id": ("uuid", True, None),
            "instance_id": ("uuid", True, None),
            "receipt_ref": ("jsonb", False, None),
            "sequence": ("smallint", True, None),
            "state": ("text", True, None),
        },
        {
            (
                "model_dispatch_event_v2_instance_id_dispatch_attempt_id_fkey",
                "f",
                "FOREIGN KEY (instance_id, dispatch_attempt_id) REFERENCES "
                "model_dispatch_v2(instance_id, dispatch_attempt_id)",
                True,
                True,
            ),
            (
                "model_dispatch_event_v2_instance_id_dispatch_attempt_id_sta_key",
                "u",
                "UNIQUE (instance_id, dispatch_attempt_id, state)",
                True,
                True,
            ),
            (
                "model_dispatch_event_v2_pkey",
                "p",
                "PRIMARY KEY (instance_id, dispatch_attempt_id, sequence)",
                True,
                True,
            ),
            (
                "model_dispatch_event_v2_sequence_check",
                "c",
                "CHECK (((sequence >= 1) AND (sequence <= 3)))",
                True,
                True,
            ),
            (
                "model_dispatch_event_v2_state_check",
                "c",
                "CHECK ((state = ANY (ARRAY['RESERVED'::text, 'SENT'::text, "
                "'SETTLED'::text, 'RELEASED'::text])))",
                True,
                True,
            ),
        },
    ),
    "model_dispatch_v2": (
        {
            "dispatch_attempt_id": ("uuid", True, None),
            "instance_id": ("uuid", True, None),
            "operation_id": ("uuid", True, None),
            "payload": ("jsonb", True, None),
        },
        {
            (
                "model_dispatch_v2_instance_id_operation_id_fkey",
                "f",
                "FOREIGN KEY (instance_id, operation_id) REFERENCES "
                "system_operation(instance_id, operation_id)",
                True,
                True,
            ),
            (
                "model_dispatch_v2_instance_id_operation_id_key",
                "u",
                "UNIQUE (instance_id, operation_id)",
                True,
                True,
            ),
            (
                "model_dispatch_v2_payload_check",
                "c",
                "CHECK ((jsonb_typeof(payload) = 'object'::text))",
                True,
                True,
            ),
            (
                "model_dispatch_v2_pkey",
                "p",
                "PRIMARY KEY (instance_id, dispatch_attempt_id)",
                True,
                True,
            ),
        },
    ),
    "model_record_v2": (
        {
            "created_at": ("timestamp with time zone", True, "clock_timestamp()"),
            "digest": ("text", True, None),
            "id": ("uuid", True, None),
            "instance_id": ("uuid", True, None),
            "kind": ("text", True, None),
            "payload": ("jsonb", True, None),
            "revision": ("bigint", True, None),
        },
        {
            (
                "model_record_v2_digest_check",
                "c",
                "CHECK ((digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
            (
                "model_record_v2_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            (
                "model_record_v2_instance_id_kind_id_revision_digest_key",
                "u",
                "UNIQUE (instance_id, kind, id, revision, digest)",
                True,
                True,
            ),
            (
                "model_record_v2_payload_check",
                "c",
                "CHECK ((jsonb_typeof(payload) = 'object'::text))",
                True,
                True,
            ),
            ("model_record_v2_pkey", "p", "PRIMARY KEY (instance_id, id)", True, True),
            ("model_record_v2_revision_check", "c", "CHECK ((revision = 1))", True, True),
        },
    ),
    "system_operation": (
        {
            "cancel_epoch": ("bigint", True, None),
            "command_id": ("uuid", True, None),
            "config_snapshot_ref": ("jsonb", True, None),
            "deadline": ("timestamp with time zone", True, None),
            "execution_owner_id": ("uuid", True, None),
            "finish_reason": ("text", False, None),
            "generation": ("bigint", True, None),
            "input_projection_ref": ("jsonb", True, None),
            "instance_id": ("uuid", True, None),
            "operation_id": ("uuid", True, None),
            "outcome_ref": ("jsonb", False, None),
            "owner_epoch": ("bigint", True, None),
            "payload_digest": ("text", True, None),
            "purpose": ("text", True, None),
            "schema_version": ("smallint", True, None),
            "state": ("text", True, None),
            "state_revision": ("bigint", True, None),
        },
        {
            ("system_operation_cancel_epoch_check", "c", "CHECK ((cancel_epoch >= 1))", True, True),
            ("system_operation_check", "c", "CHECK ((command_id = operation_id))", True, True),
            (
                "system_operation_finish_reason_check",
                "c",
                "CHECK ((finish_reason = ANY (ARRAY['COMPLETED'::text, 'FAILED'::text, "
                "'CANCELLED'::text, 'DEADLINE'::text, 'OWNER_LOST'::text])))",
                True,
                True,
            ),
            ("system_operation_generation_check", "c", "CHECK ((generation >= 0))", True, True),
            (
                "system_operation_instance_id_command_id_key",
                "u",
                "UNIQUE (instance_id, command_id)",
                True,
                True,
            ),
            (
                "system_operation_instance_id_fkey",
                "f",
                "FOREIGN KEY (instance_id) REFERENCES instance_control(instance_id)",
                True,
                True,
            ),
            ("system_operation_owner_epoch_check", "c", "CHECK ((owner_epoch >= 1))", True, True),
            (
                "system_operation_payload_digest_check",
                "c",
                "CHECK ((payload_digest ~ '^[0-9a-f]{64}$'::text))",
                True,
                True,
            ),
            ("system_operation_pkey", "p", "PRIMARY KEY (instance_id, operation_id)", True, True),
            (
                "system_operation_purpose_check",
                "c",
                "CHECK ((purpose = 'SETTINGS_TEST'::text))",
                True,
                True,
            ),
            (
                "system_operation_schema_version_check",
                "c",
                "CHECK ((schema_version = 1))",
                True,
                True,
            ),
            (
                "system_operation_state_check",
                "c",
                "CHECK ((state = ANY (ARRAY['PENDING'::text, 'RUNNING'::text, "
                "'STOPPING'::text, 'FINISHED'::text, 'NEEDS_RECONCILIATION'::text])))",
                True,
                True,
            ),
            (
                "system_operation_state_revision_check",
                "c",
                "CHECK ((state_revision >= 1))",
                True,
                True,
            ),
        },
    ),
    "system_operation_event": (
        {
            "instance_id": ("uuid", True, None),
            "operation_id": ("uuid", True, None),
            "payload": ("jsonb", True, None),
            "state_revision": ("bigint", True, None),
        },
        {
            (
                "system_operation_event_instance_id_operation_id_fkey",
                "f",
                "FOREIGN KEY (instance_id, operation_id) REFERENCES "
                "system_operation(instance_id, operation_id)",
                True,
                True,
            ),
            (
                "system_operation_event_payload_check",
                "c",
                "CHECK ((jsonb_typeof(payload) = 'object'::text))",
                True,
                True,
            ),
            (
                "system_operation_event_pkey",
                "p",
                "PRIMARY KEY (instance_id, operation_id, state_revision)",
                True,
                True,
            ),
            (
                "system_operation_event_state_revision_check",
                "c",
                "CHECK ((state_revision >= 1))",
                True,
                True,
            ),
        },
    ),
}
