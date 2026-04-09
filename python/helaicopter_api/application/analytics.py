"""Application-layer analytics logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.application.conversations import list_conversations
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.application.conversation_refs import derive_route_slug
from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
from helaicopter_api.pure.analytics import build_analytics, filter_analytics_conversations
from helaicopter_api.schema.analytics import AnalyticsDataResponse
from helaicopter_api.schema.conversations import ConversationSummaryResponse
from helaicopter_db.db import create_olap_engine
from helaicopter_domain.vocab import ProviderName


RECENT_SUPPLEMENT_HOURS = 6
_LIVE_CONVERSATION_SERVICE_ATTRS = (
    "cache",
    "settings",
    "claude_conversation_reader",
    "codex_store",
    "openclaw_store",
)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_analytics(
    services: InstanceOf[BackendServices],
    *,
    days: int | None = None,
    provider: str | None = None,
    now: datetime | None = None,
) -> AnalyticsDataResponse:
    """Load persisted summaries, apply analytics filters, and aggregate the response.

    Merges warehouse and SQLite conversation summaries, applies optional
    provider and time-period filters, then delegates to the pure analytics
    layer to compute token counts, costs, and per-day buckets.

    Args:
        services: Initialised backend services providing the SQLite store and
            optional OLAP warehouse connection.
        days: Optional rolling window in days. When ``None`` all available
            history is included.
        provider: Optional provider filter (``"claude"``, ``"codex"``, or
            ``"all"``/``None`` for no filtering).
        now: Reference timestamp used as the end of the rolling window.
            Defaults to the current UTC time when omitted.

    Returns:
        Aggregated analytics data including token counts, costs, conversation
        counts, and per-day time-series buckets.

    Raises:
        ValueError: If ``provider`` is not one of the supported values.
    """
    normalized_provider = _normalize_provider(provider)
    current_time = _ensure_utc(now)
    conversations = _load_authoritative_analytics_conversations(services, now=current_time)
    filtered = filter_analytics_conversations(
        conversations,
        provider=normalized_provider,
        days=days,
        now=current_time,
    )
    analytics = build_analytics(filtered, days=days, now=current_time)
    return AnalyticsDataResponse.model_validate(analytics.to_dict())


def _normalize_provider(provider: str | None) -> ProviderName | None:
    if provider is None or provider == "all":
        return None
    if provider in {"claude", "codex", "openclaw"}:
        return cast(ProviderName, provider)
    raise ValueError(f"Unsupported analytics provider: {provider}")


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _load_authoritative_analytics_conversations(
    services: BackendServices,
    *,
    now: datetime,
) -> list[HistoricalConversationSummary]:
    warehouse_rows = list_warehouse_historical_conversations(services)
    sqlite_rows = services.app_sqlite_store.list_historical_conversations()
    supplement_cutoff = now - timedelta(hours=RECENT_SUPPLEMENT_HOURS)
    combined: dict[tuple[str, str, str | None], HistoricalConversationSummary]

    if warehouse_rows:
        combined = {_analytics_identity_key(row): row for row in warehouse_rows}
        for row in sqlite_rows:
            ended_at = _ended_at_or_none(row)
            if ended_at is None or ended_at >= supplement_cutoff:
                combined[_analytics_identity_key(row)] = row
    else:
        combined = {_analytics_identity_key(row): row for row in sqlite_rows}

    for summary in _list_live_analytics_conversations(services):
        live_row = _historical_summary_from_live_summary(summary)
        existing = combined.get(_analytics_identity_key(live_row))
        if existing is None or _should_replace_analytics_summary(existing, live_row):
            combined[_analytics_identity_key(live_row)] = live_row

    return list(combined.values())


def _list_live_analytics_conversations(
    services: BackendServices,
) -> list[ConversationSummaryResponse]:
    if not _supports_live_conversation_supplement(services):
        return []
    return list_conversations(services)


def _supports_live_conversation_supplement(services: BackendServices) -> bool:
    return all(hasattr(services, attribute) for attribute in _LIVE_CONVERSATION_SERVICE_ATTRS)


def list_warehouse_historical_conversations(
    services: BackendServices,
) -> list[HistoricalConversationSummary]:
    """Query the OLAP warehouse for historical conversation summaries.

    Connects to the configured DuckDB/OLAP engine, executes the fact-table
    join query, and returns one ``HistoricalConversationSummary`` per row.
    Returns an empty list when the engine is unavailable or the query fails.

    Args:
        services: Initialised backend services; ``services.settings`` is used
            to create the OLAP engine connection.

    Returns:
        List of conversation summaries sourced from the warehouse, or an empty
        list if the warehouse is unconfigured or a ``SQLAlchemyError`` is raised.
    """
    settings = getattr(services, "settings", None)
    if settings is None:
        return []

    engine = create_olap_engine(settings)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                      fact.conversation_id,
                      fact.provider,
                      fact.session_id,
                      fact.started_at,
                      fact.ended_at,
                      fact.first_message,
                      fact.message_count,
                      fact.total_input_tokens,
                      fact.total_output_tokens,
                      fact.total_cache_write_tokens,
                      fact.total_cache_read_tokens,
                      fact.total_reasoning_tokens,
                      fact.tool_use_count,
                      fact.subagent_count,
                      fact.task_count,
                      project.project_path,
                      project.project_name,
                      model.model_name AS model
                    FROM fact_conversations AS fact
                    JOIN dim_projects AS project
                      ON project.project_id = fact.project_id
                    LEFT JOIN dim_models AS model
                      ON model.model_id = fact.model_id
                    ORDER BY fact.ended_at DESC
                    """
                )
            )
            return [
                HistoricalConversationSummary(
                    conversation_id=str(row.conversation_id),
                    provider=str(row.provider),
                    session_id=str(row.session_id),
                    project_path=str(row.project_path),
                    project_name=str(row.project_name),
                    first_message=str(row.first_message),
                    route_slug=derive_route_slug(str(row.first_message)),
                    started_at=_serialize_datetime(row.started_at),
                    ended_at=_serialize_datetime(row.ended_at),
                    message_count=int(row.message_count or 0),
                    model=str(row.model) if row.model is not None else None,
                    total_input_tokens=int(row.total_input_tokens or 0),
                    total_output_tokens=int(row.total_output_tokens or 0),
                    total_cache_write_tokens=int(row.total_cache_write_tokens or 0),
                    total_cache_read_tokens=int(row.total_cache_read_tokens or 0),
                    total_reasoning_tokens=int(row.total_reasoning_tokens or 0),
                    tool_use_count=int(row.tool_use_count or 0),
                    subagent_count=int(row.subagent_count or 0),
                    task_count=int(row.task_count or 0),
                )
                for row in rows
            ]
    except SQLAlchemyError:
        return []
    finally:
        engine.dispose()


