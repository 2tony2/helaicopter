"""History API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from helaicopter_api.application.conversations import list_history
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import HistoryEntryResponse, HistoryQueryParams
from helaicopter_api.server.dependencies import get_services

history_router = APIRouter(prefix="/history", tags=["history"])


@history_router.get("", response_model=list[HistoryEntryResponse])
async def history_index(
    params: Annotated[
        HistoryQueryParams,
        Query(description="Merged Claude and Codex command history filters."),
    ],
    services: BackendServices = Depends(get_services),
) -> list[HistoryEntryResponse]:
    """Return combined CLI history from Claude and Codex sources."""
    return list_history(services, limit=params.limit)
