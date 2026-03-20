"""Prefect orchestration API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from helaicopter_api.application.prefect_orchestration import (
    get_prefect_flow_run,
    list_prefect_deployments,
    list_prefect_flow_runs,
    list_prefect_work_pools,
    list_prefect_workers,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.prefect_orchestration import (
    PrefectDeploymentResponse,
    PrefectFlowRunResponse,
    PrefectWorkPoolResponse,
    PrefectWorkerResponse,
)
from helaicopter_api.server.dependencies import get_services

prefect_orchestration_router = APIRouter(
    prefix="/orchestration/prefect",
    tags=["orchestration"],
)


@prefect_orchestration_router.get(
    "/deployments",
    response_model=list[PrefectDeploymentResponse],
    response_model_by_alias=True,
    summary="List primary Prefect deployments for orchestration.",
)
async def prefect_deployments_index(
    services: BackendServices = Depends(get_services),
) -> list[PrefectDeploymentResponse]:
    """List primary Prefect deployments available for orchestration.

    Returns:
        A list of Prefect deployment records from the primary orchestration path.
    """
    return list_prefect_deployments(services)


@prefect_orchestration_router.get(
    "/flow-runs",
    response_model=list[PrefectFlowRunResponse],
    response_model_by_alias=True,
    summary="List primary Prefect flow runs for orchestration.",
)
async def prefect_flow_runs_index(
    services: BackendServices = Depends(get_services),
) -> list[PrefectFlowRunResponse]:
    """List primary Prefect flow runs for orchestration.

    Returns:
        A list of Prefect flow run records from the primary orchestration path.
    """
    return list_prefect_flow_runs(services)


@prefect_orchestration_router.get(
    "/flow-runs/{flow_run_id}",
    response_model=PrefectFlowRunResponse,
    response_model_by_alias=True,
    summary="Get a primary Prefect flow run for orchestration.",
)
async def prefect_flow_run_detail(
    flow_run_id: str,
    services: BackendServices = Depends(get_services),
) -> PrefectFlowRunResponse:
    """Return a single Prefect flow run by its ID.

    Args:
        flow_run_id: The unique identifier of the Prefect flow run to retrieve.

    Returns:
        Prefect flow run record with status and metadata.
    """
    return get_prefect_flow_run(services, flow_run_id)


@prefect_orchestration_router.get(
    "/workers",
    response_model=list[PrefectWorkerResponse],
    response_model_by_alias=True,
    summary="List Prefect workers serving the primary orchestration path.",
)
async def prefect_workers_index(
    services: BackendServices = Depends(get_services),
) -> list[PrefectWorkerResponse]:
    """List Prefect workers serving the primary orchestration path.

    Returns:
        A list of Prefect worker records currently registered for orchestration.
    """
    return list_prefect_workers(services)


@prefect_orchestration_router.get(
    "/work-pools",
    response_model=list[PrefectWorkPoolResponse],
    response_model_by_alias=True,
    summary="List Prefect work pools serving the primary orchestration path.",
)
async def prefect_work_pools_index(
    services: BackendServices = Depends(get_services),
) -> list[PrefectWorkPoolResponse]:
    """List Prefect work pools serving the primary orchestration path.

    Returns:
        A list of Prefect work pool records used by the orchestration infrastructure.
    """
    return list_prefect_work_pools(services)
