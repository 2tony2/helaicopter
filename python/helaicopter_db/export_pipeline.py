from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from helaicopter_api.application.conversations import (
    _get_codex_live_conversation,
    _get_openclaw_live_conversation,
    _openclaw_session_artifacts,
    _shape_claude_live_conversation_detail,
    _summarize_openclaw_artifact,
    _summarize_claude_session,
    _summarize_codex_artifact,
)
from helaicopter_api.bootstrap.services import build_services
from helaicopter_api.schema.conversations import (
    ConversationContextAnalyticsResponse,
    ConversationDetailResponse,
    ConversationMessageBlockResponse,
    ConversationMessageResponse,
    ConversationPlanResponse,
    ConversationSubagentResponse,
    ConversationSummaryResponse,
)
from helaicopter_api.server.config import Settings, load_settings
from helaicopter_semantics import resolve_provider
from helaicopter_semantics.pricing import CLAUDE_PRICING, OPENAI_PRICING, CostBreakdown, calculate_cost

from .export_types import (
    ExportConversationEnvelope,
    parse_export_conversation_envelope,
)
from .utils import conversation_id, provider_for_project_path

MAX_WINDOW_DAYS = 365
MILLIS_PER_DAY = 24 * 60 * 60 * 1000
SCOPE_LABEL = f"Historical conversations before today from the last {MAX_WINDOW_DAYS} days"


@dataclass
class ExportMeta:
    conversation_count: int
    input_key: str
    scope_label: str
    window_days: int
    window_start: str | None
    window_end: str | None


def _utc_now_ms() -> int:
    return int(datetime.now(tz=UTC).timestamp() * 1000)


def _start_of_today(now_ms: int | None = None) -> datetime:
    current = datetime.fromtimestamp((now_ms or _utc_now_ms()) / 1000, tz=UTC)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_today_iso(now_ms: int | None = None) -> str:
    return _start_of_today(now_ms).isoformat().replace("+00:00", "Z")


def _stable(value: object) -> object:
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, dict):
        return {key: _stable(value[key]) for key in sorted(value)}
    return value


def _drop_none_fields(value: object) -> object:
    if isinstance(value, list):
        return [_drop_none_fields(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _drop_none_fields(nested)
            for key, nested in value.items()
            if nested is not None
        }
    return value


def _iter_historical_envelopes(settings: Settings | None = None) -> Iterable[ExportConversationEnvelope]:
    backend_settings = settings or load_settings()
    deduped: dict[str, ExportConversationEnvelope] = {}
    for iterator in (
        _iter_claude_historical_envelopes(backend_settings),
        _iter_codex_historical_envelopes(backend_settings),
        _iter_openclaw_historical_envelopes(backend_settings),
    ):
        for envelope in iterator:
            parsed = parse_export_conversation_envelope(_drop_none_fields(envelope))
            if parsed is not None and parsed.get("type") == "conversation":
                parsed["summary"]["provider"] = _summary_provider(parsed["summary"])
                key = _conversation_key(parsed)
                existing = deduped.get(key)
                if existing is None or _envelope_rank(parsed) >= _envelope_rank(existing):
                    deduped[key] = parsed
    yield from deduped.values()


def iter_export_rows(settings: Settings | None = None) -> Iterable[ExportConversationEnvelope]:
    yield from _iter_historical_envelopes(settings)


def read_export_meta(settings: Settings | None = None) -> ExportMeta:
    rows = list(_iter_historical_envelopes(settings))
    sorted_summaries = sorted(
        (_stable(row["summary"]) for row in rows),
        key=lambda item: json.dumps(item),
    )
    input_key = hashlib.sha256(json.dumps(sorted_summaries).encode("utf-8")).hexdigest()
    now_ms = _utc_now_ms()
    cutoff_start = now_ms - MAX_WINDOW_DAYS * MILLIS_PER_DAY
    timestamps = [
        int(summary["timestamp"])
        for summary in sorted_summaries
        if isinstance(summary, dict) and _finite_number(summary.get("timestamp"))
    ]
    oldest_conversation = min(timestamps) if timestamps else cutoff_start
    window_start = datetime.fromtimestamp(
        max(cutoff_start, oldest_conversation) / 1000,
        tz=UTC,
    ).isoformat().replace("+00:00", "Z")
    return ExportMeta(
        conversation_count=len(rows),
        input_key=input_key,
        scope_label=SCOPE_LABEL,
        window_days=MAX_WINDOW_DAYS,
        window_start=window_start,
        window_end=_start_of_today_iso(now_ms),
    )


def _iter_claude_historical_envelopes(settings: Settings) -> Iterable[dict[str, object]]:
    services = build_services(settings)
    cutoff_ms = _utc_now_ms() - MAX_WINDOW_DAYS * MILLIS_PER_DAY
    start_of_today_ms = int(_start_of_today().timestamp() * 1000)
    for project_dir in services.claude_conversation_reader.list_projects():
        for session in services.claude_conversation_reader.list_sessions(project_dir.dir_name):
            modified_at_ms = int(session.modified_at * 1000)
            if modified_at_ms < cutoff_ms:
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
                modified_at_ms=modified_at_ms,
            )
            if summary is None or summary.timestamp >= start_of_today_ms or summary.last_updated_at < cutoff_ms:
                continue
            detail = _shape_claude_live_conversation_detail(
                services,
                project_path=project_dir.dir_name,
                session_id=session.session_id,
                events=events,
                modified_at_ms=modified_at_ms,
                thread_type="main",
            )
            yield _build_envelope(
                summary=summary,
                detail=detail,
                tasks=[task.model_dump(mode="python") for task in services.claude_task_reader.read_tasks(session.session_id)],
                source_path=session.path,
                source_file_modified_at=modified_at_ms,
            )


