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
    """List saved evaluation prompts with the built-in default first.

    Returns:
        Ordered list of evaluation prompt templates. The built-in default
        prompt appears first, followed by user-managed prompts sorted by
        creation time.
    """
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
    """Create a new user-managed evaluation prompt.

    Args:
        body: Prompt creation payload containing ``name``, ``prompt_text``
            (both required and non-blank), and an optional ``description``.

    Returns:
        The newly created evaluation prompt with its assigned ``prompt_id``
        and timestamps.

    Raises:
        HTTPException: 400 if the payload fails validation (e.g. blank fields).
        HTTPException: 503 if the backing storage is unavailable.
    """
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
    """Delete one stored user-managed evaluation prompt.

    Args:
        prompt_id: Unique identifier of the prompt to delete. Built-in default
            prompts cannot be deleted.

    Returns:
        Empty 204 No Content response on success.

    Raises:
        HTTPException: 400 if the prompt ID refers to a protected built-in
            prompt.
        HTTPException: 404 if no prompt with the given ID exists.
    """
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
    """Update one stored evaluation prompt.

    Args:
        prompt_id: Unique identifier of the prompt to update.
        body: Update payload containing the revised ``name``, ``prompt_text``,
            and optional ``description``. All write fields are validated as
            non-blank.

    Returns:
        The updated evaluation prompt reflecting the new field values and an
        updated ``updated_at`` timestamp.

    Raises:
        HTTPException: 400 if the payload fails validation.
        HTTPException: 404 if no prompt with the given ID exists.
        HTTPException: 503 if the backing storage is unavailable.
    """
    try:
        return update_evaluation_prompt(services, prompt_id, body)
    except EvaluationPromptNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
