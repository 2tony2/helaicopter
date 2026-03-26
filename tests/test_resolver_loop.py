"""Tests for the permanent resolver loop and dispatch logic."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from oats.graph import EdgePredicate, TaskGraph, TaskKind, TaskNode, TypedEdge
from helaicopter_api.application.resolver import ResolverLoop, TaskResult
from helaicopter_api.application.dispatch import (
    InMemoryWorkerRegistry,
    select_worker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(task_id: str, *, status: str = "pending") -> TaskNode:
    return TaskNode(task_id=task_id, title=task_id, kind=TaskKind.IMPLEMENTATION, status=status)


def build_single_task_graph(task_id: str, **_kw: object) -> TaskGraph:
    """Graph with one root task, no edges."""
    graph = TaskGraph()
    graph.add_node(_make_node(task_id))
    return graph


def build_linear_graph(task_ids: list[str]) -> TaskGraph:
    """A -> B -> C  chain connected by CODE_READY edges."""
    graph = TaskGraph()
    for tid in task_ids:
        graph.add_node(_make_node(tid))
    for i in range(len(task_ids) - 1):
        graph.add_edge(TypedEdge(
            from_task=task_ids[i],
            to_task=task_ids[i + 1],
            predicate=EdgePredicate.CODE_READY,
        ))
    return graph


def _task_agent_map(*pairs: tuple[str, str]) -> dict[str, str]:
    return {tid: agent for tid, agent in pairs}


def _task_model_map(*pairs: tuple[str, str]) -> dict[str, str]:
    return {tid: model for tid, model in pairs}


def _run(coro):  # noqa: ANN001, ANN202
    """Run an async coroutine synchronously (no pytest-asyncio needed)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# InMemoryWorkerRegistry tests
# ---------------------------------------------------------------------------


class TestInMemoryWorkerRegistry:
    def test_register_creates_idle_worker(self) -> None:
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        assert worker.worker_id.startswith("wkr_")
        assert worker.status == "idle"
        assert worker.provider == "claude"

    def test_idle_workers_filters_by_provider(self) -> None:
        registry = InMemoryWorkerRegistry()
        registry.register(provider="claude", models=["claude-sonnet-4-6"])
        registry.register(provider="codex", models=["o3-pro"])
        assert len(registry.idle_workers(provider="claude")) == 1
        assert len(registry.idle_workers(provider="codex")) == 1

    def test_stale_workers_returns_overdue(self) -> None:
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        worker.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        worker.status = "busy"
        stale = registry.stale_workers(threshold=timedelta(minutes=3))
        assert worker in stale

    def test_stale_workers_ignores_recent(self) -> None:
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        worker.status = "busy"
        stale = registry.stale_workers(threshold=timedelta(minutes=3))
        assert worker not in stale


# ---------------------------------------------------------------------------
# select_worker tests
# ---------------------------------------------------------------------------


class TestSelectWorker:
    def test_selects_matching_provider(self) -> None:
        registry = InMemoryWorkerRegistry()
        w = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        selected = select_worker(provider="claude", model="claude-sonnet-4-6", registry=registry)
        assert selected is w

    def test_returns_none_when_no_match(self) -> None:
        registry = InMemoryWorkerRegistry()
        registry.register(provider="claude", models=["claude-sonnet-4-6"])
        selected = select_worker(provider="codex", model="o3-pro", registry=registry)
        assert selected is None

    def test_skips_busy_workers(self) -> None:
        registry = InMemoryWorkerRegistry()
        w = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        w.status = "busy"
        selected = select_worker(provider="claude", model="claude-sonnet-4-6", registry=registry)
        assert selected is None

    def test_skips_auth_expired_workers(self) -> None:
        registry = InMemoryWorkerRegistry()
        registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            auth_status="expired",
        )
        selected = select_worker(provider="claude", model="claude-sonnet-4-6", registry=registry)
        assert selected is None

    def test_skips_draining_workers(self) -> None:
        registry = InMemoryWorkerRegistry()
        w = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        w.status = "draining"
        selected = select_worker(provider="claude", model="claude-sonnet-4-6", registry=registry)
        assert selected is None


# ---------------------------------------------------------------------------
# ResolverLoop.tick() tests
# ---------------------------------------------------------------------------


