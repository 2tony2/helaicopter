"""Tests for the canonical semantic foundation layer.

This test module covers the authoritative semantic definitions that other
layers depend on:
- Pricing tables and model matching
- Token field alias normalization
- Provider resolution
- Long-context premium rules
"""

from __future__ import annotations

import pytest

from helaicopter_semantics import (
    CACHE_CREATION_ALIASES,
    CACHE_READ_ALIASES,
    CLAUDE_PRICING,
    CostBreakdown,
    OPENAI_PRICING,
    RunRuntimeStatus,
    TaskRuntimeStatus,
    calculate_cost,
    normalize_token_fields,
    resolve_pricing,
    resolve_provider,
    status_tone,
    supports_long_context_premium,
)


class TestCanonicalPricing:
    """Tests for canonical pricing tables and model matching."""

    def test_exact_model_match_returns_correct_pricing(self) -> None:
        claude_sonnet = resolve_pricing("claude-sonnet-4-5-20250929")
        assert claude_sonnet == CLAUDE_PRICING["claude-sonnet-4-5-20250929"]
        assert claude_sonnet.input == 3.0
        assert claude_sonnet.output == 15.0

        gpt5 = resolve_pricing("gpt-5")
        assert gpt5 == OPENAI_PRICING["gpt-5"]
        assert gpt5.input == 1.25
        assert gpt5.output == 10.0

    def test_prefix_match_resolves_to_base_model(self) -> None:
        versioned_sonnet = resolve_pricing("claude-sonnet-4-5-20250929-with-suffix")
        assert versioned_sonnet == CLAUDE_PRICING["claude-sonnet-4-5-20250929"]

    def test_fuzzy_match_handles_common_variants(self) -> None:
        assert resolve_pricing("gpt5") == OPENAI_PRICING["gpt-5"]
        assert resolve_pricing("model-contains-gpt-5.4-somewhere") == OPENAI_PRICING["gpt-5.4"]
        assert resolve_pricing("gpt-5.4-mini") == OPENAI_PRICING["gpt-5.4-mini"]
        assert resolve_pricing("gpt-5.4-nano") == OPENAI_PRICING["gpt-5.4-nano"]
        assert resolve_pricing("sonnet-something") == CLAUDE_PRICING["claude-sonnet-4-6"]
        assert resolve_pricing("haiku-model") == CLAUDE_PRICING["claude-haiku-4-5-20251001"]

    def test_missing_model_returns_default_pricing(self) -> None:
        from helaicopter_semantics.pricing import DEFAULT_PRICING
        assert resolve_pricing(None) == DEFAULT_PRICING
        assert resolve_pricing("") == DEFAULT_PRICING
        assert resolve_pricing("completely-unknown-model") == DEFAULT_PRICING

    def test_openai_cache_pricing_is_zero_for_writes(self) -> None:
        """OpenAI cache fills are free, only cache reads are discounted."""
        gpt5_pricing = OPENAI_PRICING["gpt-5"]
        assert gpt5_pricing.cache_write_5m == 0.0
        assert gpt5_pricing.cache_write_1h == 0.0
        assert gpt5_pricing.cache_read == 0.125  # Discounted input price


class TestCostCalculation:
    """Tests for canonical cost calculation logic."""

    def test_calculate_cost_itemizes_token_types(self) -> None:
        cost = calculate_cost(
            input_tokens=100_000,
            output_tokens=50_000,
            cache_write_tokens=10_000,
            cache_read_tokens=5_000,
            model="claude-sonnet-4-5-20250929",
        )

        assert cost.input_cost == pytest.approx(0.3)  # 100k / 1M * 3.0
        assert cost.output_cost == pytest.approx(0.75)  # 50k / 1M * 15.0
        assert cost.cache_write_cost == pytest.approx(0.0375)  # 10k / 1M * 3.75
        assert cost.cache_read_cost == pytest.approx(0.0015)  # 5k / 1M * 0.3
        assert cost.total_cost == pytest.approx(1.089)

    def test_calculate_cost_handles_openai_cache_semantics(self) -> None:
        """OpenAI cache writes are free, reads are discounted."""
        cost = calculate_cost(
            input_tokens=120_000,
            output_tokens=30_000,
            cache_write_tokens=40_000,  # Should be free
            cache_read_tokens=10_000,
            model="gpt-5",
        )

        assert cost.input_cost == pytest.approx(0.15)  # 120k / 1M * 1.25
        assert cost.output_cost == pytest.approx(0.3)  # 30k / 1M * 10.0
        assert cost.cache_write_cost == pytest.approx(0.0)  # Free for OpenAI
        assert cost.cache_read_cost == pytest.approx(0.00125)  # 10k / 1M * 0.125
        assert cost.total_cost == pytest.approx(0.45125)


