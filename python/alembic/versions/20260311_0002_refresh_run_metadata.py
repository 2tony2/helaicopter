from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260311_0002"
down_revision = "20260311_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.add_column("refresh_runs", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column("refresh_runs", sa.Column("scope_label", sa.Text(), nullable=True))
    op.add_column("refresh_runs", sa.Column("window_days", sa.Integer(), nullable=True))
    op.add_column("refresh_runs", sa.Column("window_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refresh_runs", sa.Column("window_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "refresh_runs",
        sa.Column("source_conversation_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.drop_column("refresh_runs", "source_conversation_count")
    op.drop_column("refresh_runs", "window_end")
    op.drop_column("refresh_runs", "window_start")
    op.drop_column("refresh_runs", "window_days")
    op.drop_column("refresh_runs", "scope_label")
    op.drop_column("refresh_runs", "idempotency_key")
