"""Large-graph integration tests for the Oats v2 runtime.

Verifies the full system at scale: 10-30 node graphs with multi-level
dependencies, dynamic discovery, concurrent execution, and interruption/resume.
"""

from __future__ import annotations

from oats.discovery import Discovery, insert_discovered_tasks
from oats.graph import EdgePredicate, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.scheduler import ReadyQueueScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_layered_graph(layers: list[int]) -> TaskGraph:
    """Build a layered graph where each layer depends on all tasks in the previous layer.

    E.g., layers=[3, 4, 3] creates 3 root tasks, 4 middle tasks (each depending
    on all 3 roots), and 3 leaf tasks (each depending on all 4 middle tasks).
    Uses code_ready edges for simplicity.
    """
    graph = TaskGraph()
    all_layer_ids: list[list[str]] = []
    task_counter = 0

    for layer_idx, width in enumerate(layers):
        layer_ids: list[str] = []
        for i in range(width):
            tid = f"L{layer_idx}_t{task_counter}"
            task_counter += 1
            graph.add_node(TaskNode(
                task_id=tid, kind=TaskKind.IMPLEMENTATION, title=f"Task {tid}",
            ))
            layer_ids.append(tid)

            # Add edges from previous layer
            if layer_idx > 0:
                for prev_tid in all_layer_ids[layer_idx - 1]:
                    graph.add_edge(TypedEdge(
                        from_task=prev_tid, to_task=tid,
                        predicate=EdgePredicate.CODE_READY,
                    ))
        all_layer_ids.append(layer_ids)

    return graph


def build_test_graph(
    task_ids: list[str],
    deps: dict[str, list[str]] | None = None,
) -> TaskGraph:
    """Build a graph from explicit task IDs and dependency map."""
    graph = TaskGraph()
    for tid in task_ids:
        graph.add_node(TaskNode(
            task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid.upper(),
        ))
    if deps:
        for tid, dep_list in deps.items():
            for dep in dep_list:
                graph.add_edge(TypedEdge(
                    from_task=dep, to_task=tid,
                    predicate=EdgePredicate.CODE_READY,
                ))
    return graph


def run_to_completion(
    scheduler: ReadyQueueScheduler,
    *,
    fail_tasks: set[str] | None = None,
    max_iterations: int = 200,
) -> list[str]:
    """Simulate running the scheduler to completion.

    Returns the order of task completions.
    """
    fail_tasks = fail_tasks or set()
    completion_order: list[str] = []
    iteration = 0

    while not scheduler.is_terminal() and iteration < max_iterations:
        iteration += 1
        ready = scheduler.get_ready_tasks()
        if not ready:
            break  # Deadlock or all blocked

        for task in ready:
            scheduler.mark_running(task.task_id)

        for task in ready:
            if task.task_id in fail_tasks:
                scheduler.record_failure(
                    task.task_id,
                    error_summary="Intentional test failure",
                    max_attempts=1,
                    current_attempt=1,
                )
            else:
                scheduler.record_completion(task.task_id, success=True)
                completion_order.append(task.task_id)

    return completion_order


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLargeGraphExecution:
    def test_20_task_layered_graph_completes(self) -> None:
        """A 20-task graph with 4 levels executes correctly with concurrency 4."""
        graph = build_layered_graph([4, 6, 6, 4])
        assert len(graph.nodes) == 20

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
        completion_order = run_to_completion(scheduler)

        assert len(completion_order) == 20
        assert scheduler.is_terminal()
        assert all(n.status == "succeeded" for n in graph.nodes.values())

        # Verify topological ordering was respected
        completion_index = {tid: i for i, tid in enumerate(completion_order)}
        for edge in graph.edges:
            assert completion_index[edge.from_task] < completion_index[edge.to_task], (
                f"{edge.from_task} should complete before {edge.to_task}"
            )

    def test_30_task_wide_graph_with_high_concurrency(self) -> None:
        """30 independent tasks execute with concurrency 10."""
        graph = TaskGraph()
        for i in range(30):
            graph.add_node(TaskNode(
                task_id=f"t{i}", kind=TaskKind.IMPLEMENTATION, title=f"T{i}",
            ))

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=10)
        completion_order = run_to_completion(scheduler)

        assert len(completion_order) == 30
        assert scheduler.is_terminal()


