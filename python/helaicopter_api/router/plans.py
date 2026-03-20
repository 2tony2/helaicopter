"""Plans API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from helaicopter_api.application.plans import get_plan, list_plans
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.contracts.plans import (
    PlanDetailResponse,
    PlanSummaryResponse,
)
from helaicopter_api.server.dependencies import get_services

plans_router = APIRouter(prefix="/plans", tags=["plans"])


@plans_router.get("", response_model=list[PlanSummaryResponse])
async def plans_index(
    services: BackendServices = Depends(get_services),
) -> list[PlanSummaryResponse]:
    """List saved plans from Claude and Codex sources."""
    return list_plans(services)


@plans_router.get("/{slug}", response_model=PlanDetailResponse)
async def plans_detail(
    slug: str,
    services: BackendServices = Depends(get_services),
) -> PlanDetailResponse:
    """Return one plan by encoded id or legacy Claude slug."""
    plan = get_plan(services, slug)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
