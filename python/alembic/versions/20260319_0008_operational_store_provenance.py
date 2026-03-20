from __future__ import annotations

from alembic import context
from alembic import op
import sqlalchemy as sa


revision = "20260319_0008"
down_revision = "20260316_0007"
branch_labels = None
depends_on = None


_TABLES = (
    "conversations",
    "conversation_messages",
    "message_blocks",
    "conversation_plans",
    "conversation_subagents",
    "conversation_tasks",
    "context_buckets",
    "context_steps",
)


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    for table_name in _TABLES:
        op.add_column(table_name, sa.Column("record_source", sa.Text(), nullable=True))
        op.add_column(table_name, sa.Column("source_file_modified_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            table_name,
            sa.Column(
                "loaded_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "first_ingested_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "last_refreshed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    for table_name in reversed(_TABLES):
        op.drop_column(table_name, "last_refreshed_at")
        op.drop_column(table_name, "first_ingested_at")
        op.drop_column(table_name, "loaded_at")
        op.drop_column(table_name, "source_file_modified_at")
        op.drop_column(table_name, "record_source")
