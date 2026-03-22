"""legacy `snake_case` schemas for conversations; Wave 7 keeps this deferred."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel
from helaicopter_domain.ids import AgentId, PlanId, SessionId
from helaicopter_domain.paths import EncodedProjectKey, ProjectDisplayPath
from helaicopter_domain.vocab import ProviderName, ProviderSelection

ConversationDagProviderParam = ProviderSelection

ConversationThreadType = Literal["main", "subagent"]
ContextCategory = Literal["tool", "mcp", "subagent", "thinking", "conversation"]


class ConversationListQueryParams(BaseModel):
    """Stable request parameters for conversation summaries."""

    model_config = ConfigDict(extra="forbid")

    project: EncodedProjectKey | None = Field(
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

    project: EncodedProjectKey | None = Field(
        default=None,
        description="Optional encoded project path filter.",
    )
    days: int | None = Field(
        default=None,
        ge=1,
        description="Restrict summaries to the trailing number of days.",
    )
    provider: ProviderSelection | None = Field(
        default=None,
        description="Optional provider filter. Use `all` or omit for combined DAGs across Claude, Codex, and OpenClaw.",
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
    """Summary of a single Claude, Codex, or OpenClaw conversation session."""

    session_id: SessionId
    project_path: EncodedProjectKey
    project_name: ProjectDisplayPath
    route_slug: str
    conversation_ref: str
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
    tool_breakdown: dict[str, int] = {}
    subagent_count: int = 0
    subagent_type_breakdown: dict[str, int] = {}
    task_count: int = 0
    git_branch: str | None = None
    reasoning_effort: str | None = None
    speed: str | None = None
    total_reasoning_tokens: int | None = None


class ConversationUsageResponse(BaseModel):
    """Token usage counts for a single conversation or message."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


class ConversationToolInputResponse(RootModel[dict[str, object]]):
    """Opaque tool input payload exposed on the legacy conversation surface."""


class ConversationTextBlockResponse(BaseModel):
    """Rendered plain-text block within a conversation message."""

    type: Literal["text"]
    text: str


class ConversationThinkingBlockResponse(BaseModel):
    """Rendered reasoning block within a conversation message."""

    type: Literal["thinking"]
    thinking: str
    char_count: int | None = None


class ConversationToolCallBlockResponse(BaseModel):
    """Rendered tool-call block within a conversation message."""

    type: Literal["tool_call"]
    tool_use_id: str | None = None
    tool_name: str | None = None
    input: ConversationToolInputResponse = Field(
        default_factory=lambda: ConversationToolInputResponse(root={})
    )
    result: str | None = None
    is_error: bool | None = None


ConversationMessageBlockResponse = Annotated[
    ConversationTextBlockResponse
    | ConversationThinkingBlockResponse
    | ConversationToolCallBlockResponse,
    Field(discriminator="type"),
]


class ConversationMessageResponse(BaseModel):
    """Single rendered conversation message."""

    id: str
    role: str
    timestamp: float
    blocks: list[ConversationMessageBlockResponse] = []
    usage: ConversationUsageResponse | None = None
    model: str | None = None
    reasoning_tokens: int | None = None
    speed: str | None = None


class ConversationPlanStepResponse(BaseModel):
    """A single step within an embedded conversation plan."""

    step: str
    status: str


class ConversationPlanResponse(BaseModel):
    """Embedded plan extracted from a conversation."""

    id: PlanId
    slug: str
    title: str
    preview: str
    content: str
    provider: ProviderName
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: SessionId | None = None
    project_path: EncodedProjectKey | None = None
    route_slug: str | None = None
    conversation_ref: str | None = None
    explanation: str | None = None
    steps: list[ConversationPlanStepResponse] = []


class ConversationSubagentResponse(BaseModel):
    """Known subagent metadata for a conversation."""

    agent_id: AgentId
    description: str | None = None
    subagent_type: str | None = None
    nickname: str | None = None
    has_file: bool = False
    project_path: EncodedProjectKey | None = None
    session_id: SessionId | None = None
    route_slug: str | None = None
    conversation_ref: str | None = None


class ConversationContextBucketResponse(BaseModel):
    """Aggregated token usage for a named context category (e.g. tool, mcp, subagent)."""

    label: str
    category: ContextCategory
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class ConversationContextStepResponse(BaseModel):
    """Per-message token usage entry in the context analytics step sequence."""

    message_id: str = Field(
        description="Source/provider message identifier captured in context analytics; not the persisted conversation message row ID."
    )
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
    """Bucketed and step-level context usage analytics for a conversation."""

    buckets: list[ConversationContextBucketResponse] = []
    steps: list[ConversationContextStepResponse] = []


class ConversationContextWindowResponse(BaseModel):
    """Summary of context window utilisation across all API calls in a conversation."""

    peak_context_window: int = 0
    api_calls: int = 0
    cumulative_tokens: int = 0


class ConversationDetailResponse(BaseModel):
    """Structured detail response for one conversation."""

    session_id: SessionId
    project_path: EncodedProjectKey
    route_slug: str
    conversation_ref: str
    thread_type: ConversationThreadType = "main"
    created_at: float
    last_updated_at: float
    is_running: bool
    messages: list[ConversationMessageResponse] = []
    plans: list[ConversationPlanResponse] = []
    total_usage: ConversationUsageResponse = Field(default_factory=ConversationUsageResponse)
    model: str | None = None
    git_branch: str | None = None
    start_time: float = 0
    end_time: float = 0
    subagents: list[ConversationSubagentResponse] = []
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

    encoded_path: EncodedProjectKey
    display_name: ProjectDisplayPath
    full_path: str
    session_count: int = 0
    last_activity: float = 0


class HistoryPastedContentsResponse(RootModel[dict[str, object]]):
    """Opaque pasted-content payload exposed on the legacy history surface."""


class HistoryEntryResponse(BaseModel):
    """One CLI history entry from Claude or Codex."""

    display: str
    pasted_contents: HistoryPastedContentsResponse | None = None
    timestamp: float = 0
    project: str | None = None


class ConversationTaskResponse(BaseModel):
    """Legacy task payload exposed on the conversations API."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    task_id: str | None = Field(default=None, alias="taskId")
    title: str | None = None


class TaskListResponse(BaseModel):
    """Task payloads associated with a conversation session."""

    session_id: SessionId
    tasks: list[ConversationTaskResponse] = []


class ConversationDagNodeResponse(BaseModel):
    """A single node in the conversation agent-tree DAG."""

    id: str
    session_id: SessionId
    parent_session_id: SessionId | None = None
    project_path: EncodedProjectKey
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
    path: str | None = None
    is_root: bool


class ConversationRefResolutionResponse(BaseModel):
    """Resolved routing metadata for a conversation reference."""

    conversation_ref: str
    route_slug: str
    project_path: EncodedProjectKey
    session_id: SessionId
    thread_type: ConversationThreadType
    parent_session_id: SessionId | None = None


class ConversationDagEdgeResponse(BaseModel):
    """A directed edge connecting two nodes in the conversation agent-tree DAG."""

    id: str
    source: str
    target: str


class ConversationDagStatsResponse(BaseModel):
    """Aggregate structural statistics for a conversation agent-tree DAG."""

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

    project_path: EncodedProjectKey
    root_session_id: SessionId
    nodes: list[ConversationDagNodeResponse] = []
    edges: list[ConversationDagEdgeResponse] = []
    stats: ConversationDagStatsResponse


class ConversationDagSummaryResponse(ConversationSummaryResponse):
    """Conversation summary row with embedded DAG stats."""

    dag: ConversationDagStatsResponse
