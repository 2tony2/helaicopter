"""Pure pricing helpers shared by analytics computations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input: float
    output: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    input_cost: float
    output_cost: float
    cache_write_cost: float
    cache_read_cost: float

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost + self.cache_write_cost + self.cache_read_cost


CLAUDE_PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 10.0, 0.5),
    "claude-opus-4-5-20251101": ModelPricing(5.0, 25.0, 6.25, 10.0, 0.5),
    "claude-opus-4-1": ModelPricing(15.0, 75.0, 18.75, 30.0, 1.5),
    "claude-opus-4": ModelPricing(15.0, 75.0, 18.75, 30.0, 1.5),
    "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 6.0, 0.3),
    "claude-sonnet-4-5-20250929": ModelPricing(3.0, 15.0, 3.75, 6.0, 0.3),
    "claude-sonnet-4": ModelPricing(3.0, 15.0, 3.75, 6.0, 0.3),
    "claude-haiku-4-5-20251001": ModelPricing(1.0, 5.0, 1.25, 2.0, 0.1),
    "claude-haiku-3-5": ModelPricing(0.8, 4.0, 1.0, 1.6, 0.08),
    "claude-haiku-3": ModelPricing(0.25, 1.25, 0.3, 0.5, 0.03),
}

OPENAI_PRICING: dict[str, ModelPricing] = {
    "gpt-5.4": ModelPricing(2.5, 15.0, 0.0, 0.0, 0.25),
    "gpt-5.2": ModelPricing(1.75, 14.0, 0.0, 0.0, 0.175),
    "gpt-5.1": ModelPricing(1.25, 10.0, 0.0, 0.0, 0.125),
    "gpt-5": ModelPricing(1.25, 10.0, 0.0, 0.0, 0.125),
    "gpt-5-mini": ModelPricing(0.25, 2.0, 0.0, 0.0, 0.025),
    "o3": ModelPricing(2.0, 8.0, 0.0, 0.0, 0.5),
    "o4-mini": ModelPricing(1.1, 4.4, 0.0, 0.0, 0.275),
}

DEFAULT_PRICING = CLAUDE_PRICING["claude-opus-4-6"]


def resolve_pricing(model: str | None) -> ModelPricing:
    """Resolve token pricing using the same matching rules as the legacy TS path."""
    if not model:
        return DEFAULT_PRICING
    if model in CLAUDE_PRICING:
        return CLAUDE_PRICING[model]
    if model in OPENAI_PRICING:
        return OPENAI_PRICING[model]
    for key, pricing in CLAUDE_PRICING.items():
        if model.startswith(key):
            return pricing
    for key, pricing in OPENAI_PRICING.items():
        if model.startswith(key):
            return pricing
    if "gpt-5.4" in model or "gpt5.4" in model:
        return OPENAI_PRICING["gpt-5.4"]
    if "gpt-5.2" in model or "gpt5.2" in model:
        return OPENAI_PRICING["gpt-5.2"]
    if "gpt-5.1" in model or "gpt5.1" in model:
        return OPENAI_PRICING["gpt-5.1"]
    if "gpt-5-mini" in model or "gpt5-mini" in model:
        return OPENAI_PRICING["gpt-5-mini"]
    if "gpt-5" in model or "gpt5" in model:
        return OPENAI_PRICING["gpt-5"]
    if "o4-mini" in model:
        return OPENAI_PRICING["o4-mini"]
    if "o3" in model:
        return OPENAI_PRICING["o3"]
    if "opus-4-6" in model or "opus-4-5" in model:
        return CLAUDE_PRICING["claude-opus-4-6"]
    if "opus-4-1" in model or "opus-4" in model:
        return CLAUDE_PRICING["claude-opus-4"]
    if "sonnet" in model:
        return CLAUDE_PRICING["claude-sonnet-4-5-20250929"]
    if "haiku" in model:
        return CLAUDE_PRICING["claude-haiku-4-5-20251001"]
    return DEFAULT_PRICING


def calculate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    model: str | None,
) -> CostBreakdown:
    """Calculate API-style token costs.

    OpenAI/Codex cache fills are preserved from the legacy implementation by
    resolving those models to a zero cache-write price and a discounted cached
    read price.
    """
    pricing = resolve_pricing(model)
    return CostBreakdown(
        input_cost=(input_tokens / 1_000_000) * pricing.input,
        output_cost=(output_tokens / 1_000_000) * pricing.output,
        cache_write_cost=(cache_write_tokens / 1_000_000) * pricing.cache_write_5m,
        cache_read_cost=(cache_read_tokens / 1_000_000) * pricing.cache_read,
    )


def supports_long_context_premium(model: str | None) -> bool:
    if not model:
        return False
    return any(
        token in model
        for token in ("opus-4-6", "opus-4-5", "sonnet-4-6", "sonnet-4-5", "sonnet-4")
    )
