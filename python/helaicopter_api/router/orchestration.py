"""OATS local-runtime orchestration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from helaicopter_api.application.oats_run_actions import refresh_oats_run, resume_oats_run
from helaicopter_api.application.orchestration import get_oats_facts, list_oats_runs
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.orchestration import OrchestrationFactsResponse, OrchestrationRunResponse
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
    return refresh_oats_run(services, run_id)


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
    return resume_oats_run(services, run_id)
