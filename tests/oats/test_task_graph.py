"""Tests for the graph runtime model: construction, typed edges, evaluation."""

from __future__ import annotations

import pytest

from oats.graph import (
    EdgePredicate,
    GraphCycleError,
    TaskGraph,
    TaskKind,
    TaskNode,
    TypedEdge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(task_id: str, kind: TaskKind = TaskKind.IMPLEMENTATION) -> TaskNode:
    return TaskNode(task_id=task_id, kind=kind, title=task_id.capitalize())


def build_linear_graph(ids: list[str]) -> TaskGraph:
    """a -> b -> c  (all code_ready edges)."""
    graph = TaskGraph()
    for tid in ids:
        graph.add_node(_node(tid))
    for i in range(len(ids) - 1):
        graph.add_edge(
            TypedEdge(
                from_task=ids[i],
                to_task=ids[i + 1],
                predicate=EdgePredicate.CODE_READY,
            )
        )
    return graph


def build_diamond_graph() -> TaskGraph:
    """a -> b, a -> c, b -> d, c -> d."""
    graph = TaskGraph()
    for tid in ["a", "b", "c", "d"]:
        graph.add_node(_node(tid))
    for src, dst in [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]:
        graph.add_edge(
            TypedEdge(from_task=src, to_task=dst, predicate=EdgePredicate.CODE_READY)
        )
    return graph


def build_test_spec_graph(
    tasks: list[str],
    deps: dict[str, list[str]],
) -> TaskGraph:
    """Build a graph from task IDs and dependency mapping."""
    graph = TaskGraph()
    for tid in tasks:
        graph.add_node(_node(tid))
    for tid, dep_list in deps.items():
        for dep in dep_list:
            graph.add_edge(
                TypedEdge(
                    from_task=dep,
                    to_task=tid,
                    predicate=EdgePredicate.CODE_READY,
                )
            )
    return graph


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_graph_from_spec_dependencies() -> None:
    """Build a TaskGraph from a spec with 5 tasks and mixed dependencies."""
    graph = build_test_spec_graph(
        tasks=["auth", "models", "api", "dashboard", "e2e"],
        deps={
            "api": ["auth", "models"],
            "dashboard": ["api"],
            "e2e": ["dashboard", "api"],
        },
    )

    assert len(graph.nodes) == 5
    assert len(graph.edges) == 5
    assert all(e.predicate == EdgePredicate.CODE_READY for e in graph.edges)
    assert graph.is_acyclic()


def test_graph_rejects_cycle() -> None:
    """Inserting an edge that creates a cycle must raise."""
    graph = build_linear_graph(["a", "b", "c"])
    with pytest.raises(GraphCycleError):
        graph.add_edge(
            TypedEdge(
                from_task="c", to_task="a", predicate=EdgePredicate.CODE_READY
            )
        )


def test_self_loop_rejected() -> None:
    """A self-loop is also a cycle."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    with pytest.raises(GraphCycleError):
        graph.add_edge(
            TypedEdge(
                from_task="a", to_task="a", predicate=EdgePredicate.CODE_READY
            )
        )


def test_edge_predicate_evaluation_code_ready() -> None:
    """Edge satisfaction changes based on task state."""
    graph = build_linear_graph(["a", "b"])
    edge = graph.edges_to("b")[0]

    assert not edge.satisfied
    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    assert edge.satisfied


def test_typed_edge_pr_merged_requires_pr_state() -> None:
    """A pr_merged edge is not satisfied by code_ready alone."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    graph.add_node(_node("b"))
    graph.add_edge(
        TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.PR_MERGED)
    )

    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    edge = graph.edges_to("b")[0]
    assert not edge.satisfied  # code_ready but not pr_merged

    graph.record_pr_merged("a")
    graph.evaluate_edges_from("a")
    assert edge.satisfied


