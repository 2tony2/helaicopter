from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260319_0009"
down_revision = "20260319_0008"
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
        "fact_orchestration_runs",
        sa.Column("run_fact_id", sa.Text(), primary_key=True),
        sa.Column("run_source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("flow_run_name", sa.Text(), nullable=True),
        sa.Column("run_title", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column("config_path", sa.Text(), nullable=True),
        sa.Column("artifact_root", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("canonical_status_source", sa.Text(), nullable=False),
        sa.Column("has_runtime_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_terminal_record", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("running_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_fact_orchestration_runs_run_source_updated_at",
        "fact_orchestration_runs",
        ["run_source", "updated_at"],
    )
    op.create_table(
        "fact_orchestration_task_attempts",
        sa.Column("task_attempt_fact_id", sa.Text(), primary_key=True),
        sa.Column(
            "run_fact_id",
            sa.Text(),
            sa.ForeignKey("fact_orchestration_runs.run_fact_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("task_title", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("upstream_task_ids_json", sa.Text(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("reasoning_effort", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_progress_event_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_fact_orchestration_task_attempts_run_fact_id_task_id",
        "fact_orchestration_task_attempts",
        ["run_fact_id", "task_id"],
    )


def downgrade_oltp() -> None:
    op.drop_index(
        "ix_fact_orchestration_task_attempts_run_fact_id_task_id",
        table_name="fact_orchestration_task_attempts",
    )
    op.drop_table("fact_orchestration_task_attempts")
    op.drop_index("ix_fact_orchestration_runs_run_source_updated_at", table_name="fact_orchestration_runs")
    op.drop_table("fact_orchestration_runs")


def upgrade_olap() -> None:
    op.create_table(
        "fact_orchestration_runs",
        sa.Column("run_fact_id", sa.Text(), primary_key=True),
        sa.Column("run_source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("flow_run_name", sa.Text(), nullable=True),
        sa.Column("run_title", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column("config_path", sa.Text(), nullable=True),
        sa.Column("artifact_root", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("canonical_status_source", sa.Text(), nullable=False),
        sa.Column("has_runtime_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_terminal_record", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("running_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "fact_orchestration_task_attempts",
        sa.Column("task_attempt_fact_id", sa.Text(), primary_key=True),
        sa.Column("run_fact_id", sa.Text(), nullable=False),
        sa.Column("run_source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("task_title", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("upstream_task_ids_json", sa.Text(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("reasoning_effort", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_progress_event_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade_olap() -> None:
    op.drop_table("fact_orchestration_task_attempts")
    op.drop_table("fact_orchestration_runs")
