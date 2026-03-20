# Helaicopter Semantics Package

This package owns the **canonical semantic definitions** for Helaicopter analytics.

## Purpose

No other layer should maintain independent copies of pricing, model matching, token aliases, or provider resolution logic. This package is the single source of truth.

## What This Package Owns

### 1. Model Pricing (`pricing.py`)

- **Canonical pricing tables** for Claude and OpenAI/Codex models
- **Model matching rules** with exact match, prefix match, and fuzzy fallback
- **Cost calculation** logic with per-token-type itemization
- **Long-context premium** rules for Opus 4.x and Sonnet 4.x models

**Key APIs:**
- `resolve_pricing(model: str | None) -> ModelPricing`
- `calculate_cost(...) -> CostBreakdown`
- `supports_long_context_premium(model: str | None) -> bool`

### 2. Token Field Aliases (`token_aliases.py`)

Different API providers use different field names for the same token types:
- `cache_creation_input_tokens` → `cache_write_tokens`
- `cache_read_input_tokens` → `cache_read_tokens`
- `cache_creation_tokens` → `cache_write_tokens`

This module provides **explicit normalization** instead of silent proxy-based mapping.

**Key APIs:**
- `normalize_token_fields(raw: dict) -> NormalizedTokenFields`
- `CACHE_CREATION_ALIASES` - frozen set of all cache write aliases
- `CACHE_READ_ALIASES` - frozen set of all cache read aliases

### 3. Provider Resolution (`models.py`)

Determines whether a conversation/request is "claude" or "codex" based on:
1. Explicit provider field
2. Project path prefix (`codex:` prefix)
3. Model identifier heuristics
4. Default to "claude"

**Key APIs:**
- `resolve_provider(model=..., provider=..., project_path=...) -> ProviderIdentifier`

## Contract Drift Removal

This package addresses the following unsound contract edges:

### Cache Token Field Normalization

**Before:** The frontend used a JavaScript Proxy to silently normalize `cache_creation_input_tokens` and `cache_read_input_tokens` into `cache_write_tokens` and `cache_read_tokens`. This hid transport drift and made it easy for backend and frontend semantics to diverge.

**After:** The backend now has explicit, tested normalization logic in `token_aliases.py`. The frontend can eventually remove its proxy-based normalization once transport is stabilized.

**Test Coverage:** See `test_semantics.py::TestContractDriftRemoval` for explicit regression tests.

## Usage

### In Analytics Code

```python
from helaicopter_semantics import (
    calculate_cost,
    resolve_pricing,
    resolve_provider,
    supports_long_context_premium,
)

# Resolve provider from metadata
provider = resolve_provider(
    model="gpt-5",
    provider="claude",
    project_path="codex:-Users-tony-Code-helaicopter"
)  # Returns "codex"

# Calculate cost
cost = calculate_cost(
    input_tokens=100_000,
    output_tokens=50_000,
    cache_write_tokens=10_000,
    cache_read_tokens=5_000,
    model="claude-sonnet-4-5-20250929",
)

# Check long-context premium eligibility
if conversation.total_input_tokens > 200_000 and supports_long_context_premium(model):
    premium = cost.input_cost + (cost.output_cost * 0.5) + ...
```

### In Ingestion Code

```python
from helaicopter_semantics import normalize_token_fields

# Normalize raw API response
raw_usage = {
    "input_tokens": 100_000,
    "output_tokens": 50_000,
    "cache_creation_input_tokens": 10_000,  # Historical alias
    "cache_read_input_tokens": 5_000,  # Historical alias
}

normalized = normalize_token_fields(raw_usage)
# Returns:
# {
#     "input_tokens": 100_000,
#     "output_tokens": 50_000,
#     "cache_write_tokens": 10_000,
#     "cache_read_tokens": 5_000,
# }
```

## Testing

See `tests/test_semantics.py` for comprehensive test coverage:

- Pricing table accuracy
- Model matching rules (exact, prefix, fuzzy)
- Cost calculation correctness
- Long-context premium rules
- Token alias normalization
- Provider resolution heuristics
- Contract drift removal verification

All 25 tests pass and provide golden test coverage for semantic correctness.

## Future Work

This package is the **Phase 1** foundation. Future phases will:

1. **Phase 2:** Add ingestion adapters that use `normalize_token_fields()` before persistence
2. **Phase 3:** Add orchestration status vocabulary mapping (currently in `helaicopter_domain.vocab`)
3. **Phase 4:** Remove frontend business logic duplication and normalization proxies
