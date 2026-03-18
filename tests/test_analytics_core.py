"""Tests for the backend analytics core."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from helaicopter_api.application.analytics import get_analytics
from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
from helaicopter_api.pure.analytics import (
    build_analytics,
    build_time_window,
    filter_analytics_conversations,
)


def _summary(
    conversation_id: str,
    *,
    provider: str = "claude",
    project_path: str = "-Users-tony-Code-helaicopter",
    started_at: str,
    ended_at: str,
    model: str | None,
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    total_cache_write_tokens: int = 0,
    total_cache_read_tokens: int = 0,
    total_reasoning_tokens: int = 0,
    tool_use_count: int = 0,
    failed_tool_call_count: int = 0,
    tool_breakdown: dict[str, int] | None = None,
    subagent_count: int = 0,
    subagent_type_breakdown: dict[str, int] | None = None,
) -> HistoricalConversationSummary:
    return HistoricalConversationSummary(
        conversation_id=conversation_id,
        provider=provider,
        session_id=f"session-{conversation_id}",
        project_path=project_path,
        project_name="helaicopter",
        first_message="Ship the analytics port",
        started_at=started_at,
        ended_at=ended_at,
        message_count=3,
        model=model,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cache_write_tokens=total_cache_write_tokens,
        total_cache_read_tokens=total_cache_read_tokens,
        total_reasoning_tokens=total_reasoning_tokens,
        tool_use_count=tool_use_count,
        failed_tool_call_count=failed_tool_call_count,
        tool_breakdown=tool_breakdown or {},
        subagent_count=subagent_count,
        subagent_type_breakdown=subagent_type_breakdown or {},
        task_count=1,
    )


class TestPureAnalyticsFiltering:
    def test_filtering_is_explicit_for_provider_and_day_window(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        recent_claude = _summary(
            "claude-recent",
            started_at="2026-03-16T09:00:00Z",
            ended_at="2026-03-16T10:00:00Z",
            model="claude-sonnet-4-5-20250929",
        )
        recent_codex = _summary(
            "codex-recent",
            provider="claude",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at="2026-03-17T08:00:00Z",
            ended_at="2026-03-17T09:00:00Z",
            model="gpt-5",
        )
        old_claude = _summary(
            "claude-old",
            started_at="2026-03-10T09:00:00Z",
            ended_at="2026-03-10T10:00:00Z",
            model="claude-sonnet-4-5-20250929",
        )
        missing_end = _summary(
            "missing-end",
            started_at="2026-03-17T09:00:00Z",
            ended_at="",
            model="claude-sonnet-4-5-20250929",
        )

        filtered = filter_analytics_conversations(
            [recent_claude, recent_codex, old_claude, missing_end],
            days=3,
            now=now,
        )

        assert [conversation.conversation_id for conversation in filtered] == [
            "claude-recent",
            "codex-recent",
        ]

        codex_only = filter_analytics_conversations(filtered, provider="codex", now=now)
        assert [conversation.conversation_id for conversation in codex_only] == ["codex-recent"]

    def test_time_windows_use_requested_days_or_earliest_start(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        conversations = [
            _summary(
                "first",
                started_at="2026-03-11T07:00:00Z",
                ended_at="2026-03-11T08:00:00Z",
                model="claude-sonnet-4-5-20250929",
            ),
            _summary(
                "second",
                started_at="2026-03-15T10:00:00Z",
                ended_at="2026-03-15T11:00:00Z",
                model="gpt-5",
            ),
        ]

        explicit_window = build_time_window(conversations, days=7, now=now)
        assert explicit_window.start == datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
        assert explicit_window.end == now
        assert explicit_window.days == 7

        inferred_window = build_time_window(conversations, now=now)
        assert inferred_window.start == datetime(2026, 3, 11, 7, 0, tzinfo=UTC)
        assert inferred_window.end == now
        assert inferred_window.days is None


class TestPureAnalyticsAggregation:
    def test_build_analytics_preserves_provider_splits_and_bucketing(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        claude = _summary(
            "claude-1",
            started_at="2026-03-16T09:15:00Z",
            ended_at="2026-03-16T09:45:00Z",
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=100_000,
            total_output_tokens=50_000,
            total_cache_write_tokens=10_000,
            total_cache_read_tokens=20_000,
            total_reasoning_tokens=5_000,
            tool_use_count=2,
            failed_tool_call_count=1,
            tool_breakdown={"read_file": 2},
            subagent_count=1,
            subagent_type_breakdown={"planner": 1},
        )
        codex = _summary(
            "codex-1",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at="2026-03-17T11:00:00Z",
            ended_at="2026-03-17T11:30:00Z",
            model="gpt-5",
            total_input_tokens=200_000,
            total_output_tokens=20_000,
            total_cache_write_tokens=50_000,
            total_cache_read_tokens=10_000,
            total_reasoning_tokens=15_000,
            tool_use_count=4,
            failed_tool_call_count=1,
            tool_breakdown={"search": 3, "read_file": 1},
            subagent_count=2,
            subagent_type_breakdown={"researcher": 2},
        )

        analytics = build_analytics([claude, codex], days=7, now=now)

        assert analytics.total_conversations == 2
        assert analytics.total_input_tokens == 300_000
        assert analytics.total_output_tokens == 70_000
        assert analytics.total_cache_creation_tokens == 60_000
        assert analytics.total_cache_read_tokens == 30_000
        assert analytics.total_reasoning_tokens == 20_000
        assert analytics.total_tool_calls == 6
        assert analytics.total_failed_tool_calls == 2

        assert analytics.tool_breakdown == {"read_file": 3, "search": 3}
        assert analytics.tool_breakdown_by_provider["read_file"].claude == 2
        assert analytics.tool_breakdown_by_provider["read_file"].codex == 1
        assert analytics.subagent_type_breakdown_by_provider["planner"].claude == 1
        assert analytics.subagent_type_breakdown_by_provider["researcher"].codex == 2
        assert analytics.model_breakdown_by_provider["claude-sonnet-4-5-20250929"].claude == 1
        assert analytics.model_breakdown_by_provider["gpt-5"].codex == 1

        assert [entry.date for entry in analytics.daily_usage] == ["2026-03-16", "2026-03-17"]
        assert analytics.daily_usage[0].claude_conversations == 1
        assert analytics.daily_usage[1].codex_conversations == 1

        assert len(analytics.time_series.daily) == 2
        first_day, second_day = analytics.time_series.daily
        assert first_day.claude_conversations == 1
        assert first_day.codex_conversations == 0
        assert first_day.tool_error_rate_pct == pytest.approx(50.0)
        assert second_day.codex_conversations == 1
        assert second_day.claude_conversations == 0
        assert second_day.codex_tool_error_rate_pct == pytest.approx(25.0)

        assert analytics.cost_breakdown_by_provider["claude"].total_cost == pytest.approx(1.0935)
        assert analytics.cost_breakdown_by_provider["codex"].total_cost == pytest.approx(0.45125)
        assert analytics.estimated_cost == pytest.approx(1.54475)

    def test_build_analytics_preserves_cache_and_long_context_pricing_rules(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        long_context_claude = _summary(
            "claude-long",
            started_at="2026-03-17T07:00:00Z",
            ended_at="2026-03-17T08:00:00Z",
            model="claude-opus-4-6",
            total_input_tokens=300_000,
            total_output_tokens=100_000,
            total_cache_write_tokens=50_000,
            total_cache_read_tokens=25_000,
        )
        codex = _summary(
            "codex-cache",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at="2026-03-17T09:00:00Z",
            ended_at="2026-03-17T09:10:00Z",
            model="gpt-5",
            total_input_tokens=120_000,
            total_output_tokens=30_000,
            total_cache_write_tokens=40_000,
            total_cache_read_tokens=10_000,
        )

        analytics = build_analytics([long_context_claude, codex], days=1, now=now)

        claude_cost = analytics.cost_breakdown_by_provider["claude"]
        codex_cost = analytics.cost_breakdown_by_provider["codex"]

        assert claude_cost.input_cost == pytest.approx(1.5)
        assert claude_cost.output_cost == pytest.approx(2.5)
        assert claude_cost.cache_write_cost == pytest.approx(0.3125)
        assert claude_cost.cache_read_cost == pytest.approx(0.0125)
        assert claude_cost.long_context_premium == pytest.approx(3.075)
        assert claude_cost.long_context_conversations == 1
        assert claude_cost.total_cost == pytest.approx(7.4)

        assert codex_cost.input_cost == pytest.approx(0.15)
        assert codex_cost.output_cost == pytest.approx(0.3)
        assert codex_cost.cache_write_cost == pytest.approx(0.0)
        assert codex_cost.cache_read_cost == pytest.approx(0.00125)
        assert codex_cost.long_context_premium == pytest.approx(0.0)
        assert codex_cost.total_cost == pytest.approx(0.45125)


class TestApplicationAnalytics:
    def test_application_layer_loads_persisted_summaries_then_applies_explicit_filters(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        conversations = [
            _summary(
                "claude-recent",
                started_at="2026-03-17T06:00:00Z",
                ended_at="2026-03-17T07:00:00Z",
                model="claude-sonnet-4-5-20250929",
                total_input_tokens=10_000,
            ),
            _summary(
                "codex-recent",
                provider="codex",
                project_path="codex:-Users-tony-Code-helaicopter",
                started_at="2026-03-17T08:00:00Z",
                ended_at="2026-03-17T09:00:00Z",
                model="gpt-5",
                total_input_tokens=20_000,
            ),
            _summary(
                "codex-old",
                provider="codex",
                project_path="codex:-Users-tony-Code-helaicopter",
                started_at="2026-03-12T08:00:00Z",
                ended_at="2026-03-12T09:00:00Z",
                model="gpt-5",
                total_input_tokens=30_000,
            ),
        ]

        class StubStore:
            def __init__(self, rows: list[HistoricalConversationSummary]) -> None:
                self.rows = rows
                self.calls: list[dict[str, object]] = []

            def list_historical_conversations(self, **kwargs: object) -> list[HistoricalConversationSummary]:
                self.calls.append(kwargs)
                return list(self.rows)

        store = StubStore(conversations)
        services = SimpleNamespace(app_sqlite_store=store)

        response = get_analytics(services, days=1, provider="codex", now=now)

        assert store.calls == [{}]
        assert response.total_conversations == 1
        assert response.total_input_tokens == 20_000
        assert response.cost_breakdown_by_provider["codex"].input_cost == pytest.approx(0.025)
        assert "claude" not in response.cost_breakdown_by_provider

    def test_application_layer_rejects_unknown_provider(self) -> None:
        services = SimpleNamespace(app_sqlite_store=SimpleNamespace(list_historical_conversations=lambda: []))

        with pytest.raises(ValueError, match="Unsupported analytics provider"):
            get_analytics(services, provider="openai")
