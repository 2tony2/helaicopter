"""Application-layer analytics orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.pure.analytics import build_analytics, filter_analytics_conversations
from helaicopter_api.schema.analytics import AnalyticsDataResponse
from helaicopter_domain.vocab import ProviderName


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_analytics(
    services: InstanceOf[BackendServices],
    *,
    days: int | None = None,
    provider: str | None = None,
    now: datetime | None = None,
) -> AnalyticsDataResponse:
    """Load persisted summaries, apply analytics filters, and aggregate the response."""
    normalized_provider = _normalize_provider(provider)
    current_time = _ensure_utc(now)
    conversations = services.app_sqlite_store.list_historical_conversations()
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
    if provider in {"claude", "codex"}:
        return cast(ProviderName, provider)
    raise ValueError(f"Unsupported analytics provider: {provider}")


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
