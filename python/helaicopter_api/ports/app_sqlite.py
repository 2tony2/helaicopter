"""Port protocols for app-local SQLite data and persistence."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

SupportedProvider = Literal["claude", "codex"]
EvaluationStatus = Literal["running", "completed", "failed"]
EvaluationScope = Literal["full", "failed_tool_calls", "guided_subset"]


class HistoricalConversationSummary(BaseModel):
    conversation_id: str
    provider: str
    session_id: str
    project_path: str
    project_name: str
    thread_type: str = "main"
    first_message: str
    started_at: str
    ended_at: str
    message_count: int = 0
    model: str | None = None
    git_branch: str | None = None
    reasoning_effort: str | None = None
    speed: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_write_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_reasoning_tokens: int = 0
    tool_use_count: int = 0
    failed_tool_call_count: int = 0
    tool_breakdown: dict[str, int] = Field(default_factory=dict)
    subagent_count: int = 0
    subagent_type_breakdown: dict[str, int] = Field(default_factory=dict)
    task_count: int = 0


class HistoricalMessageBlock(BaseModel):
    block_index: int
    block_type: str
    text_content: str | None = None
    tool_use_id: str | None = None
    tool_name: str | None = None
    tool_input_json: str | None = None
    tool_result_text: str | None = None
    is_error: bool = False


class HistoricalConversationMessage(BaseModel):
    message_id: str
    ordinal: int
    role: str
    timestamp: str
    model: str | None = None
    reasoning_tokens: int = 0
    speed: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    text_preview: str = ""
    blocks: list[HistoricalMessageBlock] = Field(default_factory=list)


class HistoricalConversationPlan(BaseModel):
    plan_row_id: str
    plan_id: str
    slug: str
    title: str
    preview: str
    content: str
    provider: str
    timestamp: str
    model: str | None = None
    explanation: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)


class HistoricalConversationSubagent(BaseModel):
    subagent_row_id: str
    agent_id: str
    description: str | None = None
    subagent_type: str | None = None
    nickname: str | None = None
    has_file: bool = False


class HistoricalContextBucket(BaseModel):
    bucket_row_id: str
    label: str
    category: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class HistoricalContextStep(BaseModel):
    step_row_id: str
    message_id: str
    ordinal: int
    role: str
    label: str
    category: str
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0


class HistoricalConversationRecord(HistoricalConversationSummary):
    messages: list[HistoricalConversationMessage] = Field(default_factory=list)
    plans: list[HistoricalConversationPlan] = Field(default_factory=list)
    subagents: list[HistoricalConversationSubagent] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    context_buckets: list[HistoricalContextBucket] = Field(default_factory=list)
    context_steps: list[HistoricalContextStep] = Field(default_factory=list)


class EvaluationPromptRecord(BaseModel):
    prompt_id: str
    name: str
    description: str | None = None
    prompt_text: str
    is_default: bool = False
    created_at: str
    updated_at: str


class ConversationEvaluationRecord(BaseModel):
    evaluation_id: str
    conversation_id: str
    prompt_id: str | None = None
    provider: SupportedProvider
    model: str
    status: EvaluationStatus
    scope: EvaluationScope
    selection_instruction: str | None = None
    prompt_name: str
    prompt_text: str
    report_markdown: str | None = None
    raw_output: str | None = None
    error_message: str | None = None
    command: str
    created_at: str
    finished_at: str | None = None
    duration_ms: int | None = None


class ProviderSubscriptionSetting(BaseModel):
    provider: SupportedProvider
    has_subscription: bool
    monthly_cost: float
    updated_at: str


class SubscriptionSettings(BaseModel):
    claude: ProviderSubscriptionSetting
    codex: ProviderSubscriptionSetting


@runtime_checkable
class AppSqliteStore(Protocol):
    """Read historical app-local data and persist mutable app settings."""

    def list_historical_conversations(
        self,
        *,
        project_path: str | None = None,
        days: int | None = None,
    ) -> list[HistoricalConversationSummary]:
        """Return persisted historical conversations from the OLTP SQLite DB."""
        ...

    def get_historical_conversation(
        self,
        *,
        project_path: str,
        session_id: str,
    ) -> HistoricalConversationRecord | None:
        """Return one persisted historical conversation with nested detail tables."""
        ...

    def get_historical_tasks_for_session(self, session_id: str) -> list[dict[str, Any]] | None:
        """Return persisted task payloads for one session, or ``None`` if missing."""
        ...

    def ensure_default_evaluation_prompt(self) -> EvaluationPromptRecord:
        """Persist the built-in default prompt when possible and return it."""
        ...

    def list_evaluation_prompts(self) -> list[EvaluationPromptRecord]:
        """Return evaluation prompts, including the built-in default prompt."""
        ...

    def get_evaluation_prompt(self, prompt_id: str) -> EvaluationPromptRecord | None:
        """Return one prompt by id, resolving the built-in default explicitly."""
        ...

    def create_evaluation_prompt(
        self,
        *,
        name: str,
        prompt_text: str,
        description: str | None = None,
    ) -> EvaluationPromptRecord:
        """Persist and return a user-managed evaluation prompt."""
        ...

    def update_evaluation_prompt(
        self,
        prompt_id: str,
        *,
        name: str,
        prompt_text: str,
        description: str | None = None,
    ) -> EvaluationPromptRecord:
        """Update and return one prompt."""
        ...

    def delete_evaluation_prompt(self, prompt_id: str) -> None:
        """Delete a non-default prompt."""
        ...

    def list_conversation_evaluations(self, conversation_id: str) -> list[ConversationEvaluationRecord]:
        """Return evaluations for one conversation, newest first."""
        ...

    def create_conversation_evaluation(
        self,
        *,
        conversation_id: str,
        provider: SupportedProvider,
        model: str,
        status: EvaluationStatus,
        scope: EvaluationScope,
        prompt_name: str,
        prompt_text: str,
        command: str,
        prompt_id: str | None = None,
        selection_instruction: str | None = None,
        report_markdown: str | None = None,
        raw_output: str | None = None,
        error_message: str | None = None,
        finished_at: str | None = None,
        duration_ms: int | None = None,
    ) -> ConversationEvaluationRecord:
        """Persist and return a conversation evaluation."""
        ...

    def update_conversation_evaluation(
        self,
        evaluation_id: str,
        *,
        status: EvaluationStatus,
        command: str,
        report_markdown: str | None = None,
        raw_output: str | None = None,
        error_message: str | None = None,
        finished_at: str | None = None,
        duration_ms: int | None = None,
    ) -> ConversationEvaluationRecord:
        """Update and return one persisted conversation evaluation."""
        ...

    def get_subscription_settings(self) -> SubscriptionSettings:
        """Return persisted subscription settings merged with backend defaults."""
        ...

    def update_subscription_settings(
        self,
        updates: dict[SupportedProvider, dict[str, Any]],
    ) -> SubscriptionSettings:
        """Persist provider subscription settings and return the merged result."""
        ...
