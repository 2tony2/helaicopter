"""Conversation summary and detail API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from helaicopter_api.application.conversations import (
    get_conversation,
    get_conversation_dag,
    get_subagent_conversation,
    list_conversations,
    resolve_conversation_ref,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import (
    ConversationDagResponse,
    ConversationDetailResponse,
    ConversationListQueryParams,
    ConversationRefResolutionResponse,
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


@conversations_router.get("/by-ref/{conversation_ref}", response_model=ConversationRefResolutionResponse)
async def conversation_by_ref(
    conversation_ref: str,
    services: BackendServices = Depends(get_services),
) -> ConversationRefResolutionResponse:
    """Resolve a stable conversation ref to the current canonical route target."""
    conversation = resolve_conversation_ref(
        services,
        conversation_ref=conversation_ref,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


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


@conversations_router.get(
    "/{project_path}/{session_id}/subagents/{agent_id}",
    response_model=ConversationDetailResponse,
)
async def conversations_subagent_detail(
    project_path: str,
    session_id: str,
    agent_id: str,
    services: BackendServices = Depends(get_services),
) -> ConversationDetailResponse:
    """Return one subagent transcript beneath its parent conversation route."""
    conversation = get_subagent_conversation(
        services,
        project_path=project_path,
        parent_session_id=session_id,
        agent_id=agent_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Subagent conversation not found")
    return conversation
