from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol
import uuid

from prefect import runtime, task
from pydantic import BaseModel, Field

from oats.models import PlannedTask
from oats.prefect.artifacts import LocalArtifactCheckpointStore
from oats.prefect.models import PrefectFlowPayload, PrefectTaskNode
from oats.prefect.worktree import prepare_task_worktree
from oats.repo_config import load_repo_config
from oats.runner import AgentInvocationError, build_task_prompt, invoke_agent


class TaskExecutor(Protocol):
    def __call__(
        self,
        payload: PrefectFlowPayload,
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
        worktree_path: Path,
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
    prepared_worktree = prepare_task_worktree(payload, task_node)
    artifact_store.write_task_checkpoint(
        task_node,
        status="running",
        attempt=resolved_attempt,
        upstream_task_ids=list(upstream_results),
    )

    try:
        task_result = (executor or _oats_executor)(
            payload,
            task_node,
            upstream_results,
            resolved_attempt,
            prepared_worktree.worktree_path,
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
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    upstream_results: dict[str, dict[str, object]],
    attempt: int,
    worktree_path: Path,
) -> dict[str, object]:
    del payload, worktree_path
    return {
        "task_id": task_node.task_id,
        "title": task_node.title,
        "attempt": attempt,
        "upstream_task_ids": sorted(upstream_results),
    }


def _oats_executor(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    upstream_results: dict[str, dict[str, object]],
    attempt: int,
    worktree_path: Path,
) -> dict[str, object]:
    config = load_repo_config(payload.config_path)
    planned_task = PlannedTask(
        id=task_node.task_id,
        title=task_node.title,
        prompt=task_node.prompt,
        depends_on=list(task_node.depends_on),
        agent=task_node.agent,
        model=task_node.model,
        reasoning_effort=task_node.reasoning_effort,
        acceptance_criteria=list(task_node.acceptance_criteria),
        validation_commands=list(task_node.validation_commands),
        branch_name=(task_node.repo_context.task_branch if task_node.repo_context else task_node.task_id),
        pr_base=(
            task_node.repo_context.integration_branch
            if task_node.repo_context
            else payload.repo_base_branch
        ),
    )
    prompt = build_task_prompt(
        planned_task,
        payload.run_title,
        read_only=False,
    )
    result = invoke_agent(
        agent_name=planned_task.agent,
        agent_command=config.agent[planned_task.agent],
        role="executor",
        cwd=worktree_path,
        prompt=prompt,
        read_only=False,
        timeout_seconds=1800,
        dangerous_bypass=False,
        model=planned_task.model,
        reasoning_effort=planned_task.reasoning_effort,
        raise_on_nonzero=False,
    )
    if result.timed_out:
        raise TimeoutError(
            f"Executor timed out for task {task_node.task_id} on attempt {attempt}"
        )
    if result.exit_code != 0:
        raise AgentInvocationError(
            f"Executor failed for task {task_node.task_id} with exit code {result.exit_code}\n"
            f"stderr:\n{result.raw_stderr or '<empty>'}"
        )
    return {
        "task_id": task_node.task_id,
        "title": task_node.title,
        "attempt": attempt,
        "upstream_task_ids": sorted(upstream_results),
        "agent": result.agent,
        "model": planned_task.model,
        "reasoning_effort": planned_task.reasoning_effort,
        "session_id": str(result.session_id) if result.session_id is not None else None,
        "output_text": result.output_text,
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
