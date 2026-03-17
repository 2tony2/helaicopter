from pathlib import Path

from oats.repo_config import find_repo_config, load_repo_config
from oats.parser import parse_run_spec
from oats.planner import build_execution_plan
from oats.pr import (
    build_final_pr_plan,
    build_pr_create_command,
    build_task_pr_plans,
    execute_pr_plan,
)


def test_load_repo_config() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)

    assert config.repo.base_branch == "main"
    assert config.agents.executor == "claude"
    assert config.agents.merge_operator == "codex"
    assert config.agent["codex"].command == "codex"
    assert config.git.final_pr_target == "main"
    assert config.git.auto_merge_task_prs_into_integration is False


def test_execution_plan_uses_integration_branch_targeting() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))

    plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    assert plan.integration_branch == "oats/overnight/run-auth-and-dashboard"
    assert plan.task_pr_target == plan.integration_branch
    assert plan.final_pr_target == "main"
    assert plan.tasks[0].branch_name == "oats/task/auth"
    assert plan.tasks[0].pr_base == plan.integration_branch


def test_pr_commands_target_integration_branch_then_main() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    task_pr = build_task_pr_plans(plan)[0]
    final_pr = build_final_pr_plan(plan)

    task_pr_command = build_pr_create_command(task_pr)
    final_pr_command = build_pr_create_command(final_pr)

    assert "--base" in task_pr_command
    assert plan.integration_branch in task_pr_command
    assert "oats/task/auth" in task_pr_command
    assert "--base" in final_pr_command
    assert "main" in final_pr_command
    assert plan.integration_branch in final_pr_command


def test_pr_apply_dry_run_records_all_commands() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    run = parse_run_spec(Path("examples/sample_run.md"))
    plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    record = execute_pr_plan(plan, config, execute=False)

    labels = [command.label for command in record.commands]
    assert labels == [
        "integration-1",
        "integration-2",
        "integration-3",
        "task-pr-create:auth",
        "task-pr-create:dashboard_api",
    ]
    assert all(command.executed is False for command in record.commands)
    assert record.auto_merge_enabled is False
    assert record.final_pr_created is False


def test_pr_apply_dry_run_with_auto_merge_uses_merge_operator() -> None:
    config_path = find_repo_config(Path("examples"))
    config = load_repo_config(config_path)
    config.git.auto_merge_task_prs_into_integration = True
    run = parse_run_spec(Path("examples/sample_run.md"))
    plan = build_execution_plan(
        config=config,
        run_spec=run,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )

    record = execute_pr_plan(plan, config, execute=False)

    labels = [command.label for command in record.commands]
    assert labels == [
        "integration-1",
        "integration-2",
        "integration-3",
        "task-pr-create:auth",
        "task-pr-merge:auth",
        "task-pr-create:dashboard_api",
        "task-pr-merge:dashboard_api",
        "final-pr-create",
    ]
    merge_record = next(command for command in record.commands if command.label == "task-pr-merge:auth")
    assert merge_record.agent == "codex"
    assert record.auto_merge_enabled is True
    assert record.final_pr_created is True
