"""Conversation summary and detail API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from helaicopter_api.application.conversations import (
    get_conversation,
    get_conversation_dag,
    list_conversations,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import (
    ConversationDagResponse,
    ConversationDetailResponse,
    ConversationListQueryParams,
    ConversationSummaryResponse,
)
from helaicopter_api.server.dependencies import get_services

conversations_router = APIRouter(prefix="/conversations", tags=["conversations"])


@conversations_router.get("", response_model=list[ConversationSummaryResponse])
async def conversations_index(
    params: Annotated[
        ConversationListQueryParams,
        Query(description="Conversation list filters for project and trailing-day windows."),
    ],
    services: BackendServices = Depends(get_services),
) -> list[ConversationSummaryResponse]:
    """List merged Claude and Codex conversation summaries."""
    return list_conversations(services, project=params.project, days=params.days)


@conversations_router.get("/{project_path}/{session_id}", response_model=ConversationDetailResponse)
async def conversations_detail(
    project_path: str,
    session_id: str,
    services: BackendServices = Depends(get_services),
) -> ConversationDetailResponse:
    """Return one conversation detail from persisted or live data."""
    conversation = get_conversation(
        services,
        project_path=project_path,
        session_id=session_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@conversations_router.get("/{project_path}/{session_id}/dag", response_model=ConversationDagResponse)
async def conversations_dag_detail(
    project_path: str,
    session_id: str,
    services: BackendServices = Depends(get_services),
) -> ConversationDagResponse:
    """Return one backend-built conversation DAG."""
    dag = get_conversation_dag(
        services,
        project_path=project_path,
        session_id=session_id,
    )
    if dag is None:
        raise HTTPException(status_code=404, detail="Conversation DAG not found")
    return dag
