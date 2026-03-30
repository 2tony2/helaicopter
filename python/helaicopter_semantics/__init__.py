"""Canonical semantic definitions for Helaicopter analytics.

This package owns the authoritative definitions for:
- Model pricing tables
- Model matching and provider resolution
- Long-context premium rules
- Token field alias reconciliation
- Cost calculation logic

No other layer should maintain independent copies of this logic.
"""

from __future__ import annotations

from .pricing import (
    CLAUDE_PRICING,
    DEFAULT_PRICING,
    OPENAI_PRICING,
    CostBreakdown,
    ModelPricing,
    calculate_cost,
    resolve_pricing,
    supports_long_context_premium,
)
from .token_aliases import (
    CACHE_CREATION_ALIASES,
    CACHE_READ_ALIASES,
    normalize_token_fields,
)
from .models import ProviderIdentifier, resolve_provider

__all__ = [
    "CACHE_CREATION_ALIASES",
    "CACHE_READ_ALIASES",
    "CLAUDE_PRICING",
    "CostBreakdown",
    "DEFAULT_PRICING",
    "ModelPricing",
    "OPENAI_PRICING",
    "ProviderIdentifier",
    "calculate_cost",
    "normalize_token_fields",
    "resolve_pricing",
    "resolve_provider",
    "supports_long_context_premium",
]
