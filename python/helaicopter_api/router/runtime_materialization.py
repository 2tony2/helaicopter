"""Dedicated runtime materialization endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from helaicopter_api.application.runtime_materialization import get_materialized_runtime_run
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.runtime_materialization import MaterializedRuntimeRun
from helaicopter_api.server.dependencies import get_services

runtime_materialization_router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@runtime_materialization_router.get(
    "/runtime/{run_id}",
    response_model=MaterializedRuntimeRun,
    response_model_by_alias=True,
    summary="Get one materialized live runtime payload.",
)
async def orchestration_runtime_detail(
    run_id: str,
    services: BackendServices = Depends(get_services),
) -> MaterializedRuntimeRun:
    try:
        return get_materialized_runtime_run(services, run_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
