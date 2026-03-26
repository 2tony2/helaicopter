"""Graph runtime model for Oats v2.

The task DAG with typed edges is the central runtime abstraction. Every run
is a directed acyclic graph of typed nodes connected by typed dependency
edges. The runtime evaluates edge predicates to determine which tasks are
executable.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from helaicopter_domain.vocab import TaskRuntimeStatus


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EdgePredicate(str, Enum):
    """Typed dependency edge predicates."""

    CODE_READY = "code_ready"
    PR_CREATED = "pr_created"
    PR_MERGED = "pr_merged"
    CHECKS_PASSING = "checks_passing"
    REVIEW_APPROVED = "review_approved"
    ARTIFACT_READY = "artifact_ready"


class TaskKind(str, Enum):
    """The kind of work a task node represents."""

    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    MERGE = "merge"
    VERIFICATION = "verification"
    META = "meta"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GraphCycleError(Exception):
    """Raised when an edge would introduce a cycle."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TaskNode(BaseModel):
    """A node in the task graph."""

    task_id: str
    kind: TaskKind = TaskKind.IMPLEMENTATION
    title: str
    prompt: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    status: TaskRuntimeStatus = "pending"
    agent: str | None = None
    model: str | None = None
    discovered_by: str | None = None

    # Flags set by record_* methods for edge evaluation
    pr_created: bool = False
    pr_merged: bool = False
    checks_passing: bool = False
    review_approved: bool = False


class TypedEdge(BaseModel):
    """A typed dependency edge between two task nodes."""

    from_task: str
    to_task: str
    predicate: EdgePredicate
    satisfied: bool = False
    satisfied_at: datetime | None = None


