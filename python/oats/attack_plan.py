"""Structured attack plan construction for worker task execution."""

from __future__ import annotations

from pydantic import BaseModel

from oats.envelope import AcceptanceCriterion, AttackPlan, ContextSnippet
from oats.graph import TaskNode


class PlanStep(BaseModel):
    """A referenced implementation plan step."""

    ref: str
    text: str


def build_attack_plan(
    task: TaskNode,
    *,
    plan_steps: list[PlanStep],
    context_snippets: list[ContextSnippet],
) -> AttackPlan:
    """Build a structured attack plan from task metadata and supporting context."""
    criteria = [
        AcceptanceCriterion(description=criterion)
        for criterion in task.acceptance_criteria
    ]

    sections = [f"# Objective\n\n{task.title}"]
    if task.prompt:
        sections.append(f"# Task Prompt\n\n{task.prompt}")
    if plan_steps:
        rendered_steps = "\n".join(f"- `{step.ref}` {step.text}" for step in plan_steps)
        sections.append(f"# Plan Steps\n\n{rendered_steps}")
    if criteria:
        rendered_criteria = "\n".join(f"- {criterion.description}" for criterion in criteria)
        sections.append(f"# Acceptance Criteria\n\n{rendered_criteria}")
    if context_snippets:
        rendered_context = "\n".join(
            f"- `{snippet.source}`: {snippet.relevance}" for snippet in context_snippets
        )
        sections.append(f"# Context\n\n{rendered_context}")

    return AttackPlan(
        objective=task.title,
        instructions="\n\n".join(sections),
        context_snippets=context_snippets,
        plan_step_refs=[step.ref for step in plan_steps],
        acceptance_criteria=criteria,
    )