class TestLongContextPremium:
    """Tests for long-context premium rules."""

    def test_opus_4_6_models_use_standard_pricing_across_full_context(self) -> None:
        assert not supports_long_context_premium("claude-opus-4-6")
        assert not supports_long_context_premium("claude-opus-4-5-20251101")
        assert not supports_long_context_premium("opus-4-6-variant")

    def test_sonnet_4_6_models_use_standard_pricing_across_full_context(self) -> None:
        assert not supports_long_context_premium("claude-sonnet-4-6")

    def test_legacy_sonnet_4_models_keep_long_context_premium(self) -> None:
        assert supports_long_context_premium("claude-sonnet-4-5-20250929")
        assert supports_long_context_premium("sonnet-4-custom")

    def test_older_models_do_not_support_long_context_premium(self) -> None:
        assert not supports_long_context_premium("claude-haiku-4-5-20251001")
        assert not supports_long_context_premium("claude-haiku-3-5")
        assert not supports_long_context_premium("gpt-5")
        assert not supports_long_context_premium("claude-opus-4-1")
        assert not supports_long_context_premium(None)


class TestTokenFieldAliases:
    """Tests for token field alias normalization."""

    def test_cache_creation_aliases_are_comprehensive(self) -> None:
        """Verify all known cache creation aliases are registered."""
        assert "cache_creation_input_tokens" in CACHE_CREATION_ALIASES
        assert "cache_creation_tokens" in CACHE_CREATION_ALIASES
        assert "cache_write_tokens" in CACHE_CREATION_ALIASES

    def test_cache_read_aliases_are_comprehensive(self) -> None:
        """Verify all known cache read aliases are registered."""
        assert "cache_read_input_tokens" in CACHE_READ_ALIASES
        assert "cache_read_tokens" in CACHE_READ_ALIASES

    def test_normalize_token_fields_handles_standard_fields(self) -> None:
        normalized = normalize_token_fields({
            "input_tokens": 100,
            "output_tokens": 50,
            "reasoning_tokens": 25,
        })

        assert normalized["input_tokens"] == 100
        assert normalized["output_tokens"] == 50
        assert normalized["reasoning_tokens"] == 25

    def test_normalize_token_fields_maps_cache_creation_aliases(self) -> None:
        """Test that cache_creation_input_tokens maps to cache_write_tokens."""
        normalized = normalize_token_fields({
            "input_tokens": 100,
            "cache_creation_input_tokens": 50,
        })

        assert normalized["input_tokens"] == 100
        assert normalized["cache_write_tokens"] == 50
        assert "cache_creation_input_tokens" not in normalized

    def test_normalize_token_fields_maps_cache_read_aliases(self) -> None:
        """Test that cache_read_input_tokens maps to cache_read_tokens."""
        normalized = normalize_token_fields({
            "input_tokens": 100,
            "cache_read_input_tokens": 25,
        })

        assert normalized["input_tokens"] == 100
        assert normalized["cache_read_tokens"] == 25
        assert "cache_read_input_tokens" not in normalized

    def test_normalize_token_fields_aggregates_multiple_aliases(self) -> None:
        """Test that multiple cache aliases aggregate correctly."""
        normalized = normalize_token_fields({
            "cache_creation_tokens": 30,
            "cache_creation_input_tokens": 20,
        })

        assert normalized["cache_write_tokens"] == 50

    def test_normalize_token_fields_omits_zero_values(self) -> None:
        """Test that fields with no value are omitted."""
        normalized = normalize_token_fields({
            "input_tokens": 100,
        })

        assert "cache_write_tokens" not in normalized
        assert "cache_read_tokens" not in normalized
        assert "reasoning_tokens" not in normalized


class TestProviderResolution:
    """Tests for canonical provider resolution logic."""

    def test_explicit_codex_provider_field_takes_precedence(self) -> None:
        provider = resolve_provider(
            provider="codex",
            model="claude-sonnet-4-5-20250929",
            project_path="normal-path",
        )
        assert provider == "codex"

    def test_explicit_openclaw_provider_field_takes_precedence(self) -> None:
        provider = resolve_provider(
            provider="openclaw",
            model="gpt-5",
            project_path="codex:-Users-tony-Code-helaicopter",
        )
        assert provider == "openclaw"

    def test_codex_project_path_prefix_identifies_codex(self) -> None:
        provider = resolve_provider(
            project_path="codex:-Users-tony-Code-helaicopter",
        )
        assert provider == "codex"

    def test_openclaw_project_path_prefix_identifies_openclaw(self) -> None:
        provider = resolve_provider(
            model="gpt-5",
            project_path="openclaw:-Users-tony-Code-helaicopter",
        )
        assert provider == "openclaw"

    def test_openclaw_provenance_is_not_coerced_to_codex_by_openaiish_model(self) -> None:
        provider = resolve_provider(
            provider="openclaw",
            model="gpt-5",
            project_path="openclaw:-Users-tony-Code-helaicopter",
        )
        assert provider == "openclaw"

    def test_gpt_model_identifies_codex(self) -> None:
        provider = resolve_provider(model="gpt-5")
        assert provider == "codex"

        provider = resolve_provider(model="gpt-5-mini")
        assert provider == "codex"

    def test_o3_o4_models_identify_codex(self) -> None:
        provider = resolve_provider(model="o3")
        assert provider == "codex"

        provider = resolve_provider(model="o4-mini")
        assert provider == "codex"

    def test_claude_model_identifies_claude(self) -> None:
        provider = resolve_provider(model="claude-sonnet-4-5-20250929")
        assert provider == "claude"

    def test_default_provider_is_claude(self) -> None:
        provider = resolve_provider()
        assert provider == "claude"

        provider = resolve_provider(model=None, provider=None, project_path=None)
        assert provider == "claude"


