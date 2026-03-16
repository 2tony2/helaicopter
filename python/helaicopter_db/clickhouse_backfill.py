from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .clickhouse_bootstrap import apply_clickhouse_schema, _post_sql
from .export_pipeline import ExportMeta, iter_export_rows, read_export_meta
from .settings import CLICKHOUSE_SETTINGS, ClickHouseConnectionSettings
from .utils import conversation_id, parse_timestamp_ms, provider_for_project_path, to_json, utc_now

DECIMAL_SCALE = Decimal("0.00000001")
BACKFILL_MODE = "full_rebuild"
BACKFILL_TABLES = (
    "conversation_metadata_agg",
    "conversation_message_rollup_agg",
    "conversation_tool_rollup_agg",
    "conversation_usage_rollup_agg",
    "daily_usage_metrics_agg",
    "daily_usage_tool_agg",
    "tool_usage_rollups_agg",
    "subagent_usage_rollups_agg",
    "conversation_events",
    "message_events",
    "tool_events",
    "usage_events",
)
INSERT_BATCH_SIZE = 1_000


@dataclass
class ClickHouseBackfillCounters:
    conversation_events: int = 0
    message_events: int = 0
    tool_events: int = 0
    usage_events: int = 0


@dataclass
class ClickHouseBackfillResult:
    enabled: bool
    status: str
    target: str
    mode: str
    started_at: str | None
    finished_at: str | None
    duration_ms: int | None
    error: str | None
    idempotency_key: str | None
    source_conversation_count: int
    scope_label: str | None
    rows_loaded: dict[str, int]

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "target": self.target,
            "mode": self.mode,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "durationMs": self.duration_ms,
            "error": self.error,
            "idempotencyKey": self.idempotency_key,
            "sourceConversationCount": self.source_conversation_count,
            "scopeLabel": self.scope_label,
            "rowsLoaded": self.rows_loaded,
        }


def disabled_backfill_status() -> dict[str, Any]:
    return ClickHouseBackfillResult(
        enabled=False,
        status="disabled",
        target=CLICKHOUSE_SETTINGS.redacted_url,
        mode=BACKFILL_MODE,
        started_at=None,
        finished_at=None,
        duration_ms=None,
        error=None,
        idempotency_key=None,
        source_conversation_count=0,
        scope_label=None,
        rows_loaded={
            "conversationEvents": 0,
            "messageEvents": 0,
            "toolEvents": 0,
            "usageEvents": 0,
        },
    ).to_status_payload()


def running_backfill_status(
    export_meta: ExportMeta,
    *,
    started_at: datetime,
    settings: ClickHouseConnectionSettings = CLICKHOUSE_SETTINGS,
) -> dict[str, Any]:
    return ClickHouseBackfillResult(
        enabled=True,
        status="running",
        target=settings.redacted_url,
        mode=BACKFILL_MODE,
        started_at=started_at.isoformat(),
        finished_at=None,
        duration_ms=None,
        error=None,
        idempotency_key=export_meta.input_key,
        source_conversation_count=export_meta.conversation_count,
        scope_label=export_meta.scope_label,
        rows_loaded={
            "conversationEvents": 0,
            "messageEvents": 0,
            "toolEvents": 0,
            "usageEvents": 0,
        },
    ).to_status_payload()


def _format_clickhouse_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _decimal_text(value: Decimal | float | int | str) -> str:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return str(decimal_value.quantize(DECIMAL_SCALE, rounding=ROUND_HALF_UP))


