from __future__ import annotations

from alembic import context
from alembic import op
import sqlalchemy as sa


revision = "20260311_0005"
down_revision = "20260311_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return
    op.add_column(
        "conversations",
        sa.Column("thread_type", sa.Text(), nullable=False, server_default="main"),
    )


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return
    op.drop_column("conversations", "thread_type")
