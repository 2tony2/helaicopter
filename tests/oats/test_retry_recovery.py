"""Tests for retry/recovery state machine and failure propagation."""

from __future__ import annotations

import re

from oats.graph import EdgePredicate, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.scheduler import ReadyQueueScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_linear_graph(task_ids: list[str], *, max_attempts: int = 3) -> TaskGraph:
    graph = TaskGraph()
    for tid in task_ids:
        graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid.upper()))
    for i in range(len(task_ids) - 1):
        graph.add_edge(TypedEdge(
            from_task=task_ids[i], to_task=task_ids[i + 1],
            predicate=EdgePredicate.CODE_READY,
        ))
    return graph


def build_single_task_graph(task_id: str) -> TaskGraph:
    graph = TaskGraph()
    graph.add_node(TaskNode(task_id=task_id, kind=TaskKind.IMPLEMENTATION, title=task_id.upper()))
    return graph


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------

class TestTransientRetry:
    def test_transient_failure_triggers_retry(self) -> None:
        """A failure matching a transient pattern should allow retry."""
        graph = build_linear_graph(["a", "b"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        scheduler.mark_running("a")

        action = scheduler.record_failure(
            "a",
            error_summary="Connection reset by peer",
            max_attempts=3,
            current_attempt=1,
        )

        assert action.kind == "retry"
        assert action.backoff_seconds > 0

    def test_non_transient_failure_marks_failed_and_propagates(self) -> None:
        """A non-transient failure marks the task failed and blocks descendants."""
        graph = build_linear_graph(["a", "b", "c"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        scheduler.mark_running("a")

        action = scheduler.record_failure(
            "a",
            error_summary="SyntaxError in generated code",
            max_attempts=3,
            current_attempt=1,
        )

        assert action.kind == "fail"
        assert graph.nodes["b"].status == "blocked_by_failure"
        assert graph.nodes["c"].status == "blocked_by_failure"


class TestRetryBudget:
    def test_budget_exhaustion_marks_failed(self) -> None:
        """After max_attempts failures, task is marked failed regardless of transience."""
        graph = build_single_task_graph("a")
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # Attempt 1 - transient failure
        scheduler.mark_running("a")
        action1 = scheduler.record_failure(
            "a",
            error_summary="Connection reset by peer",
            max_attempts=2,
            current_attempt=1,
        )
        assert action1.kind == "retry"

        # Reset to pending for retry
        graph.nodes["a"].status = "pending"

        # Attempt 2 - transient failure but budget exhausted
        scheduler.mark_running("a")
        action2 = scheduler.record_failure(
            "a",
            error_summary="Connection reset by peer",
            max_attempts=2,
            current_attempt=2,
        )
        assert action2.kind == "fail"
        assert graph.nodes["a"].status == "failed"


class TestFailurePropagation:
    def test_deep_chain_propagation(self) -> None:
        """Failure in first task blocks all descendants in chain."""
        graph = build_linear_graph(["a", "b", "c", "d"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        scheduler.mark_running("a")

        scheduler.record_failure(
            "a", error_summary="Fatal error", max_attempts=1, current_attempt=1,
        )

        assert graph.nodes["a"].status == "failed"
        assert graph.nodes["b"].status == "blocked_by_failure"
        assert graph.nodes["c"].status == "blocked_by_failure"
        assert graph.nodes["d"].status == "blocked_by_failure"

    def test_independent_branches_not_affected(self) -> None:
        """Failure in one branch doesn't affect independent branches."""
        graph = TaskGraph()
        for tid in ["a", "b", "x", "y"]:
            graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid))
        graph.add_edge(TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.CODE_READY))
        graph.add_edge(TypedEdge(from_task="x", to_task="y", predicate=EdgePredicate.CODE_READY))

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        scheduler.mark_running("a")
        scheduler.record_failure(
            "a", error_summary="Fatal", max_attempts=1, current_attempt=1,
        )

        assert graph.nodes["a"].status == "failed"
        assert graph.nodes["b"].status == "blocked_by_failure"
        # Independent branch untouched
        assert graph.nodes["x"].status == "pending"
        assert graph.nodes["y"].status == "pending"


class TestTerminalWithFailures:
    def test_terminal_with_mixed_success_and_blocked(self) -> None:
        """Terminal state reached when some tasks succeeded and others are blocked."""
        graph = TaskGraph()
        for tid in ["a", "b", "x", "y"]:
            graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid))
        graph.add_edge(TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.CODE_READY))
        graph.add_edge(TypedEdge(from_task="x", to_task="y", predicate=EdgePredicate.CODE_READY))

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # Fail a, succeed x
        scheduler.mark_running("a")
        scheduler.record_failure("a", error_summary="Fatal", max_attempts=1, current_attempt=1)

        scheduler.mark_running("x")
        scheduler.record_completion("x", success=True)
        scheduler.mark_running("y")
        scheduler.record_completion("y", success=True)

        assert scheduler.is_terminal()
