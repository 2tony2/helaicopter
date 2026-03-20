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
    """List merged Claude and Codex conversation summaries.

    Args:
        params: Query parameters for filtering results. Supports ``project``
            (encoded project path) to scope results to a single project, and
            ``days`` to restrict to the trailing number of days.

    Returns:
        List of conversation summary objects ordered by recency, combining
        Claude and Codex sessions with token usage and metadata.
    """
    return list_conversations(services, project=params.project, days=params.days)


@conversations_router.get("/by-ref/{conversation_ref}", response_model=ConversationRefResolutionResponse)
async def conversation_by_ref(
    conversation_ref: str,
    services: BackendServices = Depends(get_services),
) -> ConversationRefResolutionResponse:
    """Resolve a stable conversation ref to the current canonical route target.

    Args:
        conversation_ref: Stable identifier for the conversation, independent
            of project path or session routing changes.

    Returns:
        Resolution payload containing the canonical ``route_slug``,
        ``project_path``, ``session_id``, and ``thread_type`` for the
        conversation.

    Raises:
        HTTPException: 404 if no conversation matches the given ref.
    """
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
    parent_session_id: str | None = Query(default=None),
    services: BackendServices = Depends(get_services),
) -> ConversationDetailResponse:
    """Return one conversation detail from persisted or live data.

    Args:
        project_path: Encoded project key identifying the project the
            conversation belongs to.
        session_id: Unique session identifier for the conversation.
        parent_session_id: Optional session ID of the parent conversation when
            accessing a subagent thread directly.

    Returns:
        Full conversation detail including all messages, tool calls, plans,
        subagent references, token usage, and context analytics.

    Raises:
        HTTPException: 404 if the conversation cannot be found.
    """
    conversation = get_conversation(
        services,
        project_path=project_path,
        session_id=session_id,
        parent_session_id=parent_session_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@conversations_router.get("/{project_path}/{session_id}/dag", response_model=ConversationDagResponse)
async def conversations_dag_detail(
    project_path: str,
    session_id: str,
    parent_session_id: str | None = Query(default=None),
    services: BackendServices = Depends(get_services),
) -> ConversationDagResponse:
    """Return one backend-built conversation DAG.

    Args:
        project_path: Encoded project key for the conversation.
        session_id: Session identifier of the root conversation whose agent
            tree should be returned.
        parent_session_id: Optional parent session ID when the root is itself
            a subagent thread.

    Returns:
        DAG payload containing nodes (one per agent/subagent transcript),
        directed edges, and aggregate graph statistics such as depth and
        total token counts.

    Raises:
        HTTPException: 404 if no DAG is found for the given session.
    """
    dag = get_conversation_dag(
        services,
        project_path=project_path,
        session_id=session_id,
        parent_session_id=parent_session_id,
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
    """Return one subagent transcript beneath its parent conversation route.

    Args:
        project_path: Encoded project key for the parent conversation.
        session_id: Session ID of the parent (root) conversation that spawned
            the subagent.
        agent_id: Identifier of the specific subagent whose transcript should
            be returned.

    Returns:
        Full conversation detail for the subagent, scoped to its transcript
        with messages, usage, and context analytics.

    Raises:
        HTTPException: 404 if the subagent conversation cannot be found.
    """
    conversation = get_subagent_conversation(
        services,
        project_path=project_path,
        parent_session_id=session_id,
        agent_id=agent_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Subagent conversation not found")
    return conversation
