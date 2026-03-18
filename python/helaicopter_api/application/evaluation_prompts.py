"""Application-layer evaluation prompt management."""

from __future__ import annotations

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.evaluations import (
    EvaluationPromptCreateRequest,
    EvaluationPromptResponse,
    EvaluationPromptUpdateRequest,
)


class EvaluationPromptNotFoundError(LookupError):
    """Raised when a prompt id does not resolve to a stored prompt."""


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_evaluation_prompts(services: InstanceOf[BackendServices]) -> list[EvaluationPromptResponse]:
    """Return all prompts after explicitly ensuring the built-in default exists."""
    services.app_sqlite_store.ensure_default_evaluation_prompt()
    prompts = services.app_sqlite_store.list_evaluation_prompts()
    return [_to_response(prompt) for prompt in prompts]


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def resolve_evaluation_prompt(
    services: InstanceOf[BackendServices],
    *,
    prompt_id: str | None = None,
) -> EvaluationPromptResponse:
    """Resolve one prompt, defaulting to the built-in prompt when no id is supplied."""
    if prompt_id is None:
        return _to_response(services.app_sqlite_store.ensure_default_evaluation_prompt())

    prompt = services.app_sqlite_store.get_evaluation_prompt(prompt_id)
    if prompt is None:
        raise EvaluationPromptNotFoundError(f"Prompt {prompt_id!r} not found.")
    return _to_response(prompt)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def create_evaluation_prompt(
    services: InstanceOf[BackendServices],
    body: EvaluationPromptCreateRequest,
) -> EvaluationPromptResponse:
    """Persist and return a user-managed evaluation prompt."""
    prompt = services.app_sqlite_store.create_evaluation_prompt(
        name=body.name,
        description=body.description,
        prompt_text=body.prompt_text,
    )
    return _to_response(prompt)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def update_evaluation_prompt(
    services: InstanceOf[BackendServices],
    prompt_id: str,
    body: EvaluationPromptUpdateRequest,
) -> EvaluationPromptResponse:
    """Update one stored evaluation prompt."""
    try:
        prompt = services.app_sqlite_store.update_evaluation_prompt(
            prompt_id,
            name=body.name,
            description=body.description,
            prompt_text=body.prompt_text,
        )
    except ValueError as error:
        if str(error) == "Prompt not found.":
            raise EvaluationPromptNotFoundError(f"Prompt {prompt_id!r} not found.") from error
        raise

    return _to_response(prompt)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def delete_evaluation_prompt(services: InstanceOf[BackendServices], prompt_id: str) -> None:
    """Delete one stored user-managed prompt."""
    try:
        services.app_sqlite_store.delete_evaluation_prompt(prompt_id)
    except ValueError as error:
        if str(error) == "Prompt not found.":
            raise EvaluationPromptNotFoundError(f"Prompt {prompt_id!r} not found.") from error
        raise


def _to_response(prompt: object) -> EvaluationPromptResponse:
    if hasattr(prompt, "model_dump"):
        return EvaluationPromptResponse.model_validate(prompt.model_dump(mode="python"))
    return EvaluationPromptResponse.model_validate(prompt)
