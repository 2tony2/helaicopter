"""Worker registry REST endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from helaicopter_api.application.workers import (
    deregister_worker,
    drain_worker,
    get_worker,
    heartbeat_worker,
    list_workers,
    pull_next_task,
    report_task_result,
    register_worker,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.workers import (
    WorkerDetailResponse,
    WorkerHeartbeatRequest,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerTaskReportRequest,
)
from helaicopter_api.server.dependencies import get_services
from oats.envelope import ExecutionEnvelope

workers_router = APIRouter(prefix="/workers", tags=["workers"])


@workers_router.post(
    "/register",
    response_model=WorkerRegistrationResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new worker.",
)
async def worker_register(
    body: WorkerRegistrationRequest,
    services: BackendServices = Depends(get_services),
) -> WorkerRegistrationResponse:
    """Register a worker with the control plane."""
    return register_worker(services.sqlite_engine, body)


@workers_router.get(
    "",
    response_model=list[WorkerDetailResponse],
    response_model_by_alias=True,
    summary="List registered workers.",
)
async def worker_list(
    provider: str | None = Query(None, description="Filter by provider name."),
    services: BackendServices = Depends(get_services),
) -> list[WorkerDetailResponse]:
    """List all registered workers, optionally filtered by provider."""
    return list_workers(services.sqlite_engine, provider=provider)


@workers_router.get(
    "/{worker_id}",
    response_model=WorkerDetailResponse,
    response_model_by_alias=True,
    summary="Get worker detail.",
)
async def worker_detail(
    worker_id: str,
    services: BackendServices = Depends(get_services),
) -> WorkerDetailResponse:
    """Return detail for a single worker."""
    result = get_worker(services.sqlite_engine, worker_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return result


@workers_router.post(
    "/{worker_id}/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Send worker heartbeat.",
)
async def worker_heartbeat(
    worker_id: str,
    body: WorkerHeartbeatRequest,
    request: Request,
    services: BackendServices = Depends(get_services),
) -> dict[str, str]:
    """Update heartbeat timestamp and optional status for a worker."""
    if not heartbeat_worker(
        services.sqlite_engine,
        worker_id,
        body,
        registry=request.app.state.worker_registry,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return {"ok": "true"}


@workers_router.post(
    "/{worker_id}/drain",
    status_code=status.HTTP_200_OK,
    summary="Drain a worker.",
)
async def worker_drain(
    worker_id: str,
    request: Request,
    services: BackendServices = Depends(get_services),
) -> dict[str, str]:
    """Set worker to draining state — finishes current task, then stops accepting new ones."""
    if not drain_worker(
        services.sqlite_engine,
        worker_id,
        registry=request.app.state.worker_registry,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return {"ok": "true"}


@workers_router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deregister a worker.",
)
async def worker_deregister(
    worker_id: str,
    services: BackendServices = Depends(get_services),
) -> Response:
    """Remove a worker from the registry."""
    if not deregister_worker(services.sqlite_engine, worker_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@workers_router.get(
    "/{worker_id}/next-task",
    response_model=ExecutionEnvelope,
    response_model_by_alias=True,
    summary="Claim the next ready task for a worker.",
)
async def worker_next_task(
    worker_id: str,
    request: Request,
    services: BackendServices = Depends(get_services),
) -> ExecutionEnvelope | Response:
    """Return the next dispatchable task envelope for this worker, if any."""
    resolver = request.app.state.resolver
    runtime_dir = Path(request.app.state.settings.runtime_dir)
    try:
        envelope = pull_next_task(
            services.sqlite_engine,
            worker_id=worker_id,
            resolver=resolver,
            runtime_dir=runtime_dir,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found") from exc

    if envelope is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return envelope


@workers_router.post(
    "/{worker_id}/report",
    status_code=status.HTTP_200_OK,
    summary="Report task completion from a worker.",
)
async def worker_report(
    worker_id: str,
    body: WorkerTaskReportRequest,
    request: Request,
    services: BackendServices = Depends(get_services),
) -> dict[str, str]:
    """Persist a worker result and enqueue completion processing."""
    resolver = request.app.state.resolver
    runtime_dir = Path(request.app.state.settings.runtime_dir)
    if not report_task_result(
        services.sqlite_engine,
        worker_id=worker_id,
        request=body,
        resolver=resolver,
        runtime_dir=runtime_dir,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return {"ok": "true"}
