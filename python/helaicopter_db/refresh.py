from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from helaicopter_api.server.config import Settings, load_settings

from .db import create_olap_engine, create_oltp_engine
from .export_pipeline import ExportMeta, iter_export_rows, read_export_meta
from .models import (
    ContextBucketRecord,
    ContextStepRecord,
    ConversationMessage,
    ConversationPlanRecord,
    ConversationRecord,
    ConversationSubagentRecord,
    ConversationTaskRecord,
    DimDate,
    DimModel,
    DimProject,
    DimSubagentType,
    DimTool,
    FactConversation,
    FactDailyUsage,
    FactOrchestrationRun,
    FactOrchestrationTaskAttempt,
    FactSubagentUsage,
    FactToolUsage,
    MessageBlockRecord,
    OltpFactOrchestrationRun,
    OltpFactOrchestrationTaskAttempt,
    RefreshRun,
)
from .orchestration_facts import collect_orchestration_facts
from .schemaspy import generate_schema_docs
from .settings import (
    get_database_settings,
    ensure_runtime_dirs,
)
from .status import build_status_payload, load_status, write_status
from .utils import (
    conversation_context_bucket_id,
    conversation_context_step_id,
    conversation_id,
    conversation_message_block_id,
    conversation_message_id,
    conversation_plan_row_id,
    conversation_subagent_row_id,
    conversation_task_row_id,
    date_key,
    model_dim_id,
    parse_timestamp_ms,
    project_dim_id,
    provider_for_project_path,
    subagent_dim_id,
    to_json,
    tool_dim_id,
    utc_now,
)


@dataclass
class RefreshCounters:
    conversations: int = 0
    messages: int = 0
    tool_calls: int = 0
    plans: int = 0


def _run_migrations(target: str, settings: Settings | None = None) -> None:
    backend_settings = settings or load_settings()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(backend_settings.project_root / "alembic.ini"),
            "-x",
            f"target={target}",
            "upgrade",
            "head",
        ],
        check=True,
        cwd=backend_settings.project_root,
        capture_output=True,
        text=True,
    )


def _cost_as_text(cost: float) -> str:
    return f"{cost:.8f}"


def _ensure_lock(settings: Settings | None = None) -> None:
    ensure_runtime_dirs(settings)
    lock_file = get_database_settings(settings).lock_file
    while True:
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            lock_pid = _read_lock_pid(lock_file)
            if lock_pid is not None and _pid_is_running(lock_pid):
                raise RuntimeError("A database refresh is already in progress.") from exc

            with suppress(FileNotFoundError):
                lock_file.unlink()
            continue

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return


def _read_lock_pid(lock_file: Path) -> int | None:
    try:
        raw_value = lock_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None

    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError:
        return None


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _release_lock(settings: Settings | None = None) -> None:
    lock_file = get_database_settings(settings).lock_file
    with suppress(FileNotFoundError):
        lock_file.unlink()


