"""Original relay identities are retained; no historical payload is rewritten."""

from alembic import op

from omnis.core.model_schema import RELAY_AUTHORITY_GUARD

revision = "0018_model_relay_authority"
down_revision = "0017_model_removal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.model_relay_authority (
            instance_id uuid NOT NULL REFERENCES public.instance_control(instance_id),
            kind text NOT NULL CHECK (kind IN ('MODEL_DISPATCH','METADATA_COMMAND')),
            id uuid NOT NULL,
            execution_owner_id uuid NOT NULL,
            generation bigint NOT NULL CHECK (generation >= 0),
            owner_epoch bigint NOT NULL CHECK (owner_epoch > 0),
            cancel_epoch bigint NOT NULL CHECK (cancel_epoch > 0),
            deadline text NOT NULL CHECK (length(deadline) <= 32 AND deadline ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?[+]00:00$' AND isfinite(deadline::timestamptz)),
            provider text NOT NULL CHECK (provider IN ('openrouter','orcarouter')),
            operation_serial bigint NOT NULL CHECK (operation_serial > 0),
            state text NOT NULL CHECK (state IN ('ACTIVE','DRAINED')),
            PRIMARY KEY(instance_id,kind,id),
            UNIQUE(instance_id,operation_serial)
        );
        CREATE TRIGGER model_relay_no_delete BEFORE DELETE OR TRUNCATE
            ON public.model_relay_authority FOR EACH STATEMENT
            EXECUTE FUNCTION public.model_v2_immutable();
    """)
    op.execute(
        "CREATE FUNCTION public.model_relay_authority_guard() RETURNS trigger "
        "LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$"
        + RELAY_AUTHORITY_GUARD
        + "$$; CREATE TRIGGER model_relay_guard BEFORE INSERT OR UPDATE ON public.model_relay_authority "
        "FOR EACH ROW EXECUTE FUNCTION public.model_relay_authority_guard()"
    )


def downgrade() -> None:
    raise RuntimeError("Relay authority history requires reviewed backup restoration")
