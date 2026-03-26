"""Tests for the ready-queue scheduler."""

from __future__ import annotations

import pytest

from oats.graph import EdgePredicate, GraphCycleError, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.scheduler import ReadyQueueScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_linear_graph(task_ids: list[str]) -> TaskGraph:
    """Build a -> b -> c linear graph with code_ready edges."""
    graph = TaskGraph()
    for tid in task_ids:
        graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid.upper()))
    for i in range(len(task_ids) - 1):
        graph.add_edge(TypedEdge(
            from_task=task_ids[i], to_task=task_ids[i + 1],
            predicate=EdgePredicate.CODE_READY,
        ))
    return graph


def build_diamond_graph() -> TaskGraph:
    """a -> b, a -> c, b -> d, c -> d."""
    graph = TaskGraph()
    for tid in ["a", "b", "c", "d"]:
        graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid.upper()))
    graph.add_edge(TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.CODE_READY))
    graph.add_edge(TypedEdge(from_task="a", to_task="c", predicate=EdgePredicate.CODE_READY))
    graph.add_edge(TypedEdge(from_task="b", to_task="d", predicate=EdgePredicate.CODE_READY))
    graph.add_edge(TypedEdge(from_task="c", to_task="d", predicate=EdgePredicate.CODE_READY))
    return graph


def build_wide_graph(width: int) -> TaskGraph:
    """N independent tasks with no dependencies."""
    graph = TaskGraph()
    for i in range(width):
        graph.add_node(TaskNode(task_id=f"t{i}", kind=TaskKind.IMPLEMENTATION, title=f"T{i}"))
    return graph


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReadyQueueSeeding:
    def test_seeds_ready_queue_from_graph(self) -> None:
        """Tasks with no inbound edges are immediately ready."""
        graph = build_diamond_graph()
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=2)
        ready = scheduler.get_ready_tasks()
        assert [t.task_id for t in ready] == ["a"]

    def test_wide_graph_all_tasks_ready(self) -> None:
        """Independent tasks are all ready."""
        graph = build_wide_graph(5)
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=10)
        ready = scheduler.get_ready_tasks()
        assert len(ready) == 5


class TestCompletionAndEnqueue:
    def test_enqueues_dependents_after_completion(self) -> None:
        """Completing a task evaluates outbound edges and enqueues newly-ready dependents."""
        graph = build_diamond_graph()
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)

        ready = scheduler.get_ready_tasks()
        assert set(t.task_id for t in ready) == {"b", "c"}

    def test_diamond_requires_both_parents(self) -> None:
        """Task d needs both b and c completed."""
        graph = build_diamond_graph()
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)

        scheduler.mark_running("b")
        scheduler.record_completion("b", success=True)

        # d should NOT be ready yet (c not completed)
        ready = scheduler.get_ready_tasks()
        assert set(t.task_id for t in ready) == {"c"}

        scheduler.mark_running("c")
        scheduler.record_completion("c", success=True)

        ready = scheduler.get_ready_tasks()
        assert [t.task_id for t in ready] == ["d"]


class TestConcurrencyLimit:
    def test_respects_concurrency_limit(self) -> None:
        """Cannot exceed concurrency_limit running tasks."""
        graph = build_wide_graph(10)
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=3)
        ready = scheduler.get_ready_tasks()
        assert len(ready) == 3

    def test_returns_more_after_completions(self) -> None:
        """After completing tasks, more slots open."""
        graph = build_wide_graph(10)
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=2)

        ready = scheduler.get_ready_tasks()
        assert len(ready) == 2
        for t in ready:
            scheduler.mark_running(t.task_id)

        scheduler.record_completion(ready[0].task_id, success=True)
        ready2 = scheduler.get_ready_tasks()
        assert len(ready2) == 1  # one slot opened


class TestTypedEdgeBlocking:
    def test_blocks_on_unsatisfied_pr_merged_edge(self) -> None:
        """A task behind a pr_merged edge does not become ready on code_ready alone."""
        graph = TaskGraph()
        graph.add_node(TaskNode(task_id="a", kind=TaskKind.IMPLEMENTATION, title="A"))
        graph.add_node(TaskNode(task_id="b", kind=TaskKind.IMPLEMENTATION, title="B"))
        graph.add_edge(TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.PR_MERGED))
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)

        ready = scheduler.get_ready_tasks()
        assert len(ready) == 0  # b is not ready — pr_merged not satisfied


class TestTerminalState:
    def test_detects_terminal_state(self) -> None:
        """Scheduler is terminal when all tasks are succeeded/failed and nothing is running."""
        graph = build_linear_graph(["a", "b"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        assert not scheduler.is_terminal()

        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)
        scheduler.mark_running("b")
        scheduler.record_completion("b", success=True)

        assert scheduler.is_terminal()

    def test_not_terminal_while_running(self) -> None:
        graph = build_linear_graph(["a", "b"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        scheduler.mark_running("a")
        assert not scheduler.is_terminal()
