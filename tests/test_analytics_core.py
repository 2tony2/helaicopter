"""Tests for the backend analytics core."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from helaicopter_api.application.analytics import get_analytics
from helaicopter_api.application import analytics as analytics_application
from helaicopter_api.application.conversation_refs import derive_route_slug
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
from helaicopter_api.pure.analytics import (
    build_analytics,
    build_time_window,
    filter_analytics_conversations,
)
from helaicopter_api.schema.conversations import ConversationSummaryResponse


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


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
        route_slug=derive_route_slug("Ship the analytics port"),
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

    def test_filtering_can_return_only_openclaw_conversations(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        recent_openclaw = _summary(
            "openclaw-recent",
            provider="openclaw",
            project_path="openclaw:agent:main",
            started_at="2026-03-17T08:00:00Z",
            ended_at="2026-03-17T08:30:00Z",
            model="openclaw-v1",
        )
        recent_claude = _summary(
            "claude-recent",
            started_at="2026-03-17T09:00:00Z",
            ended_at="2026-03-17T09:30:00Z",
            model="claude-sonnet-4-5-20250929",
        )
        recent_codex = _summary(
            "codex-recent",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at="2026-03-17T10:00:00Z",
            ended_at="2026-03-17T10:30:00Z",
            model="gpt-5",
        )

        filtered = filter_analytics_conversations(
            [recent_openclaw, recent_claude, recent_codex],
            provider="openclaw",
            days=3,
            now=now,
        )

        assert [conversation.conversation_id for conversation in filtered] == ["openclaw-recent"]

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
    def test_build_analytics_keeps_day_scoped_aggregation_to_one_main_pass(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)

        class SinglePassConversationList(list[HistoricalConversationSummary]):
            def __init__(self, items: list[HistoricalConversationSummary]) -> None:
                super().__init__(items)
                self.iterations = 0

            def __iter__(self):  # type: ignore[override]
                self.iterations += 1
                if self.iterations > 1:
                    raise AssertionError("day-scoped analytics should not re-iterate conversations after the main loop")
                return super().__iter__()

        conversations = SinglePassConversationList(
            [
                _summary(
                    "claude-1",
                    started_at="2026-03-17T09:15:00Z",
                    ended_at="2026-03-17T09:45:00Z",
                    model="claude-sonnet-4-5-20250929",
                    subagent_count=1,
                ),
                _summary(
                    "codex-1",
                    provider="codex",
                    project_path="codex:-Users-tony-Code-helaicopter",
                    started_at="2026-03-17T11:00:00Z",
                    ended_at="2026-03-17T11:30:00Z",
                    model="gpt-5",
                    subagent_count=2,
                ),
            ]
        )

        analytics = build_analytics(conversations, days=1, now=now)

        assert analytics.rates["subagents"].per_day == pytest.approx(3.0)

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

    def test_build_analytics_keeps_openclaw_counts_costs_and_tool_breakdowns_separate(self) -> None:
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
            tool_use_count=2,
            tool_breakdown={"read_file": 2},
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
            tool_use_count=4,
            failed_tool_call_count=1,
            tool_breakdown={"search": 3, "read_file": 1},
        )
        openclaw = _summary(
            "openclaw-1",
            provider="openclaw",
            project_path="openclaw:agent:main",
            started_at="2026-03-17T07:00:00Z",
            ended_at="2026-03-17T07:20:00Z",
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=50_000,
            total_output_tokens=5_000,
            total_cache_write_tokens=1_000,
            total_cache_read_tokens=2_000,
            tool_use_count=3,
            failed_tool_call_count=1,
            tool_breakdown={"search": 1, "bash": 2},
        )

        analytics = build_analytics([claude, codex, openclaw], days=7, now=now)

        assert analytics.total_conversations == 3
        assert analytics.tool_breakdown == {"bash": 2, "read_file": 3, "search": 4}
        assert analytics.tool_breakdown_by_provider["search"].claude == 0
        assert analytics.tool_breakdown_by_provider["search"].codex == 3
        assert analytics.tool_breakdown_by_provider["search"].openclaw == 1
        assert analytics.tool_breakdown_by_provider["bash"].openclaw == 2
        assert analytics.model_breakdown_by_provider["claude-sonnet-4-5-20250929"].claude == 1
        assert analytics.model_breakdown_by_provider["claude-sonnet-4-5-20250929"].openclaw == 1
        assert analytics.cost_breakdown_by_provider["claude"].total_cost == pytest.approx(1.0935)
        assert analytics.cost_breakdown_by_provider["codex"].total_cost == pytest.approx(0.45125)
        assert analytics.cost_breakdown_by_provider["openclaw"].total_cost == pytest.approx(0.22935)

    def test_build_analytics_omits_unpriced_openclaw_costs_from_cost_math(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        openclaw = _summary(
            "openclaw-unpriced",
            provider="openclaw",
            project_path="openclaw:agent:main",
            started_at="2026-03-17T07:00:00Z",
            ended_at="2026-03-17T07:20:00Z",
            model="openclaw-internal-preview",
            total_input_tokens=50_000,
            total_output_tokens=5_000,
            total_cache_write_tokens=1_000,
            total_cache_read_tokens=2_000,
            tool_use_count=3,
            failed_tool_call_count=1,
            tool_breakdown={"search": 1, "bash": 2},
        )

        analytics = build_analytics([openclaw], days=7, now=now)

        assert analytics.total_conversations == 1
        assert analytics.total_tool_calls == 3
        assert analytics.tool_breakdown_by_provider["bash"].openclaw == 2
        assert analytics.model_breakdown_by_provider["openclaw-internal-preview"].openclaw == 1
        assert analytics.estimated_cost == pytest.approx(0.0)
        assert analytics.cost_breakdown.total_cost == pytest.approx(0.0)
        assert analytics.cost_breakdown_by_provider["openclaw"].total_cost == pytest.approx(0.0)
        assert analytics.cost_breakdown_by_model["openclaw-internal-preview"].total_cost == pytest.approx(0.0)

    def test_build_analytics_keeps_claude_and_codex_provider_filters_stable(self) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        conversations = [
            _summary(
                "claude-1",
                started_at="2026-03-16T09:00:00Z",
                ended_at="2026-03-16T09:30:00Z",
                model="claude-sonnet-4-5-20250929",
                tool_use_count=1,
                tool_breakdown={"read_file": 1},
            ),
            _summary(
                "codex-1",
                provider="codex",
                project_path="codex:-Users-tony-Code-helaicopter",
                started_at="2026-03-17T09:00:00Z",
                ended_at="2026-03-17T09:30:00Z",
                model="gpt-5",
                tool_use_count=2,
                tool_breakdown={"search": 2},
            ),
            _summary(
                "openclaw-1",
                provider="openclaw",
                project_path="openclaw:agent:main",
                started_at="2026-03-17T10:00:00Z",
                ended_at="2026-03-17T10:30:00Z",
                model="openclaw-v1",
                tool_use_count=3,
                tool_breakdown={"bash": 3},
            ),
        ]

        claude_only = build_analytics(
            filter_analytics_conversations(conversations, provider="claude", now=now),
            days=7,
            now=now,
        )
        codex_only = build_analytics(
            filter_analytics_conversations(conversations, provider="codex", now=now),
            days=7,
            now=now,
        )

        assert claude_only.total_conversations == 1
        assert claude_only.tool_breakdown == {"read_file": 1}
        assert set(claude_only.cost_breakdown_by_provider) == {"claude"}

        assert codex_only.total_conversations == 1
        assert codex_only.tool_breakdown == {"search": 2}
        assert set(codex_only.cost_breakdown_by_provider) == {"codex"}

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
    def test_warehouse_rows_derive_route_slug_from_first_message(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'olap.sqlite'}", future=True)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE fact_conversations (
                          conversation_id TEXT PRIMARY KEY,
                          provider TEXT NOT NULL,
                          session_id TEXT NOT NULL,
                          project_id TEXT NOT NULL,
                          model_id TEXT,
                          started_at TEXT NOT NULL,
                          ended_at TEXT NOT NULL,
                          first_message TEXT NOT NULL,
                          message_count INTEGER NOT NULL,
                          total_input_tokens INTEGER NOT NULL,
                          total_output_tokens INTEGER NOT NULL,
                          total_cache_write_tokens INTEGER NOT NULL,
                          total_cache_read_tokens INTEGER NOT NULL,
                          total_reasoning_tokens INTEGER NOT NULL,
                          tool_use_count INTEGER NOT NULL,
                          subagent_count INTEGER NOT NULL,
                          task_count INTEGER NOT NULL
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE dim_projects (
                          project_id TEXT PRIMARY KEY,
                          provider TEXT NOT NULL,
                          project_path TEXT NOT NULL,
                          project_name TEXT NOT NULL
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE dim_models (
                          model_id TEXT PRIMARY KEY,
                          provider TEXT NOT NULL,
                          model_name TEXT NOT NULL
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO dim_projects (project_id, provider, project_path, project_name)
                        VALUES ('project-1', 'claude', '-Users-tony-Code-helaicopter', 'helaicopter')
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO dim_models (model_id, provider, model_name)
                        VALUES ('model-1', 'claude', 'claude-sonnet-4-5-20250929')
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO fact_conversations (
                          conversation_id,
                          provider,
                          session_id,
                          project_id,
                          model_id,
                          started_at,
                          ended_at,
                          first_message,
                          message_count,
                          total_input_tokens,
                          total_output_tokens,
                          total_cache_write_tokens,
                          total_cache_read_tokens,
                          total_reasoning_tokens,
                          tool_use_count,
                          subagent_count,
                          task_count
                        ) VALUES (
                          'claude:session-warehouse',
                          'claude',
                          'session-warehouse',
                          'project-1',
                          'model-1',
                          '2026-03-17T06:00:00Z',
                          '2026-03-17T07:00:00Z',
                          'Warehouse analytics title!!!',
                          3,
                          10,
                          5,
                          0,
                          0,
                          0,
                          0,
                          0,
                          1
                        )
                        """
                    )
                )

            monkeypatch.setattr(analytics_application, "create_olap_engine", lambda _settings=None: engine)
            services = _services_stub(settings=object())

            rows = analytics_application.list_warehouse_historical_conversations(services)
        finally:
            engine.dispose()

        assert len(rows) == 1
        assert rows[0].route_slug == derive_route_slug("Warehouse analytics title!!!")

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
        services = _services_stub(app_sqlite_store=store)

        response = get_analytics(services, days=1, provider="codex", now=now)

        assert store.calls == [{}]
        assert response.total_conversations == 1
        assert response.total_input_tokens == 20_000
        assert response.cost_breakdown_by_provider["codex"].input_cost == pytest.approx(0.025)
        assert "claude" not in response.cost_breakdown_by_provider

    def test_application_layer_rejects_unknown_provider(self) -> None:
        services = _services_stub(
            app_sqlite_store=SimpleNamespace(list_historical_conversations=lambda: [])
        )

        with pytest.raises(ValueError, match="Unsupported analytics provider"):
            get_analytics(services, provider="openai")

    def test_application_layer_supplements_live_conversation_summaries_when_persisted_history_is_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)

        class EmptyStore:
            def list_historical_conversations(self, **_kwargs: object) -> list[HistoricalConversationSummary]:
                return []

        monkeypatch.setattr(
            analytics_application,
            "list_warehouse_historical_conversations",
            lambda _services: [],
        )
        monkeypatch.setattr(
            analytics_application,
            "list_conversations",
            lambda _services: [
                analytics_application.ConversationSummaryResponse(
                    session_id="live-codex-session",
                    provider="codex",
                    project_path="codex:-Users-tony-Code-helaicopter",
                    project_name="Code/helaicopter",
                    route_slug="fix-live-analytics",
                    conversation_ref="fix-live-analytics--codex-live-codex-session",
                    thread_type="main",
                    first_message="Fix live analytics",
                    timestamp=(now - timedelta(hours=2)).timestamp() * 1000,
                    created_at=(now - timedelta(hours=2)).timestamp() * 1000,
                    last_updated_at=(now - timedelta(hours=1)).timestamp() * 1000,
                    is_running=True,
                    message_count=12,
                    model="gpt-5",
                    total_input_tokens=24_000,
                    total_output_tokens=6_000,
                    total_cache_creation_tokens=1_000,
                    total_cache_read_tokens=2_000,
                    tool_use_count=9,
                    failed_tool_call_count=2,
                    tool_breakdown={"Shell": 6, "Read": 3},
                    subagent_count=2,
                    subagent_type_breakdown={"worker": 2},
                    task_count=1,
                    total_reasoning_tokens=800,
                )
            ],
        )

        services = _services_stub(
            app_sqlite_store=EmptyStore(),
            cache=object(),
            settings=object(),
            claude_conversation_reader=object(),
            codex_store=object(),
            openclaw_store=object(),
        )
        response = get_analytics(services, days=1, provider="codex", now=now)

        assert response.total_conversations == 1
        assert response.total_input_tokens == 24_000
        assert response.total_output_tokens == 6_000
        assert response.total_cache_creation_tokens == 1_000
        assert response.total_cache_read_tokens == 2_000
        assert response.total_tool_calls == 9
        assert response.total_failed_tool_calls == 2
        assert response.total_reasoning_tokens == 800
        assert response.subagent_type_breakdown == {"worker": 2}
        assert response.tool_breakdown == {"Shell": 6, "Read": 3}
        assert response.cost_breakdown_by_provider["codex"].total_cost > 0

    def test_application_layer_skips_live_supplement_when_live_services_are_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
        called = False

        class EmptyStore:
            def list_historical_conversations(self, **_kwargs: object) -> list[HistoricalConversationSummary]:
                return []

        def _unexpected_list_conversations(_services: BackendServices) -> list[ConversationSummaryResponse]:
            nonlocal called
            called = True
            return []

        monkeypatch.setattr(analytics_application, "list_conversations", _unexpected_list_conversations)

        services = _services_stub(app_sqlite_store=EmptyStore())
        response = get_analytics(services, days=1, now=now)

        assert called is False
        assert response.total_conversations == 0
