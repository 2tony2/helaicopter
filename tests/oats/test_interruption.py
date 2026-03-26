"""Tests for interruption handling and resume."""

from __future__ import annotations

from oats.graph import EdgePredicate, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.scheduler import ReadyQueueScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_wide_graph(width: int) -> TaskGraph:
    graph = TaskGraph()
    for i in range(width):
        graph.add_node(TaskNode(task_id=f"t{i}", kind=TaskKind.IMPLEMENTATION, title=f"T{i}"))
    return graph


def build_linear_graph(task_ids: list[str]) -> TaskGraph:
    graph = TaskGraph()
    for tid in task_ids:
        graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid.upper()))
    for i in range(len(task_ids) - 1):
        graph.add_edge(TypedEdge(
            from_task=task_ids[i], to_task=task_ids[i + 1],
            predicate=EdgePredicate.CODE_READY,
        ))
    return graph


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInterruption:
    def test_snapshot_running_tasks(self) -> None:
        """Can snapshot which tasks are currently running for interruption record."""
        graph = build_wide_graph(5)
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=3)

        ready = scheduler.get_ready_tasks()
        for t in ready:
            scheduler.mark_running(t.task_id)

        assert len(scheduler.running_task_ids) == 3

    def test_mark_running_tasks_as_pending_for_resume(self) -> None:
        """After interruption, running tasks should be reset to pending for resume."""
        graph = build_wide_graph(5)
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=3)

        ready = scheduler.get_ready_tasks()
        for t in ready:
            scheduler.mark_running(t.task_id)

        # Simulate interruption: reset running tasks
        running_ids = list(scheduler.running_task_ids)
        scheduler.reset_running_to_pending()

        for tid in running_ids:
            assert graph.nodes[tid].status == "pending"
        assert len(scheduler.running_task_ids) == 0


class TestResumeFromPersistedState:
    def test_resume_rebuilds_ready_queue(self) -> None:
        """Resuming from a state where some tasks completed rebuilds correct ready queue."""
        graph = build_linear_graph(["a", "b", "c"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # Complete a
        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)

        # b was running at interruption, reset to pending
        scheduler.mark_running("b")
        scheduler.reset_running_to_pending()

        # Create new scheduler (simulating resume from persisted graph)
        new_scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        ready = new_scheduler.get_ready_tasks()

        assert "b" in [t.task_id for t in ready]

    def test_resume_skips_completed_and_failed(self) -> None:
        """Resume doesn't re-queue completed or failed tasks."""
        graph = TaskGraph()
        for tid in ["a", "b", "c", "d"]:
            graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid))
        graph.add_edge(TypedEdge(from_task="a", to_task="c", predicate=EdgePredicate.CODE_READY))
        graph.add_edge(TypedEdge(from_task="b", to_task="d", predicate=EdgePredicate.CODE_READY))

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # a succeeded, b failed
        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)
        scheduler.mark_running("b")
        scheduler.record_failure("b", error_summary="Fatal", max_attempts=1, current_attempt=1)

        # Resume
        new_scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        ready = new_scheduler.get_ready_tasks()

        ready_ids = [t.task_id for t in ready]
        assert "c" in ready_ids  # a succeeded, c is ready
        assert "a" not in ready_ids
        assert "b" not in ready_ids
        assert "d" not in ready_ids  # blocked_by_failure
