"""Pure analytics aggregation for persisted conversation summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
from helaicopter_semantics import (
    CLAUDE_PRICING,
    OPENAI_PRICING,
    calculate_cost,
    resolve_provider,
    supports_long_context_premium,
)

AnalyticsProvider = Literal["claude", "codex", "openclaw"]
TimeSeriesKey = Literal["hourly", "daily", "weekly", "monthly"]
TIME_SERIES_KEYS: tuple[TimeSeriesKey, TimeSeriesKey, TimeSeriesKey, TimeSeriesKey] = (
    "hourly",
    "daily",
    "weekly",
    "monthly",
)


@dataclass(slots=True)
class ProviderBreakdown:
    claude: int = 0
    codex: int = 0
    openclaw: int = 0


@dataclass(slots=True)
class AnalyticsCostBreakdown:
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_write_cost: float = 0.0
    cache_read_cost: float = 0.0
    long_context_premium: float = 0.0
    long_context_conversations: int = 0
    total_cost: float = 0.0


@dataclass(slots=True)
class AnalyticsRateValue:
    per_hour: float = 0.0
    per_day: float = 0.0
    per_week: float = 0.0
    per_month: float = 0.0


@dataclass(slots=True)
class AnalyticsTimeSeriesPoint:
    key: str
    label: str
    start: str
    end: str
    estimated_cost: float = 0.0
    claude_estimated_cost: float = 0.0
    codex_estimated_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    conversations: int = 0
    tool_calls: int = 0
    failed_tool_calls: int = 0
    tool_error_rate_pct: float = 0.0
    subagents: int = 0
    claude_input_tokens: int = 0
    claude_output_tokens: int = 0
    claude_cache_write_tokens: int = 0
    claude_cache_read_tokens: int = 0
    claude_reasoning_tokens: int = 0
    claude_total_tokens: int = 0
    claude_conversations: int = 0
    claude_tool_calls: int = 0
    claude_failed_tool_calls: int = 0
    claude_tool_error_rate_pct: float = 0.0
    claude_subagents: int = 0
    openclaw_estimated_cost: float = 0.0
    openclaw_input_tokens: int = 0
    openclaw_output_tokens: int = 0
    openclaw_cache_write_tokens: int = 0
    openclaw_cache_read_tokens: int = 0
    openclaw_reasoning_tokens: int = 0
    openclaw_total_tokens: int = 0
    openclaw_conversations: int = 0
    openclaw_tool_calls: int = 0
    openclaw_failed_tool_calls: int = 0
    openclaw_tool_error_rate_pct: float = 0.0
    openclaw_subagents: int = 0
    codex_input_tokens: int = 0
    codex_output_tokens: int = 0
    codex_cache_write_tokens: int = 0
    codex_cache_read_tokens: int = 0
    codex_reasoning_tokens: int = 0
    codex_total_tokens: int = 0
    codex_conversations: int = 0
    codex_tool_calls: int = 0
    codex_failed_tool_calls: int = 0
    codex_tool_error_rate_pct: float = 0.0
    codex_subagents: int = 0


@dataclass(slots=True)
class AnalyticsTimeSeries:
    hourly: list[AnalyticsTimeSeriesPoint] = field(default_factory=list)
    daily: list[AnalyticsTimeSeriesPoint] = field(default_factory=list)
    weekly: list[AnalyticsTimeSeriesPoint] = field(default_factory=list)
    monthly: list[AnalyticsTimeSeriesPoint] = field(default_factory=list)


@dataclass(slots=True)
class DailyUsage:
    date: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    conversations: int = 0
    subagents: int = 0
    claude_input_tokens: int = 0
    claude_output_tokens: int = 0
    claude_cache_write_tokens: int = 0
    claude_cache_read_tokens: int = 0
    codex_input_tokens: int = 0
    codex_output_tokens: int = 0
    codex_cache_write_tokens: int = 0
    codex_cache_read_tokens: int = 0
    claude_conversations: int = 0
    codex_conversations: int = 0
    openclaw_input_tokens: int = 0
    openclaw_output_tokens: int = 0
    openclaw_cache_write_tokens: int = 0
    openclaw_cache_read_tokens: int = 0
    openclaw_conversations: int = 0
    claude_subagents: int = 0
    codex_subagents: int = 0
    openclaw_subagents: int = 0


@dataclass(slots=True)
class AnalyticsData:
    total_conversations: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_tool_calls: int = 0
    total_failed_tool_calls: int = 0
    model_breakdown: dict[str, int] = field(default_factory=dict)
    tool_breakdown: dict[str, int] = field(default_factory=dict)
    subagent_type_breakdown: dict[str, int] = field(default_factory=dict)
    model_breakdown_by_provider: dict[str, ProviderBreakdown] = field(default_factory=dict)
    tool_breakdown_by_provider: dict[str, ProviderBreakdown] = field(default_factory=dict)
    subagent_type_breakdown_by_provider: dict[str, ProviderBreakdown] = field(default_factory=dict)
    daily_usage: list[DailyUsage] = field(default_factory=list)
    rates: AnalyticsRateValueMap = field(default_factory=dict)
    time_series: AnalyticsTimeSeries = field(default_factory=AnalyticsTimeSeries)
    estimated_cost: float = 0.0
    cost_breakdown: AnalyticsCostBreakdown = field(default_factory=AnalyticsCostBreakdown)
    cost_breakdown_by_provider: dict[str, AnalyticsCostBreakdown] = field(default_factory=dict)
    cost_breakdown_by_model: dict[str, AnalyticsCostBreakdown] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


AnalyticsRateValueMap = dict[str, AnalyticsRateValue]


@dataclass(frozen=True, slots=True)
class AnalyticsWindow:
    start: datetime
    end: datetime
    days: int | None


def filter_analytics_conversations(
    conversations: list[HistoricalConversationSummary],
    *,
    provider: AnalyticsProvider | None = None,
    days: int | None = None,
    now: datetime | None = None,
) -> list[HistoricalConversationSummary]:
    """Apply provider and day-window filtering explicitly for analytics reads.

    The persisted SQLite adapter can return the full historical set, so the
    application layer keeps analytics scoping here instead of burying it in a
    route or store query. Day windows follow the legacy path and filter on the
    conversation end time, while charts still bucket by start time.
    """
    current_time = _ensure_utc(now)
    cutoff = current_time - timedelta(days=days) if days is not None else None
    filtered: list[HistoricalConversationSummary] = []
    for conversation in conversations:
        conversation_provider = provider_for_summary(conversation)
        if provider is not None and conversation_provider != provider:
            continue
        if cutoff is not None:
            ended_at = _parse_datetime(conversation.ended_at)
            if ended_at is None or ended_at < cutoff:
                continue
        filtered.append(conversation)
    return filtered


def build_time_window(
    conversations: list[HistoricalConversationSummary],
    *,
    days: int | None = None,
    now: datetime | None = None,
) -> AnalyticsWindow:
    """Resolve the analytics rate window.

    Explicit day requests use ``now - days``; otherwise the window begins at the
    earliest conversation start so the rate math matches the legacy Node path.
    """
    current_time = _ensure_utc(now)
    if days is not None:
        return AnalyticsWindow(
            start=current_time - timedelta(days=days),
            end=current_time,
            days=days,
        )

    timestamps = [
        timestamp
        for conversation in conversations
        if (timestamp := _parse_datetime(conversation.started_at)) is not None
    ]
    earliest = min(timestamps, default=current_time)
    return AnalyticsWindow(start=earliest, end=current_time, days=None)


def build_analytics(
    conversations: list[HistoricalConversationSummary],
    *,
    days: int | None = None,
    now: datetime | None = None,
) -> AnalyticsData:
    current_time = _ensure_utc(now)
    window = build_time_window(conversations, days=days, now=current_time)
    data = AnalyticsData()
    daily_usage_map: dict[str, DailyUsage] = {}
    time_series_maps: dict[TimeSeriesKey, dict[str, AnalyticsTimeSeriesPoint]] = {
        key: {} for key in TIME_SERIES_KEYS
    }
    total_subagents = 0
    total_tokens_accumulator = 0

    for conversation in conversations:
        provider = provider_for_summary(conversation)
        reasoning_tokens = conversation.total_reasoning_tokens or 0
        conversation_cost = _conversation_cost_breakdown(conversation, provider=provider)
        total_tokens = _analytics_total_tokens(conversation, provider=provider)
        total_tokens_accumulator += total_tokens

        data.total_conversations += 1
        data.total_input_tokens += conversation.total_input_tokens
        data.total_output_tokens += conversation.total_output_tokens
        data.total_cache_creation_tokens += conversation.total_cache_write_tokens
        data.total_cache_read_tokens += conversation.total_cache_read_tokens
        data.total_reasoning_tokens += reasoning_tokens
        data.total_tool_calls += conversation.tool_use_count
        data.total_failed_tool_calls += conversation.failed_tool_call_count
        total_subagents += conversation.subagent_count
        _add_cost_breakdown(data.cost_breakdown, conversation_cost)

        provider_cost = data.cost_breakdown_by_provider.setdefault(provider, AnalyticsCostBreakdown())
        model_key = conversation.model or "unknown"
        model_cost = data.cost_breakdown_by_model.setdefault(model_key, AnalyticsCostBreakdown())
        _add_cost_breakdown(provider_cost, conversation_cost)
        _add_cost_breakdown(model_cost, conversation_cost)

        if conversation.model:
            data.model_breakdown[conversation.model] = data.model_breakdown.get(conversation.model, 0) + 1
            _increment_provider_breakdown(
                data.model_breakdown_by_provider,
                conversation.model,
                provider,
                1,
            )

        for tool_name, count in conversation.tool_breakdown.items():
            data.tool_breakdown[tool_name] = data.tool_breakdown.get(tool_name, 0) + count
            _increment_provider_breakdown(data.tool_breakdown_by_provider, tool_name, provider, count)

        for subagent_type, count in conversation.subagent_type_breakdown.items():
            data.subagent_type_breakdown[subagent_type] = (
                data.subagent_type_breakdown.get(subagent_type, 0) + count
            )
            _increment_provider_breakdown(
                data.subagent_type_breakdown_by_provider,
                subagent_type,
                provider,
                count,
            )

        started_at = _parse_datetime(conversation.started_at)
        if started_at is None:
            continue

        date_key = _isoformat(started_at)[:10]
        daily_usage = daily_usage_map.setdefault(date_key, DailyUsage(date=date_key))
        daily_usage.input_tokens += conversation.total_input_tokens
        daily_usage.output_tokens += conversation.total_output_tokens
        daily_usage.cache_write_tokens += conversation.total_cache_write_tokens
        daily_usage.cache_read_tokens += conversation.total_cache_read_tokens
        daily_usage.conversations += 1
        daily_usage.subagents += conversation.subagent_count
        if provider == "claude":
            daily_usage.claude_input_tokens += conversation.total_input_tokens
            daily_usage.claude_output_tokens += conversation.total_output_tokens
            daily_usage.claude_cache_write_tokens += conversation.total_cache_write_tokens
            daily_usage.claude_cache_read_tokens += conversation.total_cache_read_tokens
            daily_usage.claude_conversations += 1
            daily_usage.claude_subagents += conversation.subagent_count
        elif provider == "codex":
            daily_usage.codex_input_tokens += conversation.total_input_tokens
            daily_usage.codex_output_tokens += conversation.total_output_tokens
            daily_usage.codex_cache_write_tokens += conversation.total_cache_write_tokens
            daily_usage.codex_cache_read_tokens += conversation.total_cache_read_tokens
            daily_usage.codex_conversations += 1
            daily_usage.codex_subagents += conversation.subagent_count
        else:
            daily_usage.openclaw_input_tokens += conversation.total_input_tokens
            daily_usage.openclaw_output_tokens += conversation.total_output_tokens
            daily_usage.openclaw_cache_write_tokens += conversation.total_cache_write_tokens
            daily_usage.openclaw_cache_read_tokens += conversation.total_cache_read_tokens
            daily_usage.openclaw_conversations += 1
            daily_usage.openclaw_subagents += conversation.subagent_count

        for key in TIME_SERIES_KEYS:
            bucket_start = _bucket_start(started_at, key)
            bucket_id = _isoformat(bucket_start)
            bucket = time_series_maps[key].setdefault(bucket_id, _create_empty_time_series_point(bucket_start, key))
            bucket.estimated_cost += conversation_cost.total_cost
            bucket.input_tokens += conversation.total_input_tokens
            bucket.output_tokens += conversation.total_output_tokens
            bucket.cache_write_tokens += conversation.total_cache_write_tokens
            bucket.cache_read_tokens += conversation.total_cache_read_tokens
            bucket.reasoning_tokens += reasoning_tokens
            bucket.total_tokens += total_tokens
            bucket.conversations += 1
            bucket.tool_calls += conversation.tool_use_count
            bucket.failed_tool_calls += conversation.failed_tool_call_count
            bucket.subagents += conversation.subagent_count
            if provider == "claude":
                bucket.claude_estimated_cost += conversation_cost.total_cost
                bucket.claude_input_tokens += conversation.total_input_tokens
                bucket.claude_output_tokens += conversation.total_output_tokens
                bucket.claude_cache_write_tokens += conversation.total_cache_write_tokens
                bucket.claude_cache_read_tokens += conversation.total_cache_read_tokens
                bucket.claude_reasoning_tokens += reasoning_tokens
                bucket.claude_total_tokens += total_tokens
                bucket.claude_conversations += 1
                bucket.claude_tool_calls += conversation.tool_use_count
                bucket.claude_failed_tool_calls += conversation.failed_tool_call_count
                bucket.claude_subagents += conversation.subagent_count
            elif provider == "codex":
                bucket.codex_estimated_cost += conversation_cost.total_cost
                bucket.codex_input_tokens += conversation.total_input_tokens
                bucket.codex_output_tokens += conversation.total_output_tokens
                bucket.codex_cache_write_tokens += conversation.total_cache_write_tokens
                bucket.codex_cache_read_tokens += conversation.total_cache_read_tokens
                bucket.codex_reasoning_tokens += reasoning_tokens
                bucket.codex_total_tokens += total_tokens
                bucket.codex_conversations += 1
                bucket.codex_tool_calls += conversation.tool_use_count
                bucket.codex_failed_tool_calls += conversation.failed_tool_call_count
                bucket.codex_subagents += conversation.subagent_count
            else:
                bucket.openclaw_estimated_cost += conversation_cost.total_cost
                bucket.openclaw_input_tokens += conversation.total_input_tokens
                bucket.openclaw_output_tokens += conversation.total_output_tokens
                bucket.openclaw_cache_write_tokens += conversation.total_cache_write_tokens
                bucket.openclaw_cache_read_tokens += conversation.total_cache_read_tokens
                bucket.openclaw_reasoning_tokens += reasoning_tokens
                bucket.openclaw_total_tokens += total_tokens
                bucket.openclaw_conversations += 1
                bucket.openclaw_tool_calls += conversation.tool_use_count
                bucket.openclaw_failed_tool_calls += conversation.failed_tool_call_count
                bucket.openclaw_subagents += conversation.subagent_count

    total_tokens = total_tokens_accumulator
    data.estimated_cost = data.cost_breakdown.total_cost
    data.daily_usage = [daily_usage_map[key] for key in sorted(daily_usage_map)]
    data.rates = _build_rates(
        window,
        estimated_cost=data.estimated_cost,
        total_tokens=total_tokens,
        total_input_tokens=data.total_input_tokens,
        total_output_tokens=data.total_output_tokens,
        total_cache_creation_tokens=data.total_cache_creation_tokens,
        total_cache_read_tokens=data.total_cache_read_tokens,
        total_reasoning_tokens=data.total_reasoning_tokens,
        conversations=data.total_conversations,
        tool_calls=data.total_tool_calls,
        failed_tool_calls=data.total_failed_tool_calls,
        subagents=total_subagents,
    )
    data.time_series = AnalyticsTimeSeries(
        hourly=_materialize_time_series(time_series_maps["hourly"], "hourly"),
        daily=_materialize_time_series(time_series_maps["daily"], "daily"),
        weekly=_materialize_time_series(time_series_maps["weekly"], "weekly"),
        monthly=_materialize_time_series(time_series_maps["monthly"], "monthly"),
    )
    return data


def provider_for_summary(conversation: HistoricalConversationSummary) -> AnalyticsProvider:
    """Infer provider using canonical semantic resolution rules."""
    return resolve_provider(
        model=conversation.model,
        provider=conversation.provider,
        project_path=conversation.project_path,
    )


def _analytics_total_tokens(
    conversation: HistoricalConversationSummary,
    *,
    provider: AnalyticsProvider,
) -> int:
    if provider == "codex":
        return conversation.total_input_tokens + conversation.total_output_tokens
    return (
        conversation.total_input_tokens
        + conversation.total_output_tokens
        + conversation.total_cache_write_tokens
        + conversation.total_cache_read_tokens
        + (conversation.total_reasoning_tokens or 0)
    )


def _conversation_cost_breakdown(
    conversation: HistoricalConversationSummary,
    *,
    provider: AnalyticsProvider,
) -> AnalyticsCostBreakdown:
    if provider == "openclaw" and not _openclaw_has_known_cost_model(conversation.model):
        return AnalyticsCostBreakdown()

    cost = calculate_cost(
        input_tokens=conversation.total_input_tokens,
        output_tokens=conversation.total_output_tokens,
        cache_write_tokens=conversation.total_cache_write_tokens,
        cache_read_tokens=conversation.total_cache_read_tokens,
        model=conversation.model,
    )
    long_context_premium = 0.0
    long_context_conversations = 0
    if conversation.total_input_tokens > 200_000 and supports_long_context_premium(conversation.model):
        long_context_premium = cost.input_cost + (cost.output_cost * 0.5) + cost.cache_write_cost + cost.cache_read_cost
        long_context_conversations = 1

    return AnalyticsCostBreakdown(
        input_cost=cost.input_cost,
        output_cost=cost.output_cost,
        cache_write_cost=cost.cache_write_cost,
        cache_read_cost=cost.cache_read_cost,
        long_context_premium=long_context_premium,
        long_context_conversations=long_context_conversations,
        total_cost=cost.total_cost + long_context_premium,
    )


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


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _bucket_start(timestamp: datetime, key: TimeSeriesKey) -> datetime:
    dt = timestamp.astimezone(UTC)
    if key == "hourly":
        return dt.replace(minute=0, second=0, microsecond=0)
    if key == "daily":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if key == "weekly":
        day_delta = dt.weekday()
        start = dt - timedelta(days=day_delta)
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_bucket_start(start: datetime, key: TimeSeriesKey) -> datetime:
    if key == "hourly":
        return start + timedelta(hours=1)
    if key == "daily":
        return start + timedelta(days=1)
    if key == "weekly":
        return start + timedelta(days=7)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1, day=1)
    return start.replace(month=start.month + 1, day=1)


def _format_bucket_label(start: datetime, key: TimeSeriesKey) -> str:
    iso = _isoformat(start)
    if key == "hourly":
        return iso[5:13].replace("T", " ") + ":00"
    if key == "daily":
        return iso[:10]
    if key == "weekly":
        return f"Week of {iso[:10]}"
    return iso[:7]


def _create_empty_time_series_point(start: datetime, key: TimeSeriesKey) -> AnalyticsTimeSeriesPoint:
    return AnalyticsTimeSeriesPoint(
        key=_isoformat(start),
        label=_format_bucket_label(start, key),
        start=_isoformat(start),
        end=_isoformat(_next_bucket_start(start, key)),
    )


def _materialize_time_series(
    buckets: dict[str, AnalyticsTimeSeriesPoint],
    key: TimeSeriesKey,
) -> list[AnalyticsTimeSeriesPoint]:
    if not buckets:
        return []
    ordered_keys = sorted(buckets)
    first = _parse_datetime(ordered_keys[0])
    last = _parse_datetime(ordered_keys[-1])
    if first is None or last is None:
        return []
    points: list[AnalyticsTimeSeriesPoint] = []
    cursor = first
    while cursor <= last:
        bucket_key = _isoformat(cursor)
        point = buckets.get(bucket_key)
        if point is None:
            point = _create_empty_time_series_point(cursor, key)
        _apply_tool_error_rates(point)
        points.append(point)
        cursor = _next_bucket_start(cursor, key)
    return points


def _apply_tool_error_rates(point: AnalyticsTimeSeriesPoint) -> None:
    point.tool_error_rate_pct = (point.failed_tool_calls / point.tool_calls) * 100 if point.tool_calls else 0.0
    point.claude_tool_error_rate_pct = (
        (point.claude_failed_tool_calls / point.claude_tool_calls) * 100 if point.claude_tool_calls else 0.0
    )
    point.codex_tool_error_rate_pct = (
        (point.codex_failed_tool_calls / point.codex_tool_calls) * 100 if point.codex_tool_calls else 0.0
    )
    point.openclaw_tool_error_rate_pct = (
        (point.openclaw_failed_tool_calls / point.openclaw_tool_calls) * 100 if point.openclaw_tool_calls else 0.0
    )


def _increment_provider_breakdown(
    mapping: dict[str, ProviderBreakdown],
    key: str,
    provider: AnalyticsProvider,
    count: int,
) -> None:
    entry = mapping.setdefault(key, ProviderBreakdown())
    if provider == "claude":
        entry.claude += count
    elif provider == "codex":
        entry.codex += count
    else:
        entry.openclaw += count


def _add_cost_breakdown(target: AnalyticsCostBreakdown, source: AnalyticsCostBreakdown) -> None:
    target.input_cost += source.input_cost
    target.output_cost += source.output_cost
    target.cache_write_cost += source.cache_write_cost
    target.cache_read_cost += source.cache_read_cost
    target.long_context_premium += source.long_context_premium
    target.long_context_conversations += source.long_context_conversations
    target.total_cost += source.total_cost


def _build_rate_value(total: float, hours: float, days: float) -> AnalyticsRateValue:
    return AnalyticsRateValue(
        per_hour=total / hours,
        per_day=total / days,
        per_week=(total / days) * 7,
        per_month=(total / days) * 30,
    )


def _build_rates(
    window: AnalyticsWindow,
    *,
    estimated_cost: float,
    total_tokens: int,
    total_input_tokens: int,
    total_output_tokens: int,
    total_cache_creation_tokens: int,
    total_cache_read_tokens: int,
    total_reasoning_tokens: int,
    conversations: int,
    tool_calls: int,
    failed_tool_calls: int,
    subagents: int,
) -> AnalyticsRateValueMap:
    duration_ms = max((window.end - window.start).total_seconds() * 1000, 60 * 60 * 1000)
    duration_hours = max(duration_ms / (60 * 60 * 1000), 1.0)
    duration_days = max(duration_ms / (24 * 60 * 60 * 1000), 1 / 24)
    return {
        "spend": _build_rate_value(estimated_cost, duration_hours, duration_days),
        "total_tokens": _build_rate_value(total_tokens, duration_hours, duration_days),
        "input_tokens": _build_rate_value(total_input_tokens, duration_hours, duration_days),
        "output_tokens": _build_rate_value(total_output_tokens, duration_hours, duration_days),
        "cache_write_tokens": _build_rate_value(total_cache_creation_tokens, duration_hours, duration_days),
        "cache_read_tokens": _build_rate_value(total_cache_read_tokens, duration_hours, duration_days),
        "reasoning_tokens": _build_rate_value(total_reasoning_tokens, duration_hours, duration_days),
        "conversations": _build_rate_value(conversations, duration_hours, duration_days),
        "tool_calls": _build_rate_value(tool_calls, duration_hours, duration_days),
        "failed_tool_calls": _build_rate_value(failed_tool_calls, duration_hours, duration_days),
        "subagents": _build_rate_value(subagents, duration_hours, duration_days),
    }
