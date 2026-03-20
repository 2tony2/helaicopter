from __future__ import annotations

import re

from helaicopter_domain.vocab import ProviderName
from oats.models import RepoConfig
from oats.prefect.models import (
    PrefectDeploymentSpec,
    PrefectFlowPayload,
    PrefectTaskEdge,
    PrefectTaskGraph,
    PrefectTaskNode,
)
from oats.prefect.settings import PrefectSettings
from oats.prefect.worktree import build_task_repo_context
from oats.run_definition import CanonicalRunDefinition, CanonicalTaskDefinition
from oats.stacked_prs import derive_initial_task_status, derive_parent_branch
from oats.pr import build_integration_branch_name, build_task_branch_name


SHARED_FLOW_NAME = "oats-compiled-run"
SHARED_FLOW_ENTRYPOINT = "python/oats/prefect/flows.py:run_compiled_oats_flow"


def compile_run_definition(
    run_definition: CanonicalRunDefinition,
    repo_config: RepoConfig,
) -> PrefectDeploymentSpec:
    settings = PrefectSettings()
    integration_branch = build_integration_branch_name(
        repo_config.git.integration_branch_prefix,
        run_definition.title,
    )
    task_branch_map = {
        task.task_id: task.branch_name or build_task_branch_name(repo_config.git.task_branch_prefix, task.task_id)
        for task in run_definition.tasks
    }
    nodes = [
        _compile_task_node(
            task,
            integration_branch=integration_branch,
            task_branch_map=task_branch_map,
            run_title=run_definition.title,
            worktree_dir=run_definition.execution.worktree_dir,
            default_agent=repo_config.agents.executor,
        )
        for task in run_definition.tasks
    ]
    task_graph = PrefectTaskGraph(
        nodes=nodes,
        edges=[
            PrefectTaskEdge(upstream_task_id=dependency, downstream_task_id=task.task_id)
            for task in run_definition.tasks
            for dependency in task.depends_on
        ],
    )
    flow_payload = PrefectFlowPayload(
        run_id=None,
        run_title=run_definition.title,
        source_path=run_definition.source_path,
        repo_root=run_definition.repo_root,
        config_path=run_definition.config_path,
        repo_base_branch=repo_config.repo.base_branch,
        worktree_dir=run_definition.execution.worktree_dir,
        default_concurrency=run_definition.execution.default_concurrency,
        default_validation_commands=list(run_definition.default_validation_commands),
        tasks=nodes,
        task_graph=task_graph,
    )
    deployment_name = _deployment_name(run_definition)

    return PrefectDeploymentSpec(
        flow_name=SHARED_FLOW_NAME,
        deployment_name=deployment_name,
        entrypoint=SHARED_FLOW_ENTRYPOINT,
        description=(
            f"Compiled Oats deployment for {run_definition.title} from "
            f"{run_definition.source_path}"
        ),
        work_pool_name=settings.work_pool,
        work_queue_name=settings.default_queue,
        tags=_build_tags(run_definition, repo_config),
        parameters={"payload": flow_payload.model_dump(mode="json")},
        task_graph=task_graph,
        flow_payload=flow_payload,
    )


def _compile_task_node(
    task: CanonicalTaskDefinition,
    *,
    integration_branch: str,
    task_branch_map: dict[str, str],
    run_title: str,
    worktree_dir: str,
    default_agent: ProviderName,
) -> PrefectTaskNode:
    task_branch = task.branch_name or task_branch_map[task.task_id]
    parent_branch, branch_strategy = (
        (task.parent_branch, task.branch_strategy)
        if task.parent_branch is not None
        else derive_parent_branch(
            _CanonicalStackedTask(task_id=task.task_id, depends_on=list(task.depends_on), branch_name=task_branch),
            feature_branch=integration_branch,
            upstream_branch_map=task_branch_map,
        )
    )
    pr_base = task.pr_base or parent_branch
    initial_task_status = (
        task.initial_task_status
        if task.initial_task_status == "blocked"
        else derive_initial_task_status(task.depends_on)
    )
    return PrefectTaskNode(
        task_id=task.task_id,
        title=task.title,
        prompt=task.prompt,
        depends_on=list(task.depends_on),
        agent=task.agent or default_agent,
        model=task.model,
        reasoning_effort=task.reasoning_effort,
        acceptance_criteria=list(task.acceptance_criteria),
        notes=list(task.notes),
        validation_commands=list(task.validation_commands),
        branch_strategy=branch_strategy,
        initial_task_status=initial_task_status,
        repo_context=build_task_repo_context(
            run_title=run_title,
            task_id=task.task_id,
            worktree_dir=worktree_dir,
            integration_branch=integration_branch,
            task_branch=task_branch,
            parent_branch=parent_branch,
            pr_base=pr_base,
        ),
    )


class _CanonicalStackedTask:
    def __init__(self, *, task_id: str, depends_on: list[str], branch_name: str) -> None:
        self.id = task_id
        self.depends_on = depends_on
        self.branch_name = branch_name


def _deployment_name(run_definition: CanonicalRunDefinition) -> str:
    repo_slug = _slugify(run_definition.repo_root.name)
    run_slug = _slugify(run_definition.title)
    return f"{repo_slug}-{run_slug}"


def _build_tags(run_definition: CanonicalRunDefinition, repo_config: RepoConfig) -> list[str]:
    tags = {
        "oats",
        f"repo:{_slugify(run_definition.repo_root.name)}",
        f"run:{_slugify(run_definition.title)}",
        f"base-branch:{_slugify(repo_config.repo.base_branch)}",
    }
    return sorted(tags)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "run"
