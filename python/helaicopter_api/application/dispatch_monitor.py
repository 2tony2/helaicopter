"""Read-only dispatch observability helpers."""

from __future__ import annotations

from helaicopter_api.application.dispatch import InMemoryWorkerRegistry, RegisteredWorker, select_worker
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.schema.dispatch import (
    DeferredDispatchQueueEntry,
    DispatchHistoryEntry,
    DispatchQueueEntry,
    DispatchHistoryResponse,
    QueueSnapshotResponse,
)


def _resolve_task_metadata(resolver: ResolverLoop, task_id: str, *, node_provider: str | None, node_model: str | None) -> tuple[str, str]:
    provider = node_provider or resolver._task_agents.get(task_id, "claude")
    model = node_model or resolver._task_models.get(task_id, "claude-sonnet-4-6")
    return provider, model


def _deferred_reason(
    *,
    provider: str,
    model: str,
    registry: InMemoryWorkerRegistry,
) -> str:
    workers = [worker for worker in registry.all_workers() if worker.provider == provider]
    if not workers:
        return "no_registered_worker"

    capable_workers = [worker for worker in workers if not worker.models or model in worker.models]
    if not capable_workers:
        capable_workers = workers

    if all(worker.auth_status == "expired" or worker.status == "auth_expired" for worker in capable_workers):
        return "auth_expired"
    if all(worker.status == "draining" for worker in capable_workers):
        return "draining"
    if all(worker.status == "busy" for worker in capable_workers):
        return "busy"
    if all(worker.status == "dead" for worker in capable_workers):
        return "dead"
    return "no_capable_worker"


def get_queue_snapshot(resolver: ResolverLoop) -> QueueSnapshotResponse:
    """Describe ready versus deferred tasks without mutating resolver state."""
    ready: list[DispatchQueueEntry] = []
    deferred: list[DeferredDispatchQueueEntry] = []

    for run_id, graph in resolver._graphs.items():
        for task_id in graph.ready_tasks():
            node = graph.nodes[task_id]
            if node.status != "pending":
                continue

            provider, model = _resolve_task_metadata(
                resolver,
                task_id,
                node_provider=node.agent,
                node_model=node.model,
            )
            entry = DispatchQueueEntry(
                run_id=run_id,
                task_id=task_id,
                provider=provider,
                model=model,
            )
            worker = select_worker(
                provider=provider,
                model=model,
                registry=resolver._registry,
            )
            if worker is None:
                deferred.append(
                    DeferredDispatchQueueEntry(
                        **entry.model_dump(),
                        reason=_deferred_reason(
                            provider=provider,
                            model=model,
                            registry=resolver._registry,
                        ),
                    )
                )
                continue

            ready.append(entry)

    return QueueSnapshotResponse(ready=ready, deferred=deferred)


def get_dispatch_history(resolver: ResolverLoop, *, limit: int) -> DispatchHistoryResponse:
    """Return recent dispatch events in newest-first order."""
    entries = [
        DispatchHistoryEntry(
            run_id=entry.run_id,
            task_id=entry.task_id,
            worker_id=entry.worker_id,
            provider=entry.provider,
            model=entry.model,
            dispatched_at=entry.dispatched_at.isoformat(),
        )
        for entry in resolver.dispatch_history(limit=limit)
    ]
    return DispatchHistoryResponse(entries=entries)
