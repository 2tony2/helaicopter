from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260311_0004"
down_revision = "20260311_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.create_table(
        "subscription_settings",
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("has_subscription", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("monthly_cost", sa.Float(), nullable=False, server_default="200"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.drop_table("subscription_settings")
