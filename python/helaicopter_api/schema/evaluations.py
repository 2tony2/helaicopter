"""Schemas for conversation evaluation records and prompts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class EvaluationCamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class EvaluationPromptWriteRequest(EvaluationCamelModel):
    """Shared validation for prompt create/update payloads."""

    name: str
    description: str | None = None
    prompt_text: str

    @field_validator("name", "prompt_text", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("name", "prompt_text")
    @classmethod
    def _require_non_empty_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Field cannot be blank.")
        return value

    @field_validator("description", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class EvaluationPromptCreateRequest(EvaluationPromptWriteRequest):
    """Payload accepted by the prompt creation endpoint."""


class EvaluationPromptUpdateRequest(EvaluationPromptWriteRequest):
    """Payload accepted by the prompt update endpoint."""


class EvaluationPromptResponse(EvaluationCamelModel):
    """An evaluation prompt template."""

    prompt_id: str
    name: str
    description: str | None = None
    prompt_text: str
    is_default: bool = False
    created_at: str
    updated_at: str


class ConversationEvaluationResponse(EvaluationCamelModel):
    """Result of running an evaluation against a conversation."""

    evaluation_id: str
    conversation_id: str
    prompt_id: str | None = None
    provider: Literal["claude", "codex"]
    model: str
    status: Literal["running", "completed", "failed"]
    scope: Literal["full", "failed_tool_calls", "guided_subset"]
    selection_instruction: str | None = None
    prompt_name: str
    prompt_text: str
    report_markdown: str | None = None
    raw_output: str | None = None
    error_message: str | None = None
    command: str
    created_at: str
    finished_at: str | None = None
    duration_ms: float | None = None


class ConversationEvaluationCreateRequest(EvaluationCamelModel):
    """Payload accepted by the conversation evaluation create endpoint."""

    provider: Literal["claude", "codex"]
    model: str
    scope: Literal["full", "failed_tool_calls", "guided_subset"]
    prompt_id: str | None = None
    prompt_name: str | None = None
    prompt_text: str | None = None
    selection_instruction: str | None = None

    @field_validator("model", mode="before")
    @classmethod
    def _strip_model(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("model")
    @classmethod
    def _require_model(cls, value: str) -> str:
        if not value:
            raise ValueError("Model is required.")
        return value

    @field_validator("prompt_id", "prompt_name", "prompt_text", "selection_instruction", mode="before")
    @classmethod
    def _strip_optional_fields(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("prompt_id")
    @classmethod
    def _require_prompt_id_text_when_present(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Prompt id cannot be blank.")
        return value

    @model_validator(mode="after")
    def _validate_prompt_selection(self) -> "ConversationEvaluationCreateRequest":
        if self.scope == "guided_subset" and not self.selection_instruction:
            raise ValueError("Selection instruction is required for guided subsets.")
        if self.prompt_id is None and bool(self.prompt_name) != bool(self.prompt_text):
            raise ValueError("Prompt name and prompt text must be provided together.")
        return self
