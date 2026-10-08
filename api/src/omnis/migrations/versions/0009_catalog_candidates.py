"""Private immutable source records, commands and definitive catalog reservations."""

from alembic import op

revision = "0009_catalog_candidates"
down_revision = "0008_engagement_edit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE catalog_record (
            id uuid PRIMARY KEY, owner_id uuid NOT NULL, group_id uuid NOT NULL,
            kind text NOT NULL, revision integer NOT NULL CHECK (revision >= 1),
            digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
            envelope jsonb NOT NULL CHECK (jsonb_typeof(envelope) = 'object'),
            UNIQUE (id, revision),
            CHECK ((envelope->>'id')::uuid = id),
            CHECK ((envelope->>'revision')::integer = revision),
            CHECK (envelope->>'kind' = kind), CHECK (envelope->>'digest' = digest)
        )
    """)
    op.execute("""
        CREATE TABLE catalog_identity (
            id uuid PRIMARY KEY, owner_id uuid NOT NULL,
            package_key text NOT NULL, entity_kind text NOT NULL, entity_key text NOT NULL,
            UNIQUE (package_key, entity_kind, entity_key)
        )
    """)
    op.execute("""
        CREATE TABLE catalog_reservation (
            id uuid NOT NULL REFERENCES catalog_identity(id),
            revision integer NOT NULL CHECK (revision >= 1),
            digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
            draft_id uuid NOT NULL REFERENCES catalog_record(id),
            PRIMARY KEY (id, revision), UNIQUE (id, digest)
        )
    """)
    op.execute("""
        CREATE TABLE catalog_command (
            owner_id uuid NOT NULL, command_id uuid NOT NULL,
            operation text NOT NULL, request_digest text NOT NULL,
            result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
            PRIMARY KEY (owner_id, command_id),
            CHECK (request_digest ~ '^[0-9a-f]{64}$')
        )
    """)
    op.execute("""
        CREATE FUNCTION catalog_immutable() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN
        RAISE EXCEPTION 'immutable catalog ledger';
        END;$$
    """)
    for table in ("catalog_record", "catalog_identity", "catalog_reservation", "catalog_command"):
        op.execute(
            f"CREATE TRIGGER catalog_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION catalog_immutable()"
        )


def downgrade() -> None:
    raise RuntimeError("Catalog reservations are definitive; restore a reviewed backup instead")