def _should_skip(
    force: bool,
    stale_after_seconds: int,
    export_meta: ExportMeta,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    if force:
        return None
    existing = load_status(settings)
    if existing:
        last_success = existing.get("lastSuccessfulRefreshAt")
        if existing.get("status") == "completed" and existing.get("idempotencyKey") == export_meta.input_key:
            return existing
        if last_success:
            elapsed = (utc_now() - datetime_from_iso(last_success)).total_seconds()
            if elapsed < stale_after_seconds:
                return existing

    latest_completed = _load_latest_completed_refresh(settings)
    if latest_completed and latest_completed.idempotency_key == export_meta.input_key:
        finished_at = latest_completed.finished_at.isoformat() if latest_completed.finished_at else None
        started_at = latest_completed.started_at.isoformat()
        return build_status_payload(
            status="completed",
            trigger=latest_completed.trigger,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=latest_completed.duration_ms,
            error=None,
            last_successful_refresh_at=finished_at,
            idempotency_key=latest_completed.idempotency_key,
            scope_label=latest_completed.scope_label or export_meta.scope_label,
            window_days=latest_completed.window_days or export_meta.window_days,
            window_start=latest_completed.window_start.isoformat() if latest_completed.window_start else export_meta.window_start,
            window_end=latest_completed.window_end.isoformat() if latest_completed.window_end else export_meta.window_end,
            source_conversation_count=latest_completed.source_conversation_count or export_meta.conversation_count,
            settings=settings,
        )
    return None


def datetime_from_iso(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _incremental_state_path(settings: Settings | None = None) -> Path:
    ensure_runtime_dirs(settings)
    return get_database_settings(settings).runtime_dir / "refresh_state.json"


def _load_incremental_state(settings: Settings | None = None) -> dict[str, str]:
    path = _incremental_state_path(settings)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _write_incremental_state(state: dict[str, str], settings: Settings | None = None) -> None:
    path = _incremental_state_path(settings)
    path.write_text(json.dumps(state, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _conversation_refresh_key(envelope: dict[str, Any]) -> str:
    summary = envelope["summary"]
    provider = provider_for_project_path(summary["projectPath"])
    return conversation_id(provider, summary["sessionId"])


def _conversation_refresh_hash(envelope: dict[str, Any]) -> str:
    return hashlib.sha256(to_json(envelope).encode("utf-8")).hexdigest()


def _load_latest_completed_refresh(settings: Settings | None = None) -> RefreshRun | None:
    sqlite = get_database_settings(settings).sqlite
    if not sqlite.path.exists():
        return None

    engine = create_oltp_engine(settings)
    try:
        with Session(engine) as session:
            return session.scalars(
                select(RefreshRun)
                .where(RefreshRun.status == "completed")
                .order_by(RefreshRun.started_at.desc())
                .limit(1)
            ).first()
    except Exception:
        return None
    finally:
        engine.dispose()


def _reset_oltp_data(session: Session) -> None:
    for model in (
        OltpFactOrchestrationTaskAttempt,
        OltpFactOrchestrationRun,
        MessageBlockRecord,
        ConversationMessage,
        ConversationPlanRecord,
        ConversationSubagentRecord,
        ConversationTaskRecord,
        ContextBucketRecord,
        ContextStepRecord,
        ConversationRecord,
    ):
        session.execute(delete(model))


def _delete_conversations(session: Session, conversation_ids: set[str]) -> None:
    if not conversation_ids:
        return
    message_ids = select(ConversationMessage.message_id).where(
        ConversationMessage.conversation_id.in_(conversation_ids)
    )
    session.execute(delete(MessageBlockRecord).where(MessageBlockRecord.message_id.in_(message_ids)))
    for model in (
        ConversationMessage,
        ConversationPlanRecord,
        ConversationSubagentRecord,
        ConversationTaskRecord,
        ContextBucketRecord,
        ContextStepRecord,
    ):
        session.execute(delete(model).where(model.conversation_id.in_(conversation_ids)))
    session.execute(delete(ConversationRecord).where(ConversationRecord.conversation_id.in_(conversation_ids)))


def _reset_olap_data(session: Session) -> None:
    for model in (
        FactOrchestrationTaskAttempt,
        FactOrchestrationRun,
        FactSubagentUsage,
        FactToolUsage,
        FactDailyUsage,
        FactConversation,
        DimSubagentType,
        DimTool,
        DimModel,
        DimProject,
        DimDate,
    ):
        session.execute(delete(model))


def _delete_olap_conversations(session: Session, conversation_ids: set[str]) -> None:
    if not conversation_ids:
        return
    session.execute(delete(FactConversation).where(FactConversation.conversation_id.in_(conversation_ids)))


def _reset_olap_derived_tables(session: Session) -> None:
    for model in (
        FactOrchestrationTaskAttempt,
        FactOrchestrationRun,
        FactSubagentUsage,
        FactToolUsage,
        FactDailyUsage,
    ):
        session.execute(delete(model))


def _reset_oltp_orchestration_facts(session: Session) -> None:
    for model in (OltpFactOrchestrationTaskAttempt, OltpFactOrchestrationRun):
        session.execute(delete(model))


def _text_preview(blocks: list[dict[str, Any]]) -> str:
    text_parts = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "text" and block.get("text"):
            text_parts.append(str(block["text"]))
        elif block_type == "thinking" and block.get("thinking"):
            text_parts.append(str(block["thinking"]))
    return "\n\n".join(text_parts)[:4000]


def _tool_result_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return to_json(value)


def _optional_timestamp_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return parse_timestamp_ms(value)
    except (TypeError, ValueError, OSError):
        return None


def _record_source(summary: dict[str, Any]) -> str | None:
    for key in ("recordSource", "sourcePath"):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _provenance_fields(
    *,
    record_source: str | None,
    source_file_modified_at: datetime | None,
    loaded_at: datetime,
    first_ingested_at: datetime,
) -> dict[str, Any]:
    return {
        "record_source": record_source,
        "source_file_modified_at": source_file_modified_at,
        "loaded_at": loaded_at,
        "first_ingested_at": first_ingested_at,
        "last_refreshed_at": loaded_at,
    }


def _child_first_ingested_map(
    session: Session,
    model: type[OltpBase],
    *,
    key_column: str,
    conversation_id: str,
) -> dict[str, datetime]:
    key_attr = getattr(model, key_column)
    rows = session.execute(
        select(key_attr, model.first_ingested_at).where(model.conversation_id == conversation_id)
    ).all()
    return {str(key): first_ingested_at for key, first_ingested_at in rows}


def _message_block_first_ingested_map(session: Session, *, conversation_id: str) -> dict[str, datetime]:
    rows = session.execute(
        select(MessageBlockRecord.block_id, MessageBlockRecord.first_ingested_at)
        .join(ConversationMessage, ConversationMessage.message_id == MessageBlockRecord.message_id)
        .where(ConversationMessage.conversation_id == conversation_id)
    ).all()
    return {str(block_id): first_ingested_at for block_id, first_ingested_at in rows}


def _delete_conversation_children(session: Session, conversation_id: str) -> None:
    message_ids = [
        row[0]
        for row in session.execute(
            select(ConversationMessage.message_id).where(ConversationMessage.conversation_id == conversation_id)
        ).all()
    ]
    if message_ids:
        session.execute(delete(MessageBlockRecord).where(MessageBlockRecord.message_id.in_(message_ids)))
    for model in (
        ConversationMessage,
        ConversationPlanRecord,
        ConversationSubagentRecord,
        ConversationTaskRecord,
        ContextBucketRecord,
        ContextStepRecord,
    ):
        session.execute(delete(model).where(model.conversation_id == conversation_id))


def _delete_missing_conversations(session: Session, seen_conversation_ids: set[str]) -> None:
    existing_ids = {
        conversation_id
        for conversation_id, in session.execute(select(ConversationRecord.conversation_id)).all()
    }
    for conversation_id in sorted(existing_ids - seen_conversation_ids):
        _delete_conversation_children(session, conversation_id)
        session.execute(delete(ConversationRecord).where(ConversationRecord.conversation_id == conversation_id))


def _load_conversation(
    oltp_session: Session,
    olap_session: Session,
    envelope: dict[str, Any],
    counters: RefreshCounters,
    daily_usage: dict[str, dict[str, Any]],
    tool_usage: dict[str, dict[str, Any]],
    subagent_usage: dict[str, dict[str, Any]],
    *,
    loaded_at: datetime,
) -> None:
    summary = envelope["summary"]
    detail = envelope.get("detail") or {}
    tasks = envelope.get("tasks") or []
    cost = envelope.get("cost") or {}

    provider = provider_for_project_path(summary["projectPath"])
    conv_id = conversation_id(provider, summary["sessionId"])
    started_at = parse_timestamp_ms(summary["timestamp"])
    ended_at = parse_timestamp_ms(detail.get("endTime", summary["timestamp"]))
    started_date = started_at.date()
    started_date_key = date_key(started_date)
    ended_date_key = date_key(ended_at.date())
    project_id = project_dim_id(provider, summary["projectPath"])
    model_name = summary.get("model") or "unknown"
    model_id = model_dim_id(provider, model_name)
    record_source = _record_source(summary)
    source_file_modified_at = _optional_timestamp_ms(summary.get("sourceFileModifiedAt"))
    existing_conversation = oltp_session.get(ConversationRecord, conv_id)
    first_ingested_at = existing_conversation.first_ingested_at if existing_conversation is not None else loaded_at
    message_first_ingested = _child_first_ingested_map(
        oltp_session,
        ConversationMessage,
        key_column="message_id",
        conversation_id=conv_id,
    )
    block_first_ingested = _message_block_first_ingested_map(oltp_session, conversation_id=conv_id)
    plan_first_ingested = _child_first_ingested_map(
        oltp_session,
        ConversationPlanRecord,
        key_column="plan_row_id",
        conversation_id=conv_id,
    )
    subagent_first_ingested = _child_first_ingested_map(
        oltp_session,
        ConversationSubagentRecord,
        key_column="subagent_row_id",
        conversation_id=conv_id,
    )
    task_first_ingested = _child_first_ingested_map(
        oltp_session,
        ConversationTaskRecord,
        key_column="task_row_id",
        conversation_id=conv_id,
    )
    bucket_first_ingested = _child_first_ingested_map(
        oltp_session,
        ContextBucketRecord,
        key_column="bucket_row_id",
        conversation_id=conv_id,
    )
    step_first_ingested = _child_first_ingested_map(
        oltp_session,
        ContextStepRecord,
        key_column="step_row_id",
        conversation_id=conv_id,
    )

    _delete_conversation_children(oltp_session, conv_id)

    olap_session.merge(
        DimDate(
            date_key=started_date_key,
            calendar_date=started_date,
            year=started_date.year,
            month=started_date.month,
            day=started_date.day,
            iso_week=started_date.isocalendar().week,
            weekday=started_date.isoweekday(),
        )
    )
    if started_date_key != ended_date_key:
        ended_date = ended_at.date()
        olap_session.merge(
            DimDate(
                date_key=ended_date_key,
                calendar_date=ended_date,
                year=ended_date.year,
                month=ended_date.month,
                day=ended_date.day,
                iso_week=ended_date.isocalendar().week,
                weekday=ended_date.isoweekday(),
            )
        )

    olap_session.merge(
        DimProject(
            project_id=project_id,
            provider=provider,
            project_path=summary["projectPath"],
            project_name=summary["projectName"],
        )
    )

    if summary.get("model"):
        olap_session.merge(
            DimModel(
                model_id=model_id,
                provider=provider,
                model_name=model_name,
            )
        )

    counters.conversations += 1
    if existing_conversation is None:
        conversation = ConversationRecord(conversation_id=conv_id)
        oltp_session.add(conversation)
    else:
        conversation = existing_conversation

    conversation.provider = provider
    conversation.session_id = summary["sessionId"]
    conversation.project_path = summary["projectPath"]
    conversation.project_name = summary["projectName"]
    conversation.thread_type = summary.get("threadType", "main")
    conversation.first_message = summary["firstMessage"]
    conversation.started_at = started_at
    conversation.ended_at = ended_at
    conversation.message_count = summary["messageCount"]
    conversation.model = summary.get("model")
    conversation.git_branch = summary.get("gitBranch")
    conversation.reasoning_effort = summary.get("reasoningEffort")
    conversation.speed = summary.get("speed")
    conversation.total_input_tokens = summary.get("totalInputTokens", 0)
    conversation.total_output_tokens = summary.get("totalOutputTokens", 0)
    conversation.total_cache_write_tokens = summary.get("totalCacheCreationTokens", 0)
    conversation.total_cache_read_tokens = summary.get("totalCacheReadTokens", 0)
    conversation.total_reasoning_tokens = summary.get("totalReasoningTokens", 0) or 0
    conversation.tool_use_count = summary.get("toolUseCount", 0)
    conversation.subagent_count = summary.get("subagentCount", 0)
    conversation.task_count = summary.get("taskCount", 0)
    conversation.estimated_input_cost = _cost_as_text(cost.get("inputCost", 0))
    conversation.estimated_output_cost = _cost_as_text(cost.get("outputCost", 0))
    conversation.estimated_cache_write_cost = _cost_as_text(cost.get("cacheWriteCost", 0))
    conversation.estimated_cache_read_cost = _cost_as_text(cost.get("cacheReadCost", 0))
    conversation.estimated_total_cost = _cost_as_text(cost.get("totalCost", 0))
    for field, value in _provenance_fields(
        record_source=record_source,
        source_file_modified_at=source_file_modified_at,
        loaded_at=loaded_at,
        first_ingested_at=first_ingested_at,
    ).items():
        setattr(conversation, field, value)

    for ordinal, message in enumerate(detail.get("messages") or []):
        persisted_message_id = conversation_message_id(conv_id, ordinal)
        message_row = ConversationMessage(
            message_id=persisted_message_id,
            conversation_id=conv_id,
            ordinal=ordinal,
            role=message.get("role", "assistant"),
            timestamp=parse_timestamp_ms(message.get("timestamp")),
            model=message.get("model"),
            reasoning_tokens=message.get("reasoningTokens") or 0,
            speed=message.get("speed"),
            input_tokens=message.get("usage", {}).get("input_tokens", 0),
            output_tokens=message.get("usage", {}).get("output_tokens", 0),
            cache_write_tokens=message.get("usage", {}).get("cache_creation_input_tokens", 0),
            cache_read_tokens=message.get("usage", {}).get("cache_read_input_tokens", 0),
            text_preview=_text_preview(message.get("blocks") or []),
            **_provenance_fields(
                record_source=record_source,
                source_file_modified_at=source_file_modified_at,
                loaded_at=loaded_at,
                first_ingested_at=message_first_ingested.get(persisted_message_id, loaded_at),
            ),
        )
        counters.messages += 1
        oltp_session.add(message_row)

        for block_index, block in enumerate(message.get("blocks") or []):
            block_type = block.get("type")
            tool_name = block.get("toolName")
            if block_type == "tool_call":
                counters.tool_calls += 1
            oltp_session.add(
                MessageBlockRecord(
                    block_id=conversation_message_block_id(persisted_message_id, block_index),
                    message_id=message_row.message_id,
                    block_index=block_index,
                    block_type=block_type or "unknown",
                    text_content=block.get("text") or block.get("thinking"),
                    tool_use_id=block.get("toolUseId"),
                    tool_name=tool_name,
                    tool_input_json=to_json(block.get("input")) if block.get("input") is not None else None,
                    tool_result_text=_tool_result_text(block.get("result")),
                    is_error=bool(block.get("isError", False)),
                    **_provenance_fields(
                        record_source=record_source,
                        source_file_modified_at=source_file_modified_at,
                        loaded_at=loaded_at,
                        first_ingested_at=block_first_ingested.get(
                            conversation_message_block_id(persisted_message_id, block_index),
                            loaded_at,
                        ),
                    ),
                )
            )

    for ordinal, plan in enumerate(detail.get("plans") or []):
        counters.plans += 1
        oltp_session.add(
            ConversationPlanRecord(
                plan_row_id=conversation_plan_row_id(conv_id, ordinal),
                conversation_id=conv_id,
                plan_id=plan["id"],
                slug=plan["slug"],
                title=plan["title"],
                preview=plan["preview"],
                content=plan["content"],
                provider=plan["provider"],
                timestamp=parse_timestamp_ms(plan["timestamp"]),
                model=plan.get("model"),
                explanation=plan.get("explanation"),
                steps_json=to_json(plan.get("steps")) if plan.get("steps") is not None else None,
                **_provenance_fields(
                    record_source=record_source,
                    source_file_modified_at=source_file_modified_at,
                    loaded_at=loaded_at,
                    first_ingested_at=plan_first_ingested.get(conversation_plan_row_id(conv_id, ordinal), loaded_at),
                ),
            )
        )

    for ordinal, subagent in enumerate(detail.get("subagents") or []):
        oltp_session.add(
            ConversationSubagentRecord(
                subagent_row_id=conversation_subagent_row_id(conv_id, ordinal),
                conversation_id=conv_id,
                agent_id=subagent["agentId"],
                description=subagent.get("description"),
                subagent_type=subagent.get("subagentType"),
                nickname=subagent.get("nickname"),
                has_file=bool(subagent.get("hasFile", False)),
                **_provenance_fields(
                    record_source=record_source,
                    source_file_modified_at=source_file_modified_at,
                    loaded_at=loaded_at,
                    first_ingested_at=subagent_first_ingested.get(
                        conversation_subagent_row_id(conv_id, ordinal),
                        loaded_at,
                    ),
                ),
            )
        )

    for ordinal, task in enumerate(tasks):
        oltp_session.add(
            ConversationTaskRecord(
                task_row_id=conversation_task_row_id(conv_id, ordinal),
                conversation_id=conv_id,
                ordinal=ordinal,
                task_json=to_json(task),
                **_provenance_fields(
                    record_source=record_source,
                    source_file_modified_at=source_file_modified_at,
                    loaded_at=loaded_at,
                    first_ingested_at=task_first_ingested.get(conversation_task_row_id(conv_id, ordinal), loaded_at),
                ),
            )
        )

    for ordinal, bucket in enumerate((detail.get("contextAnalytics") or {}).get("buckets") or []):
        oltp_session.add(
            ContextBucketRecord(
                bucket_row_id=conversation_context_bucket_id(conv_id, ordinal),
                conversation_id=conv_id,
                label=bucket["label"],
                category=bucket["category"],
                input_tokens=bucket.get("inputTokens", 0),
                output_tokens=bucket.get("outputTokens", 0),
                cache_write_tokens=bucket.get("cacheWriteTokens", 0),
                cache_read_tokens=bucket.get("cacheReadTokens", 0),
                total_tokens=bucket.get("totalTokens", 0),
                calls=bucket.get("calls", 0),
                **_provenance_fields(
                    record_source=record_source,
                    source_file_modified_at=source_file_modified_at,
                    loaded_at=loaded_at,
                    first_ingested_at=bucket_first_ingested.get(
                        conversation_context_bucket_id(conv_id, ordinal),
                        loaded_at,
                    ),
                ),
            )
        )

    for ordinal, step in enumerate((detail.get("contextAnalytics") or {}).get("steps") or []):
        oltp_session.add(
            ContextStepRecord(
                step_row_id=conversation_context_step_id(conv_id, ordinal),
                conversation_id=conv_id,
                message_id=step["messageId"],
                ordinal=ordinal,
                role=step["role"],
                label=step["label"],
                category=step["category"],
                timestamp=parse_timestamp_ms(step["timestamp"]),
                input_tokens=step.get("inputTokens", 0),
                output_tokens=step.get("outputTokens", 0),
                cache_write_tokens=step.get("cacheWriteTokens", 0),
                cache_read_tokens=step.get("cacheReadTokens", 0),
                total_tokens=step.get("totalTokens", 0),
                **_provenance_fields(
                    record_source=record_source,
                    source_file_modified_at=source_file_modified_at,
                    loaded_at=loaded_at,
                    first_ingested_at=step_first_ingested.get(
                        conversation_context_step_id(conv_id, ordinal),
                        loaded_at,
                    ),
                ),
            )
        )

    olap_session.add(
        FactConversation(
            conversation_id=conv_id,
            provider=provider,
            session_id=summary["sessionId"],
            project_id=project_id,
            model_id=model_id if summary.get("model") else None,
            started_date_key=started_date_key,
            ended_date_key=ended_date_key,
            started_at=started_at,
            ended_at=ended_at,
            first_message=summary["firstMessage"],
            message_count=summary["messageCount"],
            total_input_tokens=summary.get("totalInputTokens", 0),
            total_output_tokens=summary.get("totalOutputTokens", 0),
            total_cache_write_tokens=summary.get("totalCacheCreationTokens", 0),
            total_cache_read_tokens=summary.get("totalCacheReadTokens", 0),
            total_reasoning_tokens=summary.get("totalReasoningTokens", 0) or 0,
            tool_use_count=summary.get("toolUseCount", 0),
            subagent_count=summary.get("subagentCount", 0),
            task_count=summary.get("taskCount", 0),
            estimated_total_cost=Decimal(str(cost.get("totalCost", 0))),
            estimated_input_cost=Decimal(str(cost.get("inputCost", 0))),
            estimated_output_cost=Decimal(str(cost.get("outputCost", 0))),
            estimated_cache_write_cost=Decimal(str(cost.get("cacheWriteCost", 0))),
            estimated_cache_read_cost=Decimal(str(cost.get("cacheReadCost", 0))),
        )
    )

    daily_id = f"{provider}:{started_date_key}:{model_id if summary.get('model') else 'unknown'}"
    daily_row = daily_usage.setdefault(
        daily_id,
        {
            "provider": provider,
            "date_key": started_date_key,
            "model_id": model_id if summary.get("model") else None,
            "conversation_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_write_tokens": 0,
            "cache_read_tokens": 0,
            "reasoning_tokens": 0,
            "tool_calls": 0,
            "estimated_total_cost": Decimal("0"),
        },
    )
    daily_row["conversation_count"] += 1
    daily_row["input_tokens"] += summary.get("totalInputTokens", 0)
    daily_row["output_tokens"] += summary.get("totalOutputTokens", 0)
    daily_row["cache_write_tokens"] += summary.get("totalCacheCreationTokens", 0)
    daily_row["cache_read_tokens"] += summary.get("totalCacheReadTokens", 0)
    daily_row["reasoning_tokens"] += summary.get("totalReasoningTokens", 0) or 0
    daily_row["tool_calls"] += summary.get("toolUseCount", 0)
    daily_row["estimated_total_cost"] += Decimal(str(cost.get("totalCost", 0)))

    for tool_name, count in (summary.get("toolBreakdown") or {}).items():
        tool_id = tool_dim_id(provider, tool_name)
        olap_session.merge(DimTool(tool_id=tool_id, provider=provider, tool_name=tool_name))
        tool_usage_id = f"{provider}:{started_date_key}:{project_id}:{tool_id}"
        usage_row = tool_usage.setdefault(
            tool_usage_id,
            {
                "provider": provider,
                "date_key": started_date_key,
                "project_id": project_id,
                "tool_id": tool_id,
                "conversation_count": 0,
                "tool_calls": 0,
            },
        )
        usage_row["conversation_count"] += 1
        usage_row["tool_calls"] += count

    for subagent_type, count in (summary.get("subagentTypeBreakdown") or {}).items():
        dim_id = subagent_dim_id(provider, subagent_type)
        olap_session.merge(
            DimSubagentType(
                subagent_type_id=dim_id,
                provider=provider,
                subagent_type=subagent_type,
            )
        )
        usage_id = f"{provider}:{started_date_key}:{project_id}:{dim_id}"
        usage_row = subagent_usage.setdefault(
            usage_id,
            {
                "provider": provider,
                "date_key": started_date_key,
                "project_id": project_id,
                "subagent_type_id": dim_id,
                "conversation_count": 0,
                "subagent_count": 0,
            },
        )
        usage_row["conversation_count"] += 1
        usage_row["subagent_count"] += count


def _accumulate_usage(
    envelope: dict[str, Any],
    daily_usage: dict[str, dict[str, Any]],
    tool_usage: dict[str, dict[str, Any]],
    subagent_usage: dict[str, dict[str, Any]],
) -> None:
    summary = envelope["summary"]
    cost = envelope.get("cost") or {}
    provider = provider_for_project_path(summary["projectPath"])
    started_at = parse_timestamp_ms(summary["timestamp"])
    started_date_key = date_key(started_at.date())
    project_id = project_dim_id(provider, summary["projectPath"])
    model_name = summary.get("model") or "unknown"
    model_id = model_dim_id(provider, model_name)

    daily_id = f"{provider}:{started_date_key}:{model_id if summary.get('model') else 'unknown'}"
    daily_row = daily_usage.setdefault(
        daily_id,
        {
            "provider": provider,
            "date_key": started_date_key,
            "model_id": model_id if summary.get("model") else None,
            "conversation_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_write_tokens": 0,
            "cache_read_tokens": 0,
            "reasoning_tokens": 0,
            "tool_calls": 0,
            "estimated_total_cost": Decimal("0"),
        },
    )
    daily_row["conversation_count"] += 1
    daily_row["input_tokens"] += summary.get("totalInputTokens", 0)
    daily_row["output_tokens"] += summary.get("totalOutputTokens", 0)
    daily_row["cache_write_tokens"] += summary.get("totalCacheCreationTokens", 0)
    daily_row["cache_read_tokens"] += summary.get("totalCacheReadTokens", 0)
    daily_row["reasoning_tokens"] += summary.get("totalReasoningTokens", 0) or 0
    daily_row["tool_calls"] += summary.get("toolUseCount", 0)
    daily_row["estimated_total_cost"] += Decimal(str(cost.get("totalCost", 0)))

    for tool_name, count in (summary.get("toolBreakdown") or {}).items():
        tool_id = tool_dim_id(provider, tool_name)
        usage_id = f"{provider}:{started_date_key}:{project_id}:{tool_id}"
        usage_row = tool_usage.setdefault(
            usage_id,
            {
                "provider": provider,
                "date_key": started_date_key,
                "project_id": project_id,
                "tool_id": tool_id,
                "conversation_count": 0,
                "tool_calls": 0,
            },
        )
        usage_row["conversation_count"] += 1
        usage_row["tool_calls"] += count

    for subagent_type, count in (summary.get("subagentTypeBreakdown") or {}).items():
        dim_id = subagent_dim_id(provider, subagent_type)
        usage_id = f"{provider}:{started_date_key}:{project_id}:{dim_id}"
        usage_row = subagent_usage.setdefault(
            usage_id,
            {
                "provider": provider,
                "date_key": started_date_key,
                "project_id": project_id,
                "subagent_type_id": dim_id,
                "conversation_count": 0,
                "subagent_count": 0,
            },
        )
        usage_row["conversation_count"] += 1
        usage_row["subagent_count"] += count


def run_refresh(
    force: bool,
    trigger: str,
    stale_after_seconds: int,
    settings: Settings | None = None,
) -> dict[str, Any]:
    backend_settings = settings or load_settings()
    export_meta = read_export_meta(backend_settings)
    skip = _should_skip(force, stale_after_seconds, export_meta, backend_settings)
    if skip is not None:
        return skip

    _ensure_lock(backend_settings)
    started_at = utc_now()
    previous_status = load_status(backend_settings) or {}
    last_successful_refresh_at = previous_status.get("lastSuccessfulRefreshAt")
    previous_incremental_state = _load_incremental_state(backend_settings)
    envelopes = list(iter_export_rows(backend_settings))
    current_incremental_state = {
        _conversation_refresh_key(envelope): _conversation_refresh_hash(envelope) for envelope in envelopes
    }
    full_reconcile = force or not previous_incremental_state
    deleted_conversation_ids = set(previous_incremental_state) - set(current_incremental_state)
    changed_conversation_ids = {
        conversation_key
        for conversation_key, fingerprint in current_incremental_state.items()
        if previous_incremental_state.get(conversation_key) != fingerprint
    }

    running_status = {
        **previous_status,
        "status": "running",
        "trigger": trigger,
        "startedAt": started_at.isoformat(),
        "finishedAt": None,
        "durationMs": None,
        "error": None,
        "idempotencyKey": export_meta.input_key,
        "scopeLabel": export_meta.scope_label,
        "windowDays": export_meta.window_days,
        "windowStart": export_meta.window_start,
        "windowEnd": export_meta.window_end,
        "sourceConversationCount": export_meta.conversation_count,
    }
    write_status(running_status, backend_settings)

    oltp_engine = create_oltp_engine(backend_settings)
    olap_engine = create_olap_engine(backend_settings)
    counters = RefreshCounters()

    try:
        _run_migrations("oltp", backend_settings)
        _run_migrations("olap", backend_settings)

        with Session(oltp_engine) as oltp_session, Session(olap_engine) as olap_session:
            if full_reconcile:
                _reset_oltp_data(oltp_session)
                _reset_olap_data(olap_session)
            else:
                _delete_conversations(oltp_session, deleted_conversation_ids)
                _reset_oltp_orchestration_facts(oltp_session)
                _delete_olap_conversations(olap_session, deleted_conversation_ids | changed_conversation_ids)
                _reset_olap_derived_tables(olap_session)
            oltp_session.commit()
            olap_session.commit()
            run_record = RefreshRun(
                run_id=str(uuid.uuid4()),
                trigger=trigger,
                status="running",
                idempotency_key=export_meta.input_key,
                scope_label=export_meta.scope_label,
                window_days=export_meta.window_days,
                window_start=datetime_from_iso(export_meta.window_start) if export_meta.window_start else None,
                window_end=datetime_from_iso(export_meta.window_end) if export_meta.window_end else None,
                source_conversation_count=export_meta.conversation_count,
                started_at=started_at,
                finished_at=None,
                duration_ms=None,
                error_message=None,
                conversations_loaded=0,
                messages_loaded=0,
                tool_calls_loaded=0,
                plans_loaded=0,
            )
            oltp_session.add(run_record)

            daily_usage: dict[str, dict[str, Any]] = {}
            tool_usage: dict[str, dict[str, Any]] = {}
            subagent_usage: dict[str, dict[str, Any]] = {}

            for envelope in envelopes:
                _accumulate_usage(envelope, daily_usage, tool_usage, subagent_usage)
                if full_reconcile or _conversation_refresh_key(envelope) in changed_conversation_ids:
                    _load_conversation(
                        oltp_session,
                        olap_session,
                        envelope,
                        counters,
                        {},
                        {},
                        {},
                        loaded_at=started_at,
                    )

            for daily_usage_id, row in daily_usage.items():
                olap_session.add(
                    FactDailyUsage(
                        daily_usage_id=daily_usage_id,
                        provider=row["provider"],
                        date_key=row["date_key"],
                        model_id=row["model_id"],
                        conversation_count=row["conversation_count"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        cache_write_tokens=row["cache_write_tokens"],
                        cache_read_tokens=row["cache_read_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        tool_calls=row["tool_calls"],
                        estimated_total_cost=row["estimated_total_cost"],
                    )
                )

            for tool_usage_id, row in tool_usage.items():
                olap_session.add(
                    FactToolUsage(
                        tool_usage_id=tool_usage_id,
                        provider=row["provider"],
                        date_key=row["date_key"],
                        project_id=row["project_id"],
                        tool_id=row["tool_id"],
                        conversation_count=row["conversation_count"],
                        tool_calls=row["tool_calls"],
                    )
                )

            for subagent_usage_id, row in subagent_usage.items():
                olap_session.add(
                    FactSubagentUsage(
                        subagent_usage_id=subagent_usage_id,
                        provider=row["provider"],
                        date_key=row["date_key"],
                        project_id=row["project_id"],
                        subagent_type_id=row["subagent_type_id"],
                        conversation_count=row["conversation_count"],
                        subagent_count=row["subagent_count"],
                    )
                )

            orchestration_run_facts, orchestration_task_attempt_facts = collect_orchestration_facts(
                backend_settings.project_root
            )
            for fact in orchestration_run_facts:
                oltp_session.add(
                    OltpFactOrchestrationRun(
                        run_fact_id=fact.run_fact_id,
                        run_source=fact.run_source,
                        run_id=fact.run_id,
                        flow_run_name=fact.flow_run_name,
                        run_title=fact.run_title,
                        source_path=fact.source_path,
                        repo_root=fact.repo_root,
                        config_path=fact.config_path,
                        artifact_root=fact.artifact_root,
                        status=fact.status,
                        canonical_status_source=fact.canonical_status_source,
                        has_runtime_snapshot=fact.has_runtime_snapshot,
                        has_terminal_record=fact.has_terminal_record,
                        task_count=fact.task_count,
                        completed_task_count=fact.completed_task_count,
                        running_task_count=fact.running_task_count,
                        failed_task_count=fact.failed_task_count,
                        task_attempt_count=fact.task_attempt_count,
                        started_at=fact.started_at,
                        updated_at=fact.updated_at,
                        finished_at=fact.finished_at,
                    )
                )
                olap_session.add(
                    FactOrchestrationRun(
                        run_fact_id=fact.run_fact_id,
                        run_source=fact.run_source,
                        run_id=fact.run_id,
                        flow_run_name=fact.flow_run_name,
                        run_title=fact.run_title,
                        source_path=fact.source_path,
                        repo_root=fact.repo_root,
                        config_path=fact.config_path,
                        artifact_root=fact.artifact_root,
                        status=fact.status,
                        canonical_status_source=fact.canonical_status_source,
                        has_runtime_snapshot=fact.has_runtime_snapshot,
                        has_terminal_record=fact.has_terminal_record,
                        task_count=fact.task_count,
                        completed_task_count=fact.completed_task_count,
                        running_task_count=fact.running_task_count,
                        failed_task_count=fact.failed_task_count,
                        task_attempt_count=fact.task_attempt_count,
                        started_at=fact.started_at,
                        updated_at=fact.updated_at,
                        finished_at=fact.finished_at,
                    )
                )

            for fact in orchestration_task_attempt_facts:
                oltp_session.add(
                    OltpFactOrchestrationTaskAttempt(
                        task_attempt_fact_id=fact.task_attempt_fact_id,
                        run_fact_id=fact.run_fact_id,
                        run_source=fact.run_source,
                        run_id=fact.run_id,
                        task_id=fact.task_id,
                        task_title=fact.task_title,
                        attempt=fact.attempt,
                        status=fact.status,
                        upstream_task_ids_json=fact.upstream_task_ids_json,
                        agent=fact.agent,
                        session_id=fact.session_id,
                        model=fact.model,
                        reasoning_effort=fact.reasoning_effort,
                        error=fact.error,
                        output_text=fact.output_text,
                        started_at=fact.started_at,
                        updated_at=fact.updated_at,
                        finished_at=fact.finished_at,
                        last_heartbeat_at=fact.last_heartbeat_at,
                        last_progress_event_at=fact.last_progress_event_at,
                    )
                )
                olap_session.add(
                    FactOrchestrationTaskAttempt(
                        task_attempt_fact_id=fact.task_attempt_fact_id,
                        run_fact_id=fact.run_fact_id,
                        run_source=fact.run_source,
                        run_id=fact.run_id,
                        task_id=fact.task_id,
                        task_title=fact.task_title,
                        attempt=fact.attempt,
                        status=fact.status,
                        upstream_task_ids_json=fact.upstream_task_ids_json,
                        agent=fact.agent,
                        session_id=fact.session_id,
                        model=fact.model,
                        reasoning_effort=fact.reasoning_effort,
                        error=fact.error,
                        output_text=fact.output_text,
                        started_at=fact.started_at,
                        updated_at=fact.updated_at,
                        finished_at=fact.finished_at,
                        last_heartbeat_at=fact.last_heartbeat_at,
                        last_progress_event_at=fact.last_progress_event_at,
                    )
                )

            warehouse_finished_at = utc_now()
            warehouse_duration_ms = int((warehouse_finished_at - started_at).total_seconds() * 1000)
            run_record.status = "completed"
            run_record.finished_at = warehouse_finished_at
            run_record.duration_ms = warehouse_duration_ms
            run_record.conversations_loaded = counters.conversations
            run_record.messages_loaded = counters.messages
            run_record.tool_calls_loaded = counters.tool_calls
            run_record.plans_loaded = counters.plans

            oltp_session.commit()
            olap_session.commit()

        oltp_engine.dispose()
        olap_engine.dispose()

        try:
            generate_schema_docs(backend_settings)
        except Exception as exc:
            print(f"Schema docs generation failed: {exc}", file=sys.stderr)

        finished_at = warehouse_finished_at
        duration_ms = warehouse_duration_ms

        last_successful_refresh_at = finished_at.isoformat()
        payload = build_status_payload(
            status="completed",
            trigger=trigger,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_ms=duration_ms,
            error=None,
            last_successful_refresh_at=last_successful_refresh_at,
            idempotency_key=export_meta.input_key,
            scope_label=export_meta.scope_label,
            window_days=export_meta.window_days,
            window_start=export_meta.window_start,
            window_end=export_meta.window_end,
            source_conversation_count=export_meta.conversation_count,
            settings=backend_settings,
        )
        write_status(payload, backend_settings)
        _write_incremental_state(current_incremental_state, backend_settings)
        return payload
    except Exception as exc:
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        payload = {
            **(previous_status or {}),
            "status": "failed",
            "trigger": trigger,
            "startedAt": started_at.isoformat(),
            "finishedAt": finished_at.isoformat(),
            "durationMs": duration_ms,
            "error": str(exc),
            "lastSuccessfulRefreshAt": last_successful_refresh_at,
            "idempotencyKey": export_meta.input_key,
            "scopeLabel": export_meta.scope_label,
            "windowDays": export_meta.window_days,
            "windowStart": export_meta.window_start,
            "windowEnd": export_meta.window_end,
            "sourceConversationCount": export_meta.conversation_count,
        }
        write_status(payload, backend_settings)
        raise
    finally:
        oltp_engine.dispose()
        olap_engine.dispose()
        _release_lock(backend_settings)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--stale-after-seconds", type=int, default=21600)
    args = parser.parse_args()

    try:
        payload = run_refresh(
            force=args.force,
            trigger=args.trigger,
            stale_after_seconds=args.stale_after_seconds,
        )
        print(json.dumps(payload, ensure_ascii=True))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=True))
        raise


if __name__ == "__main__":
    main()
