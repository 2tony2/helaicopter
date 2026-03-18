"""Evaluation prompt management API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from helaicopter_api.application.evaluation_prompts import (
    EvaluationPromptNotFoundError,
    create_evaluation_prompt,
    delete_evaluation_prompt,
    list_evaluation_prompts,
    update_evaluation_prompt,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.evaluations import (
    EvaluationPromptCreateRequest,
    EvaluationPromptResponse,
    EvaluationPromptUpdateRequest,
)
from helaicopter_api.server.dependencies import get_services

evaluation_prompts_router = APIRouter(prefix="/evaluation-prompts", tags=["evaluations"])


@evaluation_prompts_router.get("", response_model=list[EvaluationPromptResponse], response_model_by_alias=True)
async def evaluation_prompts_index(
    services: BackendServices = Depends(get_services),
) -> list[EvaluationPromptResponse]:
    """List saved evaluation prompts with the built-in default first."""
    return list_evaluation_prompts(services)


@evaluation_prompts_router.post(
    "",
    response_model=EvaluationPromptResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def evaluation_prompts_create(
    body: EvaluationPromptCreateRequest,
    services: BackendServices = Depends(get_services),
) -> EvaluationPromptResponse:
    """Create a new user-managed evaluation prompt."""
    try:
        return create_evaluation_prompt(services, body)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@evaluation_prompts_router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def evaluation_prompts_delete(
    prompt_id: str,
    services: BackendServices = Depends(get_services),
) -> Response:
    """Delete one stored user-managed evaluation prompt."""
    try:
        delete_evaluation_prompt(services, prompt_id)
    except EvaluationPromptNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@evaluation_prompts_router.patch(
    "/{prompt_id}",
    response_model=EvaluationPromptResponse,
    response_model_by_alias=True,
)
async def evaluation_prompts_update(
    prompt_id: str,
    body: EvaluationPromptUpdateRequest,
    services: BackendServices = Depends(get_services),
) -> EvaluationPromptResponse:
    """Update one stored evaluation prompt."""
    try:
        return update_evaluation_prompt(services, prompt_id, body)
    except EvaluationPromptNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