class TestGraphWithDiscovery:
    def test_mid_run_discovery_and_completion(self) -> None:
        """A task discovers 3 sub-tasks. All complete successfully."""
        graph = build_test_graph(
            ["plan", "api", "frontend", "e2e"],
            {"api": ["plan"], "frontend": ["plan"], "e2e": ["api", "frontend"]},
        )
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # Complete "plan"
        scheduler.mark_running("plan")
        scheduler.record_completion("plan", success=True)

        # Complete "api" — it discovers 2 sub-tasks
        scheduler.mark_running("api")
        scheduler.record_completion("api", success=True)

        discovery = Discovery(
            discovered_by="api",
            tasks=[
                TaskNode(task_id="task_auth", kind=TaskKind.IMPLEMENTATION,
                         title="Auth", discovered_by="api"),
                TaskNode(task_id="task_validate", kind=TaskKind.IMPLEMENTATION,
                         title="Validate", discovered_by="api"),
            ],
            edges_to_add=[
                TypedEdge(from_task="api", to_task="task_auth", predicate=EdgePredicate.CODE_READY),
                TypedEdge(from_task="api", to_task="task_validate", predicate=EdgePredicate.CODE_READY),
                TypedEdge(from_task="task_auth", to_task="e2e", predicate=EdgePredicate.CODE_READY),
            ],
        )
        mutations = insert_discovered_tasks(graph, scheduler, discovery)
        assert len(mutations) == 1
        assert len(graph.nodes) == 6  # 4 original + 2 discovered

        # Discovered tasks should be ready (api completed, edges satisfied)
        ready = scheduler.get_ready_tasks()
        ready_ids = {t.task_id for t in ready}
        assert "task_auth" in ready_ids
        assert "task_validate" in ready_ids

        # Complete remaining tasks
        completion_order = run_to_completion(scheduler)
        assert scheduler.is_terminal()
        assert all(n.status == "succeeded" for n in graph.nodes.values())


class TestInterruptionAndResume:
    def test_interrupted_graph_resumes_correctly(self) -> None:
        """A 15-task graph is interrupted after some completions and resumes."""
        graph = build_layered_graph([3, 5, 4, 3])
        assert len(graph.nodes) == 15

        scheduler = ReadyQueueScheduler(graph, concurrency_limit=3)

        # Complete first layer
        ready = scheduler.get_ready_tasks()
        for t in ready:
            scheduler.mark_running(t.task_id)
        for t in ready:
            scheduler.record_completion(t.task_id, success=True)

        # Start second layer, then "interrupt"
        ready2 = scheduler.get_ready_tasks()
        for t in ready2:
            scheduler.mark_running(t.task_id)

        # Interrupt: reset running tasks
        running = list(scheduler.running_task_ids)
        assert len(running) > 0
        scheduler.reset_running_to_pending()

        # Resume: create new scheduler from same graph
        resumed = ReadyQueueScheduler(graph, concurrency_limit=3)
        completion_order = run_to_completion(resumed)

        assert resumed.is_terminal()
        assert all(n.status == "succeeded" for n in graph.nodes.values())


class TestCascadingFailure:
    def test_failure_blocks_descendants_but_not_independent_branches(self) -> None:
        """Failure in one branch blocks descendants but independent branches complete."""
        graph = build_test_graph(
            ["a", "b", "c", "d", "x", "y"],
            {"b": ["a"], "c": ["b"], "d": ["c"], "y": ["x"]},
        )
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        completion_order = run_to_completion(scheduler, fail_tasks={"a"})

        assert graph.nodes["a"].status == "failed"
        assert graph.nodes["b"].status == "blocked_by_failure"
        assert graph.nodes["c"].status == "blocked_by_failure"
        assert graph.nodes["d"].status == "blocked_by_failure"
        # Independent branch completed
        assert graph.nodes["x"].status == "succeeded"
        assert graph.nodes["y"].status == "succeeded"

    def test_failure_in_diamond_graph(self) -> None:
        """Failure at a merge point blocks only the merge target and descendants."""
        graph = build_test_graph(
            ["a", "b", "c", "d", "e"],
            {"c": ["a", "b"], "d": ["c"], "e": ["c"]},
        )
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # Complete a and b, fail c
        completion_order = run_to_completion(scheduler, fail_tasks={"c"})

        assert graph.nodes["a"].status == "succeeded"
        assert graph.nodes["b"].status == "succeeded"
        assert graph.nodes["c"].status == "failed"
        assert graph.nodes["d"].status == "blocked_by_failure"
        assert graph.nodes["e"].status == "blocked_by_failure"


class TestRetryInLargeGraph:
    def test_transient_failure_with_retry_succeeds(self) -> None:
        """A task with transient failure retries and the graph completes."""
        graph = build_test_graph(
            ["a", "b", "c"],
            {"b": ["a"], "c": ["b"]},
        )
        scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

        # Complete a
        scheduler.mark_running("a")
        scheduler.record_completion("a", success=True)

        # b fails transiently (attempt 1)
        scheduler.mark_running("b")
        action = scheduler.record_failure(
            "b",
            error_summary="Connection reset by peer",
            max_attempts=3,
            current_attempt=1,
        )
        assert action.kind == "retry"

        # b is reset to pending, retry succeeds
        scheduler.mark_running("b")
        scheduler.record_completion("b", success=True)

        # c should now be ready
        ready = scheduler.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "c"

        scheduler.mark_running("c")
        scheduler.record_completion("c", success=True)

        assert scheduler.is_terminal()
        assert all(n.status == "succeeded" for n in graph.nodes.values())
