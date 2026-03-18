"""Schemas for usage analytics and cost data."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnalyticsProviderParam = Literal["all", "claude", "codex"]


class AnalyticsQueryParams(BaseModel):
    """Stable request parameters for the analytics index endpoint."""

    model_config = ConfigDict(extra="forbid")

    days: int | None = Field(
        default=None,
        ge=1,
        description="Restrict analytics to the trailing number of days.",
    )
    provider: AnalyticsProviderParam | None = Field(
        default=None,
        description="Optional provider filter. Use `all` or omit for combined analytics.",
    )


class AnalyticsCostBreakdownResponse(BaseModel):
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_write_cost: float = 0.0
    cache_read_cost: float = 0.0
    long_context_premium: float = 0.0
    long_context_conversations: int = 0
    total_cost: float = 0.0


class ProviderBreakdownResponse(BaseModel):
    claude: int = 0
    codex: int = 0


class AnalyticsRateValueResponse(BaseModel):
    per_hour: float = 0.0
    per_day: float = 0.0
    per_week: float = 0.0
    per_month: float = 0.0


class AnalyticsRatesResponse(BaseModel):
    spend: AnalyticsRateValueResponse
    total_tokens: AnalyticsRateValueResponse
    input_tokens: AnalyticsRateValueResponse
    output_tokens: AnalyticsRateValueResponse
    cache_write_tokens: AnalyticsRateValueResponse
    cache_read_tokens: AnalyticsRateValueResponse
    reasoning_tokens: AnalyticsRateValueResponse
    conversations: AnalyticsRateValueResponse
    tool_calls: AnalyticsRateValueResponse
    failed_tool_calls: AnalyticsRateValueResponse
    subagents: AnalyticsRateValueResponse


class AnalyticsTimeSeriesPointResponse(BaseModel):
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


class AnalyticsTimeSeriesResponse(BaseModel):
    hourly: list[AnalyticsTimeSeriesPointResponse] = Field(default_factory=list)
    daily: list[AnalyticsTimeSeriesPointResponse] = Field(default_factory=list)
    weekly: list[AnalyticsTimeSeriesPointResponse] = Field(default_factory=list)
    monthly: list[AnalyticsTimeSeriesPointResponse] = Field(default_factory=list)


class DailyUsageResponse(BaseModel):
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
    claude_subagents: int = 0
    codex_subagents: int = 0


class AnalyticsDataResponse(BaseModel):
    """Top-level analytics payload."""

    total_conversations: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_tool_calls: int = 0
    total_failed_tool_calls: int = 0
    model_breakdown: dict[str, int] = Field(default_factory=dict)
    tool_breakdown: dict[str, int] = Field(default_factory=dict)
    subagent_type_breakdown: dict[str, int] = Field(default_factory=dict)
    model_breakdown_by_provider: dict[str, ProviderBreakdownResponse] = Field(default_factory=dict)
    tool_breakdown_by_provider: dict[str, ProviderBreakdownResponse] = Field(default_factory=dict)
    subagent_type_breakdown_by_provider: dict[str, ProviderBreakdownResponse] = Field(default_factory=dict)
    daily_usage: list[DailyUsageResponse] = Field(default_factory=list)
    rates: AnalyticsRatesResponse | None = None
    time_series: AnalyticsTimeSeriesResponse | None = None
    estimated_cost: float = 0.0
    cost_breakdown: AnalyticsCostBreakdownResponse | None = None
    cost_breakdown_by_provider: dict[str, AnalyticsCostBreakdownResponse] = Field(default_factory=dict)
    cost_breakdown_by_model: dict[str, AnalyticsCostBreakdownResponse] = Field(default_factory=dict)