class TestResolverTick:
    def test_dispatches_ready_task_to_idle_worker(self) -> None:
        """When a task is ready and a capable idle worker exists, dispatch occurs."""
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])

        graph = build_single_task_graph("auth")
        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": graph},
            task_agents=_task_agent_map(("auth", "claude")),
            task_models=_task_model_map(("auth", "claude-sonnet-4-6")),
        )

        _run(resolver.tick())

        assert worker.status == "busy"
        assert worker.current_task_id == "auth"

    def test_defers_task_when_no_capable_worker(self) -> None:
        """A ready task for codex is deferred when only claude workers are available."""
        registry = InMemoryWorkerRegistry()
        registry.register(provider="claude", models=["claude-sonnet-4-6"])

        graph = build_single_task_graph("ml-task")
        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": graph},
            task_agents=_task_agent_map(("ml-task", "codex")),
            task_models=_task_model_map(("ml-task", "o3-pro")),
        )

        _run(resolver.tick())

        assert graph.get_node("ml-task").status == "pending"

    def test_reaps_dead_worker_and_retries_task(self) -> None:
        """A worker that misses heartbeat threshold is reaped; its task is retried."""
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        worker.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        worker.status = "busy"
        worker.current_task_id = "auth"
        worker.current_run_id = "run_1"

        graph = build_single_task_graph("auth")
        graph.get_node("auth").status = "running"

        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": graph},
            task_agents=_task_agent_map(("auth", "claude")),
            task_models=_task_model_map(("auth", "claude-sonnet-4-6")),
            heartbeat_timeout=timedelta(minutes=3),
        )

        _run(resolver.tick())

        assert worker.status == "dead"
        assert graph.get_node("auth").status == "pending"

    def test_processes_worker_completion(self) -> None:
        """Completion event triggers edge evaluation and may enqueue dependents."""
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])

        graph = build_linear_graph(["a", "b"])
        graph.get_node("a").status = "running"

        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": graph},
            task_agents=_task_agent_map(("a", "claude"), ("b", "claude")),
            task_models=_task_model_map(("a", "claude-sonnet-4-6"), ("b", "claude-sonnet-4-6")),
        )

        result = TaskResult(
            task_id="a",
            run_id="run_1",
            worker_id=worker.worker_id,
            status="succeeded",
            duration_seconds=60.0,
        )
        resolver.submit_completion(result)

        _run(resolver.tick())

        assert graph.get_node("a").status == "succeeded"
        # b should now be ready and dispatched
        assert graph.get_node("b").status == "running"

    def test_skips_dispatch_for_expired_auth(self) -> None:
        """A worker with expired auth is skipped during dispatch."""
        registry = InMemoryWorkerRegistry()
        registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            auth_status="expired",
        )

        graph = build_single_task_graph("auth")
        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": graph},
            task_agents=_task_agent_map(("auth", "claude")),
            task_models=_task_model_map(("auth", "claude-sonnet-4-6")),
        )

        _run(resolver.tick())

        assert graph.get_node("auth").status == "pending"

    def test_failed_completion_does_not_enqueue_dependents(self) -> None:
        """A failed task should not make downstream tasks ready."""
        registry = InMemoryWorkerRegistry()
        worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])

        graph = build_linear_graph(["a", "b"])
        graph.get_node("a").status = "running"

        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": graph},
            task_agents=_task_agent_map(("a", "claude"), ("b", "claude")),
            task_models=_task_model_map(("a", "claude-sonnet-4-6"), ("b", "claude-sonnet-4-6")),
        )

        result = TaskResult(
            task_id="a",
            run_id="run_1",
            worker_id=worker.worker_id,
            status="failed",
            duration_seconds=30.0,
        )
        resolver.submit_completion(result)

        _run(resolver.tick())

        assert graph.get_node("a").status == "failed"
        assert graph.get_node("b").status != "running"

    def test_multiple_runs_dispatched_independently(self) -> None:
        """Tasks from different runs dispatch to separate workers."""
        registry = InMemoryWorkerRegistry()
        w1 = registry.register(provider="claude", models=["claude-sonnet-4-6"])
        w2 = registry.register(provider="claude", models=["claude-sonnet-4-6"])

        g1 = build_single_task_graph("t1")
        g2 = build_single_task_graph("t2")

        resolver = ResolverLoop(
            registry=registry,
            graphs={"run_1": g1, "run_2": g2},
            task_agents=_task_agent_map(("t1", "claude"), ("t2", "claude")),
            task_models=_task_model_map(("t1", "claude-sonnet-4-6"), ("t2", "claude-sonnet-4-6")),
        )

        _run(resolver.tick())

        busy = [w for w in [w1, w2] if w.status == "busy"]
        assert len(busy) == 2
