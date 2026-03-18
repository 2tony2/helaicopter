from __future__ import annotations

from pathlib import Path

from oats.models import ExecutionPlan, PlannedTask, RepoConfig, RunSpec
from oats.pr import build_final_pr_title, build_task_branch_name


class PlanError(RuntimeError):
    """Raised when the execution plan is invalid."""


def build_execution_plan(
    config: RepoConfig,
    run_spec: RunSpec,
    repo_root: Path,
    config_path: Path,
) -> ExecutionPlan:
    task_ids = {task.id for task in run_spec.tasks}
    planned_tasks: list[PlannedTask] = []
    integration_branch = _build_integration_branch(
        config.git.integration_branch_prefix,
        run_spec.title,
    )

    for task in run_spec.tasks:
        unknown_deps = sorted(dep for dep in task.depends_on if dep not in task_ids)
        if unknown_deps:
            joined = ", ".join(unknown_deps)
            raise PlanError(f"Task '{task.id}' depends on unknown tasks: {joined}")

        validation_commands = (
            task.validation_override
            if task.validation_override
            else config.validation.commands
        )
        planned_tasks.append(
            PlannedTask(
                id=task.id,
                title=task.title or task.id.replace("_", " ").replace("-", " ").title(),
                prompt=task.prompt,
                depends_on=task.depends_on,
                acceptance_criteria=task.acceptance_criteria,
                validation_commands=validation_commands,
                branch_name=build_task_branch_name(config.git.task_branch_prefix, task.id),
                pr_base=integration_branch,
            )
        )

    _validate_acyclic(planned_tasks)
    return ExecutionPlan(
        run_title=run_spec.title,
        repo_root=repo_root.resolve(),
        config_path=config_path.resolve(),
        run_spec_path=run_spec.source_path.resolve(),
        integration_branch=integration_branch,
        task_pr_target=integration_branch,
        final_pr_target=config.git.final_pr_target,
        integration_branch_base=config.git.integration_branch_base,
        require_manual_final_review=config.git.require_manual_final_review,
        final_pr_title=build_final_pr_title(run_spec.title),
        tasks=planned_tasks,
    )


def _validate_acyclic(tasks: list[PlannedTask]) -> None:
    adjacency = {task.id: task.depends_on for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise PlanError(f"Cycle detected involving task '{task_id}'")
        visiting.add(task_id)
        for dependency in adjacency[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task.id)


def _build_integration_branch(prefix: str, run_title: str) -> str:
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    slug = "".join(
        char.lower() if char.isalnum() else "-"
        for char in run_title.strip()
    )
    compact_slug = "-".join(segment for segment in slug.split("-") if segment)
    compact_slug = compact_slug or "run"
    return f"{normalized_prefix}{compact_slug}"
