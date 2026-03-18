"""Orchestration API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from helaicopter_api.application.orchestration import list_oats_runs
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.orchestration import OrchestrationRunResponse
from helaicopter_api.server.dependencies import get_services

orchestration_router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@orchestration_router.get("/oats", response_model=list[OrchestrationRunResponse], response_model_by_alias=True)
async def orchestration_oats_index(
    services: BackendServices = Depends(get_services),
) -> list[OrchestrationRunResponse]:
    """List backend-shaped OATS run summaries for the orchestration dashboard."""
    return list_oats_runs(services)
