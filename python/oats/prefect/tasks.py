from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
import uuid

from prefect import runtime, task
from pydantic import BaseModel, Field

from oats.prefect.artifacts import LocalArtifactCheckpointStore
from oats.prefect.models import PrefectFlowPayload, PrefectTaskNode
from oats.prefect.worktree import prepare_task_worktree


class TaskExecutor(Protocol):
    def __call__(
        self,
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
    ) -> dict[str, object]: ...


class CompiledTaskResult(BaseModel):
    task_id: str
    attempt: int
    status: str
    upstream_task_ids: list[str] = Field(default_factory=list)
    result: dict[str, object] = Field(default_factory=dict)


def run_task_with_retries(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    *,
    upstream_results: dict[str, dict[str, object]],
    artifact_store: LocalArtifactCheckpointStore,
    max_retries: int,
    executor: Any = None,
) -> CompiledTaskResult:
    attempt = 1
    while True:
        try:
            return execute_compiled_task_attempt(
                payload,
                task_node,
                upstream_results=upstream_results,
                artifact_store=artifact_store,
                executor=executor,
                attempt=attempt,
            )
        except Exception:
            if attempt > max_retries:
                raise
            attempt += 1


def execute_compiled_task_attempt(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    *,
    upstream_results: dict[str, dict[str, object]],
    artifact_store: LocalArtifactCheckpointStore,
    executor: Any = None,
    attempt: int | None = None,
) -> CompiledTaskResult:
    resolved_attempt = attempt if attempt is not None else _resolve_attempt()
    prepare_task_worktree(payload, task_node)
    artifact_store.write_task_checkpoint(
        task_node,
        status="running",
        attempt=resolved_attempt,
        upstream_task_ids=list(upstream_results),
    )

    try:
        task_result = (executor or _default_executor)(
            task_node,
            upstream_results,
            resolved_attempt,
        )
    except Exception as exc:
        artifact_store.write_task_checkpoint(
            task_node,
            status="failed",
            attempt=resolved_attempt,
            upstream_task_ids=list(upstream_results),
            error=str(exc),
        )
        raise

    result = CompiledTaskResult(
        task_id=task_node.task_id,
        attempt=resolved_attempt,
        status="completed",
        upstream_task_ids=sorted(upstream_results),
        result=dict(task_result),
    )
    artifact_store.write_task_checkpoint(
        task_node,
        status=result.status,
        attempt=result.attempt,
        upstream_task_ids=result.upstream_task_ids,
        result=result.result,
    )
    return result


prefect_compiled_task = task(name="oats-compiled-task", retries=2, retry_delay_seconds=0)(
    execute_compiled_task_attempt
)


def resolve_flow_run_identity(
    *,
    flow_run_id: str | None = None,
    flow_run_name: str | None = None,
) -> tuple[str, str | None]:
    resolved_id = flow_run_id or _runtime_value(runtime.flow_run.id) or f"local-{uuid.uuid4().hex}"
    resolved_name = flow_run_name or _runtime_value(runtime.flow_run.name)
    return resolved_id, resolved_name


def _default_executor(
    task_node: PrefectTaskNode,
    upstream_results: dict[str, dict[str, object]],
    attempt: int,
) -> dict[str, object]:
    return {
        "task_id": task_node.task_id,
        "title": task_node.title,
        "attempt": attempt,
        "upstream_task_ids": sorted(upstream_results),
    }


def _resolve_attempt() -> int:
    value = _runtime_value(runtime.task_run.run_count)
    if isinstance(value, int) and value >= 1:
        return value
    return 1


def _runtime_value(getter: Callable[[], Any] | Any) -> Any:
    try:
        return getter() if callable(getter) else getter
    except Exception:
        return None
