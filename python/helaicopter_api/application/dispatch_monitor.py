"""Read-only dispatch observability helpers."""

from __future__ import annotations

from helaicopter_api.application.provider_readiness import build_provider_readiness_from_store
from helaicopter_api.application.dispatch import (
    InMemoryWorkerRegistry,
    dispatch_reason_label,
    select_worker,
)
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
    resolver: ResolverLoop,
    run_id: str,
    task_id: str,
    provider: str,
    model: str,
    registry: InMemoryWorkerRegistry,
) -> str:
    if resolver.interrupted_task_record(run_id=run_id, task_id=task_id) is not None:
        return "worker_interrupted"
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
    readiness_by_provider: dict[str, object | None] = {}

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
            if provider not in readiness_by_provider:
                readiness_by_provider[provider] = build_provider_readiness_from_store(
                    provider=provider,
                    engine=resolver._sqlite_engine,
                    workers=resolver._registry.all_workers(),
                )
            readiness = readiness_by_provider[provider]
            if (
                readiness is not None
                and readiness.status == "blocked"
                and resolver.interrupted_task_record(run_id=run_id, task_id=task_id) is None
            ):
                deferred.append(
                    DeferredDispatchQueueEntry(
                        **entry.model_dump(),
                        reason="provider_not_ready",
                        reason_label=dispatch_reason_label("provider_not_ready"),
                        can_retry=False,
                    )
                )
                continue
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
                            resolver=resolver,
                            run_id=run_id,
                            task_id=task_id,
                            provider=provider,
                            model=model,
                            registry=resolver._registry,
                        ),
                        reason_label=dispatch_reason_label(
                            _deferred_reason(
                                resolver=resolver,
                                run_id=run_id,
                                task_id=task_id,
                                provider=provider,
                                model=model,
                                registry=resolver._registry,
                            )
                        ),
                        can_retry=_deferred_reason(
                            resolver=resolver,
                            run_id=run_id,
                            task_id=task_id,
                            provider=provider,
                            model=model,
                            registry=resolver._registry,
                        )
                        == "worker_interrupted",
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