def _ended_at_or_none(row: HistoricalConversationSummary) -> datetime | None:
    raw = row.ended_at
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _serialize_datetime(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def _analytics_identity_key(row: HistoricalConversationSummary) -> tuple[str, str, str | None]:
    provider = row.provider
    return (
        row.project_path if provider == "openclaw" else provider,
        row.session_id,
        row.project_path if provider == "openclaw" else None,
    )


def _historical_summary_from_live_summary(
    summary: ConversationSummaryResponse,
) -> HistoricalConversationSummary:
    provider = summary.provider or _provider_from_project_path(summary.project_path)
    return HistoricalConversationSummary(
        conversation_id=_live_conversation_id(summary, provider=provider),
        provider=provider,
        session_id=summary.session_id,
        project_path=summary.project_path,
        project_name=summary.project_name,
        thread_type=summary.thread_type,
        first_message=summary.first_message,
        route_slug=summary.route_slug,
        started_at=_epoch_ms_to_iso(summary.created_at),
        ended_at=_epoch_ms_to_iso(summary.last_updated_at),
        message_count=summary.message_count,
        model=summary.model,
        git_branch=summary.git_branch,
        reasoning_effort=summary.reasoning_effort,
        speed=summary.speed,
        total_input_tokens=summary.total_input_tokens,
        total_output_tokens=summary.total_output_tokens,
        total_cache_write_tokens=summary.total_cache_creation_tokens,
        total_cache_read_tokens=summary.total_cache_read_tokens,
        total_reasoning_tokens=summary.total_reasoning_tokens or 0,
        tool_use_count=summary.tool_use_count,
        failed_tool_call_count=summary.failed_tool_call_count,
        tool_breakdown=dict(summary.tool_breakdown),
        subagent_count=summary.subagent_count,
        subagent_type_breakdown=dict(summary.subagent_type_breakdown),
        task_count=summary.task_count,
    )


def _should_replace_analytics_summary(
    existing: HistoricalConversationSummary,
    candidate: HistoricalConversationSummary,
) -> bool:
    existing_ended_at = _ended_at_or_none(existing)
    candidate_ended_at = _ended_at_or_none(candidate)
    if existing_ended_at is None:
        return False
    if candidate_ended_at is None:
        return True
    return candidate_ended_at >= existing_ended_at


def _epoch_ms_to_iso(value: float) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat().replace("+00:00", "Z")


def _live_conversation_id(summary: ConversationSummaryResponse, *, provider: str) -> str:
    if provider == "openclaw":
        return f"{summary.project_path}::{summary.session_id}"
    return f"{provider}:{summary.session_id}"


def _provider_from_project_path(project_path: str) -> str:
    if project_path.startswith("openclaw:"):
        return "openclaw"
    if project_path.startswith("codex:"):
        return "codex"
    return "claude"
