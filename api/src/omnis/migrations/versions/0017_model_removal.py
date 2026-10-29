"""Retire library membership without changing archived identity or history."""

from alembic import op

from omnis.core.provider_schema import MODEL_RETIRE_GUARD

revision = "0017_model_removal"
down_revision = "0016_provider_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.provider_model_entry
            ADD COLUMN removed_registry_revision bigint,
            ADD CONSTRAINT provider_model_removed_registry_fk
                FOREIGN KEY(instance_id, removed_registry_revision)
                REFERENCES public.provider_model_registry_revision(instance_id, revision),
            DROP CONSTRAINT provider_model_entry_instance_id_connection_id_model_key;
        CREATE UNIQUE INDEX provider_model_available_unique
            ON public.provider_model_entry(instance_id, connection_id, model)
            WHERE removed_registry_revision IS NULL;
        DROP TRIGGER provider_settings_no_change ON public.provider_model_entry;
        CREATE TRIGGER provider_settings_no_change
            BEFORE DELETE OR TRUNCATE ON public.provider_model_entry
            FOR EACH STATEMENT EXECUTE FUNCTION public.provider_settings_immutable();
    """)
    op.execute(
        "CREATE FUNCTION public.provider_model_retire_guard() RETURNS trigger "
        "LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$"
        + MODEL_RETIRE_GUARD
        + "$$; CREATE TRIGGER provider_model_retire BEFORE UPDATE ON public.provider_model_entry "
        "FOR EACH ROW EXECUTE FUNCTION public.provider_model_retire_guard()"
    )


def downgrade() -> None:
    raise RuntimeError("Retired model history requires reviewed backup restoration")
