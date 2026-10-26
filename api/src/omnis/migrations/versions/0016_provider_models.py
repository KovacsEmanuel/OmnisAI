"""Add typed immutable configured models/receipts; retain all old Settings bytes."""

from alembic import op

revision = "0016_provider_models"
down_revision = "0015_model_test_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.provider_model_registry_revision (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            revision bigint NOT NULL CHECK (revision >= 1),
            PRIMARY KEY(instance_id, revision)
        );
        CREATE TABLE public.provider_model_entry (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            entry_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            model text COLLATE "C" NOT NULL CHECK (model ~ '^[!-~]{1,255}[!-~]?$'),
            PRIMARY KEY(instance_id, entry_id),
            UNIQUE(instance_id, connection_id, model),
            UNIQUE(instance_id, entry_id, connection_id)
        );
        CREATE TABLE public.provider_model_entry_revision (
            instance_id uuid NOT NULL,
            entry_id uuid NOT NULL,
            revision bigint NOT NULL CHECK (revision >= 1),
            connection_id uuid NOT NULL,
            connection_revision bigint NOT NULL CHECK (connection_revision >= 1),
            registry_revision bigint NOT NULL CHECK (registry_revision >= 1),
            output_tokens integer NOT NULL CHECK (output_tokens BETWEEN 1 AND 65536),
            PRIMARY KEY(instance_id, entry_id, revision),
            CONSTRAINT provider_model_entry_registry_key UNIQUE(instance_id, entry_id, registry_revision),
            CONSTRAINT provider_model_entry_identity_fk FOREIGN KEY(instance_id, entry_id, connection_id)
                REFERENCES public.provider_model_entry(instance_id, entry_id, connection_id),
            CONSTRAINT provider_model_entry_connection_fk FOREIGN KEY(instance_id, connection_id, connection_revision)
                REFERENCES public.provider_connection_revision(instance_id, connection_id, revision),
            CONSTRAINT provider_model_entry_registry_fk FOREIGN KEY(instance_id, registry_revision)
                REFERENCES public.provider_model_registry_revision(instance_id, revision)
        );
        CREATE TABLE public.provider_model_command (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            command_id uuid NOT NULL,
            request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
            result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
            PRIMARY KEY(instance_id, command_id)
        );
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_model_registry_revision
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable();
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_model_entry
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable();
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_model_entry_revision
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable();
        CREATE TRIGGER provider_settings_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.provider_model_command
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable()
    """)
    backfill()


def backfill() -> None:
    # Default wins only the entry cap; distinct role caps stay in untouched selection history.
    op.execute("""
        WITH current_selection AS (
            SELECT DISTINCT ON (instance_id) instance_id,payload
            FROM public.provider_selection_revision ORDER BY instance_id,revision DESC
        ), choices AS (
            SELECT instance_id,choice,ordinality FROM current_selection,
            LATERAL jsonb_array_elements(jsonb_build_array(payload->'default',payload->'brain',
                payload->'investigator',payload->'validator')) WITH ORDINALITY AS roles(choice,ordinality)
            WHERE choice <> 'null'::jsonb
        ), exact_choices AS (
            SELECT DISTINCT ON (instance_id,choice->>'connection_id',(choice->>'model') COLLATE "C")
                instance_id,choice,ordinality FROM choices
            ORDER BY instance_id,choice->>'connection_id',(choice->>'model') COLLATE "C",ordinality
        ), entries AS (
            SELECT instance_id,choice,
                md5(instance_id::text || ':' || (choice->>'connection_id') || ':' || (choice->>'model'))::uuid AS entry_id
            FROM exact_choices
        ), registry AS (
            INSERT INTO public.provider_model_registry_revision(instance_id,revision)
            SELECT DISTINCT instance_id,1 FROM entries
            ON CONFLICT DO NOTHING RETURNING instance_id
        ), identities AS (
            INSERT INTO public.provider_model_entry(instance_id,entry_id,connection_id,model)
            SELECT e.instance_id,e.entry_id,(e.choice->>'connection_id')::uuid,e.choice->>'model'
            FROM entries e JOIN registry r USING(instance_id)
            RETURNING instance_id,entry_id
        )
        INSERT INTO public.provider_model_entry_revision(instance_id,entry_id,revision,connection_id,
            connection_revision,registry_revision,output_tokens)
        SELECT e.instance_id,e.entry_id,1,(e.choice->>'connection_id')::uuid,
            (e.choice->>'connection_revision')::bigint,1,(e.choice->>'output_tokens')::integer
        FROM entries e JOIN identities i USING(instance_id,entry_id)
    """)


def downgrade() -> None:
    raise RuntimeError("Configured model history requires reviewed backup restoration")
