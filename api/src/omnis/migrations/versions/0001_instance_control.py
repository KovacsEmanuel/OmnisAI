"""Seed a closed InstanceControl singleton for the control plane.

Revision ID: 0001_instance_control
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_instance_control"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instance_control",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column(
            "instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            unique=True,
        ),
        sa.Column("admission_open", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("shutdown_command_id", postgresql.UUID(as_uuid=True)),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("quiesced_generation", sa.BigInteger()),
        sa.Column("quiesced_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="ck_instance_control_singleton"),
        sa.CheckConstraint("generation >= 0", name="ck_instance_control_generation"),
    )
    op.execute("INSERT INTO instance_control (id) VALUES (1)")


def downgrade() -> None:
    raise RuntimeError("Instance identity is durable; restore a reviewed backup instead")
