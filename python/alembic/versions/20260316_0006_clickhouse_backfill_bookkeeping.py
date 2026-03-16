from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260316_0006"
down_revision = "20260311_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.add_column("refresh_runs", sa.Column("clickhouse_backfill_status", sa.Text(), nullable=True))
    op.add_column(
        "refresh_runs",
        sa.Column("clickhouse_backfill_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "refresh_runs",
        sa.Column(
            "clickhouse_conversation_events_loaded",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "refresh_runs",
        sa.Column(
            "clickhouse_message_events_loaded",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "refresh_runs",
        sa.Column(
            "clickhouse_tool_events_loaded",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "refresh_runs",
        sa.Column(
            "clickhouse_usage_events_loaded",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.drop_column("refresh_runs", "clickhouse_usage_events_loaded")
    op.drop_column("refresh_runs", "clickhouse_tool_events_loaded")
    op.drop_column("refresh_runs", "clickhouse_message_events_loaded")
    op.drop_column("refresh_runs", "clickhouse_conversation_events_loaded")
    op.drop_column("refresh_runs", "clickhouse_backfill_error_message")
    op.drop_column("refresh_runs", "clickhouse_backfill_status")