def _iter_codex_historical_envelopes(settings: Settings) -> Iterable[dict[str, object]]:
    services = build_services(settings)
    cutoff_ms = _utc_now_ms() - MAX_WINDOW_DAYS * MILLIS_PER_DAY
    start_of_today_ms = int(_start_of_today().timestamp() * 1000)
    thread_by_id = {thread.id: thread for thread in services.codex_store.list_threads()}
    for artifact in services.codex_store.list_session_artifacts():
        modified_at_ms = int(artifact.modified_at * 1000)
        if modified_at_ms < cutoff_ms:
            continue
        summary, _parent_thread_id, _agent_role = _summarize_codex_artifact(
            artifact,
            thread=thread_by_id.get(artifact.session_id),
        )
        if summary is None or summary.timestamp >= start_of_today_ms or summary.last_updated_at < cutoff_ms:
            continue
        detail = _get_codex_live_conversation(
            services,
            session_id=artifact.session_id,
            project_path=summary.project_path,
        )
        if detail is None:
            continue
        yield _build_envelope(
            summary=summary,
            detail=detail,
            tasks=[],
            source_path=artifact.path,
            source_file_modified_at=modified_at_ms,
        )


def _iter_openclaw_historical_envelopes(settings: Settings) -> Iterable[dict[str, object]]:
    services = build_services(settings)
    cutoff_ms = _utc_now_ms() - MAX_WINDOW_DAYS * MILLIS_PER_DAY
    start_of_today_ms = int(_start_of_today().timestamp() * 1000)
    for artifact in _openclaw_session_artifacts(services):
        modified_at_ms = int(artifact.modified_at * 1000)
        if modified_at_ms < cutoff_ms:
            continue
        summary = _summarize_openclaw_artifact(artifact)
        if summary is None or summary.timestamp >= start_of_today_ms or summary.last_updated_at < cutoff_ms:
            continue
        detail = _get_openclaw_live_conversation(
            services,
            session_id=summary.session_id,
            project_path=summary.project_path,
        )
        if detail is None:
            continue
        yield _build_envelope(
            summary=summary,
            detail=detail,
            tasks=[],
            source_path=artifact.path,
            source_file_modified_at=modified_at_ms,
        )


