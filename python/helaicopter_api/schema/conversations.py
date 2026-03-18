"""Schemas for conversation summaries, detail views, and related read APIs."""

from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ConversationThreadType = Literal["main", "subagent"]
ConversationBlockType = Literal["text", "thinking", "tool_call"]
ContextCategory = Literal["tool", "mcp", "subagent", "thinking", "conversation"]
ConversationDagProviderParam = Literal["all", "claude", "codex"]


class ConversationListQueryParams(BaseModel):
    """Stable request parameters for conversation summaries."""

    model_config = ConfigDict(extra="forbid")

    project: str | None = Field(
        default=None,
        description="Optional encoded project path filter.",
    )
    days: int | None = Field(
        default=None,
        ge=1,
        description="Restrict summaries to the trailing number of days.",
    )


class ConversationDagListQueryParams(BaseModel):
    """Stable request parameters for conversation DAG summaries."""

    model_config = ConfigDict(extra="forbid")

    project: str | None = Field(
        default=None,
        description="Optional encoded project path filter.",
    )
    days: int | None = Field(
        default=None,
        ge=1,
        description="Restrict summaries to the trailing number of days.",
    )
    provider: ConversationDagProviderParam | None = Field(
        default=None,
        description="Optional provider filter. Use `all` or omit for combined DAGs.",
    )


class HistoryQueryParams(BaseModel):
    """Stable request parameters for combined CLI history."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of history entries to return.",
    )


class ConversationSummaryResponse(BaseModel):
    """Summary of a single Claude/Codex conversation session."""

    session_id: str
    project_path: str
    project_name: str
    thread_type: Literal["main", "subagent"]
    first_message: str
    timestamp: float
    created_at: float
    last_updated_at: float
    is_running: bool
    message_count: int = 0
    model: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    tool_use_count: int = 0
    failed_tool_call_count: int = 0
    tool_breakdown: dict[str, int] = Field(default_factory=dict)
    subagent_count: int = 0
    subagent_type_breakdown: dict[str, int] = Field(default_factory=dict)
    task_count: int = 0
    git_branch: str | None = None
    reasoning_effort: str | None = None
    speed: str | None = None
    total_reasoning_tokens: int | None = None


class ConversationUsageResponse(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


class ConversationMessageBlockResponse(BaseModel):
    """Display-oriented block within a conversation message."""

    type: ConversationBlockType
    text: str | None = None
    thinking: str | None = None
    char_count: int | None = None
    tool_use_id: str | None = None
    tool_name: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    is_error: bool | None = None


class ConversationMessageResponse(BaseModel):
    """Single rendered conversation message."""

    id: str
    role: str
    timestamp: float
    blocks: list[ConversationMessageBlockResponse] = Field(default_factory=list)
    usage: ConversationUsageResponse | None = None
    model: str | None = None
    reasoning_tokens: int | None = None
    speed: str | None = None


class ConversationPlanStepResponse(BaseModel):
    step: str
    status: str


class ConversationPlanResponse(BaseModel):
    """Embedded plan extracted from a conversation."""

    id: str
    slug: str
    title: str
    preview: str
    content: str
    provider: Literal["claude", "codex"]
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: str | None = None
    project_path: str | None = None
    explanation: str | None = None
    steps: list[ConversationPlanStepResponse] = Field(default_factory=list)


class ConversationSubagentResponse(BaseModel):
    """Known subagent metadata for a conversation."""

    agent_id: str
    description: str | None = None
    subagent_type: str | None = None
    nickname: str | None = None
    has_file: bool = False
    project_path: str | None = None
    session_id: str | None = None


class ConversationContextBucketResponse(BaseModel):
    label: str
    category: ContextCategory
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class ConversationContextStepResponse(BaseModel):
    message_id: str
    index: int
    role: str
    label: str
    category: ContextCategory
    timestamp: float
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0


class ConversationContextAnalyticsResponse(BaseModel):
    buckets: list[ConversationContextBucketResponse] = Field(default_factory=list)
    steps: list[ConversationContextStepResponse] = Field(default_factory=list)


class ConversationContextWindowResponse(BaseModel):
    peak_context_window: int = 0
    api_calls: int = 0
    cumulative_tokens: int = 0


class ConversationDetailResponse(BaseModel):
    """Structured detail response for one conversation."""

    session_id: str
    project_path: str
    thread_type: ConversationThreadType = "main"
    created_at: float
    last_updated_at: float
    is_running: bool
    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    plans: list[ConversationPlanResponse] = Field(default_factory=list)
    total_usage: ConversationUsageResponse = Field(default_factory=ConversationUsageResponse)
    model: str | None = None
    git_branch: str | None = None
    start_time: float = 0
    end_time: float = 0
    subagents: list[ConversationSubagentResponse] = Field(default_factory=list)
    context_analytics: ConversationContextAnalyticsResponse = Field(
        default_factory=ConversationContextAnalyticsResponse
    )
    context_window: ConversationContextWindowResponse = Field(
        default_factory=ConversationContextWindowResponse
    )
    reasoning_effort: str | None = None
    speed: str | None = None
    total_reasoning_tokens: int | None = None


class ProjectResponse(BaseModel):
    """Project listing entry for the conversations UI."""

    encoded_path: str
    display_name: str
    full_path: str
    session_count: int = 0
    last_activity: float = 0


class HistoryEntryResponse(BaseModel):
    """One CLI history entry from Claude or Codex."""

    display: str
    pasted_contents: dict[str, Any] | None = None
    timestamp: float = 0
    project: str | None = None


class TaskListResponse(BaseModel):
    """Task payloads associated with a conversation session."""

    session_id: str
    tasks: list[dict[str, Any]] = Field(default_factory=list)


class ConversationDagNodeResponse(BaseModel):
    """A single node in the conversation agent-tree DAG."""

    id: str
    session_id: str
    parent_session_id: str | None = None
    project_path: str
    label: str
    description: str | None = None
    nickname: str | None = None
    subagent_type: str | None = None
    thread_type: ConversationThreadType
    has_transcript: bool
    model: str | None = None
    message_count: int = 0
    total_tokens: int = 0
    timestamp: float
    depth: int = 0
    path: str
    is_root: bool


class ConversationDagEdgeResponse(BaseModel):
    id: str
    source: str
    target: str


class ConversationDagStatsResponse(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    total_subagent_nodes: int = 0
    max_depth: int = 0
    max_breadth: int = 0
    leaf_count: int = 0
    root_subagent_count: int = 0
    total_messages: int = 0
    total_tokens: int = 0


class ConversationDagResponse(BaseModel):
    """Full agent-tree DAG for a conversation."""

    project_path: str
    root_session_id: str
    nodes: list[ConversationDagNodeResponse] = Field(default_factory=list)
    edges: list[ConversationDagEdgeResponse] = Field(default_factory=list)
    stats: ConversationDagStatsResponse


class ConversationDagSummaryResponse(ConversationSummaryResponse):
    """Conversation summary row with embedded DAG stats."""

    dag: ConversationDagStatsResponse
