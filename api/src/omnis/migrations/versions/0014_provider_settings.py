"""Add API-key Settings history, distinct from V1/native records."""

from alembic import op

revision = "0014_provider_settings"
down_revision = "0013_mission_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.provider_connection_revision (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            connection_id uuid NOT NULL,
            provider text NOT NULL CHECK (provider IN ('openrouter','orcarouter')),
            revision bigint NOT NULL CHECK (revision >= 1),
            enabled boolean NOT NULL,
            secret_id uuid NOT NULL,
            credential_revision bigint NOT NULL CHECK (credential_revision >= 1),
            PRIMARY KEY(instance_id, connection_id, revision),
            UNIQUE(instance_id, provider, revision)
        );
        CREATE TABLE public.provider_selection_revision (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            selection_id uuid NOT NULL,
            revision bigint NOT NULL CHECK (revision >= 1),
            payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
            PRIMARY KEY(instance_id, selection_id),
            UNIQUE(instance_id, revision)
        );
        CREATE TABLE public.provider_settings_command (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            command_id uuid NOT NULL,
            request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
            result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
            PRIMARY KEY(instance_id, command_id)
        );
        CREATE FUNCTION public.provider_settings_immutable() RETURNS trigger
            LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'provider Settings history is immutable';
        END;$$;
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_connection_revision
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable();
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_selection_revision
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable();
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_settings_command
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable()
    """)


def downgrade() -> None:
    raise RuntimeError("Credential history requires reviewed backup restoration")
