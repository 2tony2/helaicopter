"""Subagent conversation detail API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from helaicopter_api.application.conversations import get_subagent_conversation
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.conversations import ConversationDetailResponse
from helaicopter_api.server.dependencies import get_services

subagents_router = APIRouter(prefix="/subagents", tags=["conversations"])


@subagents_router.get(
    "/{project_path}/{session_id}/{agent_id}",
    response_model=ConversationDetailResponse,
)
async def subagents_detail(
    project_path: str,
    session_id: str,
    agent_id: str,
    services: BackendServices = Depends(get_services),
) -> ConversationDetailResponse:
    """Return one subagent transcript for the conversation viewer."""
    conversation = get_subagent_conversation(
        services,
        project_path=project_path,
        parent_session_id=session_id,
        agent_id=agent_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Subagent conversation not found")
    return conversation
