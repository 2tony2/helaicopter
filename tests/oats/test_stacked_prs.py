from pathlib import Path

from oats.parser import parse_run_spec
from oats.planner import build_execution_plan
from oats.repo_config import find_repo_config, load_repo_config
from oats.stacked_prs import derive_parent_branch, derive_stacked_pr_graph


def test_derive_parent_branch_handles_root_single_and_multi_dependency_tasks(
    tmp_path: Path,
) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run_spec_path = tmp_path / "stacked.md"
    run_spec_path.write_text(
        """# Run: Stacked Branch Graph

## Tasks

### auth
Implement auth.

### dashboard
Depends on: auth

Build dashboard endpoints.

### verify
Depends on: auth, dashboard

Run validation.
""",
        encoding="utf-8",
    )

    plan = build_execution_plan(
        config=config,
        run_spec=parse_run_spec(run_spec_path),
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )
    tasks_by_id = {task.id: task for task in plan.tasks}

    assert derive_parent_branch(
        tasks_by_id["auth"],
        feature_branch=plan.integration_branch,
        upstream_branch_map={task_id: task.branch_name for task_id, task in tasks_by_id.items()},
    ) == (plan.integration_branch, "feature_base")
    assert derive_parent_branch(
        tasks_by_id["dashboard"],
        feature_branch=plan.integration_branch,
        upstream_branch_map={task_id: task.branch_name for task_id, task in tasks_by_id.items()},
    ) == (tasks_by_id["auth"].branch_name, "single_parent")
    assert derive_parent_branch(
        tasks_by_id["verify"],
        feature_branch=plan.integration_branch,
        upstream_branch_map={task_id: task.branch_name for task_id, task in tasks_by_id.items()},
    ) == (plan.integration_branch, "after_dependency_merges")


def test_derive_stacked_pr_graph_marks_multi_dependency_tasks_blocked(
    tmp_path: Path,
) -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run_spec_path = tmp_path / "stacked.md"
    run_spec_path.write_text(
        """# Run: Stacked Status Graph

## Tasks

### auth
Implement auth.

### dashboard
Depends on: auth

Build dashboard endpoints.

### verify
Depends on: auth, dashboard

Run validation.
""",
        encoding="utf-8",
    )

    plan = build_execution_plan(
        config=config,
        run_spec=parse_run_spec(run_spec_path),
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    graph = derive_stacked_pr_graph(plan.tasks, feature_branch=plan.integration_branch)

    assert graph["verify"].branch_strategy == "after_dependency_merges"
    assert graph["verify"].initial_task_status == "blocked"
