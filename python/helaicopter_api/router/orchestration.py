"""OATS local-runtime orchestration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from helaicopter_api.application.oats_run_actions import refresh_oats_run, resume_oats_run
from helaicopter_api.application.orchestration import (
    cancel_oats_task,
    force_retry_oats_task,
    get_oats_facts,
    get_oats_run,
    insert_oats_task,
    list_oats_runs,
    pause_oats_run,
    reroute_oats_task,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.orchestration import (
    OrchestrationFactsResponse,
    OrchestrationInsertTaskRequest,
    OrchestrationRerouteTaskRequest,
    OrchestrationRunActionResponse,
    OrchestrationRunResponse,
)
from helaicopter_api.server.dependencies import get_services

orchestration_router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@orchestration_router.get(
    "/oats",
    response_model=list[OrchestrationRunResponse],
    response_model_by_alias=True,
    summary="List OATS local-runtime records.",
)
async def orchestration_oats_index(
    services: BackendServices = Depends(get_services),
) -> list[OrchestrationRunResponse]:
    """List all OATS run records found in the local runtime directory.

    Returns:
        A list of OATS run records parsed from repo-local runtime and record
        files, each describing the run ID, status, and associated task attempts.
    """
    return list_oats_runs(services)


@orchestration_router.get(
    "/oats/facts",
    response_model=OrchestrationFactsResponse,
    response_model_by_alias=True,
    summary="List canonical OATS orchestration analytics facts.",
)
async def orchestration_oats_facts(
    services: BackendServices = Depends(get_services),
) -> OrchestrationFactsResponse:
    """Return canonical analytics facts derived from repo-local OATS artifacts.

    Returns:
        Aggregated orchestration facts including run counts, task-attempt
        outcomes, and timing metrics computed from all local OATS records.
    """
    return get_oats_facts(services)


@orchestration_router.get(
    "/oats/{run_id}",
    response_model=OrchestrationRunResponse,
    response_model_by_alias=True,
    summary="Get a single OATS runtime record.",
)
async def orchestration_oats_detail(
    run_id: str,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunResponse:
    try:
        return get_oats_run(services, run_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/refresh",
    response_model=OrchestrationRunResponse,
    response_model_by_alias=True,
    summary="Refresh stacked PR state for a persisted OATS run.",
)
async def orchestration_oats_refresh(
    run_id: str,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunResponse:
    """Refresh the stacked PR state for a persisted OATS run.

    Args:
        run_id: Unique identifier of the OATS run to refresh.

    Returns:
        The updated OATS run record reflecting the latest stacked PR state.
    """
    try:
        return refresh_oats_run(services, run_id)
    except RuntimeError as error:
        # Missing or invalid backend settings, or runtime errors from adapters
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/resume",
    response_model=OrchestrationRunResponse,
    response_model_by_alias=True,
    summary="Resume stacked PR state for a persisted OATS run.",
)
async def orchestration_oats_resume(
    run_id: str,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunResponse:
    """Resume a stalled or paused OATS run, re-triggering stacked PR progression.

    Args:
        run_id: Unique identifier of the OATS run to resume.

    Returns:
        The updated OATS run record after the resume action has been dispatched.
    """
    try:
        return resume_oats_run(services, run_id)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/pause",
    response_model=OrchestrationRunActionResponse,
    response_model_by_alias=True,
    summary="Pause a graph-native OATS run.",
)
async def orchestration_oats_pause(
    run_id: str,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunActionResponse:
    try:
        return pause_oats_run(services, run_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/tasks/{task_id}/cancel",
    response_model=OrchestrationRunActionResponse,
    response_model_by_alias=True,
    summary="Cancel a graph task and block descendants.",
)
async def orchestration_oats_cancel_task(
    run_id: str,
    task_id: str,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunActionResponse:
    try:
        return cancel_oats_task(services, run_id, task_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/tasks/{task_id}/force-retry",
    response_model=OrchestrationRunActionResponse,
    response_model_by_alias=True,
    summary="Reset a failed graph task back to pending.",
)
async def orchestration_oats_force_retry_task(
    run_id: str,
    task_id: str,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunActionResponse:
    try:
        return force_retry_oats_task(services, run_id, task_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/tasks/{task_id}/reroute",
    response_model=OrchestrationRunActionResponse,
    response_model_by_alias=True,
    summary="Change the provider/model assigned to a graph task.",
)
async def orchestration_oats_reroute_task(
    run_id: str,
    task_id: str,
    request: OrchestrationRerouteTaskRequest,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunActionResponse:
    try:
        return reroute_oats_task(services, run_id, task_id, request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@orchestration_router.post(
    "/oats/{run_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=OrchestrationRunActionResponse,
    response_model_by_alias=True,
    summary="Insert an operator-authored task into a graph-native OATS run.",
)
async def orchestration_oats_insert_task(
    run_id: str,
    request: OrchestrationInsertTaskRequest,
    services: BackendServices = Depends(get_services),
) -> OrchestrationRunActionResponse:
    try:
        return insert_oats_task(services, run_id, request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
