from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from helaicopter_db.orchestration_facts import collect_orchestration_facts
from oats.models import (
    AgentInvocationResult,
    RunExecutionRecord,
    RunRuntimeState,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)


def _write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def test_collect_orchestration_facts_reconciles_runtime_and_terminal_records(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    run_id = "oats-run-1"
    state_path = tmp_path / ".oats" / "runtime" / run_id / "state.json"
    record_path = tmp_path / ".oats" / "runs" / "oats-run-1.json"

    _write_model(
        state_path,
        RunRuntimeState(
            run_id=run_id,
            run_title="Run: Analytics Reconcile",
            repo_root=tmp_path,
            config_path=tmp_path / ".oats" / "config.toml",
            run_spec_path=tmp_path / "examples" / "analytics.md",
            mode="writable",
            integration_branch="oats/overnight/analytics",
            task_pr_target="oats/overnight/analytics",
            final_pr_target="main",
            runtime_dir=state_path.parent,
            status="running",
            active_task_id="task-a",
            started_at=now - timedelta(minutes=3),
            updated_at=now - timedelta(seconds=10),
            heartbeat_at=now - timedelta(seconds=2),
            tasks=[
                TaskRuntimeRecord(
                    task_id="task-a",
                    title="Task A",
                    branch_name="oats/task/task-a",
                    pr_base="oats/overnight/analytics",
                    agent="claude",
                    status="running",
                    attempts=2,
                )
            ],
        ),
    )
    _write_model(
        record_path,
        RunExecutionRecord(
            run_id=run_id,
            run_title="Run: Analytics Reconcile",
            repo_root=tmp_path,
            config_path=tmp_path / ".oats" / "config.toml",
            run_spec_path=tmp_path / "examples" / "analytics.md",
            mode="writable",
            integration_branch="oats/overnight/analytics",
            task_pr_target="oats/overnight/analytics",
            final_pr_target="main",
            tasks=[
                TaskExecutionRecord(
                    task_id="task-a",
                    title="Task A",
                    invocation=AgentInvocationResult(
                        agent="claude",
                        role="executor",
                        command=["claude"],
                        cwd=tmp_path,
                        prompt="task",
                        exit_code=0,
                        started_at=now - timedelta(minutes=5),
                        finished_at=now - timedelta(minutes=4),
                    ),
                )
            ],
            recorded_at=now - timedelta(minutes=4),
        ),
    )

    run_facts, task_attempt_facts = collect_orchestration_facts(tmp_path)
    run_fact = next(fact for fact in run_facts if fact.run_id == run_id)
    task_fact = next(fact for fact in task_attempt_facts if fact.run_id == run_id)

    assert run_fact.status == "running"
    assert run_fact.canonical_status_source == "runtime_state_active"
    assert run_fact.has_runtime_snapshot is True
    assert run_fact.has_terminal_record is True
    assert run_fact.task_attempt_count == 1
    assert task_fact.attempt == 2
    assert task_fact.status == "running"


def test_collect_orchestration_facts_ignores_removed_legacy_artifacts(tmp_path: Path) -> None:
    flow_run_dir = tmp_path / ".oats" / "prefect" / "flow-runs" / "flow-run-1"
    flow_run_dir.mkdir(parents=True, exist_ok=True)
    (flow_run_dir / "metadata.json").write_text("{}", encoding="utf-8")

    run_facts, task_attempt_facts = collect_orchestration_facts(tmp_path)

    assert run_facts == []
    assert task_attempt_facts == []
