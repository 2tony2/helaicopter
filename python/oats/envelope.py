"""Execution envelope construction for the Oats v2 graph runtime.

Each agent invocation is wrapped in a typed envelope that captures identity,
resource limits, retry policy, and output contract.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from oats.graph import TaskNode
from oats.identity import generate_attempt_id, generate_session_id


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetryPolicy(BaseModel):
    """Retry configuration for a task execution."""

    max_attempts: int = 3
    backoff_seconds: list[float] = Field(default_factory=lambda: [30.0, 120.0, 300.0])
    transient_patterns: list[str] = Field(default_factory=lambda: [
        r"Connection reset",
        r"timeout",
        r"rate limit",
        r"503",
        r"429",
    ])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        loc_by_alias=True,
    )


class ContextSnippet(CamelModel):
    """Relevant source excerpt included in an attack plan."""

    source: str
    content: str
    relevance: str


class AcceptanceCriterion(CamelModel):
    """A structured acceptance criterion for worker verification."""

    description: str


class AttackPlan(CamelModel):
    """Structured prompt payload for worker execution."""

    objective: str
    instructions: str
    context_snippets: list[ContextSnippet] = Field(default_factory=list)
    plan_step_refs: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)


class ExecutionEnvelope(BaseModel):
    """Typed envelope for an agent invocation."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        loc_by_alias=True,
    )

    session_id: str
    attempt_id: str
    task_id: str
    run_id: str
    agent: str                       # claude | codex
    model: str
    reasoning_effort: str | None = None
    worker_id: str | None = None
    dispatch_mode: str | None = None
    worktree_path: str
    parent_branch: str
    timeout_seconds: int
    max_output_tokens: int | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    context: dict = Field(default_factory=dict)
    attack_plan: AttackPlan | None = None
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    discovery_enabled: bool = False


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def build_execution_envelope(
    *,
    task: TaskNode,
    run_id: str,
    agent: str,
    model: str,
    worktree_path: str,
    parent_branch: str,
    timeout_seconds: int = 300,
    max_attempts: int | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    context: dict | None = None,
    worker_id: str | None = None,
    dispatch_mode: str | None = None,
    attack_plan: AttackPlan | None = None,
    acceptance_criteria: list[AcceptanceCriterion] | None = None,
    discovery_enabled: bool = False,
) -> ExecutionEnvelope:
    """Build an execution envelope for a task with fresh session/attempt IDs."""
    retry_policy = RetryPolicy()
    if max_attempts is not None:
        retry_policy = RetryPolicy(max_attempts=max_attempts)

    return ExecutionEnvelope(
        session_id=generate_session_id(),
        attempt_id=generate_attempt_id(),
        task_id=task.task_id,
        run_id=run_id,
        agent=agent,
        model=model,
        reasoning_effort=reasoning_effort,
        worker_id=worker_id,
        dispatch_mode=dispatch_mode,
        worktree_path=worktree_path,
        parent_branch=parent_branch,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        retry_policy=retry_policy,
        context=context or {},
        attack_plan=attack_plan,
        acceptance_criteria=acceptance_criteria or [],
        discovery_enabled=discovery_enabled,
    )
