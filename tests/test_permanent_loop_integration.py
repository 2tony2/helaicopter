"""Integration coverage for the permanent worker loop architecture."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from oats.graph import EdgePredicate, TaskGraph, TaskKind, TaskNode, TypedEdge
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop, TaskResult


def _make_node(
    task_id: str,
    *,
    agent: str = "claude",
    model: str = "claude-sonnet-4-6",
    status: str = "pending",
) -> TaskNode:
    return TaskNode(
        task_id=task_id,
        title=task_id,
        kind=TaskKind.IMPLEMENTATION,
        agent=agent,
        model=model,
        status=status,
    )


def build_graph(nodes: list[TaskNode], edges: list[TypedEdge] | None = None) -> TaskGraph:
    graph = TaskGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    return graph


def _find_worker_for_task(
    registry: InMemoryWorkerRegistry,
    *,
    run_id: str,
    task_id: str,
) -> str | None:
    for worker in registry.all_workers():
        if worker.current_run_id == run_id and worker.current_task_id == task_id:
            return worker.worker_id
    return None


async def run_to_completion(
    resolver: ResolverLoop,
    *,
    graphs: dict[str, TaskGraph],
    max_ticks: int = 20,
) -> None:
    for _ in range(max_ticks):
        await resolver.tick()
        progress = False
        for run_id, graph in graphs.items():
            for node in graph.nodes.values():
                if node.status == "running":
                    worker_id = _find_worker_for_task(
                        resolver._registry,
                        run_id=run_id,
                        task_id=node.task_id,
                    )
                    assert worker_id is not None
                    resolver.submit_completion(
                        TaskResult(
                            task_id=node.task_id,
                            run_id=run_id,
                            worker_id=worker_id,
                            status="succeeded",
                            duration_seconds=1.0,
                        )
                    )
                    progress = True
        if all(node.status == "succeeded" for graph in graphs.values() for node in graph.nodes.values()):
            return
        if not progress and not any(node.status == "pending" for graph in graphs.values() for node in graph.nodes.values()):
            break
    raise AssertionError("resolver did not complete all tasks within the tick budget")


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


@dataclass
class InMemoryCredential:
    credential_id: str
    credential_type: str
    token_expires_at: datetime | None
    refresh_failures_remaining: int = 0


class InMemoryAuthStore:
    def __init__(self, credential: InMemoryCredential) -> None:
        self._credential = credential

    def get(self, credential_id: str) -> InMemoryCredential | None:
        if credential_id != self._credential.credential_id:
            return None
        return self._credential

    def refresh_credential(self, credential_id: str) -> InMemoryCredential:
        credential = self.get(credential_id)
        assert credential is not None
        if credential.refresh_failures_remaining > 0:
            credential.refresh_failures_remaining -= 1
            raise RuntimeError("refresh failed")
        credential.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        return credential


def test_two_workers_two_runs_concurrent_dispatch() -> None:
    registry = InMemoryWorkerRegistry()
    registry.register(provider="claude", models=["claude-sonnet-4-6"])
    registry.register(provider="codex", models=["o3-pro"])

    run_a = build_graph([
        _make_node("a_claude", agent="claude", model="claude-sonnet-4-6"),
        _make_node("a_codex", agent="codex", model="o3-pro"),
    ])
    run_b = build_graph([
        _make_node("b_claude", agent="claude", model="claude-sonnet-4-6"),
        _make_node("b_codex", agent="codex", model="o3-pro"),
    ])

    graphs = {"run_a": run_a, "run_b": run_b}
    resolver = ResolverLoop(registry=registry, graphs=graphs)

    _run(resolver.tick())

    running = {
        (run_id, node.task_id)
        for run_id, graph in graphs.items()
        for node in graph.nodes.values()
        if node.status == "running"
    }
    assert ("run_a", "a_claude") in running or ("run_b", "b_claude") in running
    assert ("run_a", "a_codex") in running or ("run_b", "b_codex") in running

    _run(run_to_completion(resolver, graphs=graphs))


def test_auth_expiry_mid_run_defers_then_resumes() -> None:
    credential = InMemoryCredential(
        credential_id="cred_1",
        credential_type="oauth_token",
        token_expires_at=datetime.now(UTC) + timedelta(seconds=1),
        refresh_failures_remaining=1,
    )
    auth_store = InMemoryAuthStore(credential)
    registry = InMemoryWorkerRegistry()
    worker = registry.register(
        provider="claude",
        models=["claude-sonnet-4-6"],
        auth_credential_id=credential.credential_id,
    )

    graph = build_graph(
        [_make_node("a"), _make_node("b")],
        [TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.CODE_READY)],
    )
    resolver = ResolverLoop(
        registry=registry,
        graphs={"run_1": graph},
        auth_store=auth_store,
        token_refresh_threshold=timedelta(seconds=0),
    )

    _run(resolver.tick())
    credential.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    resolver.submit_completion(
        TaskResult(
            task_id="a",
            run_id="run_1",
            worker_id=worker.worker_id,
            status="succeeded",
            duration_seconds=1.0,
        )
    )
    _run(resolver.tick())
    assert graph.get_node("a").status == "succeeded"
    assert worker.status == "auth_expired"
    assert graph.get_node("b").status == "pending"

    _run(resolver.tick())

    assert worker.status == "busy"
    assert worker.current_task_id == "b"
    assert graph.get_node("b").status == "running"


def test_worker_death_triggers_retry_on_different_worker() -> None:
    registry = InMemoryWorkerRegistry()
    worker_a = registry.register(provider="claude", models=["claude-sonnet-4-6"])
    worker_b = registry.register(provider="claude", models=["claude-sonnet-4-6"])
    graph = build_graph([_make_node("auth")])

    resolver = ResolverLoop(
        registry=registry,
        graphs={"run_1": graph},
        heartbeat_timeout=timedelta(seconds=1),
    )

    _run(resolver.tick())

    dispatched_worker_id = next(
        worker.worker_id for worker in (worker_a, worker_b) if worker.current_task_id == "auth"
    )
    failed_worker = registry.get(dispatched_worker_id)
    assert failed_worker is not None
    failed_worker.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=5)

    _run(resolver.tick())

    assert failed_worker.status == "dead"
    surviving_worker_id = worker_b.worker_id if dispatched_worker_id == worker_a.worker_id else worker_a.worker_id
    assert registry.get(surviving_worker_id).current_task_id == "auth"
    assert graph.get_node("auth").status == "running"


def test_discovered_task_with_satisfied_deps_dispatches_same_tick() -> None:
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
    graph = build_graph([_make_node("a", status="succeeded")])

    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})
    resolver.submit_discovery(
        "run_1",
        source_task_id="a",
        discovered_tasks=[
            {
                "taskId": "b",
                "title": "b",
                "kind": "implementation",
                "agent": "claude",
                "model": "claude-sonnet-4-6",
                "dependencies": [{"taskId": "a", "predicate": "code_ready"}],
            }
        ],
    )

    _run(resolver.tick())

    assert worker.current_task_id == "b"
    assert graph.get_node("b").status == "running"


def test_discovered_task_creating_cycle_is_rejected() -> None:
    registry = InMemoryWorkerRegistry()
    graph = build_graph(
        [_make_node("a"), _make_node("b", status="succeeded")],
        [TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.CODE_READY)],
    )
    graph.evaluate_edges_from("b")
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    resolver.submit_discovery(
        "run_1",
        source_task_id="b",
        discovered_tasks=[
            {
                "taskId": "c",
                "title": "c",
                "kind": "implementation",
                "dependencies": [{"taskId": "b", "predicate": "code_ready"}],
                "dependents": [{"taskId": "a", "predicate": "code_ready"}],
            }
        ],
    )

    _run(resolver.tick())

    assert graph.get_node_optional("c") is None


def test_discovered_task_with_nonexistent_dep_is_rejected() -> None:
    registry = InMemoryWorkerRegistry()
    graph = build_graph([_make_node("a", status="succeeded")])
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    resolver.submit_discovery(
        "run_1",
        source_task_id="a",
        discovered_tasks=[
            {
                "taskId": "b",
                "title": "b",
                "kind": "implementation",
                "dependencies": [{"taskId": "missing", "predicate": "code_ready"}],
            }
        ],
    )

    _run(resolver.tick())

    assert graph.get_node_optional("b") is None
