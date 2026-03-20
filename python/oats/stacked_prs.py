from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from helaicopter_domain.vocab import TaskRuntimeStatus

BranchStrategy = Literal["feature_base", "single_parent", "after_dependency_merges"]


class _DependencyTask(Protocol):
    id: str
    depends_on: list[str]
    branch_name: str


class StackedTaskPlan(BaseModel):
    task_id: str
    branch_name: str
    depends_on: list[str] = Field(default_factory=list)
    parent_branch: str
    pr_base: str
    branch_strategy: BranchStrategy
    initial_task_status: TaskRuntimeStatus


def derive_parent_branch(
    task: _DependencyTask,
    *,
    feature_branch: str,
    upstream_branch_map: Mapping[str, str],
) -> tuple[str, BranchStrategy]:
    if not task.depends_on:
        return feature_branch, "feature_base"
    if len(task.depends_on) == 1:
        return upstream_branch_map[task.depends_on[0]], "single_parent"
    return feature_branch, "after_dependency_merges"


def derive_initial_task_status(depends_on: Sequence[str]) -> TaskRuntimeStatus:
    return "blocked" if len(depends_on) > 1 else "pending"


def derive_stacked_pr_graph(
    tasks: Sequence[_DependencyTask],
    *,
    feature_branch: str,
) -> dict[str, StackedTaskPlan]:
    upstream_branch_map = {task.id: task.branch_name for task in tasks}
    graph: dict[str, StackedTaskPlan] = {}
    for task in tasks:
        parent_branch, branch_strategy = derive_parent_branch(
            task,
            feature_branch=feature_branch,
            upstream_branch_map=upstream_branch_map,
        )
        graph[task.id] = StackedTaskPlan(
            task_id=task.id,
            branch_name=task.branch_name,
            depends_on=list(task.depends_on),
            parent_branch=parent_branch,
            pr_base=parent_branch,
            branch_strategy=branch_strategy,
            initial_task_status=derive_initial_task_status(task.depends_on),
        )
    return graph
