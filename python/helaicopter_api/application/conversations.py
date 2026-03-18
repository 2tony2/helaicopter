"""Application-layer read APIs for conversations, projects, history, and tasks."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.app_sqlite import (
    HistoricalConversationMessage,
    HistoricalConversationRecord,
    HistoricalConversationSummary,
    HistoricalMessageBlock,
)
from helaicopter_api.ports.claude_fs import RawConversationEvent
from helaicopter_api.ports.codex_sqlite import CodexSessionArtifact, CodexThreadRecord
from helaicopter_api.pure.conversation_dag import build_conversation_dag
from helaicopter_api.schema.conversations import (
    ConversationContextAnalyticsResponse,
    ConversationContextBucketResponse,
    ConversationContextStepResponse,
    ConversationContextWindowResponse,
    ConversationDagProviderParam,
    ConversationDagResponse,
    ConversationDagSummaryResponse,
    ConversationDetailResponse,
    ConversationListQueryParams,
    ConversationMessageBlockResponse,
    ConversationMessageResponse,
    ConversationPlanResponse,
    ConversationPlanStepResponse,
    ConversationSubagentResponse,
    ConversationSummaryResponse,
    ConversationUsageResponse,
    HistoryEntryResponse,
    ProjectResponse,
    TaskListResponse,
)

_CODEX_SESSION_ID_PATTERN = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.jsonl$"
)
_ACTIVE_WINDOW = timedelta(minutes=1)
_MAX_RESULT_LENGTH = 20_000


def list_conversations(
    services: BackendServices,
    *,
    project: str | None = None,
    days: int | None = None,
) -> list[ConversationSummaryResponse]:
    """Return merged persisted and live conversation summaries."""
    summaries_by_key: dict[tuple[str, str], ConversationSummaryResponse] = {}

    for summary in services.app_sqlite_store.list_historical_conversations(
        project_path=project,
        days=days,
    ):
        shaped = _shape_historical_summary(summary)
        _merge_summary(summaries_by_key, shaped)

    if project is None or not project.startswith("codex:"):
        for shaped in _list_claude_live_summaries(services, project=project, days=days):
            _merge_summary(summaries_by_key, shaped)

    if project is None or project.startswith("codex:"):
        for shaped in _list_codex_live_summaries(services, project=project, days=days):
            _merge_summary(summaries_by_key, shaped)

    return sorted(
        summaries_by_key.values(),
        key=lambda item: (-item.last_updated_at, item.project_path, item.session_id),
    )


def get_conversation(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
) -> ConversationDetailResponse | None:
    """Return one conversation detail view from persisted data or live artifacts."""
    if historical := services.app_sqlite_store.get_historical_conversation(
        project_path=project_path,
        session_id=session_id,
    ):
        return _shape_historical_detail(historical)

    if project_path.startswith("codex:"):
        return _get_codex_live_conversation(services, session_id=session_id, project_path=project_path)
    return _get_claude_live_conversation(services, project_path=project_path, session_id=session_id)


def get_subagent_conversation(
    services: BackendServices,
    *,
    project_path: str,
    parent_session_id: str,
    agent_id: str,
) -> ConversationDetailResponse | None:
    """Return one subagent conversation, including Claude live subagent files."""
    conversation = get_conversation(
        services,
        project_path=project_path,
        session_id=agent_id,
    )
    if conversation is not None or project_path.startswith("codex:"):
        return conversation
    return _get_claude_live_subagent_conversation(
        services,
        project_path=project_path,
        parent_session_id=parent_session_id,
        session_id=agent_id,
    )


def list_conversation_dags(
    services: BackendServices,
    *,
    project: str | None = None,
    days: int | None = None,
    provider: ConversationDagProviderParam | None = None,
) -> list[ConversationDagSummaryResponse]:
    """Return main conversations with backend-built sub-agent DAG summaries."""
    provider_filter = None if provider in {None, "all"} else provider
    summaries = list_conversations(services, project=project, days=days)
    dag_summaries: list[ConversationDagSummaryResponse] = []

    for summary in summaries:
        if summary.thread_type != "main" or summary.subagent_count == 0:
            continue
        if provider_filter is not None and _provider_for_project_path(summary.project_path) != provider_filter:
            continue
        dag = get_conversation_dag(
            services,
            project_path=summary.project_path,
            session_id=summary.session_id,
        )
        if dag is None:
            continue
        dag_summaries.append(
            ConversationDagSummaryResponse(
                **summary.model_dump(),
                dag=dag.stats,
            )
        )

    return dag_summaries


def get_conversation_dag(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
) -> ConversationDagResponse | None:
    """Return the backend-owned DAG for one main or subagent conversation tree."""
    cache: dict[tuple[str, str | None, str], ConversationDetailResponse | None] = {}

    def load_conversation(child_session_id: str, parent_session_id: str | None) -> ConversationDetailResponse | None:
        cache_key = (project_path, parent_session_id, child_session_id)
        if cache_key not in cache:
            cache[cache_key] = _load_conversation_for_dag(
                services,
                project_path=project_path,
                session_id=child_session_id,
                parent_session_id=parent_session_id,
            )
        return cache[cache_key]

    return build_conversation_dag(
        project_path=project_path,
        root_session_id=session_id,
        load_conversation=load_conversation,
    )


def list_projects(services: BackendServices) -> list[ProjectResponse]:
    """Return aggregated project rows derived from merged conversation summaries."""
    projects: dict[str, ProjectResponse] = {}
    for summary in list_conversations(services):
        existing = projects.get(summary.project_path)
        if existing is None:
            projects[summary.project_path] = ProjectResponse(
                encoded_path=summary.project_path,
                display_name=_project_display_name(summary.project_path),
                full_path=_project_full_path(services, summary.project_path),
                session_count=1,
                last_activity=summary.last_updated_at,
            )
            continue
        existing.session_count += 1
        if summary.last_updated_at > existing.last_activity:
            existing.last_activity = summary.last_updated_at

    return sorted(
        projects.values(),
        key=lambda item: (-item.last_activity, item.display_name.lower()),
    )


def list_history(
    services: BackendServices,
    *,
    limit: int,
) -> list[HistoryEntryResponse]:
    """Return merged Claude and Codex history entries."""
    entries = [
        HistoryEntryResponse(
            display=item.display,
            pasted_contents=item.pasted_contents,
            timestamp=float(item.timestamp),
            project=item.project,
        )
        for item in services.claude_history_reader.read_history(limit=limit)
    ]
    entries.extend(
        HistoryEntryResponse(
            display=item.display,
            timestamp=float(item.timestamp),
            project=item.project,
        )
        for item in services.codex_store.read_history(limit=limit)
    )
    entries.sort(key=lambda item: item.timestamp, reverse=True)
    return entries[:limit]


def get_tasks(
    services: BackendServices,
    *,
    session_id: str,
) -> TaskListResponse:
    """Return task payloads for a session from persisted storage or Claude artifacts."""
    tasks = services.app_sqlite_store.get_historical_tasks_for_session(session_id)
    if tasks is None:
        tasks = services.claude_task_reader.read_tasks(session_id)
    return TaskListResponse(session_id=session_id, tasks=tasks or [])


def _provider_for_project_path(project_path: str) -> str:
    return "codex" if project_path.startswith("codex:") else "claude"


def _load_conversation_for_dag(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
    parent_session_id: str | None,
) -> ConversationDetailResponse | None:
    conversation = get_conversation(
        services,
        project_path=project_path,
        session_id=session_id,
    )
    if conversation is not None:
        return conversation
    if project_path.startswith("codex:") or parent_session_id is None:
        return None
    return _get_claude_live_subagent_conversation(
        services,
        project_path=project_path,
        parent_session_id=parent_session_id,
        session_id=session_id,
    )


def _merge_summary(
    summaries_by_key: dict[tuple[str, str], ConversationSummaryResponse],
    candidate: ConversationSummaryResponse,
) -> None:
    provider = "codex" if candidate.project_path.startswith("codex:") else "claude"
    key = (provider, candidate.session_id)
    existing = summaries_by_key.get(key)
    if existing is None:
        summaries_by_key[key] = candidate
        return
    if candidate.is_running and not existing.is_running:
        summaries_by_key[key] = candidate
        return
    if candidate.last_updated_at >= existing.last_updated_at:
        summaries_by_key[key] = candidate


def _shape_historical_summary(summary: HistoricalConversationSummary) -> ConversationSummaryResponse:
    created_at = _to_epoch_ms(summary.started_at)
    last_updated_at = _to_epoch_ms(summary.ended_at)
    return ConversationSummaryResponse(
        session_id=summary.session_id,
        project_path=summary.project_path,
        project_name=summary.project_name,
        thread_type=summary.thread_type if summary.thread_type in {"main", "subagent"} else "main",
        first_message=summary.first_message,
        timestamp=created_at,
        created_at=created_at,
        last_updated_at=last_updated_at,
        is_running=False,
        message_count=summary.message_count,
        model=summary.model,
        total_input_tokens=summary.total_input_tokens,
        total_output_tokens=summary.total_output_tokens,
        total_cache_creation_tokens=summary.total_cache_write_tokens,
        total_cache_read_tokens=summary.total_cache_read_tokens,
        tool_use_count=summary.tool_use_count,
        failed_tool_call_count=summary.failed_tool_call_count,
        tool_breakdown=dict(summary.tool_breakdown),
        subagent_count=summary.subagent_count,
        subagent_type_breakdown=dict(summary.subagent_type_breakdown),
        task_count=summary.task_count,
        git_branch=summary.git_branch,
        reasoning_effort=summary.reasoning_effort,
        speed=summary.speed,
        total_reasoning_tokens=summary.total_reasoning_tokens or None,
    )


def _shape_historical_detail(record: HistoricalConversationRecord) -> ConversationDetailResponse:
    created_at = _to_epoch_ms(record.started_at)
    last_updated_at = _to_epoch_ms(record.ended_at)
    messages = [_shape_historical_message(message) for message in record.messages]
    total_usage = ConversationUsageResponse(
        input_tokens=record.total_input_tokens,
        output_tokens=record.total_output_tokens,
        cache_creation_tokens=record.total_cache_write_tokens,
        cache_read_tokens=record.total_cache_read_tokens,
    )
    context_steps = [
        ConversationContextStepResponse(
            message_id=step.message_id,
            index=step.ordinal,
            role=step.role,
            label=step.label,
            category=_normalize_context_category(step.category),
            timestamp=_to_epoch_ms(step.timestamp),
            input_tokens=step.input_tokens,
            output_tokens=step.output_tokens,
            cache_write_tokens=step.cache_write_tokens,
            cache_read_tokens=step.cache_read_tokens,
            total_tokens=step.total_tokens,
        )
        for step in record.context_steps
    ]
    peak_context_window = max(
        (
            step.input_tokens + step.cache_write_tokens + step.cache_read_tokens
            for step in record.context_steps
        ),
        default=0,
    )
    return ConversationDetailResponse(
        session_id=record.session_id,
        project_path=record.project_path,
        thread_type=record.thread_type if record.thread_type in {"main", "subagent"} else "main",
        created_at=created_at,
        last_updated_at=last_updated_at,
        is_running=False,
        messages=messages,
        plans=[
            ConversationPlanResponse(
                id=plan.plan_id,
                slug=plan.slug,
                title=plan.title,
                preview=plan.preview,
                content=plan.content,
                provider="codex" if plan.provider == "codex" else "claude",
                timestamp=_to_epoch_ms(plan.timestamp),
                model=plan.model,
                explanation=plan.explanation,
                steps=_shape_plan_steps(plan.steps),
            )
            for plan in record.plans
        ],
        total_usage=total_usage,
        model=record.model,
        git_branch=record.git_branch,
        start_time=created_at,
        end_time=last_updated_at,
        subagents=[
            ConversationSubagentResponse(
                agent_id=subagent.agent_id,
                description=subagent.description,
                subagent_type=subagent.subagent_type,
                nickname=subagent.nickname,
                has_file=subagent.has_file,
                project_path=record.project_path,
                session_id=record.session_id,
            )
            for subagent in record.subagents
        ],
        context_analytics=ConversationContextAnalyticsResponse(
            buckets=[
                ConversationContextBucketResponse(
                    label=bucket.label,
                    category=_normalize_context_category(bucket.category),
                    input_tokens=bucket.input_tokens,
                    output_tokens=bucket.output_tokens,
                    cache_write_tokens=bucket.cache_write_tokens,
                    cache_read_tokens=bucket.cache_read_tokens,
                    total_tokens=bucket.total_tokens,
                    calls=bucket.calls,
                )
                for bucket in record.context_buckets
            ],
            steps=context_steps,
        ),
        context_window=ConversationContextWindowResponse(
            peak_context_window=peak_context_window,
            api_calls=len(record.context_steps),
            cumulative_tokens=(
                total_usage.input_tokens
                + total_usage.output_tokens
                + total_usage.cache_creation_tokens
                + total_usage.cache_read_tokens
            ),
        ),
        reasoning_effort=record.reasoning_effort,
        speed=record.speed,
        total_reasoning_tokens=record.total_reasoning_tokens or None,
    )


def _shape_historical_message(message: HistoricalConversationMessage) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id=message.message_id,
        role=message.role,
        timestamp=_to_epoch_ms(message.timestamp),
        blocks=[_shape_historical_block(block) for block in message.blocks],
        usage=ConversationUsageResponse(
            input_tokens=message.input_tokens,
            output_tokens=message.output_tokens,
            cache_creation_tokens=message.cache_write_tokens,
            cache_read_tokens=message.cache_read_tokens,
        ),
        model=message.model,
        reasoning_tokens=message.reasoning_tokens or None,
        speed=message.speed,
    )


def _shape_historical_block(block: HistoricalMessageBlock) -> ConversationMessageBlockResponse:
    block_type = block.block_type if block.block_type in {"text", "thinking", "tool_call"} else "text"
    input_payload = _parse_json_object(block.tool_input_json)
    return ConversationMessageBlockResponse(
        type=block_type,
        text=block.text_content if block_type == "text" else None,
        thinking=block.text_content if block_type == "thinking" else None,
        char_count=len(block.text_content) if block_type == "thinking" and block.text_content else None,
        tool_use_id=block.tool_use_id,
        tool_name=block.tool_name,
        input=input_payload,
        result=block.tool_result_text,
        is_error=block.is_error if block_type == "tool_call" else None,
    )


def _list_claude_live_summaries(
    services: BackendServices,
    *,
    project: str | None,
    days: int | None,
) -> list[ConversationSummaryResponse]:
    cutoff_ms = _cutoff_ms(days)
    summaries: list[ConversationSummaryResponse] = []
    for project_dir in services.claude_conversation_reader.list_projects():
        if project is not None and project_dir.dir_name != project:
            continue
        for session in services.claude_conversation_reader.list_sessions(project_dir.dir_name):
            if cutoff_ms and session.modified_at * 1000 < cutoff_ms:
                continue
            events = services.claude_conversation_reader.read_session_events(
                project_dir.dir_name,
                session.session_id,
            )
            if not events:
                continue
            summary = _summarize_claude_session(
                services,
                events=events,
                project_path=project_dir.dir_name,
                session_id=session.session_id,
                source_path=session.path,
                modified_at_ms=session.modified_at * 1000,
            )
            if summary is None:
                continue
            if cutoff_ms and summary.last_updated_at < cutoff_ms:
                continue
            summaries.append(summary)
    return summaries


def _summarize_claude_session(
    services: BackendServices,
    *,
    events: list[RawConversationEvent],
    project_path: str,
    session_id: str,
    source_path: str,
    modified_at_ms: float,
) -> ConversationSummaryResponse | None:
    first_message = ""
    message_count = 0
    model: str | None = None
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation_tokens = 0
    total_cache_read_tokens = 0
    tool_use_count = 0
    failed_tool_call_count = 0
    tool_breakdown: dict[str, int] = {}
    subagent_type_breakdown: dict[str, int] = {}
    created_at = 0.0
    end_timestamp = 0.0
    git_branch: str | None = None
    speed: str | None = None

    for event in events:
        if event.type == "file-history-snapshot":
            continue
        ts = _to_epoch_ms(event.timestamp)
        if ts:
            if not created_at or ts < created_at:
                created_at = ts
            if ts > end_timestamp:
                end_timestamp = ts
        if git_branch is None and event.git_branch:
            git_branch = event.git_branch
        message = _event_message(event)
        if event.type == "user" and message.get("role") == "user":
            message_count += 1
            if not first_message:
                first_message = _first_user_message_text(message)[:200]
            for block in _message_content_list(message):
                if _block_type(block) == "tool_result" and bool(block.get("is_error")):
                    failed_tool_call_count += 1
        elif event.type == "assistant" and message.get("role") == "assistant":
            message_count += 1
            if model is None and isinstance(message.get("model"), str):
                model = message["model"]
            usage = _usage_from_message(message)
            total_input_tokens += usage.input_tokens
            total_output_tokens += usage.output_tokens
            total_cache_creation_tokens += usage.cache_creation_tokens
            total_cache_read_tokens += usage.cache_read_tokens
            if speed is None and usage.speed:
                speed = usage.speed
            for block in _message_content_list(message):
                if _block_type(block) != "tool_use":
                    continue
                tool_use_count += 1
                tool_name = _string_or_none(block.get("name")) or "unknown"
                tool_breakdown[tool_name] = tool_breakdown.get(tool_name, 0) + 1
                if tool_name == "Task":
                    subagent_type = _string_or_none(_dict_or_none(block.get("input")).get("subagent_type"))
                    subagent_key = subagent_type or "unknown"
                    subagent_type_breakdown[subagent_key] = subagent_type_breakdown.get(subagent_key, 0) + 1

    if not created_at and not end_timestamp and not first_message and message_count == 0:
        return None

    last_updated_at = max(end_timestamp, modified_at_ms)
    return ConversationSummaryResponse(
        session_id=session_id,
        project_path=project_path,
        project_name=_project_display_name(project_path),
        thread_type="main",
        first_message=first_message,
        timestamp=created_at,
        created_at=created_at,
        last_updated_at=last_updated_at,
        is_running=_is_likely_active(last_updated_at),
        message_count=message_count,
        model=model,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cache_creation_tokens=total_cache_creation_tokens,
        total_cache_read_tokens=total_cache_read_tokens,
        tool_use_count=tool_use_count,
        failed_tool_call_count=failed_tool_call_count,
        tool_breakdown=tool_breakdown,
        subagent_count=sum(subagent_type_breakdown.values()),
        subagent_type_breakdown=subagent_type_breakdown,
        task_count=len(services.claude_task_reader.read_tasks(session_id)),
        git_branch=git_branch,
        speed=speed,
    )


def _get_claude_live_conversation(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
) -> ConversationDetailResponse | None:
    events = services.claude_conversation_reader.read_session_events(project_path, session_id)
    if not events:
        return None
    return _shape_claude_live_conversation_detail(
        services,
        project_path=project_path,
        session_id=session_id,
        events=events,
        modified_at_ms=_claude_session_modified_at_ms(services, project_path=project_path, session_id=session_id),
        thread_type="main",
    )


def _get_claude_live_subagent_conversation(
    services: BackendServices,
    *,
    project_path: str,
    parent_session_id: str,
    session_id: str,
) -> ConversationDetailResponse | None:
    events, modified_at_ms = _read_claude_subagent_events(
        services,
        project_path=project_path,
        parent_session_id=parent_session_id,
        session_id=session_id,
    )
    if not events:
        return None
    return _shape_claude_live_conversation_detail(
        services,
        project_path=project_path,
        session_id=session_id,
        events=events,
        modified_at_ms=modified_at_ms,
        thread_type="subagent",
    )


def _shape_claude_live_conversation_detail(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
    events: list[RawConversationEvent],
    modified_at_ms: float,
    thread_type: str,
) -> ConversationDetailResponse:
    messages: list[ConversationMessageResponse] = []
    pending_tool_calls: dict[str, ConversationMessageBlockResponse] = {}
    total_usage = _UsageTotals()
    bucket_totals: dict[str, _BucketTotals] = {}
    context_steps: list[ConversationContextStepResponse] = []
    plans = _extract_claude_plans(events, session_id=session_id, project_path=project_path)
    model: str | None = None
    git_branch: str | None = None
    speed: str | None = None
    created_at = 0.0
    end_time = 0.0
    next_step_index = 0

    for event in events:
        if event.type in {"file-history-snapshot", "progress"}:
            continue
        ts = _to_epoch_ms(event.timestamp)
        if ts:
            if not created_at or ts < created_at:
                created_at = ts
            if ts > end_time:
                end_time = ts
        if git_branch is None and event.git_branch:
            git_branch = event.git_branch

        message = _event_message(event)
        if event.type == "user" and message.get("role") == "user":
            user_blocks: list[ConversationMessageBlockResponse] = []
            for block in _message_content_list(message):
                block_type = _block_type(block)
                if block_type == "tool_result":
                    tool_use_id = _string_or_none(block.get("tool_use_id"))
                    pending = pending_tool_calls.get(tool_use_id or "")
                    if pending is not None:
                        pending.result = _tool_result_text(block.get("content"))[:_MAX_RESULT_LENGTH]
                        pending.is_error = bool(block.get("is_error"))
                    continue
                if block_type == "text":
                    text = _string_or_none(block.get("text"))
                    if text:
                        user_blocks.append(ConversationMessageBlockResponse(type="text", text=text))
            if not user_blocks:
                text = _string_or_none(message.get("content"))
                if text:
                    user_blocks.append(ConversationMessageBlockResponse(type="text", text=text))
            if user_blocks:
                messages.append(
                    ConversationMessageResponse(
                        id=event.uuid or f"user-{len(messages)}",
                        role="user",
                        timestamp=ts,
                        blocks=user_blocks,
                    )
                )
            continue

        if event.type != "assistant" or message.get("role") != "assistant":
            continue

        if model is None and isinstance(message.get("model"), str):
            model = message["model"]
        usage = _usage_from_message(message)
        total_usage.add(usage)
        if speed is None and usage.speed:
            speed = usage.speed

        blocks: list[ConversationMessageBlockResponse] = []
        tool_names: list[str] = []
        has_thinking = False
        for block in _message_content_list(message):
            block_type = _block_type(block)
            if block_type == "text":
                text = _string_or_none(block.get("text"))
                if text:
                    blocks.append(ConversationMessageBlockResponse(type="text", text=text))
            elif block_type == "thinking":
                thinking = _string_or_none(block.get("thinking"))
                if thinking:
                    has_thinking = True
                    blocks.append(
                        ConversationMessageBlockResponse(
                            type="thinking",
                            thinking=thinking,
                            char_count=len(thinking),
                        )
                    )
            elif block_type == "tool_use":
                tool_name = _string_or_none(block.get("name")) or "unknown"
                tool_call = ConversationMessageBlockResponse(
                    type="tool_call",
                    tool_use_id=_string_or_none(block.get("id")),
                    tool_name=tool_name,
                    input=_dict_or_none(block.get("input")),
                )
                blocks.append(tool_call)
                if tool_call.tool_use_id:
                    pending_tool_calls[tool_call.tool_use_id] = tool_call
                tool_names.append(tool_name)

        if not blocks:
            continue

        message_id = event.uuid or f"assistant-{len(messages)}"
        messages.append(
            ConversationMessageResponse(
                id=message_id,
                role="assistant",
                timestamp=ts,
                blocks=blocks,
                usage=usage.response(),
                model=_string_or_none(message.get("model")),
                speed=usage.speed,
            )
        )

        if usage.total_tokens == 0:
            continue
        if tool_names:
            per_tool = usage.split(len(tool_names))
            for tool_name in tool_names:
                _add_bucket(bucket_totals, label=tool_name, category=_tool_category(tool_name), usage=per_tool)
            label = ", ".join(tool_names)
            category = (
                "mcp"
                if any(name.startswith("mcp__") for name in tool_names)
                else ("subagent" if "Task" in tool_names else "tool")
            )
        elif has_thinking:
            _add_bucket(bucket_totals, label="Thinking", category="thinking", usage=usage)
            label = "Thinking + text"
            category = "thinking"
        else:
            _add_bucket(bucket_totals, label="Conversation", category="conversation", usage=usage)
            label = "Text response"
            category = "conversation"
        context_steps.append(
            ConversationContextStepResponse(
                message_id=message_id,
                index=next_step_index,
                role="assistant",
                label=label,
                category=category,
                timestamp=ts,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_write_tokens=usage.cache_creation_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                total_tokens=usage.total_tokens,
            )
        )
        next_step_index += 1

    last_updated_at = max(end_time, modified_at_ms)
    peak_context_window = max(
        (
            step.input_tokens + step.cache_write_tokens + step.cache_read_tokens
            for step in context_steps
        ),
        default=0,
    )
    return ConversationDetailResponse(
        session_id=session_id,
        project_path=project_path,
        thread_type=thread_type if thread_type in {"main", "subagent"} else "main",
        created_at=created_at,
        last_updated_at=last_updated_at,
        is_running=_is_likely_active(last_updated_at),
        messages=messages,
        plans=plans,
        total_usage=total_usage.response(),
        model=model,
        git_branch=git_branch,
        start_time=created_at,
        end_time=end_time,
        subagents=_discover_claude_subagents(
            services,
            project_path=project_path,
            session_id=session_id,
            events=events,
        ),
        context_analytics=ConversationContextAnalyticsResponse(
            buckets=_sorted_buckets(bucket_totals),
            steps=context_steps,
        ),
        context_window=ConversationContextWindowResponse(
            peak_context_window=peak_context_window,
            api_calls=len(context_steps),
            cumulative_tokens=total_usage.total_tokens,
        ),
        speed=speed,
    )


def _discover_claude_subagents(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
    events: list[RawConversationEvent],
) -> list[ConversationSubagentResponse]:
    existing_files = set(_list_claude_subagent_ids(services, project_path=project_path, session_id=session_id))
    pending_meta: dict[str, dict[str, str | None]] = {}
    discovered_meta: dict[str, dict[str, str | None]] = {}

    for event in events:
        message = _event_message(event)
        if event.type == "assistant" and message.get("role") == "assistant":
            for block in _message_content_list(message):
                if _block_type(block) != "tool_use" or _string_or_none(block.get("name")) != "Task":
                    continue
                pending_meta[_string_or_none(block.get("id")) or ""] = {
                    "description": _string_or_none(_dict_or_none(block.get("input")).get("description")),
                    "subagent_type": _string_or_none(_dict_or_none(block.get("input")).get("subagent_type")),
                    "nickname": None,
                }
        elif event.type == "user" and message.get("role") == "user":
            for block in _message_content_list(message):
                if _block_type(block) != "tool_result":
                    continue
                spawn = _parse_claude_subagent_tool_result(block.get("content"))
                agent_id = spawn["agent_id"]
                if not agent_id:
                    continue
                meta = pending_meta.pop(_string_or_none(block.get("tool_use_id")) or "", None) or {}
                discovered_meta[agent_id] = {
                    "description": _string_or_none(meta.get("description")) or spawn["description"],
                    "subagent_type": _string_or_none(meta.get("subagent_type")),
                    "nickname": spawn["nickname"],
                }

    subagents: list[ConversationSubagentResponse] = []
    for agent_id in sorted(existing_files | set(discovered_meta)):
        meta = discovered_meta.get(agent_id, {})
        subagents.append(
            ConversationSubagentResponse(
                agent_id=agent_id,
                description=_string_or_none(meta.get("description")),
                subagent_type=_string_or_none(meta.get("subagent_type")),
                nickname=_string_or_none(meta.get("nickname")),
                has_file=agent_id in existing_files,
                project_path=project_path,
                session_id=session_id,
            )
        )
    return subagents


def _list_claude_subagent_ids(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
) -> list[str]:
    directory = services.settings.claude_projects_dir / project_path / session_id / "subagents"
    if not directory.is_dir():
        return []
    agent_ids: list[str] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or not path.name.startswith("agent-") or path.suffix != ".jsonl":
            continue
        agent_ids.append(path.stem.removeprefix("agent-"))
    return agent_ids


def _read_claude_subagent_events(
    services: BackendServices,
    *,
    project_path: str,
    parent_session_id: str,
    session_id: str,
) -> tuple[list[RawConversationEvent], float]:
    path = _claude_subagent_file_path(
        services,
        project_path=project_path,
        parent_session_id=parent_session_id,
        session_id=session_id,
    )
    if not path.is_file():
        return [], 0.0
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        modified_at_ms = path.stat().st_mtime * 1000
    except OSError:
        return [], 0.0
    return _parse_claude_raw_events(content), modified_at_ms


def _claude_session_modified_at_ms(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
) -> float:
    path = services.settings.claude_projects_dir / project_path / f"{session_id}.jsonl"
    if not path.is_file():
        return 0.0
    try:
        return path.stat().st_mtime * 1000
    except OSError:
        return 0.0


def _claude_subagent_file_path(
    services: BackendServices,
    *,
    project_path: str,
    parent_session_id: str,
    session_id: str,
) -> Path:
    return (
        services.settings.claude_projects_dir
        / project_path
        / parent_session_id
        / "subagents"
        / f"agent-{session_id}.jsonl"
    )


def _parse_claude_raw_events(content: str) -> list[RawConversationEvent]:
    events: list[RawConversationEvent] = []
    for raw in _parse_jsonl_objects(content):
        try:
            events.append(RawConversationEvent.model_validate(_normalize_claude_event_keys(raw)))
        except Exception:  # noqa: BLE001
            continue
    return events


def _normalize_claude_event_keys(raw: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "parentUuid": "parent_uuid",
        "sessionId": "session_id",
        "gitBranch": "git_branch",
        "planContent": "plan_content",
    }
    return {mapping.get(key, key): value for key, value in raw.items()}


def _parse_claude_subagent_tool_result(content: Any) -> dict[str, str | None]:
    text = _tool_result_text(content)
    if not text:
        return {"agent_id": None, "description": None, "nickname": None}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"agent_id": None, "description": None, "nickname": None}
    if not isinstance(parsed, dict):
        return {"agent_id": None, "description": None, "nickname": None}
    return {
        "agent_id": _string_or_none(parsed.get("agentId") or parsed.get("agent_id") or parsed.get("id")),
        "description": _string_or_none(parsed.get("description")),
        "nickname": _string_or_none(parsed.get("nickname")),
    }


def _extract_claude_plans(
    events: list[RawConversationEvent],
    *,
    session_id: str,
    project_path: str,
) -> list[ConversationPlanResponse]:
    plans: list[ConversationPlanResponse] = []
    latest_model: str | None = None
    for event in events:
        message = _event_message(event)
        if event.type == "assistant" and message.get("role") == "assistant":
            latest_model = _string_or_none(message.get("model")) or latest_model
        if not isinstance(event.plan_content, str) or not event.plan_content.strip():
            continue
        plan_meta = _summarize_plan_content(event.plan_content, event.slug or session_id)
        event_id = event.uuid.strip() or session_id
        plans.append(
            ConversationPlanResponse(
                id=_encode_plan_id(
                    {
                        "kind": "claude-session",
                        "projectPath": project_path,
                        "sessionId": session_id,
                        "eventId": event_id,
                    }
                ),
                slug=plan_meta["slug"],
                title=plan_meta["title"],
                preview=plan_meta["preview"],
                content=event.plan_content,
                provider="claude",
                timestamp=_to_epoch_ms(event.timestamp),
                model=latest_model,
                session_id=session_id,
                project_path=project_path,
            )
        )
    return sorted(plans, key=lambda item: item.timestamp, reverse=True)


def _list_codex_live_summaries(
    services: BackendServices,
    *,
    project: str | None,
    days: int | None,
) -> list[ConversationSummaryResponse]:
    cutoff_ms = _cutoff_ms(days)
    thread_by_id = _codex_threads_by_id(services)
    summaries: list[ConversationSummaryResponse] = []
    metadata_by_session: dict[str, tuple[str | None, str | None]] = {}

    for artifact in _codex_session_artifacts(services):
        if cutoff_ms and artifact.modified_at * 1000 < cutoff_ms:
            continue
        thread = thread_by_id.get(artifact.session_id)
        summary, parent_thread_id, agent_role = _summarize_codex_artifact(
            artifact,
            thread=thread,
        )
        if summary is None:
            continue
        if project is not None and summary.project_path != project:
            continue
        if cutoff_ms and summary.last_updated_at < cutoff_ms:
            continue
        summaries.append(summary)
        metadata_by_session[summary.session_id] = (parent_thread_id, agent_role)

    child_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for session_id, (parent_thread_id, agent_role) in metadata_by_session.items():
        if not parent_thread_id:
            continue
        child_groups[parent_thread_id][agent_role or "default"] += 1

    merged: list[ConversationSummaryResponse] = []
    for summary in summaries:
        if summary.thread_type == "subagent":
            merged.append(summary)
            continue
        child_group = child_groups.get(summary.session_id)
        if not child_group:
            merged.append(summary)
            continue
        updated = summary.model_copy(deep=True)
        updated.subagent_count = sum(child_group.values())
        if not updated.subagent_type_breakdown:
            updated.subagent_type_breakdown = dict(child_group)
        merged.append(updated)

    return merged


def _summarize_codex_artifact(
    artifact: CodexSessionArtifact,
    *,
    thread: CodexThreadRecord | None,
) -> tuple[ConversationSummaryResponse | None, str | None, str | None]:
    lines = _parse_jsonl_objects(artifact.content)
    if not lines:
        return None, None, None

    session_id = artifact.session_id
    first_message = ""
    message_count = 0
    model = "gpt-5"
    cwd = thread.cwd or ""
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_read_tokens = 0
    total_reasoning_tokens = 0
    reasoning_effort: str | None = None
    tool_use_count = 0
    failed_tool_call_count = 0
    tool_breakdown: dict[str, int] = {}
    subagent_count = 0
    subagent_type_breakdown: dict[str, int] = {}
    parent_thread_id: str | None = _parse_parent_thread_id(thread.source if thread else None)
    agent_role: str | None = thread.agent_role if thread else None
    timestamp = 0.0
    end_timestamp = 0.0
    pending_spawn_calls: dict[str, str | None] = {}

    for line in lines:
        ts = _to_epoch_ms(line.get("timestamp"))
        if ts:
            if not timestamp or ts < timestamp:
                timestamp = ts
            if ts > end_timestamp:
                end_timestamp = ts

        line_type = _string_or_none(line.get("type"))
        payload = _dict_or_none(line.get("payload"))
        if line_type == "session_meta":
            session_id = _string_or_none(payload.get("id")) or session_id
            cwd = _string_or_none(payload.get("cwd")) or cwd
            source = payload.get("source")
            if isinstance(source, dict):
                parent_thread_id = _string_or_none(
                    _dict_or_none(_dict_or_none(source.get("subagent")).get("thread_spawn")).get("parent_thread_id")
                ) or parent_thread_id
            agent_role = _string_or_none(payload.get("agent_role")) or agent_role
        elif line_type == "turn_context":
            model = _string_or_none(payload.get("model")) or model
            reasoning_effort = _string_or_none(payload.get("reasoning_effort")) or reasoning_effort
        elif line_type == "response_item":
            item_type = _string_or_none(payload.get("type"))
            if item_type == "message":
                role = _string_or_none(payload.get("role"))
                if role in {"user", "assistant"}:
                    message_count += 1
                if role == "user" and not first_message:
                    first_message = _first_codex_user_message(payload)[:200]
            elif item_type == "function_call":
                tool_use_count += 1
                tool_name = _codex_tool_display_name(_string_or_none(payload.get("name")) or "unknown")
                tool_breakdown[tool_name] = tool_breakdown.get(tool_name, 0) + 1
                if _string_or_none(payload.get("name")) == "spawn_agent":
                    pending_spawn_calls[_string_or_none(payload.get("call_id")) or ""] = _spawn_agent_type(
                        _parse_json_string_object(payload.get("arguments"))
                    )
            elif item_type == "custom_tool_call":
                tool_use_count += 1
                tool_name = _codex_tool_display_name(_string_or_none(payload.get("name")) or "unknown")
                tool_breakdown[tool_name] = tool_breakdown.get(tool_name, 0) + 1
            elif item_type == "web_search_call":
                tool_use_count += 1
                tool_name = _codex_tool_display_name("web_search_call")
                tool_breakdown[tool_name] = tool_breakdown.get(tool_name, 0) + 1
            elif item_type == "function_call_output":
                output = _string_or_none(payload.get("output")) or ""
                if _codex_output_is_error(output):
                    failed_tool_call_count += 1
                call_id = _string_or_none(payload.get("call_id")) or ""
                if call_id in pending_spawn_calls:
                    spawn = _parse_spawn_agent_output(output)
                    if spawn["agent_id"]:
                        subagent_count += 1
                        key = pending_spawn_calls[call_id] or "default"
                        subagent_type_breakdown[key] = subagent_type_breakdown.get(key, 0) + 1
                    pending_spawn_calls.pop(call_id, None)
            elif item_type == "custom_tool_call_output":
                output = _string_or_none(payload.get("output")) or ""
                if '"exit_code":' in output and '"exit_code":0' not in output:
                    failed_tool_call_count += 1
        elif line_type == "event_msg" and _string_or_none(payload.get("type")) == "token_count":
            info = _dict_or_none(payload.get("info"))
            total_usage = _dict_or_none(info.get("total_token_usage"))
            total_input_tokens = _int_value(total_usage.get("input_tokens"))
            total_output_tokens = _int_value(total_usage.get("output_tokens"))
            total_cache_read_tokens = _int_value(total_usage.get("cached_input_tokens"))
            total_reasoning_tokens = _int_value(total_usage.get("reasoning_output_tokens"))

    if not cwd:
        cwd = "unknown"
    project_path = f"codex:{_cwd_to_project_path(cwd)}"
    project_name = _cwd_to_display_name(cwd)
    last_updated_at = max(
        end_timestamp,
        artifact.modified_at * 1000,
        float((thread.updated_at or 0) * 1000 if thread and thread.updated_at else 0),
    )
    summary = ConversationSummaryResponse(
        session_id=session_id,
        project_path=project_path,
        project_name=project_name,
        thread_type="subagent" if parent_thread_id else "main",
        first_message=(thread.first_user_message or first_message or "")[:200],
        timestamp=timestamp,
        created_at=timestamp,
        last_updated_at=last_updated_at,
        is_running=_is_likely_active(last_updated_at),
        message_count=message_count,
        model=model,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cache_creation_tokens=0,
        total_cache_read_tokens=total_cache_read_tokens,
        tool_use_count=tool_use_count,
        failed_tool_call_count=failed_tool_call_count,
        tool_breakdown=tool_breakdown,
        subagent_count=subagent_count,
        subagent_type_breakdown=subagent_type_breakdown,
        task_count=0,
        git_branch=thread.git_branch if thread else None,
        reasoning_effort=reasoning_effort,
        total_reasoning_tokens=total_reasoning_tokens or None,
    )
    return summary, parent_thread_id, agent_role


def _get_codex_live_conversation(
    services: BackendServices,
    *,
    session_id: str,
    project_path: str,
) -> ConversationDetailResponse | None:
    artifact = next((item for item in _codex_session_artifacts(services) if item.session_id == session_id), None)
    if artifact is None:
        return None

    lines = _parse_jsonl_objects(artifact.content)
    if not lines:
        return None

    thread_by_id = _codex_threads_by_id(services)
    thread = thread_by_id.get(session_id)
    messages: list[ConversationMessageResponse] = []
    pending_tool_calls: dict[str, ConversationMessageBlockResponse] = {}
    pending_blocks: list[ConversationMessageBlockResponse] = []
    pending_tool_names: list[str] = []
    total_usage = _UsageTotals()
    bucket_totals: dict[str, _BucketTotals] = {}
    context_steps: list[ConversationContextStepResponse] = []
    plans = _extract_codex_plans(lines, session_id=session_id, project_path=project_path)
    subagents = _discover_codex_subagents(lines, session_id=session_id, project_path=project_path, thread_by_id=thread_by_id)
    model: str | None = None
    reasoning_effort: str | None = None
    git_branch = thread.git_branch if thread else None
    created_at = 0.0
    end_time = 0.0
    has_thinking = False
    prev_totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}
    pending_reasoning_tokens = 0
    last_assistant_timestamp = 0.0
    last_assistant_id = ""
    next_index = 0

    def flush_pending_message(step_usage: _UsageTotals | None) -> None:
        nonlocal pending_blocks, pending_tool_names, has_thinking, pending_reasoning_tokens, next_index
        if not pending_blocks:
            return
        message_id = last_assistant_id or f"assistant-{next_index}"
        messages.append(
            ConversationMessageResponse(
                id=message_id,
                role="assistant",
                timestamp=last_assistant_timestamp,
                blocks=list(pending_blocks),
                usage=step_usage.response() if step_usage else None,
                model=model,
                reasoning_tokens=pending_reasoning_tokens or None,
            )
        )
        if step_usage and step_usage.total_tokens:
            if pending_tool_names:
                per_tool = step_usage.split(len(pending_tool_names))
                for tool_name in pending_tool_names:
                    _add_bucket(bucket_totals, label=tool_name, category="tool", usage=per_tool)
                label = ", ".join(pending_tool_names)
                category = "tool"
            elif has_thinking:
                _add_bucket(bucket_totals, label="Thinking", category="thinking", usage=step_usage)
                label = "Thinking + text"
                category = "thinking"
            else:
                _add_bucket(bucket_totals, label="Conversation", category="conversation", usage=step_usage)
                label = "Text response"
                category = "conversation"
            context_steps.append(
                ConversationContextStepResponse(
                    message_id=message_id,
                    index=next_index,
                    role="assistant",
                    label=label,
                    category=category,
                    timestamp=last_assistant_timestamp,
                    input_tokens=step_usage.input_tokens,
                    output_tokens=step_usage.output_tokens,
                    cache_write_tokens=step_usage.cache_creation_tokens,
                    cache_read_tokens=step_usage.cache_read_tokens,
                    total_tokens=step_usage.total_tokens,
                )
            )
        pending_blocks = []
        pending_tool_names = []
        has_thinking = False
        pending_reasoning_tokens = 0
        next_index += 1

    for line in lines:
        ts = _to_epoch_ms(line.get("timestamp"))
        if ts:
            if not created_at or ts < created_at:
                created_at = ts
            if ts > end_time:
                end_time = ts
        line_type = _string_or_none(line.get("type"))
        payload = _dict_or_none(line.get("payload"))

        if line_type == "turn_context":
            model = _string_or_none(payload.get("model")) or model
            reasoning_effort = _string_or_none(payload.get("reasoning_effort")) or reasoning_effort
            continue

        if line_type == "event_msg":
            if _string_or_none(payload.get("type")) != "token_count":
                continue
            info = _dict_or_none(payload.get("info"))
            total_token_usage = _dict_or_none(info.get("total_token_usage"))
            if not total_token_usage:
                continue
            step_usage = _UsageTotals(
                input_tokens=_int_value(total_token_usage.get("input_tokens")) - prev_totals["input_tokens"],
                output_tokens=_int_value(total_token_usage.get("output_tokens")) - prev_totals["output_tokens"],
                cache_read_tokens=(
                    _int_value(total_token_usage.get("cached_input_tokens")) - prev_totals["cached_input_tokens"]
                ),
                cache_creation_tokens=0,
            )
            reasoning_delta = _int_value(total_token_usage.get("reasoning_output_tokens")) - prev_totals["reasoning_output_tokens"]
            if reasoning_delta > 0:
                pending_reasoning_tokens = reasoning_delta
            prev_totals = {
                "input_tokens": _int_value(total_token_usage.get("input_tokens")),
                "cached_input_tokens": _int_value(total_token_usage.get("cached_input_tokens")),
                "output_tokens": _int_value(total_token_usage.get("output_tokens")),
                "reasoning_output_tokens": _int_value(total_token_usage.get("reasoning_output_tokens")),
            }
            flush_pending_message(step_usage)
            continue

        if line_type != "response_item":
            continue

        item_type = _string_or_none(payload.get("type"))
        if item_type == "message":
            role = _string_or_none(payload.get("role"))
            content = payload.get("content")
            if role == "user":
                text_blocks = [
                    ConversationMessageBlockResponse(type="text", text=text)
                    for text in _codex_message_texts(content, input_mode=True)
                ]
                if text_blocks:
                    messages.append(
                        ConversationMessageResponse(
                            id=f"user-{len(messages)}",
                            role="user",
                            timestamp=ts,
                            blocks=text_blocks,
                        )
                    )
            elif role == "assistant":
                for text in _codex_message_texts(content, input_mode=False):
                    pending_blocks.append(ConversationMessageBlockResponse(type="text", text=text))
                last_assistant_timestamp = ts
                last_assistant_id = f"assistant-{next_index}"
            continue

        if item_type == "reasoning":
            for text in _codex_reasoning_texts(payload.get("summary")):
                has_thinking = True
                pending_blocks.append(
                    ConversationMessageBlockResponse(
                        type="thinking",
                        thinking=text,
                        char_count=len(text),
                    )
                )
            continue

        if item_type == "function_call":
            tool_name = _codex_tool_display_name(_string_or_none(payload.get("name")) or "unknown")
            tool_call = ConversationMessageBlockResponse(
                type="tool_call",
                tool_use_id=_string_or_none(payload.get("call_id")),
                tool_name=tool_name,
                input=_parse_json_string_object(payload.get("arguments")),
            )
            pending_blocks.append(tool_call)
            if tool_call.tool_use_id:
                pending_tool_calls[tool_call.tool_use_id] = tool_call
            pending_tool_names.append(tool_name)
            last_assistant_timestamp = ts
            last_assistant_id = f"assistant-{next_index}"
            continue

        if item_type == "function_call_output":
            call_id = _string_or_none(payload.get("call_id")) or ""
            pending = pending_tool_calls.get(call_id)
            if pending is not None:
                output = (_string_or_none(payload.get("output")) or "")[:_MAX_RESULT_LENGTH]
                pending.result = output
                pending.is_error = _codex_output_is_error(output)
            continue

        if item_type == "custom_tool_call":
            tool_name = _codex_tool_display_name(_string_or_none(payload.get("name")) or "unknown")
            tool_call = ConversationMessageBlockResponse(
                type="tool_call",
                tool_use_id=_string_or_none(payload.get("call_id")),
                tool_name=tool_name,
                input={"patch": _string_or_none(payload.get("input")) or ""},
            )
            pending_blocks.append(tool_call)
            if tool_call.tool_use_id:
                pending_tool_calls[tool_call.tool_use_id] = tool_call
            pending_tool_names.append(tool_name)
            last_assistant_timestamp = ts
            last_assistant_id = f"assistant-{next_index}"
            continue

        if item_type == "custom_tool_call_output":
            call_id = _string_or_none(payload.get("call_id")) or ""
            pending = pending_tool_calls.get(call_id)
            if pending is not None:
                raw_output = _string_or_none(payload.get("output")) or ""
                pending.result = _extract_custom_tool_output(raw_output)[:_MAX_RESULT_LENGTH]
                pending.is_error = '"exit_code":' in raw_output and '"exit_code":0' not in raw_output
            continue

        if item_type == "web_search_call":
            action = _dict_or_none(payload.get("action"))
            tool_call = ConversationMessageBlockResponse(
                type="tool_call",
                tool_use_id=f"web-search-{next_index}-{int(ts)}",
                tool_name=_codex_tool_display_name("web_search_call"),
                input=_compact_dict(
                    {
                        "type": _string_or_none(action.get("type")),
                        "query": _string_or_none(action.get("query")),
                        "queries": [item for item in _list_of_strings(action.get("queries")) if item],
                    }
                ),
                result=f"Status: {_string_or_none(payload.get('status'))}" if _string_or_none(payload.get("status")) else None,
            )
            pending_blocks.append(tool_call)
            pending_tool_names.append(tool_call.tool_name or "Web Search")
            last_assistant_timestamp = ts
            last_assistant_id = f"assistant-{next_index}"

    flush_pending_message(None)
    total_usage = _UsageTotals(
        input_tokens=prev_totals["input_tokens"],
        output_tokens=prev_totals["output_tokens"],
        cache_creation_tokens=0,
        cache_read_tokens=prev_totals["cached_input_tokens"],
    )
    peak_context_window = max(
        (
            step.input_tokens + step.cache_write_tokens + step.cache_read_tokens
            for step in context_steps
        ),
        default=0,
    )
    return ConversationDetailResponse(
        session_id=session_id,
        project_path=project_path,
        thread_type="subagent" if _parse_parent_thread_id(thread.source if thread else None) else "main",
        created_at=created_at,
        last_updated_at=max(end_time, artifact.modified_at * 1000, float((thread.updated_at or 0) * 1000 if thread and thread.updated_at else 0)),
        is_running=_is_likely_active(max(end_time, artifact.modified_at * 1000)),
        messages=messages,
        plans=plans,
        total_usage=total_usage.response(),
        model=model,
        git_branch=git_branch,
        start_time=created_at,
        end_time=end_time,
        subagents=subagents,
        context_analytics=ConversationContextAnalyticsResponse(
            buckets=_sorted_buckets(bucket_totals),
            steps=context_steps,
        ),
        context_window=ConversationContextWindowResponse(
            peak_context_window=peak_context_window,
            api_calls=len(context_steps),
            cumulative_tokens=total_usage.total_tokens,
        ),
        reasoning_effort=reasoning_effort,
        total_reasoning_tokens=prev_totals["reasoning_output_tokens"] or None,
    )


def _extract_codex_plans(
    lines: list[dict[str, Any]],
    *,
    session_id: str,
    project_path: str,
) -> list[ConversationPlanResponse]:
    plans: list[ConversationPlanResponse] = []
    latest_model: str | None = None

    for line in lines:
        line_type = _string_or_none(line.get("type"))
        payload = _dict_or_none(line.get("payload"))
        if line_type == "turn_context":
            latest_model = _string_or_none(payload.get("model")) or latest_model
            continue
        if line_type != "response_item":
            continue
        if _string_or_none(payload.get("type")) != "function_call" or _string_or_none(payload.get("name")) != "update_plan":
            continue
        call_id = _string_or_none(payload.get("call_id"))
        if not call_id:
            continue
        args = _parse_json_string_object(payload.get("arguments"))
        explanation = _string_or_none(args.get("explanation"))
        steps = [
            ConversationPlanStepResponse(step=_string_or_none(item.get("step")) or "", status=_string_or_none(item.get("status")) or "")
            for item in _list_of_dicts(args.get("plan"))
            if _string_or_none(item.get("step"))
        ]
        if not explanation and not steps:
            continue
        title = _first_non_empty_line(explanation) or "Codex plan"
        title = _truncate(title, max_length=80)
        slug = f"codex-{_slugify(title)}-{call_id[-8:]}"
        preview_parts = [explanation] if explanation else []
        preview_parts.extend(f"{_checkbox_for_status(step.status)} {step.step}" for step in steps)
        preview = _truncate(" ".join(part for part in preview_parts if part), max_length=240)
        content_lines = [f"# {title}"]
        if explanation:
            content_lines.extend(["", explanation])
        if steps:
            content_lines.append("")
            content_lines.extend(f"- {_checkbox_for_status(step.status)} {step.step}" for step in steps)
        plans.append(
            ConversationPlanResponse(
                id=_encode_plan_id({"kind": "codex-session", "sessionId": session_id, "callId": call_id}),
                slug=slug,
                title=title,
                preview=preview,
                content="\n".join(content_lines).strip(),
                provider="codex",
                timestamp=_to_epoch_ms(line.get("timestamp")),
                model=latest_model,
                session_id=session_id,
                project_path=project_path,
                explanation=explanation,
                steps=steps,
            )
        )
    return sorted(plans, key=lambda item: item.timestamp, reverse=True)


def _discover_codex_subagents(
    lines: list[dict[str, Any]],
    *,
    session_id: str,
    project_path: str,
    thread_by_id: dict[str, CodexThreadRecord],
) -> list[ConversationSubagentResponse]:
    pending_spawn_calls: dict[str, dict[str, str | None]] = {}
    subagents: dict[str, ConversationSubagentResponse] = {}

    for line in lines:
        if _string_or_none(line.get("type")) != "response_item":
            continue
        payload = _dict_or_none(line.get("payload"))
        item_type = _string_or_none(payload.get("type"))
        if item_type == "function_call" and _string_or_none(payload.get("name")) == "spawn_agent":
            args = _parse_json_string_object(payload.get("arguments"))
            pending_spawn_calls[_string_or_none(payload.get("call_id")) or ""] = {
                "description": _summarize_spawn_agent_message(args),
                "subagent_type": _spawn_agent_type(args),
            }
            continue
        if item_type != "function_call_output":
            continue
        call_id = _string_or_none(payload.get("call_id")) or ""
        pending = pending_spawn_calls.pop(call_id, None)
        if pending is None:
            continue
        spawn = _parse_spawn_agent_output(payload.get("output"))
        agent_id = spawn["agent_id"]
        if not agent_id:
            continue
        thread = thread_by_id.get(agent_id)
        subagents[agent_id] = ConversationSubagentResponse(
            agent_id=agent_id,
            description=pending["description"],
            subagent_type=thread.agent_role if thread else pending["subagent_type"],
            nickname=thread.agent_nickname if thread else spawn["nickname"],
            has_file=agent_id in thread_by_id,
            project_path=project_path,
            session_id=session_id,
        )

    for agent_id, thread in thread_by_id.items():
        if _parse_parent_thread_id(thread.source) != session_id:
            continue
        existing = subagents.get(agent_id)
        subagents[agent_id] = ConversationSubagentResponse(
            agent_id=agent_id,
            description=existing.description if existing else None,
            subagent_type=thread.agent_role or (existing.subagent_type if existing else None),
            nickname=thread.agent_nickname or (existing.nickname if existing else None),
            has_file=True,
            project_path=project_path,
            session_id=session_id,
        )

    return sorted(subagents.values(), key=lambda item: item.agent_id)


def _codex_session_artifacts(services: BackendServices) -> list[CodexSessionArtifact]:
    cached = services.cache.get("codex_session_artifacts")
    if isinstance(cached, list):
        return cached
    artifacts = services.codex_store.list_session_artifacts()
    services.cache.set("codex_session_artifacts", artifacts)
    return artifacts


def _codex_threads_by_id(services: BackendServices) -> dict[str, CodexThreadRecord]:
    cached = services.cache.get("codex_threads_by_id")
    if isinstance(cached, dict):
        return cached
    threads = {thread.id: thread for thread in services.codex_store.list_threads()}
    services.cache.set("codex_threads_by_id", threads)
    return threads


def _parse_jsonl_objects(content: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def _event_message(event: RawConversationEvent) -> dict[str, Any]:
    return event.message if isinstance(event.message, dict) else {}


def _message_content_list(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def _first_user_message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and _block_type(block) == "text":
                text = _string_or_none(block.get("text"))
                if text:
                    return text
    return ""


def _block_type(block: dict[str, Any]) -> str | None:
    return _string_or_none(block.get("type"))


def _tool_result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(_string_or_none(item.get("text")) or json.dumps(item, ensure_ascii=True))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _shape_plan_steps(raw_steps: list[dict[str, Any]]) -> list[ConversationPlanStepResponse]:
    steps: list[ConversationPlanStepResponse] = []
    for step in raw_steps:
        label = _string_or_none(step.get("step"))
        if not label:
            continue
        steps.append(
            ConversationPlanStepResponse(
                step=label,
                status=_string_or_none(step.get("status")) or "",
            )
        )
    return steps


def _sorted_buckets(bucket_totals: dict[str, _BucketTotals]) -> list[ConversationContextBucketResponse]:
    buckets = [
        ConversationContextBucketResponse(
            label=label,
            category=totals.category,
            input_tokens=totals.input_tokens,
            output_tokens=totals.output_tokens,
            cache_write_tokens=totals.cache_creation_tokens,
            cache_read_tokens=totals.cache_read_tokens,
            total_tokens=totals.total_tokens,
            calls=totals.calls,
        )
        for label, totals in bucket_totals.items()
    ]
    buckets.sort(key=lambda item: item.total_tokens, reverse=True)
    return buckets


def _add_bucket(
    bucket_totals: dict[str, _BucketTotals],
    *,
    label: str,
    category: str,
    usage: _UsageTotals,
) -> None:
    existing = bucket_totals.get(label)
    if existing is None:
        existing = _BucketTotals(category=category)
        bucket_totals[label] = existing
    existing.input_tokens += usage.input_tokens
    existing.output_tokens += usage.output_tokens
    existing.cache_creation_tokens += usage.cache_creation_tokens
    existing.cache_read_tokens += usage.cache_read_tokens
    existing.calls += 1


def _tool_category(tool_name: str) -> str:
    if tool_name.startswith("mcp__"):
        return "mcp"
    if tool_name == "Task":
        return "subagent"
    return "tool"


def _project_display_name(project_path: str) -> str:
    if project_path.startswith("codex:"):
        return f"Codex/{_project_display_name(project_path[len('codex:'):])}"
    if project_path.startswith("-"):
        segments = project_path.replace("-", "/").lstrip("/").split("/")
        filtered = [segment for segment in segments if segment]
        start_index = next(
            (
                index
                for index, segment in enumerate(filtered)
                if index >= 2 and segment not in {"Users", "Documents"}
            ),
            0,
        )
        return "/".join(filtered[max(start_index, 0) :][-3:])
    return project_path


def _project_full_path(services: BackendServices, project_path: str) -> str:
    if project_path.startswith("codex:"):
        return project_path
    return str(services.settings.claude_projects_dir / project_path)


def _cwd_to_project_path(cwd: str) -> str:
    return cwd.replace("/", "-") if cwd else "unknown"


def _cwd_to_display_name(cwd: str) -> str:
    if not cwd:
        return "Unknown"
    segments = [segment for segment in cwd.split("/") if segment]
    start_index = next(
        (
            index
            for index, segment in enumerate(segments)
            if index >= 2 and segment not in {"Users", "Documents"}
        ),
        0,
    )
    return "/".join(segments[max(start_index, 0) :][-3:])


def _parse_parent_thread_id(source: str | None) -> str | None:
    if not source or not source.strip().startswith("{"):
        return None
    try:
        parsed = json.loads(source)
    except json.JSONDecodeError:
        return None
    return _string_or_none(
        _dict_or_none(_dict_or_none(parsed.get("subagent")).get("thread_spawn")).get("parent_thread_id")
    )


def _codex_tool_display_name(raw_name: str) -> str:
    return {
        "exec_command": "Shell",
        "apply_patch": "Patch",
        "spawn_agent": "Spawn Agent",
        "send_input": "Send Input",
        "wait": "Wait",
        "close_agent": "Close Agent",
        "web_search_call": "Web Search",
    }.get(raw_name, raw_name)


def _first_codex_user_message(payload: dict[str, Any]) -> str:
    for text in _codex_message_texts(payload.get("content"), input_mode=True):
        if text:
            return text
    return ""


def _codex_message_texts(content: Any, *, input_mode: bool) -> list[str]:
    if not isinstance(content, list):
        return []
    expected_type = "input_text" if input_mode else "output_text"
    texts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if _string_or_none(block.get("type")) != expected_type:
            continue
        text = _string_or_none(block.get("text"))
        if not text:
            continue
        if input_mode and text.startswith("<"):
            continue
        texts.append(text)
    return texts


def _codex_reasoning_texts(summary: Any) -> list[str]:
    if not isinstance(summary, list):
        return []
    texts: list[str] = []
    for block in summary:
        if isinstance(block, dict):
            text = _string_or_none(block.get("text"))
            if text:
                texts.append(text)
    return texts


def _codex_output_is_error(output: str) -> bool:
    match = re.search(r"Process exited with code (\d+)", output)
    return match is not None and match.group(1) != "0"


def _extract_custom_tool_output(raw_output: str) -> str:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return raw_output
    if isinstance(parsed, dict) and isinstance(parsed.get("output"), str):
        return parsed["output"]
    return raw_output


def _spawn_agent_type(args: dict[str, Any]) -> str | None:
    return _string_or_none(args.get("agent_type"))


def _summarize_spawn_agent_message(args: dict[str, Any]) -> str | None:
    message = _string_or_none(args.get("message"))
    if not message:
        return None
    first_line = _first_non_empty_line(message)
    if first_line is None:
        return None
    return _truncate(first_line, max_length=200)


def _parse_spawn_agent_output(raw_output: Any) -> dict[str, str | None]:
    if not isinstance(raw_output, str):
        return {"agent_id": None, "nickname": None}
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return {"agent_id": None, "nickname": None}
    if not isinstance(parsed, dict):
        return {"agent_id": None, "nickname": None}
    return {
        "agent_id": _string_or_none(parsed.get("agent_id") or parsed.get("agentId") or parsed.get("id")),
        "nickname": _string_or_none(parsed.get("nickname")),
    }


def _cutoff_ms(days: int | None) -> float:
    if days is None:
        return 0.0
    return (datetime.now(UTC) - timedelta(days=days)).timestamp() * 1000


def _is_likely_active(last_updated_at: float) -> bool:
    if last_updated_at <= 0:
        return False
    now_ms = datetime.now(UTC).timestamp() * 1000
    return now_ms - last_updated_at <= _ACTIVE_WINDOW.total_seconds() * 1000


def _to_epoch_ms(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0.0
        try:
            return datetime.fromisoformat(stripped.replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            try:
                return float(stripped)
            except ValueError:
                return 0.0
    return 0.0


def _normalize_context_category(value: str | None) -> str:
    if value in {"tool", "mcp", "subagent", "thinking", "conversation"}:
        return value
    return "conversation"


def _parse_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_string_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str):
        return {}
    return _parse_json_object(raw)


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _dict_or_none(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _first_non_empty_line(value: str | None) -> str | None:
    if value is None:
        return None
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _truncate(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3].rstrip()}..."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "plan"


def _checkbox_for_status(status: str) -> str:
    if status == "completed":
        return "[x]"
    if status == "in_progress":
        return "[-]"
    return "[ ]"


def _summarize_plan_content(content: str, fallback_slug: str) -> dict[str, str]:
    lines = [line.rstrip() for line in content.splitlines()]
    title_line = next((line for line in lines if line.strip()), fallback_slug)
    title = title_line.lstrip("#").strip() or fallback_slug
    preview = _truncate(" ".join(line.strip() for line in lines if line.strip()), max_length=240)
    return {
        "slug": _slugify(fallback_slug or title),
        "title": _truncate(title, max_length=80),
        "preview": preview,
    }


def _encode_plan_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return raw.encode("utf-8").hex()


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in {None, "", []}}


class _UsageTotals:
    def __init__(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        speed: str | None = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_tokens = cache_creation_tokens
        self.cache_read_tokens = cache_read_tokens
        self.speed = speed

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    def add(self, other: _UsageTotals) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.cache_read_tokens += other.cache_read_tokens
        if self.speed is None:
            self.speed = other.speed

    def split(self, count: int) -> _UsageTotals:
        if count <= 0:
            return _UsageTotals()
        return _UsageTotals(
            input_tokens=round(self.input_tokens / count),
            output_tokens=round(self.output_tokens / count),
            cache_creation_tokens=round(self.cache_creation_tokens / count),
            cache_read_tokens=round(self.cache_read_tokens / count),
        )

    def response(self) -> ConversationUsageResponse:
        return ConversationUsageResponse(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens,
        )


def _usage_from_message(message: dict[str, Any]) -> _UsageTotals:
    usage = _dict_or_none(message.get("usage"))
    return _UsageTotals(
        input_tokens=_int_value(usage.get("input_tokens")),
        output_tokens=_int_value(usage.get("output_tokens")),
        cache_creation_tokens=_int_value(
            usage.get("cache_creation_input_tokens")
            or _dict_or_none(usage.get("cache_creation")).get("ephemeral_5m_input_tokens")
            or _dict_or_none(usage.get("cache_creation")).get("ephemeral_1h_input_tokens")
        ),
        cache_read_tokens=_int_value(usage.get("cache_read_input_tokens") or usage.get("cached_input_tokens")),
        speed=_string_or_none(usage.get("speed")),
    )


class _BucketTotals(_UsageTotals):
    def __init__(self, *, category: str) -> None:
        super().__init__()
        self.category = _normalize_context_category(category)
        self.calls = 0
