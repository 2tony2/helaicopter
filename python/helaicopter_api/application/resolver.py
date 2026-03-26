"""Permanent resolver loop for the OATS graph runtime.

The resolver loop is a continuously-running asyncio task that:
  1. Ingests completion events from workers
  2. Processes completions — records results, evaluates outbound edges
  3. Reaps dead workers (heartbeat timeout)
  4. Dispatches ready tasks to available workers

Single-process assumption: exactly one resolver loop per backend process.
State authority: task graph in ``.oats/runtime/`` (file-based), worker
registry and auth credentials in SQLite.  The resolver holds in-memory
indices rebuilt from authoritative stores on startup.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.engine import Engine

from oats.discovery import Discovery, DuplicateTaskIdError, insert_discovered_tasks
from oats.graph import TaskGraph
from oats.graph import EdgePredicate, GraphCycleError, TaskKind, TaskNode, TypedEdge
from oats.scheduler import ReadyQueueScheduler

from .dispatch import InMemoryWorkerRegistry, RegisteredWorker, select_worker
from .worker_state import (
    complete_worker_task,
    mark_worker_auth_expired,
    mark_worker_dead,
    mark_worker_dispatched,
    restore_worker_auth,
)

logger = logging.getLogger(__name__)


class AuthCredentialSnapshot(Protocol):
    credential_type: str
    token_expires_at: datetime | None


class AuthStore(Protocol):
    def get(self, credential_id: str) -> AuthCredentialSnapshot | None: ...

    def refresh_credential(self, credential_id: str) -> AuthCredentialSnapshot: ...


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class TaskResult(BaseModel):
    """Structured result from a worker completion."""

    task_id: str
    run_id: str
    worker_id: str
    status: str  # succeeded | failed | timed_out | needs_retry
    duration_seconds: float
    attempt_id: str | None = None
    branch_name: str | None = None
    commit_sha: str | None = None
    error_summary: str | None = None


class DispatchEvent(BaseModel):
    """Observability event emitted whenever a task is dispatched."""

    run_id: str
    task_id: str
    worker_id: str
    provider: str
    model: str
    dispatched_at: datetime


class DiscoverySubmission(BaseModel):
    """Queued discovered-task insertion submitted by a running task."""

    run_id: str
    source_task_id: str
    discovered_tasks: list[dict[str, object]]


# ---------------------------------------------------------------------------
# ResolverLoop
# ---------------------------------------------------------------------------


class ResolverLoop:
    """Core resolver loop that evaluates graphs and dispatches to workers.

    The loop does not run continuously by itself — call :meth:`tick` once
    per cycle.  In production, :meth:`run` drives an infinite ``tick`` loop
    with a configurable poll interval.  In tests, call ``tick()`` directly.
    """

    def __init__(
        self,
        *,
        registry: InMemoryWorkerRegistry,
        graphs: dict[str, TaskGraph] | None = None,
        task_agents: dict[str, str] | None = None,
        task_models: dict[str, str] | None = None,
        auth_store: AuthStore | None = None,
        sqlite_engine: Engine | None = None,
        runtime_dir: Path | None = None,
        token_refresh_threshold: timedelta = timedelta(minutes=5),
        heartbeat_timeout: timedelta = timedelta(minutes=3),
        poll_interval_seconds: float = 5.0,
        dispatch_history_limit: int = 1000,
    ) -> None:
        self._registry = registry
        self._graphs: dict[str, TaskGraph] = graphs or {}
        self._task_agents: dict[str, str] = task_agents or {}
        self._task_models: dict[str, str] = task_models or {}
        self._auth_store = auth_store
        self._sqlite_engine = sqlite_engine
        self._runtime_dir = runtime_dir
        self._token_refresh_threshold = token_refresh_threshold
        self._heartbeat_timeout = heartbeat_timeout
        self._poll_interval = poll_interval_seconds
        self._completion_queue: deque[TaskResult] = deque()
        self._discovery_queue: deque[DiscoverySubmission] = deque()
        self._dispatch_history: deque[DispatchEvent] = deque(maxlen=dispatch_history_limit)
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_completion(self, result: TaskResult) -> None:
        """Enqueue a completion event for processing on the next tick."""
        self._completion_queue.append(result)

    def submit_graph(self, run_id: str, graph: TaskGraph) -> None:
        """Add a new run graph to the resolver."""
        self._graphs[run_id] = graph

    def submit_discovery(
        self,
        run_id: str,
        *,
        source_task_id: str,
        discovered_tasks: list[dict[str, object]],
    ) -> None:
        """Queue discovered tasks for insertion on the next tick."""
        self._discovery_queue.append(
            DiscoverySubmission(
                run_id=run_id,
                source_task_id=source_task_id,
                discovered_tasks=discovered_tasks,
            )
        )

    def dispatch_history(self, *, limit: int = 50) -> list[DispatchEvent]:
        """Return recent dispatch events in newest-first order."""
        events = list(self._dispatch_history)
        if limit < len(events):
            events = events[-limit:]
        events.reverse()
        return events

    def record_dispatch_event(
        self,
        *,
        run_id: str,
        task_id: str,
        worker_id: str,
        provider: str,
        model: str,
    ) -> None:
        """Record a dispatch event in-memory and on disk when configured."""
        event = DispatchEvent(
            run_id=run_id,
            task_id=task_id,
            worker_id=worker_id,
            provider=provider,
            model=model,
            dispatched_at=datetime.now(UTC),
        )
        self._dispatch_history.append(event)
        if self._runtime_dir is None:
            return

        history_path = self._runtime_dir / "dispatch_history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json")) + "\n")

    async def tick(self) -> None:
        """Execute one resolver cycle.

        Order of operations:
          1. Process completion events (record results, evaluate edges)
          2. Refresh OAuth credentials that are near expiry
          3. Reap dead workers (heartbeat timeout) and re-queue their tasks
          4. Dispatch ready tasks to available workers
        """
        self._process_completions()
        self._process_discoveries()
        self._refresh_expiring_credentials()
        self._reap_dead_workers()
        self._dispatch_ready_tasks()

    async def run(self) -> None:
        """Run the resolver loop indefinitely (production entry point)."""
        self._running = True
        logger.info("Resolver loop started (poll_interval=%.1fs)", self._poll_interval)
        try:
            while self._running:
                await self.tick()
                await asyncio.sleep(self._poll_interval)
        finally:
            logger.info("Resolver loop stopped")

    def stop(self) -> None:
        """Signal the loop to stop after the current tick."""
        self._running = False

    # ------------------------------------------------------------------
    # Completion processing
    # ------------------------------------------------------------------

    def _process_completions(self) -> None:
        """Drain the completion queue and update graph + registry state."""
        while self._completion_queue:
            result = self._completion_queue.popleft()
            run_id = result.run_id
            graph = self._graphs.get(run_id)
            if graph is None:
                logger.warning("Completion for unknown run %s (task %s)", run_id, result.task_id)
                continue

            node = graph.nodes.get(result.task_id)
            if node is None:
                logger.warning("Completion for unknown task %s in run %s", result.task_id, run_id)
                continue

            # Release worker
            worker = self._registry.get(result.worker_id)
            if worker is not None:
                complete_worker_task(
                    engine=self._sqlite_engine,
                    registry=self._registry,
                    worker_id=result.worker_id,
                )

            if result.status == "succeeded":
                graph.record_task_success(result.task_id)
                graph.evaluate_edges_from(result.task_id)
                logger.info("Task %s succeeded in run %s", result.task_id, run_id)
            else:
                node.status = "failed"
                logger.info(
                    "Task %s %s in run %s: %s",
                    result.task_id,
                    result.status,
                    run_id,
                    result.error_summary or "(no detail)",
                )

    # ------------------------------------------------------------------
    # Discovery processing
    # ------------------------------------------------------------------

    def _process_discoveries(self) -> None:
        while self._discovery_queue:
            submission = self._discovery_queue.popleft()
            graph = self._graphs.get(submission.run_id)
            if graph is None:
                logger.warning("Discovery submitted for unknown run %s", submission.run_id)
                continue

            discovery = self._build_discovery(submission)
            if discovery is None:
                continue

            scheduler = ReadyQueueScheduler(
                graph,
                concurrency_limit=max(len(graph.nodes) + len(discovery.tasks), 1),
            )
            try:
                insert_discovered_tasks(graph, scheduler, discovery)
            except (DuplicateTaskIdError, GraphCycleError, ValueError) as exc:
                logger.warning(
                    "Rejected discovery from %s in run %s: %s",
                    submission.source_task_id,
                    submission.run_id,
                    exc,
                )

    def _build_discovery(self, submission: DiscoverySubmission) -> Discovery | None:
        tasks: list[TaskNode] = []
        edges: list[TypedEdge] = []

        for task_spec in submission.discovered_tasks:
            task_id = str(task_spec["taskId"])
            title = str(task_spec.get("title", task_id))
            kind = TaskKind(str(task_spec.get("kind", TaskKind.IMPLEMENTATION.value)))
            agent = task_spec.get("agent")
            model = task_spec.get("model")
            task = TaskNode(
                task_id=task_id,
                title=title,
                kind=kind,
                agent=str(agent) if agent is not None else None,
                model=str(model) if model is not None else None,
                discovered_by=submission.source_task_id,
            )
            tasks.append(task)

            for dep in task_spec.get("dependencies", []):
                dependency = dict(dep)
                edges.append(
                    TypedEdge(
                        from_task=str(dependency["taskId"]),
                        to_task=task_id,
                        predicate=EdgePredicate(str(dependency.get("predicate", "code_ready"))),
                    )
                )

            for dependent in task_spec.get("dependents", []):
                downstream = dict(dependent)
                edges.append(
                    TypedEdge(
                        from_task=task_id,
                        to_task=str(downstream["taskId"]),
                        predicate=EdgePredicate(str(downstream.get("predicate", "code_ready"))),
                    )
                )

        return Discovery(
            discovered_by=submission.source_task_id,
            tasks=tasks,
            edges_to_add=edges,
        )

    # ------------------------------------------------------------------
    # Credential lifecycle
    # ------------------------------------------------------------------

    def _refresh_expiring_credentials(self) -> None:
        if self._auth_store is None:
            return

        now = datetime.now(UTC)
        refresh_before = now + self._token_refresh_threshold
        for worker in self._registry.all_workers():
            credential_id = worker.auth_credential_id
            if credential_id is None:
                continue

            credential = self._auth_store.get(credential_id)
            if credential is None:
                continue
            if credential.credential_type != "oauth_token":
                continue
            if credential.token_expires_at is None or credential.token_expires_at > refresh_before:
                continue

            try:
                self._auth_store.refresh_credential(credential_id)
            except Exception:
                mark_worker_auth_expired(
                    engine=self._sqlite_engine,
                    registry=self._registry,
                    worker_id=worker.worker_id,
                )
                logger.warning("Failed to refresh auth credential %s for worker %s", credential_id, worker.worker_id)
                continue

            restore_worker_auth(
                engine=self._sqlite_engine,
                registry=self._registry,
                worker_id=worker.worker_id,
            )

    # ------------------------------------------------------------------
    # Dead-worker reaping
    # ------------------------------------------------------------------

    def _reap_dead_workers(self) -> None:
        """Mark stale workers as dead and re-queue their in-flight tasks."""
        stale = self._registry.stale_workers(threshold=self._heartbeat_timeout)
        for worker in stale:
            task_id = worker.current_task_id
            run_id = worker.current_run_id
            logger.warning(
                "Reaping dead worker %s (last heartbeat: %s)",
                worker.worker_id,
                worker.last_heartbeat_at,
            )
            mark_worker_dead(
                engine=self._sqlite_engine,
                registry=self._registry,
                worker_id=worker.worker_id,
            )

            # Re-queue the task if it was running
            if task_id and run_id:
                graph = self._graphs.get(run_id)
                if graph and task_id in graph.nodes:
                    node = graph.nodes[task_id]
                    if node.status == "running":
                        node.status = "pending"
                        logger.info("Re-queued task %s from dead worker %s", task_id, worker.worker_id)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch_ready_tasks(self) -> None:
        """Find ready tasks across all active graphs and dispatch to workers."""
        for run_id, graph in self._graphs.items():
            ready_ids = graph.ready_tasks()
            for task_id in ready_ids:
                node = graph.nodes[task_id]
                if node.status != "pending":
                    continue

                provider = node.agent or self._task_agents.get(task_id, "claude")
                model = node.model or self._task_models.get(task_id, "claude-sonnet-4-6")

                worker = select_worker(
                    provider=provider,
                    model=model,
                    registry=self._registry,
                )
                if worker is None:
                    # No capable worker — task stays pending (deferred)
                    continue

                # Dispatch: update worker and task state
                node.status = "running"
                mark_worker_dispatched(
                    engine=self._sqlite_engine,
                    registry=self._registry,
                    worker_id=worker.worker_id,
                    run_id=run_id,
                    task_id=task_id,
                )
                self.record_dispatch_event(
                    run_id=run_id,
                    task_id=task_id,
                    worker_id=worker.worker_id,
                    provider=provider,
                    model=model,
                )
                logger.info(
                    "Dispatched task %s (run %s) to worker %s",
                    task_id,
                    run_id,
                    worker.worker_id,
                )
