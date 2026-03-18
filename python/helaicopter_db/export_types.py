from __future__ import annotations

from typing import TypedDict

from pydantic import TypeAdapter, ValidationError


class ExportCostBreakdown(TypedDict):
    inputCost: float
    outputCost: float
    cacheWriteCost: float
    cacheReadCost: float
    totalCost: float


class ExportUsagePayload(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


class ExportMessageBlockPayload(TypedDict, total=False):
    type: str
    text: str
    thinking: str
    toolUseId: str
    toolName: str
    input: object
    result: object
    isError: bool


class ExportMessagePayload(TypedDict, total=False):
    role: str
    timestamp: int | float
    model: str
    reasoningTokens: int
    speed: str
    usage: ExportUsagePayload
    blocks: list[ExportMessageBlockPayload]


class ExportPlanPayload(TypedDict, total=False):
    id: str
    slug: str
    title: str
    preview: str
    content: str
    provider: str
    timestamp: int | float
    model: str
    explanation: str
    steps: list[dict[str, object]]


class ExportSubagentPayload(TypedDict, total=False):
    agentId: str
    description: str
    subagentType: str
    nickname: str
    hasFile: bool


class ExportContextBucketPayload(TypedDict, total=False):
    label: str
    category: str
    inputTokens: int
    outputTokens: int
    cacheWriteTokens: int
    cacheReadTokens: int
    totalTokens: int
    calls: int


class ExportContextStepPayload(TypedDict, total=False):
    messageId: str
    role: str
    label: str
    category: str
    timestamp: int | float
    inputTokens: int
    outputTokens: int
    cacheWriteTokens: int
    cacheReadTokens: int
    totalTokens: int


class ExportContextAnalyticsPayload(TypedDict, total=False):
    buckets: list[ExportContextBucketPayload]
    steps: list[ExportContextStepPayload]


class ExportConversationSummaryPayload(TypedDict, total=False):
    sessionId: str
    projectPath: str
    projectName: str
    threadType: str
    firstMessage: str
    timestamp: int | float
    messageCount: int
    model: str
    gitBranch: str
    reasoningEffort: str
    speed: str
    totalInputTokens: int
    totalOutputTokens: int
    totalCacheCreationTokens: int
    totalCacheReadTokens: int
    totalReasoningTokens: int
    toolUseCount: int
    subagentCount: int
    taskCount: int
    toolBreakdown: dict[str, int]
    subagentTypeBreakdown: dict[str, int]


class ExportConversationDetailPayload(TypedDict, total=False):
    endTime: int | float
    messages: list[ExportMessagePayload]
    plans: list[ExportPlanPayload]
    subagents: list[ExportSubagentPayload]
    contextAnalytics: ExportContextAnalyticsPayload


class ExportConversationEnvelope(TypedDict):
    type: str
    summary: ExportConversationSummaryPayload
    detail: ExportConversationDetailPayload | None
    tasks: list[object]
    cost: ExportCostBreakdown


class ExportMetaPayload(TypedDict):
    conversationCount: int
    inputKey: str
    scopeLabel: str
    windowDays: int
    windowStart: str | None
    windowEnd: str | None


_EXPORT_CONVERSATION_ENVELOPE_ADAPTER = TypeAdapter(ExportConversationEnvelope)
_EXPORT_META_PAYLOAD_ADAPTER = TypeAdapter(ExportMetaPayload)


def parse_export_conversation_envelope(payload: object) -> ExportConversationEnvelope | None:
    try:
        return _EXPORT_CONVERSATION_ENVELOPE_ADAPTER.validate_python(payload)
    except ValidationError:
        return None


def parse_export_meta_payload(payload: object) -> ExportMetaPayload | None:
    try:
        return _EXPORT_META_PAYLOAD_ADAPTER.validate_python(payload)
    except ValidationError:
        return None
