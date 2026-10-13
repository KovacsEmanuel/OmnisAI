"""Add immutable mission revision2 without rekeying revision1 history.

Canonical envelope validation/digest computation remains a backend responsibility.
This storage prerequisite does not add an application consumer or compatibility grant.
"""

from alembic import op

revision = "0013_mission_revisions"
down_revision = "0012_contract_methods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.managed_record ADD CONSTRAINT managed_record_id_owner_run_key
            UNIQUE (id, owner_id, run_id);
        CREATE TABLE public.managed_mission_revision (
            mission_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            run_id uuid NOT NULL,
            revision bigint NOT NULL,
            envelope jsonb NOT NULL,
            CONSTRAINT managed_mission_revision_pkey PRIMARY KEY (mission_id, revision),
            CONSTRAINT managed_mission_revision_root_fkey
                FOREIGN KEY (mission_id, owner_id, run_id)
                REFERENCES public.managed_record(id, owner_id, run_id),
            CONSTRAINT managed_mission_revision_number_check CHECK (revision = 2),
            CONSTRAINT managed_mission_revision_object_check
                CHECK (jsonb_typeof(envelope) = 'object'),
            CONSTRAINT managed_mission_revision_kind_check
                CHECK ((envelope->'kind' = '"mission"'::jsonb) IS TRUE),
            CONSTRAINT managed_mission_revision_id_check
                CHECK ((envelope->'id' = to_jsonb(mission_id::text)) IS TRUE),
            CONSTRAINT managed_mission_revision_schema_check
                CHECK ((envelope->'schema_version' = '1'::jsonb
                    AND envelope->>'schema_version' = '1') IS TRUE),
            CONSTRAINT managed_mission_revision_revision_check
                CHECK ((envelope->'revision' = '2'::jsonb
                    AND envelope->>'revision' = '2') IS TRUE)
        );
        CREATE FUNCTION public.managed_mission_revision_guard() RETURNS trigger LANGUAGE plpgsql
            SET search_path TO pg_catalog, pg_temp AS $$DECLARE
        root jsonb;
        predecessor jsonb;
        basis jsonb;
        mission_basis jsonb;
        mission_count bigint;
        BEGIN
        SELECT envelope INTO root FROM public.managed_record
            WHERE id = NEW.mission_id AND owner_id = NEW.owner_id AND run_id = NEW.run_id;
        IF NOT FOUND OR (root->'kind' = '"mission"'::jsonb
            AND root->'revision' = '1'::jsonb AND root->>'revision' = '1'
            AND root->'schema_version' = '1'::jsonb AND root->>'schema_version' = '1'
            AND root->'id' = to_jsonb(NEW.mission_id::text)
            AND jsonb_typeof(root->'digest') = 'string'
            AND root->>'digest' ~ '^[0-9a-f]{64}$') IS NOT TRUE THEN
            RAISE EXCEPTION 'invalid mission revision root';
        END IF;
        basis := NEW.envelope->'payload'->'basis_refs';
        IF jsonb_typeof(basis) IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'invalid mission predecessor';
        END IF;
        SELECT count(*) INTO mission_count FROM jsonb_array_elements(basis) AS refs(value)
            WHERE value->'kind' = '"mission"'::jsonb;
        IF mission_count <> 1 THEN
            RAISE EXCEPTION 'invalid mission predecessor';
        END IF;
        SELECT value INTO mission_basis FROM jsonb_array_elements(basis) AS refs(value)
            WHERE value->'kind' = '"mission"'::jsonb;
        predecessor := jsonb_build_object('kind', 'mission', 'id', NEW.mission_id::text,
            'revision', 1, 'digest', root->>'digest');
        IF (mission_basis = predecessor AND mission_basis->>'revision' = '1') IS NOT TRUE THEN
            RAISE EXCEPTION 'invalid mission predecessor';
        END IF;
        RETURN NEW;
        END;$$;
        CREATE TRIGGER managed_mission_revision_root BEFORE INSERT ON public.managed_mission_revision
            FOR EACH ROW EXECUTE FUNCTION public.managed_mission_revision_guard();
        CREATE FUNCTION public.managed_mission_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'mission revisions are immutable';
        END;$$;
        CREATE TRIGGER managed_mission_revision_no_change
            BEFORE UPDATE OR DELETE OR TRUNCATE ON public.managed_mission_revision
            FOR EACH STATEMENT EXECUTE FUNCTION public.managed_mission_revision_immutable()
    """)


def downgrade() -> None:
    raise RuntimeError("Mission revision history requires reviewed backup restoration")
