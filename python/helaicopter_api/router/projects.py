"""Project listing API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from helaicopter_api.application.conversations import list_projects
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import ProjectResponse
from helaicopter_api.server.dependencies import get_services

projects_router = APIRouter(prefix="/projects", tags=["projects"])


@projects_router.get("", response_model=list[ProjectResponse])
async def projects_index(
    services: BackendServices = Depends(get_services),
) -> list[ProjectResponse]:
    """List projects aggregated from conversation summaries."""
    return list_projects(services)
