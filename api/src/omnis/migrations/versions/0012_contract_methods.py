"""Enable checked CONTRACT/PURE success; preserve historical cold task rows."""

from alembic import op

revision = "0012_contract_methods"
down_revision = "0011_managed_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE managed_task DROP CONSTRAINT managed_task_state_check;
        ALTER TABLE managed_task ADD CONSTRAINT managed_task_state_check
            CHECK (state IN ('QUEUED','BOUND','BLOCKED','SUCCEEDED'));
        ALTER TABLE managed_task ADD CONSTRAINT managed_task_success_check
            CHECK (state <> 'SUCCEEDED' OR (result_id IS NOT NULL AND check_id IS NOT NULL))
    """)


def downgrade() -> None:
    raise RuntimeError("Managed method history requires reviewed backup restoration")