class GraphMutation(BaseModel):
    """Records a dynamic graph modification (discovered tasks)."""

    mutation_id: str
    kind: Literal[
        "insert_tasks",
        "add_edges",
        "remove_edges",
        "pause_run",
        "cancel_task",
        "force_retry_task",
        "reroute_task",
    ]
    discovered_by: str  # task_id
    source: Literal["discovery", "operator"] = "discovery"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nodes_added: list[str] = Field(default_factory=list)
    edges_added: list[TypedEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# TaskGraph
# ---------------------------------------------------------------------------


class TaskGraph(BaseModel):
    """A directed acyclic graph of task nodes connected by typed edges.

    The graph is the single source of truth for scheduling. All readiness,
    state transitions, and ordering derive from graph evaluation.
    """

    nodes: dict[str, TaskNode] = Field(default_factory=dict)
    edges: list[TypedEdge] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: TaskNode) -> None:
        if node.task_id in self.nodes:
            raise ValueError(f"Task '{node.task_id}' already exists in graph")
        self.nodes[node.task_id] = node

    def get_node(self, task_id: str) -> TaskNode:
        return self.nodes[task_id]

    def get_node_optional(self, task_id: str) -> TaskNode | None:
        return self.nodes.get(task_id)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, edge: TypedEdge) -> None:
        """Add a typed edge, rejecting if it would create a cycle."""
        if edge.from_task not in self.nodes:
            raise ValueError(f"Unknown task '{edge.from_task}' in edge source")
        if edge.to_task not in self.nodes:
            raise ValueError(f"Unknown task '{edge.to_task}' in edge target")

        # Temporarily add edge and check for cycles
        self.edges.append(edge)
        if not self._is_acyclic():
            self.edges.pop()
            raise GraphCycleError(
                f"Edge {edge.from_task} -> {edge.to_task} would create a cycle"
            )

    def edges_from(self, task_id: str) -> list[TypedEdge]:
        """All outbound edges from a task."""
        return [e for e in self.edges if e.from_task == task_id]

    def edges_to(self, task_id: str) -> list[TypedEdge]:
        """All inbound edges to a task."""
        return [e for e in self.edges if e.to_task == task_id]

    # ------------------------------------------------------------------
    # State recording
    # ------------------------------------------------------------------

    def record_task_success(self, task_id: str) -> None:
        node = self.nodes[task_id]
        node.status = "succeeded"

    def cancel_task(self, task_id: str) -> None:
        node = self.nodes[task_id]
        node.status = "cancelled"
        for descendant_id in self._descendants_of(task_id):
            descendant = self.nodes[descendant_id]
            if descendant.status in {"pending", "queued", "blocked", "blocked_by_failure"}:
                descendant.status = "blocked_by_failure"

    def force_retry_task(self, task_id: str) -> None:
        self.nodes[task_id].status = "pending"

    def reroute_task(
        self,
        task_id: str,
        *,
        provider: str,
        model: str | None,
    ) -> None:
        node = self.nodes[task_id]
        node.agent = provider
        node.model = model

    def record_pr_created(self, task_id: str) -> None:
        self.nodes[task_id].pr_created = True

    def record_pr_merged(self, task_id: str) -> None:
        node = self.nodes[task_id]
        node.pr_merged = True
        # PR merged implies PR was created
        node.pr_created = True

    def record_checks_passing(self, task_id: str) -> None:
        self.nodes[task_id].checks_passing = True

    def record_review_approved(self, task_id: str) -> None:
        self.nodes[task_id].review_approved = True

    # ------------------------------------------------------------------
    # Edge evaluation
    # ------------------------------------------------------------------

    def evaluate_edges_from(self, task_id: str) -> None:
        """Re-evaluate all outbound edges from a task."""
        node = self.nodes[task_id]
        now = datetime.now(timezone.utc)
        for edge in self.edges_from(task_id):
            was_satisfied = edge.satisfied
            edge.satisfied = self._evaluate_predicate(node, edge.predicate)
            if edge.satisfied and not was_satisfied:
                edge.satisfied_at = now

    def _evaluate_predicate(self, node: TaskNode, predicate: EdgePredicate) -> bool:
        """Check whether a node satisfies a given edge predicate."""
        if predicate == EdgePredicate.CODE_READY:
            return node.status == "succeeded"
        elif predicate == EdgePredicate.PR_CREATED:
            return node.pr_created
        elif predicate == EdgePredicate.PR_MERGED:
            return node.pr_merged
        elif predicate == EdgePredicate.CHECKS_PASSING:
            return node.checks_passing
        elif predicate == EdgePredicate.REVIEW_APPROVED:
            return node.review_approved
        elif predicate == EdgePredicate.ARTIFACT_READY:
            # Artifact readiness is tracked externally; default to code_ready
            return node.status == "succeeded"
        return False

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def is_acyclic(self) -> bool:
        return self._is_acyclic()

    def _is_acyclic(self) -> bool:
        """Kahn's algorithm: returns True if the graph has no cycles."""
        in_degree: dict[str, int] = {tid: 0 for tid in self.nodes}
        for edge in self.edges:
            in_degree[edge.to_task] += 1

        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        visited = 0
        while queue:
            current = queue.popleft()
            visited += 1
            for edge in self.edges:
                if edge.from_task == current:
                    in_degree[edge.to_task] -= 1
                    if in_degree[edge.to_task] == 0:
                        queue.append(edge.to_task)

        return visited == len(self.nodes)

    def _descendants_of(self, task_id: str) -> set[str]:
        descendants: set[str] = set()
        queue = deque([task_id])
        while queue:
            current = queue.popleft()
            for edge in self.edges_from(current):
                if edge.to_task in descendants:
                    continue
                descendants.add(edge.to_task)
                queue.append(edge.to_task)
        return descendants

    def topological_order(self) -> list[str]:
        """Return task IDs in topological order (Kahn's algorithm)."""
        in_degree: dict[str, int] = {tid: 0 for tid in self.nodes}
        for edge in self.edges:
            in_degree[edge.to_task] += 1

        queue = deque(
            sorted(tid for tid, deg in in_degree.items() if deg == 0)
        )
        result: list[str] = []
        while queue:
            current = queue.popleft()
            result.append(current)
            successors = sorted(
                e.to_task for e in self.edges if e.from_task == current
            )
            for succ in successors:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        return result

    def ready_tasks(self) -> list[str]:
        """Return task IDs that are pending and have all inbound edges satisfied."""
        ready = []
        for tid, node in self.nodes.items():
            if node.status != "pending":
                continue
            inbound = self.edges_to(tid)
            if not inbound or all(e.satisfied for e in inbound):
                ready.append(tid)
        # Return in topological order for determinism
        topo = self.topological_order()
        topo_index = {t: i for i, t in enumerate(topo)}
        ready.sort(key=lambda t: topo_index.get(t, 0))
        return ready
