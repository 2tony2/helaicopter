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

_PROVENANCE_COLUMNS: list[tuple[str, sa.types.TypeEngine, dict]] = [
    ("record_source", sa.Text(), {"nullable": True}),
    ("source_file_modified_at", sa.DateTime(timezone=True), {"nullable": True}),
    (
        "loaded_at",
        sa.DateTime(timezone=True),
        {"nullable": False, "server_default": "1970-01-01T00:00:00+00:00"},
    ),
    (
        "first_ingested_at",
        sa.DateTime(timezone=True),
        {"nullable": False, "server_default": "1970-01-01T00:00:00+00:00"},
    ),
    (
        "last_refreshed_at",
        sa.DateTime(timezone=True),
        {"nullable": False, "server_default": "1970-01-01T00:00:00+00:00"},
    ),
]


def _existing_columns(table_name: str) -> set[str]:
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    for table_name in _TABLES:
        existing = _existing_columns(table_name)
        for col_name, col_type, col_kwargs in _PROVENANCE_COLUMNS:
            if col_name not in existing:
                op.add_column(table_name, sa.Column(col_name, col_type, **col_kwargs))


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
