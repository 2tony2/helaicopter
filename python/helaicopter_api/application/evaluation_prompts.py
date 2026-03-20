"""Application-layer evaluation prompt management."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.evaluations import (
    EvaluationPromptCreateRequest,
    EvaluationPromptResponse,
    EvaluationPromptUpdateRequest,
)
from helaicopter_domain.ids import PromptId


@runtime_checkable
class _ModelDumpable(Protocol):
    def model_dump(self, *, mode: str = "python") -> object: ...


class EvaluationPromptNotFoundError(LookupError):
    """Raised when a prompt id does not resolve to a stored prompt."""


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_evaluation_prompts(services: InstanceOf[BackendServices]) -> list[EvaluationPromptResponse]:
    """Return all prompts after explicitly ensuring the built-in default exists.

    Guarantees the built-in default evaluation prompt is present before
    querying, so callers always receive at least one entry.

    Args:
        services: Initialised backend services providing the SQLite prompt store.

    Returns:
        List of all stored ``EvaluationPromptResponse`` objects, including the
        built-in default.
    """
    services.app_sqlite_store.ensure_default_evaluation_prompt()
    prompts = services.app_sqlite_store.list_evaluation_prompts()
    return [_to_response(prompt) for prompt in prompts]


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def resolve_evaluation_prompt(
    services: InstanceOf[BackendServices],
    *,
    prompt_id: str | None = None,
) -> EvaluationPromptResponse:
    """Resolve one prompt, defaulting to the built-in prompt when no id is supplied.

    Args:
        services: Initialised backend services providing the SQLite prompt store.
        prompt_id: Optional prompt identifier. When ``None``, the built-in
            default prompt is returned (creating it if it does not yet exist).

    Returns:
        The resolved ``EvaluationPromptResponse``.

    Raises:
        EvaluationPromptNotFoundError: If a ``prompt_id`` is supplied but does
            not match any stored prompt.
    """
    if prompt_id is None:
        return _to_response(services.app_sqlite_store.ensure_default_evaluation_prompt())

    prompt = services.app_sqlite_store.get_evaluation_prompt(PromptId(prompt_id))
    if prompt is None:
        raise EvaluationPromptNotFoundError(f"Prompt {prompt_id!r} not found.")
    return _to_response(prompt)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def create_evaluation_prompt(
    services: InstanceOf[BackendServices],
    body: EvaluationPromptCreateRequest,
) -> EvaluationPromptResponse:
    """Persist and return a user-managed evaluation prompt.

    Args:
        services: Initialised backend services providing the SQLite prompt store.
        body: Create request containing the prompt ``name``, ``description``,
            and ``prompt_text``.

    Returns:
        The newly created ``EvaluationPromptResponse``.
    """
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
    """Update one stored evaluation prompt.

    Args:
        services: Initialised backend services providing the SQLite prompt store.
        prompt_id: Identifier of the prompt to update.
        body: Update request containing the new ``name``, ``description``,
            and/or ``prompt_text`` values.

    Returns:
        The updated ``EvaluationPromptResponse``.

    Raises:
        EvaluationPromptNotFoundError: If the prompt ID does not match any
            stored prompt.
    """
    try:
        prompt = services.app_sqlite_store.update_evaluation_prompt(
            PromptId(prompt_id),
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
    """Delete one stored user-managed prompt.

    Args:
        services: Initialised backend services providing the SQLite prompt store.
        prompt_id: Identifier of the prompt to delete.

    Raises:
        EvaluationPromptNotFoundError: If the prompt ID does not match any
            stored prompt.
    """
    try:
        services.app_sqlite_store.delete_evaluation_prompt(PromptId(prompt_id))
    except ValueError as error:
        if str(error) == "Prompt not found.":
            raise EvaluationPromptNotFoundError(f"Prompt {prompt_id!r} not found.") from error
        raise


def _to_response(prompt: object) -> EvaluationPromptResponse:
    if isinstance(prompt, _ModelDumpable):
        return EvaluationPromptResponse.model_validate(prompt.model_dump(mode="python"))
    return EvaluationPromptResponse.model_validate(prompt)
