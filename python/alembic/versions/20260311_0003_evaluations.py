from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260311_0003"
down_revision = "20260311_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.create_table(
        "evaluation_prompts",
        sa.Column("prompt_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluation_prompts_name", "evaluation_prompts", ["name"])

    op.create_table(
        "conversation_evaluations",
        sa.Column("evaluation_id", sa.Text(), primary_key=True),
        sa.Column("conversation_id", sa.Text(), nullable=False),
        sa.Column(
            "prompt_id",
            sa.Text(),
            sa.ForeignKey("evaluation_prompts.prompt_id", ondelete="SET NULL"),
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("selection_instruction", sa.Text()),
        sa.Column("prompt_name", sa.Text(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("report_markdown", sa.Text()),
        sa.Column("raw_output", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
    )
    op.create_index(
        "ix_conversation_evaluations_conversation_id_created_at",
        "conversation_evaluations",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return

    op.drop_index(
        "ix_conversation_evaluations_conversation_id_created_at",
        table_name="conversation_evaluations",
    )
    op.drop_table("conversation_evaluations")
    op.drop_index("ix_evaluation_prompts_name", table_name="evaluation_prompts")
    op.drop_table("evaluation_prompts")
