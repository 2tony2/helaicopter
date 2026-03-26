from pathlib import Path

from oats.graph import EdgePredicate
from oats.parser import parse_run_spec
from oats.planner import build_execution_plan
from oats.repo_config import find_repo_config, load_repo_config
from oats.runtime_state import build_graph_from_planned_tasks, build_initial_runtime_state, migrate_v1_state
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


# ---------------------------------------------------------------------------
# Graph construction from planned tasks
# ---------------------------------------------------------------------------


def test_build_graph_from_planned_tasks_creates_typed_edges(
    tmp_path: Path,
) -> None:
    """Planner should produce a TaskGraph with correct typed edges."""
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run_spec_path = tmp_path / "graph.md"
    run_spec_path.write_text(
        """# Run: Graph Build Test

## Tasks

### auth
Implement auth.

### models
Implement models.

### api
Depends on: auth, models

Build API.

### dashboard
Depends on: api

Build dashboard.
""",
        encoding="utf-8",
    )

    plan = build_execution_plan(
        config=config,
        run_spec=parse_run_spec(run_spec_path),
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    graph = build_graph_from_planned_tasks(plan.tasks)

    assert len(graph.nodes) == 4
    assert len(graph.edges) == 3  # auth->api, models->api, api->dashboard

    # Single-parent deps get code_ready edges
    dashboard_edges = graph.edges_to("dashboard")
    assert len(dashboard_edges) == 1
    assert dashboard_edges[0].predicate == EdgePredicate.CODE_READY

    # Multi-dependency tasks with after_dependency_merges get pr_merged edges
    api_edges = graph.edges_to("api")
    assert len(api_edges) == 2
    assert all(e.predicate == EdgePredicate.PR_MERGED for e in api_edges)


def test_build_initial_runtime_state_includes_graph(
    tmp_path: Path,
) -> None:
    """build_initial_runtime_state should populate the graph field."""
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run_spec_path = tmp_path / "graph_init.md"
    run_spec_path.write_text(
        """# Run: Init Graph Test

## Tasks

### auth
Implement auth.

### api
Depends on: auth

Build API.
""",
        encoding="utf-8",
    )

    plan = build_execution_plan(
        config=config,
        run_spec=parse_run_spec(run_spec_path),
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    state = build_initial_runtime_state(
        plan, mode="writable", run_id="run_test", executor_agent="claude",
    )

    assert state.graph is not None
    assert len(state.graph.nodes) == 2
    assert len(state.graph.edges) == 1


def test_migrate_v1_state_creates_graph_from_tasks() -> None:
    """Loading a v1 state without a graph field creates the graph from tasks."""
    from oats.models import RunRuntimeState, TaskRuntimeRecord, TaskPullRequestSnapshot

    state = RunRuntimeState(
        contract_version="oats-runtime-v2",
        run_id="run_v1",
        run_title="V1 migration test",
        repo_root=Path("/tmp"),
        config_path=Path("/tmp/config.toml"),
        run_spec_path=Path("/tmp/spec.md"),
        mode="writable",
        integration_branch="feat/test",
        task_pr_target="feat/test",
        final_pr_target="main",
        runtime_dir=Path("/tmp/runtime"),
        tasks=[
            TaskRuntimeRecord(
                task_id="a", title="A", branch_name="oats/task/a",
                pr_base="feat/test", agent="claude", depends_on=[],
            ),
            TaskRuntimeRecord(
                task_id="b", title="B", branch_name="oats/task/b",
                pr_base="feat/test", agent="claude", depends_on=["a"],
            ),
            TaskRuntimeRecord(
                task_id="c", title="C", branch_name="oats/task/c",
                pr_base="feat/test", agent="claude", depends_on=["b"],
            ),
        ],
        graph=None,
    )

    migrated = migrate_v1_state(state)

    assert migrated.graph is not None
    assert len(migrated.graph.nodes) == 3
    assert len(migrated.graph.edges) == 2
    assert migrated.graph.is_acyclic()
