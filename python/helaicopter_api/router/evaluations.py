"""Conversation evaluation job API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from helaicopter_api.application.evaluation_prompts import EvaluationPromptNotFoundError
from helaicopter_api.application.evaluations import (
    ConversationEvaluationConversationNotFoundError,
    create_conversation_evaluation,
    list_conversation_evaluations,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.evaluations import (
    ConversationEvaluationCreateRequest,
    ConversationEvaluationResponse,
)
from helaicopter_api.server.dependencies import get_services

evaluations_router = APIRouter(prefix="/conversations", tags=["evaluations"])


@evaluations_router.get(
    "/{project_path}/{session_id}/evaluations",
    response_model=list[ConversationEvaluationResponse],
    response_model_by_alias=True,
)
async def conversation_evaluations_index(
    project_path: str,
    session_id: str,
    parent_session_id: str | None = Query(default=None),
    services: BackendServices = Depends(get_services),
) -> list[ConversationEvaluationResponse]:
    """List persisted evaluation jobs for a specific conversation.

    Args:
        project_path: Path identifying the project that owns the conversation.
        session_id: Unique identifier of the conversation session.
        parent_session_id: Optional parent session ID to scope the lookup to a
            sub-conversation. Defaults to None.

    Returns:
        A list of evaluation job records associated with the conversation,
        ordered by creation time.
    """
    try:
        return list_conversation_evaluations(
            services,
            project_path=project_path,
            session_id=session_id,
            parent_session_id=parent_session_id,
        )
    except ConversationEvaluationConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@evaluations_router.post(
    "/{project_path}/{session_id}/evaluations",
    response_model=ConversationEvaluationResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def conversation_evaluations_create(
    project_path: str,
    session_id: str,
    body: ConversationEvaluationCreateRequest,
    parent_session_id: str | None = Query(default=None),
    services: BackendServices = Depends(get_services),
) -> ConversationEvaluationResponse:
    """Create and enqueue a backend-owned evaluation job for a conversation.

    Args:
        project_path: Path identifying the project that owns the conversation.
        session_id: Unique identifier of the conversation session to evaluate.
        body: Evaluation job creation request containing the evaluation prompt
            reference and any additional configuration.
        parent_session_id: Optional parent session ID to scope the evaluation
            to a sub-conversation. Defaults to None.

    Returns:
        The newly created evaluation job record in an accepted (pending) state.
    """
    try:
        return create_conversation_evaluation(
            services,
            project_path=project_path,
            session_id=session_id,
            body=body,
            parent_session_id=parent_session_id,
        )
    except ConversationEvaluationConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EvaluationPromptNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
