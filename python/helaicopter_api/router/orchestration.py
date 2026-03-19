"""OATS local-runtime orchestration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from helaicopter_api.application.orchestration import list_oats_runs
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.orchestration import OrchestrationRunResponse
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
    """View over repo-local OATS runtime and record files."""
    return list_oats_runs(services)
