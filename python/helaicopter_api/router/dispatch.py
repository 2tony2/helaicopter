"""Dispatch queue monitoring and history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from helaicopter_api.application.dispatch_monitor import (
    get_dispatch_history,
    get_queue_snapshot,
)
from helaicopter_api.schema.dispatch import DispatchHistoryResponse, QueueSnapshotResponse

dispatch_router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@dispatch_router.get(
    "/queue",
    response_model=QueueSnapshotResponse,
    response_model_by_alias=True,
    summary="Inspect current ready and deferred dispatch state.",
)
async def dispatch_queue(request: Request) -> QueueSnapshotResponse:
    """Return a snapshot of dispatchable and deferred tasks."""
    return get_queue_snapshot(request.app.state.resolver)


@dispatch_router.get(
    "/history",
    response_model=DispatchHistoryResponse,
    response_model_by_alias=True,
    summary="List recent dispatch events.",
)
async def dispatch_history(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
) -> DispatchHistoryResponse:
    """Return recent dispatch history in newest-first order."""
    return get_dispatch_history(request.app.state.resolver, limit=limit)
