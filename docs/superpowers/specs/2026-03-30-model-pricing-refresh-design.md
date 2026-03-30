# Model Pricing Refresh Design

## Goal

Refresh Helaicopter's Codex and Claude pricing references to match current official pricing, while preserving compatibility for historical model IDs already present in stored analytics data.

## Current Context

The repo currently keeps pricing logic in four places:

- `python/helaicopter_semantics/pricing.py` as the canonical backend table
- `python/helaicopter_api/pure/pricing.py` as a deprecated compatibility mirror
- `src/lib/constants.ts` as the frontend pricing mirror
- `src/lib/pricing.ts` and `src/app/pricing/page.tsx` as the frontend matching and explanation layer

Tests already cover canonical pricing resolution, compatibility behavior, and frontend cost calculations.

## External Pricing Facts

As of March 30, 2026, the official sources used for this refresh show:

- OpenAI's API pricing page lists `GPT-5.4`, `GPT-5.4 mini`, and `GPT-5.4 nano` with token pricing and cached-input pricing.
- OpenAI's Codex pricing page lists `GPT-5.4`, `GPT-5.4-mini`, and `GPT-5.3-Codex` as current Codex-facing models, and states API-key usage is billed on standard API pricing.
- Anthropic's March 13, 2026 1M context GA announcement states that Opus 4.6 and Sonnet 4.6 now use standard pricing across the full 1M context window with no long-context premium.

## Recommended Approach

Update the pricing layer in place instead of redesigning it:

1. Keep existing legacy model entries so historical analytics continue to resolve deterministically.
2. Add current GPT-5.4 family entries needed for current Codex/OpenAI model names.
3. Update fuzzy matching so generic `sonnet` resolves to the latest tracked Sonnet model and GPT-5.4 mini/nano aliases resolve correctly.
4. Remove long-context premium behavior for Claude 4.6 models and update pricing-page copy so it no longer claims a blanket Claude premium.
5. Refresh tests first, then implementation, then page copy.

## Non-Goals

- Reworking the overall pricing architecture
- Removing legacy model aliases that may still appear in historical data
- Switching cost estimation away from API-style token pricing
- Repricing older Claude 4.0/4.5 historical entries beyond what the current repo needs for compatibility

## Files In Scope

- `python/helaicopter_semantics/pricing.py`
- `python/helaicopter_api/pure/pricing.py`
- `src/lib/constants.ts`
- `src/lib/pricing.ts`
- `src/app/pricing/page.tsx`
- `tests/test_semantics.py`
- `tests/test_pricing_compat.py`
- `src/lib/pricing.test.ts`
- `python/helaicopter_semantics/README.md`

## Design Decisions

### Canonical pricing stays Python-first

The backend semantic table remains the source of truth. The deprecated pure helper and the frontend constants file are updated to mirror it so existing callers stay stable.

### Legacy entries remain available

Entries like `gpt-5.2`, `gpt-5.1`, and dated Claude IDs remain in the tables because stored usage data may still reference them. "Latest versions" means adding current entries and updating latest-family resolution, not deleting historical compatibility.

### Claude long-context handling becomes model-specific

The repo currently treats both Opus 4.6 and Sonnet 4.x as premium candidates. That is no longer correct for current 4.6 models. The premium helpers should stop applying to Opus 4.6 and Sonnet 4.6 and the pricing page should explicitly call out that 1M context is standard-price for those models.

### UI copy should describe current behavior, not stale assumptions

The pricing page currently presents a universal Claude premium table and caveats that contradict current Anthropic announcements. The page should instead:

- show current Claude and OpenAI/Codex tables
- mention GPT-5.4 mini and nano where present
- explain that Opus 4.6 and Sonnet 4.6 have no long-context premium
- avoid claiming a general Claude long-context surcharge

## Testing Strategy

- Python: update pricing-resolution and long-context tests in `tests/test_semantics.py` and `tests/test_pricing_compat.py`
- Frontend: update `src/lib/pricing.test.ts` for the new model aliases and for removal of the 4.6 premium assumption
- Verification commands:
  - `uv run pytest tests/test_semantics.py tests/test_pricing_compat.py -q`
  - `node --import tsx --test src/lib/pricing.test.ts`

## Risks

- Fuzzy matching could accidentally reroute historical `sonnet` strings to the wrong pricing bucket if aliases are changed carelessly.
- Frontend copy can drift from backend logic if we update tables without updating the explanatory page.
- Codex/OpenAI naming is split across product and API pages, so the implementation should preserve legacy aliases while adding current GPT-5.4 family names.