def _json_each_row(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _split_integer(total: int, count: int) -> list[int]:
    if count <= 0:
        return []
    base = total // count
    remainder = total % count
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _split_decimal(total: Decimal, count: int) -> list[Decimal]:
    if count <= 0:
        return []
    scaled_total = int(
        (total / DECIMAL_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    scaled_parts = _split_integer(scaled_total, count)
    return [Decimal(part) * DECIMAL_SCALE for part in scaled_parts]


def _message_text_preview(blocks: list[dict[str, Any]]) -> str:
    text_parts: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "text" and block.get("text"):
            text_parts.append(str(block["text"]))
        elif block_type == "thinking" and block.get("thinking"):
            text_parts.append(str(block["thinking"]))
    preview = "\n\n".join(text_parts).strip()
    if preview:
        return preview[:4000]

    tool_names = [
        str(block.get("toolName"))
        for block in blocks
        if block.get("type") == "tool_call" and block.get("toolName")
    ]
    if tool_names:
        return ", ".join(tool_names)[:4000]
    return ""


def _message_cost_allocations(
    detail_messages: list[dict[str, Any]],
    cost: dict[str, Any],
) -> dict[str, dict[str, Decimal]]:
    assistant_messages = [
        message
        for message in detail_messages
        if isinstance(message.get("usage"), dict)
    ]
    if not assistant_messages:
        return {}

    totals = {
        "inputCost": sum(
            int((message.get("usage") or {}).get("input_tokens", 0))
            for message in assistant_messages
        ),
        "outputCost": sum(
            int((message.get("usage") or {}).get("output_tokens", 0))
            for message in assistant_messages
        ),
        "cacheWriteCost": sum(
            int((message.get("usage") or {}).get("cache_creation_input_tokens", 0))
            for message in assistant_messages
        ),
        "cacheReadCost": sum(
            int((message.get("usage") or {}).get("cache_read_input_tokens", 0))
            for message in assistant_messages
        ),
    }
    usage_field_for_cost = {
        "inputCost": "input_tokens",
        "outputCost": "output_tokens",
        "cacheWriteCost": "cache_creation_input_tokens",
        "cacheReadCost": "cache_read_input_tokens",
    }

    per_message = {
        str(message["id"]): {
            "inputCost": Decimal("0"),
            "outputCost": Decimal("0"),
            "cacheWriteCost": Decimal("0"),
            "cacheReadCost": Decimal("0"),
            "totalCost": Decimal("0"),
        }
        for message in assistant_messages
        if message.get("id")
    }

    for cost_key, denominator in totals.items():
        total_cost = Decimal(str(cost.get(cost_key, 0)))
        if total_cost == 0 or denominator <= 0:
            continue

        allocations: list[Decimal] = []
        for index, message in enumerate(assistant_messages):
            usage = message.get("usage") or {}
            if index == len(assistant_messages) - 1:
                allocated = total_cost - sum(allocations)
            else:
                share = Decimal(str(int(usage.get(usage_field_for_cost[cost_key], 0)))) / Decimal(
                    denominator
                )
                allocated = (total_cost * share).quantize(
                    DECIMAL_SCALE,
                    rounding=ROUND_HALF_UP,
                )
            allocations.append(allocated)
            message_id = str(message.get("id"))
            if not message_id:
                continue
            per_message[message_id][cost_key] += allocated
            per_message[message_id]["totalCost"] += allocated

    return per_message


def _insert_json_rows(
    settings: ClickHouseConnectionSettings,
    table_name: str,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    payload = "\n".join(_json_each_row(row) for row in rows)
    statement = f"INSERT INTO {settings.database}.{table_name} FORMAT JSONEachRow\n{payload}\n"
    _post_sql(settings, statement, database=settings.database)


def _flush_batches(
    settings: ClickHouseConnectionSettings,
    batches: dict[str, list[dict[str, Any]]],
) -> None:
    for table_name, rows in batches.items():
        _insert_json_rows(settings, table_name, rows)
        rows.clear()


def _truncate_backfill_tables(settings: ClickHouseConnectionSettings) -> None:
    for table_name in BACKFILL_TABLES:
        _post_sql(
            settings,
            f"TRUNCATE TABLE {settings.database}.{table_name}",
            database=settings.database,
        )


def run_clickhouse_backfill(
    *,
    settings: ClickHouseConnectionSettings = CLICKHOUSE_SETTINGS,
    export_meta: ExportMeta | None = None,
    wait_for_ready: bool = False,
    wait_timeout_seconds: float = 30.0,
) -> ClickHouseBackfillResult:
    meta = export_meta or read_export_meta()
    started_at = utc_now()
    counters = ClickHouseBackfillCounters()
    batches = {
        "conversation_events": [],
        "message_events": [],
        "tool_events": [],
        "usage_events": [],
    }

    try:
        apply_clickhouse_schema(
            settings,
            wait_for_ready=wait_for_ready,
            wait_timeout_seconds=wait_timeout_seconds,
        )
        _truncate_backfill_tables(settings)

        for envelope in iter_export_rows():
            summary = envelope["summary"]
            detail = envelope.get("detail") or {}
            cost = envelope.get("cost") or {}

            provider = provider_for_project_path(summary["projectPath"])
            conv_id = conversation_id(provider, summary["sessionId"])
            started_dt = parse_timestamp_ms(summary["timestamp"])
            ended_dt = parse_timestamp_ms(detail.get("endTime", summary["timestamp"]))
            conversation_payload = {
                "summary": summary,
                "cost": cost,
                "taskCount": len(envelope.get("tasks") or []),
            }
            batches["conversation_events"].append(
                {
                    "provider": provider,
                    "conversation_id": conv_id,
                    "session_id": summary["sessionId"],
                    "event_id": f"{conv_id}:conversation_started",
                    "event_time": _format_clickhouse_datetime(started_dt),
                    "ordinal": 0,
                    "event_type": "conversation_started",
                    "project_path": summary["projectPath"],
                    "project_name": summary["projectName"],
                    "git_branch": summary.get("gitBranch") or "",
                    "model": summary.get("model") or "",
                    "message_id": "",
                    "message_index": 0,
                    "message_role": "",
                    "tool_call_id": "",
                    "tool_name": "",
                    "tool_status": "",
                    "subagent_id": "",
                    "subagent_type": "",
                    "usage_input_tokens": 0,
                    "usage_output_tokens": 0,
                    "usage_cache_write_tokens": 0,
                    "usage_cache_read_tokens": 0,
                    "usage_reasoning_tokens": 0,
                    "estimated_input_cost": _decimal_text(0),
                    "estimated_output_cost": _decimal_text(0),
                    "estimated_cache_write_cost": _decimal_text(0),
                    "estimated_cache_read_cost": _decimal_text(0),
                    "estimated_total_cost": _decimal_text(0),
                    "is_terminal_event": 0,
                    "payload_json": to_json(conversation_payload),
                }
            )
            counters.conversation_events += 1
            batches["conversation_events"].append(
                {
                    "provider": provider,
                    "conversation_id": conv_id,
                    "session_id": summary["sessionId"],
                    "event_id": f"{conv_id}:conversation_completed",
                    "event_time": _format_clickhouse_datetime(ended_dt),
                    "ordinal": 1,
                    "event_type": "conversation_completed",
                    "project_path": summary["projectPath"],
                    "project_name": summary["projectName"],
                    "git_branch": summary.get("gitBranch") or "",
                    "model": summary.get("model") or "",
                    "message_id": "",
                    "message_index": int(summary.get("messageCount", 0)),
                    "message_role": "",
                    "tool_call_id": "",
                    "tool_name": "",
                    "tool_status": "",
                    "subagent_id": "",
                    "subagent_type": "",
                    "usage_input_tokens": int(summary.get("totalInputTokens", 0)),
                    "usage_output_tokens": int(summary.get("totalOutputTokens", 0)),
                    "usage_cache_write_tokens": int(summary.get("totalCacheCreationTokens", 0)),
                    "usage_cache_read_tokens": int(summary.get("totalCacheReadTokens", 0)),
                    "usage_reasoning_tokens": int(summary.get("totalReasoningTokens", 0) or 0),
                    "estimated_input_cost": _decimal_text(cost.get("inputCost", 0)),
                    "estimated_output_cost": _decimal_text(cost.get("outputCost", 0)),
                    "estimated_cache_write_cost": _decimal_text(cost.get("cacheWriteCost", 0)),
                    "estimated_cache_read_cost": _decimal_text(cost.get("cacheReadCost", 0)),
                    "estimated_total_cost": _decimal_text(cost.get("totalCost", 0)),
                    "is_terminal_event": 1,
                    "payload_json": to_json(conversation_payload),
                }
            )
            counters.conversation_events += 1

            detail_messages = detail.get("messages") or []
            message_costs = _message_cost_allocations(detail_messages, cost)
            subagent_type_assignments: list[str] = []
            for subagent_type, count in sorted((summary.get("subagentTypeBreakdown") or {}).items()):
                subagent_type_assignments.extend([subagent_type] * int(count))
            if not subagent_type_assignments:
                subagent_type_assignments = [
                    str(subagent.get("subagentType") or "")
                    for subagent in (detail.get("subagents") or [])
                    if subagent.get("subagentType")
                ]
            residual_subagents = max(int(summary.get("subagentCount", 0)) - len(subagent_type_assignments), 0)
            if residual_subagents:
                subagent_type_assignments.extend(["unknown"] * residual_subagents)
            assigned_subagent_index = 0

            for message_index, message in enumerate(detail_messages):
                message_id = str(message.get("id") or f"{conv_id}:message:{message_index}")
                message_time = parse_timestamp_ms(message.get("timestamp"))
                usage = message.get("usage") or {}
                message_total_cost = message_costs.get(message_id, {}).get("totalCost", Decimal("0"))
                tool_blocks = [
                    (block_index, block)
                    for block_index, block in enumerate(message.get("blocks") or [])
                    if block.get("type") == "tool_call"
                ]

                batches["message_events"].append(
                    {
                        "provider": provider,
                        "conversation_id": conv_id,
                        "session_id": summary["sessionId"],
                        "event_id": f"{conv_id}:message:{message_id}",
                        "message_id": message_id,
                        "message_index": message_index,
                        "message_time": _format_clickhouse_datetime(message_time),
                        "ordinal": message_index,
                        "project_path": summary["projectPath"],
                        "project_name": summary["projectName"],
                        "git_branch": summary.get("gitBranch") or "",
                        "model": message.get("model") or summary.get("model") or "",
                        "role": message.get("role") or "",
                        "author_name": "",
                        "message_kind": "message",
                        "content_text": _message_text_preview(message.get("blocks") or []),
                        "content_json": to_json(message.get("blocks") or []),
                        "input_tokens": int(usage.get("input_tokens", 0)),
                        "output_tokens": int(usage.get("output_tokens", 0)),
                        "cache_write_tokens": int(usage.get("cache_creation_input_tokens", 0)),
                        "cache_read_tokens": int(usage.get("cache_read_input_tokens", 0)),
                        "reasoning_tokens": int(message.get("reasoningTokens", 0) or 0),
                        "estimated_total_cost": _decimal_text(message_total_cost),
                        "has_tool_calls": 1 if tool_blocks else 0,
                        "is_error": 1
                        if any(block.get("isError") for _index, block in tool_blocks)
                        else 0,
                    }
                )
                counters.message_events += 1

                if tool_blocks:
                    input_tokens = _split_integer(int(usage.get("input_tokens", 0)), len(tool_blocks))
                    output_tokens = _split_integer(int(usage.get("output_tokens", 0)), len(tool_blocks))
                    cache_write_tokens = _split_integer(
                        int(usage.get("cache_creation_input_tokens", 0)),
                        len(tool_blocks),
                    )
                    cache_read_tokens = _split_integer(
                        int(usage.get("cache_read_input_tokens", 0)),
                        len(tool_blocks),
                    )
                    reasoning_tokens = _split_integer(
                        int(message.get("reasoningTokens", 0) or 0),
                        len(tool_blocks),
                    )
                    tool_costs = _split_decimal(message_total_cost, len(tool_blocks))

                    for tool_offset, (block_index, block) in enumerate(tool_blocks):
                        assigned_subagent_type = ""
                        if assigned_subagent_index < len(subagent_type_assignments):
                            assigned_subagent_type = subagent_type_assignments[assigned_subagent_index]
                            assigned_subagent_index += 1
                        batches["tool_events"].append(
                            {
                                "provider": provider,
                                "conversation_id": conv_id,
                                "session_id": summary["sessionId"],
                                "event_id": f"{conv_id}:tool:{message_id}:{block_index}",
                                "tool_call_id": block.get("toolUseId")
                                or f"{message_id}:tool:{block_index}",
                                "tool_name": block.get("toolName") or "unknown",
                                "started_at": _format_clickhouse_datetime(message_time),
                                "finished_at": _format_clickhouse_datetime(message_time),
                                "duration_ms": 0,
                                "ordinal": block_index,
                                "project_path": summary["projectPath"],
                                "project_name": summary["projectName"],
                                "git_branch": summary.get("gitBranch") or "",
                                "model": message.get("model") or summary.get("model") or "",
                                "parent_message_id": message_id,
                                "parent_message_index": message_index,
                                "tool_status": "error" if block.get("isError") else "completed",
                                "subagent_id": "",
                                "subagent_type": assigned_subagent_type,
                                "input_payload_json": to_json(block.get("input") or {}),
                                "output_payload_json": to_json(
                                    {"result": block.get("result")}
                                    if block.get("result") is not None
                                    else {}
                                ),
                                "error_text": str(block.get("result") or "")
                                if block.get("isError")
                                else "",
                                "input_tokens": input_tokens[tool_offset],
                                "output_tokens": output_tokens[tool_offset],
                                "cache_write_tokens": cache_write_tokens[tool_offset],
                                "cache_read_tokens": cache_read_tokens[tool_offset],
                                "reasoning_tokens": reasoning_tokens[tool_offset],
                                "estimated_total_cost": _decimal_text(tool_costs[tool_offset]),
                            }
                        )
                        counters.tool_events += 1

            batches["usage_events"].append(
                {
                    "provider": provider,
                    "conversation_id": conv_id,
                    "session_id": summary["sessionId"],
                    "event_id": f"{conv_id}:usage:conversation_total",
                    "event_time": _format_clickhouse_datetime(started_dt),
                    "ordinal": 0,
                    "project_path": summary["projectPath"],
                    "project_name": summary["projectName"],
                    "git_branch": summary.get("gitBranch") or "",
                    "model": summary.get("model") or "",
                    "message_id": "",
                    "message_index": 0,
                    "tool_call_id": "",
                    "usage_source": "conversation_total",
                    "input_tokens": int(summary.get("totalInputTokens", 0)),
                    "output_tokens": int(summary.get("totalOutputTokens", 0)),
                    "cache_write_tokens": int(summary.get("totalCacheCreationTokens", 0)),
                    "cache_read_tokens": int(summary.get("totalCacheReadTokens", 0)),
                    "reasoning_tokens": int(summary.get("totalReasoningTokens", 0) or 0),
                    "estimated_input_cost": _decimal_text(cost.get("inputCost", 0)),
                    "estimated_output_cost": _decimal_text(cost.get("outputCost", 0)),
                    "estimated_cache_write_cost": _decimal_text(cost.get("cacheWriteCost", 0)),
                    "estimated_cache_read_cost": _decimal_text(cost.get("cacheReadCost", 0)),
                    "estimated_total_cost": _decimal_text(cost.get("totalCost", 0)),
                }
            )
            counters.usage_events += 1

            if any(len(rows) >= INSERT_BATCH_SIZE for rows in batches.values()):
                _flush_batches(settings, batches)

        _flush_batches(settings, batches)
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        return ClickHouseBackfillResult(
            enabled=True,
            status="completed",
            target=settings.redacted_url,
            mode=BACKFILL_MODE,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_ms=duration_ms,
            error=None,
            idempotency_key=meta.input_key,
            source_conversation_count=meta.conversation_count,
            scope_label=meta.scope_label,
            rows_loaded={
                "conversationEvents": counters.conversation_events,
                "messageEvents": counters.message_events,
                "toolEvents": counters.tool_events,
                "usageEvents": counters.usage_events,
            },
        )
    except Exception as exc:
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        return ClickHouseBackfillResult(
            enabled=True,
            status="failed",
            target=settings.redacted_url,
            mode=BACKFILL_MODE,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_ms=duration_ms,
            error=str(exc),
            idempotency_key=meta.input_key,
            source_conversation_count=meta.conversation_count,
            scope_label=meta.scope_label,
            rows_loaded={
                "conversationEvents": counters.conversation_events,
                "messageEvents": counters.message_events,
                "toolEvents": counters.tool_events,
                "usageEvents": counters.usage_events,
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill historical conversation envelopes into ClickHouse.",
    )
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--database")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--secure", action="store_true")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--wait-for-ready", action="store_true")
    parser.add_argument("--wait-timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    overrides = {
        "host": args.host or CLICKHOUSE_SETTINGS.host,
        "port": args.port or CLICKHOUSE_SETTINGS.port,
        "database": args.database or CLICKHOUSE_SETTINGS.database,
        "user": args.user or CLICKHOUSE_SETTINGS.user,
        "password": args.password if args.password is not None else CLICKHOUSE_SETTINGS.password,
        "secure": args.secure or CLICKHOUSE_SETTINGS.secure,
        "verify_tls": False if args.insecure else CLICKHOUSE_SETTINGS.verify_tls,
    }
    settings = replace(CLICKHOUSE_SETTINGS, **overrides)
    result = run_clickhouse_backfill(
        settings=settings,
        wait_for_ready=args.wait_for_ready,
        wait_timeout_seconds=args.wait_timeout_seconds,
    )
    payload = result.to_status_payload()
    payload["trigger"] = args.trigger
    print(json.dumps(payload, ensure_ascii=True))
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