def _build_envelope(
    *,
    summary: ConversationSummaryResponse,
    detail: ConversationDetailResponse,
    tasks: list[object],
    source_path: str,
    source_file_modified_at: int,
) -> dict[str, object]:
    provider = resolve_provider(model=summary.model, project_path=summary.project_path)
    cost = _export_cost_breakdown(summary, provider=provider)
    return {
        "type": "conversation",
        "summary": _summary_payload(summary, source_path=source_path, source_file_modified_at=source_file_modified_at),
        "detail": _detail_payload(detail),
        "tasks": tasks,
        "cost": {
            "inputCost": cost.input_cost,
            "outputCost": cost.output_cost,
            "cacheWriteCost": cost.cache_write_cost,
            "cacheReadCost": cost.cache_read_cost,
            "totalCost": cost.total_cost,
        },
    }


def _export_cost_breakdown(
    summary: ConversationSummaryResponse,
    *,
    provider: str,
) -> CostBreakdown:
    if provider == "openclaw" and not _openclaw_has_known_cost_model(summary.model):
        return CostBreakdown(
            input_cost=0.0,
            output_cost=0.0,
            cache_write_cost=0.0,
            cache_read_cost=0.0,
        )
    return calculate_cost(
        input_tokens=summary.total_input_tokens,
        output_tokens=summary.total_output_tokens,
        cache_write_tokens=summary.total_cache_creation_tokens,
        cache_read_tokens=summary.total_cache_read_tokens,
        model=summary.model,
    )


def _summary_payload(
    summary: ConversationSummaryResponse,
    *,
    source_path: str,
    source_file_modified_at: int,
) -> dict[str, object]:
    provider = resolve_provider(model=summary.model, project_path=summary.project_path)
    return {
        "sessionId": summary.session_id,
        "provider": provider,
        "projectPath": summary.project_path,
        "projectName": summary.project_name,
        "threadType": summary.thread_type,
        "firstMessage": summary.first_message,
        "timestamp": int(summary.timestamp),
        "messageCount": summary.message_count,
        "model": summary.model,
        "gitBranch": summary.git_branch,
        "reasoningEffort": summary.reasoning_effort,
        "speed": summary.speed,
        "totalInputTokens": summary.total_input_tokens,
        "totalOutputTokens": summary.total_output_tokens,
        "totalCacheCreationTokens": summary.total_cache_creation_tokens,
        "totalCacheReadTokens": summary.total_cache_read_tokens,
        "totalReasoningTokens": summary.total_reasoning_tokens or 0,
        "toolUseCount": summary.tool_use_count,
        "subagentCount": summary.subagent_count,
        "taskCount": summary.task_count,
        "toolBreakdown": dict(summary.tool_breakdown),
        "subagentTypeBreakdown": dict(summary.subagent_type_breakdown),
        "recordSource": source_path,
        "sourcePath": source_path,
        "sourceFileModifiedAt": source_file_modified_at,
    }


def _openclaw_has_known_cost_model(model: str | None) -> bool:
    if not model:
        return False
    if model in CLAUDE_PRICING or model in OPENAI_PRICING:
        return True
    if any(model.startswith(key) for key in CLAUDE_PRICING):
        return True
    if any(model.startswith(key) for key in OPENAI_PRICING):
        return True
    if "gpt-5.4" in model or "gpt5.4" in model:
        return True
    if "gpt-5.2" in model or "gpt5.2" in model:
        return True
    if "gpt-5.1" in model or "gpt5.1" in model:
        return True
    if "gpt-5-mini" in model or "gpt5-mini" in model:
        return True
    if "gpt-5" in model or "gpt5" in model:
        return True
    if "o4-mini" in model or "o3" in model:
        return True
    if "opus-4-6" in model or "opus-4-5" in model:
        return True
    if "opus-4-1" in model or "opus-4" in model:
        return True
    if "sonnet" in model or "haiku" in model:
        return True
    return False


def _detail_payload(detail: ConversationDetailResponse) -> dict[str, object]:
    return {
        "endTime": int(detail.end_time),
        "messages": [_message_payload(message) for message in detail.messages],
        "plans": [_plan_payload(plan) for plan in detail.plans],
        "subagents": [_subagent_payload(subagent) for subagent in detail.subagents],
        "contextAnalytics": _context_analytics_payload(detail.context_analytics),
    }


