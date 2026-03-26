"""Tests for dynamic discovered-task insertion."""

from __future__ import annotations

import pytest

from oats.discovery import (
    Discovery,
    DuplicateTaskIdError,
    insert_discovered_tasks,
    parse_discovery_file,
)
from oats.graph import EdgePredicate, GraphCycleError, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.scheduler import ReadyQueueScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
# Tests: Parsing
# ---------------------------------------------------------------------------

class TestParseDiscoveryFile:
    def test_parse_discovery_file(self) -> None:
        """Discovery file is parsed into validated task and edge objects."""
        raw = {
            "discovered_by": "api",
            "tasks": [
                {
                    "task_id": "task_extract-middleware",
                    "title": "Extract shared auth middleware",
                    "kind": "implementation",
                    "dependencies": [{"task_id": "api", "predicate": "code_ready"}],
                    "execution": {"agent": "codex", "model": "o3-pro"},
                }
            ],
            "edges_to_add": [
                {"from": "task_extract-middleware", "to": "dashboard", "predicate": "code_ready"}
            ],
        }
        discovery = parse_discovery_file(raw)
        assert len(discovery.tasks) == 1
        assert discovery.tasks[0].task_id == "task_extract-middleware"
        assert discovery.discovered_by == "api"
        # 1 dependency edge (api -> task_extract-middleware) + 1 explicit edge
        assert len(discovery.edges_to_add) == 2


# ---------------------------------------------------------------------------
# Tests: Graph insertion
# ---------------------------------------------------------------------------

class TestInsertDiscoveredTasks:
    def test_insert_discovered_tasks_into_live_graph(self) -> None:
        """Discovered tasks and edges are inserted and participate in scheduling."""
        graph = build_linear_graph(["a", "b"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        discovery = Discovery(
            discovered_by="a",
            tasks=[TaskNode(task_id="a1", kind=TaskKind.IMPLEMENTATION, title="Sub-task",
                            discovered_by="a")],
            edges_to_add=[
                TypedEdge(from_task="a", to_task="a1", predicate=EdgePredicate.CODE_READY),
                TypedEdge(from_task="a1", to_task="b", predicate=EdgePredicate.CODE_READY),
            ],
        )

        graph.record_task_success("a")
        graph.evaluate_edges_from("a")
        mutations = insert_discovered_tasks(graph, scheduler, discovery)

        assert "a1" in graph.nodes
        assert len(mutations) == 1
        assert mutations[0].nodes_added == ["a1"]

        # a1 should be in ready queue (a is succeeded, code_ready edge is satisfied)
        ready = scheduler.get_ready_tasks()
        assert "a1" in [t.task_id for t in ready]

    def test_discovery_rejects_cycle(self) -> None:
        """Discovery that would create a cycle is rejected."""
        graph = build_linear_graph(["a", "b", "c"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        discovery = Discovery(
            discovered_by="c",
            tasks=[],
            edges_to_add=[TypedEdge(from_task="c", to_task="a", predicate=EdgePredicate.CODE_READY)],
        )

        with pytest.raises(GraphCycleError):
            insert_discovered_tasks(graph, scheduler, discovery)

    def test_discovery_rejects_duplicate_task_id(self) -> None:
        """Discovery with a task_id that already exists is rejected."""
        graph = build_linear_graph(["a", "b"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        discovery = Discovery(
            discovered_by="a",
            tasks=[TaskNode(task_id="b", kind=TaskKind.IMPLEMENTATION, title="Duplicate")],
            edges_to_add=[],
        )

        with pytest.raises(DuplicateTaskIdError):
            insert_discovered_tasks(graph, scheduler, discovery)

    def test_graph_mutations_logged_with_provenance(self) -> None:
        """Graph mutations are recorded with timestamp and discovering task."""
        graph = build_linear_graph(["a", "b"])
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        graph.record_task_success("a")
        graph.evaluate_edges_from("a")

        discovery = Discovery(
            discovered_by="a",
            tasks=[TaskNode(task_id="a1", kind=TaskKind.IMPLEMENTATION, title="Sub", discovered_by="a")],
            edges_to_add=[TypedEdge(from_task="a", to_task="a1", predicate=EdgePredicate.CODE_READY)],
        )
        mutations = insert_discovered_tasks(graph, scheduler, discovery)

        assert mutations[0].discovered_by == "a"
        assert mutations[0].kind == "insert_tasks"
        assert mutations[0].mutation_id.startswith("mut_")

    def test_discovered_tasks_with_satisfied_deps_immediately_ready(self) -> None:
        """If a discovered task's dependencies are already satisfied, it's immediately ready."""
        graph = TaskGraph()
        graph.add_node(TaskNode(task_id="a", kind=TaskKind.IMPLEMENTATION, title="A"))
        graph.record_task_success("a")

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        discovery = Discovery(
            discovered_by="a",
            tasks=[TaskNode(task_id="a1", kind=TaskKind.IMPLEMENTATION, title="Sub", discovered_by="a")],
            edges_to_add=[TypedEdge(from_task="a", to_task="a1", predicate=EdgePredicate.CODE_READY)],
        )
        insert_discovered_tasks(graph, scheduler, discovery)

        ready = scheduler.get_ready_tasks()
        assert "a1" in [t.task_id for t in ready]
