from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260311_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target == "oltp":
        upgrade_oltp()
    else:
        upgrade_olap()


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target == "oltp":
        downgrade_oltp()
    else:
        downgrade_olap()


def upgrade_oltp() -> None:
    op.create_table(
        "refresh_runs",
        sa.Column("run_id", sa.Text(), primary_key=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("conversations_loaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_loaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls_loaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plans_loaded", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("project_name", sa.Text(), nullable=False),
        sa.Column("first_message", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.Text()),
        sa.Column("git_branch", sa.Text()),
        sa.Column("reasoning_effort", sa.Text()),
        sa.Column("speed", sa.Text()),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subagent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_input_cost", sa.Text()),
        sa.Column("estimated_output_cost", sa.Text()),
        sa.Column("estimated_cache_write_cost", sa.Text()),
        sa.Column("estimated_cache_read_cost", sa.Text()),
        sa.Column("estimated_total_cost", sa.Text()),
    )
    op.create_index(
        "ix_conversations_provider_started_at",
        "conversations",
        ["provider", "started_at"],
    )
    op.create_index(
        "ix_conversations_project_path",
        "conversations",
        ["project_path"],
    )
    op.create_table(
        "conversation_messages",
        sa.Column("message_id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Text(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("speed", sa.Text()),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text_preview", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_messages_conversation_id_timestamp",
        "conversation_messages",
        ["conversation_id", "timestamp"],
    )
    op.create_table(
        "message_blocks",
        sa.Column("block_id", sa.Text(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Text(),
            sa.ForeignKey("conversation_messages.message_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.Text(), nullable=False),
        sa.Column("text_content", sa.Text()),
        sa.Column("tool_use_id", sa.Text()),
        sa.Column("tool_name", sa.Text()),
        sa.Column("tool_input_json", sa.Text()),
        sa.Column("tool_result_text", sa.Text()),
        sa.Column("is_error", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_message_blocks_message_id", "message_blocks", ["message_id"])
    op.create_table(
        "conversation_plans",
        sa.Column("plan_row_id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Text(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("preview", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("explanation", sa.Text()),
        sa.Column("steps_json", sa.Text()),
    )
    op.create_index(
        "ix_plans_conversation_id_timestamp",
        "conversation_plans",
        ["conversation_id", "timestamp"],
    )
    op.create_table(
        "conversation_subagents",
        sa.Column("subagent_row_id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Text(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("subagent_type", sa.Text()),
        sa.Column("nickname", sa.Text()),
        sa.Column("has_file", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_subagents_conversation_id", "conversation_subagents", ["conversation_id"])
    op.create_table(
        "conversation_tasks",
        sa.Column("task_row_id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Text(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("task_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_tasks_conversation_id", "conversation_tasks", ["conversation_id"])
    op.create_table(
        "context_buckets",
        sa.Column("bucket_row_id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Text(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_context_buckets_conversation_id", "context_buckets", ["conversation_id"])
    op.create_table(
        "context_steps",
        sa.Column("step_row_id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Text(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_context_steps_conversation_id_timestamp",
        "context_steps",
        ["conversation_id", "timestamp"],
    )


def downgrade_oltp() -> None:
    op.drop_index("ix_context_steps_conversation_id_timestamp", table_name="context_steps")
    op.drop_table("context_steps")
    op.drop_index("ix_context_buckets_conversation_id", table_name="context_buckets")
    op.drop_table("context_buckets")
    op.drop_index("ix_tasks_conversation_id", table_name="conversation_tasks")
    op.drop_table("conversation_tasks")
    op.drop_index("ix_subagents_conversation_id", table_name="conversation_subagents")
    op.drop_table("conversation_subagents")
    op.drop_index("ix_plans_conversation_id_timestamp", table_name="conversation_plans")
    op.drop_table("conversation_plans")
    op.drop_index("ix_message_blocks_message_id", table_name="message_blocks")
    op.drop_table("message_blocks")
    op.drop_index("ix_messages_conversation_id_timestamp", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_project_path", table_name="conversations")
    op.drop_index("ix_conversations_provider_started_at", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("refresh_runs")


def upgrade_olap() -> None:
    op.create_table(
        "dim_dates",
        sa.Column("date_key", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("calendar_date", sa.Date(), nullable=False, unique=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("iso_week", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
    )
    op.create_table(
        "dim_projects",
        sa.Column("project_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False, unique=True),
        sa.Column("project_name", sa.Text(), nullable=False),
    )
    op.create_table(
        "dim_models",
        sa.Column("model_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
    )
    op.create_table(
        "dim_tools",
        sa.Column("tool_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
    )
    op.create_table(
        "dim_subagent_types",
        sa.Column("subagent_type_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("subagent_type", sa.Text(), nullable=False),
    )
    op.create_table(
        "fact_conversations",
        sa.Column("conversation_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("dim_projects.project_id"), nullable=False),
        sa.Column("model_id", sa.Text(), sa.ForeignKey("dim_models.model_id")),
        sa.Column("started_date_key", sa.Integer(), sa.ForeignKey("dim_dates.date_key"), nullable=False),
        sa.Column("ended_date_key", sa.Integer(), sa.ForeignKey("dim_dates.date_key"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_message", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subagent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("estimated_input_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("estimated_output_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("estimated_cache_write_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("estimated_cache_read_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
    )
    op.create_table(
        "fact_daily_usage",
        sa.Column("daily_usage_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("date_key", sa.Integer(), sa.ForeignKey("dim_dates.date_key"), nullable=False),
        sa.Column("model_id", sa.Text(), sa.ForeignKey("dim_models.model_id")),
        sa.Column("conversation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
    )
    op.create_table(
        "fact_tool_usage",
        sa.Column("tool_usage_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("date_key", sa.Integer(), sa.ForeignKey("dim_dates.date_key"), nullable=False),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("dim_projects.project_id"), nullable=False),
        sa.Column("tool_id", sa.Text(), sa.ForeignKey("dim_tools.tool_id"), nullable=False),
        sa.Column("conversation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "fact_subagent_usage",
        sa.Column("subagent_usage_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("date_key", sa.Integer(), sa.ForeignKey("dim_dates.date_key"), nullable=False),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("dim_projects.project_id"), nullable=False),
        sa.Column(
            "subagent_type_id",
            sa.Text(),
            sa.ForeignKey("dim_subagent_types.subagent_type_id"),
            nullable=False,
        ),
        sa.Column("conversation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subagent_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade_olap() -> None:
    op.drop_table("fact_subagent_usage")
    op.drop_table("fact_tool_usage")
    op.drop_table("fact_daily_usage")
    op.drop_table("fact_conversations")
    op.drop_table("dim_subagent_types")
    op.drop_table("dim_tools")
    op.drop_table("dim_models")
    op.drop_table("dim_projects")
    op.drop_table("dim_dates")
