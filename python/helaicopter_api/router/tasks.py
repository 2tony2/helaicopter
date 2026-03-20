"""Task list API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from helaicopter_api.application.conversations import get_tasks
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import TaskListResponse
from helaicopter_api.server.dependencies import get_services

tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


@tasks_router.get("/{session_id}", response_model=TaskListResponse)
async def tasks_detail(
    session_id: str,
    parent_session_id: str | None = Query(default=None),
    services: BackendServices = Depends(get_services),
) -> TaskListResponse:
    """Return tasks associated with a session."""
    return get_tasks(
        services,
        session_id=session_id,
        parent_session_id=parent_session_id,
    )
