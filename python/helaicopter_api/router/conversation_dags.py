"""Conversation DAG summary API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from helaicopter_api.application.conversations import list_conversation_dags
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import (
    ConversationDagListQueryParams,
    ConversationDagSummaryResponse,
)
from helaicopter_api.server.dependencies import get_services

conversation_dags_router = APIRouter(prefix="/conversation-dags", tags=["conversation-dags"])


@conversation_dags_router.get("", response_model=list[ConversationDagSummaryResponse])
async def conversation_dags_index(
    params: Annotated[
        ConversationDagListQueryParams,
        Query(description="Conversation DAG list filters for project, provider, and trailing-day windows."),
    ],
    services: BackendServices = Depends(get_services),
) -> list[ConversationDagSummaryResponse]:
    """List main conversations with backend-built DAG stats."""
    return list_conversation_dags(
        services,
        project=params.project,
        days=params.days,
        provider=params.provider,
    )