def test_typed_edge_pr_created() -> None:
    """A pr_created edge requires a PR to exist."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    graph.add_node(_node("b"))
    graph.add_edge(
        TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.PR_CREATED)
    )

    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    assert not graph.edges_to("b")[0].satisfied

    graph.record_pr_created("a")
    graph.evaluate_edges_from("a")
    assert graph.edges_to("b")[0].satisfied


def test_typed_edge_checks_passing() -> None:
    """A checks_passing edge requires checks to pass."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    graph.add_node(_node("b"))
    graph.add_edge(
        TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.CHECKS_PASSING)
    )

    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    assert not graph.edges_to("b")[0].satisfied

    graph.record_checks_passing("a")
    graph.evaluate_edges_from("a")
    assert graph.edges_to("b")[0].satisfied


def test_typed_edge_review_approved() -> None:
    """A review_approved edge requires review approval."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    graph.add_node(_node("b"))
    graph.add_edge(
        TypedEdge(
            from_task="a", to_task="b", predicate=EdgePredicate.REVIEW_APPROVED
        )
    )

    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    assert not graph.edges_to("b")[0].satisfied

    graph.record_review_approved("a")
    graph.evaluate_edges_from("a")
    assert graph.edges_to("b")[0].satisfied


def test_topological_order_respects_edge_types() -> None:
    """Topological sort accounts for edge direction."""
    graph = build_diamond_graph()  # a -> b, a -> c, b -> d, c -> d
    order = graph.topological_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_ready_tasks_initial() -> None:
    """Tasks with no inbound edges are ready initially."""
    graph = build_diamond_graph()
    ready = graph.ready_tasks()
    assert ready == ["a"]


def test_ready_tasks_after_completion() -> None:
    """After completing 'a', both 'b' and 'c' become ready."""
    graph = build_diamond_graph()
    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    ready = graph.ready_tasks()
    assert sorted(ready) == ["b", "c"]


def test_ready_tasks_diamond_full_resolution() -> None:
    """Walk the entire diamond to completion."""
    graph = build_diamond_graph()

    # Initially only a is ready
    assert graph.ready_tasks() == ["a"]

    # Complete a
    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    assert sorted(graph.ready_tasks()) == ["b", "c"]

    # Complete b
    graph.record_task_success("b")
    graph.evaluate_edges_from("b")
    # d still needs c
    assert graph.ready_tasks() == ["c"]

    # Complete c
    graph.record_task_success("c")
    graph.evaluate_edges_from("c")
    assert graph.ready_tasks() == ["d"]


def test_edges_from_and_edges_to() -> None:
    """Verify edge lookup by source and target."""
    graph = build_diamond_graph()

    from_a = graph.edges_from("a")
    assert len(from_a) == 2
    assert {e.to_task for e in from_a} == {"b", "c"}

    to_d = graph.edges_to("d")
    assert len(to_d) == 2
    assert {e.from_task for e in to_d} == {"b", "c"}


def test_add_node_duplicate_rejected() -> None:
    """Adding a node with the same task_id raises."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    with pytest.raises(ValueError, match="already exists"):
        graph.add_node(_node("a"))


def test_add_edge_unknown_task_rejected() -> None:
    """Edges referencing non-existent tasks raise."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    with pytest.raises(ValueError, match="Unknown task"):
        graph.add_edge(
            TypedEdge(
                from_task="a", to_task="z", predicate=EdgePredicate.CODE_READY
            )
        )


def test_graph_node_status_tracking() -> None:
    """Recording success changes the node status."""
    graph = TaskGraph()
    graph.add_node(_node("a"))
    assert graph.get_node("a").status == "pending"

    graph.record_task_success("a")
    assert graph.get_node("a").status == "succeeded"


def test_graph_serialization_roundtrip() -> None:
    """A graph survives Pydantic serialization."""
    graph = build_diamond_graph()
    graph.record_task_success("a")
    graph.evaluate_edges_from("a")

    data = graph.model_dump()
    restored = TaskGraph.model_validate(data)

    assert len(restored.nodes) == 4
    assert len(restored.edges) == 4
    assert restored.get_node("a").status == "succeeded"
    # Edge satisfaction is preserved
    assert any(e.satisfied for e in restored.edges_from("a"))
