"""Schemas for dispatch queue monitoring and history endpoints."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class DispatchQueueEntry(CamelCaseHttpResponseModel):
    """A task currently ready for dispatch."""

    run_id: str
    task_id: str
    provider: str
    model: str


class DeferredDispatchQueueEntry(DispatchQueueEntry):
    """A task deferred from dispatch and the reason why."""

    reason: str


class QueueSnapshotResponse(CamelCaseHttpResponseModel):
    """Current ready and deferred dispatch state."""

    ready: list[DispatchQueueEntry]
    deferred: list[DeferredDispatchQueueEntry]


class DispatchHistoryEntry(CamelCaseHttpResponseModel):
    """One recent dispatch event."""

    run_id: str
    task_id: str
    worker_id: str
    provider: str
    model: str
    dispatched_at: str


class DispatchHistoryResponse(CamelCaseHttpResponseModel):
    """Recent dispatch history."""

    entries: list[DispatchHistoryEntry]
