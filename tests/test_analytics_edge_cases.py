"""Edge-case tests for analytics aggregation.

Covers empty inputs, invalid timestamps, and window/rate clamping.
"""

from __future__ import annotations

from datetime import UTC, datetime

from helaicopter_api.pure.analytics import build_analytics
from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary


def _summary(*, started_at: str | None, ended_at: str | None, **overrides: object) -> HistoricalConversationSummary:
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    base = dict(
        conversation_id="conv-1",
        provider="claude",
        session_id="session-1",
        project_path="-Users-tony-Code-helaicopter",
        project_name="helaicopter",
        first_message="Hello",
        route_slug="hello",
        started_at=started_at or now_iso,
        ended_at=ended_at or now_iso,
        message_count=1,
        model="claude-sonnet-4-5-20250929",
        total_input_tokens=0,
        task_count=0,
    )
    base.update(overrides)
    return HistoricalConversationSummary(**base)


class TestAnalyticsEdgeCases:
    def test_empty_input_returns_zeroes(self) -> None:
        fixed_now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        data = build_analytics([], days=1, now=fixed_now)

        assert data.total_conversations == 0
        assert data.estimated_cost == 0.0
        # Rates clamp to a minimum one-hour window; still zero with zero totals
        assert data.rates["spend"].per_hour == 0.0
        assert data.time_series.hourly == []
        assert data.daily_usage == []

    def test_invalid_started_at_excluded_from_buckets_but_totals_accumulate(self) -> None:
        # started_at is invalid; totals should still roll up, but time series stays empty
        row = _summary(
            started_at="not-a-timestamp",
            ended_at="2026-03-19T10:00:00Z",
            total_input_tokens=12_000,
            total_output_tokens=3_000,
            total_cache_write_tokens=1_000,
            total_cache_read_tokens=500,
        )

        data = build_analytics([row], days=7, now=datetime(2026, 3, 20, tzinfo=UTC))

        assert data.total_conversations == 1
        assert data.total_input_tokens == 12_000
        assert data.time_series.daily == []
        assert data.daily_usage == []

