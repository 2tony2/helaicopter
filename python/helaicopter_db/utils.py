from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from helaicopter_domain.ids import (
    ConversationId,
    ConversationContextBucketId,
    ConversationContextStepId,
    ConversationMessageBlockId,
    ConversationMessageId,
    ConversationPlanRowId,
    ConversationSubagentRowId,
    ConversationTaskRowId,
    ModelId,
    ProjectId,
    SessionId,
    SubagentTypeId,
    ToolId,
)
from helaicopter_domain.paths import EncodedProjectKey
from helaicopter_domain.vocab import ProviderName


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_timestamp_ms(value: int | float | None) -> datetime:
    if value is None:
        return utc_now()
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def date_key(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def provider_for_project_path(project_path: EncodedProjectKey) -> ProviderName:
    return "codex" if project_path.startswith("codex:") else "claude"


def conversation_id(provider: ProviderName, session_id: SessionId) -> ConversationId:
    return ConversationId(f"{provider}:{session_id}")


def conversation_message_id(conversation_id: ConversationId, ordinal: int) -> ConversationMessageId:
    return ConversationMessageId(f"{conversation_id}:message:{ordinal}")


def conversation_message_block_id(
    message_id: ConversationMessageId,
    block_index: int,
) -> ConversationMessageBlockId:
    return ConversationMessageBlockId(f"{message_id}:block:{block_index}")


def conversation_plan_row_id(
    conversation_id: ConversationId,
    ordinal: int,
) -> ConversationPlanRowId:
    return ConversationPlanRowId(f"{conversation_id}:plan:{ordinal}")


def conversation_subagent_row_id(
    conversation_id: ConversationId,
    ordinal: int,
) -> ConversationSubagentRowId:
    return ConversationSubagentRowId(f"{conversation_id}:subagent:{ordinal}")


def conversation_task_row_id(
    conversation_id: ConversationId,
    ordinal: int,
) -> ConversationTaskRowId:
    return ConversationTaskRowId(f"{conversation_id}:task:{ordinal}")


def conversation_context_bucket_id(
    conversation_id: ConversationId,
    ordinal: int,
) -> ConversationContextBucketId:
    return ConversationContextBucketId(f"{conversation_id}:bucket:{ordinal}")


def conversation_context_step_id(
    conversation_id: ConversationId,
    ordinal: int,
) -> ConversationContextStepId:
    return ConversationContextStepId(f"{conversation_id}:step:{ordinal}")


def tool_dim_id(provider: ProviderName, tool_name: str) -> ToolId:
    return ToolId(f"{provider}:{tool_name}")


def model_dim_id(provider: ProviderName, model_name: str) -> ModelId:
    return ModelId(f"{provider}:{model_name}")


def project_dim_id(provider: ProviderName, project_path: EncodedProjectKey) -> ProjectId:
    return ProjectId(f"{provider}:{project_path}")


def subagent_dim_id(provider: ProviderName, subagent_type: str) -> SubagentTypeId:
    return SubagentTypeId(f"{provider}:{subagent_type}")


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
