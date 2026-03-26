"""Discovered-task protocol for the Oats v2 graph runtime.

Running agents can discover sub-tasks not present in the original plan.
This module handles parsing, validating, and inserting discovered tasks
into the live graph.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from oats.graph import (
    EdgePredicate,
    GraphCycleError,
    GraphMutation,
    TaskGraph,
    TaskKind,
    TaskNode,
    TypedEdge,
)
from oats.identity import generate_mutation_id
from oats.scheduler import ReadyQueueScheduler


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DuplicateTaskIdError(Exception):
    """Raised when a discovered task has an ID that already exists."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DiscoveredTaskSpec(BaseModel):
    """A task discovered at runtime."""

    task_id: str
    title: str
    kind: str = "implementation"
    dependencies: list[dict] = Field(default_factory=list)
    execution: dict = Field(default_factory=dict)


class DiscoveredEdgeSpec(BaseModel):
    """An edge to add from a discovery file."""

    from_task: str = Field(alias="from")
    to_task: str = Field(alias="to")
    predicate: str = "code_ready"

    model_config = {"populate_by_name": True}


class DiscoveryFile(BaseModel):
    """Schema for .oats/discovered/<task_id>.json files."""

    discovered_by: str
    tasks: list[DiscoveredTaskSpec] = Field(default_factory=list)
    edges_to_add: list[DiscoveredEdgeSpec] = Field(default_factory=list)


class Discovery(BaseModel):
    """Validated discovery with graph-ready objects."""

    discovered_by: str
    tasks: list[TaskNode] = Field(default_factory=list)
    edges_to_add: list[TypedEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_discovery_file(raw: dict) -> Discovery:
    """Parse a raw discovery file dict into a validated Discovery object."""
    file = DiscoveryFile.model_validate(raw)

    tasks: list[TaskNode] = []
    edges: list[TypedEdge] = []

    for task_spec in file.tasks:
        kind = TaskKind(task_spec.kind)
        node = TaskNode(
            task_id=task_spec.task_id,
            kind=kind,
            title=task_spec.title,
            discovered_by=file.discovered_by,
        )
        tasks.append(node)

        # Create edges from task dependencies
        for dep in task_spec.dependencies:
            predicate = EdgePredicate(dep.get("predicate", "code_ready"))
            edges.append(TypedEdge(
                from_task=dep["task_id"],
                to_task=task_spec.task_id,
                predicate=predicate,
            ))

    # Add extra edges
    for edge_spec in file.edges_to_add:
        predicate = EdgePredicate(edge_spec.predicate)
        edges.append(TypedEdge(
            from_task=edge_spec.from_task,
            to_task=edge_spec.to_task,
            predicate=predicate,
        ))

    return Discovery(
        discovered_by=file.discovered_by,
        tasks=tasks,
        edges_to_add=edges,
    )


# ---------------------------------------------------------------------------
# Insertion
# ---------------------------------------------------------------------------


def insert_discovered_tasks(
    graph: TaskGraph,
    scheduler: ReadyQueueScheduler,
    discovery: Discovery,
) -> list[GraphMutation]:
    """Insert discovered tasks and edges into the live graph.

    Validates no duplicate IDs and no cycles. Returns the mutations recorded.
    Raises DuplicateTaskIdError or GraphCycleError on validation failure.
    """
    # Validate no duplicate task IDs
    for task in discovery.tasks:
        if task.task_id in graph.nodes:
            raise DuplicateTaskIdError(
                f"Task '{task.task_id}' already exists in graph"
            )

    # Insert nodes first
    for task in discovery.tasks:
        graph.add_node(task)

    # Insert edges (add_edge checks for cycles)
    added_edges: list[TypedEdge] = []
    try:
        for edge in discovery.edges_to_add:
            graph.add_edge(edge)
            added_edges.append(edge)
    except (GraphCycleError, ValueError):
        # Rollback: remove added nodes and edges
        for edge in added_edges:
            if edge in graph.edges:
                graph.edges.remove(edge)
        for task in discovery.tasks:
            graph.nodes.pop(task.task_id, None)
        raise

    # Evaluate edges for newly inserted nodes — edges from already-completed
    # tasks need to be evaluated so the new nodes can become ready
    evaluated_sources: set[str] = set()
    for edge in discovery.edges_to_add:
        if edge.from_task not in evaluated_sources and edge.from_task in graph.nodes:
            graph.evaluate_edges_from(edge.from_task)
            evaluated_sources.add(edge.from_task)

    # Record the mutation
    mutation = GraphMutation(
        mutation_id=generate_mutation_id(),
        kind="insert_tasks",
        discovered_by=discovery.discovered_by,
        timestamp=datetime.now(timezone.utc),
        nodes_added=[t.task_id for t in discovery.tasks],
        edges_added=added_edges,
    )

    return [mutation]
