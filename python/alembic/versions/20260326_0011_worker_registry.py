from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260326_0011"
down_revision = "20260320_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return
    upgrade_oltp()


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return
    downgrade_oltp()


def upgrade_oltp() -> None:
    op.create_table(
        "worker_registry",
        sa.Column("worker_id", sa.Text(), primary_key=True),
        sa.Column("worker_type", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("capabilities_json", sa.Text(), nullable=False),
        sa.Column("auth_credential_id", sa.Text(), nullable=True),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("worktree_root", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_task_id", sa.Text(), nullable=True),
        sa.Column("current_run_id", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_worker_registry_provider", "worker_registry", ["provider"])
    op.create_index("ix_worker_registry_status", "worker_registry", ["status"])


def downgrade_oltp() -> None:
    op.drop_index("ix_worker_registry_status", table_name="worker_registry")
    op.drop_index("ix_worker_registry_provider", table_name="worker_registry")
    op.drop_table("worker_registry")
