from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from prefect import flow
from pydantic import BaseModel, Field

from oats.prefect.artifacts import LocalArtifactCheckpointStore
from oats.prefect.models import PrefectFlowPayload
from oats.prefect.tasks import CompiledTaskResult, resolve_flow_run_identity, run_task_with_retries


class CompiledFlowRunResult(BaseModel):
    flow_run_id: str
    flow_run_name: str | None = None
    artifact_root: Path
    metadata_path: Path
    execution_order: list[str] = Field(default_factory=list)
    task_results: dict[str, CompiledTaskResult] = Field(default_factory=dict)


@flow(name="oats-compiled-run")
def run_compiled_oats_flow(
    payload: PrefectFlowPayload | dict[str, Any],
    *,
    executor: Any = None,
    flow_run_id: str | None = None,
    flow_run_name: str | None = None,
    max_retries: int = 0,
) -> CompiledFlowRunResult:
    return execute_compiled_flow_graph(
        payload,
        executor=executor,
        flow_run_id=flow_run_id,
        flow_run_name=flow_run_name,
        max_retries=max_retries,
    )


def execute_compiled_flow_graph(
    payload: PrefectFlowPayload | dict[str, Any],
    *,
    executor: Any = None,
    flow_run_id: str | None = None,
    flow_run_name: str | None = None,
    max_retries: int = 0,
) -> CompiledFlowRunResult:
    compiled_payload = _coerce_payload(payload)
    resolved_flow_run_id, resolved_flow_run_name = resolve_flow_run_identity(
        flow_run_id=flow_run_id,
        flow_run_name=flow_run_name,
    )
    artifact_store = LocalArtifactCheckpointStore(
        payload=compiled_payload,
        flow_run_id=resolved_flow_run_id,
        flow_run_name=resolved_flow_run_name,
    )
    metadata_path = artifact_store.initialize()

    execution_order = _topological_order(compiled_payload)
    nodes_by_id = {task.task_id: task for task in compiled_payload.tasks}
    task_results: dict[str, CompiledTaskResult] = {}

    try:
        for task_id in execution_order:
            task_node = nodes_by_id[task_id]
            upstream_results = {
                upstream_task_id: task_results[upstream_task_id].result
                for upstream_task_id in task_node.depends_on
            }
            task_results[task_id] = run_task_with_retries(
                compiled_payload,
                task_node,
                upstream_results=upstream_results,
                artifact_store=artifact_store,
                max_retries=max_retries,
                executor=executor,
            )
    finally:
        artifact_store.finalize()

    return CompiledFlowRunResult(
        flow_run_id=resolved_flow_run_id,
        flow_run_name=resolved_flow_run_name,
        artifact_root=artifact_store.paths.artifact_root,
        metadata_path=metadata_path,
        execution_order=execution_order,
        task_results=task_results,
    )


def _coerce_payload(payload: PrefectFlowPayload | dict[str, Any]) -> PrefectFlowPayload:
    if isinstance(payload, PrefectFlowPayload):
        return payload
    return PrefectFlowPayload.model_validate(payload)


def _topological_order(payload: PrefectFlowPayload) -> list[str]:
    ordered_task_ids = [task.task_id for task in payload.tasks]
    nodes_by_id = {task.task_id: task for task in payload.tasks}
    dependency_map = {task.task_id: set(task.depends_on) for task in payload.tasks}

    for edge in payload.task_graph.edges:
        if edge.downstream_task_id not in dependency_map:
            raise ValueError(f"Unknown downstream task in graph: {edge.downstream_task_id}")
        if edge.upstream_task_id not in nodes_by_id:
            raise ValueError(f"Unknown upstream task in graph: {edge.upstream_task_id}")
        dependency_map[edge.downstream_task_id].add(edge.upstream_task_id)

    indegree = {task_id: len(dependencies) for task_id, dependencies in dependency_map.items()}
    dependents: dict[str, list[str]] = {task_id: [] for task_id in ordered_task_ids}
    for task_id, dependencies in dependency_map.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, []).append(task_id)

    queue = deque(task_id for task_id in ordered_task_ids if indegree[task_id] == 0)
    ordered: list[str] = []
    while queue:
        task_id = queue.popleft()
        ordered.append(task_id)
        for dependent in dependents.get(task_id, []):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) != len(ordered_task_ids):
        raise ValueError("Task graph contains a cycle or unresolved dependency")
    return ordered
