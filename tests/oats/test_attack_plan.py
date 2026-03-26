"""Tests for structured attack plan construction."""

from __future__ import annotations

from oats.attack_plan import PlanStep, build_attack_plan
from oats.envelope import ContextSnippet
from oats.graph import TaskKind, TaskNode


class TestBuildAttackPlan:
    def test_attack_plan_from_task_and_plan_steps(self) -> None:
        """Attack plan assembles objective, instructions, and context from inputs."""
        task = TaskNode(
            task_id="auth",
            kind=TaskKind.IMPLEMENTATION,
            title="Auth Service Setup",
        )
        plan_steps = [
            PlanStep(ref="1.1", text="Create auth middleware with JWT validation"),
            PlanStep(ref="1.2", text="Add rate limiting per-user"),
        ]
        context = [
            ContextSnippet(
                source="src/middleware/index.ts",
                content="export function existingMiddleware() {}",
                relevance="Existing middleware pattern to follow",
            ),
        ]

        plan = build_attack_plan(task, plan_steps=plan_steps, context_snippets=context)

        assert "Auth Service Setup" in plan.objective
        assert "JWT validation" in plan.instructions
        assert len(plan.context_snippets) == 1
        assert plan.plan_step_refs == ["1.1", "1.2"]

    def test_attack_plan_includes_acceptance_criteria(self) -> None:
        """Attack plan includes structured acceptance criteria from the task."""
        task = TaskNode(
            task_id="auth",
            kind=TaskKind.IMPLEMENTATION,
            title="Auth",
            acceptance_criteria=["All tests pass", "No lint errors"],
        )

        plan = build_attack_plan(task, plan_steps=[], context_snippets=[])

        assert len(plan.acceptance_criteria) == 2
        assert plan.acceptance_criteria[0].description == "All tests pass"