class TestContractDriftRemoval:
    """Tests verifying explicit contract drift cleanup.

    The frontend normalization proxy silently maps cache_creation_input_tokens
    to cache_write_tokens and similar aliases. The semantic layer now makes
    this mapping explicit and testable, removing the unsound proxy behavior.
    """

    def test_cache_creation_input_tokens_explicitly_maps_to_cache_write_tokens(self) -> None:
        """Frontend relied on proxy normalization; backend now has explicit mapping."""
        # Before: Frontend Proxy silently normalized this
        # After: Explicit semantic normalization with test coverage
        normalized = normalize_token_fields({
            "input_tokens": 100_000,
            "output_tokens": 50_000,
            "cache_creation_input_tokens": 10_000,  # Historical alias
            "cache_read_input_tokens": 5_000,  # Historical alias
        })

        assert normalized == {
            "input_tokens": 100_000,
            "output_tokens": 50_000,
            "cache_write_tokens": 10_000,  # Explicitly normalized
            "cache_read_tokens": 5_000,  # Explicitly normalized
        }

    def test_analytics_cost_calculation_uses_explicit_normalization(self) -> None:
        """Verify cost calculation works with normalized token fields."""
        # This test documents that the backend no longer relies on frontend
        # normalization and instead uses explicit semantic layer mapping
        raw_tokens = {
            "input_tokens": 100_000,
            "output_tokens": 50_000,
            "cache_creation_input_tokens": 10_000,
            "cache_read_input_tokens": 5_000,
        }

        normalized = normalize_token_fields(raw_tokens)

        cost = calculate_cost(
            input_tokens=normalized.get("input_tokens", 0),
            output_tokens=normalized.get("output_tokens", 0),
            cache_write_tokens=normalized.get("cache_write_tokens", 0),
            cache_read_tokens=normalized.get("cache_read_tokens", 0),
            model="claude-sonnet-4-5-20250929",
        )

        # Verify cost is calculated correctly from normalized fields
        assert cost.total_cost == pytest.approx(1.089)


class TestOrchestrationStatusVocabulary:
    """Tests for canonical orchestration status vocabulary and display mapping."""

    def test_run_status_vocabulary_is_complete(self) -> None:
        """Verify all run statuses are defined."""
        # This test ensures the canonical vocabulary is accessible
        run_statuses: list[RunRuntimeStatus] = [
            "pending",
            "planning",
            "running",
            "completed",
            "failed",
            "timed_out",
        ]
        for status in run_statuses:
            tone = status_tone(status)
            assert tone is not None

    def test_task_status_vocabulary_is_complete(self) -> None:
        """Verify all task statuses are defined."""
        task_statuses: list[TaskRuntimeStatus] = [
            "pending",
            "running",
            "succeeded",
            "failed",
            "timed_out",
            "skipped",
            "blocked",
        ]
        for status in task_statuses:
            tone = status_tone(status)
            assert tone is not None

    def test_status_tone_maps_success_states(self) -> None:
        """Success states map to success tone."""
        assert status_tone("succeeded") == "success"
        assert status_tone("completed") == "success"

    def test_status_tone_maps_error_states(self) -> None:
        """Error states map to error tone."""
        assert status_tone("failed") == "error"
        assert status_tone("timed_out") == "error"

    def test_status_tone_maps_warning_states(self) -> None:
        """Warning states map to warning tone."""
        assert status_tone("blocked") == "warning"
        assert status_tone("skipped") == "warning"

    def test_status_tone_maps_in_progress_states(self) -> None:
        """In-progress states map to in_progress tone."""
        assert status_tone("running") == "in_progress"
        assert status_tone("planning") == "in_progress"

    def test_status_tone_maps_pending_state(self) -> None:
        """Pending state maps to info tone."""
        assert status_tone("pending") == "info"