def _message_payload(message: ConversationMessageResponse) -> dict[str, object]:
    usage = message.usage
    return {
        "role": message.role,
        "timestamp": int(message.timestamp),
        "model": message.model,
        "reasoningTokens": message.reasoning_tokens or 0,
        "speed": message.speed,
        "usage": {
            "input_tokens": usage.input_tokens if usage is not None else 0,
            "output_tokens": usage.output_tokens if usage is not None else 0,
            "cache_creation_input_tokens": usage.cache_creation_tokens if usage is not None else 0,
            "cache_read_input_tokens": usage.cache_read_tokens if usage is not None else 0,
        },
        "blocks": [_block_payload(block) for block in message.blocks],
    }


def _block_payload(block: ConversationMessageBlockResponse) -> dict[str, object]:
    payload = block.model_dump(mode="python")
    block_type = payload.get("type")
    if block_type == "tool_call":
        return {
            "type": "tool_call",
            "toolUseId": payload.get("tool_use_id"),
            "toolName": payload.get("tool_name"),
            "input": payload.get("input", {}).get("root", {}),
            "result": payload.get("result"),
            "isError": payload.get("is_error"),
        }
    if block_type == "thinking":
        return {
            "type": "thinking",
            "thinking": payload.get("thinking", ""),
        }
    return {
        "type": "text",
        "text": payload.get("text", ""),
    }


def _plan_payload(plan: ConversationPlanResponse) -> dict[str, object]:
    return {
        "id": plan.id,
        "slug": plan.slug,
        "title": plan.title,
        "preview": plan.preview,
        "content": plan.content,
        "provider": plan.provider,
        "timestamp": int(plan.timestamp),
        "model": plan.model,
        "explanation": plan.explanation,
        "steps": [step.model_dump(mode="python") for step in plan.steps],
    }


def _subagent_payload(subagent: ConversationSubagentResponse) -> dict[str, object]:
    return {
        "agentId": subagent.agent_id,
        "description": subagent.description,
        "subagentType": subagent.subagent_type,
        "nickname": subagent.nickname,
        "hasFile": subagent.has_file,
    }


def _context_analytics_payload(analytics: ConversationContextAnalyticsResponse) -> dict[str, object]:
    return {
        "buckets": [
            {
                "label": bucket.label,
                "category": bucket.category,
                "inputTokens": bucket.input_tokens,
                "outputTokens": bucket.output_tokens,
                "cacheWriteTokens": bucket.cache_write_tokens,
                "cacheReadTokens": bucket.cache_read_tokens,
                "totalTokens": bucket.total_tokens,
                "calls": bucket.calls,
            }
            for bucket in analytics.buckets
        ],
        "steps": [
            {
                "messageId": step.message_id,
                "role": step.role,
                "label": step.label,
                "category": step.category,
                "timestamp": int(step.timestamp),
                "inputTokens": step.input_tokens,
                "outputTokens": step.output_tokens,
                "cacheWriteTokens": step.cache_write_tokens,
                "cacheReadTokens": step.cache_read_tokens,
                "totalTokens": step.total_tokens,
            }
            for step in analytics.steps
        ],
    }


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _conversation_key(envelope: ExportConversationEnvelope) -> str:
    summary = envelope["summary"]
    provider = _summary_provider(summary)
    return conversation_id(provider, summary["sessionId"])


def _summary_provider(summary: dict[str, object]) -> str:
    provider = summary.get("provider")
    if isinstance(provider, str) and provider:
        return provider
    project_path = summary["projectPath"]
    if isinstance(project_path, str) and project_path.startswith("openclaw:"):
        return "openclaw"
    return provider_for_project_path(project_path)


def _envelope_rank(envelope: ExportConversationEnvelope) -> tuple[int, int]:
    summary = envelope["summary"]
    modified_at = int(summary.get("sourceFileModifiedAt") or 0)
    timestamp = int(summary.get("timestamp") or 0)
    return modified_at, timestamp
