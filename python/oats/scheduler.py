"""Ready-queue scheduler for the Oats v2 graph runtime.

The scheduler maintains a ready queue of tasks whose inbound edge predicates
are all satisfied. Tasks are pushed into the queue by edge evaluation on
completion, not pulled by scanning — O(degree) per completion instead of O(|V|).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from oats.envelope import RetryPolicy
from oats.graph import TaskGraph, TaskNode


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class CompletionAction:
    """Describes what the runtime should do after a task completes."""
    kind: Literal["succeed", "retry", "fail"]
    backoff_seconds: float = 0.0


class ReadyQueueScheduler:
    """Ready-queue scheduler wrapping a TaskGraph.

    Maintains the set of running task IDs and delegates readiness evaluation
    to the graph. Enforces concurrency limits.
    """

    def __init__(self, graph: TaskGraph, concurrency_limit: int = 3) -> None:
        self.graph = graph
        self.concurrency_limit = concurrency_limit
        self._running: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ready_tasks(self) -> list[TaskNode]:
        """Return tasks eligible for execution, respecting concurrency limit.

        A task is ready when:
          - status is "pending"
          - all inbound edges are satisfied
          - adding it would not exceed concurrency_limit
        """
        available_slots = self.concurrency_limit - len(self._running)
        if available_slots <= 0:
            return []

        ready_ids = self.graph.ready_tasks()
        return [self.graph.get_node(tid) for tid in ready_ids[:available_slots]]

    def mark_running(self, task_id: str) -> None:
        """Mark a task as running."""
        self.graph.nodes[task_id].status = "running"
        self._running.add(task_id)

    def record_completion(self, task_id: str, *, success: bool) -> None:
        """Record task completion, evaluate outbound edges, update readiness.

        Args:
            task_id: The completed task.
            success: True if task succeeded, False if failed.
        """
        self._running.discard(task_id)

        if success:
            self.graph.record_task_success(task_id)
            self.graph.evaluate_edges_from(task_id)
        else:
            self.graph.nodes[task_id].status = "failed"
            self._propagate_blocked_by_failure(task_id)

    def is_terminal(self) -> bool:
        """True when no tasks are running/pending/queued and ready queue is empty."""
        if self._running:
            return False
        for node in self.graph.nodes.values():
            if node.status in ("pending", "running", "queued"):
                # Check if any pending task could still become ready
                if node.status == "pending":
                    inbound = self.graph.edges_to(node.task_id)
                    if not inbound or all(e.satisfied for e in inbound):
                        return False  # There's a ready task not yet started
                else:
                    return False
        return True

    def record_failure(
        self,
        task_id: str,
        *,
        error_summary: str,
        max_attempts: int = 3,
        current_attempt: int = 1,
        transient_patterns: list[str] | None = None,
        backoff_seconds: list[float] | None = None,
    ) -> CompletionAction:
        """Record a task failure and determine retry vs. fail.

        Returns a CompletionAction indicating whether to retry or fail.
        """
        self._running.discard(task_id)

        if transient_patterns is None:
            transient_patterns = RetryPolicy().transient_patterns
        if backoff_seconds is None:
            backoff_seconds = RetryPolicy().backoff_seconds

        is_transient = any(
            re.search(pattern, error_summary, re.IGNORECASE)
            for pattern in transient_patterns
        )

        if is_transient and current_attempt < max_attempts:
            # Retry with backoff
            idx = min(current_attempt - 1, len(backoff_seconds) - 1)
            backoff = backoff_seconds[idx] if backoff_seconds else 30.0
            self.graph.nodes[task_id].status = "pending"
            return CompletionAction(kind="retry", backoff_seconds=backoff)

        # Non-transient or budget exhausted: fail
        self.graph.nodes[task_id].status = "failed"
        self._propagate_blocked_by_failure(task_id)
        return CompletionAction(kind="fail")

    def reset_running_to_pending(self) -> list[str]:
        """Reset all running tasks to pending (for interruption/resume).

        Returns the list of task IDs that were reset.
        """
        reset_ids = list(self._running)
        for tid in reset_ids:
            self.graph.nodes[tid].status = "pending"
        self._running.clear()
        return reset_ids

    @property
    def running_task_ids(self) -> set[str]:
        return set(self._running)

    # ------------------------------------------------------------------
    # Failure propagation
    # ------------------------------------------------------------------

    def _propagate_blocked_by_failure(self, failed_task_id: str) -> None:
        """Mark all reachable descendants as blocked_by_failure."""
        visited: set[str] = set()
        stack = [failed_task_id]
        while stack:
            current = stack.pop()
            for edge in self.graph.edges_from(current):
                child = edge.to_task
                if child not in visited:
                    visited.add(child)
                    node = self.graph.nodes[child]
                    if node.status in ("pending", "queued", "blocked"):
                        node.status = "blocked_by_failure"
                    stack.append(child)
