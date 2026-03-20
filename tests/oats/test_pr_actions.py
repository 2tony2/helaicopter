from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from oats.models import (
    FinalPullRequestSnapshot,
    TaskPullRequestSnapshot,
)
from oats.parser import parse_run_spec
from oats.planner import build_execution_plan
from oats.pr import PullRequestMergeConflictError, refresh_run, resume_run
from oats.repo_config import find_repo_config, load_repo_config
from oats.runtime_state import build_initial_runtime_state, write_runtime_state


def test_refresh_run_updates_waiting_task_prs_and_advances_merge_ready_items(
    tmp_path: Path,
) -> None:
    state = _build_runtime_state(tmp_path)
    state.stack_status = "awaiting_task_merge"
    state.tasks[0].task_pr = TaskPullRequestSnapshot(
        number=101,
        state="open",
        merge_gate_status="awaiting_checks",
        base_branch=state.integration_branch,
        head_branch=state.tasks[0].branch_name,
    )
    state.final_pr = FinalPullRequestSnapshot(state="open", review_gate_status="awaiting_human")

    refreshed = refresh_run(
        state=state,
        github_client=StubGitHubClient(
            task_reads={
                "auth": TaskPullRequestSnapshot(
                    number=101,
                    state="open",
                    merge_gate_status="merge_ready",
                    checks_summary={"state": "success"},
                    base_branch=state.integration_branch,
                    head_branch=state.tasks[0].branch_name,
                    snapshot_source="github_cli",
                )
            }
        ),
    )

    assert refreshed.tasks[0].task_pr.merge_gate_status == "merged"
    assert refreshed.tasks[0].task_pr.state == "merged"
    assert refreshed.stack_status in {"building", "ready_for_final_review"}


def test_refresh_run_retargets_open_child_prs_after_parent_merge(tmp_path: Path) -> None:
    state = _build_runtime_state(tmp_path)
    parent = state.tasks[0]
    child = state.tasks[1]
    parent.task_pr = TaskPullRequestSnapshot(
        number=101,
        state="merged",
        merge_gate_status="merged",
        base_branch=state.integration_branch,
        head_branch=parent.branch_name,
    )
    child.task_pr = TaskPullRequestSnapshot(
        number=102,
        state="open",
        merge_gate_status="awaiting_checks",
        base_branch=parent.branch_name,
        head_branch=child.branch_name,
    )

    refreshed = refresh_run(
        state=state,
        github_client=StubGitHubClient(
            task_reads={
                "auth": parent.task_pr,
                "dashboard_api": child.task_pr,
            }
        ),
    )

    updated_child = next(task for task in refreshed.tasks if task.task_id == "dashboard_api")
    assert updated_child.task_pr.base_branch == refreshed.feature_branch.name
    assert any(entry.kind == "pr_retarget" for entry in refreshed.tasks[0].operation_history)


def test_resume_run_reuses_existing_stack_and_marks_run_completed_when_final_pr_is_merged(
    tmp_path: Path,
) -> None:
    state = _build_runtime_state(tmp_path)
    state.final_pr = FinalPullRequestSnapshot(
        number=999,
        state="open",
        review_gate_status="awaiting_human",
    )
    write_runtime_state(state)

    resumed = resume_run(
        run_id="run-123",
        repo_root=tmp_path,
        github_client=StubGitHubClient(
            final_pr_read=FinalPullRequestSnapshot(
                number=999,
                state="merged",
                review_gate_status="merged",
                checks_summary={"state": "success"},
                snapshot_source="github_cli",
            )
        ),
    )

    assert resumed.run_id == "run-123"
    assert resumed.feature_branch.name == "oats/overnight/run-auth-and-dashboard"
    assert resumed.final_pr.state == "merged"
    assert resumed.final_pr.snapshot_source == "github_cli"
    assert resumed.final_pr.checks_summary["state"] == "success"
    assert resumed.status == "completed"
    assert resumed.stack_status == "completed"


def test_merge_failure_records_conflict_resolution_history(tmp_path: Path) -> None:
    state = _build_runtime_state(tmp_path)
    state.tasks[0].task_pr = TaskPullRequestSnapshot(
        number=101,
        state="open",
        merge_gate_status="merge_ready",
        checks_summary={"state": "success"},
        base_branch=state.integration_branch,
        head_branch=state.tasks[0].branch_name,
    )

    refreshed = refresh_run(
        state=state,
        github_client=StubGitHubClient(
            task_reads={"auth": state.tasks[0].task_pr},
            conflict_task_ids={"auth"},
        ),
    )

    assert refreshed.stack_status == "resolving_conflict"
    assert refreshed.active_operation is not None
    assert refreshed.active_operation.kind == "conflict_resolution"
    assert refreshed.active_operation.started_at is not None
    assert any(entry.kind == "conflict_resolution" for entry in refreshed.tasks[0].operation_history)


