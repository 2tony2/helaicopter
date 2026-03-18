"""Conversation evaluation job API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

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
)
async def conversation_evaluations_index(
    project_path: str,
    session_id: str,
    services: BackendServices = Depends(get_services),
) -> list[ConversationEvaluationResponse]:
    """List persisted evaluation jobs for one conversation."""
    return list_conversation_evaluations(
        services,
        project_path=project_path,
        session_id=session_id,
    )


@evaluations_router.post(
    "/{project_path}/{session_id}/evaluations",
    response_model=ConversationEvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def conversation_evaluations_create(
    project_path: str,
    session_id: str,
    body: ConversationEvaluationCreateRequest,
    services: BackendServices = Depends(get_services),
) -> ConversationEvaluationResponse:
    """Create and submit a backend-owned evaluation job."""
    try:
        return create_conversation_evaluation(
            services,
            project_path=project_path,
            session_id=session_id,
            body=body,
        )
    except ConversationEvaluationConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EvaluationPromptNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
