from __future__ import annotations

import re

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


SHARED_FLOW_NAME = "oats-compiled-run"
SHARED_FLOW_ENTRYPOINT = "python/oats/prefect/flows.py:run_compiled_oats_flow"


def compile_run_definition(
    run_definition: CanonicalRunDefinition,
    repo_config: RepoConfig,
) -> PrefectDeploymentSpec:
    settings = PrefectSettings()
    nodes = [
        _compile_task_node(
            task,
            run_title=run_definition.title,
            worktree_dir=run_definition.execution.worktree_dir,
            task_branch_prefix=repo_config.git.task_branch_prefix,
            integration_branch_prefix=repo_config.git.integration_branch_prefix,
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
    run_title: str,
    worktree_dir: str,
    task_branch_prefix: str,
    integration_branch_prefix: str,
    default_agent: str,
) -> PrefectTaskNode:
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
        repo_context=build_task_repo_context(
            run_title=run_title,
            task_id=task.task_id,
            worktree_dir=worktree_dir,
            task_branch_prefix=task_branch_prefix,
            integration_branch_prefix=integration_branch_prefix,
        ),
    )


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