def test_refresh_run_creates_final_pr_when_the_last_task_pr_merges(tmp_path: Path) -> None:
    state = _build_runtime_state(tmp_path)
    state.tasks[0].task_pr = TaskPullRequestSnapshot(
        number=101,
        state="merged",
        merge_gate_status="merged",
        base_branch=state.integration_branch,
        head_branch=state.tasks[0].branch_name,
    )
    state.tasks[1].task_pr = TaskPullRequestSnapshot(
        number=102,
        state="open",
        merge_gate_status="merge_ready",
        checks_summary={"state": "success"},
        base_branch=state.tasks[0].branch_name,
        head_branch=state.tasks[1].branch_name,
    )

    refreshed = refresh_run(
        state=state,
        github_client=StubGitHubClient(
            task_reads={
                "auth": state.tasks[0].task_pr,
                "dashboard_api": state.tasks[1].task_pr,
            },
            final_pr_create=FinalPullRequestSnapshot(
                number=999,
                state="open",
                review_gate_status="awaiting_human",
                snapshot_source="github_cli",
            ),
        ),
    )

    assert refreshed.final_pr.state == "open"
    assert refreshed.final_pr.review_gate_status == "awaiting_human"
    assert refreshed.final_pr.last_refreshed_at is not None
    assert refreshed.stack_status == "ready_for_final_review"


def test_resume_run_unblocks_merge_gated_multi_dependency_tasks_after_upstream_prs_merge(
    tmp_path: Path,
) -> None:
    state = _build_multi_dependency_runtime_state(tmp_path)
    upstream_merged = TaskPullRequestSnapshot(
        state="merged",
        merge_gate_status="merged",
        checks_summary={"state": "success"},
    )
    state.tasks[0].task_pr = upstream_merged
    state.tasks[1].task_pr = upstream_merged
    write_runtime_state(state)

    resumed = resume_run(
        run_id="run-123",
        repo_root=tmp_path,
        github_client=StubGitHubClient(
            task_reads={
                "auth": upstream_merged,
                "dashboard": upstream_merged,
            }
        ),
    )

    verify = next(task for task in resumed.tasks if task.task_id == "verify")
    assert verify.status == "pending"
    assert verify.parent_branch == resumed.feature_branch.name


class StubGitHubClient:
    def __init__(
        self,
        *,
        task_reads: dict[str, TaskPullRequestSnapshot] | None = None,
        final_pr_read: FinalPullRequestSnapshot | None = None,
        final_pr_create: FinalPullRequestSnapshot | None = None,
        conflict_task_ids: set[str] | None = None,
    ) -> None:
        self.task_reads = task_reads or {}
        self.final_pr_read = final_pr_read
        self.final_pr_create = final_pr_create
        self.conflict_task_ids = conflict_task_ids or set()

    def read_task_pr(self, task) -> TaskPullRequestSnapshot:
        snapshot = self.task_reads.get(str(task.task_id), task.task_pr)
        return snapshot.model_copy(deep=True)

    def merge_task_pr(
        self,
        task,
        snapshot: TaskPullRequestSnapshot,
        *,
        merge_method: str,
    ) -> TaskPullRequestSnapshot:
        assert merge_method == "merge_commit"
        if str(task.task_id) in self.conflict_task_ids:
            raise PullRequestMergeConflictError(f"merge conflict for {task.task_id}")
        return snapshot.model_copy(
            update={
                "state": "merged",
                "merge_gate_status": "merged",
                "snapshot_source": "github_cli",
                "last_refreshed_at": datetime.now(timezone.utc),
            },
            deep=True,
        )

    def retarget_task_pr(self, task, *, base_branch: str) -> TaskPullRequestSnapshot:
        updated = task.task_pr.model_copy(
            update={
                "base_branch": base_branch,
                "snapshot_source": "github_cli",
                "last_refreshed_at": datetime.now(timezone.utc),
            },
            deep=True,
        )
        self.task_reads[str(task.task_id)] = updated
        return updated

    def create_final_pr(self, state) -> FinalPullRequestSnapshot:
        snapshot = self.final_pr_create or FinalPullRequestSnapshot(
            number=999,
            state="open",
            review_gate_status="awaiting_human",
            snapshot_source="github_cli",
        )
        return snapshot.model_copy(
            update={"last_refreshed_at": datetime.now(timezone.utc)},
            deep=True,
        )

    def read_final_pr(self, state) -> FinalPullRequestSnapshot:
        snapshot = self.final_pr_read or state.final_pr
        return snapshot.model_copy(
            update={
                "last_refreshed_at": snapshot.last_refreshed_at or datetime.now(timezone.utc),
            },
            deep=True,
        )


def _build_runtime_state(tmp_path: Path):
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    execution_plan = build_execution_plan(
        config=config,
        run_spec=parse_run_spec(Path("examples/sample_run.md")),
        repo_root=tmp_path,
        config_path=tmp_path / ".oats" / "config.toml",
    )
    return build_initial_runtime_state(
        execution_plan=execution_plan,
        mode="writable",
        run_id="run-123",
        executor_agent=config.agents.executor,
    )


def _build_multi_dependency_runtime_state(tmp_path: Path):
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run_spec_path = tmp_path / "multi-dependency.md"
    run_spec_path.write_text(
        """# Run: Auth And Dashboard

## Tasks

### auth
Implement auth.

### dashboard
Depends on: auth

Build dashboard.

### verify
Depends on: auth, dashboard

Run validation.
""",
        encoding="utf-8",
    )
    execution_plan = build_execution_plan(
        config=config,
        run_spec=parse_run_spec(run_spec_path),
        repo_root=tmp_path,
        config_path=tmp_path / ".oats" / "config.toml",
    )
    return build_initial_runtime_state(
        execution_plan=execution_plan,
        mode="writable",
        run_id="run-123",
        executor_agent=config.agents.executor,
    )
