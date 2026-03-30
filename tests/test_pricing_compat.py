"""Compatibility tests for legacy pure.pricing helpers.

These tests focus on edge cases and backwards‑compatibility behaviors while
the codebase migrates to the canonical `helaicopter_semantics` package.
"""

from __future__ import annotations

import pytest

from helaicopter_api.pure.pricing import (
    CLAUDE_PRICING,
    DEFAULT_PRICING,
    OPENAI_PRICING,
    calculate_cost,
    resolve_pricing,
    supports_long_context_premium,
)


class TestResolvePricingCompat:
    def test_default_and_unknown_models(self) -> None:
        assert resolve_pricing(None) == DEFAULT_PRICING
        assert resolve_pricing("") == DEFAULT_PRICING
        assert resolve_pricing("totally-unknown-model") == DEFAULT_PRICING

    def test_fuzzy_and_family_matches(self) -> None:
        # OpenAI family
        assert resolve_pricing("gpt5") == OPENAI_PRICING["gpt-5"]
        assert resolve_pricing("contains-gpt-5.4") == OPENAI_PRICING["gpt-5.4"]
        assert resolve_pricing("gpt-5.4-mini") == OPENAI_PRICING["gpt-5.4-mini"]
        assert resolve_pricing("gpt-5.4-nano") == OPENAI_PRICING["gpt-5.4-nano"]
        assert resolve_pricing("o3-2026-01-01") == OPENAI_PRICING["o3"]
        assert resolve_pricing("o4-mini-variant") == OPENAI_PRICING["o4-mini"]

        # Claude family
        assert resolve_pricing("claude-sonnet-4-5-20250929-extra") == CLAUDE_PRICING[
            "claude-sonnet-4-5-20250929"
        ]
        assert resolve_pricing("some-sonnet") == CLAUDE_PRICING["claude-sonnet-4-6"]
        assert resolve_pricing("some-opus-4-6-sku") == CLAUDE_PRICING["claude-opus-4-6"]
        assert resolve_pricing("some-opus-4-1-sku") == CLAUDE_PRICING["claude-opus-4"]


class TestCalculateCostCompat:
    def test_zero_usage_costs_zero(self) -> None:
        cost = calculate_cost(
            input_tokens=0,
            output_tokens=0,
            cache_write_tokens=0,
            cache_read_tokens=0,
            model=None,
        )
        assert cost.input_cost == 0.0
        assert cost.output_cost == 0.0
        assert cost.cache_write_cost == 0.0
        assert cost.cache_read_cost == 0.0
        assert cost.total_cost == 0.0

    def test_boundary_values_and_precision(self) -> None:
        # 1 token in each bucket should be tiny but non‑zero depending on pricing
        cost = calculate_cost(
            input_tokens=1,
            output_tokens=1,
            cache_write_tokens=1,
            cache_read_tokens=1,
            model="claude-sonnet-4-5-20250929",
        )
        # Sanity: totals are consistent with itemization
        assert cost.total_cost == pytest.approx(
            cost.input_cost + cost.output_cost + cost.cache_write_cost + cost.cache_read_cost
        )


class TestLongContextPremiumFlag:
    def test_flag_applies_only_to_supported_models(self) -> None:
        assert not supports_long_context_premium("claude-opus-4-6")
        assert not supports_long_context_premium("claude-sonnet-4-6")
        assert supports_long_context_premium("claude-sonnet-4-5-20250929")
        assert not supports_long_context_premium("claude-haiku-3-5")
        assert not supports_long_context_premium("gpt-5")
        assert not supports_long_context_premium(None)
